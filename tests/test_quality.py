from datetime import date

import pandas as pd

from fx_treasury_risk import config
from fx_treasury_risk.data.cache import SeriesCache
from fx_treasury_risk.data.quality import ewma_vol, run_quality
from tests.conftest import MINI_CCYS, MINI_SPECS, MiniTruth

TODAY = date(2017, 2, 3)  # mini data ends 2017-01-31; pretend we retrieved it that day


def _run(paths: config.Paths, today: date = TODAY):  # type: ignore[no-untyped-def]
    return run_quality(paths, specs=MINI_SPECS, ccys=MINI_CCYS, today=today, write=True)


def _retrieved_on(paths: config.Paths, day: str) -> None:
    """Rewrite manifest retrieval timestamps so staleness is judged against ``day``."""
    cache = SeriesCache(paths.cache_dir)
    entries = cache.manifest()
    for k, e in entries.items():
        entries[k] = type(e)(**{**e.__dict__, "retrieved_at": f"{day}T12:00:00+00:00"})
    cache._save_manifest(entries)


def test_consistent_cache_passes(tmp_paths: config.Paths, mini: MiniTruth) -> None:
    _retrieved_on(tmp_paths, "2017-02-01")
    report = _run(tmp_paths)
    by_name = {c.name: c for c in report.checks}
    assert by_name["cache_complete"].status == "PASS"
    assert by_name["schema"].status == "PASS"
    assert by_name["staleness"].status == "PASS", by_name["staleness"].summary
    assert by_name["reconciliation"].status == "PASS"
    assert by_name["master_completeness"].status == "PASS"
    assert by_name["calendar"].status == "PASS"
    assert by_name["rates_range"].status == "PASS"
    assert report.status in ("PASS", "WARN")  # outliers may WARN on random data
    assert (tmp_paths.reports_dir / "quality_report.md").exists()
    alerts = (tmp_paths.reports_dir / "alerts.md").read_text(encoding="utf-8")
    assert "Alerts" in alerts


def test_unit_error_fails_reconciliation(tmp_paths: config.Paths, mini: MiniTruth) -> None:
    cache = SeriesCache(tmp_paths.cache_dir)
    bad = cache.read("boc", "FXEURCAD") * 100  # e.g. quoted per 100 units
    cache.write("boc", "FXEURCAD", bad, url="test://bad")
    _retrieved_on(tmp_paths, "2017-02-01")
    report = _run(tmp_paths)
    rec = {c.name: c for c in report.checks}["reconciliation"]
    assert rec.status == "FAIL"
    assert rec.evidence is not None
    eur = rec.evidence[(rec.evidence.ccy == "EUR") & (rec.evidence.source == "boc")].iloc[0]
    assert eur.breaches  # which statistic trips first depends on the overlap window
    assert report.failed and "reconciliation" in (tmp_paths.reports_dir / "alerts.md").read_text()


def test_stale_series_fails(tmp_paths: config.Paths, mini: MiniTruth) -> None:
    cache = SeriesCache(tmp_paths.cache_dir)
    short = cache.read("fred", "DEXUSEU")
    cache.write("fred", "DEXUSEU", short[short.index < "2017-01-10"], url="test://stale")
    _retrieved_on(tmp_paths, "2017-02-01")  # 22 days after the last print, limit is 14
    report = _run(tmp_paths)
    stale = {c.name: c for c in report.checks}["staleness"]
    assert stale.status == "FAIL"
    assert stale.evidence is not None and "fred:DEXUSEU" in set(stale.evidence.series)


def test_old_cache_only_warns(tmp_paths: config.Paths, mini: MiniTruth) -> None:
    _retrieved_on(tmp_paths, "2017-02-01")
    report = _run(tmp_paths, today=date(2017, 6, 1))
    stale = {c.name: c for c in report.checks}["staleness"]
    assert stale.status == "WARN"
    assert "refreshed" in stale.summary


def test_missing_series_fails_and_skips_db_checks(tmp_paths: config.Paths, mini: MiniTruth) -> None:
    (tmp_paths.cache_dir / "fred" / "DEXUSEU.csv").unlink()
    report = _run(tmp_paths)
    names = [c.name for c in report.checks]
    assert {c.name: c for c in report.checks}["cache_complete"].status == "FAIL"
    assert "reconciliation" not in names


def test_ewma_vol_is_lagged() -> None:
    r = pd.Series([0.0] * 10 + [0.1] + [0.0] * 5)
    v = ewma_vol(r, lam=0.94)
    assert pd.isna(v.iloc[0])
    assert v.iloc[10] == 0.0  # the shock day itself uses only past returns
    assert v.iloc[11] > 0.0


def _scale(cache: SeriesCache, key: str, factor: float, start: str, end: str | None = None) -> None:
    source, series_id = key.split(":")
    s = cache.read(source, series_id)
    mask = (s.index >= start) & (s.index <= (end or s.index[-1]))
    s[mask] = s[mask] * factor
    cache.write(source, series_id, s, url="test://mini")


def test_outliers_are_checked_against_the_other_sources(
    tmp_paths: config.Paths, mini: MiniTruth
) -> None:
    cache = SeriesCache(tmp_paths.cache_dir)
    # a genuine EUR move: every source sees EUR 8% stronger from 20 January
    for key in (
        "fred:DEXUSEU",
        "boc:FXEURCAD",
        "ecb:D.USD.EUR.SP00.A",
        "ecb:D.JPY.EUR.SP00.A",
        "ecb:D.CAD.EUR.SP00.A",
    ):
        _scale(cache, key, 1.08, "2017-01-20")
    # a bad print: FRED alone shows JPY 10% stronger for one day
    _scale(cache, "fred:DEXJPUS", 1 / 1.10, "2017-01-24", "2017-01-24")
    report = _run(tmp_paths)
    out = {c.name: c for c in report.checks}["return_outliers"]
    ev = out.evidence.set_index(["ccy", "date"])
    assert ev.loc[("EUR", "2017-01-20"), "confirmed_by"] == "2 of 2"
    assert ev.loc[("JPY", "2017-01-24"), "confirmed_by"] == "0 of 2"
    assert "by none" in out.summary
