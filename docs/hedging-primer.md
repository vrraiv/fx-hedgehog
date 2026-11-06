# Hedging primer

Instrument mechanics in the repo's own notation. Everything here is implemented in
`fx_treasury_risk/hedge/` (milestone 3); this document is written alongside the code so
that every formula can be pointed at a function and a test.

## Notation

| Symbol | Meaning | Where it lives |
|---|---|---|
| `S_t` | spot, USD per one unit of FCY (`usd_per_fcy`) | `fx_usd_master` |
| `F_{t,T}` | outright forward price agreed at `t` for delivery at `T`, same quote direction | `hedge/forwards.py` |
| `r_usd`, `r_fcy` | annualized simple short rates in percent for the tenor `T - t` | `rates_short` view |
| `tau` | year fraction of the tenor | |
| `E_fcy` | exposure in foreign currency units, positive = long FCY | `exposure/` |
| `h` | hedge ratio in [0, 1]: fraction of `E_fcy` sold forward | `hedge/optimizer.py` |

## 1. Why a forward hedges an exposure

The business expects to *receive* `E_fcy` units of foreign currency at `T` (positive
exposure). Its USD value at `T` is `E_fcy * S_T`, unknown today. Selling `h * E_fcy`
forward at `F_{t,T}` locks that fraction in: at `T` the business delivers the currency and
receives `h * E_fcy * F_{t,T}` dollars regardless of `S_T`. The remaining `(1-h) * E_fcy`
is still exposed. Hedged USD value at `T`:

    V_T = h * E_fcy * F_{t,T} + (1 - h) * E_fcy * S_T

A negative exposure (payout owed) is hedged by *buying* forward; the algebra is identical
with the sign of `E_fcy`.

## 2. Forward pricing by covered interest parity

A forward is priced by no-arbitrage, not by expectations. Two ways to hold a dollar for
`tau` years must give the same result: (a) earn `r_usd`; (b) convert to FCY at `S_t`, earn
`r_fcy`, and convert back at the forward `F` agreed today. Equating them:

    F_{t,T} = S_t * (1 + r_usd * tau) / (1 + r_fcy * tau)        (simple rates)

with rates as decimals (percent / 100). The continuously-compounded form is
`F = S * exp((r_usd - r_fcy) * tau)`; the difference between the two at a three-month
tenor is of the order of 0.1 bp of the spot and is ignored.

**Forward points** are `F - S`, conventionally quoted in pips. In our notation a positive
forward point means the FCY is *more* expensive forward than spot, which happens when
`r_usd > r_fcy`.

Worked example (the unit test in `tests/test_forwards.py` uses these numbers):
`S = 1.1000` USD per EUR, `r_usd = 5.00%`, `r_fcy = 3.50%`, `tau = 0.25`.
`F = 1.1000 * 1.0125 / 1.00875 = 1.10409`. Forward points = +40.9 pips.

### Day count

`tau` is computed as `days / 360` for USD, EUR, JPY, CHF and MXN money-market rates and
`days / 365` for GBP, CAD, AUD, BRL, INR and SGD (the `day_count` column of
`rates_short`). Using 360 instead of 365 for a 5% rate changes `F` by
`S * 0.05 * days * (1/360 - 1/365)`: about 1.7 bp of spot at three months and 0.6 bp at
the one-month tenor the policy uses. The code applies the convention per currency and
`tests/test_forwards.py` checks the size of the effect. Brazilian rates are quoted on a
252-business-day compounded basis; treating them as simple ACT/365 at one month
overstates the carry by a few basis points, which is noted rather than modelled.

### Discount-basis T-bills

FRED `DTB3` is quoted on a *bank discount* basis. The simple yield used in CIP is
`y = d / (1 - d * tau)` where `d` is the discount rate; at `d = 5%` and `tau = 0.25` this
is 5.06%. The conversion is applied before pricing.

## 3. Carry: the cost of hedging

Selling FCY forward instead of spot earns (or pays) the forward points. Over the hedge
horizon the **expected cost of the hedge** relative to leaving the exposure open is, to
first order,

    carry_usd = h * E_fcy * (S_t - F_{t,T})   ~=   h * E_usd * (r_fcy - r_usd) * tau

Hedging a high-yielding currency (BRL, MXN, INR against USD) *costs* carry: the forward
sells the currency below spot. Hedging a low-yielding currency (JPY, CHF in 2010-2022)
*earns* carry. This is the number the optimizer minimizes, subject to a risk budget.

Carry is an *expected* cost only under the random-walk assumption for spot (uncovered
interest parity failing on average). The report states this assumption explicitly and the
backtest reports *realized* hedging cost, which includes the spot move.

## 4. Roll cost

Exposures persist beyond the tenor of a single forward, so hedges are rolled: at each
monthly rebalance the maturing forward is settled and a new one is dealt. Over a year of
monthly rolls the realized cost is the sum of twelve monthly carries plus the bid-ask
spread paid on each roll. The backtest charges a per-currency one-way spread from the
table in `config/hedge.yaml` (0.5 bp for EUR to 8 bp for BRL, stylized) on the full
notional dealt each month and reports it separately from carry (ADR-0013).

In the backtest the forward's P&L is marked daily as `notional * dS` (a forward's delta is
one) plus carry `notional * (S_0 - F)` accrued evenly over the month; the two sum to the
payoff `notional * (S_T - F)` at maturity. `tests/test_policy.py` checks that identity.

## 5. What is deliberately not modelled in v1

* **Options.** A forward removes upside as well as downside; an option keeps the upside
  for a premium. Pricing options needs an implied-volatility surface per currency, which
  is not available from public sources at daily frequency for ten currencies, and adds a
  non-linear P&L that the ES budget would have to be computed on by simulation. The
  demonstration's question (minimum carry for a fixed ES) is well posed with forwards
  alone; options are a backlog item.
* **Cross-currency basis.** Post-2008, CIP deviates by a basis of a few to tens of basis
  points for major currencies. Public daily basis data is not available; the forward
  prices here are therefore slightly off market, uniformly across the sample. The
  backtest's realized carry is affected at that order of magnitude.
* **Non-deliverable forwards.** BRL and INR forwards are cash-settled NDFs in practice.
  The P&L mechanics are the same as a deliverable forward; the pricing differs by the
  onshore/offshore basis, which is not modelled.
* **Credit, margin, collateral.** Forwards are assumed uncollateralized with a bank line.
