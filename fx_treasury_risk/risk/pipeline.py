"""``fxrisk risk``: VaR/ES comparison table and stress table on the latest exposure."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import duckdb
import pandas as pd

from fx_treasury_risk import config, db
from fx_treasury_risk.report.tables import df_to_markdown, write_markdown
from fx_treasury_risk.risk.returns import fx_returns
from fx_treasury_risk.risk.stress import stress_table
from fx_treasury_risk.risk.var_es import risk_table

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class RiskRun:
    """Outputs of one risk run."""

    as_of: pd.Timestamp
    exposures: pd.DataFrame  # ccy x {net_usd, net_of_hedges_usd}
    risk: pd.DataFrame  # tidy VaR/ES table with a `basis` column
    stress: pd.DataFrame  # tidy stress table with a `basis` column


def load_exposures(
    con: duckdb.DuckDBPyConnection, as_of: pd.Timestamp | None = None
) -> pd.DataFrame:
    """Group net exposures by currency (USD) on ``as_of`` (default: last FX date)."""
    if as_of is None:
        as_of = pd.Timestamp(
            con.execute("SELECT max(obs_date) FROM exposure_group_fx").fetchall()[0][0]
        )
    df = con.execute(
        "SELECT ccy, net_usd, net_of_hedges_usd FROM exposure_group_fx "
        "WHERE obs_date = ? ORDER BY ccy",
        [as_of.date()],
    ).df()
    return df.set_index("ccy")


def load_prices(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Wide usd_per_fcy matrix on the FX calendar (forward-filled)."""
    df = con.execute("SELECT obs_date, ccy, usd_per_fcy FROM fx_usd_master_filled").df()
    px = df.pivot(index="obs_date", columns="ccy", values="usd_per_fcy")
    px.index = pd.DatetimeIndex(px.index)
    px.columns.name = None
    return px


def run_risk(
    paths: config.Paths, as_of: pd.Timestamp | None = None, mc_paths: int = 20_000
) -> RiskRun:
    """Compute the risk and stress tables and store them in DuckDB."""
    con = db.connect(paths)
    try:
        exposures = load_exposures(con, as_of)
        as_of_ts = as_of or pd.Timestamp(
            con.execute("SELECT max(obs_date) FROM exposure_group_fx").fetchall()[0][0]
        )
        returns = fx_returns(con)
        returns = returns[returns.index <= as_of_ts]
        prices = load_prices(con)
        prices = prices[prices.index <= as_of_ts]
        ccys = [c for c in config.EXPOSURE_CCYS if c in exposures.index]

        risk_frames, stress_frames = [], []
        for basis, col in (("net", "net_usd"), ("net_of_hedges", "net_of_hedges_usd")):
            w = exposures.loc[ccys, col].astype(float)
            rt = risk_table(w, returns, horizons=config.RISK_HORIZONS, mc_paths=mc_paths)
            rt.insert(0, "basis", basis)
            risk_frames.append(rt)
            st = stress_table(w, prices, returns)
            st.insert(0, "basis", basis)
            stress_frames.append(st)
        risk = pd.concat(risk_frames, ignore_index=True)
        stress = pd.concat(stress_frames, ignore_index=True)
        risk.insert(0, "as_of", as_of_ts.date())
        stress.insert(0, "as_of", as_of_ts.date())

        con.register("risk_df", risk)
        con.execute("CREATE OR REPLACE TABLE risk_results AS SELECT * FROM risk_df")
        con.register("stress_df", stress)
        con.execute("CREATE OR REPLACE TABLE stress_results AS SELECT * FROM stress_df")
        con.unregister("risk_df")
        con.unregister("stress_df")
        log.info("risk_results: %d rows; stress_results: %d rows", len(risk), len(stress))
    finally:
        con.close()
    run = RiskRun(as_of=as_of_ts, exposures=exposures, risk=risk, stress=stress)
    write_risk_tables(paths, run)
    return run


def write_risk_tables(paths: config.Paths, run: RiskRun) -> Path:
    """Dump the exposures, VaR/ES comparison and stress tables to reports/risk_tables.md."""
    expo = (
        (run.exposures / 1e6)
        .round(2)
        .rename(columns={"net_usd": "net (USD m)", "net_of_hedges_usd": "net of hedges (USD m)"})
    )
    sections = [("Exposures by currency", df_to_markdown(expo, index=True))]
    for basis in ("net", "net_of_hedges"):
        tbl = headline_table(run.risk, basis)
        labels = cast(list[tuple[str, int, float]], tbl.columns.to_list())
        tbl.columns = [f"{m[:-4]} {h}d {c:.0%}" for m, h, c in labels]
        sections.append((f"VaR / ES, basis = {basis} (USD m)", df_to_markdown(tbl, index=True)))
    st = run.stress[run.stress["basis"] == "net"][
        ["scenario", "kind", "window", "propagated", "largest_move", "pnl_usd", "note"]
    ].copy()
    st["pnl_usd"] = (st["pnl_usd"] / 1e6).round(2)
    st = st.rename(columns={"pnl_usd": "P&L (USD m)"})
    sections.append(("Stress, basis = net", df_to_markdown(st)))
    out = paths.reports_dir / "risk_tables.md"
    write_markdown(out, f"Risk tables as of {run.as_of.date()}", sections)
    return out


def headline_table(risk: pd.DataFrame, basis: str = "net") -> pd.DataFrame:
    """Compact VaR/ES comparison: rows = method/cov, columns = horizon x confidence, USD m."""
    sub = risk[risk["basis"] == basis].copy()
    sub["label"] = sub["method"] + " / " + sub["cov_method"]
    out = sub.pivot_table(
        index="label", columns=["horizon_days", "confidence"], values=["var_usd", "es_usd"]
    )
    return (out / 1e6).round(2)
