"""Optimizer against hand-reasoned two- and three-currency cases."""

import numpy as np
import pytest
from scipy import stats

from fx_treasury_risk.hedge import optimizer as opt


def _problem(
    exposure: list[float],
    cost: list[float],
    budget: float,
    corr: float = 0.0,
    vol: float = 0.01,
    spread: float = 0.0,
) -> opt.HedgeProblem:
    k = len(exposure)
    c = np.full((k, k), corr) + (1 - corr) * np.eye(k)
    cov = c * vol**2
    return opt.HedgeProblem(
        ccys=[f"C{i}" for i in range(k)],
        exposure_usd=np.array(exposure, dtype=float),
        cov_daily=cov,
        horizon_days=21,
        confidence=0.99,
        nu=5.0,
        es_budget_usd=budget,
        cost_rate=np.array(cost, dtype=float),
        spread_bp=np.full(k, spread),
        tenor_days=30,
    )


def test_es_multiplier_limits() -> None:
    normal = stats.norm.pdf(stats.norm.ppf(0.99)) / 0.01
    assert opt.es_multiplier(1e6, 0.99) == pytest.approx(normal, rel=1e-3)
    assert opt.es_multiplier(4.0, 0.99) > normal  # fat tails raise ES for the same sigma


def test_full_hedge_has_zero_es_and_unhedged_matches_formula() -> None:
    p = _problem([1e6, 1e6], [0.02, 0.02], budget=1e4)
    assert p.residual_es(np.ones(2)) == pytest.approx(0.0, abs=1e-6)
    w = p.exposure_usd
    sigma = np.sqrt(w @ p.cov_horizon @ w)
    assert p.residual_es(np.zeros(2)) == pytest.approx(p.k_es * sigma)


def test_cheaper_currency_is_hedged_first() -> None:
    # equal exposures and vols, independent; C1 is twice as costly to hedge as C0
    p = _problem(
        [1e6, 1e6],
        [0.01, 0.02],
        budget=0.6 * _problem([1e6, 1e6], [0.01, 0.02], 1).residual_es(np.zeros(2)),
    )
    sol = opt.optimize_hedge(p)
    assert sol.binding
    assert sol.residual_es_usd == pytest.approx(p.es_budget_usd, rel=1e-4)
    assert sol.ratios["C0"] > sol.ratios["C1"]
    # the hedge of a long exposure is a sale: negative notional
    assert (sol.notional_usd <= 0).all()


def test_symmetric_problem_gives_equal_ratios_and_budget_binds() -> None:
    p = _problem([2e6, 2e6, 2e6], [0.03, 0.03, 0.03], budget=1.0)
    unhedged = p.residual_es(np.zeros(3))
    p = opt.HedgeProblem(**{**p.__dict__, "es_budget_usd": 0.5 * unhedged})
    sol = opt.optimize_hedge(p)
    assert np.allclose(sol.ratios.to_numpy(), sol.ratios.mean(), atol=1e-3)
    assert sol.ratios.mean() == pytest.approx(0.5, abs=1e-3)  # ES is linear in (1 - h) here


def test_negative_carry_currency_is_hedged_even_with_slack_budget() -> None:
    # C1 earns carry when hedged (cost rate negative): the optimizer hedges it fully
    # regardless of the budget, and leaves the costly C0 alone when the budget allows
    p = _problem([1e6, 1e6], [0.03, -0.02], budget=1e12)
    sol = opt.optimize_hedge(p)
    assert sol.ratios["C1"] == pytest.approx(1.0, abs=1e-4)
    assert sol.ratios["C0"] == pytest.approx(0.0, abs=1e-4)
    assert not sol.binding


def test_short_exposure_is_bought_forward() -> None:
    p = _problem([-1e6, 1e6], [0.02, 0.02], budget=0.0)
    sol = opt.optimize_hedge(p)
    assert sol.ratios.to_numpy() == pytest.approx([1.0, 1.0], abs=1e-4)
    assert sol.notional_usd["C0"] > 0 and sol.notional_usd["C1"] < 0


def test_spread_and_turnover_costs_are_accounted() -> None:
    p = _problem([1e6, 1e6], [0.0, 0.0], budget=1e12, spread=10.0)
    sol = opt.optimize_hedge(p, h_prev=np.array([0.5, 0.5]), turnover_penalty_bp=5.0)
    # with zero carry, hedging only costs spread: stay unhedged ... except the turnover
    # penalty pulls towards the previous 0.5 ratios; spread (10bp) beats penalty (5bp)
    assert sol.ratios.max() < 0.51
    assert sol.spread_cost_usd == pytest.approx(10 / 1e4 * np.abs(sol.notional_usd).sum())


def test_min_ticket_zeroes_small_hedges() -> None:
    p = _problem(
        [1e6, 2e4],
        [0.01, 0.01],
        budget=0.9 * _problem([1e6, 2e4], [0.01, 0.01], 1).residual_es(np.zeros(2)),
    )
    sol = opt.optimize_hedge(p, min_ticket_usd=50_000)
    assert sol.ratios["C1"] == 0.0


def test_frontier_is_monotone() -> None:
    p = _problem([1e6, 2e6, 1.5e6], [0.01, 0.03, -0.01], budget=1.0, corr=0.3)
    f = opt.frontier(p, n_points=8)
    assert (np.diff(f["residual_es_usd"]) >= -1e-6).all()
    assert (np.diff(f["carry_cost_usd"]) <= 1e-6).all()  # more risk allowed -> cheaper
    assert f.iloc[0]["residual_es_usd"] == pytest.approx(0.0, abs=1e-6)
