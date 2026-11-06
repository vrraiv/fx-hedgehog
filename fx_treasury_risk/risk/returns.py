"""Daily log returns of the USD-per-FCY master table."""

from __future__ import annotations

import duckdb
import numpy as np
import pandas as pd

from fx_treasury_risk import config


def fx_returns(
    con: duckdb.DuckDBPyConnection, ccys: tuple[str, ...] = config.EXPOSURE_CCYS
) -> pd.DataFrame:
    """Wide frame of daily log returns, index = NY business day, one column per currency.

    Returns over a forward-filled cell are set to NaN (we do not want a zero return
    manufactured by the fill); downstream estimators drop rows with any NaN.
    """
    df = con.execute(
        """
        SELECT obs_date, ccy, usd_per_fcy, is_filled
        FROM fx_usd_master_filled
        ORDER BY ccy, obs_date
        """
    ).df()
    px = df.pivot(index="obs_date", columns="ccy", values="usd_per_fcy")
    filled = df.pivot(index="obs_date", columns="ccy", values="is_filled").astype(bool)
    logpx = pd.DataFrame(np.log(px.to_numpy(dtype=float)), index=px.index, columns=px.columns)
    r = logpx.diff()
    r = r.mask(filled | filled.shift(1, fill_value=False))
    r = r.iloc[1:]
    r.index = pd.DatetimeIndex(r.index, name="obs_date")
    r.columns.name = None
    out: pd.DataFrame = r[list(ccys)]
    return out


def horizon_returns(r: pd.DataFrame, horizon: int) -> pd.DataFrame:
    """Overlapping ``horizon``-day log returns (rolling sums); first rows are dropped."""
    if horizon == 1:
        return r.dropna()
    return r.rolling(horizon).sum().dropna()
