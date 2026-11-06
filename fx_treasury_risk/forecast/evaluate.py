"""Rolling-origin evaluation: pinball loss and interval coverage per currency and horizon."""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from fx_treasury_risk.forecast.models import MAX_HORIZON, MODELS, QUANTILES

log = logging.getLogger(__name__)

REPORT_HORIZONS: tuple[int, ...] = (1, 5, 10, 21, 42, 63)
CENTRAL_INTERVALS: dict[int, tuple[float, float]] = {
    50: (0.25, 0.75),
    80: (0.10, 0.90),
    95: (0.025, 0.975),
}


def pinball_loss(y: np.ndarray, q: np.ndarray, tau: float) -> np.ndarray:
    """Quantile (pinball) loss ``max(tau (y - q), (tau - 1)(y - q))``, elementwise."""
    d = y - q
    out: np.ndarray = np.maximum(tau * d, (tau - 1) * d)
    return out


def monthly_origins(
    calendar: pd.DatetimeIndex, start: pd.Timestamp, horizon: int
) -> pd.DatetimeIndex:
    """Last trading day before each month start, leaving ``horizon`` days of actuals.

    The origin is the day *before* the first trading day of the month, so that the first
    forecast horizon is that first trading day: this lines up with a monthly rebalance.
    """
    cal = pd.DatetimeIndex(calendar)
    pos = np.arange(len(cal))
    month = cal.year * 100 + cal.month
    first_of_month = pd.Series(pos, index=cal).groupby(month.to_numpy()).min().to_numpy()
    origins = [
        cal[p - 1]
        for p in first_of_month
        if p >= 1 and cal[p] >= start and p - 1 + horizon < len(cal)
    ]
    return pd.DatetimeIndex(origins)


def rolling_origin_forecasts(
    y: pd.Series,
    calendar: pd.DatetimeIndex,
    origins: pd.DatetimeIndex,
    models: tuple[str, ...] = tuple(MODELS),
    horizon: int = MAX_HORIZON,
    window: int = 750,
) -> pd.DataFrame:
    """Forecast quantiles from every origin for every model, with actuals attached."""
    frames = []
    for origin in origins:
        hist = y[y.index <= origin]
        for name in models:
            f = MODELS[name](hist, calendar, horizon, window)
            df = f.to_frame()
            df["ccy"] = str(y.name)
            frames.append(df)
    out = pd.concat(frames, ignore_index=True)
    actual = y.rename("actual")
    out = out.merge(actual, left_on="target_date", right_index=True, how="left")
    return out


def evaluate(forecasts: pd.DataFrame) -> pd.DataFrame:
    """Summary per (ccy, model, horizon): scaled pinball loss, coverage, median error.

    ``pinball_pct`` is the mean pinball loss over all quantiles divided by the mean
    actual, in percent, so it is comparable across currencies. ``skill`` is one minus
    the ratio to the seasonal-naive pinball loss at the same (ccy, horizon).
    """
    df = forecasts.dropna(subset=["actual"]).copy()
    qcols = [f"q{int(q * 1000):03d}" for q in QUANTILES]
    losses = np.column_stack(
        [
            pinball_loss(df["actual"].to_numpy(), df[c].to_numpy(), q)
            for c, q in zip(qcols, QUANTILES, strict=True)
        ]
    )
    df["pinball"] = losses.mean(axis=1)
    df["abs_err_median"] = np.abs(df["actual"] - df["q500"])
    actual = df["actual"].to_numpy(dtype=float)
    for level, (lo, hi) in CENTRAL_INTERVALS.items():
        lo_q = df[f"q{int(lo * 1000):03d}"].to_numpy(dtype=float)
        hi_q = df[f"q{int(hi * 1000):03d}"].to_numpy(dtype=float)
        df[f"in_{level}"] = (actual >= lo_q) & (actual <= hi_q)
    g = df.groupby(["ccy", "model", "horizon"])
    out = g.agg(
        n=("actual", "size"),
        mean_actual=("actual", "mean"),
        pinball=("pinball", "mean"),
        mae_median=("abs_err_median", "mean"),
        coverage_50=("in_50", "mean"),
        coverage_80=("in_80", "mean"),
        coverage_95=("in_95", "mean"),
    ).reset_index()
    out["pinball_pct"] = 100 * out["pinball"] / out["mean_actual"]
    out["mape_median_pct"] = 100 * out["mae_median"] / out["mean_actual"]
    base = out[out["model"] == "seasonal_naive"][["ccy", "horizon", "pinball"]].rename(
        columns={"pinball": "pinball_naive"}
    )
    out = out.merge(base, on=["ccy", "horizon"], how="left")
    out["skill_vs_naive"] = 1 - out["pinball"] / out["pinball_naive"]
    return out


def headline(evaluation: pd.DataFrame, horizons: tuple[int, ...] = REPORT_HORIZONS) -> pd.DataFrame:
    """Compact table at the report horizons, averaged over currencies."""
    sub = evaluation[evaluation["horizon"].isin(horizons)]
    return (
        sub.groupby(["model", "horizon"])
        .agg(
            pinball_pct=("pinball_pct", "mean"),
            mape_median_pct=("mape_median_pct", "mean"),
            coverage_50=("coverage_50", "mean"),
            coverage_80=("coverage_80", "mean"),
            coverage_95=("coverage_95", "mean"),
            skill_vs_naive=("skill_vs_naive", "mean"),
        )
        .reset_index()
    )
