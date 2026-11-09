"""Exposure SQL checked against a tiny hand-written set of flows."""

from pathlib import Path

import duckdb
import pandas as pd
import pytest

from fx_treasury_risk import config, db
from fx_treasury_risk.exposure.build import build_exposure
from tests.conftest import MiniTruth


def _write_flows(path: Path, rows: list[tuple[str, str, str, str, float]]) -> Path:
    df = pd.DataFrame(rows, columns=["date", "entity", "ccy", "flow_type", "amount"])
    df["date"] = pd.to_datetime(df["date"])
    con = duckdb.connect()
    con.register("f", df)
    con.execute(f"COPY (SELECT * FROM f) TO '{path.as_posix()}' (FORMAT PARQUET)")
    con.close()
    return path


def test_components_follow_one_authorization(tmp_paths: config.Paths, mini: MiniTruth) -> None:
    """Walk one EUR 1,000 sale at EA through its life and check every component."""
    db.build_database(tmp_paths).close()
    take, s = 0.025, 0.6
    a = 1000.0
    rows = [
        ("2017-01-04", "EA", "EUR", "auth", a),
        ("2017-01-04", "EA", "EUR", "payable_accrual", a * (1 - take) * s),
        ("2017-01-06", "EA", "EUR", "settlement", a),
        ("2017-01-09", "EA", "EUR", "payout_same", a * (1 - take) * s),
        ("2017-01-09", "EA", "EUR", "payout_converted", a * (1 - take) * (1 - s)),
        ("2017-01-31", "EA", "EUR", "fee_sweep", a * take),
        ("2017-01-04", "US", "EUR", "interco_receivable", 500.0),
        ("2017-01-04", "EA", "EUR", "interco_payable", 500.0),
    ]
    flows = _write_flows(tmp_paths.data_dir / "flows.parquet", rows)
    con = build_exposure(tmp_paths, flows)
    try:
        e = (
            con.execute(
                "SELECT exposure_date, in_flight_fcy, balance_fcy, payable_fcy, "
                "intercompany_fcy, net_fcy, gross_fcy "
                "FROM exposure_daily WHERE entity='EA' AND ccy='EUR' ORDER BY exposure_date"
            )
            .df()
            .set_index("exposure_date")
        )
        e.index = pd.to_datetime(e.index)
        # day of sale: receivable up, payable down, loan payable
        d = e.loc["2017-01-04"]
        assert d.in_flight_fcy == pytest.approx(a) and d.balance_fcy == 0
        assert d.payable_fcy == pytest.approx(-a * (1 - take) * s)
        assert d.intercompany_fcy == pytest.approx(-500)
        assert d.net_fcy == pytest.approx(a - a * (1 - take) * s - 500)
        assert d.gross_fcy == pytest.approx(a + a * (1 - take) * s + 500)
        # a day with no flows carries the position forward unchanged
        pd.testing.assert_series_equal(e.loc["2017-01-05"], d, check_names=False)
        # settlement: receivable to cash
        d = e.loc["2017-01-06"]
        assert d.in_flight_fcy == pytest.approx(0) and d.balance_fcy == pytest.approx(a)
        # payout: cash and payable both down, converted share sold
        d = e.loc["2017-01-09"]
        assert d.payable_fcy == pytest.approx(0)
        assert d.balance_fcy == pytest.approx(a * take)
        # sweep: nothing left but the loan
        d = e.loc["2017-01-31"]
        assert d.balance_fcy == pytest.approx(0)
        assert d.net_fcy == pytest.approx(-500)
        # group level: intercompany nets to zero, gross counts both legs
        g = con.execute(
            "SELECT sum(net_fcy) AS net, sum(gross_fcy) AS gross FROM exposure_daily "
            "WHERE ccy='EUR' AND exposure_date = DATE '2017-01-31'"
        ).fetchall()[0]
        assert g[0] == pytest.approx(0) and g[1] == pytest.approx(1000)
        # USD translation uses the as-of FX rate; the weekend 2017-01-07 uses Friday's rate
        usd = con.execute(
            "SELECT fx_date, usd_per_fcy, net_usd, net_fcy FROM exposure_daily_usd "
            "WHERE entity='EA' AND ccy='EUR' AND exposure_date = DATE '2017-01-07'"
        ).fetchall()[0]
        assert str(usd[0]) == "2017-01-06"
        assert usd[1] == pytest.approx(mini.usd_per_eur["2017-01-06"])
        assert usd[2] == pytest.approx(usd[3] * usd[1])
    finally:
        con.close()


