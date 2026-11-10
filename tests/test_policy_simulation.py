"""The walk-forward loop on a synthetic two-currency market: identities and no look-ahead."""

from dataclasses import replace
from datetime import date

import numpy as np
import pandas as pd
import pytest

from fx_treasury_risk.backtest import policy
from fx_treasury_risk.hedge.config import HedgeConfig

CCYS = ["EUR", "BRL"]
POLICIES = ("unhedged", "legacy_50", "full_hedge", "optimizer")


def _config(**overrides: object) -> HedgeConfig:
    base = HedgeConfig(
        es_budget_usd=400_000.0,
        horizon_days=21,
        confidence=0.99,
        risk_lam=0.94,
        risk_window=250,
        forward_tenor_days=30,
        bid_ask_bp={"EUR": 1.0, "BRL": 8.0},
        min_ticket_usd=0.0,
        oos_start=date(2021, 3, 1),
        exposure_input="forecast",
        policies=POLICIES,
        turnover_penalty_bp=10.0,
    )
    return replace(base, **overrides)  # type: ignore[arg-type]


def _market(seed: int = 0, usd_rate: float = 5.0, brl_rate: float = 12.0) -> policy.MarketData:
    """Two years of daily data: EUR calm, BRL volatile and high-yielding."""
    rng = np.random.default_rng(seed)
    cal = pd.bdate_range("2020-01-01", "2021-12-31")
    n = len(cal)
    returns = rng.standard_normal((n, 2)) * np.array([0.005, 0.012])
    returns[0] = 0.0
    prices = np.array([1.10, 0.20]) * np.exp(np.cumsum(returns, axis=0))
    wave = 1 + 0.1 * np.sin(np.arange(n) / 7.0)
    exposure = np.column_stack([8e6 * wave, 30e6 * wave[::-1]])
    rates = pd.DataFrame({"USD": usd_rate, "EUR": 3.0, "BRL": brl_rate}, index=cal)
    rebal = policy.rebalance_dates(cal, pd.Timestamp("2020-02-01"))
    origins = cal[[cal.get_loc(d) - 1 for d in rebal]]
    # a noisy forecast of the coming month's average exposure, known at the origin
    months = pd.Series(cal.to_period("M"), index=cal)
    avg = pd.DataFrame(exposure, index=cal, columns=CCYS).groupby(months.to_numpy()).mean()
    forecast = pd.DataFrame(
        [avg.loc[o.to_period("M") + 1].to_numpy() * rng.uniform(0.95, 1.05, 2) for o in origins],
        index=origins,
        columns=CCYS,
    )
    legacy = (-0.5 * avg).shift(1).dropna()
    legacy.index = legacy.index.to_timestamp()
    return policy.MarketData(
        calendar=cal,
        prices=prices,
        returns=returns,
        exposure_fcy=exposure,
        rates=rates,
        forecast_fcy=forecast,
        legacy_fcy=legacy,
        day_count={"USD": 360, "EUR": 360, "BRL": 360},
        ccys=CCYS,
    )


def test_components_add_up_and_static_policies_are_what_they_say() -> None:
    md = _market()
    daily, dec = policy.simulate_policies(md, _config())
    parts = daily[["pnl_unhedged", "pnl_hedge_mtm", "pnl_carry", "pnl_spread"]].sum(axis=1)
    np.testing.assert_allclose(daily["pnl_total"], parts)
    assert set(daily["policy"]) == set(POLICIES)
    # every policy carries the same exposure, so the unhedged leg is identical
    legs = daily.pivot(index="date", columns="policy", values="pnl_unhedged")
    for p in POLICIES[1:]:
        np.testing.assert_allclose(legs[p], legs["unhedged"])
    unhedged = daily[daily["policy"] == "unhedged"]
    assert (unhedged[["pnl_hedge_mtm", "pnl_carry", "pnl_spread"]] == 0).all().all()
    d = dec.set_index(["policy", "rebalance"])
    assert (d.loc["full_hedge", ["h_EUR", "h_BRL"]] == 1.0).all().all()
    assert (d.loc["full_hedge", "ex_ante_es_usd"] == 0).all()
    np.testing.assert_allclose(
        d.loc["unhedged", "ex_ante_es_usd"], d.loc["unhedged", "unhedged_es_usd"]
    )


