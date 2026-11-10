# Hedge recommendation as of 2026-10-30

## Setup

Exposure input: calendar_ar1 median forecast, averaged over the trading days of 2026-11. Risk model: Student-t with EWMA(0.94) covariance at 21 days / 99%. Forwards: 30-day tenor priced by CIP.

## Headline

| quantity | value |
|---|---|
| unhedged ES (USD m) | 12.89 |
| ES budget (USD m) | 4 |
| residual ES with recommended hedges (USD m) | 4 |
| expected carry cost per year (USD m) | -0.35 |
| spread cost per year (USD m) | 0.33 |
| tail index nu | 4.94 |
| budget binding | yes |

## Recommended hedge ratios by currency

| ccy | exposure (currency units) | exposure (USD m) | hedge ratio | forward notional (USD m) | carry (% / yr, + = cost) | spread (bp) | rate source | proxy rate |
|---|---|---|---|---|---|---|---|---|
| EUR | 38,321,816 | 42.78 | 1 | -42.78 | -1.39 | 0.5 | ecb:FM.D.U2.EUR.4F.KR.DFR.LEV | no |
| GBP | 25,915,558 | 34.72 | 1 | -34.72 | -0.18 | 0.7 | bis:D.GB | no |
| CAD | 33,060,186 | 23.69 | 1 | -23.69 | -1.43 | 0.7 | bis:D.CA | no |
| JPY | 2,832,796,980 | 17.99 | 1 | -17.99 | -2.66 | 0.6 | bis:D.JP | no |
| AUD | 17,555,619 | 12.36 | 1 | -12.36 | 0.67 | 0.9 | bis:D.AU | no |
| CHF | 16,764,669 | 20.37 | 1 | -20.37 | -3.93 | 0.8 | bis:D.CH | no |
| MXN | 442,459,964 | 23.54 | 0 | 0 | 2.65 | 3 | bis:D.MX | no |
| BRL | 149,164,679 | 27.49 | 0.69 | -18.95 | 9.71 | 8 | bis:D.BR | no |
| INR | 2,704,869,286 | 28.49 | 0 | 0 | 1.56 | 6 | bis:D.IN | no |
| SGD | 16,395,972 | 12.83 | 1 | -12.83 | 0 | 1.5 | proxy:USD:D.US | yes |

## Reference policies at today's exposures

| policy | residual ES (USD m) | expected cost (USD m / yr, + = cost) |
|---|---|---|
| unhedged | 12.89 | 0 |
| legacy 50% | 6.57 | 1.16 |
| full hedge | 0 | 2.25 |
| optimizer | 4 | -0.02 |

## Frontier (every other point)

| ES budget (USD m) | residual ES (USD m) | expected cost (USD m / yr, + = cost) | mean hedge ratio |
|---|---|---|---|
| 0 | 0 | 2.25 | 1 |
| 0.89 | 0.89 | 1.72 | 0.94 |
| 1.78 | 1.78 | 1.19 | 0.88 |
| 2.67 | 2.67 | 0.67 | 0.82 |
| 3.56 | 3.56 | 0.2 | 0.79 |
| 4.45 | 4.45 | -0.23 | 0.76 |
| 5.33 | 5.33 | -0.62 | 0.75 |
| 6.22 | 6.22 | -0.98 | 0.74 |
| 7.11 | 7.11 | -1.33 | 0.72 |
| 8 | 8 | -1.67 | 0.71 |
| 8.89 | 8.89 | -2 | 0.7 |
| 9.78 | 9.48 | -2.17 | 0.5 |
| 10.67 | 9.48 | -2.17 | 0.5 |
| 11.56 | 9.48 | -2.17 | 0.5 |
| 12.45 | 9.48 | -2.17 | 0.5 |

## Figure

![frontier](figures/hedge_frontier.png)
