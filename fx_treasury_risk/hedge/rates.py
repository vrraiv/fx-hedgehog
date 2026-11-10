"""Read ``rates_short`` from DuckDB and build the forward table for a date."""

from __future__ import annotations

import duckdb
import pandas as pd

from fx_treasury_risk import config
from fx_treasury_risk.hedge.forwards import forward_table


def rates_on(con: duckdb.DuckDBPyConnection, as_of: pd.Timestamp) -> pd.DataFrame:
    """``rates_short`` rows for one date, indexed by currency."""
    df = con.execute(
        "SELECT * FROM rates_short WHERE obs_date = ? ORDER BY ccy", [as_of.date()]
    ).df()
    if df.empty:
        raise ValueError(f"no short rates on {as_of.date()}")
    return df.set_index("ccy")


def rates_wide(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Rate percent by date (rows) and currency (columns), for the policy backtest."""
    df = con.execute("SELECT obs_date, ccy, rate_pct FROM rates_short ORDER BY obs_date, ccy").df()
    wide = df.pivot(index="obs_date", columns="ccy", values="rate_pct")
    wide.index = pd.DatetimeIndex(wide.index)
    wide.columns.name = None
    return wide


def spots_on(con: duckdb.DuckDBPyConnection, as_of: pd.Timestamp) -> pd.Series:
    """``usd_per_fcy`` by currency on one date (forward-filled master)."""
    df = con.execute(
        "SELECT ccy, usd_per_fcy FROM fx_usd_master_filled WHERE obs_date = ? ORDER BY ccy",
        [as_of.date()],
    ).df()
    return df.set_index("ccy")["usd_per_fcy"].astype(float)


def forward_table_on(
    con: duckdb.DuckDBPyConnection,
    as_of: pd.Timestamp,
    days: int,
    ccys: tuple[str, ...] = config.EXPOSURE_CCYS,
) -> pd.DataFrame:
    """Forward quotes for the exposure currencies on ``as_of``."""
    spots = spots_on(con, as_of)
    rates = rates_on(con, as_of)
    return forward_table(spots[list(ccys)], rates, days)
