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

## 4. Exposure aggregation *(milestone 2)*

## 5. Risk engine *(milestone 2)*

## 6. Exposure forecasting *(milestone 3)*

## 7. Hedge optimization *(milestone 3)*

## 8. Backtesting *(milestones 2-3)*
