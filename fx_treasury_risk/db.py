"""DuckDB connection and SQL file loader.

All SQL lives in ``sql/*.sql`` and is loaded by file name; Python never embeds SQL strings
beyond trivial ``SELECT * FROM <view>`` reads. Files may contain ``${name}`` placeholders
that are substituted with :func:`string.Template` (no brace escaping headaches, and an
unknown placeholder raises instead of silently passing through).
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import asdict
from pathlib import Path
from string import Template

import duckdb
import pandas as pd

from fx_treasury_risk import config
from fx_treasury_risk.data.cache import SeriesCache
from fx_treasury_risk.data.registry import ALL_SERIES

log = logging.getLogger(__name__)


def load_sql(
    name: str, params: Mapping[str, str] | None = None, *, sql_dir: Path = config.SQL_DIR
) -> str:
    """Read ``sql/<name>.sql`` and substitute ``${placeholders}`` from ``params``."""
    path = sql_dir / f"{name}.sql"
    text = path.read_text(encoding="utf-8")
    return Template(text).substitute(**params) if params else text


def execute_file(con: duckdb.DuckDBPyConnection, name: str, **params: str) -> None:
    """Execute every statement in a SQL file."""
    log.debug("executing sql/%s.sql", name)
    con.execute(load_sql(name, params))


def connect(paths: config.Paths, *, read_only: bool = False) -> duckdb.DuckDBPyConnection:
    """Open (or create) the project DuckDB database."""
    paths.data_dir.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(paths.db_path), read_only=read_only)


def catalog_frame() -> pd.DataFrame:
    """The series registry as a DataFrame (the ``catalog_df`` the SQL layer expects)."""
    df = pd.DataFrame([asdict(s) for s in ALL_SERIES])
    return df[
        [
            "source",
            "series_id",
            "category",
            "ccy",
            "quote",
            "frequency",
            "vintage",
            "tenor_months",
            "unit",
            "description",
        ]
    ]


def build_database(paths: config.Paths) -> duckdb.DuckDBPyConnection:
    """Rebuild the data layer from the cache: raw table, catalogue, FX views and master.

    Every statement is ``CREATE OR REPLACE``, so the call is idempotent and leaves tables
    written by later stages (flows, exposure, risk) untouched. Returns an open connection.
    """
    con = connect(paths)
    cache_glob = (paths.cache_dir / "*" / "*.csv").as_posix()
    execute_file(con, "010_raw_observations", cache_glob=cache_glob)
    check_raw_counts(con, SeriesCache(paths.cache_dir))
    con.register("catalog_df", catalog_frame())
    execute_file(con, "020_series_catalog")
    con.unregister("catalog_df")
    execute_file(con, "030_fx_usd_per_fcy")
    execute_file(con, "040_fx_reconciliation")
    execute_file(con, "050_fx_usd_master")
    execute_file(con, "100_rates_short")
    n_raw = con.execute("SELECT count(*) FROM raw_observations").fetchall()[0][0]
    log.info("database rebuilt at %s (%s raw observations)", paths.db_path, n_raw)
    return con


def check_raw_counts(con: duckdb.DuckDBPyConnection, cache: SeriesCache) -> None:
    """Fail if any cached series loaded a different number of rows than its manifest says.

    One glob reads every cached CSV, and a file the reader cannot parse the same way as the
    others (for instance, different line endings) is dropped silently rather than raising.
    The manifest records each series' row count at write time, so it is the reference.
    """
    loaded = {
        (str(s), str(i)): int(n)
        for s, i, n in con.execute(
            "SELECT source, series_id, count(*) FROM raw_observations GROUP BY ALL"
        ).fetchall()
    }
    bad = []
    for e in cache.manifest().values():
        n = loaded.get((e.source, e.series_id), 0)
        if n != e.n_obs:
            bad.append(f"{e.source}:{e.series_id} (manifest {e.n_obs}, loaded {n})")
    if bad:
        raise RuntimeError("cached series did not load completely: " + "; ".join(bad))


def table_exists(con: duckdb.DuckDBPyConnection, name: str) -> bool:
    """True if a table or view called ``name`` exists (stages that may not have run yet)."""
    return bool(
        con.execute(
            "SELECT 1 FROM information_schema.tables WHERE table_name = ?", [name]
        ).fetchall()
    )


def read_table(con: duckdb.DuckDBPyConnection, name: str) -> pd.DataFrame:
    """Fetch a whole table or view as a DataFrame."""
    df: pd.DataFrame = con.table(name).df()
    return df
