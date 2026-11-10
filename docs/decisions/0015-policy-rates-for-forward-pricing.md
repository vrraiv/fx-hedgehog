# ADR-0015: Price forwards off central-bank policy rates

**Status:** accepted, 2026-11-09. Supersedes the source table in ADR-0006.

## Context

Carry, the expected cost of a hedge, is set by the difference between the USD rate and
the foreign rate over the tenor of the forward (hedging primer, section 3). ADR-0006
assembled those rates from whatever public series existed per currency:

| Currency | Rate used |
|---|---|
| USD | 3-month Treasury bill (secured, government credit, discount basis) |
| CAD | 3-month Canadian T-bill |
| EUR, GBP, JPY, AUD, CHF, MXN | OECD 3-month interbank, monthly average; EUR and GBP stale by up to ten months and replaced by policy rates |
| BRL, INR | OECD overnight rate, monthly average |

Three problems followed.

* **The differential compared unlike instruments.** T-bills normally trade below
  unsecured interbank rates, so subtracting a USD bill rate from a foreign interbank rate
  biased foreign currencies towards looking costly to hedge. For the currencies where the
  true differential is small this decided the sign: the GBP-USD differential was under
  25 bp on 44% of days since 2015, and the optimizer's GBP ratio jumped by more than 0.5
  in seven months.
* **Monthly averages are stale and arrive late.** A month's average is not known until
  the month is over and is published weeks later; the backtest had to lag them, and the
  EUR and GBP series had stopped updating altogether.
* **Mixed tenors.** Three-month, overnight and policy rates were combined in one table.

The instrument that matches a one-month forward is a one- or three-month OIS rate. No
free, keyless source publishes OIS rates for ten currencies.

## Decision

Every currency is priced off its central bank's **policy rate**, from one family of
daily series:

| Currency | Primary | Fallback |
|---|---|---|
| USD, GBP, CAD, JPY, AUD, CHF, MXN, BRL, INR | BIS `WS_CBPOL` daily policy rate | none |
| EUR | ECB deposit facility rate (ECB Data Portal, `FM.D.U2.EUR.4F.KR.DFR.LEV`) | BIS euro-area series (main refinancing rate) |
| SGD | USD rate, flagged `is_proxy` (Singapore has no policy rate; the MAS targets the exchange rate) | none |

* **Why the deposit rate for the euro area.** The BIS series for the euro area is the
  main refinancing rate. Since excess liquidity arrived in 2014, euro money-market rates
  (EONIA, then €STR) have traded at or just below the deposit facility rate, 40-50 bp
  under the refinancing rate through 2015-2022 (in March 2016, 0.00% against -0.40%).
  Using the refinancing rate would have overstated the cost of hedging EUR by that much
  for most of the backtest.
* **Why policy rates are defensible.** Overnight index swaps, the market rate for these
  tenors, are swaps on the compounded overnight rate, which central banks steer to their
  policy rate. A policy rate is therefore the rate a one-month OIS would equal if no
  change were expected within the month. It is daily, known on the day (decisions are
  announced before they take effect, so there is no look-ahead), never stale, and the
  same instrument in every currency.
* The fallback machinery of ADR-0006 is kept: a primary more than 120 days stale gives
  way to the fallback. Only the euro area has one.
* The FRED T-bill, SOFR and OECD series and the Bank of Canada T-bill are no longer
  fetched, and the T-bill discount-to-yield conversion is removed with them.

## Consequences

* Carry is the policy-rate differential. It ignores rate changes expected within the
  month: around a hiking or cutting cycle a one-month OIS moves ahead of the policy rate
  by up to the size of the expected move, so carry is understated for a currency whose
  central bank is expected to hike and overstated for one expected to cut. At a
  one-month tenor this is a few basis points of carry in most months and up to about
  25 bp a year at turning points.
* Day counts are unchanged (ACT/360 for USD, EUR, JPY, CHF, MXN; ACT/365 for GBP, CAD,
  AUD, BRL, INR), and SGD carry is still zero by construction (backlog B1).
* A free source of OIS rates would replace this table without changing anything
  downstream: `rates_short` is the only input to forward pricing (backlog B2).
