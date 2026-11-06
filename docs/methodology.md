# Methodology

This document fixes the conventions every module uses. When code and this document
disagree, the code is wrong. Sections marked *(milestone N)* are filled in as that
milestone lands.

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

* All rates are **annualized, in percent**, as published. Day-count conventions differ by
  market (ACT/360 for USD money markets, ACT/365 for GBP and CAD T-bills); the hedging
  primer states which one the forward-pricing code assumes and the error that assumption
  introduces at the horizons used here (well below a basis point of forward points).
* `DTB3` is a *discount-basis* T-bill rate; the primer explains the conversion to a simple
  yield.

### 1.4 Calendar and horizons

* The master calendar is the set of **New York business days** on which the Federal
  Reserve published H.10 rates. Sources that trade on US holidays are dropped on those
  days so that every daily return spans one NY trading day.
* Horizons are counted in trading days: 1, 10 and 21 (one month). A year has 252.

## 2. Data layer *(milestone 1)*

### 2.1 Sources and precedence

| Role | Source | Series | Fixing time |
|---|---|---|---|
| Primary USD crosses | FRED H.10 | `DEXUSEU`, `DEXUSUK`, `DEXCAUS`, `DEXJPUS`, `DEXUSAL`, `DEXSZUS`, `DEXMXUS`, `DEXBZUS`, `DEXINUS`, `DEXSIUS` | noon, New York |
| Cross-check and fallback 1 | Bank of Canada Valet | `FXUSDCAD` + nine `FX*CAD` (2017-), legacy noon series `IEXE*` / `EUROCAE01` (2010-2017) | daily average (current) / noon (legacy), Toronto |
| Cross-check and fallback 2 | ECB Data Portal | `EXR.D.<CCY>.EUR.SP00.A` for ten currencies | 14:15 CET |
| Short rates | FRED (`DTB3`, `SOFR`, OECD `IR3TIB01*`, `IRSTCI01*`), BoC (`V39079`, `TB.CDN.90D.MID`), BIS `WS_CBPOL` | see ADR-0006 | |
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
EWMA sigma, WARN only, for human review) and a plausibility range on rates. Failures write
`reports/alerts.md` and return exit code 1.

## 3. Synthetic flows *(milestone 2)*

Configuration: `config/flows.yaml`. Generator: `fx_treasury_risk/flows/generator.py`.
Design rationale: ADR-0008.

### 3.1 What is generated

For each (entity, currency) pair with a configured daily volume, and for every calendar
day, the generator produces positive amounts by flow type:

| Flow type | When | Amount (A = authorized amount, t = take rate, s = same-currency payout share) |
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

## 4. Exposure aggregation *(milestone 2)*

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

`hedge_positions` is the table the optimizer (milestone 3) writes. Until then
`hedges_legacy` supplies a placeholder programme: on the first of each month, sell
forward 50% of last month's average net exposure in each non-USD currency for one month.
`hedges_all` prefers optimizer rows where they exist.

### 4.4 Risk input

`exposure_group_fx` is group net exposure by currency on the FX calendar, in currency
units and USD, with and without hedges. The risk engine reads only this table.

## 5. Risk engine *(milestone 2)*

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
  unnamed currencies, reported with and without propagation.
* **Output:** `risk_results` and `stress_results` in DuckDB; `reports/risk_tables.md`.

## 6. Exposure forecasting *(milestone 3)*

Code: `fx_treasury_risk/forecast/`. Choices and evidence: ADR-0011. Output:
`reports/forecast_eval.md` and the three figures it embeds.

* **Target:** group net exposure per currency in currency units (`net_fcy` from
  `exposure_group_fx`), on the NY business-day calendar, 1-63 trading days ahead.
* **Baseline:** seasonal naive at lag 21 trading days; intervals from its own in-window
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

## 7. Hedge optimization *(milestone 3)*

Code: `fx_treasury_risk/hedge/`. Instrument mechanics: `docs/hedging-primer.md`.
Formulation and solver: ADR-0012. Output: `reports/hedge_recommendation.md` and
`reports/figures/hedge_frontier.png`.

* **Short rates** (`sql/100_rates_short.sql`): per currency a primary 3-month market
  rate where available, falling back to the BIS daily policy rate when the primary is
  more than 120 days stale; monthly series carried to daily with an ASOF JOIN; SGD
  proxied by USD and flagged. US T-bills converted from discount to simple yield.
* **Forwards:** covered interest parity with simple rates and per-market day counts,
  tenor = calendar days to the next rebalance (30 for the as-of table). Forward points
  and the annualized hedge cost rate `(S - F)/S * 365/days` are reported per currency.
* **Optimizer:** minimise expected carry plus bid-ask subject to the 21-day 99% ES of
  the hedged book (variance-matched Student-t on the EWMA(0.94) covariance) staying
  within the budget; ratios in [0, 1]; minimum ticket as a post-step; SLSQP.
* **Frontier:** the budget is swept from zero to the unhedged ES; each point is the
  optimal (residual ES, annualized cost) pair. Unhedged, legacy 50% and full hedge are
  plotted for reference.

## 8. Backtesting *(milestones 2-3)*

### 8.1 VaR and ES coverage *(milestone 2)*

Code: `fx_treasury_risk/backtest/coverage.py`, `var_backtest.py`. Design: ADR-0010.
Daily one-day forecasts from 2015-01-02 along the actual exposure path for historical
simulation, normal (sample and EWMA covariance) and Student-t (EWMA) models. Tests:
Kupiec, Christoffersen, conditional coverage, Basel traffic light, Acerbi-Szekely Z1 and
Z2 with simulated p-values. Output: `var_backtest_results`; `reports/var_backtest.md`.

### 8.2 Hedge-policy backtest *(milestone 3)*

Code: `fx_treasury_risk/backtest/policy.py`. Design: ADR-0013. Output:
`reports/policy_backtest.md` and three figures.

Walk-forward, monthly rebalance from 2015-01-02, one-month forwards priced by CIP at the
origin, hedging the 21-day-ahead forecast exposure; realised P&L from the actual
exposure path, forward mark-to-market, carry and spread. Policies: unhedged, legacy 50%,
full hedge, optimizer under a fixed USD 4m ES budget. Metrics: P&L volatility (daily
annualized and monthly), total P&L, carry and spread per year, maximum drawdown, worst
month, months with a loss beyond the budget, share of months in which the budget bound;
overall, by year, and for March/April 2020 and September/October 2022.
