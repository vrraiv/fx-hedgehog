# ADR-0009: Risk engine choices (windows, horizons, tails, Monte Carlo)

**Status:** accepted, 2026-11-06

## Context

The engine reports VaR and ES at 95/99% over 1, 10 and 21 days by historical simulation,
parametric normal and Student-t, and a t-copula Monte Carlo, on sample, EWMA (0.94 and
0.97) and Ledoit-Wolf covariances: a deliberately wide set, so that the choice of model
is made by the coverage backtest (ADR-0010) rather than assumed. Several details
remain: estimation window, how to
reach multi-day horizons, where the tail index comes from, and how exposure enters.

## Decision

* **Linear P&L in USD:** `P&L = sum_c E_c (exp(r_c) - 1)` with `E_c` the USD value of
  the net exposure in currency `c` and `r_c` the log return of `usd_per_fcy`. Exposure is
  held fixed over the horizon (a treasury measures the risk of today's book).
* **Window:** 1,000 trading days (about four years) for the historical simulation, the
  sample covariance and the Ledoit-Wolf estimator. EWMA uses the full history with the
  recursion initialised from the first 60 days.
* **Horizons:** historical simulation uses *overlapping* h-day log returns over the
  window (more observations than non-overlapping blocks; the dependence between
  overlapping observations widens the sampling error of the quantile, which the report
  notes). Parametric methods scale daily volatility by `sqrt(h)`. Monte Carlo simulates
  `h` independent daily steps and compounds them, so fat tails are not scaled by
  `sqrt(h)` but diversified across days as they should be.
* **Student-t:** degrees of freedom fitted by maximum likelihood on the standardised
  portfolio return over the window, clipped to [2.5, 100]; the t distribution is scaled
  so that its variance matches the covariance-implied `sigma^2`. ES uses the closed form
  `sigma_s f(q) (nu + q^2) / ((nu - 1)(1 - alpha))`.
* **Monte Carlo:** t-copula with the copula degrees of freedom set to the median of the
  per-currency marginal fits, marginal Student-t with per-currency degrees of freedom,
  EWMA volatilities and correlations, 20,000 paths, fixed seed. Both EWMA lambdas are
  run so the sensitivity to decay is visible.
* **Ledoit-Wolf** is implemented from the 2004 paper (identity target) in thirty lines
  rather than imported from scikit-learn, to avoid a large dependency for one function
  and so the estimator can be read and tested (`tests/test_risk.py`).
* **Stress:** five historical replays (CHF 2015, Brexit 2016, March 2020, the 2022 USD
  surge, the 2013 taper tantrum as the EM episode) and four hypothetical shocks. The
  hypothetical shocks name a subset of currencies and propagate to the rest by the
  Gaussian conditional expectation under the sample covariance of the last 1,000 days;
  the unpropagated variant is reported next to it, and each propagated row lists its
  three largest implied moves, so the effect of the correlation assumption is visible.
  The covariance was EWMA(0.94) until a sanity check showed a +10% JPY shock implying
  BRL +11%: a month-long memory produced a beta above one that the 1,000-day sample
  (BRL +1.7%) and Ledoit-Wolf (the same) do not support. Stress scenarios should rest
  on through-the-cycle co-movement; the VaR models are where recent volatility belongs.
* **Tidy output:** every estimate is a row with `method`, `cov_method`, `horizon_days`,
  `confidence`, `params`, `var_usd`, `es_usd`, `basis` (net or net of hedges) and
  `as_of`, stored in DuckDB as `risk_results` and `stress_results`.

## Consequences

* Methods are comparable in one table; the decision report shows the spread across
  methods as a model-risk band rather than a single number.
* The Monte Carlo is the slowest component (about 30 seconds for the full table); the
  daily backtest therefore excludes it (ADR-0010).
