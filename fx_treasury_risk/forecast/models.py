"""Forecast models. Each returns quantiles of future exposure for horizons 1..H."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from fx_treasury_risk.forecast.calendar import day_type_codes, feature_matrix, future_dates

QUANTILES: tuple[float, ...] = (0.025, 0.10, 0.25, 0.50, 0.75, 0.90, 0.975)
SEASON_DAYS = 28  # seasonal naive: same weekday, four weeks earlier
MAX_HORIZON = 63


@dataclass(frozen=True)
class Forecast:
    """Quantile forecasts: ``quantiles`` has shape (H, len(QUANTILES)), rows = horizon 1..H."""

    model: str
    origin: pd.Timestamp
    dates: pd.DatetimeIndex
    quantiles: np.ndarray
    params: str = ""

    def to_frame(self) -> pd.DataFrame:
        """Long frame with one row per horizon and a column per quantile."""
        df = pd.DataFrame(self.quantiles, columns=[f"q{int(q * 1000):03d}" for q in QUANTILES])
        df.insert(0, "horizon", np.arange(1, len(df) + 1))
        df.insert(1, "target_date", self.dates)
        df.insert(0, "origin", self.origin)
        df.insert(0, "model", self.model)
        return df


def _error_quantiles(errors_by_h: list[np.ndarray]) -> np.ndarray:
    """Quantiles of log errors per horizon; shape (H, len(QUANTILES)). Zero if too few errors."""
    out = np.zeros((len(errors_by_h), len(QUANTILES)))
    for i, err in enumerate(errors_by_h):
        if len(err) >= 20:
            out[i] = np.quantile(err, QUANTILES)
    return out


# ---------------------------------------------------------------------------------------
# seasonal naive
# ---------------------------------------------------------------------------------------
def seasonal_naive(
    y: pd.Series, calendar: pd.DatetimeIndex, horizon: int = MAX_HORIZON, window: int = 750
) -> Forecast:
    """Repeat the value on the same weekday four weeks earlier; empirical error quantiles.

    The target date ``d`` takes the value at ``d - 28k`` calendar days (the last trading
    day on or before it, if that day is a holiday), with ``k`` the fewest four-week steps
    that reach back to the origin. Four weeks rather than "21 trading days" keeps the
    weekday: flows have a weekday pattern, and a lag that drifts across weekdays would make
    the baseline weaker than a treasury analyst's obvious first guess. Interval width at
    each horizon comes from the quantiles of the same rule's log errors over the training
    window, so it widens with ``k``.
    """
    yv = y.to_numpy(dtype=float)
    hist = pd.DatetimeIndex(y.index)
    n = len(yv)
    origin = pd.Timestamp(hist[-1])
    dates = future_dates(origin, horizon, calendar)
    ks = np.ceil((dates - origin).days.to_numpy() / SEASON_DAYS).astype(int)
    points = yv[_lag_index(hist, dates, ks)]
    start = max(0, n - window)
    errors = []
    for k in ks:
        src = _lag_index(hist, hist[start:], np.full(n - start, k))
        ok = src >= 0
        t = np.arange(start, n)[ok]
        errors.append(np.log(yv[t] / yv[src[ok]]))
    out = points[:, None] * np.exp(_error_quantiles(errors))
    return Forecast("seasonal_naive", origin, dates, out, f"season={SEASON_DAYS}d")


def _lag_index(hist: pd.DatetimeIndex, targets: pd.DatetimeIndex, k: np.ndarray) -> np.ndarray:
    """Row of ``hist`` on or before ``target - 28k`` days; -1 if before the sample."""
    src = targets - pd.to_timedelta(SEASON_DAYS * np.asarray(k), unit="D")
    out: np.ndarray = hist.searchsorted(src, side="right") - 1
    return out


# ---------------------------------------------------------------------------------------
# calendar regression with AR(1) errors on the log scale
# ---------------------------------------------------------------------------------------
@dataclass(frozen=True)
class CalendarAR1Fit:
    """Fitted parameters of the structural regression."""

    beta: np.ndarray
    columns: list[str]
    phi: float
    sigma: float
    resid: np.ndarray  # OLS residuals e_t over the training window
    fitted: np.ndarray  # x_t' beta over the training window
    log_y: np.ndarray
    t0: pd.Timestamp
    n_obs: int
    day_type: np.ndarray  # day-type code of each training date
    type_scale: np.ndarray  # residual s.d. per day-type code (pooled where data are thin)


def fit_calendar_ar1(
    y: pd.Series, window: int = 750, calendar: pd.DatetimeIndex | None = None
) -> CalendarAR1Fit:
    """OLS of log exposure on calendar features, AR(1) on the residuals.

    ``log y_t = x_t' beta + e_t``, ``e_t = phi e_{t-1} + eps_t``. The two-step estimate
    (OLS, then AR(1) on residuals) is consistent because the regressors are deterministic.
    """
    ys = y.iloc[-window:]
    if (ys <= 0).any():
        raise ValueError("calendar_ar1 needs strictly positive exposure (log scale)")
    t0 = pd.Timestamp(ys.index[0])
    cal = pd.DatetimeIndex(y.index) if calendar is None else calendar
    x = feature_matrix(pd.DatetimeIndex(ys.index), t0, cal)
    xv = x.to_numpy()
    ly = np.log(ys.to_numpy(dtype=float))
    beta, *_ = np.linalg.lstsq(xv, ly, rcond=None)
    fitted = xv @ beta
    e = ly - fitted
    phi = float(np.clip(np.corrcoef(e[:-1], e[1:])[0, 1], -0.99, 0.99))
    eps = e[1:] - phi * e[:-1]
    sigma = float(np.std(eps, ddof=1))
    codes = day_type_codes(x)
    scale = _type_scales(e, codes)
    return CalendarAR1Fit(
        beta, list(x.columns), phi, sigma, e, fitted, ly, t0, len(ys), codes, scale
    )


def _type_scales(resid: np.ndarray, codes: np.ndarray, min_obs: int = 30) -> np.ndarray:
    """Residual s.d. by day type, falling back to the pooled s.d. for thin types."""
    pooled = float(np.std(resid, ddof=1))
    out = np.full(codes.max() + 1, pooled)
    for c in range(codes.max() + 1):
        sel = resid[codes == c]
        if len(sel) >= min_obs:
            out[c] = float(np.std(sel, ddof=1))
    return out


def insample_horizon_errors(
    fit: CalendarAR1Fit, horizon: int, origin_type: int | None = None, min_obs: int = 24
) -> list[np.ndarray]:
    """Log errors of in-sample ``h``-step forecasts ``fitted[t+h] + phi^h e[t]`` for each h.

    These are the model's own multi-step errors over the training window, standardised
    by the residual s.d. of the target date's day type. If ``origin_type`` is given, only
    in-sample origins of that day type are used (falling back to all origins when fewer
    than ``min_obs`` are available): a forecast made on the month-end sweep day starts
    from a residual that does not carry forward like an ordinary day's, and the policy
    always forecasts from month ends.
    """
    n = len(fit.log_y)
    scale = fit.type_scale[fit.day_type]
    out = []
    for h in range(1, horizon + 1):
        if n - h <= 0:
            out.append(np.array([]))
            continue
        pred = fit.fitted[h:] + fit.phi**h * fit.resid[:-h]
        err = (fit.log_y[h:] - pred) / scale[h:]
        if origin_type is not None:
            same = fit.day_type[:-h] == origin_type
            if same.sum() >= min_obs:
                err = err[same]
        out.append(err)
    return out


def calendar_ar1(
    y: pd.Series, calendar: pd.DatetimeIndex, horizon: int = MAX_HORIZON, window: int = 750
) -> Forecast:
    """Forecast quantiles from :func:`fit_calendar_ar1`.

    Point forecast at horizon ``h`` (log scale): ``x_{T+h}' beta + phi^h e_T``. Quantiles
    add the empirical quantiles of the standardised in-sample ``h``-step log errors
    from origins of the same day type, rescaled by the target date's day-type
    volatility, then exponentiate: intervals are asymmetric in levels, widen with the
    horizon, and are wider around the month turn.
    """
    fit = fit_calendar_ar1(y, window, calendar)
    origin = pd.Timestamp(y.index[-1])
    dates = future_dates(origin, horizon, calendar)
    xfeat = feature_matrix(dates, fit.t0, calendar)
    xf = xfeat[fit.columns].to_numpy()
    h = np.arange(1, horizon + 1)
    mean = xf @ fit.beta + fit.phi**h * fit.resid[-1]
    eq = _error_quantiles(insample_horizon_errors(fit, horizon, int(fit.day_type[-1])))
    target_scale = fit.type_scale[day_type_codes(xfeat)]
    out = np.exp(mean[:, None] + target_scale[:, None] * eq)
    return Forecast(
        "calendar_ar1",
        origin,
        dates,
        out,
        f"phi={fit.phi:.3f};sigma={fit.sigma:.4f};n={fit.n_obs}",
    )


MODELS = {"seasonal_naive": seasonal_naive, "calendar_ar1": calendar_ar1}
