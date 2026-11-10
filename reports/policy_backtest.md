# Hedge-policy backtest

## Setup

Monthly rebalance from 2015-01-01 to 2026-10-30; ES budget USD 4.0m at 21 days / 99%; exposure input = forecast; one-month forwards priced by CIP at the origin; spreads from config/hedge.yaml charged on the notional dealt. P&L is the FX P&L of the group net exposure plus hedge mark-to-market, carry and spread; operating P&L is excluded.

## Summary by policy (USD m)

| policy | daily_vol_annualized_usd_m | monthly_vol_usd_m | total_pnl_usd_m | carry_per_year_usd_m | spread_per_year_usd_m | max_drawdown_usd_m | worst_month_usd_m | months_loss_gt_budget | n_months | mean_ex_ante_es_usd_m | share_months_binding |
|---|---|---|---|---|---|---|---|---|---|---|---|
| full_hedge | 7.03 | 1.91 | -1.34 | -0.89 | -0.62 | -21.39 | -7.77 | 2 | 142 | 0 | 0 |
| legacy_50 | 11.41 | 3.35 | -19.04 | -0.44 | -0.31 | -47.12 | -10.83 | 20 | 142 | 8.84 | 0 |
| optimizer | 8.19 | 2.3 | 10.18 | 2.2 | -0.23 | -19.13 | -9.31 | 5 | 142 | 3.73 | 0.62 |
| unhedged | 20.52 | 6.22 | -36.73 | 0 | 0 | -74.72 | -13.9 | 39 | 142 | 17.68 | 0 |

## Optimizer hedge ratios: mean over the backtest and at the last rebalance

| index | EUR | GBP | CAD | JPY | AUD | CHF | MXN | BRL | INR | SGD |
|---|---|---|---|---|---|---|---|---|---|---|
| mean | 1 | 0.98 | 0.99 | 0.95 | 0.87 | 0.99 | 0.21 | 0.09 | 0.01 | 1 |
| latest | 1 | 1 | 1 | 1 | 1 | 1 | 0.04 | 0 | 0 | 1 |

## Stress months (USD m)

| policy | month | pnl_unhedged | pnl_hedge_mtm | pnl_carry | pnl_spread | pnl_total | ex_ante_es_usd |
|---|---|---|---|---|---|---|---|
| full_hedge | 2020-03 | -10.63 | 11.73 | -0.05 | -0.06 | 1 | 0 |
| full_hedge | 2020-04 | 0.01 | -0.22 | -0.23 | -0.05 | -0.48 | 0 |
| full_hedge | 2022-09 | -9.65 | 6.5 | -0.03 | -0.04 | -3.21 | 0 |
| full_hedge | 2022-10 | 1.18 | -3.82 | 0.09 | -0.06 | -2.6 | 0 |
| legacy_50 | 2020-03 | -10.63 | 5.87 | -0.02 | -0.03 | -4.81 | 5.38 |
| legacy_50 | 2020-04 | 0.01 | -0.11 | -0.11 | -0.03 | -0.24 | 22.86 |
| legacy_50 | 2022-09 | -9.65 | 3.25 | -0.01 | -0.02 | -6.43 | 6.27 |
| legacy_50 | 2022-10 | 1.18 | -1.91 | 0.05 | -0.03 | -0.71 | 16.45 |
| optimizer | 2020-03 | -10.63 | 4.76 | 0.2 | -0.02 | -5.68 | 4 |
| optimizer | 2020-04 | 0.01 | -0.53 | -0.09 | -0.03 | -0.65 | 4 |
| optimizer | 2022-09 | -9.65 | 4.59 | 0.19 | -0.01 | -4.87 | 4 |
| optimizer | 2022-10 | 1.18 | -3.66 | 0.33 | -0.02 | -2.17 | 4 |
| unhedged | 2020-03 | -10.63 | 0 | 0 | 0 | -10.63 | 10.77 |
| unhedged | 2020-04 | 0.01 | 0 | 0 | 0 | 0.01 | 45.72 |
| unhedged | 2022-09 | -9.65 | 0 | 0 | 0 | -9.65 | 12.55 |
| unhedged | 2022-10 | 1.18 | 0 | 0 | 0 | 1.18 | 32.91 |

## By year (USD m)

