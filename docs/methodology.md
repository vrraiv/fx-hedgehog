# Methodology

This document fixes the conventions every module uses. When code and this document
disagree, the code is wrong. Sections follow the pipeline: data, flows, exposure, risk,
forecasting, hedging, backtesting, reporting.

## 1. Conventions

### 1.1 Reporting currency and quote direction

* **Reporting currency:** USD. Every risk number is a USD amount.
* **FX quote convention:** `usd_per_fcy` = US dollars per **one unit** of foreign currency.
  EUR 1.10 means one euro costs 1.10 dollars; JPY 0.0067 means one yen costs 0.67 cents.
  A *rising* `usd_per_fcy` means the foreign currency *strengthened* against the dollar.
* **Why this direction:** the USD value of a foreign-currency position is simply
  `amount_fcy * usd_per_fcy`, and the log return of `usd_per_fcy` *is* the return on
  holding that currency. Market conventions (EURUSD quoted one way, USDJPY the other) are
  handled once, in `sql/030_fx_usd_per_fcy.sql`, and never leak into the risk code.
* Source conventions are catalogued in `fx_treasury_risk/data/registry.py` (field
  `quote`): FRED mixes `USD_PER_FCY` and `FCY_PER_USD`; the Bank of Canada quotes
  `CAD_PER_FCY`; the ECB quotes `FCY_PER_EUR`.

### 1.2 Exposure sign

* **Positive exposure = long the foreign currency**: cash balances held, receivables,
  merchant settlements due to be received. The business gains when `usd_per_fcy` rises.
* **Negative exposure = short the foreign currency**: payouts owed, payables, funding
  drawn in that currency. The business loses when `usd_per_fcy` rises.
* P&L on an unhedged exposure over a horizon is `exposure_fcy * (S_T - S_0)` in USD, where
  `S` is `usd_per_fcy`. The risk engine works with log returns `r = ln(S_T / S_0)` and
  approximates P&L as `exposure_usd * r` where `exposure_usd = exposure_fcy * S_0`.

### 1.3 Interest rates

* All rates are **annualized, in percent**, as published: central-bank policy rates for
  every currency (ADR-0015). Day-count conventions differ by market (ACT/360 for USD, EUR,
  JPY, CHF and MXN, ACT/365 for GBP, CAD, AUD, BRL and INR); the hedging primer states the
  error the convention introduces at the horizons used here (well below a basis point of
  forward points).

### 1.4 Calendar and horizons

* The master calendar is the set of **New York business days** on which the Federal
  Reserve published H.10 rates. Sources that trade on US holidays are dropped on those
  days so that every daily return spans one NY trading day.
* Horizons are counted in trading days: 1, 10 and 21 (one month). A year has 252.

## 2. Data layer

### 2.1 Sources and precedence

| Role | Source | Series | Fixing time |
|---|---|---|---|
| Primary USD crosses | FRED H.10 | `DEXUSEU`, `DEXUSUK`, `DEXCAUS`, `DEXJPUS`, `DEXUSAL`, `DEXSZUS`, `DEXMXUS`, `DEXBZUS`, `DEXINUS`, `DEXSIUS` | noon, New York |
| Cross-check and fallback 1 | Bank of Canada Valet | `FXUSDCAD` + nine `FX*CAD` (2017-), legacy noon series `IEXE*` / `EUROCAE01` (2010-2017) | daily average (current) / noon (legacy), Toronto |
| Cross-check and fallback 2 | ECB Data Portal | `EXR.D.<CCY>.EUR.SP00.A` for ten currencies | 14:15 CET |
| Short rates | BIS `WS_CBPOL` policy rates; ECB deposit facility rate for the euro area | see ADR-0015 | |
| Stress sanity check | BIS `WS_EER` nominal broad effective exchange rates, daily | | |
| Flow seasonality | FRED `RSXFSN`/`RSXFS`; StatCan table 20-10-0056-01 | | |

