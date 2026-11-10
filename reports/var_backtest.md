# VaR / ES model selection and coverage backtest

## Model selection, 2012-2014

| method | usable by the optimizer | days | exceptions | FZ0 score, 2012-2014 | DM statistic vs selected | DM p vs selected | selected | FZ0 score, 2015 on |
|---|---|---|---|---|---|---|---|---|
| Student-t, EWMA 0.94 | yes | 752 | 10 | 14.2242 |  |  | yes | 14.5530 |
| Student-t, GARCH(1,1) volatilities | yes | 752 | 6 | 14.2319 | 0.30 | 0.77 | no | 14.5383 |
| normal, sample covariance | yes | 752 | 3 | 14.2557 | 0.41 | 0.68 | no | 14.6375 |
| Student-t, EWMA 0.97 | yes | 752 | 6 | 14.2628 | 1.83 | 0.07 | no | 14.5313 |
| historical simulation | no | 752 | 3 | 14.3216 | 0.95 | 0.34 | no | 14.5786 |
| normal, EWMA 0.94 | yes | 752 | 14 | 14.3654 | 1.54 | 0.12 | no | 14.6437 |

One-day horizon at 99%, 2012-01 to 2014-12, scored with the FZ0 joint VaR/ES loss (lower is better). The selected model has the lowest mean score among the models the optimizer can use; the Diebold-Mariano p-value says whether another model's score is distinguishable from it. GARCH: 1770 univariate fits, 0 did not converge (those keep the previous month's parameters).

## Coverage tests, 2015 onward

| basis | method | confidence | from | to | days | exceptions | expected | back-to-back | Kupiec p | Christoffersen p | conditional coverage p | traffic light | Z1 | Z1 p | Z2 | Z2 p | FZ0 score | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| net | historical simulation | 0.95 | 2015-01-02 | 2026-10-30 | 2957 | 135 | 147.85 | 18 | 0.27 | 0 | 0 | n/a | 0.01 | 0.38 | -0.08 | 0.83 | 14.14 | FAIL |
| net | historical simulation | 0.99 | 2015-01-02 | 2026-10-30 | 2957 | 29 | 29.57 | 5 | 0.92 | 0 | 0 | green | -0.02 | 0.63 | -0.04 | 0.55 | 14.58 | FAIL |
| net | normal, sample covariance | 0.95 | 2015-01-02 | 2026-10-30 | 2957 | 127 | 147.85 | 17 | 0.07 | 0 | 0 | n/a | 0.14 | 0 | -0.02 | 0.61 | 14.15 | FAIL |
| net | normal, sample covariance | 0.99 | 2015-01-02 | 2026-10-30 | 2957 | 41 | 29.57 | 8 | 0.05 | 0 | 0 | green | 0.2 | 0 | 0.66 | 0 | 14.64 | FAIL |
| net | normal, EWMA 0.94 | 0.95 | 2015-01-02 | 2026-10-30 | 2957 | 154 | 147.85 | 16 | 0.61 | 0.01 | 0.02 | n/a | 0.14 | 0 | 0.19 | 0.01 | 14.12 | FAIL |
| net | normal, EWMA 0.94 | 0.99 | 2015-01-02 | 2026-10-30 | 2957 | 50 | 29.57 | 4 | 0 | 0.01 | 0 | green | 0.2 | 0 | 1.03 | 0 | 14.64 | FAIL |
| net | Student-t, EWMA 0.94 | 0.95 | 2015-01-02 | 2026-10-30 | 2957 | 169 | 147.85 | 18 | 0.08 | 0.01 | 0.01 | n/a | 0.03 | 0.15 | 0.17 | 0.03 | 14.11 | FAIL |
| net | Student-t, EWMA 0.94 | 0.99 | 2015-01-02 | 2026-10-30 | 2957 | 32 | 29.57 | 3 | 0.66 | 0 | 0.02 | green | 0.08 | 0.07 | 0.17 | 0.18 | 14.55 | FAIL |
| net | Student-t, EWMA 0.97 | 0.95 | 2015-01-02 | 2026-10-30 | 2957 | 164 | 147.85 | 19 | 0.18 | 0 | 0 | n/a | 0.01 | 0.41 | 0.12 | 0.1 | 14.1 | FAIL |
| net | Student-t, EWMA 0.97 | 0.99 | 2015-01-02 | 2026-10-30 | 2957 | 37 | 29.57 | 3 | 0.19 | 0.01 | 0.02 | green | 0 | 0.43 | 0.26 | 0.1 | 14.53 | FAIL |
| net | Student-t, GARCH(1,1) volatilities | 0.95 | 2015-01-02 | 2026-10-30 | 2957 | 158 | 147.85 | 17 | 0.4 | 0.01 | 0.01 | n/a | -0.01 | 0.56 | 0.06 | 0.23 | 14.1 | FAIL |
| net | Student-t, GARCH(1,1) volatilities | 0.99 | 2015-01-02 | 2026-10-30 | 2957 | 29 | 29.57 | 2 | 0.92 | 0.03 | 0.1 | green | 0.05 | 0.16 | 0.03 | 0.43 | 14.54 | FAIL |

## Reading the table

One-day horizon, daily, exposure held at the previous close. Back-to-back counts exceptions on the day after another exception. Z1/Z2 are in losses: positive means realised tail losses exceeded the forecast ES. Verdict is PASS when Kupiec, Christoffersen, conditional coverage and Z2 all have p >= 0.05.
