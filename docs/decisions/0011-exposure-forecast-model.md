# ADR-0011: Exposure forecast model

**Status:** accepted, 2026-11-06

## Context

The hedge policy needs the net exposure per currency one month ahead, with honest
uncertainty, every month from 2015. A forecast is only worth using if it beats a
seasonal-naive baseline out of sample, so any model needs explicit prediction intervals
and a rolling-origin evaluation (pinball loss, coverage at 50/80/95) against that
baseline.

The exposure series has three deterministic rhythms (weekly payouts, the month-end fee
sweep, annual retail seasonality), an 8% growth trend, a regime break in 2020, and
residual autocorrelation. Within-week swings of 3x make a generic SARIMA with period 5
or 21 a poor fit: the month-end effect is calendar-driven, not lag-driven.

## Decision

* **Baseline: seasonal naive, same weekday four weeks earlier** (the target date minus
  28k calendar days, the last trading day on or before it if that is a holiday, with k
  the fewest four-week steps back to the origin), with intervals from the empirical
  quantiles of the same rule's in-window log errors at each horizon. An earlier version
  used a lag of 21 trading days, which drifts across weekdays; with flows that differ by
  weekday that made the baseline weaker than a treasury analyst's obvious first guess and
  roughly doubled the reported skill (0.73-0.81 against 0.26-0.64 now).
* **Model: calendar regression with AR(1) errors on log exposure** (a structural
  time-series model with deterministic components): weekday dummies, 0-4 trading days
  to month end, first three trading days of the month, month of year, linear trend;
  AR(1) on the OLS residuals, two-step estimation (consistent because the regressors
  are deterministic). Training window 750 days.
* **Intervals from the model's own in-sample multi-step errors**, standardised by the
  residual volatility of the target date's day type (sweep day, first days of the
  month, other) and conditioned on the origin's day type. The analytic AR(1) variance
  formula was tried first and was too narrow at short horizons: the month-end residual
  does not carry forward like an ordinary day's, and residual volatility differs by
  position in the month. Both are visible in the data and both are now in the model.
* **Month-position features are computed on the full trading calendar**, extended to the
  end of the last month with weekdays, never on the forecast window alone (an early
  version mislabelled the last forecast date as a month end and lost 63-day accuracy).
* **No statsmodels dependency.** The model is sixty lines of numpy and runs 140 origins
  x 10 currencies x 63 horizons in under twenty seconds, which keeps CI fast and the
  model fully readable. SARIMA/ETS via statsmodels and a Bayesian structural model are
  backlog items (B15).

## Evidence (reports/forecast_eval.md, 140 monthly origins 2015-2026)

| horizon | pinball % of exposure (model / naive) | skill | median MAPE | coverage 50 / 80 / 95 |
|---|---|---|---|---|
| 1 | 2.8 / 3.6 | 0.26 | 9.9% | 0.42 / 0.71 / 0.87 |
| 21 | 2.2 / 7.0 | 0.64 | 7.6% | 0.41 / 0.68 / 0.85 |
| 63 | 2.2 / 6.8 | 0.62 | 7.7% | 0.40 / 0.69 / 0.84 |

At one day the naive is hard to beat, since four weeks earlier is usually the same kind
of day; from one week out the calendar model's knowledge of where month ends fall pays
off. Its intervals are 10-15% too narrow across the board (empirical 0.85 at nominal
0.95): the 2020 regime shift and in-sample optimism of a 25-parameter fit. The naive's
own intervals are better calibrated (0.91-0.95), because they are built from
out-of-sample-like errors of a rule with no fitted parameters. The calibration plot
shows this honestly; a conformal adjustment from past out-of-sample errors is backlog
B16.

**The skill is an upper bound.** The regression has exactly the terms the synthetic
flows were generated with (weekday, month end, month of year, trend, AR(1) noise;
ADR-0008), so it is correctly specified by construction. On a real book the same model
would have to discover that structure and would face shocks the generator does not
produce; the evaluation method transfers, the skill number does not.

## Consequences

* The policy backtest hedges the median averaged over the holding month (ADR-0013),
  which uses every horizon from about 1 to 23 trading days; forecast error then flows into the
  realised P&L, which is the honest way to use a forecast in a hedge test.
* The report must say that intervals are somewhat narrow rather than present them as
  calibrated.
