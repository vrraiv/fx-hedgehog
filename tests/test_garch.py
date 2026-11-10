"""GARCH(1,1) fit and the volatility path used by the VaR backtest."""

from __future__ import annotations

import numpy as np

from fx_treasury_risk.risk import garch


def _simulate(n: int, alpha: float, beta: float, seed: int = 3) -> np.ndarray:
    rng = np.random.default_rng(seed)
    target = 1e-4
    omega = target * (1 - alpha - beta)
    h = target
    out = np.empty(n)
    for t in range(n):
        out[t] = np.sqrt(h) * rng.standard_normal()
        h = omega + alpha * out[t] ** 2 + beta * h
    return out


def test_filter_matches_the_recursion() -> None:
    r = np.array([0.01, -0.02, 0.005])
    h = garch.filter_variance(r, 0.1, 0.8, 1e-4)
    omega = 1e-4 * 0.1
    expect = [1e-4]
    for x in r:
        expect.append(omega + 0.1 * x**2 + 0.8 * expect[-1])
    assert np.allclose(h, expect)


def test_fit_recovers_known_parameters() -> None:
    r = _simulate(4000, 0.08, 0.90)
    fit = garch.fit_garch(r)
    assert fit.converged
    assert abs(fit.alpha - 0.08) < 0.03
    assert abs(fit.alpha + fit.beta - 0.98) < 0.015


def test_fit_on_constant_variance_stays_stationary() -> None:
    r = np.random.default_rng(1).standard_normal(1000) * 0.01
    fit = garch.fit_garch(r)
    assert fit.alpha >= 0 and fit.beta >= 0 and fit.alpha + fit.beta < 1


def test_vol_path_has_no_look_ahead() -> None:
    r = np.column_stack([_simulate(900, 0.08, 0.9, seed=s) for s in (1, 2)])
    base = garch.garch_vol_path(r, window=600, min_obs=300, refit_every=50)
    shocked = r.copy()
    shocked[700:] *= 5  # changing the future must not change earlier forecasts
    alt = garch.garch_vol_path(shocked, window=600, min_obs=300, refit_every=50)
    assert np.all(np.isnan(base.vol[:299]))
    assert np.allclose(base.vol[299:699], alt.vol[299:699])
    assert not np.allclose(base.vol[700:], alt.vol[700:])
    assert base.n_failed == 0 and base.n_fits == 2 * len(range(299, 900, 50))
