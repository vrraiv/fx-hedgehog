"""Risk engine against textbook cases."""

import numpy as np
import pandas as pd
import pytest
from scipy import stats

from fx_treasury_risk.risk import covariance as cv
from fx_treasury_risk.risk import stress, var_es


def _gaussian_returns(n: int = 4000, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    corr = np.array([[1.0, 0.5, 0.0], [0.5, 1.0, 0.0], [0.0, 0.0, 1.0]])
    vols = np.array([0.01, 0.02, 0.005])
    cov = corr * np.outer(vols, vols)
    x = rng.multivariate_normal(np.zeros(3), cov, size=n)
    idx = pd.bdate_range("2005-01-03", periods=n)
    return pd.DataFrame(x, index=idx, columns=["A", "B", "C"])


def test_parametric_normal_matches_textbook() -> None:
    # single exposure of USD 1m with daily vol 1%: 99% 1-day VaR = 2.326 * 10,000
    cov = pd.DataFrame([[0.01**2]], index=["A"], columns=["A"])
    w = pd.Series({"A": 1_000_000.0})
    m = var_es.parametric_normal(w, cov, 1, 0.99, "test", 100)
    assert m.var_usd == pytest.approx(2.3263 * 10_000, rel=1e-4)
    assert m.es_usd == pytest.approx(2.6652 * 10_000, rel=1e-3)  # phi(z)/(1-a) = 2.665
    # 10-day: sqrt(10) scaling; a short exposure has the same VaR
    m10 = var_es.parametric_normal(w, cov, 10, 0.99, "test", 100)
    assert m10.var_usd == pytest.approx(m.var_usd * np.sqrt(10))
    assert var_es.parametric_normal(-w, cov, 1, 0.99, "test", 100).var_usd == pytest.approx(
        m.var_usd
    )


def test_parametric_normal_diversification() -> None:
    cov = pd.DataFrame(np.diag([0.01**2, 0.01**2]), index=["A", "B"], columns=["A", "B"])
    w = pd.Series({"A": 1e6, "B": 1e6})
    both = var_es.parametric_normal(w, cov, 1, 0.95, "t", 1).var_usd
    one = var_es.parametric_normal(w[["A"]], cov.loc[["A"], ["A"]], 1, 0.95, "t", 1).var_usd
    assert both == pytest.approx(one * np.sqrt(2))


def test_student_t_es_formula_and_limit() -> None:
    # with nu large the t formulas converge to the normal ones
    r = _gaussian_returns()
    cov = cv.sample_cov(r)
    w = pd.Series({"A": 1e6, "B": 0.0, "C": 0.0})
    normal = var_es.parametric_normal(w, cov, 1, 0.99, "s", len(r))
    t = var_es.parametric_student_t(w, cov, r, 1, 0.99, "s", window=4000)
    assert abs(t.var_usd / normal.var_usd - 1) < 0.08
    assert abs(t.es_usd / normal.es_usd - 1) < 0.10
    # closed form against numerical integration for a fat tail
    nu, alpha, sigma = 4.0, 0.99, 1.0
    q = stats.t.ppf(alpha, nu)
    scale = sigma * np.sqrt((nu - 2) / nu)
    es_formula = scale * stats.t.pdf(q, nu) * (nu + q**2) / ((nu - 1) * (1 - alpha))
    xs = np.linspace(q, 200, 400_000)
    es_numeric = scale * np.trapezoid(xs * stats.t.pdf(xs, nu), xs) / (1 - alpha)
    assert es_formula == pytest.approx(es_numeric, rel=1e-3)


def test_historical_var_on_known_sample() -> None:
    r = _gaussian_returns()
    w = pd.Series({"A": 1e6, "B": 0.0, "C": 0.0})
    m = var_es.historical(w, r, 1, 0.99, window=4000)
    # exp-1 of log returns: loss quantile close to the normal 2.326% of 1m
    assert m.var_usd == pytest.approx(23_263, rel=0.08)
    assert m.es_usd > m.var_usd
    assert m.n_obs == 4000


def test_ewma_cov_and_ledoit_wolf_sanity() -> None:
    r = _gaussian_returns()
    s = cv.sample_cov(r)
    assert s.loc["A", "A"] == pytest.approx(1e-4, rel=0.1)
    assert cv.cov_to_corr(s).loc["A", "B"] == pytest.approx(0.5, abs=0.05)
    e = cv.ewma_cov(r, 0.94)
    assert e.shape == (3, 3) and np.allclose(e, e.T)
    lw, delta = cv.ledoit_wolf_cov(r)
    assert 0.0 <= delta <= 1.0
    # shrinkage pulls variances toward their mean and correlations toward zero
    assert abs(cv.cov_to_corr(lw).loc["A", "B"]) <= abs(cv.cov_to_corr(s).loc["A", "B"]) + 1e-12
    assert np.trace(lw.to_numpy()) == pytest.approx(np.trace(s.to_numpy()), rel=1e-2)
    path = cv.ewma_cov_path(r, 0.94)
    assert path.shape == (len(r), 3, 3)
    assert np.allclose(path[-1], e.to_numpy())


def test_monte_carlo_agrees_with_parametric_for_gaussian_like_data() -> None:
    r = _gaussian_returns(n=3000, seed=3)
    w = pd.Series({"A": 1e6, "B": -5e5, "C": 2e6})
    cov = cv.ewma_cov(r, 0.94)
    normal = var_es.parametric_normal(w, cov, 1, 0.95, "ewma_0.94", 3000)
    mc = var_es.monte_carlo_t(w, r, 1, 0.95, 0.94, n_paths=40_000, seed=1, window=3000)
    assert abs(mc.var_usd / normal.var_usd - 1) < 0.10
    assert mc.cov_method == "ewma_0.94" and "nu_copula" in mc.params


def test_risk_table_is_tidy() -> None:
    r = _gaussian_returns(n=1500)
    w = pd.Series({"A": 1e6, "B": 1e6, "C": 1e6})
    t = var_es.risk_table(w, r, horizons=(1, 10), confidences=(0.95,), window=1000, mc_paths=2000)
    assert {"method", "cov_method", "horizon_days", "confidence", "var_usd", "es_usd"} <= set(
        t.columns
    )
    assert (t["es_usd"] >= t["var_usd"] * 0.999).all()
    assert set(t["method"]) == {"historical", "parametric_normal", "parametric_t", "monte_carlo_t"}
    assert len(t[t.horizon_days == 10]) == len(t[t.horizon_days == 1])


def test_conditional_shock_propagation() -> None:
    cov = pd.DataFrame([[0.01, 0.009], [0.009, 0.01]], index=["A", "B"], columns=["A", "B"])
    full = stress.conditional_shock({"A": -0.10}, cov, propagate=True)
    assert full["A"] == -0.10 and full["B"] == pytest.approx(-0.09)  # beta = 0.9
    flat = stress.conditional_shock({"A": -0.10}, cov, propagate=False)
    assert flat["B"] == 0


def test_replay_returns_and_stress_table() -> None:
    idx = pd.bdate_range("2015-01-05", periods=10)
    px = pd.DataFrame({"A": np.linspace(1.0, 1.1, 10), "B": np.linspace(2.0, 1.8, 10)}, index=idx)
    w = stress.HistoricalWindow("x", idx[0].date(), idx[-1].date(), "")
    rr = stress.replay_returns(px, w)
    assert rr["A"] == pytest.approx(np.log(1.1)) and rr["B"] == pytest.approx(np.log(0.9))
    r = np.log(px).diff().dropna()
    expo = pd.Series({"A": 1e6, "B": 1e6})
    # monkeypatch the module windows to one that exists in this toy sample
    old = stress.HISTORICAL_WINDOWS
    stress.HISTORICAL_WINDOWS = (w,)
    try:
        t = stress.stress_table(expo, px, r)
    finally:
        stress.HISTORICAL_WINDOWS = old
    hist = t[t.kind == "historical"].iloc[0]
    assert hist.pnl_usd == pytest.approx(1e6 * (0.1 - 0.1), abs=1)
    usd_up = t[t.scenario == "usd_up_10"].iloc[0]
    assert usd_up.pnl_usd == pytest.approx(2e6 * (np.exp(-0.1) - 1))


def test_implied_moves_lists_unnamed_currencies_by_size() -> None:
    shock = pd.Series({"JPY": 0.10, "BRL": 0.017, "AUD": 0.039, "EUR": 0.036, "INR": 0.006})
    text = stress.implied_moves(shock, {"JPY": 0.10})
    assert text == "AUD +3.9%, EUR +3.6%, BRL +1.7%"
