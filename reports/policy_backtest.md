# Hedge-policy backtest

## Setup

Monthly rebalance from 2015-01-01 to 2026-10-30; ES budget USD 4.0m at 21 days / 99%; exposure input = forecast; one-month forwards priced by CIP at the origin; spreads from config/hedge.yaml charged on the notional dealt. P&L is the FX P&L of the group net exposure plus hedge mark-to-market, carry and spread; operating P&L is excluded.

## Summary by policy (USD m)

| policy | daily_vol_annualized_usd_m | monthly_vol_usd_m | total_pnl_usd_m | carry_per_year_usd_m | spread_per_year_usd_m | max_drawdown_usd_m | worst_month_usd_m | months_loss_gt_budget | n_months | mean_ex_ante_es_usd_m | share_months_binding |
|---|---|---|---|---|---|---|---|---|---|---|---|
| full_hedge | 7.03 | 1.92 | -1.96 | -0.97 | -0.62 | -21.4 | -7.84 | 2 | 142 | 0 | 0 |
| legacy_50 | 11.41 | 3.36 | -19.13 | -0.48 | -0.31 | -45.8 | -10.89 | 21 | 142 | 8.84 | 0 |
| optimizer | 8.18 | 2.31 | 9.57 | 2.12 | -0.23 | -19.05 | -9.37 | 5 | 142 | 3.72 | 0.61 |
| unhedged | 20.52 | 6.22 | -36.3 | 0 | 0 | -72.3 | -13.94 | 39 | 142 | 17.68 | 0 |

## Optimizer hedge ratios: mean over the backtest and at the last rebalance

| index | EUR | GBP | CAD | JPY | AUD | CHF | MXN | BRL | INR | SGD |
|---|---|---|---|---|---|---|---|---|---|---|
| mean | 1 | 0.99 | 0.99 | 0.96 | 0.87 | 0.99 | 0.21 | 0.09 | 0.01 | 1 |
| latest | 1 | 1 | 1 | 1 | 1 | 1 | 0.07 | 0 | 0 | 1 |

## Stress months (USD m)

| policy | month | pnl_unhedged | pnl_hedge_mtm | pnl_carry | pnl_spread | pnl_total | ex_ante_es_usd |
|---|---|---|---|---|---|---|---|
| full_hedge | 2020-03 | -10.6 | 11.75 | -0.04 | -0.06 | 1.05 | 0 |
| full_hedge | 2020-04 | 0.03 | -0.22 | -0.2 | -0.05 | -0.43 | 0 |
| full_hedge | 2022-09 | -9.66 | 6.49 | -0.07 | -0.04 | -3.29 | 0 |
| full_hedge | 2022-10 | 1.18 | -3.83 | -0.03 | -0.06 | -2.73 | 0 |
| legacy_50 | 2020-03 | -10.6 | 5.88 | -0.02 | -0.03 | -4.78 | 5.39 |
| legacy_50 | 2020-04 | 0.03 | -0.11 | -0.1 | -0.03 | -0.2 | 22.96 |
| legacy_50 | 2022-09 | -9.66 | 3.24 | -0.04 | -0.02 | -6.47 | 6.26 |
| legacy_50 | 2022-10 | 1.18 | -1.92 | -0.01 | -0.03 | -0.78 | 16.48 |
| optimizer | 2020-03 | -10.6 | 4.77 | 0.2 | -0.02 | -5.65 | 4 |
| optimizer | 2020-04 | 0.03 | -0.54 | -0.07 | -0.03 | -0.6 | 4 |
| optimizer | 2022-09 | -9.66 | 4.57 | 0.16 | -0.01 | -4.94 | 4 |
| optimizer | 2022-10 | 1.18 | -3.69 | 0.22 | -0.02 | -2.31 | 4 |
| unhedged | 2020-03 | -10.6 | 0 | 0 | 0 | -10.6 | 10.78 |
| unhedged | 2020-04 | 0.03 | 0 | 0 | 0 | 0.03 | 45.93 |
| unhedged | 2022-09 | -9.66 | 0 | 0 | 0 | -9.66 | 12.53 |
| unhedged | 2022-10 | 1.18 | 0 | 0 | 0 | 1.18 | 32.95 |

## By year (USD m)

