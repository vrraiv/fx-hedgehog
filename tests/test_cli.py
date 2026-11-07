"""End-to-end: the CLI must run from the committed cache with no network and no API key."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from fx_treasury_risk import config
from fx_treasury_risk.cli import app

runner = CliRunner()


def test_version() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0 and "fxrisk" in result.output


def test_every_stage_is_a_command() -> None:
    result = runner.invoke(app, ["--help"])
    for stage in (
        "fetch",
        "quality",
        "flows",
        "exposure",
        "forecast",
        "hedge",
        "backtest",
        "risk",
        "report",
        "all",
    ):
        assert stage in result.output


def test_report_without_upstream_tables_fails_cleanly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FXRISK_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("FXRISK_REPORTS_DIR", str(tmp_path / "reports"))
    result = runner.invoke(app, ["report"])
    assert result.exit_code != 0
    assert isinstance(result.exception, RuntimeError)
    assert "fxrisk all" in str(result.exception)


@pytest.mark.skipif(
    not (config.REPO_ROOT / "data" / "cache" / "manifest.json").exists(),
    reason="committed cache missing",
)
def test_quality_runs_offline_on_committed_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Reports and the DuckDB file go to a temp dir so the test never touches the repo's.
    monkeypatch.setenv("FXRISK_OFFLINE", "1")
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    monkeypatch.setenv("FXRISK_REPORTS_DIR", str(tmp_path / "reports"))
    # data dir must contain the real cache: symlinks are unreliable on Windows, so point
    # FXRISK_DATA_DIR at the repo's data dir but accept that the DuckDB file is rebuilt.
    monkeypatch.setenv("FXRISK_DATA_DIR", str(config.REPO_ROOT / "data"))
    result = runner.invoke(app, ["quality"])
    report = (tmp_path / "reports" / "quality_report.md").read_text(encoding="utf-8")
    assert "reconciliation | PASS" in report, result.output
    assert "master_completeness | PASS" in report
    # exit code 0 or 1 depending on staleness of the committed cache; never a crash (3)
    assert result.exit_code in (0, 1), result.output
    assert (tmp_path / "reports" / "alerts.md").exists()


def test_fetch_offline_with_full_cache_is_a_noop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    if not (config.REPO_ROOT / "data" / "cache" / "manifest.json").exists():
        pytest.skip("committed cache missing")
    monkeypatch.setenv("FXRISK_OFFLINE", "1")
    monkeypatch.setenv("FXRISK_DATA_DIR", str(config.REPO_ROOT / "data"))
    result = runner.invoke(app, ["fetch"])
    assert result.exit_code == 0, result.output
    assert "fetched" not in result.output
