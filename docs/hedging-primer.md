# Hedging primer

Instrument mechanics in the repo's own notation. Everything here is implemented in
`fx_treasury_risk/hedge/` and `fx_treasury_risk/backtest/policy.py`; this document is
written alongside the code so that every formula can be pointed at a function and a test.
Sections 1-5 cover one forward on one exposure; 6-8 cover the policy across currencies
and what the backtest measures; 9 is a glossary.

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

## 6. Hedge ratios and the risk budget

Section 1 fixed one currency and one ratio `h`. The policy chooses a vector of ratios,
one per currency, and the question is how to trade cost against risk across them.

Let `E_c` be the USD value of the exposure in currency `c` (positive = long), `h_c` the
hedge ratio, `r_c` the log return of `usd_per_fcy` over the horizon. The hedged P&L is
approximately

    P&L = sum_c (1 - h_c) * E_c * r_c

because a forward has delta one: hedging `h_c` of the exposure removes that fraction of
the currency's P&L (the forward's own P&L is `-h_c * E_c * r_c` plus the carry, which is
known at trade time). The hedged book is therefore a linear combination of currency
returns with weights `w_c = (1 - h_c) * E_c`.

**Expected Shortfall of a linear book.** If the returns are jointly elliptical (normal
or Student-t), every linear combination has the same shape of distribution, and its ES at
confidence `alpha` is a multiple of its standard deviation:

    ES_alpha(w) = k(nu, alpha) * sqrt(w' * Sigma * w)

with `Sigma` the covariance of the returns over the horizon and `k` a constant that
depends only on the tail index `nu` and `alpha` (`k = phi(z)/(1-alpha)` for the normal;
`es_multiplier` in `hedge/optimizer.py` for the t). The repo uses the EWMA(0.94)
covariance scaled by `sqrt(21)` and the t tail index estimated on the same window, the
model that passed the coverage tests (ADR-0010).

**Expected cost of the hedge.** From section 3, hedging `h_c` of currency `c` for one
tenor costs `h_c * E_c * (r_fcy,c - r_usd) * tau` of carry (negative = earns) plus the
bid-ask spread on the notional, `h_c * |E_c| * spread_c`. Both are linear in `h_c`.

**The problem.** Minimise the linear cost subject to `ES(w(h)) <= budget` and
`0 <= h_c <= 1`. The ES is a norm (`sqrt(w' Sigma w)` is the Sigma-norm of `w`) of an
affine function of `h`, hence convex; a linear objective over a convex set has a unique
optimum that a local solver finds (ADR-0012). The solution has a simple shape: every
currency whose forward *earns* carry is hedged fully whatever the budget, because that
lowers both cost and risk; the budget is spent on the currencies whose forwards cost
money, in the order of their cost per unit of risk removed. In the current data that is
why EUR, GBP, CAD, JPY, CHF and SGD are always at 100% and the budget is consumed by
BRL, MXN and INR (section 3: high-yielders cost carry).

A 2 bp turnover penalty on the change in notional since the previous month is added to
the objective only, so that ratios do not flip between 0 and 1 when two currencies'
costs are within rounding of each other and the budget is slack; it is not a realized
cost in the backtest.

## 7. Reading the frontier

`reports/figures/hedge_frontier.png` plots the minimum cost for every budget from zero
(full hedge, every `h_c = 1`) up to the unhedged ES (`h_c` free). Three regions:

* **Left end, budget near zero:** the cost is the full-hedge cost, carry of the
  high-yielders and spread on everything. Each extra dollar of budget lets the optimizer
  release the most expensive currency first; the frontier is steep.
* **Middle:** the frontier flattens as cheaper currencies are released. The chosen point
  (USD 4m in `config/hedge.yaml`) sits here; the slope at that point is the marginal
  cost of risk, in USD of annual carry per USD of ES, which is the number to quote when
  someone asks whether the budget should move.
* **Right end:** beyond the budget at which every carry-costing currency is unhedged, the
  constraint stops binding and the line is flat at the cost of hedging only the
  carry-earning currencies, which is negative: the cheapest book earns carry and still
  carries only the risk of the high-yielders.

The reference points on the figure (unhedged, legacy 50%, full hedge) are the same
policies the backtest runs; their distance above the frontier is the inefficiency of a
uniform ratio.

## 8. What the backtest's "hedging cost" measures

The frontier's cost is *expected*: carry under a random-walk spot, plus spread. The
backtest reports *realized* cost, which is the sum of three marked-to-market pieces for
each monthly roll (`backtest/policy.py`, ADR-0013):

    hedge mtm     = notional * (S_t - S_0)            daily, delta one
    carry accrual = notional * (S_0 - F) * (days elapsed / tenor)
    spread        = -|notional| * spread_bp / 1e4      on the trade date

The mark-to-market plus carry sum to the forward's payoff `notional * (S_T - F)` at
maturity. Realized cost differs from expected cost by the spot move on the hedged
notional, which has either sign; over a long sample its mean is the uncovered interest
parity deviation, and over a single stress month it is the whole story (in March 2020
the forwards made USD 4.8m while the exposure lost 10.6m).

Three sources of residual risk remain after hedging, and only the first is inside the ES
budget: the unhedged share of each currency; the error in the exposure forecast the
notional was sized on; and the variation of exposure within the month while the notional
is fixed. The second and third are why a full hedge still shows P&L volatility in the
backtest, and why a month can lose more than the budget.

## 9. Glossary

| Term | Meaning here |
|---|---|
| carry | `(S - F)/S` annualized; the forward discount of the currency. Positive = selling the currency forward costs money |
| CIP | covered interest parity, the no-arbitrage forward price of section 2 |
| ES, Expected Shortfall | the mean loss in the worst `(1 - alpha)` share of outcomes, here `alpha = 0.99`, 21 days |
| frontier | the minimum expected cost for each ES budget (section 7) |
| hedge ratio | fraction of the exposure sold (or bought) forward, in [0, 1] |
| legacy 50% | the placeholder programme: half of last month's average net exposure, every currency |
| NDF | non-deliverable forward, cash-settled; BRL and INR in practice |
| net of hedges | net exposure plus the forwards in force on the date |
| roll | settling the maturing forward and dealing a new one at the next rebalance |
| tenor | the forward's life, 30 days in the policy |
| UIP | uncovered interest parity, the hypothesis that carry is offset by the expected spot move; its average failure is what makes carry a cost |
