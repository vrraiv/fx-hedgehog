# ADR-0013: Hedge-policy backtest design and the ES budget

**Status:** accepted, 2026-11-06

## Context

The primary question compares hedge policies out of sample from 2015, including March
2020 and 2022. Choices: the rebalance cadence, what exposure the policy hedges, how the
forward's P&L is marked, transaction costs, which policies to compare, and the size of
the ES budget.

## Decision

* **Cadence:** monthly, on the first NY business day; one-month forwards dealt at the
  previous close (the origin) and held to the next rebalance. No intra-month adjustment.
* **Exposure input: the median forecast from ADR-0011 at the origin, averaged over the
  trading days of the month the forward covers** (``exposure_input: forecast``,
  ``hedge/sizing.py``). A forward is in force for the whole month, so it is sized on the
  month, not on one day. An earlier version hedged the single forecast 21 trading days
  out, whose date falls on any weekday and near the month-end dip: the EUR forward then
  ranged from 0.36 to 2.05 times the month's average EUR exposure. The realised P&L uses
  the *actual*
  daily exposure path,
  so forecast error is a cost of the policy, not an assumption. ``actual`` (hedge what
  you hold at the origin) is available as a switch.
* **Information set:** EWMA(0.94) covariance and Student-t tail index from data up to
  the origin; short rates at the origin; no look-ahead anywhere.
* **Forward P&L:** daily mark-to-market ``notional * dS`` (delta one) plus carry
  ``notional * (S_0 - F)`` accrued evenly over the month; the two sum to the forward's
  payoff ``notional * (S_T - F)`` (tested). Spread is charged on the first day on the
  full notional dealt, from the per-currency table in ``config/hedge.yaml``.
* **Policies:** unhedged; legacy 50% (every currency, every month); full hedge; optimizer
  (ADR-0012) with the previous month's ratios as the starting point.
* **Metrics:** annualized daily P&L volatility, monthly P&L volatility, total P&L,
  carry and spread per year, maximum drawdown of cumulative P&L, worst month, share of
  months in which the budget bound. Reported overall, by year, and for March/April 2020
  and September/October 2022. Two loss counts with different jobs:
  * *months losing more than the budget* is a plain loss frequency, comparable across
    policies. It is not a model test: a correct 99% ES is exceeded in well under 1% of
    months, and only the optimizer is held to the budget.
  * *months beyond the ex-ante VaR* is the model test: months whose loss exceeded the
    policy's own 21-day 99% VaR at the origin, about 1% of months if the model is right.
    A full hedge of the forecast has zero ex-ante VaR, so every losing month counts; that
    is the point, since all of its risk is forecast error the model does not see.
* **Significance:** the optimizer's monthly P&L minus each other policy's, tested for a
  zero mean with a Newey-West t-statistic (the Diebold-Mariano form; volatility clusters,
  so the months are not independent). The difference is split into carry plus spread,
  which is known when the forwards are dealt, and spot, which is the outcome of the risk
  left open. Over about twelve years a carry advantage of a few tenths of a million a
  month is certain, while the spot outcome of three open emerging-market currencies has a
  monthly standard deviation of about a million; the test says which dominates.
* **ES budget: USD 4m** at 21 days / 99%, fixed in USD. A treasury risk appetite is
  written as a currency amount, and a fixed amount makes the policy's behaviour visible:
  the synthetic business grows 8% a year, so the budget is slack early and binds hard
  later, which is exactly the regime a real treasury lives through. Today the unhedged
  21-day 99% ES of the forecast exposure is about USD 13m, so the budget demands a 70%
  reduction. The frontier figure shows the whole trade-off so a reader who prefers
  another budget can read off the cost.

## Consequences

* The optimizer's positions are stored in ``hedge_positions`` (entity ``GROUP``,
  source ``optimizer``) and replace the legacy placeholder month by month in the
  exposure waterfall and the risk engine's net-of-hedges basis.
* Because forwards have delta one, the policy's residual risk comes from (i) the
  unhedged share, (ii) forecast error on the hedged share, and (iii) intra-month
  exposure variation; the ex-ante ES covers only (i).
* On the current data the optimizer finishes about USD 14m ahead of a full hedge, and
  the lead is not statistically distinguishable from zero (p of about 0.3): it earned
  about USD 40m more in carry net of spread and gave back about USD 26m on spot. The case
  for the optimizer is that it takes carry within a stated risk budget, not that it has
  shown a P&L edge; the decision report says so.
