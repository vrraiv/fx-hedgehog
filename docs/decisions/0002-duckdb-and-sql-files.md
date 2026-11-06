# ADR-0002: DuckDB as the store; all SQL in `sql/*.sql`, loaded by name

**Status:** accepted, 2026-11-05

## Context

The brief requires DuckDB for storage and aggregation, with no SQL strings buried in
Python. The author wants to learn idiomatic SQL from the repository.

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
