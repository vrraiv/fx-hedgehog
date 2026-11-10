# ADR-0012: Hedge optimizer formulation and solver (scipy, not cvxpy)

**Status:** accepted, 2026-11-06

## Context

Choose hedge ratios ``h_c`` in [0, 1] per currency to minimise expected hedging cost
subject to the portfolio Expected Shortfall at 21 days / 99% staying within a budget,
with an optional turnover penalty and a minimum ticket. The two natural Python tools are
``scipy.optimize`` and ``cvxpy``.

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

**Solver: scipy SLSQP, on an exact smooth form of the problem.** Absolute values and a
square root are not differentiable where the optimum often sits (no trade, full hedge),
so they are removed without approximation: ``h >= 0`` makes the spread term linear; the
turnover term is split as ``h = h_prev + u - v`` with ``u, v >= 0``, which turns
``|h - h_prev|`` into ``u + v``; the ES constraint is written ``1 - (ES / budget)^2 >= 0``,
a quadratic. The solver gets exact gradients, the linear objective is scaled so its
largest gradient entry is one, and a zero budget returns the full hedge directly. Twenty
variables, one constraint, box bounds; solves in a few milliseconds, which matters for
the frontier (30 solves) and the backtest (140 months). An earlier version smoothed the
absolute value (``sqrt(x^2 + eps)``) and used finite-difference gradients; run side by
side over the 142 backtest months the exact form is never worse and finds a cheaper
optimum in two of them. cvxpy would express the SOCP more declaratively but pulls in a solver stack
(OSQP/SCS/Clarabel) for a problem that does not need it, and SLSQP's result is checked
against hand-derived cases in ``tests/test_optimizer.py``: cheaper currencies are hedged
first, symmetric problems give equal ratios, negative-carry currencies are hedged fully
even with slack budget, short exposures are bought forward, the frontier is monotone,
and on random problems with a turnover penalty no sampled feasible point has a lower
total cost than the solution.
A tiny solver infeasibility (1e-6 relative) is removed by scaling the residual exposure
down along a line search.

**Minimum ticket** is non-convex (a notional is zero or at least the ticket) and is
applied as a post-step: sub-ticket hedges are set to zero and kept out only if the ES
budget still holds.

**Turnover penalty** (``turnover_penalty_bp``, 10 bp of the notional changed in the
default configuration) is a regulariser in the objective only, not a realized cost: the
backtest rolls one-month forwards, so the full notional is re-dealt each month and the
bid-ask term already prices the trading. With a hard ES constraint and linear costs the
optimum is bang-bang: when the budget binds, the whole of it goes to whichever currency
buys risk reduction most cheaply that month, and small changes in volatility move it
between MXN and AUD. The penalty states a preference for a stable programme, and its
size was chosen by measuring the trade-off over the 2015-2026 backtest:

| penalty | monthly ratio jumps > 0.5 | mean monthly ratio change | total P&L (USD m) | P&L vol (USD m / yr) | hedging cost (USD m / yr) |
|---|---|---|---|---|---|
| 2 bp | 35 | 0.34 | -6.6 | 4.61 | -0.89 |
| 5 bp | 28 | 0.30 | -6.1 | 4.59 | -0.89 |
| 10 bp | 24 | 0.26 | -6.6 | 4.59 | -0.88 |
| 20 bp | 19 | 0.22 | -7.0 | 4.58 | -0.87 |

Smoothing is free in outcomes over this range; 10 bp removes a third of the large jumps.
A no-trade band would remove more but adds logic to the optimizer and is not needed for
the conclusions. The penalty is measured against the previous month's ratios, which the
hedge stage reads from the policy backtest's last rebalance (the backtest therefore runs
first).

## Consequences

* The frontier (``reports/figures/hedge_frontier.png``) is the locus of optimal (ES,
  cost) pairs as the budget sweeps from zero to the unhedged ES.
* Carry drives the answer: with USD rates above most G10 rates in 2026, hedging EUR,
  GBP, CAD, JPY, CHF *earns* carry and the optimizer hedges them fully regardless of the
  budget; the budget then decides how much of the costly BRL, MXN, INR and AUD risk to
  buy down.
