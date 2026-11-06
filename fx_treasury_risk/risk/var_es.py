"""Value-at-Risk and Expected Shortfall by historical, parametric and Monte Carlo methods.

Interface shared by every method::

    (exposure_usd: Series[ccy], returns: DataFrame[date x ccy], horizon, alpha, ...)
        -> RiskMeasure(var_usd, es_usd, ...)

Loss is ``-P&L`` in USD; both measures are returned as positive numbers at confidence
``alpha`` (0.95 or 0.99). Multi-day horizons: historical simulation uses overlapping
horizon returns; the parametric methods scale daily volatility by ``sqrt(h)``; Monte Carlo
simulates ``h`` daily steps and compounds them.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal

import numpy as np
import pandas as pd
from scipy import stats

from fx_treasury_risk.risk import covariance as cv
from fx_treasury_risk.risk.returns import horizon_returns

Confidence = float
DEFAULT_CONFIDENCES: tuple[float, ...] = (0.95, 0.99)
DEFAULT_WINDOW = 1000  # ~4 years of daily data for the historical and sample estimators


@dataclass(frozen=True)
class RiskMeasure:
    """One VaR/ES estimate with full provenance."""

    method: str
    cov_method: str
    horizon_days: int
    confidence: float
    var_usd: float
    es_usd: float
    exposure_usd: float  # sum of absolute USD exposures used
    n_obs: int
    params: str = ""

    def to_row(self) -> dict[str, object]:
        """Dict for building tidy frames."""
        return asdict(self)


def pnl_from_log_returns(exposure_usd: pd.Series, r: np.ndarray) -> np.ndarray:
    """USD P&L for each row of log returns ``r`` (shape (n, k)) given exposures (k,)."""
    w = exposure_usd.to_numpy(dtype=float)
    out: np.ndarray = (np.expm1(r) * w).sum(axis=1)
    return out


def _var_es_from_losses(loss: np.ndarray, alpha: float) -> tuple[float, float]:
    var = float(np.quantile(loss, alpha))
    tail = loss[loss >= var]
    es = float(tail.mean()) if len(tail) else var
    return var, es


# ---------------------------------------------------------------------------------------
# Historical simulation
# ---------------------------------------------------------------------------------------
def historical(
    exposure_usd: pd.Series,
    returns: pd.DataFrame,
    horizon: int,
    alpha: float,
    window: int = DEFAULT_WINDOW,
) -> RiskMeasure:
    """Empirical quantile of losses over the last ``window`` overlapping horizon returns."""
    r = horizon_returns(returns[exposure_usd.index], horizon).iloc[-window:]
    loss = -pnl_from_log_returns(exposure_usd, r.to_numpy())
    var, es = _var_es_from_losses(loss, alpha)
    return RiskMeasure(
        "historical",
        "none",
        horizon,
        alpha,
        var,
        es,
        float(exposure_usd.abs().sum()),
        len(r),
        f"window={window}",
    )


# ---------------------------------------------------------------------------------------
# Parametric (variance-covariance)
# ---------------------------------------------------------------------------------------
def _portfolio_sigma(exposure_usd: pd.Series, cov: pd.DataFrame, horizon: int) -> float:
    w = exposure_usd.to_numpy(dtype=float)
    c = cov.loc[exposure_usd.index, exposure_usd.index].to_numpy()
    return float(np.sqrt(w @ c @ w) * np.sqrt(horizon))


def parametric_normal(
    exposure_usd: pd.Series,
    cov: pd.DataFrame,
    horizon: int,
    alpha: float,
    cov_method: str,
    n_obs: int,
) -> RiskMeasure:
    """Zero-mean normal: VaR = z sigma, ES = sigma phi(z) / (1 - alpha)."""
    sigma = _portfolio_sigma(exposure_usd, cov, horizon)
    z = stats.norm.ppf(alpha)
    var = z * sigma
    es = sigma * stats.norm.pdf(z) / (1 - alpha)
    return RiskMeasure(
        "parametric_normal",
        cov_method,
        horizon,
        alpha,
        var,
        es,
        float(exposure_usd.abs().sum()),
        n_obs,
    )


def fit_student_df(x: np.ndarray, floc: float = 0.0) -> float:
    """Degrees of freedom of a Student-t fitted by maximum likelihood (location fixed)."""
    df, _loc, _scale = stats.t.fit(x, floc=floc)
    return float(np.clip(df, 2.5, 100.0))


def parametric_student_t(
    exposure_usd: pd.Series,
    cov: pd.DataFrame,
    returns: pd.DataFrame,
    horizon: int,
    alpha: float,
    cov_method: str,
    window: int = DEFAULT_WINDOW,
) -> RiskMeasure:
    """Student-t on the portfolio return with variance matched to ``sigma^2``.

    If ``T ~ t_nu`` then ``X = sigma * sqrt((nu-2)/nu) * T`` has standard deviation
    ``sigma``. ``VaR = sigma_s * t_nu^{-1}(alpha)`` and
    ``ES = sigma_s * f_nu(q) * (nu + q^2) / ((nu - 1) (1 - alpha))`` with ``q`` the quantile
    (McNeil, Frey & Embrechts, Quantitative Risk Management, eq. 2.26).
    ``nu`` is fitted on the standardised daily portfolio return over ``window`` days.
    """
    sigma = _portfolio_sigma(exposure_usd, cov, horizon)
    r = returns[exposure_usd.index].dropna().iloc[-window:]
    port = pnl_from_log_returns(exposure_usd, r.to_numpy())
    nu = fit_student_df(port / port.std(ddof=1))
    q = stats.t.ppf(alpha, nu)
    scale = sigma * np.sqrt((nu - 2) / nu)
    var = scale * q
    es = scale * stats.t.pdf(q, nu) * (nu + q**2) / ((nu - 1) * (1 - alpha))
    return RiskMeasure(
        "parametric_t",
        cov_method,
        horizon,
        alpha,
        float(var),
        float(es),
        float(exposure_usd.abs().sum()),
        len(r),
        f"nu={nu:.1f}",
    )


# ---------------------------------------------------------------------------------------
# Monte Carlo with a Student-t copula over EWMA correlations
# ---------------------------------------------------------------------------------------
def simulate_t_copula_paths(
    corr: np.ndarray,
    vols: np.ndarray,
    nu_copula: float,
    nu_marginals: np.ndarray,
    horizon: int,
    n_paths: int,
    rng: np.random.Generator,
) -> np.ndarray:
    """Simulate ``horizon``-day log returns, shape (n_paths, k).

    Each day: ``Z ~ N(0, corr)``, ``W ~ chi2(nu)/nu``, ``T = Z / sqrt(W)`` (a multivariate
    t), ``U = F_t(T)`` (uniform margins with t-copula dependence), then marginal returns
    ``r_c = vol_c * sqrt((nu_c - 2)/nu_c) * F_{t,nu_c}^{-1}(U_c)`` so that each has
    standard deviation ``vol_c``. Days are independent and summed.
    """
    k = len(vols)
    chol = np.linalg.cholesky(corr)
    total = np.zeros((n_paths, k))
    scale = vols * np.sqrt((nu_marginals - 2) / nu_marginals)
    for _ in range(horizon):
        z = rng.standard_normal((n_paths, k)) @ chol.T
        w = rng.chisquare(nu_copula, size=(n_paths, 1)) / nu_copula
        t = z / np.sqrt(w)
        u = stats.t.cdf(t, nu_copula)
        u = np.clip(u, 1e-10, 1 - 1e-10)
        total += stats.t.ppf(u, nu_marginals) * scale
    return total


def monte_carlo_t(
    exposure_usd: pd.Series,
    returns: pd.DataFrame,
    horizon: int,
    alpha: float,
    lam: float = 0.94,
    n_paths: int = 20_000,
    seed: int = 7,
    window: int = DEFAULT_WINDOW,
) -> RiskMeasure:
    """Monte Carlo VaR/ES with EWMA volatilities and correlations and t-copula tails."""
    r = returns[exposure_usd.index].dropna()
    cov = cv.ewma_cov(r, lam)
    vols = np.sqrt(np.diag(cov.to_numpy()))
    corr = cv.cov_to_corr(cov).to_numpy()
    recent = r.iloc[-window:].to_numpy()
    nu_m = np.array(
        [fit_student_df(recent[:, j] / recent[:, j].std(ddof=1)) for j in range(r.shape[1])]
    )
    nu_c = float(np.median(nu_m))
    rng = np.random.default_rng(seed)
    paths = simulate_t_copula_paths(corr, vols, nu_c, nu_m, horizon, n_paths, rng)
    loss = -pnl_from_log_returns(exposure_usd, paths)
    var, es = _var_es_from_losses(loss, alpha)
    return RiskMeasure(
        "monte_carlo_t",
        f"ewma_{lam:g}",
        horizon,
        alpha,
        var,
        es,
        float(exposure_usd.abs().sum()),
        len(r),
        f"n_paths={n_paths};nu_copula={nu_c:.1f};seed={seed}",
    )


# ---------------------------------------------------------------------------------------
# Driver: the full comparison table
# ---------------------------------------------------------------------------------------
Basis = Literal["net", "net_of_hedges"]


def risk_table(
    exposure_usd: pd.Series,
    returns: pd.DataFrame,
    horizons: tuple[int, ...] = (1, 10, 21),
    confidences: tuple[float, ...] = DEFAULT_CONFIDENCES,
    window: int = DEFAULT_WINDOW,
    mc_paths: int = 20_000,
) -> pd.DataFrame:
    """Every method x covariance x horizon x confidence, as one tidy frame."""
    covs = cv.covariance_by_method(returns[exposure_usd.index], window)
    n_obs = len(returns[exposure_usd.index].dropna().iloc[-window:])
    rows: list[dict[str, object]] = []
    for h in horizons:
        for a in confidences:
            rows.append(historical(exposure_usd, returns, h, a, window).to_row())
            for name, cov in covs.items():
                rows.append(parametric_normal(exposure_usd, cov, h, a, name, n_obs).to_row())
                rows.append(
                    parametric_student_t(exposure_usd, cov, returns, h, a, name, window).to_row()
                )
            for lam in cv.EWMA_LAMBDAS:
                rows.append(
                    monte_carlo_t(
                        exposure_usd, returns, h, a, lam, mc_paths, window=window
                    ).to_row()
                )
    return pd.DataFrame(rows)
