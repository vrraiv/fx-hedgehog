# ADR-0003: USD per unit of FCY; positive exposure = long FCY

**Status:** accepted, 2026-11-05

## Context

FX markets quote pairs inconsistently (EURUSD is dollars per euro, USDJPY is yen per
dollar). Risk systems that keep market conventions internally need per-currency sign
logic in every formula.

## Decision

* Internal rate is `usd_per_fcy`, dollars per one unit of foreign currency, for every
  currency including JPY (0.0067) and INR (0.011). Conversion happens once in
  `sql/030_fx_usd_per_fcy.sql`, driven by the `quote` field of the registry.
* Exposure sign: positive = long FCY (the business holds or will receive it). USD P&L over
  a horizon is `exposure_fcy * (S_T - S_0)`.
* Tests enforce both: `test_registry.py` requires a quote convention on every FX series;
  `test_sql_fx.py` checks the inversion against hand-built truth; the exposure module's
  tests (milestone 2) will assert that a merchant receipt in EUR produces positive EUR
  exposure.

## Consequences

* Log returns of `usd_per_fcy` are the return on holding the currency; covariance matrices
  need no sign adjustment.
* Anyone reading a JPY rate of 0.0067 must remember it is dollars per yen. Report tables
  show market-convention rates alongside for readability.
