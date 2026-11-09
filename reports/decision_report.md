# FX hedging decision report as of 2026-10-30

## Summary

Generated 2026-11-09 23:33 UTC from market data retrieved 2026-11-06; data quality **WARN**; ES budget USD 4m at 21 days / 99%; exposure input: calendar_ar1 median forecast, 21 days ahead.

## The question and the answer

*For a fixed Expected Shortfall budget at the 21-day horizon, what hedge ratios by currency minimise expected hedging cost, and how would that policy have performed out of sample from 2015 to the present, including March 2020 and 2022?*

**With a 21-day 99% Expected Shortfall budget of USD 4m, hedge EUR, GBP, CAD, JPY, AUD, CHF, SGD in full; MXN 7%, BRL 70%; leave INR unhedged.** That programme earns about USD 2.2m a year of carry against USD 0.5m of bid-ask spread, and cuts the ES of the forecast book from USD 19.6m to USD 4.0m. Out of sample from 2015 with a monthly rebalance (142 months), the policy's annualized P&L volatility is USD 8.2m against 20.5m unhedged and 7.0m for a full hedge; its total P&L is USD 10.1m (-36.3m unhedged, -1.4m full hedge), its maximum drawdown USD -19.0m (-74.5m unhedged), and 5 of 142 months lost more than the budget (39 unhedged, 2 full hedge).

| ccy | forecast exposure (USD m) | hedge ratio | forward notional (USD m) | carry % / yr (+ = costs) | spread bp | rate source |
|---|---|---|---|---|---|---|
| EUR | 127.23 | 1 | -127.23 | -1.55 | 0.5 | bis:D.XM |
| GBP | 92.63 | 1 | -92.63 | -0.34 | 0.7 | bis:D.GB |
| CAD | 54.84 | 1 | -54.84 | -1.54 | 0.7 | boc:TB.CDN.90D.MID |
| JPY | 19.49 | 1 | -19.49 | -2.5 | 0.6 | fred:IR3TIB01JPM156N |
| AUD | 12.02 | 1 | -12.02 | 0.42 | 0.9 | fred:IR3TIB01AUM156N |
| CHF | 15.69 | 1 | -15.69 | -4.13 | 0.8 | fred:IR3TIB01CHM156N |
| MXN | 24.4 | 0.07 | -1.7 | 2.8 | 3 | fred:IR3TIB01MXM156N |
| BRL | 28.44 | 0.7 | -19.87 | 9.74 | 8 | fred:IRSTCI01BRM156N |
| INR | 30.03 | 0 | 0 | 1.41 | 6 | fred:IRSTCI01INM156N |
| SGD | 13.07 | 1 | -13.07 | 0 | 1.5 | proxy:USD:DTB3 |

Carry is the annualized forward discount of the currency against USD (positive: selling the currency forward costs money; negative: it earns). The optimizer spends the budget where risk reduction is expensive and hedges everything that is cheap or free to hedge: a full hedge costs USD 0.52m a year for zero residual ES, while at the USD 4m budget the cost is USD -1.78m a year (negative = the programme earns carry). Beyond a budget of about USD 10m the constraint stops binding and the policy is simply 'hedge every currency whose forward earns carry', which is the cheapest book regardless of risk. The out-of-sample evidence is in the policy section below.

## Data and quality

Market data: 8 checks on 2026-11-06 retrievals, overall **WARN** (`reports/quality_report.md`, `reports/alerts.md`). Sources are FRED H.10 noon rates (primary), Bank of Canada and ECB crosses (reconciliation and fallback), BIS policy rates and effective exchange rates, OECD short rates via FRED, and US and Canadian retail sales for the seasonality of the synthetic flows. The flows themselves are generated from `config/flows.yaml`; no real company's data is used.

| check | status | summary |
|---|---|---|
| cache_complete | PASS | all 77 registered series cached |
| schema | PASS | all cached files well-formed |
| staleness | WARN | 2 series stale or lagging |
| reconciliation | PASS | all 20 currency/source pairs within tolerance |
| master_completeness | PASS | 0 NULL cells across 10 currencies; 1 cells filled from BoC/ECB |
| calendar | PASS | no gaps longer than 6 calendar days |
| return_outliers | WARN | 33 daily moves beyond 6 EWMA sigma (review, not necessarily errors) |
| rates_range | PASS | all 22 rate series within [-2.0, 40.0] percent |

## Exposure waterfall

