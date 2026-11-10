"""The exposure a monthly forward hedges: the average forecast over its holding month.

A forward dealt at a monthly rebalance stays in force for every trading day of the
following month, so it should be sized on the exposure over that month, not on the
exposure of a single day. In this business that distinction matters: exposure dips on
the last trading day of every month (fee sweep, weekly payouts), so a forward sized on
a forecast dated at month end under-hedges the rest of the month, and one sized on a
mid-month date over-hedges the month end.

The forecast stage stores median forecasts for every horizon from 1 to 63 trading days,
with their target dates. The holding month of a forward dealt after origin ``T`` is the
calendar month after ``T``'s month; this module averages the medians over its trading
days. The policy backtest (origins on the last trading day of each month) and the live
recommendation use the same rule.
"""

from __future__ import annotations

import pandas as pd


def holding_month(origin: pd.Timestamp) -> pd.Period:
    """The calendar month a forward dealt after ``origin`` covers."""
    return pd.Timestamp(origin).to_period("M") + 1


def holding_month_mean(medians: pd.DataFrame, origin: pd.Timestamp) -> pd.Series:
    """Average median forecast over the trading days of the holding month.

    Parameters
    ----------
    medians
        Median forecasts from one origin: index = target date, columns = currency.
    origin
        The forecast origin (the last day of data).
    """
    idx = pd.DatetimeIndex(medians.index)
    sel = medians[idx.to_period("M") == holding_month(origin)]
    if sel.empty:
        raise ValueError(
            f"no forecasts dated in {holding_month(origin)} from origin {origin.date()}; "
            "the forecast horizon must cover the whole holding month"
        )
    out: pd.Series = sel.mean()
    return out


def holding_month_by_origin(forecasts: pd.DataFrame) -> pd.DataFrame:
    """Holding-month average for every origin in a long forecast frame.

    ``forecasts`` has columns ``origin``, ``target_date``, ``ccy`` and ``q500``; the
    result is indexed by origin with one column per currency.
    """
    rows = {}
    for origin in pd.DatetimeIndex(forecasts["origin"].unique()):
        g = forecasts[forecasts["origin"] == origin]
        wide = g.pivot(index="target_date", columns="ccy", values="q500")
        rows[origin] = holding_month_mean(wide, origin)
    out = pd.DataFrame(rows).T
    out.index = pd.DatetimeIndex(out.index)
    return out
