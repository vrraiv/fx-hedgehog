"""Hedge-ratio optimizer: minimise expected hedging cost subject to an ES budget.

Problem (ADR-0012)::

    min_h   sum_c h_c E_c c_c tau                (expected carry over the horizon)
          + sum_c s_c |h_c E_c|                  (bid-ask on the notional dealt)
          + lam * sum_c |h_c - h_prev_c| |E_c|   (optional turnover penalty)
    s.t.    ES_alpha( sum_c (1 - h_c) E_c r_c ) <= budget
            0 <= h_c <= 1

with ``E_c`` the signed USD exposure (positive = long), ``c_c`` the annualized hedge
cost rate for a long exposure (``(S - F)/S * 365/days``), ``tau`` the horizon in years,
``s_c`` the one-way spread, and ``r_c`` the horizon log return. Under the variance-matched
Student-t used by the risk engine, ``ES = k * sqrt(w' Sigma_h w)`` with ``w = (1-h) E``,
which is a norm of an affine function of ``h``: the constraint set is convex and the
objective is convex (linear plus absolute values), so any local optimum is global.

The problem is handed to the solver in a smooth, exact form. ``h >= 0`` makes the spread
term linear. The turnover term is split in the standard way, ``h = h_prev + u - v`` with
``u, v >= 0``, so ``|h - h_prev|`` becomes ``u + v`` at the optimum and the objective is
linear in ``(u, v)``. The ES constraint is written as ``1 - (ES / budget)^2 >= 0``, a
quadratic that is differentiable everywhere, including at the full hedge where the
square root is not. ``scipy.optimize.minimize`` (SLSQP) gets exact gradients for both;
there are twenty variables and one constraint.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import optimize, stats


def es_multiplier(nu: float, alpha: float) -> float:
    """ES per unit of standard deviation for a variance-matched Student-t.

    ``k = sqrt((nu-2)/nu) * f_nu(q) * (nu + q^2) / ((nu - 1)(1 - alpha))`` with ``q`` the
    ``alpha`` quantile of ``t_nu``; for ``nu -> inf`` this tends to ``phi(z)/(1-alpha)``.
    """
    q = stats.t.ppf(alpha, nu)
    return float(
        np.sqrt((nu - 2) / nu) * stats.t.pdf(q, nu) * (nu + q**2) / ((nu - 1) * (1 - alpha))
    )


@dataclass(frozen=True)
class HedgeProblem:
    """Everything the optimizer needs for one rebalance date."""

    ccys: list[str]
    exposure_usd: np.ndarray  # signed, USD
    cov_daily: np.ndarray  # daily log-return covariance, k x k
    horizon_days: int
    confidence: float
    nu: float
    es_budget_usd: float
    cost_rate: np.ndarray  # annualized hedge cost rate for a long exposure, fraction
    spread_bp: np.ndarray  # one-way bid-ask, basis points of notional
    tenor_days: int

    @property
    def k_es(self) -> float:
        """ES multiplier for this confidence and tail index."""
        return es_multiplier(self.nu, self.confidence)

    @property
    def k_var(self) -> float:
        """VaR per unit of standard deviation for the variance-matched Student-t."""
        return float(np.sqrt((self.nu - 2) / self.nu) * stats.t.ppf(self.confidence, self.nu))

    @property
    def cov_horizon(self) -> np.ndarray:
        """Covariance of horizon log returns (sqrt-time scaling)."""
        return self.cov_daily * self.horizon_days

    def residual_es(self, h: np.ndarray) -> float:
        """ES of the hedged book in USD for hedge ratios ``h``."""
        w = self.exposure_usd * (1 - h)
        return float(self.k_es * np.sqrt(max(w @ self.cov_horizon @ w, 0.0)))

    def residual_var(self, h: np.ndarray) -> float:
        """VaR of the hedged book in USD for hedge ratios ``h``."""
        w = self.exposure_usd * (1 - h)
        return float(self.k_var * np.sqrt(max(w @ self.cov_horizon @ w, 0.0)))

    def carry_cost(self, h: np.ndarray) -> float:
        """Expected carry cost over one tenor, USD (positive = cost)."""
        return float(np.sum(h * self.exposure_usd * self.cost_rate * self.tenor_days / 365))

    def spread_cost(self, h: np.ndarray) -> float:
        """Bid-ask paid on the notional dealt, USD."""
        return float(np.sum(self.spread_bp / 1e4 * np.abs(h * self.exposure_usd)))


@dataclass(frozen=True)
class HedgeSolution:
    """Optimal ratios and the numbers behind them."""

    ratios: pd.Series  # by ccy, in [0, 1]
    notional_usd: pd.Series  # signed; negative = currency sold forward
    residual_es_usd: float
    unhedged_es_usd: float
    carry_cost_usd: float  # per tenor
    spread_cost_usd: float
    turnover_cost_usd: float
    budget_usd: float
    binding: bool
    status: str


def _solve(
    prob: HedgeProblem, prev: np.ndarray, lam: float, start: np.ndarray | None
) -> tuple[np.ndarray, str]:
    """Optimal ratios for a positive budget, before the minimum-ticket rule."""
    k = len(prob.ccys)
    e = prob.exposure_usd
    abs_e = np.abs(e)
    base = np.clip(prev, 0.0, 1.0)  # h = base + u - v
    # cost per unit of hedge ratio: carry over the tenor plus spread on the notional
    unit_cost = e * prob.cost_rate * prob.tenor_days / 365 + prob.spread_bp / 1e4 * abs_e
    turn = lam * abs_e
    grad_obj = np.concatenate([unit_cost + turn, -unit_cost + turn])
    # the objective is linear, so its scale is free: make the largest gradient entry one
    grad_obj = grad_obj / max(float(np.abs(grad_obj).max()), 1e-12)
    cov = prob.cov_horizon * (prob.k_es / prob.es_budget_usd) ** 2  # so ES/budget = sqrt(w'cov w)

    def ratios(x: np.ndarray) -> np.ndarray:
        out: np.ndarray = base + x[:k] - x[k:]
        return out

    def slack(x: np.ndarray) -> float:
        w = e * (1 - ratios(x))
        return float(1.0 - w @ cov @ w)

    def slack_grad(x: np.ndarray) -> np.ndarray:
        g = 2.0 * e * (cov @ (e * (1 - ratios(x))))  # d slack / d h
        return np.concatenate([g, -g])

    h0 = np.full(k, 0.5) if start is None else base
    x0 = np.concatenate([np.maximum(h0 - base, 0.0), np.maximum(base - h0, 0.0)])
    res = optimize.minimize(
        lambda x: float(grad_obj @ x),
        x0,
        jac=lambda x: grad_obj,
        method="SLSQP",
        bounds=[(0.0, float(b)) for b in np.concatenate([1 - base, base])],
        constraints=[{"type": "ineq", "fun": slack, "jac": slack_grad}],
        options={"maxiter": 500, "ftol": 1e-12},
    )
    h = np.clip(ratios(res.x), 0.0, 1.0)
    # tiny infeasibility from the solver tolerance: scale the residual down proportionally
    if prob.residual_es(h) > prob.es_budget_usd * (1 + 1e-6):
        u = 1 - h
        lo, hi = 0.0, 1.0
        for _ in range(60):
            mid = 0.5 * (lo + hi)
            if prob.residual_es(1 - u * mid) <= prob.es_budget_usd:
                lo = mid
            else:
                hi = mid
        h = 1 - u * lo
    return h, str(res.message)


def optimize_hedge(
    prob: HedgeProblem,
    h_prev: np.ndarray | None = None,
    turnover_penalty_bp: float = 0.0,
    min_ticket_usd: float = 0.0,
) -> HedgeSolution:
    """Solve the problem; apply the minimum-ticket rule afterwards.

    Minimum ticket is non-convex (a notional is either zero or at least the ticket), so
    it is applied as a post-step: notionals below the ticket are set to zero and the ES
    is recomputed. If that breaks the budget the small hedges are kept.
    """
    k = len(prob.ccys)
    e = prob.exposure_usd
    prev = np.zeros(k) if h_prev is None else np.asarray(h_prev, dtype=float)
    lam = turnover_penalty_bp / 1e4
    if prob.es_budget_usd <= 0:
        h, status = np.ones(k), "zero budget: full hedge"
    else:
        h, status = _solve(prob, prev, lam, start=None if h_prev is None else prev)

    if min_ticket_usd > 0:
        small = (np.abs(h * e) < min_ticket_usd) & (h > 0)
        trial = h.copy()
        trial[small] = 0.0
        if prob.residual_es(trial) <= prob.es_budget_usd * (1 + 1e-6):
            h = trial

    notional = -h * e
    res_es = prob.residual_es(h)
    return HedgeSolution(
        ratios=pd.Series(h, index=prob.ccys),
        notional_usd=pd.Series(notional, index=prob.ccys),
        residual_es_usd=res_es,
        unhedged_es_usd=prob.residual_es(np.zeros(k)),
        carry_cost_usd=prob.carry_cost(h),
        spread_cost_usd=prob.spread_cost(h),
        turnover_cost_usd=float(lam * np.sum(np.abs(h - prev) * np.abs(e))),
        budget_usd=prob.es_budget_usd,
        binding=bool(res_es >= prob.es_budget_usd * (1 - 1e-3)),
        status=status,
    )


def frontier(
    prob: HedgeProblem,
    n_points: int = 25,
    h_prev: np.ndarray | None = None,
    turnover_penalty_bp: float = 0.0,
    min_ticket_usd: float = 0.0,
) -> pd.DataFrame:
    """Cost-vs-residual-risk frontier by sweeping the ES budget from zero to unhedged.

    Returns one row per budget with the optimal residual ES, carry and spread cost (per
    tenor and annualized) and the hedge ratios.
    """
    unhedged = prob.residual_es(np.zeros(len(prob.ccys)))
    budgets = np.linspace(0.0, unhedged, n_points)
    rows = []
    for b in budgets:
        p = HedgeProblem(**{**prob.__dict__, "es_budget_usd": float(b)})
        sol = optimize_hedge(p, h_prev, turnover_penalty_bp, min_ticket_usd)
        per_year = 365 / prob.tenor_days
        rows.append(
            {
                "budget_usd": float(b),
                "residual_es_usd": sol.residual_es_usd,
                "carry_cost_usd": sol.carry_cost_usd,
                "spread_cost_usd": sol.spread_cost_usd,
                "total_cost_usd": sol.carry_cost_usd + sol.spread_cost_usd,
                "annual_cost_usd": (sol.carry_cost_usd + sol.spread_cost_usd) * per_year,
                "mean_ratio": float(sol.ratios.mean()),
                **{f"h_{c}": float(sol.ratios[c]) for c in prob.ccys},
            }
        )
    return pd.DataFrame(rows)
