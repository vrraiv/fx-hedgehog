# Exposure forecast evaluation

## Setup

140 monthly origins from 2014-12-31 to 2026-07-31, horizons 1-63 trading days, training window 750 days. Pinball loss is averaged over the 2.5/10/25/50/75/90/97.5 quantiles and scaled by the mean actual. Coverage is the share of actuals inside the central 50/80/95% intervals. Skill is 1 - pinball / pinball of the seasonal naive.

## By horizon, averaged over currencies

| model | horizon | pinball_pct | mape_median_pct | coverage_50 | coverage_80 | coverage_95 | skill_vs_naive |
|---|---|---|---|---|---|---|---|
| calendar_ar1 | 1 | 2.76 | 9.86 | 0.42 | 0.71 | 0.87 | 0.26 |
| calendar_ar1 | 5 | 1.62 | 5.59 | 0.39 | 0.68 | 0.86 | 0.5 |
| calendar_ar1 | 10 | 1.63 | 5.61 | 0.37 | 0.66 | 0.84 | 0.46 |
| calendar_ar1 | 21 | 2.23 | 7.61 | 0.41 | 0.68 | 0.85 | 0.64 |
| calendar_ar1 | 42 | 2.44 | 8.51 | 0.4 | 0.7 | 0.86 | 0.59 |
| calendar_ar1 | 63 | 2.24 | 7.74 | 0.4 | 0.69 | 0.84 | 0.62 |
| seasonal_naive | 1 | 3.55 | 10.39 | 0.51 | 0.79 | 0.92 | 0 |
| seasonal_naive | 5 | 3.27 | 9.87 | 0.5 | 0.81 | 0.94 | 0 |
| seasonal_naive | 10 | 3.04 | 9.24 | 0.51 | 0.84 | 0.95 | 0 |
| seasonal_naive | 21 | 7.04 | 24.08 | 0.39 | 0.67 | 0.92 | 0 |
| seasonal_naive | 42 | 6.64 | 23.92 | 0.35 | 0.69 | 0.91 | 0 |
| seasonal_naive | 63 | 6.81 | 24.66 | 0.41 | 0.73 | 0.91 | 0 |

## At 21 days, by currency

| ccy | model | pinball_pct | mape_median_pct | coverage_50 | coverage_80 | coverage_95 | skill_vs_naive |
|---|---|---|---|---|---|---|---|
| AUD | calendar_ar1 | 2.07 | 7.3 | 0.43 | 0.71 | 0.86 | 0.66 |
| AUD | seasonal_naive | 6.03 | 20.9 | 0.39 | 0.72 | 0.92 | 0 |
| BRL | calendar_ar1 | 1.77 | 6.29 | 0.39 | 0.66 | 0.84 | 0.52 |
| BRL | seasonal_naive | 3.72 | 13.06 | 0.41 | 0.71 | 0.95 | 0 |
| CAD | calendar_ar1 | 2.71 | 9.11 | 0.45 | 0.73 | 0.89 | 0.77 |
| CAD | seasonal_naive | 11.56 | 40.1 | 0.34 | 0.59 | 0.89 | 0 |
| CHF | calendar_ar1 | 2 | 7 | 0.37 | 0.64 | 0.83 | 0.62 |
| CHF | seasonal_naive | 5.3 | 17.45 | 0.41 | 0.7 | 0.91 | 0 |
| EUR | calendar_ar1 | 3 | 10.03 | 0.4 | 0.66 | 0.85 | 0.77 |
| EUR | seasonal_naive | 13.29 | 44.92 | 0.33 | 0.56 | 0.88 | 0 |
| GBP | calendar_ar1 | 2.98 | 9.92 | 0.4 | 0.67 | 0.82 | 0.75 |
| GBP | seasonal_naive | 12.09 | 40.79 | 0.32 | 0.58 | 0.89 | 0 |
| INR | calendar_ar1 | 1.68 | 5.8 | 0.41 | 0.71 | 0.88 | 0.52 |
| INR | seasonal_naive | 3.5 | 12.2 | 0.46 | 0.75 | 0.95 | 0 |
| JPY | calendar_ar1 | 2.03 | 7.04 | 0.36 | 0.68 | 0.85 | 0.58 |
| JPY | seasonal_naive | 4.82 | 16.7 | 0.39 | 0.68 | 0.93 | 0 |
| MXN | calendar_ar1 | 1.94 | 6.61 | 0.4 | 0.66 | 0.85 | 0.59 |
| MXN | seasonal_naive | 4.72 | 16.09 | 0.39 | 0.69 | 0.93 | 0 |
| SGD | calendar_ar1 | 2.1 | 7.04 | 0.46 | 0.71 | 0.85 | 0.61 |
| SGD | seasonal_naive | 5.37 | 18.56 | 0.43 | 0.76 | 0.92 | 0 |

## Latest 21-day-ahead forecast of net exposure (currency units), calendar_ar1

| ccy | target_date | 2.5% | median | 97.5% |
|---|---|---|---|---|
| EUR | 2026-11-30 | 13,862,168.43 | 17,454,373.72 | 22,754,636.73 |
| GBP | 2026-11-30 | 9,950,499.27 | 13,076,829.86 | 17,090,122.7 |
| CAD | 2026-11-30 | 17,795,142.03 | 21,109,867.42 | 26,026,221.52 |
| JPY | 2026-11-30 | 2,795,640,376.11 | 3,061,699,305.81 | 3,479,497,061.24 |
| AUD | 2026-11-30 | 15,417,884.09 | 17,107,023.86 | 18,893,863.58 |
| CHF | 2026-11-30 | 11,387,208.77 | 12,985,877.88 | 14,590,082.51 |
| MXN | 2026-11-30 | 418,046,671.88 | 451,964,470.23 | 508,458,692.88 |
| BRL | 2026-11-30 | 145,492,270.27 | 155,805,799.43 | 173,445,631.51 |
| INR | 2026-11-30 | 2,704,656,725.75 | 2,844,296,885.13 | 3,018,982,062.27 |
| SGD | 2026-11-30 | 14,647,934.63 | 16,575,817.74 | 18,524,726.43 |

## Figures

![calibration](figures/forecast_calibration.png)

![pinball](figures/forecast_pinball.png)

![example](figures/forecast_example.png)
