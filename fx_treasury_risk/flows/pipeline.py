"""``fxrisk flows``: generate the synthetic flows and persist them as Parquet."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import duckdb
import pandas as pd

from fx_treasury_risk import config
from fx_treasury_risk.data.cache import SeriesCache
from fx_treasury_risk.flows import calibration
from fx_treasury_risk.flows.config import DEFAULT_PATH, FlowConfig, load_flow_config
from fx_treasury_risk.flows.generator import generate

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class FlowsResult:
    """Where the flows went and a few headline numbers."""

    path: Path
    n_rows: int
    first_date: str
    last_date: str
    summary: pd.DataFrame  # mean daily authorized volume per (entity, ccy)


def flows_path(paths: config.Paths) -> Path:
    """Location of the generated flows file."""
    return paths.data_dir / "flows.parquet"


def run_flows(paths: config.Paths, cfg_path: Path = DEFAULT_PATH) -> FlowsResult:
    """Calibrate seasonality from the cache, generate, write Parquet via DuckDB."""
    cfg: FlowConfig = load_flow_config(cfg_path)
    cache = SeriesCache(paths.cache_dir)
    profiles = calibration.all_profiles(cache)
    log.info(
        "annual seasonality (Jan..Dec): %s",
        {k: [round(x, 3) for x in v] for k, v in profiles.items()},
    )
    flows = generate(cfg, profiles)

    out = flows_path(paths)
    out.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.register("flows_df", flows)
    con.execute(
        "COPY (SELECT * FROM flows_df ORDER BY date, entity, ccy, flow_type) "
        f"TO '{out.as_posix()}' (FORMAT PARQUET)"
    )
    con.close()

    auth = flows[flows["flow_type"] == "auth"]
    summary = (
        auth.groupby(["entity", "ccy"])["amount"].mean().rename("mean_daily_auth").reset_index()
    )
    log.info("wrote %d flow rows to %s", len(flows), out)
    return FlowsResult(
        path=out,
        n_rows=len(flows),
        first_date=flows["date"].min().strftime("%Y-%m-%d"),
        last_date=flows["date"].max().strftime("%Y-%m-%d"),
        summary=summary,
    )
