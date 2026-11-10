"""The SQL conversions are checked against the truth the mini cache was built from."""

import numpy as np
import pandas as pd
import pytest

from fx_treasury_risk import config, db
from tests.conftest import MiniTruth, build_mini_cache


def _usd_per_fcy(con, source: str, ccy: str) -> pd.Series:  # type: ignore[no-untyped-def]
    df = con.execute(
        "SELECT obs_date, usd_per_fcy FROM fx_usd_per_fcy "
        "WHERE source = ? AND ccy = ? ORDER BY obs_date",
        [source, ccy],
    ).df()
    idx = pd.DatetimeIndex(pd.to_datetime(df["obs_date"])).as_unit("ns")
    return pd.Series(df["usd_per_fcy"].to_numpy(), index=idx)


def _assert_close(got: pd.Series, want: pd.Series) -> None:
    """Same dates (ignoring index dtype/resolution) and values equal to 1e-9 relative."""
    assert list(got.index.strftime("%Y-%m-%d")) == list(want.index.strftime("%Y-%m-%d"))
    assert np.allclose(got.to_numpy(), want.to_numpy(), rtol=1e-9, atol=0)


def test_raw_table_recovers_source_and_series_from_path(
    tmp_paths: config.Paths, mini: MiniTruth
) -> None:
    con = db.build_database(tmp_paths)
    rows = con.execute(
        "SELECT source, series_id, count(*) FROM raw_observations GROUP BY ALL ORDER BY ALL"
    ).fetchall()
    # dots in ids survive the path-to-id parsing
    assert ("ecb", "FM.D.U2.EUR.4F.KR.DFR.LEV", len(mini.usd_per_eur)) in rows
    assert ("fred", "DEXUSEU", len(mini.dates)) in rows
    con.close()


def test_fred_inversion(tmp_paths: config.Paths, mini: MiniTruth) -> None:
    con = db.build_database(tmp_paths)
    _assert_close(_usd_per_fcy(con, "fred", "JPY"), mini.usd_per_jpy[mini.dates])
    _assert_close(_usd_per_fcy(con, "fred", "EUR"), mini.usd_per_eur[mini.dates])
    _assert_close(_usd_per_fcy(con, "fred", "CAD"), 1 / mini.cad_per_usd[mini.dates])
    con.close()


def test_boc_cross_division_and_vintage_precedence(
    tmp_paths: config.Paths, mini: MiniTruth
) -> None:
    con = db.build_database(tmp_paths)
    eur = _usd_per_fcy(con, "boc", "EUR")
    # Crosses equal the truth on every date: within a vintage the legacy bump cancels
    # (bump * cross / (bump * usdcad)), and on overlap dates the current vintage is used.
    _assert_close(eur, mini.usd_per_eur[eur.index])
    assert not eur.index.duplicated().any()  # overlap dates are not duplicated
    assert eur.index.min() == mini.legacy_dates.min()
    assert eur.index.max() == mini.current_dates.max()
    # the raw legacy cross really does carry the bump, so the cancellation is a real test
    legacy_only = mini.legacy_dates[mini.legacy_dates < "2017-01-03"][0]
    raw = con.execute(
        "SELECT value FROM raw_observations WHERE series_id = 'EUROCAE01' AND obs_date = ?",
        [legacy_only.date()],
    ).fetchall()[0][0]
    assert raw == pytest.approx(
        mini.usd_per_eur[legacy_only] * mini.cad_per_usd[legacy_only] * mini.legacy_bump
    )
    # CAD itself is 1 / USDCAD; on legacy-only dates it carries the bump, so test current
    cad = _usd_per_fcy(con, "boc", "CAD")
    cur = cad[cad.index >= mini.current_dates.min()]
    _assert_close(cur, 1 / mini.cad_per_usd[cur.index])
    con.close()


def test_ecb_cross_division(tmp_paths: config.Paths, mini: MiniTruth) -> None:
    con = db.build_database(tmp_paths)
    jpy = _usd_per_fcy(con, "ecb", "JPY")
    _assert_close(jpy, mini.usd_per_jpy[jpy.index])
    eur = _usd_per_fcy(con, "ecb", "EUR")
    _assert_close(eur, mini.usd_per_eur[eur.index])
    con.close()


def test_reconciliation_is_near_zero_on_consistent_data(
    tmp_paths: config.Paths, mini: MiniTruth
) -> None:
    con = db.build_database(tmp_paths)
    summary = db.read_table(con, "fx_reconciliation_summary")
    assert set(summary["source"]) == {"boc", "ecb"}
    ecb = summary[summary["source"] == "ecb"]
    # the cache stores 10 significant digits, so "zero" means below 1e-4 bp
    assert (ecb["max_abs_bp"] < 1e-4).all()
    # BoC: crosses cancel the legacy bump exactly; CAD keeps it (~2 bp) on legacy-only days
    boc = summary[summary["source"] == "boc"].set_index("ccy")
    assert boc.loc["EUR", "max_abs_bp"] < 1e-4 and boc.loc["JPY", "max_abs_bp"] < 1e-4
    assert 1.9 < boc.loc["CAD", "max_abs_bp"] < 2.1
    con.close()


def test_master_precedence_and_forward_fill(tmp_paths: config.Paths) -> None:
    gap = "2017-01-10"  # FRED has no print at all that day; BoC and ECB do
    mini = build_mini_cache(tmp_paths.cache_dir, fred_gap_dates=[gap])
    con = db.build_database(tmp_paths)
    master = db.read_table(con, "fx_usd_master")
    # calendar = FRED dates, so a day without any FRED print is not in the master at all...
    assert pd.Timestamp(gap) not in set(pd.to_datetime(master["obs_date"]))
    # ...and every cell that exists came from FRED
    assert set(master["source_used"]) == {"fred"}
    # punch a hole in one FRED series only (EUR), keeping the calendar: BoC fills it
    con.execute(
        "DELETE FROM raw_observations WHERE series_id = 'DEXUSEU' AND obs_date = DATE '2017-01-12'"
    )
    con.execute(db.load_sql("050_fx_usd_master"))
    row = con.execute(
        "SELECT usd_per_fcy, source_used FROM fx_usd_master "
        "WHERE ccy='EUR' AND obs_date=DATE '2017-01-12'"
    ).fetchall()[0]
    assert row[1] == "boc"
    assert row[0] == pytest.approx(mini.usd_per_eur["2017-01-12"], rel=1e-9)
    # a hole in every source becomes NULL in the master and is forward-filled in the view
    con.execute(
        "DELETE FROM raw_observations WHERE obs_date = DATE '2017-01-13' "
        "AND series_id IN ('DEXUSEU','FXEURCAD','EUROCAE01','D.USD.EUR.SP00.A')"
    )
    con.execute(db.load_sql("050_fx_usd_master"))
    null_row = con.execute(
        "SELECT usd_per_fcy FROM fx_usd_master WHERE ccy='EUR' AND obs_date=DATE '2017-01-13'"
    ).fetchall()[0]
    assert null_row[0] is None
    filled = con.execute(
        "SELECT usd_per_fcy, is_filled FROM fx_usd_master_filled "
        "WHERE ccy='EUR' AND obs_date=DATE '2017-01-13'"
    ).fetchall()[0]
    assert filled[1] is True
    assert filled[0] == pytest.approx(mini.usd_per_eur["2017-01-12"], rel=1e-9)
    con.close()
