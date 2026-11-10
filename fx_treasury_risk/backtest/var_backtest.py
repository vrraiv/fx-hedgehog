"""Rolling one-day VaR/ES forecasts along the actual exposure path: selection and tests.

Each day ``t`` the model sees returns up to ``t-1`` and the exposure held at the close of
``t-1``; it forecasts the loss distribution for day ``t``. Realised loss is
``-sum_c w_{t-1,c} (exp(r_{t,c}) - 1)``.

The sample is split in two (ADR-0010):

* **Selection, 2012-2014.** Every candidate is scored with the FZ0 joint VaR/ES loss at the
  optimizer's confidence. The lowest mean score among the models the optimizer can use
  is the selected model; a Diebold-Mariano test against it says whether the ranking is
  meaningful. History-hungry estimators use all data available when there is less than
  a full window (at least ``MIN_WINDOW`` days), so the selection window can start in 2012.
* **Evaluation, 2015 onward.** Coverage and ES tests for every candidate, the selected one
  included, on data no choice has seen.

The methods:

* ``historical``       empirical quantile over a rolling window of P&L recomputed with
                       the current exposure weights (reference only: the optimizer needs a
                       covariance).
* ``normal_sample``    Gaussian with the rolling sample covariance.
* ``normal_ewma``      Gaussian with EWMA(0.94) covariance.
* ``t_ewma``           Student-t with EWMA(0.94) covariance, ``nu`` refitted monthly.
* ``t_ewma97``         the same with EWMA(0.97).
* ``t_garch``          Student-t with GARCH(1,1) volatilities and EWMA(0.94) correlations.

The Monte Carlo t-copula is deliberately excluded: with EWMA correlations and a t copula it
collapses to the ``t_ewma`` distribution for a linear portfolio at a one-day horizon.
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
from fx_treasury_risk.risk import garch
from fx_treasury_risk.risk.returns import fx_returns
from fx_treasury_risk.risk.var_es import fit_student_df

log = logging.getLogger(__name__)

SELECTION_START = pd.Timestamp("2012-01-01")
OOS_START = pd.Timestamp("2015-01-02")
WINDOW = 1000
MIN_WINDOW = 500
N_SIMS = 1000

METHODS: tuple[str, ...] = (
    "historical",
    "normal_sample",
    "normal_ewma",
    "t_ewma",
    "t_ewma97",
    "t_garch",
)
# Models expressible as k * sqrt(w' Sigma w), which is what the optimizer needs.
OPTIMIZER_METHODS: tuple[str, ...] = tuple(m for m in METHODS if m != "historical")
_COV_KEY = {
    "normal_ewma": "ewma_0.94",
    "t_ewma": "ewma_0.94",
    "t_ewma97": "ewma_0.97",
    "t_garch": "garch",
}


def method_for_ewma(lam: float) -> str | None:
    """Backtest name of the Student-t EWMA model with decay ``lam`` (None if not tested)."""
    return {0.94: "t_ewma", 0.97: "t_ewma97"}.get(round(lam, 4))


@dataclass(frozen=True)
class Forecasts:
    """Aligned daily arrays for one method and one confidence level."""

    dates: pd.DatetimeIndex
    loss: np.ndarray
    var: np.ndarray
    es: np.ndarray
    sampler: np.ndarray  # (N_SIMS, T) losses drawn under the model, for the ES p-values

    def subset(self, mask: np.ndarray) -> Forecasts:
        """The same forecasts restricted to the days in ``mask``."""
        return Forecasts(
            self.dates[mask], self.loss[mask], self.var[mask], self.es[mask], self.sampler[:, mask]
        )


@dataclass(frozen=True)
class CovPaths:
    """Covariance forecasts after each row, keyed by estimator, plus the GARCH fit record."""

    paths: dict[str, np.ndarray]
    garch_fits: int
    garch_failed: int


def cov_paths(r: pd.DataFrame, keys: set[str], window: int = WINDOW) -> CovPaths:
    """Build the covariance paths named in ``keys`` (``ewma_<lam>`` or ``garch``)."""
    out: dict[str, np.ndarray] = {}
    fits = failed = 0
    for key in sorted(keys - {"garch"}):
        out[key] = cv.ewma_cov_path(r, float(key.removeprefix("ewma_")))
    if "garch" in keys:
        ew = out.get("ewma_0.94")
        if ew is None:
            ew = cv.ewma_cov_path(r, 0.94)
        sd = np.sqrt(np.einsum("tii->ti", ew))
        corr = ew / sd[:, :, None] / sd[:, None, :]
        gp = garch.garch_vol_path(r.to_numpy(), window=window, min_obs=MIN_WINDOW)
        out["garch"] = corr * gp.vol[:, :, None] * gp.vol[:, None, :]
        fits, failed = gp.n_fits, gp.n_failed
    return CovPaths(out, fits, failed)


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
    start: pd.Timestamp = SELECTION_START,
    window: int = WINDOW,
    n_sims: int = N_SIMS,
    seed: int = 11,
    min_window: int = MIN_WINDOW,
    paths: CovPaths | None = None,
) -> Forecasts:
    """Daily VaR/ES forecasts and realised losses for one method from ``start``.

    Rolling estimators use the last ``window`` days, or every earlier day when fewer are
    available; days with less than ``min_window`` of history are skipped.
    """
    r = returns.dropna()
    ccys = list(r.columns)
    w = weights[ccys].reindex(r.index).ffill()
    idx = np.flatnonzero(r.index >= start)
    idx = idx[idx >= min_window]
    rng = np.random.default_rng(seed)
    rmat = r.to_numpy()
    wmat = w.to_numpy()
    t_len = len(idx)
    loss = np.empty(t_len)
    var = np.empty(t_len)
    es = np.empty(t_len)
    sampler = np.empty((n_sims, t_len))
    key = _COV_KEY.get(method)
    if key is not None and (paths is None or key not in paths.paths):
        paths = cov_paths(r, {key}, window)
    path = paths.paths[key] if key is not None and paths is not None else None
    nu = 5.0
    z = stats.norm.ppf(alpha)
    for j, t in enumerate(idx):
        w_prev = wmat[t - 1]
        loss[j] = -float(np.expm1(rmat[t]) @ w_prev)
        hist = rmat[max(0, t - window) : t]
        if method == "historical":
            pl = -(np.expm1(hist) @ w_prev)
            v = np.quantile(pl, alpha)
            var[j] = v
            tail = pl[pl >= v]
            es[j] = tail.mean() if len(tail) else v
            sampler[:, j] = pl[rng.integers(0, len(pl), size=n_sims)]
            continue
        cov = path[t - 1] if path is not None else np.cov(hist, rowvar=False, ddof=1)
        sigma = float(np.sqrt(w_prev @ cov @ w_prev))
        if method.startswith("normal_"):
            var[j] = z * sigma
            es[j] = sigma * stats.norm.pdf(z) / (1 - alpha)
            sampler[:, j] = -rng.standard_normal(n_sims) * sigma
        elif method.startswith("t_"):
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


def _test_row(f: Forecasts, alpha: float) -> dict[str, object]:
    c = coverage.coverage_tests(f.loss, f.var, alpha)
    z1 = coverage.acerbi_szekely_z1(f.loss, f.var, f.es)
    z2 = coverage.acerbi_szekely_z2(f.loss, f.var, f.es, alpha)
    p1, p2 = coverage.simulate_z_pvalues(f.sampler, f.var, f.es, alpha, z1, z2)
    return {
        "oos_start": f.dates[0].date(),
        "oos_end": f.dates[-1].date(),
        **c.__dict__,
        "z1": z1,
        "z1_p": p1,
        "z2": z2,
        "z2_p": p2,
        "fz0": float(coverage.fz0_score(f.loss, f.var, f.es, alpha).mean()),
        "mean_var_usd": float(f.var.mean()),
        "mean_es_usd": float(f.es.mean()),
    }


def select_model(
    scores: dict[str, np.ndarray], exceptions: dict[str, int], candidates: tuple[str, ...]
) -> pd.DataFrame:
    """Rank models by mean selection-window score; DM test of each against the best."""
    eligible = [m for m in scores if m in candidates]
    best = min(eligible, key=lambda m: float(scores[m].mean()))
    rows = []
    for m, s in scores.items():
        stat, p = (float("nan"), float("nan"))
        if m != best:
            stat, p = coverage.diebold_mariano(s - scores[best])
        rows.append(
            {
                "method": m,
                "optimizer_compatible": m in candidates,
                "sel_fz0": float(s.mean()),
                "sel_exceptions": exceptions[m],
                "sel_n": len(s),
                "dm_stat_vs_selected": stat,
                "dm_p_vs_selected": p,
                "selected": m == best,
            }
        )
    return pd.DataFrame(rows).sort_values("sel_fz0").reset_index(drop=True)


@dataclass(frozen=True)
class BacktestRun:
    """Evaluation results (2015 onward) and the selection table (2012-2014)."""

    results: pd.DataFrame
    selection: pd.DataFrame


def run_var_backtest(
    paths: config.Paths,
    basis: str = "net",
    methods: tuple[str, ...] = METHODS,
    confidences: tuple[float, ...] = (0.95, 0.99),
    selection_alpha: float = 0.99,
    oos_start: pd.Timestamp = OOS_START,
) -> BacktestRun:
    """Select on 2012-2014 and test from ``oos_start``; both tables stored in DuckDB."""
    con = db.connect(paths)
    try:
        returns = fx_returns(con)
        weights = _exposure_path(con, basis)
        r = returns.dropna()
        cp = cov_paths(r, {_COV_KEY[m] for m in methods if m in _COV_KEY})
        rows: list[dict[str, object]] = []
        sel_scores: dict[str, np.ndarray] = {}
        sel_exc: dict[str, int] = {}
        oos_scores: dict[str, float] = {}
        for method in methods:
            for alpha in confidences:
                f = forecast_series(r, weights, method, alpha, SELECTION_START, paths=cp)
                in_sel = f.dates < oos_start
                oos = f.subset(~in_sel)
                row = {"basis": basis, "method": method, "confidence": alpha}
                row |= _test_row(oos, alpha)
                rows.append(row)
                if abs(alpha - selection_alpha) < 1e-9:
                    sel = f.subset(in_sel)
                    sel_scores[method] = coverage.fz0_score(sel.loss, sel.var, sel.es, alpha)
                    sel_exc[method] = int((sel.loss > sel.var).sum())
                    oos_scores[method] = float(row["fz0"])  # type: ignore[arg-type]
                log.info(
                    "%s @%.2f: %s/%s exceptions (expected %.1f), kupiec p=%.3f, z2 p=%.3f",
                    method,
                    alpha,
                    row["n_exceptions"],
                    row["n_obs"],
                    row["expected_exceptions"],
                    row["kupiec_p"],
                    row["z2_p"],
                )
        out = coverage.summarise(pd.DataFrame(rows))
        selection = select_model(sel_scores, sel_exc, OPTIMIZER_METHODS)
        selection["oos_fz0"] = selection["method"].map(oos_scores)
        selection["confidence"] = selection_alpha
        selection["garch_fits"] = cp.garch_fits
        selection["garch_not_converged"] = cp.garch_failed
        for name, frame in (("var_backtest_results", out), ("var_model_selection", selection)):
            con.register("bt_df", frame)
            con.execute(f"CREATE OR REPLACE TABLE {name} AS SELECT * FROM bt_df")
            con.unregister("bt_df")
    finally:
        con.close()
    write_backtest_table(paths, out, selection)
    return BacktestRun(out, selection)


def write_backtest_table(paths: config.Paths, out: pd.DataFrame, selection: pd.DataFrame) -> None:
    """Dump the selection and verdict tables to reports/var_backtest.md."""
    cols = [
        "basis",
        "method",
        "confidence",
        "oos_start",
        "oos_end",
        "n_obs",
        "n_exceptions",
        "expected_exceptions",
        "n_consecutive",
        "kupiec_p",
        "christoffersen_p",
        "conditional_p",
        "traffic_light",
        "z1",
        "z1_p",
        "z2",
        "z2_p",
        "fz0",
        "verdict",
    ]
    sel_cols = [
        "method",
        "optimizer_compatible",
        "sel_n",
        "sel_exceptions",
        "sel_fz0",
        "dm_stat_vs_selected",
        "dm_p_vs_selected",
        "selected",
        "oos_fz0",
    ]
    body = df_to_markdown(out[cols].round(3), readable=True)
    sel_body = df_to_markdown(
        selection[sel_cols],
        decimals={"sel_fz0": 4, "oos_fz0": 4, "dm_stat_vs_selected": 2, "dm_p_vs_selected": 2},
        readable=True,
    )
    g = selection.iloc[0]
    sel_note = (
        f"One-day horizon at {g['confidence']:.0%}, 2012-01 to 2014-12, scored with the FZ0 "
        "joint VaR/ES loss (lower is better). The selected model has the lowest mean score "
        "among the models the optimizer can use; the Diebold-Mariano p-value says whether "
        "another model's score is distinguishable from it. GARCH: "
        f"{int(g['garch_fits'])} univariate fits, {int(g['garch_not_converged'])} did not "
        "converge (those keep the previous month's parameters)."
    )
    note = (
        "One-day horizon, daily, exposure held at the previous close. Back-to-back counts "
        "exceptions on the day after another exception. Z1/Z2 are in losses: "
        "positive means realised tail losses exceeded the forecast ES. Verdict is PASS when "
        "Kupiec, Christoffersen, conditional coverage and Z2 all have p >= 0.05."
    )
    write_markdown(
        paths.reports_dir / "var_backtest.md",
        "VaR / ES model selection and coverage backtest",
        [
            ("Model selection, 2012-2014", sel_body + "\n\n" + sel_note),
            ("Coverage tests, 2015 onward", body),
            ("Reading the table", note),
        ],
    )
