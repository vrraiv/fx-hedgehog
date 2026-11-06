"""``fxrisk`` command line: one sub-command per pipeline stage.

Stages run in this order and each one reads only what earlier stages wrote::

    fetch -> quality -> flows -> exposure -> forecast -> risk -> hedge -> backtest -> report

``fxrisk all`` runs the stages that exist so far. Exit codes: 0 success, 1 quality failure,
2 stage not yet implemented, 3 unexpected error.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Annotated

import typer
from rich.console import Console
from rich.logging import RichHandler
from rich.table import Table

from fx_treasury_risk import __version__, config
from fx_treasury_risk.data.cache import SeriesCache
from fx_treasury_risk.data.fetch import fetch_all
from fx_treasury_risk.data.registry import Source

app = typer.Typer(
    name="fxrisk",
    help="FX treasury risk pipeline: data, exposure, risk, hedging, reporting.",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()

EXIT_QUALITY_FAILED = 1
EXIT_NOT_IMPLEMENTED = 2
EXIT_ERROR = 3


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(console=console, show_path=False, rich_tracebacks=True)],
    )


@app.callback()
def main(
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Debug logging.")] = False,
) -> None:
    """Configure logging for every sub-command."""
    _setup_logging(verbose)


@app.command()
def version() -> None:
    """Print the package version."""
    console.print(f"fxrisk {__version__}")


@app.command()
def fetch(
    source: Annotated[
        list[str] | None,
        typer.Option(
            "--source",
            "-s",
            help="Restrict to a source (fred, boc, ecb, bis, statcan). Repeatable.",
        ),
    ] = None,
    refresh: Annotated[
        bool, typer.Option("--refresh", help="Re-download series already in the cache.")
    ] = False,
) -> None:
    """Download every registered series into data/cache (cache-first; see --refresh)."""
    paths = config.Paths.from_env()
    cache = SeriesCache(paths.cache_dir)
    sources: Sequence[Source] | None = [s for s in source] if source else None  # type: ignore[misc]
    outcomes = fetch_all(cache, refresh=refresh, sources=sources)

    table = Table(title="fetch summary", show_lines=False)
    for col in ("series", "status", "n_obs", "last_date", "error"):
        table.add_column(col)
    for o in outcomes:
        style = {"fetched": "green", "cached": "dim", "failed": "red", "missing": "red"}[o.status]
        table.add_row(
            o.key, f"[{style}]{o.status}[/{style}]", str(o.n_obs), o.last_date, o.error[:60]
        )
    console.print(table)

    bad = [o for o in outcomes if o.status in ("failed", "missing")]
    if bad:
        console.print(f"[red]{len(bad)} series could not be fetched and are not cached.[/red]")
        raise typer.Exit(code=EXIT_ERROR)


@app.command()
def quality(
    strict: Annotated[bool, typer.Option("--strict", help="Treat warnings as failures.")] = False,
) -> None:
    """Run data-quality checks; writes reports/quality_report.md and reports/alerts.md."""
    from fx_treasury_risk.data.quality import run_quality

    paths = config.Paths.from_env()
    report = run_quality(paths)
    console.print(report.to_rich_table())
    console.print(f"report: {paths.reports_dir / 'quality_report.md'}")
    if report.failed or (strict and report.warned):
        console.print("[red]quality checks FAILED - see reports/alerts.md[/red]")
        raise typer.Exit(code=EXIT_QUALITY_FAILED)
    console.print("[green]quality checks passed[/green]")


def _not_yet(stage: str, milestone: int) -> None:
    console.print(
        f"[yellow]`fxrisk {stage}` is planned for milestone {milestone}; "
        "nothing to do yet.[/yellow]"
    )
    raise typer.Exit(code=EXIT_NOT_IMPLEMENTED)


@app.command()
def flows() -> None:
    """Generate the synthetic merchant flows (deterministic) into data/flows.parquet."""
    from fx_treasury_risk.flows.pipeline import run_flows

    paths = config.Paths.from_env()
    result = run_flows(paths)
    table = Table(title=f"flows: {result.n_rows:,} rows, {result.first_date} to {result.last_date}")
    table.add_column("entity")
    table.add_column("ccy")
    table.add_column("mean daily authorized (local ccy)", justify="right")
    for r in result.summary.itertuples(index=False):
        table.add_row(str(r.entity), str(r.ccy), f"{r.mean_daily_auth:,.0f}")
    console.print(table)
    console.print(f"written: {result.path}")


@app.command()
def exposure() -> None:
    """Aggregate net exposure by entity, currency and date in DuckDB (SQL in sql/060-090)."""
    from fx_treasury_risk.exposure.build import build_exposure, latest_waterfall

    paths = config.Paths.from_env()
    con = build_exposure(paths)
    try:
        wf = latest_waterfall(con)
    finally:
        con.close()
    table = Table(title="group exposure waterfall on the last date (USD millions)")
    for col in ("ccy", "gross", "net", "hedge", "net of hedges"):
        table.add_column(col, justify="left" if col == "ccy" else "right")
    for r in wf.itertuples(index=False):
        table.add_row(
            str(r.ccy),
            f"{r.gross_usd_m:,.1f}",
            f"{r.net_usd_m:,.1f}",
            f"{r.hedge_usd_m:,.1f}",
            f"{r.net_of_hedges_usd_m:,.1f}",
        )
    console.print(table)


@app.command()
def risk(
    mc_paths: Annotated[int, typer.Option(help="Monte Carlo paths per horizon.")] = 20_000,
) -> None:
    """Compute VaR and Expected Shortfall (all methods) and stress results, latest date."""
    from fx_treasury_risk.risk.pipeline import headline_table, run_risk

    paths = config.Paths.from_env()
    run = run_risk(paths, mc_paths=mc_paths)
    console.print(f"as of {run.as_of.date()}; exposures (USD m):")
    console.print((run.exposures / 1e6).round(1).to_string())
    for basis in ("net", "net_of_hedges"):
        console.rule(f"VaR / ES, basis = {basis} (USD m)")
        console.print(headline_table(run.risk, basis).to_string())
    console.rule("stress, basis = net (USD m)")
    st = run.stress[run.stress["basis"] == "net"][
        ["scenario", "kind", "propagated", "largest_move", "pnl_usd"]
    ].copy()
    st["pnl_usd"] = (st["pnl_usd"] / 1e6).round(2)
    console.print(st.to_string(index=False))


@app.command()
def forecast() -> None:
    """Forecast net exposure 1-63 days ahead with prediction intervals (milestone 3)."""
    _not_yet("forecast", 3)


@app.command()
def hedge() -> None:
    """Price forwards and optimize hedge ratios against an ES budget (milestone 3)."""
    _not_yet("hedge", 3)


@app.command()
def backtest(
    basis: Annotated[str, typer.Option(help="Exposure basis: net or net_of_hedges.")] = "net",
) -> None:
    """VaR/ES coverage backtests out of sample from 2015 (hedge-policy backtest: milestone 3)."""
    from fx_treasury_risk.backtest.var_backtest import run_var_backtest

    paths = config.Paths.from_env()
    out = run_var_backtest(paths, basis=basis)
    cols = [
        "method",
        "confidence",
        "n_obs",
        "n_exceptions",
        "expected_exceptions",
        "kupiec_p",
        "christoffersen_p",
        "conditional_p",
        "traffic_light",
        "z1",
        "z2",
        "z2_p",
        "verdict",
    ]
    console.print(out[cols].round(3).to_string(index=False))


@app.command()
def report() -> None:
    """Render the decision report (milestone 4)."""
    _not_yet("report", 4)


@app.command(name="all")
def run_all() -> None:
    """Run every implemented stage in order."""
    fetch(source=None, refresh=False)
    quality(strict=False)
    flows()
    exposure()
    risk()
    backtest()


if __name__ == "__main__":  # pragma: no cover
    app()
