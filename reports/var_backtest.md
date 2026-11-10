# VaR / ES model selection and coverage backtest

## Model selection, 2012-2014

| method | usable by the optimizer | days | exceptions | FZ0 score, 2012-2014 | DM statistic vs selected | DM p vs selected | selected | FZ0 score, 2015 on |
|---|---|---|---|---|---|---|---|---|
| Student-t, EWMA 0.94 | yes | 752 | 10 | 14.2242 |  |  | yes | 14.5528 |
| Student-t, GARCH(1,1) volatilities | yes | 752 | 6 | 14.2319 | 0.30 | 0.77 | no | 14.5381 |
| normal, sample covariance | yes | 752 | 3 | 14.2557 | 0.41 | 0.68 | no | 14.6369 |
| Student-t, EWMA 0.97 | yes | 752 | 6 | 14.2628 | 1.83 | 0.07 | no | 14.5311 |
| historical simulation | no | 752 | 3 | 14.3216 | 0.95 | 0.34 | no | 14.5782 |
| normal, EWMA 0.94 | yes | 752 | 14 | 14.3654 | 1.54 | 0.12 | no | 14.6432 |

One-day horizon at 99%, 2012-01 to 2014-12, scored with the FZ0 joint VaR/ES loss (lower is better). The selected model has the lowest mean score among the models the optimizer can use; the Diebold-Mariano p-value says whether another model's score is distinguishable from it. GARCH: 1770 univariate fits, 0 did not converge (those keep the previous month's parameters).

## Coverage tests, 2015 onward

| basis | method | confidence | from | to | days | exceptions | expected | back-to-back | Kupiec p | Christoffersen p | conditional coverage p | traffic light | Z1 | Z1 p | Z2 | Z2 p | FZ0 score | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| net | historical simulation | 0.95 | 2015-01-02 | 2026-11-06 | 2962 | 135 | 148.1 | 18 | 0.26 | 0 | 0 | n/a | 0.01 | 0.38 | -0.08 | 0.84 | 14.14 | FAIL |
| net | historical simulation | 0.99 | 2015-01-02 | 2026-11-06 | 2962 | 29 | 29.62 | 5 | 0.91 | 0 | 0 | green | -0.02 | 0.63 | -0.04 | 0.56 | 14.58 | FAIL |
| net | normal, sample covariance | 0.95 | 2015-01-02 | 2026-11-06 | 2962 | 127 | 148.1 | 17 | 0.07 | 0 | 0 | n/a | 0.14 | 0 | -0.02 | 0.62 | 14.14 | FAIL |
| net | normal, sample covariance | 0.99 | 2015-01-02 | 2026-11-06 | 2962 | 41 | 29.62 | 8 | 0.05 | 0 | 0 | green | 0.2 | 0 | 0.66 | 0 | 14.64 | FAIL |
| net | normal, EWMA 0.94 | 0.95 | 2015-01-02 | 2026-11-06 | 2962 | 154 | 148.1 | 16 | 0.62 | 0.01 | 0.02 | n/a | 0.14 | 0 | 0.18 | 0.01 | 14.12 | FAIL |
| net | normal, EWMA 0.94 | 0.99 | 2015-01-02 | 2026-11-06 | 2962 | 50 | 29.62 | 4 | 0 | 0.01 | 0 | green | 0.2 | 0 | 1.02 | 0 | 14.64 | FAIL |
| net | Student-t, EWMA 0.94 | 0.95 | 2015-01-02 | 2026-11-06 | 2962 | 169 | 148.1 | 18 | 0.09 | 0.01 | 0.01 | n/a | 0.03 | 0.15 | 0.17 | 0.03 | 14.11 | FAIL |
| net | Student-t, EWMA 0.94 | 0.99 | 2015-01-02 | 2026-11-06 | 2962 | 32 | 29.62 | 3 | 0.66 | 0 | 0.02 | green | 0.08 | 0.07 | 0.17 | 0.18 | 14.55 | FAIL |
| net | Student-t, EWMA 0.97 | 0.95 | 2015-01-02 | 2026-11-06 | 2962 | 164 | 148.1 | 19 | 0.19 | 0 | 0 | n/a | 0.01 | 0.41 | 0.11 | 0.1 | 14.1 | FAIL |
| net | Student-t, EWMA 0.97 | 0.99 | 2015-01-02 | 2026-11-06 | 2962 | 37 | 29.62 | 3 | 0.19 | 0.01 | 0.02 | green | 0 | 0.43 | 0.25 | 0.1 | 14.53 | FAIL |
| net | Student-t, GARCH(1,1) volatilities | 0.95 | 2015-01-02 | 2026-11-06 | 2962 | 158 | 148.1 | 17 | 0.41 | 0.01 | 0.01 | n/a | -0.01 | 0.56 | 0.06 | 0.23 | 14.1 | FAIL |
| net | Student-t, GARCH(1,1) volatilities | 0.99 | 2015-01-02 | 2026-11-06 | 2962 | 29 | 29.62 | 2 | 0.91 | 0.03 | 0.1 | green | 0.05 | 0.16 | 0.03 | 0.44 | 14.54 | FAIL |

## Reading the table

One-day horizon, daily, exposure held at the previous close. Back-to-back counts exceptions on the day after another exception. Z1/Z2 are in losses: positive means realised tail losses exceeded the forecast ES. Verdict is PASS when Kupiec, Christoffersen, conditional coverage and Z2 all have p >= 0.05.
