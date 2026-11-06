# ADR-0010: VaR/ES backtest design

**Status:** accepted, 2026-11-06

## Context

Coverage tests need a long out-of-sample series of one-day forecasts along the actual
exposure path. Choices: which methods to run daily, how the tail index is refitted, what
null distribution the ES tests simulate from, and how to summarise.

## Decision

* **Out of sample from 2015-01-02** to the last FX date, daily, one-day horizon, on the
  group net exposure held at the previous close. Realised loss is
  `-sum_c w_{t-1,c} (exp(r_{t,c}) - 1)`.
* **Methods in the daily backtest:** historical simulation (rolling 1,000-day window,
  P&L recomputed with the current weights), normal with rolling sample covariance, normal
  with EWMA(0.94), Student-t with EWMA(0.94) and the tail index refitted every 21 days.
  The t-copula Monte Carlo is excluded: for a linear portfolio at a one-day horizon with
  the same EWMA correlations and a t copula it has the same distribution as `t_ewma` to
  within simulation noise, so it would cost minutes per run and add nothing.
* **VaR tests:** Kupiec proportion of failures, Christoffersen independence, their sum as
  conditional coverage (chi-square with 2 d.f.), and the Basel traffic light on the last
  250 days at 99%.
* **ES tests:** Acerbi-Szekely Z1 (conditional on exceptions) and Z2 (unconditional),
  written in losses so that a *positive* Z means realised tail losses exceeded the ES.
  P-values come from 1,000 simulations of the whole out-of-sample path under the model's
  own daily predictive distribution (normal or t with that day's sigma; a bootstrap of
  the rolling window for historical simulation). One-sided: the p-value is the share of
  simulated paths with Z at least as large as observed.
* **Verdict:** PASS if Kupiec, Christoffersen, conditional coverage and Z2 all have
  p >= 0.05, else FAIL. Z1 is reported but not used in the verdict because it assumes
  the VaR is correct, which the other tests check separately.
* **Multi-day horizons** are not formally backtested: overlapping 10- and 21-day windows
  violate the independence the tests assume, and non-overlapping blocks leave too few
  observations (about 140 at 21 days) for the 99% tests to have power. The report shows
  10/21-day numbers with that caveat.

## Consequences

* Results are stored in `var_backtest_results` with one row per (method, confidence)
  and surfaced in the decision report with the verdict column.
* Running the backtest takes about a minute, dominated by the ES simulations.
