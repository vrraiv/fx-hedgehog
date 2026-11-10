# ADR-0006: Short-rate sources per currency, including the SGD proxy

**Status:** accepted, 2026-11-05

## Context

Covered interest parity pricing (milestone 3) needs a short rate per currency at a one- to
three-month tenor. The brief names FRED's OECD series and accepts monthly data with
forward-fill. Probing on 2026-11-05 found:

* FRED carries OECD 3-month interbank rates (`IR3TIB01*`) for EUR, GBP, JPY, AUD, CHF, CAD
  and MXN, monthly. The EUR and GBP series last printed 2026-01 (ten months stale); the
  others 2026-08/09.
* FRED has no 3-month series for BRL, INR or SGD. It carries OECD *immediate* rates
  (`IRSTCI01*`, overnight/call) for BRL and INR.
* BIS `WS_CBPOL` publishes daily policy rates for all ten economies except Singapore,
  which has no policy rate (the MAS targets the exchange rate).
* No keyless public API for an SGD money-market rate could be verified (MAS endpoints
  returned 404 or require registration).

## Decision

| Currency | Primary (tenor) | Fallback | Frequency |
|---|---|---|---|
| USD | FRED `DTB3` (3m, discount basis, converted over the bill's 91 days) | `SOFR` | daily |
| CAD | BoC `TB.CDN.90D.MID` (3m) | BIS policy rate | daily |
| EUR, GBP, JPY, AUD, CHF, MXN | FRED OECD `IR3TIB01*` (3m) | BIS policy rate | monthly, forward-filled |
| BRL, INR | FRED OECD `IRSTCI01*` (overnight) | BIS policy rate | monthly, forward-filled |
| SGD | **USD rate as proxy**, flagged `is_proxy = true` | none | daily |

Every non-USD currency falls back to the same family of series (BIS `WS_CBPOL`), so the
fallback rule is uniform. The Bank of Canada's own policy-rate series was fetched in an
earlier version but never used and has been dropped from the registry.

Rules, implemented in the `rates_short` table (`sql/100_rates_short.sql`):

1. Monthly rates are carried forward to daily with an `ASOF JOIN` on the master calendar.
2. If the primary series' last observation is older than 120 days at the valuation date,
   the daily BIS policy rate is used instead and the row is flagged `is_fallback = true`
   (with `source = 'bis'` and the BIS series id).
3. Every row carries `source`, `series_id`, `tenor_months`, `days_stale`, `is_proxy` and
   `is_fallback`, so the report can state exactly which rate priced each forward.

## Consequences

* SGD carry is zero by construction in v1 and the report says so. Empirically SGD short
  rates track USD rates with a negative spread of roughly 0.5-1.5 pp over 2015-2026, so the
  proxy understates the (small) carry *earned* by hedging SGD; the sign of the error is
  stated in the report's limitations section. Backlog B1 replaces the proxy.
* Using an overnight rate for BRL/INR at a one-month tenor ignores the term premium;
  given Selic and repo levels of 6-15%, the error is a few tens of bp of annualized carry.
* A monthly average rate forward-filled is stale by up to a month plus publication lag;
  the fallback rule bounds the lag at 120 days.