def test_unmapped_flow_type_is_rejected(tmp_paths: config.Paths, mini: MiniTruth) -> None:
    db.build_database(tmp_paths).close()
    flows = _write_flows(
        tmp_paths.data_dir / "flows.parquet", [("2017-01-04", "EA", "EUR", "mystery", 1.0)]
    )
    with pytest.raises(ValueError, match="mystery"):
        build_exposure(tmp_paths, flows)


def test_optimizer_positions_flow_through_and_exposure_rebuild_resets_them(
    tmp_paths: config.Paths, mini: MiniTruth
) -> None:
    """Stage outputs must not depend on what a previous run left in the database.

    The exposure stage starts from legacy hedges only; storing optimizer positions (the
    policy backtest's job) replaces the legacy rule for that month and is visible in
    exposure_group_fx immediately; rebuilding exposure goes back to legacy-only.
    """
    from fx_treasury_risk.backtest.policy import _store_optimizer_positions

    db.build_database(tmp_paths).close()
    rows = [
        ("2016-12-01", "EA", "EUR", "auth", 100.0),
        ("2017-01-31", "EA", "EUR", "auth", 0.0),
    ]
    flows = _write_flows(tmp_paths.data_dir / "flows.parquet", rows)
    on = "SELECT net_fcy, net_of_hedges_fcy FROM exposure_group_fx WHERE obs_date = '2017-01-10'"

    con = build_exposure(tmp_paths, flows)
    try:
        assert con.execute(on).fetchall()[0] == pytest.approx((100.0, 50.0))  # legacy 50%
        dec = pd.DataFrame(
            {
                "policy": ["optimizer"],
                "rebalance": [pd.Timestamp("2017-01-03")],
                "tenor_days": [30],
                "expo_EUR": [100.0],
                "h_EUR": [1.0],
            }
        )
        _store_optimizer_positions(con, dec, ["EUR"])
        assert con.execute(on).fetchall()[0] == pytest.approx((100.0, 0.0))  # full hedge
    finally:
        con.close()

    con = build_exposure(tmp_paths, flows)  # a second run of the exposure stage
    try:
        assert con.execute("SELECT count(*) FROM hedge_positions").fetchall()[0][0] == 0
        assert con.execute(on).fetchall()[0] == pytest.approx((100.0, 50.0))
    finally:
        con.close()


def test_legacy_hedge_is_half_of_last_months_average(
    tmp_paths: config.Paths, mini: MiniTruth
) -> None:
    db.build_database(tmp_paths).close()
    # constant receivable of 100 through December, so January's hedge is -50
    # a zero-amount flow in late January extends the exposure calendar into that month
    rows = [
        ("2016-12-01", "EA", "EUR", "auth", 100.0),
        ("2017-01-31", "EA", "EUR", "auth", 0.0),
    ]
    flows = _write_flows(tmp_paths.data_dir / "flows.parquet", rows)
    con = build_exposure(tmp_paths, flows)
    try:
        h = con.execute(
            "SELECT trade_date, maturity_date, notional_fcy FROM hedges_legacy ORDER BY trade_date"
        ).df()
        first = h.iloc[0]
        assert pd.Timestamp(first.trade_date).date().isoformat() == "2017-01-01"
        assert pd.Timestamp(first.maturity_date).date().isoformat() == "2017-02-01"
        assert h.iloc[0].notional_fcy == pytest.approx(-50.0)
        w = con.execute(
            "SELECT net_fcy, hedge_fcy, net_of_hedges_fcy FROM exposure_waterfall "
            "WHERE entity='EA' AND ccy='EUR' AND exposure_date = DATE '2017-01-15'"
        ).fetchall()[0]
        assert w == pytest.approx((100.0, -50.0, 50.0))
        # outside the hedge window nothing is hedged
        w0 = con.execute(
            "SELECT hedge_fcy FROM exposure_waterfall "
            "WHERE entity='EA' AND ccy='EUR' AND exposure_date = DATE '2016-12-15'"
        ).fetchall()[0][0]
        assert w0 == 0
    finally:
        con.close()
