# ADR-0001: Python 3.12, uv, pandas (not polars), typer

**Status:** accepted, 2026-11-05

## Context

The stack is fixed by the brief (Python 3.12, uv, ruff, pytest, mypy, DuckDB). Two
choices were left open: the in-memory dataframe library and the CLI framework.

## Decision

* **pandas** for all in-memory work. Polars is faster, but every statistical library this
  project will use (statsmodels for SARIMA/ETS, scipy, matplotlib) takes pandas objects
  natively, DuckDB's `.df()` returns pandas, and the author's existing fluency is in
  pandas/R. Nothing in the pipeline is large enough for polars' speed to matter: the
  biggest frame is 4,200 days x 10 currencies.
* **typer** for the CLI. It gives typed arguments, `--help` from docstrings and a
  `CliRunner` for tests with no boilerplate; `rich` comes with it for tables.
* **pandas-stubs** and mypy `strict = true` on the package. pandas typing is imperfect;
  where the stubs are wrong the code casts explicitly rather than `# type: ignore`.

## Consequences

* One dataframe library everywhere; no polars/pandas conversions.
* Heavy numerical work (Monte Carlo, bootstrap) uses numpy arrays directly.
