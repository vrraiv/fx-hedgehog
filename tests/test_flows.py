"""The generator's aggregate statistics must match the YAML within tolerance."""

from datetime import date

import numpy as np
import pandas as pd
import pytest

from fx_treasury_risk import config
from fx_treasury_risk.data.cache import SeriesCache
from fx_treasury_risk.flows import calibration
from fx_treasury_risk.flows.config import FlowConfig, load_flow_config
from fx_treasury_risk.flows.generator import FLOW_TYPES, generate, generate_pair

FLAT = np.ones(12)


@pytest.fixture(scope="module")
def cfg() -> FlowConfig:
    return load_flow_config()


def _short(cfg: FlowConfig, years: int = 3, regimes: bool = False) -> FlowConfig:
    """A shorter sample; regimes (the 2020 shock) are dropped unless asked for."""
    return FlowConfig(
        **{
            **cfg.__dict__,
            "start": date(2018, 1, 1),
            "end": date(2018 + years, 12, 31),
            "regimes": cfg.regimes if regimes else (),
        }
    )


def test_config_loads_and_normalises(cfg: FlowConfig) -> None:
    assert abs(sum(cfg.weekly_seasonality) / 7 - 1) < 1e-12
    assert set(cfg.entities) == set(config.ENTITIES)
    assert all(abs(sum(cfg.settlement_lag(c).values()) - 1) < 1e-9 for c in ["EUR", "BRL", "INR"])


def test_conservation_per_pair(cfg: FlowConfig) -> None:
    c = _short(cfg)
    days = pd.date_range(c.start, c.end, freq="D")
    f = generate_pair(c, "EA", "EUR", FLAT, days)
    tot = f.groupby("flow_type")["amount"].sum()
    take, s, rr = c.take_rate, c.same_ccy_share("EUR"), c.refund_rate
    assert set(tot.index) <= set(FLOW_TYPES)
    # everything authorized settles (up to the few days of end effects)
    assert tot["settlement"] == pytest.approx(tot["auth"], rel=5e-3)
    assert tot["refund_paid"] == pytest.approx(rr * tot["auth"], rel=2e-2)
    assert tot["payable_accrual"] == pytest.approx((1 - take) * s * tot["auth"], rel=1e-9)
    # merchants are paid (1 - take) of settlements net of refunds, split by currency share
    merchant = (1 - take) * (tot["settlement"] - tot["refund_paid"])
    assert tot["payout_same"] + tot["payout_converted"] == pytest.approx(merchant, rel=1e-2)
    assert tot["payout_same"] / (tot["payout_same"] + tot["payout_converted"]) == pytest.approx(
        s, abs=1e-3
    )
    # fees net of refunded fees are swept
    assert tot["fee_sweep"] == pytest.approx(
        take * (tot["settlement"] - tot["refund_paid"]), rel=1e-2
    )


def test_components_return_to_zero(cfg: FlowConfig) -> None:
    """Cumulative signed flows per component (as the SQL computes them) stay bounded."""
    c = _short(cfg, years=4)
    days = pd.date_range(c.start, c.end, freq="D")
    f = generate_pair(c, "US", "BRL", FLAT, days)
    wide = f.pivot_table(index="date", columns="flow_type", values="amount", aggfunc="sum").fillna(
        0
    )
    in_flight = (wide["auth"] - wide["settlement"]).cumsum()
    balance = (
        wide["settlement"]
        - wide["payout_same"]
        - wide["payout_converted"]
        - wide["refund_paid"]
        - wide["fee_sweep"]
    ).cumsum()
    payable = (-wide["payable_accrual"] + wide["payout_same"] + wide["refund_clawback"]).cumsum()
    daily = wide["auth"].mean()
    # bounded by a few days of volume, not drifting with cumulative volume (~1500 days)
    assert in_flight.iloc[-60:].abs().max() < 8 * daily
    assert balance.iloc[-60:].abs().max() < 8 * daily
    assert payable.iloc[-60:].abs().max() < 8 * daily
    assert (in_flight >= -1e-6).all()
    assert (payable <= 1e-6).all()