def test_legacy_deals_the_programme_notional_not_half_the_forecast() -> None:
    md = _market()
    _, dec = policy.simulate_policies(md, _config())
    leg = dec[dec["policy"] == "legacy_50"].iloc[3]
    dealt = -np.array([leg["h_EUR"] * leg["expo_EUR"], leg["h_BRL"] * leg["expo_BRL"]])
    month_start = pd.Timestamp(leg["rebalance"]).to_period("M").to_timestamp()
    np.testing.assert_allclose(dealt, md.legacy_fcy.loc[month_start].to_numpy())
    assert leg["h_EUR"] != pytest.approx(0.5, abs=1e-3)


def test_optimizer_stays_within_the_budget_and_prefers_the_cheap_hedge() -> None:
    cfg = _config()
    _, dec = policy.simulate_policies(_market(), cfg)
    opt = dec[dec["policy"] == "optimizer"]
    assert (opt["ex_ante_es_usd"] <= cfg.es_budget_usd * (1 + 1e-6)).all()
    assert (opt["unhedged_es_usd"] > cfg.es_budget_usd).all()  # the budget is a real constraint
    assert opt["binding"].mean() > 0.5
    # EUR earns carry (USD 5% > EUR 3%) and is hedged in full; BRL costs 7% a year, so the
    # budget is spent on leaving BRL open
    assert opt["h_EUR"].min() > 0.99
    assert opt["h_BRL"].mean() < 0.9


def test_decisions_do_not_see_the_future() -> None:
    md = _market()
    cfg = _config()
    daily, dec = policy.simulate_policies(md, cfg)
    # change everything from 1 September 2021 on: prices, returns, exposure, rates
    cut = md.pos(pd.Timestamp("2021-09-01"))
    prices, returns, exposure = md.prices.copy(), md.returns.copy(), md.exposure_fcy.copy()
    returns[cut:] *= 4.0
    prices[cut:] = prices[cut - 1] * np.exp(np.cumsum(returns[cut:], axis=0))
    exposure[cut:] *= 1.5
    rates = md.rates.copy()
    rates.iloc[cut:] = rates.iloc[cut:] + 2.0
    shocked = replace(md, prices=prices, returns=returns, exposure_fcy=exposure, rates=rates)
    daily2, dec2 = policy.simulate_policies(shocked, cfg)

    cols = [c for c in dec.columns if c not in ("policy", "rebalance", "origin")]
    # the September rebalance is decided at the 31 August origin, before the change
    seen = dec["rebalance"] <= pd.Timestamp("2021-09-01")
    np.testing.assert_allclose(
        dec.loc[seen, cols].to_numpy(dtype=float), dec2.loc[seen, cols].to_numpy(dtype=float)
    )
    before = daily["date"] < pd.Timestamp("2021-09-01")
    np.testing.assert_allclose(daily.loc[before, "pnl_total"], daily2.loc[before, "pnl_total"])
    # and the change is real: later months differ
    assert not np.allclose(
        dec.loc[~seen, "ex_ante_es_usd"].to_numpy(), dec2.loc[~seen, "ex_ante_es_usd"].to_numpy()
    )


def test_full_hedge_of_a_constant_book_loses_only_the_spread() -> None:
    # equal rates everywhere: the forward equals spot, so there is no carry; a constant
    # exposure hedged in full has no residual risk, whatever the spot path
    md = _market(usd_rate=3.0, brl_rate=3.0)
    flat = np.tile(md.exposure_fcy[0], (len(md.calendar), 1))
    md = replace(md, exposure_fcy=flat)
    cfg = _config(exposure_input="actual", policies=("unhedged", "full_hedge"))
    daily, _ = policy.simulate_policies(md, cfg)
    full = daily[daily["policy"] == "full_hedge"]
    monthly = full.groupby("rebalance")[["pnl_total", "pnl_spread", "pnl_carry"]].sum()
    assert (monthly["pnl_carry"].abs() < 1e-6).all()
    np.testing.assert_allclose(monthly["pnl_total"], monthly["pnl_spread"], atol=1e-6)
    assert (monthly["pnl_spread"] < 0).all()
    unhedged = daily[daily["policy"] == "unhedged"].groupby("rebalance")["pnl_total"].sum()
    assert unhedged.abs().mean() > 20 * monthly["pnl_total"].abs().mean()
