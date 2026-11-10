# ADR-0008: Synthetic flow model and where exposure comes from

**Status:** accepted, 2026-11-06

## Context

No real company data may be used. The flows must nevertheless produce FX exposure with
the structure a payments treasury actually faces: receivables in flight, multi-currency
cash balances that build between payouts, merchant payables, retained fees, and
intercompany funding. The generator must be deterministic, configurable in YAML, and
testable against the configuration.

## Decision

* **One lifecycle per authorized amount** (`fx_treasury_risk/flows/generator.py`
  docstring): authorization creates a receivable; settlement after a business-day lag
  turns it into cash; merchants are paid on a schedule, partly in the collected currency
  and partly after conversion to the entity's functional currency; refunds are paid from
  the balance and clawed back from merchants through smaller next payouts; fees net of
  refunded fees are swept monthly.
* **Economics live in SQL, not in the generator.** The generator emits positive amounts
  by flow type; `sql/060_flows.sql` maps each type to the exposure component it moves
  (`in_flight`, `balance`, `payable`, `intercompany`) and a sign. Exposure is then a
  running sum per component (`sql/070_exposure_daily.sql`). A new flow type without a
  mapping is rejected at build time.
* **Conservation is a test**, not an assumption: `tests/test_flows.py` checks that
  every component returns to a bounded level after an authorization completes its life,
  and `tests/test_sql_exposure.py` walks one EUR 1,000 sale through the SQL by hand.
* **What is calibrated:** only the annual seasonal factors, from the NSA/SA ratio of
  public retail sales (FRED `RSXFSN`/`RSXFS` for the US profile, StatCan 20-10-0056-01
  for Canada). Weekly seasonality, volumes, take rate, refund rate, lag distributions,
  payout schedules and the same-currency payout shares are stylized round numbers.
* **Intercompany loans** net to zero at group level by construction (the subsidiary
  spends the proceeds on payouts), so they appear in gross but not net exposure. This is
  deliberate: it is what the gross-to-net step of the waterfall is meant to show.
* **Determinism:** each (entity, currency) pair has its own seeded random stream derived
  from the global seed and the pair name, so editing one pair's volume does not change
  another pair's history.
* **Regimes:** multiplicative volume shocks by date range; the 2020 collapse and rebound
  are configured so the exposure forecast (ADR-0011) faces a structural break.

## Consequences

* Exposure magnitudes are a consequence of lags and payout schedules, not inputs. On the
  current configuration group net exposure runs at USD 7-95m per currency, gross up to
  about USD 1bn for EUR.
* Weekend authorizations settle on the next business days; holidays are ignored
  (weekday calendar). Flows exist on every calendar day; risk is measured on NY business
  days by exact date match.
