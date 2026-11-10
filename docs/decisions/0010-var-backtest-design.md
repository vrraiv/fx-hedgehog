# ADR-0010: VaR/ES backtest design

**Status:** accepted, 2026-11-06

## Context

Coverage tests need a long out-of-sample series of one-day forecasts along the actual
exposure path. Choices: which methods to run daily, how the tail index is refitted, what
null distribution the ES tests simulate from, how to summarise, and how to choose the
model the optimizer uses without choosing it on the data that then tests it.

## Decision

* **Two windows.** Model *selection* on 2012-01 to 2014-12; *evaluation* from 2015-01-02
  to the last FX date. Daily, one-day horizon, on the group net exposure held at the
  previous close. Realised loss is `-sum_c w_{t-1,c} (exp(r_{t,c}) - 1)`. Data start in
  January 2010, so rolling estimators use all available history (at least 500 days) until
  a full 1,000-day window exists; from 2015 every window is full.
* **Methods in the daily backtest:** historical simulation (rolling 1,000-day window,
  P&L recomputed with the current weights), normal with rolling sample covariance, normal
  with EWMA(0.94), Student-t with EWMA(0.94) or EWMA(0.97), and Student-t with GARCH(1,1)
  volatilities and EWMA(0.94) correlations; every Student-t refits its tail index every
  21 days. GARCH is fitted per currency by Gaussian quasi-maximum likelihood with variance
  targeting (two free parameters, searched in a transformed space that enforces
  stationarity), refitted every 21 days on the trailing window and warm-started from the
  previous fit; a fit that fails to converge keeps the previous parameters and is counted
  in the report. On the 2010-2026 data all 1,770 fits converge. A handful are degenerate:
  for CHF the January 2015 floor removal stays in the window for four years and the
  likelihood then prefers low persistence, and some EUR and INR fits sit at the
  persistence bound of 0.999 (integrated, EWMA-like dynamics).
* **Selection rule:** the lowest mean FZ0 score (Patton, Ziegel & Chen, 2019) at 99% on
  the selection window, among the models the optimizer can use (those expressible as
  `k * sqrt(w' Sigma w)`, so not historical simulation). FZ0 is strictly consistent for
  VaR and ES jointly and uses every day, where an exception count over three years would
  rest on about seven events. A Diebold-Mariano test against the selected model reports
  whether the ranking is meaningful. The selected model is reported next to the one the
  configuration uses, and the report flags a mismatch rather than silently switching.
* The t-copula Monte Carlo is excluded: for a linear portfolio at a one-day horizon with
  the same EWMA correlations and a t copula it has the same distribution as `t_ewma` to
  within simulation noise, so it would cost minutes per run and add nothing.
* **VaR tests:** Kupiec proportion of failures, Christoffersen independence, their sum as
  conditional coverage (chi-square with 2 d.f.), and the Basel traffic light on the last
  250 days at 99%. The number of back-to-back exceptions is reported beside the
  Christoffersen p-value: at 99% with about 30 expected exceptions, two or three
  consecutive pairs are enough to reject independence, and the reader should see whether
  a rejection rests on one episode or on a persistently slow model.
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
  and `var_model_selection` with one row per method, and surfaced in the decision report
  with the verdict column and the selection sentence.
* Outcome on the current data: Student-t EWMA(0.94) is selected; Student-t GARCH is
  second and not distinguishable from it (Diebold-Mariano p = 0.77). From 2015 GARCH
  scores marginally better and has the most accurate exception count, but no model
  passes Christoffersen at 99%: the selected model's rejection rests on three back-to-back
  exceptions, two of them in the week of the November 2016 US election (MXN led the loss
  on the first day, BRL on the second, a broad emerging-market selloff on the third). A faster or GARCH volatility reacts after the first day, not
  before it, so the clustering is a property of jump-like news, not of the decay chosen.
  The choice is not revisited on the evaluation data.
* Running the backtest takes under a minute, dominated by the ES simulations and the
  GARCH fits (about 5 seconds).