| policy | year | pnl_total_usd | monthly_vol_usd | worst_month_usd | carry_usd | spread_usd | months_loss_gt_budget |
|---|---|---|---|---|---|---|---|
| full_hedge | 2015 | -4.4 | 1.12 | -2.44 | -4.91 | -0.5 | 0 |
| full_hedge | 2016 | -7.12 | 0.75 | -1.51 | -3.98 | -0.47 | 0 |
| full_hedge | 2017 | 1.4 | 1.14 | -1.36 | -2.48 | -0.55 | 0 |
| full_hedge | 2018 | -0.55 | 1.58 | -2.32 | 0.68 | -0.54 | 0 |
| full_hedge | 2019 | 5.55 | 1.43 | -2.08 | 1.32 | -0.59 | 0 |
| full_hedge | 2020 | -5.34 | 2.25 | -5.76 | -1.23 | -0.54 | 1 |
| full_hedge | 2021 | -0.07 | 1.11 | -2.82 | -1.61 | -0.65 | 0 |
| full_hedge | 2022 | -4.44 | 3.13 | -7.77 | -0.69 | -0.62 | 1 |
| full_hedge | 2023 | 10.87 | 2.37 | -3.23 | 0.94 | -0.65 | 0 |
| full_hedge | 2024 | -1.8 | 2.11 | -3.33 | 0.57 | -0.75 | 0 |
| full_hedge | 2025 | 6.99 | 2.79 | -2.66 | 0.79 | -0.77 | 0 |
| full_hedge | 2026 | -2.44 | 1.86 | -3.38 | 0.12 | -0.75 | 0 |
| legacy_50 | 2015 | -13.96 | 2.26 | -5.52 | -2.46 | -0.25 | 1 |
| legacy_50 | 2016 | -9.7 | 2.55 | -4.01 | -1.99 | -0.23 | 1 |
| legacy_50 | 2017 | 12.23 | 2.04 | -3.25 | -1.24 | -0.27 | 0 |
| legacy_50 | 2018 | -9.5 | 2.44 | -4.09 | 0.34 | -0.27 | 1 |
| legacy_50 | 2019 | 5.04 | 2.49 | -2.81 | 0.66 | -0.29 | 0 |
| legacy_50 | 2020 | 2.81 | 4.3 | -4.81 | -0.62 | -0.27 | 2 |
| legacy_50 | 2021 | -8.51 | 2.37 | -5.06 | -0.8 | -0.32 | 1 |
| legacy_50 | 2022 | -9.42 | 5 | -10.83 | -0.35 | -0.31 | 3 |
| legacy_50 | 2023 | 12.53 | 4.51 | -4.47 | 0.47 | -0.33 | 3 |
| legacy_50 | 2024 | -14.81 | 2.78 | -4.37 | 0.28 | -0.38 | 4 |
| legacy_50 | 2025 | 21.14 | 3.92 | -4.98 | 0.39 | -0.39 | 1 |
| legacy_50 | 2026 | -6.89 | 3.77 | -6.45 | 0.06 | -0.37 | 3 |
| optimizer | 2015 | -8.98 | 1.06 | -2.52 | -1.21 | -0.21 | 0 |
| optimizer | 2016 | -0.51 | 1.58 | -3.23 | -0.26 | -0.16 | 0 |
| optimizer | 2017 | 6.57 | 1.48 | -2.3 | 1.35 | -0.17 | 0 |
| optimizer | 2018 | -3.28 | 2 | -3.46 | 3.16 | -0.18 | 0 |
| optimizer | 2019 | 7.79 | 2.06 | -2.5 | 3.89 | -0.19 | 0 |
| optimizer | 2020 | -9.98 | 3.03 | -6.02 | 0.61 | -0.23 | 2 |
| optimizer | 2021 | 0.92 | 1.21 | -2.16 | 0.7 | -0.26 | 0 |
| optimizer | 2022 | -3.25 | 3.79 | -9.31 | 2.23 | -0.25 | 2 |
| optimizer | 2023 | 17.63 | 2.85 | -1.95 | 3.97 | -0.23 | 0 |
| optimizer | 2024 | -9.04 | 2.29 | -4.19 | 3.45 | -0.28 | 1 |
| optimizer | 2025 | 14.32 | 2.52 | -2.64 | 4.47 | -0.29 | 0 |
| optimizer | 2026 | -2.01 | 1.52 | -2.56 | 3.59 | -0.29 | 0 |
| unhedged | 2015 | -23.52 | 4.56 | -8.6 | 0 | 0 | 4 |
| unhedged | 2016 | -12.27 | 5.02 | -6.82 | 0 | 0 | 3 |
| unhedged | 2017 | 23.06 | 3.38 | -5.14 | 0 | 0 | 1 |
| unhedged | 2018 | -18.44 | 4.61 | -7.12 | 0 | 0 | 5 |
| unhedged | 2019 | 4.53 | 4.73 | -5.46 | 0 | 0 | 1 |
| unhedged | 2020 | 10.95 | 7.79 | -10.63 | 0 | 0 | 2 |
| unhedged | 2021 | -16.95 | 4.96 | -10.12 | 0 | 0 | 4 |
| unhedged | 2022 | -14.41 | 8.03 | -13.9 | 0 | 0 | 4 |
| unhedged | 2023 | 14.18 | 7.54 | -8.38 | 0 | 0 | 5 |
| unhedged | 2024 | -27.82 | 6.2 | -12.39 | 0 | 0 | 5 |
| unhedged | 2025 | 35.29 | 8.15 | -13.12 | 0 | 0 | 2 |
| unhedged | 2026 | -11.34 | 7.8 | -11.25 | 0 | 0 | 3 |

## Figures

![cumulative](figures/policy_cumulative_pnl.png)

![ratios](figures/policy_hedge_ratios.png)

![monthly](figures/policy_monthly_pnl.png)
