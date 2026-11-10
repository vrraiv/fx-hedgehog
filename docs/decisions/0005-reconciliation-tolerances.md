# ADR-0005: Reconciliation tolerances calibrated on observed fixing-time differences

**Status:** accepted, 2026-11-05

## Context

USD crosses derived from Bank of Canada CAD quotes (and ECB EUR quotes) must reconcile
with FRED USD rates within a stated tolerance, failing loudly otherwise: a unit or
inversion error in any source would otherwise pass silently into every risk number. The three sources fix
at different times (FRED noon NY; BoC daily average, or noon for the legacy series; ECB
14:15 CET), so exact agreement is impossible and a tolerance has to be chosen.

## Evidence (2010-01-04 to 2026-10-30, log differences vs FRED, basis points)

| Currency | BoC median | BoC p99 | BoC mean | ECB median | ECB p99 | ECB mean |
|---|---|---|---|---|---|---|
| EUR | 1.6 | 23.5 | -0.3 | 16.2 | 103.8 | -1.1 |
| GBP | 1.9 | 30.5 | -1.0 | 16.5 | 97.1 | -1.4 |
| CAD | 2.2 | 24.8 | -0.8 | 17.1 | 98.6 | -0.5 |
| JPY | 3.3 | 28.3 | -0.6 | 15.3 | 105.0 | -1.2 |
| AUD | 2.3 | 31.6 | -0.8 | 19.4 | 115.1 | -0.6 |
| CHF | 2.5 | 24.6 | -0.9 | 17.5 | 109.8 | -2.4 |
| MXN | 3.2 | 46.7 | -1.3 | 25.9 | 127.4 | -1.0 |
| BRL | 4.8 | 55.7 | -1.6 | 35.3 | 184.0 | -0.4 |
| INR | 2.7 | 38.6 | -1.5 | 6.6 | 57.3 | -4.7 |
| SGD | 2.0 | 13.8 | -1.3 | 8.6 | 50.9 | -1.8 |

The BoC legacy noon series (2010-2017) agree with FRED to about 1-2 bp at the median; the
current daily-average series to 5-11 bp. Combined medians above are dominated by the
longer legacy window. The ECB's five-hour gap shows as a 16 bp median for majors.

## Decision

Thresholds in `fx_treasury_risk/data/quality.py`:

| Source vs FRED | median abs | p99 abs | abs mean |
|---|---|---|---|
| BoC | 25 bp | 150 bp | 10 bp |
| ECB | 60 bp | 300 bp | 15 bp |

Any breach is a FAIL. The thresholds are about 2.5-5x the worst observed statistic, so the
check is insensitive to fixing-time noise and will trip on: a quote inverted (thousands of
bp), a unit error such as per-100 quotes (~46,000 bp), a stale or frozen feed (mean drifts
and p99 explodes), or a currency mis-mapped in the registry. `tests/test_quality.py`
injects a per-100 error and asserts the FAIL.

## Consequences

* Thresholds are data-derived and documented; they should be re-examined if a source
  changes its fixing methodology.
* The reconciliation summary table is included in `reports/quality_report.md` on every run.
