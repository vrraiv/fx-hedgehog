"""Data-quality checks behind ``fxrisk quality``.

Every check returns a :class:`CheckResult` with a status of PASS, WARN or FAIL. The run
writes two files:

* ``reports/quality_report.md`` - every check with its evidence table;
* ``reports/alerts.md`` - only WARN and FAIL items, so the scheduled job and a reader
  can see at a glance whether the data is fit for the day's run.

Thresholds are deliberately calibrated on observed data (ADR-0005) rather than guessed:
the point of the reconciliation check is to catch unit errors, inverted quotes and broken
feeds, not the few basis points of noise from fixings at different times of day.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Literal

import duckdb
import numpy as np
import pandas as pd
from rich.table import Table

from fx_treasury_risk import config, db
from fx_treasury_risk.data.cache import SeriesCache
from fx_treasury_risk.data.registry import ALL_SERIES, SeriesSpec
from fx_treasury_risk.report.tables import df_to_markdown as _df_to_markdown

log = logging.getLogger(__name__)

Status = Literal["PASS", "WARN", "FAIL"]
_ORDER = {"FAIL": 0, "WARN": 1, "PASS": 2}


@dataclass(frozen=True)
class ReconTolerance:
    """Thresholds (basis points of log difference) for one source against FRED."""

    median_abs_bp: float
    p99_abs_bp: float
    abs_mean_bp: float


#: Calibrated on 2010-2026 data; see docs/decisions/0005-reconciliation-tolerances.md.
RECON_TOLERANCES: dict[str, ReconTolerance] = {
    "boc": ReconTolerance(median_abs_bp=25.0, p99_abs_bp=150.0, abs_mean_bp=10.0),
    "ecb": ReconTolerance(median_abs_bp=60.0, p99_abs_bp=300.0, abs_mean_bp=15.0),
}
#: Fraction of a series' staleness limit beyond which a WARN is raised.
STALE_WARN_FRACTION = 0.75
#: Days since the most recent retrieval before the cache is flagged as aged (WARN only).
CACHE_AGE_WARN_DAYS = 14
#: Share of NULL cells per currency tolerated in the master FX table.
MAX_NULL_SHARE = 0.005
#: Longest tolerated gap (calendar days) between consecutive NY business days.
MAX_CALENDAR_GAP_DAYS = 6
#: Return outliers: |log return| above this many EWMA standard deviations is flagged.
OUTLIER_SIGMA = 6.0
EWMA_LAMBDA = 0.94
#: Plausible range for short rates and policy rates, in percent.
RATE_RANGE = (-2.0, 40.0)


@dataclass
class CheckResult:
    """Outcome of one quality check."""

    name: str
    status: Status
    summary: str
    evidence: pd.DataFrame | None = None

    def to_markdown(self) -> str:
        """Markdown section with the evidence table, if any."""
        lines = [f"### {self.name} - **{self.status}**", "", self.summary, ""]
        if self.evidence is not None and not self.evidence.empty:
            lines += [_df_to_markdown(self.evidence), ""]
        return "\n".join(lines)


@dataclass
class QualityReport:
    """All check results from one run."""

    checks: list[CheckResult] = field(default_factory=list)
    generated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def failed(self) -> list[CheckResult]:
        """Checks with status FAIL."""
        return [c for c in self.checks if c.status == "FAIL"]

    @property
    def warned(self) -> list[CheckResult]:
        """Checks with status WARN."""
        return [c for c in self.checks if c.status == "WARN"]

    @property
    def status(self) -> Status:
        """Worst status across all checks."""
        return "FAIL" if self.failed else ("WARN" if self.warned else "PASS")

    def to_markdown(self) -> str:
        """Full report."""
        head = [
            "# Data quality report",
            "",
            f"Generated {self.generated_at:%Y-%m-%d %H:%M} UTC - overall **{self.status}**",
            "",
            "| check | status | summary |",
            "|---|---|---|",
        ]
        head += [f"| {c.name} | {c.status} | {c.summary} |" for c in self.checks]
        body = [c.to_markdown() for c in self.checks]
        return "\n".join([*head, "", "## Details", "", *body])

    def to_alerts_markdown(self) -> str:
        """Only the WARN/FAIL items (what a scheduled job should surface)."""
        items = sorted(self.failed + self.warned, key=lambda c: _ORDER[c.status])
        lines = ["# Alerts", "", f"Generated {self.generated_at:%Y-%m-%d %H:%M} UTC", ""]
        if not items:
            return "\n".join([*lines, "No alerts: all data-quality checks passed.", ""])
        lines.append(f"{len(self.failed)} FAIL, {len(self.warned)} WARN")
        lines.append("")
        lines += [c.to_markdown() for c in items]
        return "\n".join(lines)

    def to_rich_table(self) -> Table:
        """Console summary."""
        table = Table(title=f"quality checks: {self.status}")
        table.add_column("check")
        table.add_column("status")
        table.add_column("summary")
        colour = {"PASS": "green", "WARN": "yellow", "FAIL": "red"}
        for c in self.checks:
            table.add_row(c.name, f"[{colour[c.status]}]{c.status}[/{colour[c.status]}]", c.summary)
        return table


# ---------------------------------------------------------------------------------------
# individual checks
# ---------------------------------------------------------------------------------------
def check_cache_complete(
    cache: SeriesCache, specs: Sequence[SeriesSpec] = ALL_SERIES
) -> CheckResult:
    """Every registered series must be present in the cache with a manifest entry."""
    missing = [s.key for s in specs if not cache.has(s.source, s.series_id)]
    if missing:
        ev = pd.DataFrame({"missing_series": missing})
        return CheckResult(
            "cache_complete",
            "FAIL",
            f"{len(missing)} of {len(specs)} series missing from cache",
            ev,
        )
    return CheckResult("cache_complete", "PASS", f"all {len(specs)} registered series cached")


def check_schema(cache: SeriesCache, specs: Sequence[SeriesSpec] = ALL_SERIES) -> CheckResult:
    """Each CSV must parse, have unique ascending dates, finite values, positive FX rates."""
    problems: list[dict[str, str]] = []
    for spec in specs:
        path = cache.path(spec.source, spec.series_id)
        if not path.exists():
            continue  # reported by cache_complete
        try:
            df = pd.read_csv(path)
        except Exception as exc:
            problems.append({"series": spec.key, "problem": f"unreadable: {exc}"})
            continue
        if list(df.columns) != ["date", "value"]:
            problems.append({"series": spec.key, "problem": f"columns {list(df.columns)}"})
            continue
        dates = pd.to_datetime(df["date"], errors="coerce")
        vals = pd.to_numeric(df["value"], errors="coerce")
        if dates.isna().any():
            problems.append({"series": spec.key, "problem": "unparseable dates"})
        if dates.duplicated().any():
            problems.append({"series": spec.key, "problem": "duplicate dates"})
        if not dates.is_monotonic_increasing:
            problems.append({"series": spec.key, "problem": "dates not ascending"})
        if not np.isfinite(vals.to_numpy(dtype=float)).all():
            problems.append({"series": spec.key, "problem": "non-finite values"})
        if spec.category in ("fx", "eer", "retail") and (vals <= 0).any():
            problems.append({"series": spec.key, "problem": "non-positive values"})
        if len(df) == 0:
            problems.append({"series": spec.key, "problem": "empty"})
    if problems:
        return CheckResult(
            "schema", "FAIL", f"{len(problems)} schema problems", pd.DataFrame(problems)
        )
    return CheckResult("schema", "PASS", "all cached files well-formed")


def check_staleness(
    cache: SeriesCache, today: date | None = None, specs: Sequence[SeriesSpec] = ALL_SERIES
) -> CheckResult:
    """Last observation must be recent relative to retrieval; retrieval must be recent too.

    Lag between retrieval and the last observation is judged against each series'
    ``stale_after_days`` (FAIL beyond it, WARN beyond half of it). The age of the cache
    itself is only a WARN: CI runs from a committed cache that may be weeks old, and
    that is by design.
    """
    today = today or datetime.now(UTC).date()
    manifest = cache.manifest()
    rows: list[dict[str, object]] = []
    status: Status = "PASS"
    newest_retrieval: pd.Timestamp | None = None
    for spec in specs:
        entry = manifest.get(spec.key)
        if entry is None:
            continue
        retrieved = entry.retrieved_date
        newest_retrieval = (
            retrieved if newest_retrieval is None else max(newest_retrieval, retrieved)
        )
        lag = (retrieved - pd.Timestamp(entry.last_date)).days
        if spec.vintage == "legacy":
            continue  # discontinued by construction
        level: Status = "PASS"
        if lag > spec.stale_after_days:
            level = "FAIL"
        elif lag > STALE_WARN_FRACTION * spec.stale_after_days:
            level = "WARN"
        if level != "PASS":
            rows.append(
                {
                    "series": spec.key,
                    "last_date": entry.last_date,
                    "retrieved": retrieved.date().isoformat(),
                    "lag_days": lag,
                    "limit_days": spec.stale_after_days,
                    "level": level,
                }
            )
            if _ORDER[level] < _ORDER[status]:
                status = level
    summary = f"{len(rows)} series stale or lagging"
    if newest_retrieval is not None:
        age = (pd.Timestamp(today) - newest_retrieval).days
        if age > CACHE_AGE_WARN_DAYS:
            rows.append(
                {
                    "series": "(cache)",
                    "last_date": "",
                    "retrieved": newest_retrieval.date().isoformat(),
                    "lag_days": age,
                    "limit_days": CACHE_AGE_WARN_DAYS,
                    "level": "WARN",
                }
            )
            status = "WARN" if status == "PASS" else status
            summary += f"; cache last refreshed {age} days ago"
    if status == "PASS":
        summary = "all series fresh at retrieval; cache refreshed within the last two weeks"
    return CheckResult("staleness", status, summary, pd.DataFrame(rows) if rows else None)


def check_reconciliation(
    con: duckdb.DuckDBPyConnection, ccys: Sequence[str] = config.EXPOSURE_CCYS
) -> CheckResult:
    """BoC-derived and ECB-derived USD rates must agree with FRED within tolerance."""
    summary = db.read_table(con, "fx_reconciliation_summary")
    if summary.empty:
        return CheckResult("reconciliation", "FAIL", "no overlapping observations to reconcile")
    rows = []
    worst: Status = "PASS"
    seen: set[tuple[str, str]] = set()
    for rec in summary.to_dict("records"):
        ccy, source = str(rec["ccy"]), str(rec["source"])
        seen.add((ccy, source))
        median_bp, p99_bp = float(rec["median_abs_bp"]), float(rec["p99_abs_bp"])
        mean_bp = float(rec["mean_bp"])
        tol = RECON_TOLERANCES[source]
        breaches = []
        if median_bp > tol.median_abs_bp:
            breaches.append(f"median {median_bp:.1f}>{tol.median_abs_bp:g}")
        if p99_bp > tol.p99_abs_bp:
            breaches.append(f"p99 {p99_bp:.1f}>{tol.p99_abs_bp:g}")
        if abs(mean_bp) > tol.abs_mean_bp:
            breaches.append(f"|mean| {abs(mean_bp):.1f}>{tol.abs_mean_bp:g}")
        level: Status = "FAIL" if breaches else "PASS"
        if _ORDER[level] < _ORDER[worst]:
            worst = level
        rows.append(
            {
                "ccy": ccy,
                "source": source,
                "n_days": int(rec["n_days"]),
                "median_abs_bp": round(median_bp, 2),
                "p99_abs_bp": round(p99_bp, 1),
                "max_abs_bp": round(float(rec["max_abs_bp"]), 1),
                "mean_bp": round(mean_bp, 2),
                "status": level,
                "breaches": "; ".join(breaches),
            }
        )
    ev = pd.DataFrame(rows)
    n_fail = int((ev["status"] == "FAIL").sum())
    expected = {(c, s) for c in ccys for s in RECON_TOLERANCES}
    missing = sorted(expected - seen)
    if missing:
        worst = "FAIL"
    msg = (
        f"{n_fail} of {len(ev)} currency/source pairs breach tolerance"
        if n_fail
        else f"all {len(ev)} currency/source pairs within tolerance"
    )
    if missing:
        msg += f"; no overlap for {missing}"
    return CheckResult("reconciliation", worst, msg, ev)


def check_master_gaps(
    con: duckdb.DuckDBPyConnection, ccys: Sequence[str] = config.EXPOSURE_CCYS
) -> CheckResult:
    """The master FX table must be (almost) complete and say where each value came from."""
    q = """
        SELECT ccy,
               count(*)                         AS n_days,
               count(*) - count(usd_per_fcy)    AS n_null,
               sum(CASE WHEN source_used = 'fred' THEN 1 ELSE 0 END) AS n_fred,
               sum(CASE WHEN source_used = 'boc'  THEN 1 ELSE 0 END) AS n_boc,
               sum(CASE WHEN source_used = 'ecb'  THEN 1 ELSE 0 END) AS n_ecb
        FROM fx_usd_master GROUP BY ccy ORDER BY ccy
    """
    ev = con.execute(q).df()
    if ev.empty:
        return CheckResult("master_completeness", "FAIL", "master FX table is empty")
    ev["null_share"] = ev["n_null"] / ev["n_days"]
    bad = ev[ev["null_share"] > MAX_NULL_SHARE]
    missing_ccys = sorted(set(ccys) - set(ev["ccy"]))
    if not bad.empty or missing_ccys:
        return CheckResult(
            "master_completeness",
            "FAIL",
            f"{len(bad)} currencies exceed {MAX_NULL_SHARE:.1%} missing; absent: {missing_ccys}",
            ev,
        )
    filled = int(ev["n_boc"].sum() + ev["n_ecb"].sum())
    return CheckResult(
        "master_completeness",
        "PASS",
        f"{int(ev['n_null'].sum())} NULL cells across {len(ev)} currencies; "
        f"{filled} cells filled from BoC/ECB",
        ev,
    )


def check_calendar(con: duckdb.DuckDBPyConnection) -> CheckResult:
    """Consecutive NY business days must not be more than a long weekend apart."""
    q = """
        WITH d AS (SELECT DISTINCT obs_date FROM fx_usd_master),
        gaps AS (
            SELECT obs_date,
                   lag(obs_date) OVER (ORDER BY obs_date)                 AS prev_date,
                   obs_date - lag(obs_date) OVER (ORDER BY obs_date)      AS gap_days
            FROM d
        )
        SELECT prev_date, obs_date, gap_days FROM gaps WHERE gap_days > ? ORDER BY obs_date
    """
    ev = con.execute(q, [MAX_CALENDAR_GAP_DAYS]).df()
    if not ev.empty:
        return CheckResult(
            "calendar",
            "FAIL",
            f"{len(ev)} gaps longer than {MAX_CALENDAR_GAP_DAYS} days in the NY calendar",
            ev,
        )
    return CheckResult(
        "calendar", "PASS", f"no gaps longer than {MAX_CALENDAR_GAP_DAYS} calendar days"
    )


def ewma_vol(returns: pd.Series, lam: float = EWMA_LAMBDA) -> pd.Series:
    """Lagged EWMA standard deviation: sigma_t uses returns up to t-1 only."""
    var = returns.pow(2).ewm(alpha=1 - lam, adjust=False).mean().shift(1)
    return pd.Series(np.sqrt(var.to_numpy()), index=var.index)


def check_return_outliers(con: duckdb.DuckDBPyConnection) -> CheckResult:
    """Flag daily log returns beyond OUTLIER_SIGMA lagged EWMA standard deviations.

    This is a WARN, never a FAIL: genuine market events (CHF de-peg 15 Jan 2015, GBP on
    24 Jun 2016) look exactly like data errors to a statistical filter. To help the human
    who reviews the list, each move is checked against the sources the master price did
    not come from: ``confirmed_by`` counts those whose own move over the same interval
    has the same sign and at least half the size (a data error in one feed is not
    repeated by the others). The ECB fixes at 14:15 CET, so a move late in the New York
    day reaches it a day later and can leave it unconfirming. ``span_days`` is the
    calendar length of the return: more than a weekend means a source holiday, and the
    "daily" move is really two days.
    """
    df = con.execute(
        "SELECT obs_date, ccy, usd_per_fcy, is_filled, source_used FROM fx_usd_master_filled "
        "ORDER BY ccy, obs_date"
    ).df()
    by_source = con.execute("SELECT obs_date, ccy, source, usd_per_fcy FROM fx_usd_per_fcy").df()
    rows = []
    for ccy, g in df.groupby("ccy"):
        g = g.set_index("obs_date")
        px = g["usd_per_fcy"]
        r = np.log(px).diff()
        r[g["is_filled"].to_numpy()] = np.nan
        z = r / ewma_vol(r)
        src = (
            by_source[by_source["ccy"] == ccy]
            .pivot(index="obs_date", columns="source", values="usd_per_fcy")
            .reindex(px.index)
        )
        dates = pd.DatetimeIndex(px.index)
        used = g["source_used"].astype(str).to_numpy()
        ret = r.to_numpy(dtype=float)
        for i in (int(k) for k in np.flatnonzero((z.abs() > OUTLIER_SIGMA).to_numpy())):
            others = [str(s) for s in src.columns if str(s) != used[i]]
            moves = []
            for s in others:
                v0, v1 = float(src[s].iloc[i - 1]), float(src[s].iloc[i])
                if np.isfinite(v0) and np.isfinite(v1):
                    moves.append(float(np.log(v1 / v0)))
            agree = sum(
                np.sign(m) == np.sign(ret[i]) and abs(m) >= 0.5 * abs(ret[i]) for m in moves
            )
            rows.append(
                {
                    "date": dates[i].date().isoformat(),
                    "ccy": ccy,
                    "log_return_pct": round(100 * ret[i], 2),
                    "z": round(float(z.iloc[i]), 1),
                    "source": used[i],
                    "confirmed_by": f"{agree} of {len(moves)}",
                    "span_days": (dates[i] - dates[i - 1]).days,
                }
            )
    if rows:
        all_rows = pd.DataFrame(rows)
        n_conf = all_rows["confirmed_by"].str.split(" of ")
        n_all = int(n_conf.map(lambda x: x[0] == x[1] and x[1] != "0").sum())
        n_none = int(n_conf.map(lambda x: x[0] == "0").sum())
        ev = all_rows.sort_values("z", key=np.abs, ascending=False).head(25)
        return CheckResult(
            "return_outliers",
            "WARN",
            f"{len(rows)} daily moves beyond {OUTLIER_SIGMA:g} EWMA sigma: {n_all} confirmed "
            f"by every other source, {len(rows) - n_all - n_none} by some, {n_none} by none "
            "(review, not necessarily errors)",
            ev,
        )
    return CheckResult(
        "return_outliers", "PASS", f"no daily moves beyond {OUTLIER_SIGMA:g} EWMA sigma"
    )


def check_rates_range(con: duckdb.DuckDBPyConnection) -> CheckResult:
    """Policy rates must sit in a plausible percent range (catches unit errors)."""
    q = """
        SELECT o.source, o.series_id, c.ccy,
               min(o.value) AS min_pct, max(o.value) AS max_pct, max(o.obs_date) AS last_date
        FROM raw_observations o JOIN series_catalog c USING (source, series_id)
        WHERE c.category = 'policy_rate'
        GROUP BY ALL ORDER BY ALL
    """
    ev = con.execute(q).df()
    lo, hi = RATE_RANGE
    bad = ev[(ev["min_pct"] < lo) | (ev["max_pct"] > hi)]
    if not bad.empty:
        return CheckResult(
            "rates_range", "FAIL", f"{len(bad)} rate series outside [{lo}, {hi}] percent", bad
        )
    return CheckResult(
        "rates_range", "PASS", f"all {len(ev)} rate series within [{lo}, {hi}] percent", ev
    )


# ---------------------------------------------------------------------------------------
# driver
# ---------------------------------------------------------------------------------------
def run_quality(
    paths: config.Paths,
    *,
    specs: Sequence[SeriesSpec] = ALL_SERIES,
    ccys: Sequence[str] = config.EXPOSURE_CCYS,
    today: date | None = None,
    write: bool = True,
) -> QualityReport:
    """Rebuild the database from the cache, run every check, write the report files.

    ``specs`` and ``ccys`` default to the full registry and exposure list; tests pass a
    subset so they can run against a small synthetic cache.
    """
    cache = SeriesCache(paths.cache_dir)
    report = QualityReport()
    report.checks.append(check_cache_complete(cache, specs))
    report.checks.append(check_schema(cache, specs))
    report.checks.append(check_staleness(cache, today, specs))
    if report.checks[0].status == "FAIL" or report.checks[1].status == "FAIL":
        log.error("cache incomplete or malformed; skipping database checks")
    else:
        con = db.build_database(paths)
        try:
            report.checks.append(check_reconciliation(con, ccys))
            report.checks.append(check_master_gaps(con, ccys))
            report.checks.append(check_calendar(con))
            report.checks.append(check_return_outliers(con))
            report.checks.append(check_rates_range(con))
        finally:
            con.close()
    if write:
        paths.reports_dir.mkdir(parents=True, exist_ok=True)
        (paths.reports_dir / "quality_report.md").write_text(report.to_markdown(), encoding="utf-8")
        (paths.reports_dir / "alerts.md").write_text(report.to_alerts_markdown(), encoding="utf-8")
    return report
