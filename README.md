# fx-hedgehog

An FX treasury risk system for a stylized multi-entity, multi-currency payments business.
Synthetic merchant flows in ten currencies create exposure across four legal entities;
the system measures that exposure (VaR, Expected Shortfall, stress), forecasts it with
calibrated uncertainty, and chooses forward-hedge ratios that minimise carry cost for a
fixed risk budget, then backtests the policy out of sample. All market data is public and
cached in the repository; no real company's figures are used or implied.

> **Status: milestone 2 of 4.** Data layer, synthetic flows, SQL exposure aggregation,
> the risk engine (VaR/ES by six method families, stress) and the VaR/ES coverage
> backtests are complete and CI-tested. Exposure forecasting, forward pricing, the hedge
> optimizer and the policy backtest (milestone 3) and the decision report (milestone 4)
> follow.

## The question this repository answers

*For a fixed Expected Shortfall budget at the 21-day horizon, what hedge ratios by
currency minimise expected hedging cost, and how would that policy have performed out of
sample from 2015 to the present, including March 2020 and 2022?*

**Headline answer:** to be filled at milestone 3, with the cost-vs-residual-risk frontier
in `reports/figures/` and the full argument in `reports/decision_report.md`.

**What the backtests already say (milestone 2, `reports/var_backtest.md`):** on the
synthetic book, daily from 2015, plain historical simulation and the sample-covariance
normal model fail the Christoffersen independence test (exceptions cluster), the EWMA
normal model fixes clustering but fails at 99% (52 exceptions against 30 expected, Basel
yellow), and the Student-t EWMA(0.94) model passes every test at 99% (34 exceptions,
green, Acerbi-Szekely p = 0.17). That is the risk model the hedge policy will be built on.

## Architecture

```
                 public APIs (BoC, FRED, ECB, BIS, StatCan)
                                 |
                          fxrisk fetch  ---->  data/cache/<source>/<id>.csv + manifest.json
                                 |                       (committed; retrieval dates recorded)
                          fxrisk quality ---->  DuckDB rebuilt from cache
                                 |              sql/010..050: raw -> catalogue -> usd_per_fcy
                                 |                            -> reconciliation -> master
                                 |              reports/quality_report.md, reports/alerts.md
                          fxrisk flows    ---->  data/flows.parquet (deterministic, config/flows.yaml)
                          fxrisk exposure ---->  sql/060..090: flows -> components -> waterfall
                          fxrisk risk     ---->  risk_results, stress_results; reports/risk_tables.md
                          fxrisk backtest ---->  var_backtest_results; reports/var_backtest.md
                                 v
                 forecast -> hedge -> policy backtest -> report        (milestones 3-4)
```

| Layer | Where | What |
|---|---|---|
| Loaders and cache | `fx_treasury_risk/data/` | one thin loader per source, CSV cache with provenance manifest, offline guard, quality checks |
| Flows | `fx_treasury_risk/flows/`, `config/flows.yaml` | deterministic synthetic merchant flows; annual seasonality calibrated to public retail sales |
| SQL | `sql/*.sql` | every transformation, loaded by file name, commented for a reader learning SQL |
| Exposure | `sql/060-090`, `fx_treasury_risk/exposure/` | running-sum positions by component, USD translation, gross / net / net-of-hedges waterfall |
| Risk | `fx_treasury_risk/risk/` | returns, sample / EWMA / Ledoit-Wolf covariance, historical / normal / Student-t / t-copula Monte Carlo VaR and ES, stress |
| Backtest | `fx_treasury_risk/backtest/` | Kupiec, Christoffersen, conditional coverage, traffic light, Acerbi-Szekely Z1/Z2 |
| CLI | `fx_treasury_risk/cli.py` | `fxrisk fetch \| quality \| flows \| exposure \| risk \| backtest \| all` |
| Docs | `docs/` | `methodology.md` (conventions and methods), `hedging-primer.md`, `backlog.md`, `decisions/` (ADRs 0001-0010) |

## How to run

```bash
uv sync --all-groups            # Python 3.12 environment from uv.lock
uv run fxrisk all               # fetch (no-op from cache) -> quality -> flows -> exposure -> risk -> backtest
uv run pytest                   # 63 tests, no network, about a minute
```

Individual stages run in the same order as `all`. Timings on a laptop: quality 3 s,
flows 2 s, exposure 5 s, risk 40 s (Monte Carlo), backtest 90 s (ES simulations).

* A `FRED_API_KEY` in the environment or in a git-ignored `.env` switches the FRED
  loader to the official API; without it the public CSV download is used. Neither is
  needed to run from cache.
* `uv run fxrisk fetch --refresh` re-downloads everything; `FXRISK_OFFLINE=1` forbids
  network access (CI sets it).
* `fxrisk quality` exits 1 if any check fails and writes the reasons to `reports/alerts.md`.
* The DuckDB file `data/fxrisk.duckdb` is rebuilt from the cache and can be opened with
  any DuckDB client to inspect every intermediate table and view.

## Data sources

All series were retrieved on **2026-11-06 (UTC)**; exact timestamps, URLs and file hashes
are in `data/cache/manifest.json`. Coverage is 2010-01-04 onward.

