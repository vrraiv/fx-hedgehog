"""Policy backtest arithmetic on a tiny hand-built market."""

import numpy as np
import pandas as pd
import pytest

from fx_treasury_risk.backtest import policy
from fx_treasury_risk.hedge.config import load_hedge_config


def _market() -> policy.MarketData:
    cal = pd.bdate_range("2021-01-28", periods=25)  # origin 28 Jan, month = Feb trading days
    n = len(cal)
    prices = np.column_stack([np.linspace(1.20, 1.26, n), np.linspace(0.0090, 0.0085, n)])
    returns = np.diff(np.log(prices), axis=0)
    returns = np.vstack([np.zeros((1, 2)), returns])
    exposure = np.column_stack([np.full(n, 10_000_000.0), np.full(n, 2_000_000_000.0)])
    rates = pd.DataFrame({"USD": 5.0, "EUR": 3.0, "JPY": 0.0}, index=cal)
    forecast = pd.DataFrame(
        {"EUR": [10_500_000.0], "JPY": [2.1e9]}, index=pd.DatetimeIndex([cal[0]])
    )
    return policy.MarketData(
        calendar=cal,
        prices=prices,
        returns=returns,
        exposure_fcy=exposure,
        rates=rates,
        forecast_fcy=forecast,
        day_count={"USD": 360, "EUR": 360, "JPY": 360},
        ccys=["EUR", "JPY"],
    )


def test_month_pnl_identities() -> None:
    md = _market()
    t_origin, t_start, t_end = 0, 1, len(md.calendar)
    notional = np.array([-5_000_000.0, -1e9])  # sold forward half of each exposure
    forward = md.prices[t_origin] * np.array([1.001, 0.999])
    pnl = policy.month_pnl(md, t_origin, t_start, t_end, notional, forward, spread_cost_usd=1_000.0)
    # unhedged: constant exposure x total spot move
    move = md.prices[t_end - 1] - md.prices[t_origin]
    assert pnl["pnl_unhedged"].sum() == pytest.approx(float((md.exposure_fcy[0] * move).sum()))
    # forward payoff identity: mtm + carry over the month = notional * (S_T - F)
    payoff = float((notional * (md.prices[t_end - 1] - forward)).sum())
    assert pnl["pnl_hedge_mtm"].sum() + pnl["pnl_carry"].sum() == pytest.approx(payoff)
    assert pnl["pnl_spread"].sum() == -1_000.0 and pnl["pnl_spread"][1] == 0.0
    assert np.allclose(pnl["pnl_total"], sum(pnl[c] for c in policy.PNL_COLS[:-1]))
    # a full hedge dealt at a forward equal to the origin spot locks the USD value:
    # total = E (S_T - S_0) + (-E)(S_T - F) = E (F - S_0) = 0
    full = policy.month_pnl(
        md, t_origin, t_start, t_end, -md.exposure_fcy[0], md.prices[t_origin], 0.0
    )
    assert full["pnl_total"].sum() == pytest.approx(0.0, abs=1e-6)


def test_max_drawdown_counts_losses_from_the_start() -> None:
    # cumulative P&L 0 -> -1 -> -2 -> 1 -> -1: the worst fall from a peak is 0 -> -2,
    # which a peak taken only over the realised days (-1) would understate as -1
    assert policy.max_drawdown(np.array([-1.0, -1.0, 3.0, -2.0])) == pytest.approx(-2.0)
    assert policy.max_drawdown(np.array([1.0, 2.0, -0.5, 1.0])) == pytest.approx(-0.5)
    assert policy.max_drawdown(np.array([1.0, 1.0])) == 0.0


def test_rebalance_dates_first_trading_day() -> None:
    cal = pd.bdate_range("2019-12-20", "2020-03-15")
    r = policy.rebalance_dates(cal, pd.Timestamp("2020-01-01"))
    assert list(r.strftime("%Y-%m-%d")) == ["2020-01-01", "2020-02-03", "2020-03-02"]


def test_hedge_config_loads() -> None:
    c = load_hedge_config()
    assert c.horizon_days == 21 and 0.9 < c.confidence < 1.0
    assert set(c.bid_ask_bp) >= {"EUR", "BRL", "SGD"}
    assert c.policies[-1] == "optimizer"
    assert len(c.spread_vector(["EUR", "XXX"])) == 2


def test_hedge_is_sized_on_the_average_over_its_holding_month() -> None:
    """A forward dealt after a month-end origin covers the next month's trading days."""
    from fx_treasury_risk.hedge.sizing import holding_month_by_origin, holding_month_mean

    origin = pd.Timestamp("2021-01-29")
    days = pd.bdate_range("2021-02-01", periods=30)  # runs into March
    # exposure 100 on ordinary days, 40 on the last trading day of February
    eur = pd.Series(100.0, index=days)
    eur[pd.Timestamp("2021-02-26")] = 40.0
    medians = pd.DataFrame({"EUR": eur})
    feb = days[days.month == 2]
    expected = (100.0 * (len(feb) - 1) + 40.0) / len(feb)
    assert holding_month_mean(medians, origin)["EUR"] == pytest.approx(expected)
    # March forecasts are outside the holding month and are ignored
    medians.loc[days.month == 3, "EUR"] = 1e9
    assert holding_month_mean(medians, origin)["EUR"] == pytest.approx(expected)
    # the long-format version used by the backtest gives the same answer
    long = medians.reset_index(names="target_date").melt(
        id_vars="target_date", var_name="ccy", value_name="q500"
    )
    long.insert(0, "origin", origin)
    by_origin = holding_month_by_origin(long)
    assert by_origin.loc[origin, "EUR"] == pytest.approx(expected)
    with pytest.raises(ValueError, match="holding month"):
        holding_month_mean(medians, pd.Timestamp("2021-06-30"))
