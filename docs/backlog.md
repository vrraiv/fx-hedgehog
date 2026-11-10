# Backlog

Features considered and deliberately not built in v1. Each entry says what, why it was
deferred, and what it would take.

| # | Item | Why deferred | Effort |
|---|---|---|---|
| B1 | **SGD short rate from MAS.** The MAS eservices API (`eservices.mas.gov.sg/api/action/datastore_search`) returned 404 on 2026-11-05 and the newer `apimg-gw` endpoint requires registration. v1 proxies the SGD rate with the USD rate and flags it (ADR-0006). | No verified keyless public endpoint. | 0.5 day once an endpoint is confirmed |
| B2 | **Daily 3-month rates for EUR and GBP** (Euribor from the ECB portal, SONIA/term rates from the BoE). The OECD monthly series on FRED lag by up to ten months. | Two more loaders for a modest improvement in carry accuracy at the one-month horizon. | 1 day |
| B3 | **Cross-currency basis** in forward pricing. | No public daily source for ten currencies. | depends on data |
| B4 | **FX options** as a second instrument class. | Needs an implied-vol surface and a non-linear ES; see hedging primer section 5. | 3-5 days |
| B5 | **Intraday/real-time rates.** | Out of scope for a daily treasury process. | n/a |
| B6 | **Parquet cache** instead of CSV if the cache grows beyond ~50 MB. | CSV is diff-friendly and 4.5 MB today. | 0.5 day |
| B7 | **Airflow DAG executed in CI.** `dags/fxrisk_daily.py` is illustrative; `tests/test_dag.py` only checks its stage order against the CLI (ADR-0014). | Airflow in CI is slow and brittle; the CLI stages are tested directly. | 1 day |
| B8 | **BIS Triennial 2025 Table 4 shares** for INR, MXN, BRL (README cites 2022 values for those three). | The 2025 annex table was not retrievable programmatically on 2026-11-05. | 0.1 day |
| B9 | **Holiday calendars** for settlement and payouts (currently weekdays only). | Small effect on exposure timing; would need per-country calendars. | 0.5 day with `holidays` |
| B10 | **Entity-level functional-currency view** of exposure (e.g. the Canadian entity's USD balances as CAD-functional exposure). | The group USD view is what the hedge policy acts on; the entity view is a reporting lens. | 1 day, mostly SQL |
| B11 | **Multi-day coverage tests** with non-overlapping blocks or Monte-Carlo-adjusted critical values. | Too few blocks for power at 99% (ADR-0010). | 1 day |
| B12 | **GARCH / realised-volatility models** alongside EWMA. | EWMA(0.94) with t tails already passes the 99% tests; GARCH adds parameters without a clear gain for a treasury process. | 1-2 days |
| B13 | **Filtered historical simulation** (Barone-Adesi et al.) to fix the clustering failures of plain historical simulation. | Would add a fifth method; the t-EWMA model already addresses clustering. | 0.5 day |
| B14 | **Monte Carlo in the daily backtest.** | Equivalent to the t-EWMA model at a one-day horizon for a linear book (ADR-0010). | 0.5 day |
| B15 | **SARIMA / ETS (statsmodels) and a Bayesian structural model** as alternative exposure forecasters. | The calendar regression with AR(1) errors reaches skill 0.8 vs naive in sixty lines of numpy; a heavier model needs to beat that to earn the dependency. | 1-2 days |
| B16 | **Conformal calibration of forecast intervals** from past out-of-sample errors. | Intervals are 10-15% too narrow (ADR-0011); a rolling empirical adjustment would fix the level without changing the model. | 0.5 day |
| B17 | **Intra-month hedge adjustment** when exposure drifts beyond a band. | Monthly rolls are the common corporate practice; a band rule needs transaction-cost calibration. | 1 day |
| B18 | **Cross-currency basis and NDF basis** in the policy backtest's realized cost. | No public daily basis data (see B3). | depends on data |
| B19 | **Hedge the average forecast exposure over the holding period** rather than the point forecast at the 21-day target date. Exposure in the synthetic business dips on the last day of every month, so a forward sized on the month-end-dated forecast over-hedges the last day and under-hedges the middle of the month (visible in the waterfall's negative net-of-hedges on month-ends). The forecast stage already produces every horizon 1-21 at each origin; the change is to average the medians. | Changes published results; needs a re-run of the policy backtest and a re-read of ADR-0013. | 0.5 day |
| B20 | **Walkthrough notebook** (`notebooks/walkthrough.ipynb`) that opens `data/fxrisk.duckdb` and steps through the tables behind the report. | Notebooks are kept out of the pipeline so that every number is produced by tested code; the DuckDB file and the report serve the same purpose for now. | 0.5 day |
