"""GARCH(1,1) volatilities per currency, combined with EWMA correlations.

Each currency's daily variance follows ``h_{t+1} = omega + a r_t^2 + b h_t``. The model is
fitted by Gaussian quasi-maximum likelihood with variance targeting
(``omega = s^2 (1 - a - b)`` with ``s^2`` the sample variance of the fit window), which
leaves two parameters and keeps the unconditional variance at its sample value. The
search runs over ``(logit(a + b), logit(a / (a + b)))``, so every trial point satisfies
``a, b >= 0`` and ``a + b < 1`` without constraints. Tails are left to the Student-t that
the risk engine fits on the portfolio, so the Gaussian likelihood only has to locate the
variance dynamics, which it does consistently (Bollerslev & Wooldridge, 1992).

Fits that do not converge keep the previous parameters and are counted, so a backtest
can report how often that happened. Correlations come from the EWMA covariance, so the
covariance ``D_t R_t D_t`` plugs into the same ES formula as every other estimator.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import optimize, signal

# Starting point and fallback before any fit has converged: RiskMetrics-like dynamics,
# kept just inside stationarity so the variance target stays meaningful.
DEFAULT_PARAMS: tuple[float, float] = (0.05, 0.93)
MAX_PERSISTENCE = 0.999


@dataclass(frozen=True)
class GarchFit:
    """Outcome of one univariate fit."""

    alpha: float
    beta: float
    target_var: float
    converged: bool


def filter_variance(r: np.ndarray, alpha: float, beta: float, target_var: float) -> np.ndarray:
    """Conditional variances ``h_0..h_n`` for returns ``r_0..r_{n-1}``.

    ``h_0`` is the target; ``h[t]`` is the forecast for ``r_t`` made after ``r_{t-1}``, and
    the last element is the forecast for the day after the sample.
    """
    omega = target_var * (1 - alpha - beta)
    v = omega + alpha * np.asarray(r, dtype=float) ** 2
    y, _ = signal.lfilter([1.0], [1.0, -beta], v, zi=[beta * target_var])
    return np.concatenate([[target_var], y])


def _unpack(x: np.ndarray) -> tuple[float, float]:
    persistence = MAX_PERSISTENCE / (1 + np.exp(-x[0]))
    share = 1 / (1 + np.exp(-x[1]))
    return float(persistence * share), float(persistence * (1 - share))


def _pack(alpha: float, beta: float) -> np.ndarray:
    eps = 1e-6  # a previous fit can sit on a boundary; start just inside it
    p = float(np.clip((alpha + beta) / MAX_PERSISTENCE, eps, 1 - eps))
    s = float(np.clip(alpha / max(alpha + beta, eps), eps, 1 - eps))
    return np.array([np.log(p / (1 - p)), np.log(s / (1 - s))])


def fit_garch(r: np.ndarray, start: tuple[float, float] = DEFAULT_PARAMS) -> GarchFit:
    """Gaussian QMLE of a variance-targeted GARCH(1,1) on zero-mean returns ``r``."""
    x = np.asarray(r, dtype=float)
    target = float(np.mean(x**2))

    def nll(theta: np.ndarray) -> float:
        a, b = _unpack(theta)
        h = filter_variance(x, a, b, target)[:-1]
        return float(0.5 * np.sum(np.log(h) + x**2 / h))

    res = optimize.minimize(
        nll, _pack(*start), method="Nelder-Mead", options={"xatol": 1e-4, "fatol": 1e-6}
    )
    if not res.success or not np.isfinite(res.fun):
        return GarchFit(start[0], start[1], target, converged=False)
    a, b = _unpack(res.x)
    return GarchFit(a, b, target, converged=True)


@dataclass(frozen=True)
class GarchPath:
    """Daily GARCH volatilities and the fit record behind them."""

    vol: np.ndarray  # (n, k): forecast for day t+1 made after row t
    n_fits: int
    n_failed: int
    params: np.ndarray  # (n_refits, k, 2) alpha, beta used in each block


def garch_vol_path(
    r: np.ndarray, window: int = 1000, min_obs: int = 500, refit_every: int = 21
) -> GarchPath:
    """Out-of-sample GARCH volatilities along the sample, refitted every ``refit_every`` rows.

    The parameters used for rows ``t0 .. t0 + refit_every - 1`` are fitted on rows up to
    ``t0`` only (the last ``window`` of them), so the path has no look-ahead. Rows before
    ``min_obs`` are NaN. Each refit starts from the previous parameters.
    """
    n, k = r.shape
    vol = np.full((n, k), np.nan)
    prev = [DEFAULT_PARAMS] * k
    n_fits = n_failed = 0
    used: list[np.ndarray] = []
    for t0 in range(min_obs - 1, n, refit_every):
        s0 = max(0, t0 - window + 1)
        t1 = min(n, t0 + refit_every)
        block = np.empty((k, 2))
        for j in range(k):
            fit = fit_garch(r[s0 : t0 + 1, j], prev[j])
            n_fits += 1
            n_failed += not fit.converged
            prev[j] = (fit.alpha, fit.beta)
            block[j] = prev[j]
            h = filter_variance(r[s0:t1, j], fit.alpha, fit.beta, fit.target_var)
            # h[i + 1] is the forecast after row s0 + i
            vol[t0:t1, j] = np.sqrt(h[t0 - s0 + 1 : t1 - s0 + 1])
        used.append(block)
    return GarchPath(vol, n_fits, n_failed, np.array(used))