Net open exposure by currency on 2026-10-30, USD millions. *Gross* is the sum of the absolute components (receivables in flight, cash balances, merchant payables, intercompany loans) across the four entities; *net* nets them within a currency across entities; *net of hedges* adds the forwards in force on that date (the optimizer's positions where the policy has dealt, else the legacy 50% placeholder). Netting takes the group from USD 1,088m gross to 232m of absolute net exposure, and hedges to 262m. The largest net position is EUR at USD 62.9m. A negative net-of-hedges figure on a month-end is expected: exposure in the synthetic business dips on the last day of the month when fees are swept and weekly payouts land, while the forward in force was sized on the forecast for the policy's 21-day target date and runs until the next rebalance (ADR-0013; the history figure plots monthly averages for that reason).

| ccy | gross_usd_m | net_usd_m | hedge_usd_m | net_of_hedges_usd_m |
|---|---|---|---|---|
| EUR | 371.9 | 62.9 | -167.2 | -104.3 |
| GBP | 284.5 | 46.9 | -122.7 | -75.8 |
| CAD | 237.2 | 32.9 | -42.5 | -9.6 |
| INR | 32.1 | 21.6 | 0 | 21.6 |
| BRL | 29.1 | 19.6 | 0 | 19.6 |
| MXN | 32.3 | 14.1 | -1.4 | 12.7 |
| JPY | 20.7 | 11.3 | -13.2 | -2 |
| SGD | 23.4 | 8 | -9.9 | -1.9 |
| AUD | 28.5 | 7.3 | -8.9 | -1.6 |
| CHF | 28.4 | 7.3 | -20 | -12.7 |
| TOTAL (abs) | 1,088.2 | 231.9 | 385.8 | 261.7 |

![exposure waterfall](figures/exposure_waterfall.png)

![exposure history](figures/exposure_history.png)

By entity on the same date (USD m; the US parent's intercompany loans are the subsidiaries' intercompany liabilities):

| entity | ccy | in_flight_m | balance_m | payable_m | intercompany_m | net_m |
|---|---|---|---|---|---|---|
| CA | CAD | 37.1 | 21.2 | -34.4 | -54.7 | -30.8 |
| CA | USD | 20.4 | 11.8 | -19 | 0 | 13.2 |
| EA | CHF | 8.6 | 4.7 | -7.9 | 0 | 5.5 |
| EA | EUR | 85.6 | 45.3 | -77.3 | -63.9 | -10.3 |
| EA | GBP | 12.8 | 6.8 | -11.6 | 0 | 8 |
| UK | CHF | 2.9 | 1.6 | -2.7 | 0 | 1.9 |
| UK | EUR | 14.7 | 7.8 | -13.3 | 0 | 9.2 |
| UK | GBP | 61.5 | 33.4 | -56 | -51.2 | -12.3 |
| US | AUD | 11.4 | 6.5 | -10.6 | 0 | 7.3 |
| US | BRL | 19.3 | 5.1 | -4.8 | 0 | 19.6 |
| US | CAD | 14.4 | 7.7 | -13 | 54.7 | 63.8 |
| US | EUR | 0 | 0 | 0 | 63.9 | 63.9 |
| US | GBP | 0 | 0 | 0 | 51.2 | 51.2 |
| US | INR | 20.8 | 6.1 | -5.3 | 0 | 21.6 |
| US | JPY | 10.2 | 5.8 | -4.7 | 0 | 11.3 |
| US | MXN | 16.2 | 7 | -9.1 | 0 | 14.1 |
| US | SGD | 10 | 5.6 | -7.7 | 0 | 8 |
| US | USD | 189.8 | 113.8 | -179.3 | 0 | 124.3 |

## Exposure forecast and its calibration

The hedge is sized on the forecast of net exposure at the end of the next rebalance period, not on today's book, because today's receivables will have settled by then. The model is a calendar-structural regression of log exposure on weekday, month-end and month-start position, month and trend, with AR(1) errors (ADR-0011). Rolling-origin evaluation over monthly origins from 2014 against a seasonal-naive baseline:

| horizon | pinball_pct | mape_median_pct | coverage_50 | coverage_80 | coverage_95 | skill_vs_naive |
|---|---|---|---|---|---|---|
| 1 | 2.08 | 7.28 | 0.43 | 0.71 | 0.88 | 0.76 |
| 5 | 1.52 | 5.11 | 0.42 | 0.69 | 0.87 | 0.81 |
| 10 | 1.49 | 5.07 | 0.39 | 0.67 | 0.86 | 0.8 |
| 21 | 1.98 | 6.82 | 0.4 | 0.7 | 0.86 | 0.8 |
| 42 | 2.12 | 7.36 | 0.4 | 0.69 | 0.86 | 0.77 |
| 63 | 2.03 | 6.93 | 0.42 | 0.69 | 0.83 | 0.77 |

At the policy horizon the model's skill against the naive is 0.80 (pinball loss reduced by 80%) and its nominal 95% interval covers 86% of outcomes. The intervals are therefore too narrow; the report states that rather than widening them after the fact, and the hedge policy uses the median, not the band. The calibration figure shows coverage by horizon and quantile.

![forecast calibration](figures/forecast_calibration.png)

Latest 21-day-ahead forecast (currency units):

| ccy | target_date | 2.5% | median | 97.5% |
|---|---|---|---|---|
| EUR | 2026-11-30 | 104,266,570 | 113,974,414 | 128,094,997 |
| GBP | 2026-11-30 | 62,068,567 | 69,137,160 | 81,776,157 |
| CAD | 2026-11-30 | 67,782,904 | 76,545,688 | 83,746,894 |
| JPY | 2026-11-30 | 2,809,814,005 | 3,068,977,555 | 3,519,839,721 |
| AUD | 2026-11-30 | 15,569,837 | 17,081,086 | 18,682,026 |
| CHF | 2026-11-30 | 11,180,032 | 12,911,068 | 14,667,993 |
| MXN | 2026-11-30 | 413,998,062 | 458,597,511 | 511,957,519 |
| BRL | 2026-11-30 | 144,786,085 | 154,288,684 | 173,017,064 |
| INR | 2026-11-30 | 2,673,573,542 | 2,850,916,615 | 3,019,189,175 |
| SGD | 2026-11-30 | 14,899,237 | 16,700,976 | 18,696,780 |

## Risk model: VaR, Expected Shortfall and the coverage verdicts

Expected Shortfall at 21 days / 99% on 2026-10-30, USD m, for every method family in the engine, on the net exposure and on the exposure net of hedges in force:

| label | net | net_of_hedges |
|---|---|---|
| historical / none | 6.83 | 12.94 |
| monte_carlo_t / ewma_0.94 | 8.76 | 8.47 |
| monte_carlo_t / ewma_0.97 | 8.65 | 8.11 |
| parametric_normal / ewma_0.94 | 8.64 | 8.22 |
| parametric_normal / ewma_0.97 | 8.44 | 7.78 |
| parametric_normal / ledoit_wolf | 9.98 | 9.87 |
| parametric_normal / sample | 10.03 | 9.89 |
| parametric_t / ewma_0.94 | 11.23 | 10.57 |
| parametric_t / ewma_0.97 | 10.97 | 10.01 |
| parametric_t / ledoit_wolf | 12.97 | 12.69 |
| parametric_t / sample | 13.04 | 12.72 |

Which of these to believe is decided by the one-day coverage backtest from 2015 (Kupiec unconditional coverage, Christoffersen independence, Basel traffic light, Acerbi-Szekely Z2 for ES). A verdict of PASS needs every p-value at or above 0.05. Passing: normal_ewma at 95%; t_ewma at 99%.

| basis | method | confidence | exceptions | expected | Kupiec p | Christoffersen p | traffic light | AS Z2 p | verdict |
|---|---|---|---|---|---|---|---|---|---|
| net | historical | 0.95 | 151 | 147.9 | 0.79 | 0 | n/a | 0.46 | FAIL |
| net | historical | 0.99 | 30 | 29.6 | 0.94 | 0 | green | 0.52 | FAIL |
| net | normal_sample | 0.95 | 139 | 147.9 | 0.45 | 0 | n/a | 0.3 | FAIL |
| net | normal_sample | 0.99 | 42 | 29.6 | 0.03 | 0 | green | 0 | FAIL |
| net | normal_ewma | 0.95 | 148 | 147.9 | 0.99 | 0.1 | n/a | 0.05 | PASS |
| net | normal_ewma | 0.99 | 52 | 29.6 | 0 | 0.07 | yellow | 0 | FAIL |
| net | t_ewma | 0.95 | 168 | 147.9 | 0.1 | 0.08 | n/a | 0.04 | FAIL |
| net | t_ewma | 0.99 | 34 | 29.6 | 0.42 | 0.4 | green | 0.17 | PASS |

The optimizer therefore uses the Student-t model with EWMA(0.94) covariance (tail index 4.9 on the latest window). Multi-day coverage is not tested formally because overlapping windows break the tests' independence assumption (ADR-0010); the 21-day ES is the one-day model scaled by the square-root of time under the t distribution.

## Stress

Historical replays of five episodes and four hypothetical shocks applied to the net exposure on 2026-10-30, P&L in USD m. *Propagated* means the shock is given to the named currencies and the others move by their Gaussian conditional expectation; otherwise only the named currencies move.

| scenario | kind | largest_move | propagated | net | net_of_hedges |
|---|---|---|---|---|---|
| chf_depeg_2015 | historical | CHF +18.1% | no | -0.49 | 0.55 |
| brexit_2016 | historical | GBP -11.3% | no | -9 | 10.73 |
| covid_2020 | historical | MXN -17.5% | no | -16.59 | 11.08 |
| usd_surge_2022 | historical | GBP -13.3% | no | -15.8 | 16.09 |
| taper_tantrum_2013 | historical | INR -16.7% | no | -4.58 | -12.39 |
| usd_up_10 | hypothetical | EUR -10.0% | no | -22.07 | 14.65 |
| em_selloff_15 | hypothetical | MXN -15.0% | no | -6.75 | -6.55 |
| em_selloff_15 | hypothetical | MXN -15.0% | yes | -13.83 | 2.37 |
| eur_down_10 | hypothetical | EUR -10.0% | no | -5.98 | 9.93 |
| eur_down_10 | hypothetical | EUR -10.0% | yes | -16.48 | 16.04 |
| jpy_up_10 | hypothetical | BRL +11.0% | yes | 10.26 | -6.01 |
| jpy_up_10 | hypothetical | JPY +10.0% | no | 1.18 | -0.21 |

## Cost of risk reduction: the frontier and the chosen point

The frontier traces the minimum expected hedging cost (carry plus spread, per year) for every ES budget from zero (full hedge) to the unhedged ES. A full hedge costs USD 0.52m a year for zero residual ES, while at the USD 4m budget the cost is USD -1.78m a year (negative = the programme earns carry). Beyond a budget of about USD 10m the constraint stops binding and the policy is simply 'hedge every currency whose forward earns carry', which is the cheapest book regardless of risk. Reference policies at today's exposures:

| policy | residual_es_usd_m | annual_cost_usd_m |
|---|---|---|
| unhedged | 19.55 | 0 |
| legacy_50 | 9.78 | 0.26 |
| full_hedge | 0 | 0.52 |
| optimizer | 4 | -1.76 |

![cost-risk frontier](figures/hedge_frontier.png)

The optimizer is a convex programme (linear cost, ES of a linear book under an elliptical distribution is a norm of an affine function of the ratios) solved with SLSQP, with a 2 bp turnover regulariser so ratios do not flip between 0 and 1 on tiny carry differences when the budget is slack (ADR-0012).

## Out-of-sample policy performance, 2015 to the present

Walk-forward backtest, monthly rebalance from 2015-01-01, one-month forwards priced by covered interest parity at each origin, hedging the 21-day forecast; P&L marked on the actual daily exposure path with forward mark-to-market, carry accrual and spread (ADR-0013). No look-ahead: covariance, tail index, rates and forecasts use data up to the origin only.

| policy | P&L vol (USD m / yr) | total P&L (USD m) | carry + spread / yr | max drawdown | worst month | months loss > budget | share of months budget binds |
|---|---|---|---|---|---|---|---|
| unhedged | 20.5 | -36.3 | 0 | -74.5 | -13.9 | 39 | 0 |
| legacy 50% | 11.4 | -18.8 | -0.8 | -47.1 | -10.9 | 21 | 0 |
| full hedge | 7 | -1.4 | -1.5 | -21.7 | -7.8 | 2 | 0 |
| optimizer | 8.2 | 10.1 | 1.9 | -19 | -9.4 | 5 | 0.61 |

Mean optimizer hedge ratio over the backtest: EUR 1.00, GBP 0.99, CAD 0.99, JPY 0.96, AUD 0.87, CHF 0.99, MXN 0.21, BRL 0.09, INR 0.01, SGD 1.00.

![cumulative P&L by policy](figures/policy_cumulative_pnl.png)

![optimizer hedge ratios by month](figures/policy_hedge_ratios.png)

**March 2020 and 2022.** Monthly P&L by policy in the four stress months, USD m:

| month | unhedged | legacy 50% | full hedge | optimizer | optimizer ex-ante ES |
|---|---|---|---|---|---|
| 2020-03 | -10.6 | -4.77 | 1.05 | -5.65 | 4 |
| 2020-04 | 0.03 | -0.2 | -0.43 | -0.6 | 4 |
| 2022-09 | -9.66 | -6.47 | -3.28 | -4.94 | 4 |
| 2022-10 | 1.18 | -0.78 | -2.73 | -2.3 | 4 |

The optimizer's worst of the four was 2020-03 at USD -5.6m against an ex-ante ES of 4.0m: the budget bounds the risk of the hedged *forecast* exposure, not forecast error or intra-month exposure swings, which is also why the full hedge keeps USD 7.0m of annual P&L volatility.

**By year** (total P&L, USD m):

| year | unhedged | legacy 50% | full hedge | optimizer | optimizer months loss > budget |
|---|---|---|---|---|---|
| 2015 | -23.7 | -14.2 | -4.7 | -9.2 | 0 |
| 2016 | -12.3 | -9.7 | -7.1 | -0.5 | 0 |
| 2017 | 23 | 12.3 | 1.5 | 6.5 | 0 |
| 2018 | -18.3 | -9.4 | -0.4 | -3.1 | 0 |
| 2019 | 4.5 | 5.1 | 5.6 | 7.9 | 0 |
| 2020 | 11 | 2.9 | -5.2 | -9.9 | 2 |
| 2021 | -16.7 | -8.4 | 0 | 1 | 0 |
| 2022 | -14.3 | -9.7 | -5 | -3.3 | 2 |
| 2023 | 14.3 | 12.4 | 10.6 | 17.4 | 0 |
| 2024 | -27.9 | -14.8 | -1.6 | -8.9 | 1 |
| 2025 | 35.5 | 21.4 | 7.4 | 14.7 | 0 |
| 2026 | -11.4 | -6.9 | -2.4 | -2.4 | 0 |

![monthly P&L distribution by policy](figures/policy_monthly_pnl.png)

## What this model does not know

* **The business is synthetic.** Volumes, settlement lags, payout cadences and the 2020 regimes are stylized and calibrated only to public retail-sales seasonality (ADR-0008). The *method* transfers to a real book; the numbers do not.
* **The ES budget covers the hedged forecast exposure only.** Forecast error and intra-month exposure variation are outside it, which is why 5 of 142 backtest months lost more than the budget and why even a full hedge retains P&L volatility (ADR-0013). A budget meant to bound realized monthly loss would need to be set lower, or the policy would need an intra-month adjustment rule (backlog B17).
* **Forecast intervals are too narrow.** The nominal 95% band covers 86% at the 21-day horizon (ADR-0011, backlog B16). The policy uses the median, so this affects the risk statement, not the hedge sizes.
* **Carry is an expected cost under a random-walk spot.** Realized hedging cost in the backtest includes the spot move and can have either sign; the carry signal itself is not a forecast of returns (hedging primer, section 3).
* **Forwards only.** No options, no cross-currency basis, no NDF basis for BRL and INR; one-way spreads are stylized round numbers from `config/hedge.yaml` (hedging primer, section 5; backlog B3, B4, B18).
* **Short rates are monthly OECD series for most currencies**, forward-filled, with BIS policy rates as the fallback when a series lags; the SGD rate is a flagged USD proxy so SGD carry is zero by construction (ADR-0006, backlog B1, B2).
* **Coverage is tested at one day.** The 21-day ES is a scaled one-day model; the overlapping-window tests at longer horizons have too little power to be decisive (ADR-0010, backlog B11).
* **One risk model inside the optimizer.** The Student-t EWMA model is the one that passed the tests on this book; a different book might prefer another, and the engine reports all of them so that choice can be revisited.
* **Fixing-time mismatches** between sources (noon New York, 14:15 CET, Bank of Canada daily average) are reconciled within tolerance, not modelled (ADR-0005).
* **Weekday calendar, no holidays**, for settlement and payouts (backlog B9).

## Reproducing this report

```bash
uv sync --all-groups
uv run fxrisk all      # fetch (cache) -> quality -> flows -> exposure -> forecast -> backtest -> hedge -> risk -> report
```

Every number above is read from the DuckDB tables the stages write (`data/fxrisk.duckdb`); `fxrisk report` recomputes nothing. Inputs: `config/flows.yaml` (the stylized business), `config/hedge.yaml` (budget, costs, policies), `data/cache/` (market data with provenance in `manifest.json`). Methods: `docs/methodology.md`; decisions: `docs/decisions/`; instrument mechanics: `docs/hedging-primer.md`. Package version 0.1.0.
