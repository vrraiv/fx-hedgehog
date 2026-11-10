# VaR / ES coverage backtest

## Results

| basis | method | confidence | oos_start | oos_end | n_obs | n_exceptions | expected_exceptions | kupiec_p | christoffersen_p | conditional_p | traffic_light | z1 | z1_p | z2 | z2_p | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| net | historical | 0.95 | 2015-01-02 | 2026-10-30 | 2957 | 151 | 147.85 | 0.79 | 0 | 0 | n/a | -0.02 | 0.7 | 0 | 0.46 | FAIL |
| net | historical | 0.99 | 2015-01-02 | 2026-10-30 | 2957 | 30 | 29.57 | 0.94 | 0 | 0 | green | -0.03 | 0.68 | -0.02 | 0.52 | FAIL |
| net | normal_sample | 0.95 | 2015-01-02 | 2026-10-30 | 2957 | 139 | 147.85 | 0.45 | 0 | 0 | n/a | 0.11 | 0 | 0.04 | 0.29 | FAIL |
| net | normal_sample | 0.99 | 2015-01-02 | 2026-10-30 | 2957 | 41 | 29.57 | 0.05 | 0 | 0 | green | 0.2 | 0 | 0.66 | 0 | FAIL |
| net | normal_ewma | 0.95 | 2015-01-02 | 2026-10-30 | 2957 | 147 | 147.85 | 0.94 | 0.09 | 0.23 | n/a | 0.13 | 0 | 0.13 | 0.06 | PASS |
| net | normal_ewma | 0.99 | 2015-01-02 | 2026-10-30 | 2957 | 52 | 29.57 | 0 | 0.07 | 0 | yellow | 0.16 | 0 | 1.04 | 0 | FAIL |
| net | t_ewma | 0.95 | 2015-01-02 | 2026-10-30 | 2957 | 168 | 147.85 | 0.1 | 0.08 | 0.05 | n/a | 0.01 | 0.37 | 0.15 | 0.05 | PASS |
| net | t_ewma | 0.99 | 2015-01-02 | 2026-10-30 | 2957 | 34 | 29.57 | 0.42 | 0.4 | 0.51 | green | 0.03 | 0.27 | 0.18 | 0.15 | PASS |

## Reading the table

One-day horizon, daily, exposure held at the previous close. Z1/Z2 are in losses: positive means realised tail losses exceeded the forecast ES. Verdict is PASS when Kupiec, Christoffersen, conditional coverage and Z2 all have p >= 0.05.
