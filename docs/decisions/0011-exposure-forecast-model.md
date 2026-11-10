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

* **Baseline: seasonal naive** at lag 21 trading days (``y[t+h] = y[t+h-21k]``), with
  intervals from the empirical quantiles of its own in-window log errors at each
  horizon.
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

| horizon | pinball % of exposure (model / naive) | median MAPE | coverage 50 / 80 / 95 |
|---|---|---|---|
| 1 | 2.1 / 9.3 | 7.3% | 0.43 / 0.71 / 0.88 |
| 21 | 2.0 / 10.7 | 6.8% | 0.40 / 0.70 / 0.86 |
| 63 | 2.0 / 9.4 | 6.9% | 0.42 / 0.69 / 0.83 |

Skill versus the naive is about 0.8 at every horizon. Intervals are 10-15% too narrow
across the board (empirical 0.86 at nominal 0.95): the 2020 regime shift and in-sample
optimism of a 25-parameter fit. The calibration plot shows this honestly; a conformal
adjustment from past out-of-sample errors is backlog B16.

## Consequences

* The policy backtest hedges the 21-day-ahead median; forecast error then flows into the
  realised P&L, which is the honest way to use a forecast in a hedge test.
* The report must say that intervals are somewhat narrow rather than present them as
  calibrated.
