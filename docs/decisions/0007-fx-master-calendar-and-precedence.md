# ADR-0007: Master FX calendar and source precedence

**Status:** accepted, 2026-11-05

## Context

Three sources with three calendars must become one daily matrix. BoC publishes on
Canadian business days, the ECB on TARGET days, FRED on US business days. Mixing calendars
creates spurious zero returns (forward-fill) or returns spanning two days.

## Decision

* **Calendar:** NY business days as defined by the presence of any FRED H.10 print that
  day (4,210 days over 2010-01-04 to 2026-10-30). Days when other markets trade but New
  York is closed are dropped entirely.
* **Precedence per cell:** FRED, then BoC-derived, then ECB-derived. Recorded in
  `source_used`. Outcome on the current cache: 42,099 FRED cells, 1 BoC cell (INR on a day
  FRED did not print), 0 NULL.
* **Vintage stitching (BoC):** legacy noon series to 2017-04-28 and daily-average series
  from 2017-01-03; on the overlap the current series wins. Each cross is divided only by
  the USD/CAD series of its own vintage.
* **Gaps:** kept as NULL in `fx_usd_master`; `fx_usd_master_filled` forward-fills with an
  `is_filled` flag so the risk engine can drop returns computed over a filled value.

## Consequences

* All ten currencies share one calendar; covariance estimation needs no alignment step.
* A cell filled from BoC or ECB has a different fixing time than its neighbours; given one
  such cell in sixteen years this is noted, not modelled.
