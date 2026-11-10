# ADR-0002: DuckDB as the store; all SQL in `sql/*.sql`, loaded by name

**Status:** accepted, 2026-11-05

## Context

Exposure aggregation is set-based work (running sums, as-of joins, pivots) that reads
more clearly in SQL than in pandas, and a treasury team's analysts are more likely to
read SQL than Python. The SQL should therefore live in files a reader can open on their
own, not in strings buried in Python, and run on an embedded engine with no server.

## Decision

* One DuckDB file, `data/fxrisk.duckdb`, **rebuilt from the cache on every run** and never
  committed. The cache CSVs are the source of truth; the database is a derived artefact.
* Every statement lives in `sql/NNN_name.sql`, executed in numeric order by
  `fx_treasury_risk.db.build_database`. Files are `string.Template` documents: the only
  substitution is `${cache_glob}`; a literal `$` is written `$$`. `str.format` was rejected
  because DuckDB struct literals use braces.
* Python registers at most one DataFrame per file (`catalog_df` for the series registry)
  and otherwise only runs `SELECT ... FROM <view>` reads; the quality module's few
  diagnostic queries are the one exception and are kept short.
* Long ("tidy") tables are the canonical shape; wide matrices are views built with
  conditional aggregation so that the pivot logic is visible.
* SQL style: CTEs over subqueries, one concept per CTE, comments on every non-obvious
  construct (`QUALIFY`, `IGNORE NULLS`, `read_csv(filename = true)`, `ASOF JOIN` later).

## Consequences

* The database can be opened with any DuckDB client to inspect intermediate views.
* Rebuilding from CSV costs about a second; acceptable for a daily process.