| policy | year | pnl_total_usd | monthly_vol_usd | worst_month_usd | carry_usd | spread_usd | months_loss_gt_budget |
|---|---|---|---|---|---|---|---|
| full_hedge | 2015 | -4.67 | 1.11 | -2.45 | -4.92 | -0.5 | 0 |
| full_hedge | 2016 | -7.11 | 0.75 | -1.52 | -3.94 | -0.47 | 0 |
| full_hedge | 2017 | 1.48 | 1.13 | -1.35 | -2.37 | -0.55 | 0 |
| full_hedge | 2018 | -0.46 | 1.58 | -2.36 | 0.64 | -0.54 | 0 |
| full_hedge | 2019 | 5.61 | 1.43 | -2.09 | 1.37 | -0.59 | 0 |
| full_hedge | 2020 | -5.16 | 2.24 | -5.72 | -1.07 | -0.54 | 1 |
| full_hedge | 2021 | -0.04 | 1.11 | -2.81 | -1.71 | -0.65 | 0 |
| full_hedge | 2022 | -5 | 3.16 | -7.84 | -1.39 | -0.62 | 1 |
| full_hedge | 2023 | 10.47 | 2.38 | -3.25 | 0.41 | -0.65 | 0 |
| full_hedge | 2024 | -1.82 | 2.13 | -3.33 | 0.63 | -0.75 | 0 |
| full_hedge | 2025 | 7.24 | 2.79 | -2.62 | 0.84 | -0.77 | 0 |
| full_hedge | 2026 | -2.49 | 1.85 | -3.42 | 0.09 | -0.75 | 0 |
| legacy_50 | 2015 | -14.18 | 2.27 | -5.53 | -2.46 | -0.25 | 1 |
| legacy_50 | 2016 | -9.7 | 2.57 | -4.02 | -1.97 | -0.23 | 1 |
| legacy_50 | 2017 | 12.26 | 2.02 | -3.24 | -1.18 | -0.27 | 0 |
| legacy_50 | 2018 | -9.4 | 2.43 | -4.05 | 0.32 | -0.27 | 1 |
| legacy_50 | 2019 | 5.08 | 2.5 | -2.83 | 0.69 | -0.3 | 0 |
| legacy_50 | 2020 | 2.94 | 4.27 | -4.78 | -0.54 | -0.27 | 2 |
| legacy_50 | 2021 | -8.36 | 2.38 | -5.1 | -0.85 | -0.32 | 2 |
| legacy_50 | 2022 | -9.67 | 5.03 | -10.89 | -0.69 | -0.31 | 3 |
| legacy_50 | 2023 | 12.36 | 4.52 | -4.53 | 0.21 | -0.33 | 3 |
| legacy_50 | 2024 | -14.87 | 2.79 | -4.41 | 0.31 | -0.38 | 4 |
| legacy_50 | 2025 | 21.36 | 3.92 | -4.94 | 0.42 | -0.39 | 1 |
| legacy_50 | 2026 | -6.93 | 3.75 | -6.41 | 0.04 | -0.37 | 3 |
| optimizer | 2015 | -9.23 | 1.06 | -2.55 | -1.19 | -0.2 | 0 |
| optimizer | 2016 | -0.47 | 1.59 | -3.25 | -0.24 | -0.16 | 0 |
| optimizer | 2017 | 6.53 | 1.47 | -2.3 | 1.36 | -0.17 | 0 |
| optimizer | 2018 | -3.16 | 1.99 | -3.42 | 3.12 | -0.18 | 0 |
| optimizer | 2019 | 7.84 | 2.07 | -2.47 | 3.9 | -0.19 | 0 |
| optimizer | 2020 | -9.9 | 3.01 | -6 | 0.7 | -0.23 | 2 |
| optimizer | 2021 | 1.04 | 1.21 | -2.14 | 0.69 | -0.25 | 0 |
| optimizer | 2022 | -3.35 | 3.85 | -9.37 | 1.71 | -0.25 | 2 |
| optimizer | 2023 | 17.25 | 2.86 | -1.96 | 3.48 | -0.23 | 0 |
| optimizer | 2024 | -9.06 | 2.31 | -4.22 | 3.5 | -0.28 | 1 |
| optimizer | 2025 | 14.61 | 2.53 | -2.68 | 4.56 | -0.29 | 0 |
| optimizer | 2026 | -2.52 | 1.55 | -2.62 | 3.52 | -0.29 | 0 |
| unhedged | 2015 | -23.69 | 4.57 | -8.61 | 0 | 0 | 4 |
| unhedged | 2016 | -12.29 | 5.03 | -6.82 | 0 | 0 | 3 |
| unhedged | 2017 | 23.04 | 3.36 | -5.13 | 0 | 0 | 1 |
| unhedged | 2018 | -18.35 | 4.6 | -7.12 | 0 | 0 | 5 |
| unhedged | 2019 | 4.54 | 4.74 | -5.45 | 0 | 0 | 1 |
| unhedged | 2020 | 11.03 | 7.77 | -10.6 | 0 | 0 | 2 |
| unhedged | 2021 | -16.68 | 4.96 | -10.12 | 0 | 0 | 4 |
| unhedged | 2022 | -14.34 | 8.05 | -13.94 | 0 | 0 | 4 |
| unhedged | 2023 | 14.26 | 7.54 | -8.39 | 0 | 0 | 5 |
| unhedged | 2024 | -27.92 | 6.21 | -12.37 | 0 | 0 | 5 |
| unhedged | 2025 | 35.47 | 8.16 | -13.11 | 0 | 0 | 2 |
| unhedged | 2026 | -11.37 | 7.79 | -11.28 | 0 | 0 | 3 |

## Figures

![cumulative](figures/policy_cumulative_pnl.png)

![ratios](figures/policy_hedge_ratios.png)

![monthly](figures/policy_monthly_pnl.png)
