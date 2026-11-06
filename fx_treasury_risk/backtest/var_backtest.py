"""Rolling one-day VaR/ES forecasts along the actual exposure path, and their tests.

Each day ``t`` from the start of the out-of-sample window the model sees returns up to
``t-1`` and the exposure held at the close of ``t-1``; it forecasts the loss distribution
for day ``t``. Realised loss is ``-sum_c w_{t-1,c} (exp(r_{t,c}) - 1)``.

Methods implemented:

* ``historical``       empirical quantile over a rolling window of P&L recomputed with
                       the current exposure weights.
* ``normal_ewma``      Gaussian with EWMA(0.94) covariance.
* ``t_ewma``           Student-t with EWMA(0.94) covariance, ``nu`` refitted monthly.
* ``normal_sample``    Gaussian with the rolling sample covariance.

The Monte Carlo t-copula is deliberately excluded from the daily backtest: with EWMA
correlations and a t copula it collapses to the ``t_ewma`` distribution for a linear
portfolio at a one-day horizon, so it would add cost without information.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import duckdb
import numpy as np
import pandas as pd
from scipy import stats

from fx_treasury_risk import config, db
from fx_treasury_risk.backtest import coverage
from fx_treasury_risk.report.tables import df_to_markdown, write_markdown
from fx_treasury_risk.risk import covariance as cv
from fx_treasury_risk.risk.returns import fx_returns
from fx_treasury_risk.risk.var_es import fit_student_df

log = logging.getLogger(__name__)

OOS_START = pd.Timestamp("2015-01-02")
WINDOW = 1000
N_SIMS = 1000


@dataclass(frozen=True)
class Forecasts:
    """Aligned daily arrays for one method and one confidence level."""

    dates: pd.DatetimeIndex
    loss: np.ndarray
    var: np.ndarray
    es: np.ndarray
    sampler: np.ndarray  # (N_SIMS, T) losses drawn under the model, for the ES p-values


def _exposure_path(con: duckdb.DuckDBPyConnection, basis: str) -> pd.DataFrame:
    col = {"net": "net_usd", "net_of_hedges": "net_of_hedges_usd"}[basis]
    df = con.execute(f"SELECT obs_date, ccy, {col} AS w FROM exposure_group_fx").df()
    w = df.pivot(index="obs_date", columns="ccy", values="w")
    w.index = pd.DatetimeIndex(w.index)
    w.columns.name = None
    return w


def forecast_series(
    returns: pd.DataFrame,
    weights: pd.DataFrame,
    method: str,
    alpha: float,
    oos_start: pd.Timestamp = OOS_START,
    window: int = WINDOW,
    n_sims: int = N_SIMS,
    seed: int = 11,
) -> Forecasts:
    """Daily VaR/ES forecasts and realised losses for one method."""
    r = returns.dropna()
    ccys = list(r.columns)
    w = weights[ccys].reindex(r.index).ffill()
    idx = np.flatnonzero(r.index >= oos_start)
    idx = idx[idx >= window]  # need a full window of history
    rng = np.random.default_rng(seed)
    rmat = r.to_numpy()
    wmat = w.to_numpy()
    t_len = len(idx)
    loss = np.empty(t_len)
    var = np.empty(t_len)
    es = np.empty(t_len)
    sampler = np.empty((n_sims, t_len))
    ewma_path = cv.ewma_cov_path(r, 0.94) if method in ("normal_ewma", "t_ewma") else None
    nu = 5.0
    z = stats.norm.ppf(alpha)
    for j, t in enumerate(idx):
        w_prev = wmat[t - 1]
        loss[j] = -float(np.expm1(rmat[t]) @ w_prev)
        hist = rmat[t - window : t]
        if method == "historical":
            pl = -(np.expm1(hist) @ w_prev)
            v = np.quantile(pl, alpha)
            var[j] = v
            tail = pl[pl >= v]
            es[j] = tail.mean() if len(tail) else v
            sampler[:, j] = pl[rng.integers(0, window, size=n_sims)]
            continue
        cov = ewma_path[t - 1] if ewma_path is not None else np.cov(hist, rowvar=False, ddof=1)
        sigma = float(np.sqrt(w_prev @ cov @ w_prev))
        if method in ("normal_ewma", "normal_sample"):
            var[j] = z * sigma
            es[j] = sigma * stats.norm.pdf(z) / (1 - alpha)
            sampler[:, j] = -rng.standard_normal(n_sims) * sigma
        elif method == "t_ewma":
            if j % 21 == 0:  # refit the tail index monthly
                port = -(hist @ w_prev)
                nu = fit_student_df(port / port.std(ddof=1))
            q = stats.t.ppf(alpha, nu)
            scale = sigma * np.sqrt((nu - 2) / nu)
            var[j] = scale * q
            es[j] = scale * stats.t.pdf(q, nu) * (nu + q**2) / ((nu - 1) * (1 - alpha))
            sampler[:, j] = -rng.standard_t(nu, size=n_sims) * scale
        else:
            raise ValueError(f"unknown method {method!r}")
    return Forecasts(pd.DatetimeIndex(r.index[idx]), loss, var, es, sampler)


METHODS: tuple[str, ...] = ("historical", "normal_sample", "normal_ewma", "t_ewma")


def run_var_backtest(
    paths: config.Paths,
    basis: str = "net",
    methods: tuple[str, ...] = METHODS,
    confidences: tuple[float, ...] = (0.95, 0.99),
    oos_start: pd.Timestamp = OOS_START,
) -> pd.DataFrame:
    """Coverage and ES test results, one row per (method, confidence); stored in DuckDB."""
    con = db.connect(paths)
    try:
        returns = fx_returns(con)
        weights = _exposure_path(con, basis)
        rows: list[dict[str, object]] = []
        for method in methods:
            for alpha in confidences:
                f = forecast_series(returns, weights, method, alpha, oos_start)
                c = coverage.coverage_tests(f.loss, f.var, alpha)
                z1 = coverage.acerbi_szekely_z1(f.loss, f.var, f.es)
                z2 = coverage.acerbi_szekely_z2(f.loss, f.var, f.es, alpha)
                p1, p2 = coverage.simulate_z_pvalues(f.sampler, f.var, f.es, alpha, z1, z2)
                rows.append(
                    {
                        "basis": basis,
                        "method": method,
                        "confidence": alpha,
                        "oos_start": f.dates[0].date(),
                        "oos_end": f.dates[-1].date(),
                        **c.__dict__,
                        "z1": z1,
                        "z1_p": p1,
                        "z2": z2,
                        "z2_p": p2,
                        "mean_var_usd": float(f.var.mean()),
                        "mean_es_usd": float(f.es.mean()),
                    }
                )
                log.info(
                    "%s @%.2f: %d/%d exceptions (expected %.1f), kupiec p=%.3f, z2=%.2f p=%.3f",
                    method,
                    alpha,
                    c.n_exceptions,
                    c.n_obs,
                    c.expected_exceptions,
                    c.kupiec_p,
                    z2,
                    p2,
                )
        out = coverage.summarise(pd.DataFrame(rows))
        con.register("bt_df", out)
        con.execute("CREATE OR REPLACE TABLE var_backtest_results AS SELECT * FROM bt_df")
        con.unregister("bt_df")
    finally:
        con.close()
    write_backtest_table(paths, out)
    return out


def write_backtest_table(paths: config.Paths, out: pd.DataFrame) -> None:
    """Dump the verdict table to reports/var_backtest.md."""
    cols = [
        "basis",
        "method",
        "confidence",
        "oos_start",
        "oos_end",
        "n_obs",
        "n_exceptions",
        "expected_exceptions",
        "kupiec_p",
        "christoffersen_p",
        "conditional_p",
        "traffic_light",
        "z1",
        "z1_p",
        "z2",
        "z2_p",
        "verdict",
    ]
    body = df_to_markdown(out[cols].round(3))
    note = (
        "One-day horizon, daily, exposure held at the previous close. Z1/Z2 are in losses: "
        "positive means realised tail losses exceeded the forecast ES. Verdict is PASS when "
        "Kupiec, Christoffersen, conditional coverage and Z2 all have p >= 0.05."
    )
    write_markdown(
        paths.reports_dir / "var_backtest.md",
        "VaR / ES coverage backtest",
        [("Results", body), ("Reading the table", note)],
    )