def test_weekly_and_annual_seasonality_recovered(cfg: FlowConfig) -> None:
    c = _short(cfg, years=5)
    days = pd.date_range(c.start, c.end, freq="D")
    annual = np.array([0.8, 0.8, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.2, 1.4])
    annual = annual / annual.mean()
    f = generate_pair(c, "US", "JPY", annual, days)
    auth = f[f.flow_type == "auth"].set_index("date")["amount"]
    detrended = auth / np.exp(c.growth_annual_rate * (auth.index - auth.index[0]).days / 365.25)
    dow = detrended.groupby(detrended.index.day_of_week).mean()
    dow = dow / dow.mean()
    assert np.allclose(dow.to_numpy(), c.weekly_seasonality, atol=0.03)
    mon = detrended.groupby(detrended.index.month).mean()
    mon = mon / mon.mean()
    assert np.allclose(mon.to_numpy(), annual, atol=0.05)


def test_level_matches_config(cfg: FlowConfig) -> None:
    c = _short(cfg, years=2)
    days = pd.date_range(c.start, c.end, freq="D")
    f = generate_pair(c, "CA", "CAD", FLAT, days)
    auth = f[f.flow_type == "auth"].set_index("date")["amount"]
    growth = np.exp(c.growth_annual_rate * (auth.index - auth.index[0]).days / 365.25)
    assert (auth / growth).mean() == pytest.approx(
        c.entities["CA"].volumes_per_day["CAD"], rel=0.03
    )


def test_deterministic_and_pair_independent(cfg: FlowConfig) -> None:
    c = _short(cfg, years=1)
    days = pd.date_range(c.start, c.end, freq="D")
    a = generate_pair(c, "EA", "EUR", FLAT, days)
    b = generate_pair(c, "EA", "EUR", FLAT, days)
    pd.testing.assert_frame_equal(a, b)
    other = generate_pair(c, "EA", "GBP", FLAT, days)
    assert not np.allclose(
        a[a.flow_type == "auth"]["amount"].to_numpy() / c.entities["EA"].volumes_per_day["EUR"],
        other[other.flow_type == "auth"]["amount"].to_numpy()
        / c.entities["EA"].volumes_per_day["GBP"],
    )


def test_regime_multiplier_applies(cfg: FlowConfig) -> None:
    c = FlowConfig(**{**cfg.__dict__, "start": date(2020, 1, 1), "end": date(2020, 12, 31)})
    days = pd.date_range(c.start, c.end, freq="D")
    f = generate_pair(c, "EA", "EUR", FLAT, days)
    auth = f[f.flow_type == "auth"].set_index("date")["amount"]
    pre = auth["2020-02-01":"2020-03-10"].mean()
    during = auth["2020-03-20":"2020-05-25"].mean()
    assert 0.55 < during / pre < 0.78  # configured multiplier 0.65 plus noise and growth


def test_full_generate_shapes(cfg: FlowConfig) -> None:
    c = _short(cfg, years=1)
    profiles = {"US": FLAT, "CA": FLAT}
    f = generate(c, profiles)
    assert list(f.columns) == ["date", "entity", "ccy", "flow_type", "amount"]
    assert (f["amount"] > 0).all() or (
        f[f.flow_type.str.startswith("interco")]["amount"] >= 0
    ).all()
    assert set(f["entity"]) == set(c.entities)
    interco = f[f.flow_type == "interco_receivable"]
    assert set(interco["ccy"]) == {"CAD", "EUR", "GBP"} and (interco["entity"] == "US").all()


@pytest.mark.skipif(
    not (config.REPO_ROOT / "data" / "cache" / "manifest.json").exists(),
    reason="committed cache missing",
)
def test_calibration_from_cache_has_retail_shape() -> None:
    cache = SeriesCache(config.REPO_ROOT / "data" / "cache")
    us = calibration.monthly_factors(cache, "US")
    ca = calibration.monthly_factors(cache, "CA")
    for f in (us, ca):
        assert f.shape == (12,) and abs(f.mean() - 1) < 1e-12
        assert f[0] < 0.95 and f[1] < 0.95  # January and February are weak retail months
    assert us[11] > 1.08  # US December holiday season