The master FX table (`fx_usd_master`) takes FRED first, then the BoC-derived cross, then
the ECB-derived cross, and records which one was used in `source_used`. Over 2010-2026
FRED fills all but one cell.

### 2.2 Deriving USD crosses from CAD and EUR quotes

With BoC quotes `cad_per_fcy` and `cad_per_usd`:

    usd_per_fcy = cad_per_fcy / cad_per_usd

With ECB quotes `fcy_per_eur` and `usd_per_eur`:

    usd_per_fcy = usd_per_eur / fcy_per_eur

Both divisions use same-day fixings of the same source. For the BoC the two vintages
(legacy noon to 2017-04-28, daily average from 2017-01-03) are never mixed within a
division; where both exist the current vintage wins.

### 2.3 Reconciliation

For each day and currency the log difference of the derived cross against FRED is
computed (`sql/040_fx_reconciliation.sql`). Log differences are used because they are
symmetric and approximately percentage differences. Expected disagreement is non-zero and
driven by fixing time:

| Comparison | Median abs (bp) | 99th pct abs (bp) | Interpretation |
|---|---|---|---|
| BoC vs FRED | 2-5 | 14-56 | daily average vs noon; EM wider |
| ECB vs FRED | 7-35 | 51-184 | five-hour gap; BRL widest |

Tolerances (ADR-0005) are set several times above the observed statistics so that the
check fails on a unit or inversion error (hundreds or thousands of bp) or a broken feed,
and passes on fixing-time noise.

### 2.4 Quality checks

`fxrisk quality` rebuilds DuckDB from the cache and runs: cache completeness, CSV schema,
staleness (per-series publication-lag limits; cache age is WARN only), cross-source
reconciliation, master-table completeness, calendar gaps, return outliers (|r| > 6 lagged
EWMA sigma, WARN only, each checked against the sources the master price did not come
from) and a plausibility range on rates. The loader also fails if any cached series
loads a different number of rows than its manifest records. The verdicts are stored in
`quality_checks` for the decision report; failures write `reports/alerts.md` and return
exit code 1.

## 3. Synthetic flows

Configuration: `config/flows.yaml`. Generator: `fx_treasury_risk/flows/generator.py`.
Design rationale: ADR-0008.

### 3.1 What is generated

For each (entity, currency) pair with a configured daily volume, and for every calendar
day, the generator produces positive amounts by flow type:

