# Data quality report

Generated 2026-11-10 19:07 UTC - overall **WARN**

| check | status | summary |
|---|---|---|
| cache_complete | PASS | all 66 registered series cached |
| schema | PASS | all cached files well-formed |
| staleness | WARN | 2 series stale or lagging |
| reconciliation | PASS | all 20 currency/source pairs within tolerance |
| master_completeness | PASS | 0 NULL cells across 10 currencies; 1 cells filled from BoC/ECB |
| calendar | PASS | no gaps longer than 6 calendar days |
| return_outliers | WARN | 33 daily moves beyond 6 EWMA sigma: 30 confirmed by every other source, 3 by some, 0 by none (review, not necessarily errors) |
| rates_range | PASS | all 11 rate series within [-2.0, 40.0] percent |

## Details

### cache_complete - **PASS**

all 66 registered series cached

### schema - **PASS**

all cached files well-formed

### staleness - **WARN**

2 series stale or lagging

| series | last_date | retrieved | lag_days | limit_days | level |
|---|---|---|---|---|---|
| statcan:v1446859481 | 2026-08-01 | 2026-11-10 | 101 | 130 | WARN |
| statcan:v1446859483 | 2026-08-01 | 2026-11-10 | 101 | 130 | WARN |

### reconciliation - **PASS**

all 20 currency/source pairs within tolerance

| ccy | source | n_days | median_abs_bp | p99_abs_bp | max_abs_bp | mean_bp | status | breaches |
|---|---|---|---|---|---|---|---|---|
| AUD | boc | 4120 | 2.29 | 31.6 | 95.8 | -0.83 | PASS |  |
| BRL | boc | 4120 | 4.81 | 55.7 | 132.9 | -1.63 | PASS |  |
| CAD | boc | 4120 | 2.17 | 24.8 | 64.5 | -0.75 | PASS |  |
| CHF | boc | 4120 | 2.45 | 24.6 | 87.7 | -0.91 | PASS |  |
| EUR | boc | 4120 | 1.62 | 23.5 | 82 | -0.25 | PASS |  |
| GBP | boc | 4120 | 1.88 | 30.4 | 68.5 | -0.97 | PASS |  |
| INR | boc | 4119 | 2.67 | 38.6 | 200.4 | -1.49 | PASS |  |
| JPY | boc | 4120 | 3.26 | 28.3 | 183.1 | -0.56 | PASS |  |
| MXN | boc | 4120 | 3.19 | 46.6 | 126.7 | -1.32 | PASS |  |
| SGD | boc | 4120 | 1.97 | 13.8 | 49.1 | -1.33 | PASS |  |
| AUD | ecb | 4161 | 19.43 | 115.1 | 274.5 | -0.61 | PASS |  |
| BRL | ecb | 4161 | 35.18 | 183.9 | 759.7 | -0.35 | PASS |  |
| CAD | ecb | 4161 | 17.11 | 98.6 | 246.7 | -0.52 | PASS |  |
| CHF | ecb | 4161 | 17.51 | 109.8 | 292.7 | -2.36 | PASS |  |
| EUR | ecb | 4161 | 16.22 | 103.7 | 277.1 | -1.06 | PASS |  |
| GBP | ecb | 4161 | 16.46 | 97.1 | 238 | -1.35 | PASS |  |
| INR | ecb | 4160 | 6.54 | 57.3 | 206.3 | -4.66 | PASS |  |
| JPY | ecb | 4161 | 15.28 | 104.9 | 358.1 | -1.21 | PASS |  |
| MXN | ecb | 4161 | 25.98 | 127.4 | 262.1 | -1.01 | PASS |  |
| SGD | ecb | 4161 | 8.6 | 50.9 | 125.6 | -1.75 | PASS |  |

### master_completeness - **PASS**

0 NULL cells across 10 currencies; 1 cells filled from BoC/ECB

| ccy | n_days | n_null | n_fred | n_boc | n_ecb | null_share |
|---|---|---|---|---|---|---|
| AUD | 4215 | 0 | 4,215 | 0 | 0 | 0 |
| BRL | 4215 | 0 | 4,215 | 0 | 0 | 0 |
| CAD | 4215 | 0 | 4,215 | 0 | 0 | 0 |
| CHF | 4215 | 0 | 4,215 | 0 | 0 | 0 |
| EUR | 4215 | 0 | 4,215 | 0 | 0 | 0 |
| GBP | 4215 | 0 | 4,215 | 0 | 0 | 0 |
| INR | 4215 | 0 | 4,214 | 1 | 0 | 0 |
| JPY | 4215 | 0 | 4,215 | 0 | 0 | 0 |
| MXN | 4215 | 0 | 4,215 | 0 | 0 | 0 |
| SGD | 4215 | 0 | 4,215 | 0 | 0 | 0 |

