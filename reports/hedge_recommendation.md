# Hedge recommendation as of 2026-10-30

## Setup

Exposure input: calendar_ar1 median forecast, 21 days ahead. Risk model: Student-t with EWMA(0.94) covariance at 21 days / 99%. Forwards: 30-day tenor priced by CIP.

## Headline

| quantity | value |
|---|---|
| unhedged ES (USD m) | 19.61 |
| ES budget (USD m) | 4 |
| residual ES with recommended hedges (USD m) | 4 |
| expected carry cost per year (USD m) | -2.21 |
| spread cost per year (USD m) | 0.47 |
| tail index nu | 4.92 |
| budget binding | yes |

## Recommended hedge ratios by currency

| index | exposure_fcy | exposure_usd_m | hedge_ratio | notional_usd_m | carry_pct_annual | spread_bp | rate_source | is_proxy |
|---|---|---|---|---|---|---|---|---|
| EUR | 113,612,277 | 126.83 | 1 | -126.83 | -1.55 | 0.5 | bis:D.XM | no |
| GBP | 70,187,773 | 94.04 | 1 | -94.04 | -0.34 | 0.7 | bis:D.GB | no |
| CAD | 75,833,156 | 54.33 | 1 | -54.33 | -1.54 | 0.7 | boc:TB.CDN.90D.MID | no |
| JPY | 3,061,699,306 | 19.44 | 1 | -19.44 | -2.5 | 0.6 | fred:IR3TIB01JPM156N | no |
| AUD | 17,107,024 | 12.04 | 1 | -12.04 | 0.42 | 0.9 | fred:IR3TIB01AUM156N | no |
| CHF | 12,985,878 | 15.78 | 1 | -15.78 | -4.13 | 0.8 | fred:IR3TIB01CHM156N | no |
| MXN | 451,964,470 | 24.05 | 0.04 | -0.83 | 2.8 | 3 | fred:IR3TIB01MXM156N | no |
| BRL | 155,805,799 | 28.72 | 0.71 | -20.28 | 9.74 | 8 | fred:IRSTCI01BRM156N | no |
| INR | 2,844,296,885 | 29.96 | 0 | 0 | 1.41 | 6 | fred:IRSTCI01INM156N | no |
| SGD | 16,575,818 | 12.97 | 1 | -12.97 | 0 | 1.5 | proxy:USD:DTB3 | yes |

## Reference policies at today's exposures

| policy | residual_es_usd_m | annual_cost_usd_m |
|---|---|---|
| unhedged | 19.61 | 0 |
| legacy_50 | 9.81 | 0.27 |
| full_hedge | 0 | 0.54 |
| optimizer | 4 | -1.74 |

## Frontier (every other point)

| budget_usd_m | residual_es_usd_m | annual_cost_usd_m | mean_ratio |
|---|---|---|---|
| 0 | 0 | 0.54 | 1 |
| 1.35 | 1.35 | -0.25 | 0.91 |
| 2.71 | 2.71 | -1.04 | 0.83 |
| 4.06 | 4.06 | -1.77 | 0.77 |
| 5.41 | 5.41 | -2.38 | 0.75 |
| 6.76 | 6.76 | -2.93 | 0.73 |
| 8.12 | 8.12 | -3.45 | 0.72 |
| 9.47 | 9.47 | -3.95 | 0.68 |
| 10.82 | 9.87 | -4.02 | 0.5 |
| 12.17 | 9.87 | -4.02 | 0.5 |
| 13.53 | 9.87 | -4.02 | 0.5 |
| 14.88 | 9.87 | -4.02 | 0.5 |
| 16.23 | 9.87 | -4.02 | 0.5 |
| 17.59 | 9.87 | -4.02 | 0.5 |
| 18.94 | 9.87 | -4.02 | 0.5 |

## Figure

![frontier](figures/hedge_frontier.png)