| Source | Series | Used for |
|---|---|---|
| [FRED](https://fred.stlouisfed.org) H.10 | `DEXUSEU DEXUSUK DEXCAUS DEXJPUS DEXUSAL DEXSZUS DEXMXUS DEXBZUS DEXINUS DEXSIUS` | primary USD rates (noon NY) |
| FRED | `DTB3`, `SOFR`; OECD `IR3TIB01{EZ,GB,JP,AU,CH,CA,MX}M156N`, `IRSTCI01{BR,IN}M156N` | short rates for forward pricing (monthly OECD series forward-filled; see ADR-0006) |
| FRED | `RSXFSN`, `RSXFS` | US retail sales, seasonality calibration of synthetic flows |
| [Bank of Canada Valet](https://www.bankofcanada.ca/valet/docs) | `FXUSDCAD` and nine `FX*CAD` (2017-), legacy noon `IEXE*`/`EUROCAE01` (2010-2017); `V39079`, `TB.CDN.90D.MID` | CAD crosses for reconciliation and fallback; CAD rates |
| [ECB Data Portal](https://data.ecb.europa.eu) | `EXR.D.<CCY>.EUR.SP00.A`, ten currencies | second cross-check and fallback |
| [BIS](https://data.bis.org) | `WS_EER` daily nominal broad EER (11 economies); `WS_CBPOL` daily policy rates (10) | stress sanity check; fallback short rates |
| [Statistics Canada](https://www150.statcan.gc.ca) | table 20-10-0056-01, vectors `v1446859481` (NSA), `v1446859483` (SA) | Canadian retail sales seasonality |

### Reconciliation

USD rates derived from the Bank of Canada's CAD crosses agree with FRED to a median of
2-5 bp (99th percentile 14-56 bp) over 2010-2026; the differences are fixing-time
effects (daily average vs noon). ECB-derived rates differ by 7-35 bp at the median (14:15
CET vs noon NY). Tolerances are set several times above these levels so the check catches
unit and inversion errors, not noise (ADR-0005). Every run prints the full table in
`reports/quality_report.md`.

### Why these ten currencies

They span the liquid majors and three emerging-market currencies a payments business
plausibly settles in. Shares of global OTC FX turnover (each trade counts twice, so shares
sum to 200%), from the BIS Triennial Central Bank Survey:

| EUR | JPY | GBP | CHF | AUD | CAD | SGD | INR | MXN | BRL |
|---|---|---|---|---|---|---|---|---|---|
| 28.9 | 16.8 | 10.2 | 6.4 | ~6 | ~6 | ~2 | 1.6* | 1.5* | 0.9* |

2025 survey (April 2025 turnover) except `*` = 2022 survey, Table 3. Used only to
motivate the list; nothing is built on them.

## Conventions (the two that matter)

* **Rates are USD per one unit of foreign currency** (`usd_per_fcy`), for every currency.
  A rising number means the foreign currency strengthened.
* **Positive exposure = long the foreign currency.** The business gains when the currency
  strengthens.

Both are enforced by tests and explained in `docs/methodology.md`.

## The synthetic business in one paragraph

Four entities (US, Canada, euro area, UK) collect card payments in the ten currencies
plus USD, about USD 75m a day in total. Each sale creates a receivable that settles after
one to five business days, merchants are paid daily (US, Canada) or weekly (euro area,
UK), partly in the collected currency and partly after conversion, refunds come back
over the following weeks, retained fees are swept monthly, and the US parent funds the
subsidiaries with quarterly working-capital loans. The net open position in each currency
(receivables plus cash, minus merchant payables, plus intercompany) is the exposure:
USD 7-95m per currency on average, gross up to USD 1bn in EUR. A placeholder legacy
programme hedges half of last month's average net exposure; milestone 3 replaces it with
the optimizer. Details in `docs/methodology.md` sections 3-4 and ADR-0008.

## Limitations and non-goals

* **Synthetic flows.** Volumes, seasonality and settlement lags are stylised and
  calibrated only to public retail-sales seasonality. Nothing here describes a real firm.
* **SGD short rate is a USD proxy** (no verified public API; ADR-0006, backlog B1), so SGD
  carry is zero by construction.
* **Monthly OECD rates** for most currencies, forward-filled; EUR and GBP series on FRED
  lag by up to ten months and fall back to BIS policy rates (ADR-0006).
* **Forwards only; no options, no cross-currency basis, no NDF basis** (hedging primer,
  section 5).
* **Fixing-time mismatch** between sources is tolerated, not modelled.
* **Weekday calendar**, no holidays, for settlement and payouts (backlog B9).
* **Coverage tests at one day only.** Ten- and 21-day numbers are reported with a
  caveat; overlapping windows break the tests' independence assumption (ADR-0010).
* **Not a product:** no scheduler is executed in CI, no database beyond a local DuckDB
  file, no access control.

## Repository map

```
fx_treasury_risk/   package (data/, flows/, exposure/, risk/, backtest/, hedge/, forecast/, report/, cli.py)
config/             flows.yaml - the stylized business
sql/                all SQL, numbered in execution order
data/cache/         committed source data + manifest.json
tests/              pytest suite; tests/fixtures holds trimmed real API responses
docs/               methodology, hedging primer, backlog, decisions/ (ADRs)
reports/            generated outputs (quality, alerts, risk tables, backtest verdicts; later figures and the decision report)
.github/workflows/  ci.yml (lint, types, tests, every stage from cache)
```

## Licence

MIT. Data remain subject to their publishers' terms (Bank of Canada, Federal Reserve Bank
of St. Louis, ECB, BIS, Statistics Canada).
