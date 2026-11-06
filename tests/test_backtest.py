"""Coverage and ES tests on simulated data with known properties."""

import numpy as np
import pandas as pd
from scipy import stats

from fx_treasury_risk.backtest import coverage
from fx_treasury_risk.backtest.var_backtest import forecast_series


def test_kupiec_accepts_correct_and_rejects_wrong_rate() -> None:
    rng = np.random.default_rng(0)
    ok = rng.random(2000) < 0.01
    _lr, p = coverage.kupiec_pof(ok, 0.99)
    assert p > 0.05
    bad = rng.random(2000) < 0.04
    _lr, p = coverage.kupiec_pof(bad, 0.99)
    assert p < 1e-6
    # Kupiec's own table: at 99% over 250 days the 5% non-rejection region is 0..7
    # exceptions (Kupiec 1995, Table 1); 8 is outside it, 4 is inside it.
    exc = np.zeros(250, dtype=bool)
    exc[:8] = True
    lr8, p8 = coverage.kupiec_pof(exc, 0.99)
    exc[:] = False
    exc[:4] = True
    lr4, p4 = coverage.kupiec_pof(exc, 0.99)
    assert lr8 > stats.chi2.ppf(0.95, 1) > lr4
    assert p8 < 0.05 < p4


def test_christoffersen_detects_clustering() -> None:
    rng = np.random.default_rng(1)
    iid = rng.random(3000) < 0.05
    _, p_iid = coverage.christoffersen_independence(iid)
    assert p_iid > 0.01
    # clustered: exceptions come in runs of 5
    clustered = np.zeros(3000, dtype=bool)
    starts = rng.choice(2990, size=30, replace=False)
    for s in starts:
        clustered[s : s + 5] = True
    _, p_cl = coverage.christoffersen_independence(clustered)
    assert p_cl < 1e-6


def test_traffic_light_zones() -> None:
    assert coverage.traffic_light(4) == "green"
    assert coverage.traffic_light(5) == "yellow"
    assert coverage.traffic_light(10) == "red"


def test_acerbi_szekely_zero_under_h0_and_positive_when_es_understated() -> None:
    rng = np.random.default_rng(2)
    t = 20_000
    alpha = 0.975
    z = stats.norm.ppf(alpha)
    sigma_true = 1.0
    loss = rng.standard_normal(t) * sigma_true

    def model(sigma: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        s = np.full(t, sigma)
        var = z * s
        es = s * stats.norm.pdf(z) / (1 - alpha)
        sampler = rng.standard_normal((300, t)) * s  # the model's own predictive draws
        return var, es, sampler

    # correct model: both statistics near zero, p-values unremarkable
    var, es, sampler = model(sigma_true)
    z1 = coverage.acerbi_szekely_z1(loss, var, es)
    z2 = coverage.acerbi_szekely_z2(loss, var, es, alpha)
    assert abs(z1) < 0.05 and abs(z2) < 0.05
    p1, p2 = coverage.simulate_z_pvalues(sampler, var, es, alpha, z1, z2)
    assert 0.05 < p2 < 0.95 and 0.05 < p1 < 0.95

    # a model whose volatility is 30% too low understates ES: positive Z, tiny p-values
    var_l, es_l, sampler_l = model(0.7 * sigma_true)
    z1_l = coverage.acerbi_szekely_z1(loss, var_l, es_l)
    z2_l = coverage.acerbi_szekely_z2(loss, var_l, es_l, alpha)
    assert z2_l > 0.3 and z1_l > 0.1
    p1_l, p2_l = coverage.simulate_z_pvalues(sampler_l, var_l, es_l, alpha, z1_l, z2_l)
    assert p2_l < 0.01 and p1_l < 0.01


def test_forecast_series_coverage_on_gaussian_world() -> None:
    rng = np.random.default_rng(5)
    n = 2200
    idx = pd.bdate_range("2010-01-04", periods=n)
    r = pd.DataFrame(rng.standard_normal((n, 2)) * 0.01, index=idx, columns=["A", "B"])
    w = pd.DataFrame(1e6, index=idx, columns=["A", "B"])
    f = forecast_series(r, w, "normal_sample", 0.99, oos_start=idx[1000], window=1000, n_sims=50)
    assert len(f.loss) == n - 1000
    c = coverage.coverage_tests(f.loss, f.var, 0.99)
    assert c.kupiec_p > 0.01 and 0.003 < c.exception_rate < 0.025
    f2 = forecast_series(r, w, "historical", 0.95, oos_start=idx[1000], window=1000, n_sims=50)
    c2 = coverage.coverage_tests(f2.loss, f2.var, 0.95)
    assert 0.03 < c2.exception_rate < 0.075
    f3 = forecast_series(r, w, "t_ewma", 0.99, oos_start=idx[1000], window=1000, n_sims=50)
    assert np.all(f3.es > f3.var)
