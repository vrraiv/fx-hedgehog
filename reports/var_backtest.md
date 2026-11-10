# VaR / ES coverage backtest

## Results

| basis | method | confidence | oos_start | oos_end | n_obs | n_exceptions | expected_exceptions | kupiec_p | christoffersen_p | conditional_p | traffic_light | z1 | z1_p | z2 | z2_p | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| net | historical | 0.95 | 2015-01-02 | 2026-10-30 | 2957 | 135 | 147.85 | 0.27 | 0 | 0 | n/a | 0.01 | 0.35 | -0.08 | 0.83 | FAIL |
| net | historical | 0.99 | 2015-01-02 | 2026-10-30 | 2957 | 29 | 29.57 | 0.92 | 0 | 0 | green | -0.02 | 0.64 | -0.04 | 0.56 | FAIL |
| net | normal_sample | 0.95 | 2015-01-02 | 2026-10-30 | 2957 | 127 | 147.85 | 0.07 | 0 | 0 | n/a | 0.14 | 0 | -0.02 | 0.6 | FAIL |
| net | normal_sample | 0.99 | 2015-01-02 | 2026-10-30 | 2957 | 41 | 29.57 | 0.05 | 0 | 0 | green | 0.2 | 0 | 0.66 | 0 | FAIL |
| net | normal_ewma | 0.95 | 2015-01-02 | 2026-10-30 | 2957 | 154 | 147.85 | 0.61 | 0.01 | 0.02 | n/a | 0.14 | 0 | 0.19 | 0.01 | FAIL |
| net | normal_ewma | 0.99 | 2015-01-02 | 2026-10-30 | 2957 | 50 | 29.57 | 0 | 0.01 | 0 | green | 0.2 | 0 | 1.03 | 0 | FAIL |
| net | t_ewma | 0.95 | 2015-01-02 | 2026-10-30 | 2957 | 170 | 147.85 | 0.07 | 0.01 | 0.01 | n/a | 0.03 | 0.18 | 0.18 | 0.02 | FAIL |
| net | t_ewma | 0.99 | 2015-01-02 | 2026-10-30 | 2957 | 32 | 29.57 | 0.66 | 0 | 0.02 | green | 0.08 | 0.07 | 0.17 | 0.2 | FAIL |

## Reading the table

One-day horizon, daily, exposure held at the previous close. Z1/Z2 are in losses: positive means realised tail losses exceeded the forecast ES. Verdict is PASS when Kupiec, Christoffersen, conditional coverage and Z2 all have p >= 0.05.