### calendar - **PASS**

no gaps longer than 6 calendar days

### return_outliers - **WARN**

33 daily moves beyond 6 EWMA sigma: 30 confirmed by every other source, 3 by some, 0 by none (review, not necessarily errors)

| date | ccy | log_return_pct | z | source | confirmed_by | span_days |
|---|---|---|---|---|---|---|
| 2015-01-15 | CHF | 13.02 | 25.3 | fred | 2 of 2 | 1 |
| 2017-05-18 | BRL | -8.67 | -12.6 | fred | 1 of 2 | 1 |
| 2016-06-24 | GBP | -8.17 | -9.1 | fred | 2 of 2 | 1 |
| 2012-09-14 | INR | 3.76 | 8.7 | fred | 2 of 2 | 1 |
| 2025-04-04 | AUD | -4.99 | -8.6 | fred | 2 of 2 | 1 |
| 2026-07-30 | JPY | 2.72 | 8.6 | fred | 1 of 2 | 1 |
| 2026-10-26 | BRL | -7.65 | -8.2 | fred | 2 of 2 | 3 |
| 2013-06-20 | BRL | -4.11 | -7.9 | fred | 2 of 2 | 1 |
| 2014-09-04 | EUR | -1.61 | -7.9 | fred | 2 of 2 | 1 |
| 2026-10-05 | BRL | 4.59 | 7.7 | fred | 2 of 2 | 3 |
| 2011-09-06 | CHF | -8.89 | -7.5 | fred | 2 of 2 | 4 |
| 2025-04-03 | CHF | 2.63 | 7.3 | fred | 2 of 2 | 1 |
| 2021-02-26 | INR | -1.61 | -7.3 | fred | 2 of 2 | 1 |
| 2026-10-13 | INR | 1.51 | 7.1 | fred | 2 of 2 | 4 |
| 2025-01-13 | INR | -0.85 | -7 | fred | 2 of 2 | 3 |
| 2010-04-14 | SGD | 1.37 | 6.9 | fred | 2 of 2 | 1 |
| 2011-10-31 | JPY | -2.93 | -6.8 | fred | 2 of 2 | 3 |
| 2016-11-09 | MXN | -7.01 | -6.6 | fred | 2 of 2 | 1 |
| 2013-06-20 | MXN | -4.06 | -6.6 | fred | 2 of 2 | 1 |
| 2011-08-04 | JPY | -2.75 | -6.6 | fred | 2 of 2 | 1 |
| 2020-11-09 | JPY | -2.16 | -6.5 | fred | 2 of 2 | 3 |
| 2014-09-04 | CHF | -1.52 | -6.3 | fred | 2 of 2 | 1 |
| 2010-01-06 | CAD | 0.37 | 6.3 | fred | 1 of 2 | 1 |
| 2010-01-11 | EUR | 1.24 | 6.3 | fred | 2 of 2 | 3 |
| 2021-06-17 | CHF | -2.06 | -6.3 | fred | 2 of 2 | 1 |

### rates_range - **PASS**

all 11 rate series within [-2.0, 40.0] percent

| source | series_id | ccy | min_pct | max_pct | last_date |
|---|---|---|---|---|---|
| bis | D.AU | AUD | 0.1 | 4.75 | 2026-10-29 |
| bis | D.BR | BRL | 2 | 15 | 2026-11-03 |
| bis | D.CA | CAD | 0.25 | 5 | 2026-11-02 |
| bis | D.CH | CHF | -0.75 | 1.75 | 2026-11-03 |
| bis | D.GB | GBP | 0.1 | 5.25 | 2026-11-02 |
| bis | D.IN | INR | 4 | 8.5 | 2026-10-19 |
| bis | D.JP | JPY | -0.1 | 1.25 | 2026-11-03 |
| bis | D.MX | MXN | 3 | 11.25 | 2026-11-03 |
| bis | D.US | USD | 0.12 | 5.38 | 2026-11-03 |
| bis | D.XM | EUR | 0 | 4.5 | 2026-11-03 |
| ecb | FM.D.U2.EUR.4F.KR.DFR.LEV | EUR | -0.5 | 4 | 2026-11-10 |
