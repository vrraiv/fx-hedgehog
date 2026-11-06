"""Calendar features on the NY business-day calendar.

The synthetic business has three calendar rhythms the forecast must know about: weekly
payouts (Friday) at two entities, the month-end fee sweep, and annual retail seasonality.
All features are deterministic functions of the date and the trading calendar, so they
are known for any future date: the model needs no forecast of its own regressors.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

WEEKDAY_LEVELS = (0, 1, 2, 3)  # Mon..Thu dummies; Friday is the reference
DAYS_TO_MONTH_END_LEVELS = (0, 1, 2, 3, 4)  # 0 = last trading day; >= 5 is the reference
DAYS_FROM_MONTH_START_LEVELS = (0, 1, 2)  # first three trading days of the month
MONTH_LEVELS = tuple(range(2, 13))  # Feb..Dec dummies; January is the reference


def extend_to_month_end(calendar: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """Append weekdays so the calendar runs to the last trading day of its final month.

    Month-position features need to know where each month ends; for the final month of
    a truncated calendar that information is not in the data, so plain weekdays stand in
    (US holidays are then ignored for those few days).
    """
    cal = pd.DatetimeIndex(calendar).sort_values()
    last = cal[-1]
    eom = last + pd.offsets.MonthEnd(0)
    if eom <= last:
        return cal
    extra = pd.bdate_range(last + pd.Timedelta(days=1), eom)
    return pd.DatetimeIndex(cal.append(extra))


def position_in_month(dates: pd.DatetimeIndex) -> tuple[np.ndarray, np.ndarray]:
    """Trading-day index from the month start, and distance to the month's last trading day.

    Computed on ``dates`` as given, so pass a calendar that covers whole months (see
    :func:`extend_to_month_end`); a truncated final month would mislabel its last date
    as a month end.
    """
    idx = pd.DatetimeIndex(dates)
    key = idx.year * 100 + idx.month
    s = pd.Series(np.arange(len(idx)), index=idx)
    first = s.groupby(key.to_numpy()).transform("min").to_numpy()
    last = s.groupby(key.to_numpy()).transform("max").to_numpy()
    pos = np.arange(len(idx))
    return pos - first, last - pos


def feature_matrix(
    dates: pd.DatetimeIndex, t0: pd.Timestamp, calendar: pd.DatetimeIndex | None = None
) -> pd.DataFrame:
    """Design matrix (with intercept and trend) for ``dates``.

    ``t0`` anchors the trend so training and forecast dates share one time axis.
    ``calendar`` is the full trading calendar used to locate month ends; it is unioned
    with ``dates`` and extended to the end of its last month.
    """
    idx = pd.DatetimeIndex(dates)
    full = idx if calendar is None else pd.DatetimeIndex(calendar).union(idx)
    full = extend_to_month_end(full)
    from_start_all, to_end_all = position_in_month(full)
    take = full.get_indexer(idx)
    from_start, to_end = from_start_all[take], to_end_all[take]
    cols: dict[str, np.ndarray] = {"const": np.ones(len(idx))}
    cols["trend_years"] = (idx - t0).days.to_numpy() / 365.25
    for d in WEEKDAY_LEVELS:
        cols[f"dow_{d}"] = (idx.day_of_week.to_numpy() == d).astype(float)
    for k in DAYS_TO_MONTH_END_LEVELS:
        cols[f"to_eom_{k}"] = (to_end == k).astype(float)
    for k in DAYS_FROM_MONTH_START_LEVELS:
        cols[f"from_bom_{k}"] = (from_start == k).astype(float)
    for m in MONTH_LEVELS:
        cols[f"month_{m}"] = (idx.month.to_numpy() == m).astype(float)
    return pd.DataFrame(cols, index=idx)


def day_type_codes(x: pd.DataFrame) -> np.ndarray:
    """Integer code per row for the month-position dummy that is on.

    0 = none, 1-5 = to_eom_0..4, 6-8 = from_bom_0..2.

    Residual volatility differs by position in the month (the sweep day and the first
    rebuild days move most), so error quantiles are computed on residuals standardised by
    the volatility of their day type.
    """
    code = np.zeros(len(x), dtype=int)
    for i, k in enumerate(DAYS_TO_MONTH_END_LEVELS, start=1):
        code[x[f"to_eom_{k}"].to_numpy() == 1] = i
    for i, k in enumerate(DAYS_FROM_MONTH_START_LEVELS, start=1 + len(DAYS_TO_MONTH_END_LEVELS)):
        code[x[f"from_bom_{k}"].to_numpy() == 1] = i
    return code


def future_dates(last: pd.Timestamp, n: int, calendar: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """The next ``n`` trading days after ``last``.

    Uses the known calendar where it extends beyond ``last`` (backtests) and plain
    weekdays beyond its end (live forecasts; US holidays are then ignored).
    """
    known = calendar[calendar > last]
    if len(known) >= n:
        return pd.DatetimeIndex(known[:n])
    extra = pd.bdate_range(calendar[-1] + pd.Timedelta(days=1), periods=n - len(known))
    return pd.DatetimeIndex(known.append(extra))


def feature_note() -> str:
    """One-line description for reports."""
    return (
        "weekday (Mon-Thu), 0-4 trading days to month end, first 3 trading days of the month, "
        "month of year, linear trend"
    )
