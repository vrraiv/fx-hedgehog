"""Covariance estimators for daily log returns.

All functions take a wide frame of daily returns (rows = days, columns = currencies)
and return a covariance matrix as a DataFrame with the same labels, in daily units.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

EWMA_LAMBDAS: tuple[float, ...] = (0.94, 0.97)


def _clean(r: pd.DataFrame, window: int | None) -> pd.DataFrame:
    x = r.dropna()
    return x.iloc[-window:] if window else x


def sample_cov(r: pd.DataFrame, window: int | None = None) -> pd.DataFrame:
    """Unbiased sample covariance over the last ``window`` rows (all rows if None)."""
    x = _clean(r, window)
    return pd.DataFrame(
        np.cov(x.to_numpy(), rowvar=False, ddof=1), index=x.columns, columns=x.columns
    )


def ewma_cov(r: pd.DataFrame, lam: float = 0.94) -> pd.DataFrame:
    """RiskMetrics exponentially weighted covariance at the last date.

    ``S_t = lam * S_{t-1} + (1 - lam) * r_t r_t'`` with zero mean, initialised from the
    sample covariance of the first 60 rows. Weights sum to one in the limit, so the result
    is a daily covariance comparable with :func:`sample_cov`.
    """
    x = _clean(r, None).to_numpy()
    n0 = min(60, len(x))
    s = np.cov(x[:n0], rowvar=False, ddof=1)
    for row in x[n0:]:
        s = lam * s + (1 - lam) * np.outer(row, row)
    cols = _clean(r, None).columns
    return pd.DataFrame(s, index=cols, columns=cols)


def ewma_cov_path(r: pd.DataFrame, lam: float = 0.94) -> np.ndarray:
    """EWMA covariance *after* each row: array of shape (n, k, k) (used by backtests)."""
    x = _clean(r, None).to_numpy()
    n, k = x.shape
    n0 = min(60, n)
    out = np.empty((n, k, k))
    s = np.cov(x[:n0], rowvar=False, ddof=1)
    out[: n0 - 1] = s
    for t in range(n0 - 1, n):
        s = lam * s + (1 - lam) * np.outer(x[t], x[t])
        out[t] = s
    return out


def ledoit_wolf_cov(r: pd.DataFrame, window: int | None = None) -> tuple[pd.DataFrame, float]:
    """Ledoit-Wolf (2004) shrinkage towards a scaled identity.

    ``S_lw = (1 - delta) * S + delta * mu * I`` where ``mu = trace(S) / k`` and the
    intensity ``delta`` minimises expected Frobenius loss, estimated as in Ledoit & Wolf,
    "A well-conditioned estimator for large-dimensional covariance matrices", J.
    Multivariate Analysis 88 (2004), eq. 14, with ``delta`` clipped to [0, 1].
    Returns the matrix and the intensity used.
    """
    x = _clean(r, window)
    data = x.to_numpy()
    data = data - data.mean(axis=0)
    n, k = data.shape
    s = data.T @ data / n
    mu = np.trace(s) / k
    d2 = np.sum((s - mu * np.eye(k)) ** 2)  # ||S - mu I||^2_F (sum of squares)
    b2 = 0.0
    for row in data:
        b2 += np.sum((np.outer(row, row) - s) ** 2)
    b2 = min(b2 / n**2, d2)
    delta = float(b2 / d2) if d2 > 0 else 0.0
    delta = min(max(delta, 0.0), 1.0)
    s_lw = (1 - delta) * s + delta * mu * np.eye(k)
    return pd.DataFrame(s_lw, index=x.columns, columns=x.columns), delta


def cov_to_corr(cov: pd.DataFrame) -> pd.DataFrame:
    """Correlation matrix from a covariance matrix."""
    sd = np.sqrt(np.diag(cov.to_numpy()))
    c = cov.to_numpy() / np.outer(sd, sd)
    return pd.DataFrame(c, index=cov.index, columns=cov.columns)


def covariance_by_method(r: pd.DataFrame, window: int | None = 1000) -> dict[str, pd.DataFrame]:
    """All estimators keyed by a short label, for comparison tables."""
    out = {"sample": sample_cov(r, window)}
    for lam in EWMA_LAMBDAS:
        out[f"ewma_{lam:g}"] = ewma_cov(r, lam)
    lw, _ = ledoit_wolf_cov(r, window)
    out["ledoit_wolf"] = lw
    return out
