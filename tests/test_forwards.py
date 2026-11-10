"""Forward pricing against the worked example in docs/hedging-primer.md."""

import pandas as pd
import pytest

from fx_treasury_risk import config, db
from fx_treasury_risk.hedge import forwards
from tests.conftest import MiniTruth


def test_primer_worked_example() -> None:
    # S = 1.1000 USD per EUR, r_usd = 5%, r_eur = 3.5%, three months on the same day count
    f = forwards.forward_rate(1.1000, 5.0, 3.5, 90, 360, 360)
    assert f == pytest.approx(1.1000 * 1.0125 / 1.00875, rel=1e-12)
    assert f == pytest.approx(1.10409, abs=5e-6)
    assert forwards.forward_points(1.1000, f) == pytest.approx(40.9, abs=0.05)
    # the USD rate is higher, so the forward is above spot and hedging a long EUR
    # exposure *earns* carry: negative cost rate of about -(5 - 3.5)%
    cost = forwards.hedge_cost_rate(1.1000, f, 90)
    assert cost < 0 and cost == pytest.approx(-0.0151, abs=5e-4)


def test_day_count_mismatch_is_small() -> None:
    # r * days * (1/360 - 1/365): about 1.7 bp of spot at three months and 5%, 0.6 bp at one month
    same = forwards.forward_rate(1.25, 5.0, 4.0, 90, 365, 365)
    mixed = forwards.forward_rate(1.25, 5.0, 4.0, 90, 360, 365)
    assert abs(mixed - same) / same == pytest.approx(0.05 * 90 * (1 / 360 - 1 / 365), rel=0.05)
    same1 = forwards.forward_rate(1.25, 5.0, 4.0, 30, 365, 365)
    mixed1 = forwards.forward_rate(1.25, 5.0, 4.0, 30, 360, 365)
    assert abs(mixed1 - same1) / same1 < 1e-4


def test_high_yielder_costs_carry() -> None:
    # BRL at 14% vs USD 5%: forward well below spot, hedging a long BRL position costs ~9%
    s = 0.18
    f = forwards.forward_rate(s, 5.0, 14.0, 30, 360, 365)
    assert f < s
    assert forwards.hedge_cost_rate(s, f, 30) == pytest.approx(0.088, abs=0.005)


def test_rates_short_precedence_and_proxy(tmp_paths: config.Paths, mini: MiniTruth) -> None:
    con = db.build_database(tmp_paths)
    try:
        r = (
            con.execute(
                "SELECT ccy, rate_pct, source, is_proxy, is_fallback, days_stale "
                "FROM rates_short WHERE obs_date = DATE '2017-01-10' ORDER BY ccy"
            )
            .df()
            .set_index("ccy")
        )
        # every rate is a policy rate, daily, so the primaries are fresh
        assert r.loc["USD", "rate_pct"] == 0.5 and not r.loc["USD", "is_fallback"]
        assert r.loc["CAD", "rate_pct"] == 0.48 and r.loc["CAD", "source"] == "bis"
        # the euro area uses the ECB deposit facility rate, not the BIS (MRO) series
        assert r.loc["EUR", "rate_pct"] == -0.4 and r.loc["EUR", "source"] == "ecb"
        # SGD is the USD rate flagged as a proxy
        assert r.loc["SGD", "rate_pct"] == 0.5 and bool(r.loc["SGD", "is_proxy"])
        # currencies with no rate data in the mini cache are simply absent
        assert "JPY" not in r.index
    finally:
        con.close()


def test_stale_primary_falls_back(tmp_paths: config.Paths, mini: MiniTruth) -> None:
    """A deposit rate more than 120 days old gives way to the BIS euro-area series."""
    from fx_treasury_risk.data.cache import SeriesCache

    cache = SeriesCache(tmp_paths.cache_dir)
    cache.write(
        "ecb",
        "FM.D.U2.EUR.4F.KR.DFR.LEV",
        pd.Series([-0.4], index=pd.to_datetime(["2016-09-01"])),
        url="test://",
    )
    days = pd.bdate_range("2016-12-01", "2017-01-31")
    cache.write("bis", "D.XM", pd.Series(0.0, index=days), url="test://")
    con = db.build_database(tmp_paths)
    try:
        q = (
            "SELECT rate_pct, source, is_fallback FROM rates_short "
            "WHERE ccy = 'EUR' AND obs_date = ?"
        )
        assert con.execute(q, ["2016-12-15"]).fetchall()[0] == (-0.4, "ecb", False)  # 105 days old
        assert con.execute(q, ["2017-01-10"]).fetchall()[0] == (0.0, "bis", True)  # 131 days old
    finally:
        con.close()


def test_forward_table_shapes(tmp_paths: config.Paths, mini: MiniTruth) -> None:
    con = db.build_database(tmp_paths)
    try:
        from fx_treasury_risk.hedge.rates import rates_on, spots_on

        as_of = pd.Timestamp("2017-01-10")
        spots = spots_on(con, as_of)
        rates = rates_on(con, as_of)
        tbl = forwards.forward_table(spots[["CAD"]], rates, 30)
        assert list(tbl.index) == ["CAD"]
        r_usd = 0.5
        assert tbl.loc["CAD", "r_usd_pct"] == pytest.approx(r_usd)
        assert tbl.loc["CAD", "forward"] == pytest.approx(
            forwards.forward_rate(spots["CAD"], r_usd, 0.48, 30, 360, 365)
        )
    finally:
        con.close()


def test_backtest_rates_match_forward_table(tmp_paths: config.Paths, mini: MiniTruth) -> None:
    """The policy backtest's wide rate table converts T-bills the same way as the forwards."""
    con = db.build_database(tmp_paths)
    try:
        from fx_treasury_risk.hedge.rates import rates_on, rates_wide

        as_of = pd.Timestamp("2017-01-10")
        wide = rates_wide(con).loc[as_of]
        tbl = forwards.forward_table(pd.Series({"CAD": 0.75}), rates_on(con, as_of), 30)
        assert wide["USD"] == pytest.approx(tbl.loc["CAD", "r_usd_pct"])
        assert wide["CAD"] == pytest.approx(0.48)
    finally:
        con.close()
