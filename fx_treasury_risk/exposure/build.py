"""``fxrisk exposure``: load flows into DuckDB and build the exposure tables and views."""

from __future__ import annotations

import logging
from pathlib import Path

import duckdb
import pandas as pd

from fx_treasury_risk import config, db
from fx_treasury_risk.flows.pipeline import flows_path

log = logging.getLogger(__name__)

SQL_STAGES = (
    "060_flows",
    "070_exposure_daily",
    "075_hedges",
    "080_exposure_waterfall",
    "090_exposure_group",
)


def build_exposure(
    paths: config.Paths, flows_file: Path | None = None
) -> duckdb.DuckDBPyConnection:
    """Run the exposure SQL stages; the FX master must already exist (``fxrisk quality``).

    Returns an open connection. Raises if any flow type is unmapped, because an unmapped
    type would silently vanish from exposure.
    """
    flows_file = flows_file or flows_path(paths)
    if not flows_file.exists():
        raise FileNotFoundError(f"{flows_file} not found; run `fxrisk flows` first")
    con = db.connect(paths)
    if not _table_exists(con, "fx_usd_master"):
        log.info("fx_usd_master missing; rebuilding the data layer first")
        con.close()
        con = db.build_database(paths)
    db.execute_file(con, "060_flows", flows_path=flows_file.as_posix())
    unmapped = con.execute("SELECT flow_type FROM unmapped_flow_types").fetchall()
    if unmapped:
        raise ValueError(f"flow types without a flow_type_map entry: {[u[0] for u in unmapped]}")
    for stage in SQL_STAGES[1:]:
        db.execute_file(con, stage)
    n = con.execute("SELECT count(*) FROM exposure_daily").fetchall()[0][0]
    log.info("exposure_daily built: %d rows", n)
    return con


def _table_exists(con: duckdb.DuckDBPyConnection, name: str) -> bool:
    rows = con.execute(
        "SELECT 1 FROM information_schema.tables WHERE table_name = ?", [name]
    ).fetchall()
    return bool(rows)


def latest_waterfall(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Group waterfall by currency on the last exposure date, in USD millions."""
    df = con.execute(
        """
        SELECT ccy, gross_usd / 1e6 AS gross_usd_m, net_usd / 1e6 AS net_usd_m,
               hedge_usd / 1e6 AS hedge_usd_m, net_of_hedges_usd / 1e6 AS net_of_hedges_usd_m
        FROM exposure_waterfall_by_ccy
        WHERE exposure_date = (SELECT max(exposure_date) FROM exposure_waterfall_by_ccy)
        ORDER BY abs(net_usd) DESC
        """
    ).df()
    return df


def entity_breakdown(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Component breakdown per (entity, ccy) on the last date, in USD millions."""
    return con.execute(
        """
        SELECT entity, ccy,
               in_flight_usd / 1e6 AS in_flight_m, balance_usd / 1e6 AS balance_m,
               payable_usd / 1e6 AS payable_m, intercompany_usd / 1e6 AS intercompany_m,
               net_usd / 1e6 AS net_m
        FROM exposure_daily_usd
        WHERE exposure_date = (SELECT max(exposure_date) FROM exposure_daily_usd)
        ORDER BY entity, ccy
        """
    ).df()
