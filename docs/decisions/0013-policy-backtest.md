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
* **Exposure input: the 21-day-ahead median forecast** from ADR-0011 at the origin
  (``exposure_input: forecast``). The realised P&L uses the *actual* daily exposure path,
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
  carry and spread per year, maximum drawdown of cumulative P&L, worst month, number of
  months whose loss exceeded the ES budget, share of months in which the budget bound.
  Reported overall, by year, and for March/April 2020 and September/October 2022.
* **ES budget: USD 4m** at 21 days / 99%, fixed in USD. A treasury risk appetite is
  written as a currency amount, and a fixed amount makes the policy's behaviour visible:
  the synthetic business grows 8% a year, so the budget is slack early and binds hard
  later, which is exactly the regime a real treasury lives through. Today the unhedged
  21-day 99% ES of the forecast exposure is about USD 20m, so the budget demands an 80%
  reduction. The frontier figure shows the whole trade-off so a reader who prefers
  another budget can read off the cost.

## Consequences

* The optimizer's positions are stored in ``hedge_positions`` (entity ``GROUP``,
  source ``optimizer``) and replace the legacy placeholder month by month in the
  exposure waterfall and the risk engine's net-of-hedges basis.
* Because forwards have delta one, the policy's residual risk comes from (i) the
  unhedged share, (ii) forecast error on the hedged share, and (iii) intra-month
  exposure variation; the ex-ante ES covers only (i).
