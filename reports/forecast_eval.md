# Exposure forecast evaluation

## Setup

140 monthly origins from 2014-12-31 to 2026-07-31, horizons 1-63 trading days, training window 750 days. Pinball loss is averaged over the 2.5/10/25/50/75/90/97.5 quantiles and scaled by the mean actual. Coverage is the share of actuals inside the central 50/80/95% intervals. Skill is 1 - pinball / pinball of the seasonal naive.

## By horizon, averaged over currencies

| model | horizon | pinball_pct | mape_median_pct | coverage_50 | coverage_80 | coverage_95 | skill_vs_naive |
|---|---|---|---|---|---|---|---|
| calendar_ar1 | 1 | 2.08 | 7.28 | 0.43 | 0.71 | 0.88 | 0.76 |
| calendar_ar1 | 5 | 1.51 | 5.11 | 0.42 | 0.69 | 0.87 | 0.81 |
| calendar_ar1 | 10 | 1.49 | 5.07 | 0.39 | 0.67 | 0.86 | 0.8 |
| calendar_ar1 | 21 | 1.98 | 6.82 | 0.4 | 0.69 | 0.85 | 0.8 |
| calendar_ar1 | 42 | 2.12 | 7.36 | 0.4 | 0.69 | 0.86 | 0.77 |
| calendar_ar1 | 63 | 2.03 | 6.92 | 0.42 | 0.69 | 0.83 | 0.77 |
| seasonal_naive | 1 | 9.26 | 37.29 | 0.36 | 0.67 | 0.91 | 0 |
| seasonal_naive | 5 | 9.35 | 35.94 | 0.44 | 0.73 | 0.94 | 0 |
| seasonal_naive | 10 | 8.53 | 33.3 | 0.49 | 0.8 | 0.97 | 0 |
| seasonal_naive | 21 | 10.7 | 40.47 | 0.31 | 0.54 | 0.77 | 0 |
| seasonal_naive | 42 | 9.85 | 32.34 | 0.47 | 0.64 | 0.8 | 0 |
| seasonal_naive | 63 | 9.41 | 32.51 | 0.25 | 0.62 | 0.85 | 0 |

## At 21 days, by currency

| ccy | model | pinball_pct | mape_median_pct | coverage_50 | coverage_80 | coverage_95 | skill_vs_naive |
|---|---|---|---|---|---|---|---|
| AUD | calendar_ar1 | 2.08 | 7.48 | 0.4 | 0.69 | 0.87 | 0.8 |
| AUD | seasonal_naive | 10.54 | 40.05 | 0.35 | 0.54 | 0.75 | 0 |
| BRL | calendar_ar1 | 1.75 | 6.24 | 0.38 | 0.69 | 0.84 | 0.73 |
| BRL | seasonal_naive | 6.43 | 25.27 | 0.33 | 0.65 | 0.85 | 0 |
| CAD | calendar_ar1 | 2.03 | 6.87 | 0.38 | 0.71 | 0.87 | 0.81 |
| CAD | seasonal_naive | 10.96 | 40.52 | 0.36 | 0.51 | 0.76 | 0 |
| CHF | calendar_ar1 | 2.03 | 7.06 | 0.39 | 0.69 | 0.82 | 0.86 |
| CHF | seasonal_naive | 14.49 | 54.34 | 0.18 | 0.46 | 0.73 | 0 |
| EUR | calendar_ar1 | 2 | 6.91 | 0.41 | 0.73 | 0.85 | 0.86 |
| EUR | seasonal_naive | 14.43 | 54.55 | 0.19 | 0.48 | 0.74 | 0 |
| GBP | calendar_ar1 | 2.12 | 7.19 | 0.39 | 0.69 | 0.87 | 0.85 |
| GBP | seasonal_naive | 14.31 | 53.35 | 0.18 | 0.48 | 0.75 | 0 |
| INR | calendar_ar1 | 1.68 | 5.76 | 0.4 | 0.69 | 0.89 | 0.74 |
| INR | seasonal_naive | 6.4 | 25.36 | 0.39 | 0.66 | 0.83 | 0 |
| JPY | calendar_ar1 | 2.02 | 6.9 | 0.43 | 0.68 | 0.83 | 0.8 |
| JPY | seasonal_naive | 10.02 | 37.63 | 0.41 | 0.53 | 0.77 | 0 |
| MXN | calendar_ar1 | 1.95 | 6.72 | 0.42 | 0.69 | 0.86 | 0.79 |
| MXN | seasonal_naive | 9.07 | 34.73 | 0.36 | 0.58 | 0.78 | 0 |
| SGD | calendar_ar1 | 2.1 | 7.07 | 0.44 | 0.71 | 0.84 | 0.8 |
| SGD | seasonal_naive | 10.36 | 38.91 | 0.39 | 0.51 | 0.75 | 0 |

## Latest 21-day-ahead forecast of net exposure (currency units), calendar_ar1

| ccy | target_date | 2.5% | median | 97.5% |
|---|---|---|---|---|
| EUR | 2026-11-30 | 104,266,569.89 | 113,974,414.5 | 128,094,996.76 |
| GBP | 2026-11-30 | 62,068,566.73 | 69,137,160.41 | 81,776,157.35 |
| CAD | 2026-11-30 | 67,782,903.63 | 76,545,687.59 | 83,746,894.09 |
| JPY | 2026-11-30 | 2,809,814,005.03 | 3,068,977,554.6 | 3,519,839,720.89 |
| AUD | 2026-11-30 | 15,569,836.53 | 17,081,085.86 | 18,682,026.47 |
| CHF | 2026-11-30 | 11,180,032.12 | 12,911,067.83 | 14,667,993.39 |
| MXN | 2026-11-30 | 413,998,062.19 | 458,597,510.72 | 511,957,519.44 |
| BRL | 2026-11-30 | 144,786,084.88 | 154,288,684.07 | 173,017,064.21 |
| INR | 2026-11-30 | 2,673,573,541.61 | 2,850,916,615.1 | 3,019,189,174.58 |
| SGD | 2026-11-30 | 14,899,236.72 | 16,700,976.26 | 18,696,780.47 |

## Figures

![calibration](figures/forecast_calibration.png)

![pinball](figures/forecast_pinball.png)

![example](figures/forecast_example.png)
