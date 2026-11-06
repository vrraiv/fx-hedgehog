# ADR-0012: Hedge optimizer formulation and solver (scipy, not cvxpy)

**Status:** accepted, 2026-11-06

## Context

Choose hedge ratios ``h_c`` in [0, 1] per currency to minimise expected hedging cost
subject to the portfolio Expected Shortfall at 21 days / 99% staying within a budget,
with an optional turnover penalty and a minimum ticket. The brief allows
``scipy.optimize`` or ``cvxpy`` and asks for the choice to be justified.

## Decision

**Formulation** (``fx_treasury_risk/hedge/optimizer.py``):

    min_h  sum_c h_c E_c c_c tau + sum_c s_c |h_c E_c| + lam sum_c |h_c - h_prev_c| |E_c|
    s.t.   k(nu, alpha) * sqrt( w' Sigma_h w ) <= budget,   w = (1 - h) o E,   0 <= h <= 1

* ``E_c`` signed USD exposure, ``c_c = (S - F)/S * 365/days`` the annualized hedge cost
  rate for a long exposure (so ``E_c c_c`` has the right sign for short exposures too),
  ``s_c`` the one-way spread, ``tau`` the tenor in years.
* ES under the variance-matched Student-t of the risk engine is ``k * sigma`` with ``k``
  a closed-form multiplier, so the constraint is a Euclidean norm of an affine function
  of ``h``: convex. The objective is linear plus absolute values: convex. Hence every
  local optimum is global and a general-purpose NLP solver is enough.

**Solver: scipy SLSQP.** Ten variables, one smooth constraint, box bounds; solves in a
few milliseconds, which matters for the frontier (30 solves) and the backtest (140
months). cvxpy would express the SOCP more declaratively but pulls in a solver stack
(OSQP/SCS/Clarabel) for a problem that does not need it, and SLSQP's result is checked
against hand-derived cases in ``tests/test_optimizer.py``: cheaper currencies are hedged
first, symmetric problems give equal ratios, negative-carry currencies are hedged fully
even with slack budget, short exposures are bought forward, the frontier is monotone.
A tiny solver infeasibility (1e-6 relative) is removed by scaling the residual exposure
down along a line search.

**Minimum ticket** is non-convex (a notional is zero or at least the ticket) and is
applied as a post-step: sub-ticket hedges are set to zero and kept out only if the ES
budget still holds.

**Turnover penalty** is available (``turnover_penalty_bp``) but set to zero in the
default configuration: the backtest rolls one-month forwards, so the full notional is
re-dealt each month and the bid-ask term already prices the trading.

## Consequences

* The frontier (``reports/figures/hedge_frontier.png``) is the locus of optimal (ES,
  cost) pairs as the budget sweeps from zero to the unhedged ES.
* Carry drives the answer: with USD rates above most G10 rates in 2026, hedging EUR,
  GBP, CAD, JPY, CHF *earns* carry and the optimizer hedges them fully regardless of the
  budget; the budget then decides how much of the costly BRL, MXN, INR and AUD risk to
  buy down.