| Flow type | When | Amount (A = authorized amount, t = take rate, s = same-currency payout share: configured for foreign-currency collections, 1 for the entity's own currency) |
|---|---|---|
| `auth` | day of sale | A = volume x growth x weekly x annual x regime x noise |
| `payable_accrual` | day of sale | A (1-t) s |
| `settlement` | + L business days (L from a per-currency distribution) | A |
| `payout_same` | next payout date (daily or Friday) | settlements (1-t) s, net of claw-backs |
| `payout_converted` | same | settlements (1-t)(1-s), net of claw-backs |
| `refund_paid` | + R calendar days (truncated geometric, mean 12) | A x refund rate |
| `refund_clawback` | same | refund (1-t) s |
| `fee_sweep` | last business day of month | t x (settlements - refunds) |
| `interco_receivable` / `interco_payable` | first business day of each quarter | growth top-up of the parent's loan |

Noise is lognormal AR(1) with mean one. Growth is an 8% annual trend. Regimes multiply
volume over a date range (the 2020 collapse and rebound are configured).

### 3.2 What is stylized and why

* **Volumes, take rate, refund rate, lags, payout schedules, same-currency shares** are
  round numbers chosen for a treasury-sized problem (group ~USD 75m/day). They are not
  estimates of anything.
* **Annual seasonality is the one calibrated input**: twelve monthly factors from the
  NSA/SA ratio of US retail sales (FRED) for the US, euro-area and UK entities and of
  Canadian retail sales (StatCan) for the Canadian entity. Monthly retail data cannot
  identify a weekly pattern, so the weekend-heavy weekly profile is assumed.
* **Weekday calendar** for settlement and payouts; holidays are ignored.
* **Intercompany loans** are spent on payouts at the subsidiary, so they net to zero at
  group level and appear only in gross exposure.
* **No USD exposure at group level**: USD is the reporting currency. USD flows at non-US
  entities are generated for completeness and excluded from group FX exposure.

### 3.3 Tests

`tests/test_flows.py` checks, per pair, that settlements equal authorizations, payouts
equal (1-t) of settlements net of refunds split by the configured share, fees net of
refunded fees are swept, every component returns to a bounded level (no drift with
cumulative volume), the weekly and annual profiles are recovered from the output, the
level matches the configured volume, and the generator is deterministic and
pair-independent.

## 4. Exposure aggregation

All aggregation is SQL: `sql/060_flows.sql` to `sql/090_exposure_group.sql`.

### 4.1 From flows to positions

`flow_type_map` assigns each flow type to a component and a sign. A settlement, for
example, moves two components (`in_flight` -1, `balance` +1), which the join to the
mapping table fans out into two rows. Positions are running sums of signed flows per
(entity, currency, component) over a complete calendar-day grid, so days without flows
carry the previous position.

| Component | Meaning | Sign |
|---|---|---|
| `in_flight` | receivables authorized but not settled | >= 0 |
| `balance` | cash held in the currency | >= 0 |
| `payable` | owed to merchants paid in the currency | <= 0 |
| `intercompany` | parent loan: receivable at US, payable at the subsidiary | +/- |
| `net` | sum of the four | |
| `gross` | sum of absolute values | |

### 4.2 Translation and the waterfall

`exposure_daily_usd` translates at the latest NY fixing on or before the exposure date
(an `ASOF JOIN`; a weekend uses Friday's rate). `exposure_waterfall` shows the same
number three ways: gross, net, and net of active hedges, per (date, entity, currency),
and `exposure_waterfall_by_ccy` sums entities for the group view.

### 4.3 Existing hedges

`hedge_positions` holds the optimizer's monthly positions. The exposure stage recreates
it empty, so its output never depends on a previous run; the policy backtest then writes
the positions and rebuilds `exposure_group_fx`. For months without optimizer rows
`hedges_legacy` supplies a placeholder programme: on the first of each month, sell
forward 50% of last month's average net exposure in each non-USD currency for one month.
`hedges_all` prefers optimizer rows where they exist.

### 4.4 Risk input

`exposure_group_fx` is group net exposure by currency on the FX calendar, in currency
units and USD, with and without hedges. The risk engine reads only this table.

### 4.5 What kind of exposure this is: economic, not accounting

The number hedged is the **consolidated net position per currency**: every entity's
balances in a currency are added, whichever entity holds them, and the sum is valued in
USD. That is the group's economic exposure to the currency, and it is the right target
for protecting the USD value of the group. It is not what an accountant would call the
exposure, because accounting splits the same balances in two:

* **Transaction exposure**: monetary items an entity holds in a currency other than its
  own functional currency (the US parent's EUR receivables and its EUR loan to the
  euro-area subsidiary, the UK entity's EUR balances). These are remeasured through
  earnings every period.
* **Translation exposure**: an entity's position in its *own* functional currency (the
  euro-area entity's EUR payables to merchants and its EUR loan from the parent). These
  create no gain or loss in the entity's books; they move equity, not earnings, when the
  subsidiary is translated into USD on consolidation.

On 2026-10-30 the two parts are USD +286m of transaction exposure and USD -165m of
translation exposure, which net to USD 121m across the ten currencies. In EUR the parent
and the UK entity are long USD 73.5m while the euro-area entity owes USD 61.8m in its
own currency, so the model sees USD 11.7m. A treasury that hedges **reported earnings**
would hedge nearer the 73.5m; one that hedges **economic value**, as here, hedges the
net. Neither is wrong, but they are different programmes with different sizes, and the
model implements only the second. The split by entity is in `exposure_waterfall`;
separating the two in the optimizer and the backtest is backlog B21.

## 5. Risk engine

Code: `fx_treasury_risk/risk/`. Choices: ADR-0009.

* **Returns:** daily log returns of `usd_per_fcy`; returns over a forward-filled cell are
  dropped rather than recorded as zero.
* **P&L:** `sum_c E_c (exp(r_c) - 1)` with `E_c` the USD exposure (positive = long).
  Loss is minus P&L; VaR and ES are positive USD amounts.
* **Covariance:** sample (1,000 days), EWMA (0.94 and 0.97), Ledoit-Wolf identity-target
  shrinkage (1,000 days).
* **VaR/ES:** historical simulation on overlapping h-day returns; normal and Student-t
  (variance-matched, `nu` fitted by MLE) scaled by `sqrt(h)`; Monte Carlo with a t
  copula over EWMA correlations, t marginals and `h` compounded daily steps.
* **Stress:** historical replays (CHF 2015, Brexit 2016, March 2020, USD surge 2022,
  taper tantrum 2013) and hypothetical shocks with Gaussian conditional propagation to
  unnamed currencies under the 1,000-day sample covariance, reported with and without
  propagation and with the largest implied moves listed.
* **Output:** `risk_results` and `stress_results` in DuckDB; `reports/risk_tables.md`.

## 6. Exposure forecasting

Code: `fx_treasury_risk/forecast/`. Choices and evidence: ADR-0011. Output:
`reports/forecast_eval.md` and the three figures it embeds.

* **Target:** group net exposure per currency in currency units (`net_fcy` from
  `exposure_group_fx`), on the NY business-day calendar, 1-63 trading days ahead.
* **Baseline:** seasonal naive, the value on the same weekday four weeks earlier
  (28k calendar days, last trading day on or before); intervals from its own in-window
  error quantiles per horizon.
* **Model:** log exposure regressed on calendar features (weekday, 0-4 trading days to
  month end, first three trading days of the month, month of year, linear trend) with
  AR(1) errors; 750-day training window. Point forecast
  `x_{T+h}' beta + phi^h e_T`; intervals from the empirical quantiles of the model's
  in-sample `h`-step errors, standardised by the target day's day-type volatility and
  conditioned on the origin's day type.
* **Evaluation:** rolling origin, one origin per month (the last trading day, so the
  first horizon is the rebalance day), 140 origins from 2015 to 2026; pinball loss over
  seven quantiles scaled by the mean actual, median MAPE, central-interval coverage at
  50/80/95, skill versus the naive. Figures: calibration (empirical vs nominal coverage
  per horizon, one line per currency), pinball by horizon per currency, a fan chart with
  the realised path.
* **Result:** skill about 0.8 at every horizon; median MAPE 5-7%; coverage 0.86 at
  nominal 0.95, i.e. intervals somewhat too narrow (stated in the report).

## 7. Hedge optimization

Code: `fx_treasury_risk/hedge/`. Instrument mechanics: `docs/hedging-primer.md`.
Formulation and solver: ADR-0012. Output: `reports/hedge_recommendation.md` and
`reports/figures/hedge_frontier.png`.

* **Short rates** (`sql/100_rates_short.sql`, ADR-0015): the central-bank policy rate for
  every currency, daily (BIS `WS_CBPOL`; for the euro area the ECB deposit facility rate,
  with the BIS refinancing-rate series as a fallback when it is more than 120 days
  stale); SGD proxied by USD and flagged.
* **Forwards:** covered interest parity with simple rates and per-market day counts,
  tenor = calendar days to the next rebalance (30 for the as-of table). Forward points
  and the annualized hedge cost rate `(S - F)/S * 365/days` are reported per currency.
* **Optimizer:** minimise expected carry plus bid-ask subject to the 21-day 99% ES of
  the hedged book (variance-matched Student-t on the EWMA(0.94) covariance) staying
  within the budget; ratios in [0, 1]; minimum ticket as a post-step; SLSQP.
* **Frontier:** the budget is swept from zero to the unhedged ES; each point is the
  optimal (residual ES, annualized cost) pair. Unhedged, legacy 50% and full hedge are
  plotted for reference.

## 8. Backtesting

### 8.1 VaR and ES coverage

Code: `fx_treasury_risk/backtest/coverage.py`, `var_backtest.py`. Design: ADR-0010.
Daily one-day forecasts along the actual exposure path for historical simulation,
normal (sample and EWMA covariance) and Student-t (EWMA 0.94, EWMA 0.97, and GARCH(1,1)
volatilities with EWMA correlations, `fx_treasury_risk/risk/garch.py`) models. The model
the optimizer uses is selected on 2012-2014 by the mean FZ0 joint VaR/ES score, with a
Diebold-Mariano test against the runner-up; every model is then tested from 2015-01-02:
Kupiec, Christoffersen (with the count of back-to-back exceptions), conditional
coverage, Basel traffic light, Acerbi-Szekely Z1 and Z2 with simulated p-values. Output:
`var_model_selection`, `var_backtest_results`; `reports/var_backtest.md`.

### 8.2 Hedge-policy backtest

Code: `fx_treasury_risk/backtest/policy.py`. Design: ADR-0013. Output:
`reports/policy_backtest.md` and three figures.

Walk-forward, monthly rebalance from 2015-01-02, one-month forwards priced by CIP at the
origin, hedging the median forecast exposure averaged over the month the forward
covers; realised P&L from the actual
exposure path, forward mark-to-market, carry and spread. Policies: unhedged, legacy 50%
(half of last month's average net exposure, the `hedges_legacy` rule of section 4.3, no
forecast), full hedge, optimizer under a fixed USD 4m ES budget. Metrics: P&L volatility (daily
annualized and monthly), total P&L, carry and spread per year, maximum drawdown, worst
month, months with a loss beyond the budget (a loss frequency) and beyond the policy's own
ex-ante 99% VaR (the model test), share of months in which the budget bound; overall, by
year, and for March/April 2020 and September/October 2022. The optimizer's P&L lead over
each other policy is tested for a zero mean with a Newey-West t-statistic and split into
carry plus spread (known at dealing) and spot (`policy_comparison`).

## 9. Reporting and operations

Code: `fx_treasury_risk/report/decision.py`, `report/plots.py`, `sql/110_report_views.sql`,
`dags/fxrisk_daily.py`, `.github/workflows/refresh.yml`. Design: ADR-0014.

`fxrisk report` assembles `reports/decision_report.md` from the tables the earlier stages
persisted in DuckDB and the figures they drew; it computes nothing and recomputes nothing,
so the report cannot disagree with `reports/*.md`. Two figures are drawn here from
exposure views: the waterfall on the last FX date (gross, net, net of hedges by currency)
and the monthly-average history of the group book (averages rather than month-end
snapshots, because exposure dips on the last day of every month when fees are swept).
Sections, in order: the question and its answer; data and quality; exposure waterfall;
forecast calibration; VaR/ES with the coverage verdicts; stress; the cost-risk frontier
and the chosen point; out-of-sample policy performance with the 2020 and 2022 months
broken out; what the model does not know; how to reproduce.

Operations: the Airflow DAG is one task per CLI stage in the CLI's order (asserted by
`tests/test_dag.py`), illustrative only. The weekly GitHub Actions workflow refreshes
every series, reruns the pipeline and opens a pull request with the new cache and
reports; a person merges it after reading the alerts. CI itself never touches the
network.
