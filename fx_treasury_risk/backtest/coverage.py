"""Statistical tests of VaR and ES forecasts against realised P&L.

All tests take a series of realised losses ``loss_t`` (positive = money lost) and the
forecasts ``var_t``, ``es_t`` made at ``t-1`` for day ``t``, at confidence ``alpha``.

* Kupiec (1995) proportion-of-failures test: are there too many / too few exceptions?
* Christoffersen (1998) independence test: do exceptions cluster?
* Conditional coverage: the two combined (LR_cc = LR_uc + LR_ind).
* Basel traffic light: exceptions in the last 250 days at 99%.
* Consecutive exceptions: the count behind a Christoffersen failure, so a rejection
  driven by one episode can be told apart from a model that is persistently slow.
* Acerbi and Szekely (2014) Z1 and Z2 tests of Expected Shortfall, with p-values from
  Monte Carlo under the model's own predictive distribution. The statistics are written
  in terms of *losses*, so they are zero under H0 and **positive when realised tail losses
  exceed the forecast ES** (the original paper uses P&L and the opposite sign).
* FZ0 scoring function (Patton, Ziegel & Chen, 2019) for ranking VaR/ES models jointly,
  and the Diebold-Mariano (1995) test of equal expected score.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import stats


@dataclass(frozen=True)
class CoverageResult:
    """Outcome of the VaR coverage tests for one (method, confidence)."""

    n_obs: int
    n_exceptions: int
    expected_exceptions: float
    exception_rate: float
    kupiec_lr: float
    kupiec_p: float
    christoffersen_lr: float
    christoffersen_p: float
    n_consecutive: int  # exceptions that follow an exception on the previous day
    conditional_lr: float
    conditional_p: float
    traffic_light: str


def kupiec_pof(exceptions: np.ndarray, alpha: float) -> tuple[float, float]:
    """Likelihood-ratio test that the exception rate equals ``1 - alpha``.

    ``LR = -2 ln[ (1-p)^(n-x) p^x / ((1-x/n)^(n-x) (x/n)^x) ]``, chi-square with 1 d.f.
    """
    n = len(exceptions)
    x = int(exceptions.sum())
    p = 1 - alpha
    if x == 0:
        lr = -2 * n * np.log(1 - p)
    elif x == n:
        lr = -2 * n * np.log(p)
    else:
        phat = x / n
        lr = -2 * (
            (n - x) * np.log(1 - p) + x * np.log(p) - (n - x) * np.log(1 - phat) - x * np.log(phat)
        )
    return float(lr), float(stats.chi2.sf(lr, 1))


def christoffersen_independence(exceptions: np.ndarray) -> tuple[float, float]:
    """LR test that the probability of an exception does not depend on yesterday's.

    Counts transitions ``n_ij`` (from state i to state j); under independence the two
    conditional probabilities are equal. Chi-square with 1 d.f.
    """
    e = exceptions.astype(int)
    prev, cur = e[:-1], e[1:]
    n00 = int(((prev == 0) & (cur == 0)).sum())
    n01 = int(((prev == 0) & (cur == 1)).sum())
    n10 = int(((prev == 1) & (cur == 0)).sum())
    n11 = int(((prev == 1) & (cur == 1)).sum())
    p01 = n01 / (n00 + n01) if (n00 + n01) else 0.0
    p11 = n11 / (n10 + n11) if (n10 + n11) else 0.0
    p = (n01 + n11) / (n00 + n01 + n10 + n11)

    def _ll(p0: float, p1: float) -> float:
        out = 0.0
        if n00:
            out += n00 * np.log(1 - p0)
        if n01:
            out += n01 * np.log(p0)
        if n10:
            out += n10 * np.log(1 - p1)
        if n11:
            out += n11 * np.log(p1)
        return out

    lr = -2 * (_ll(p, p) - _ll(p01, p11))
    lr = max(float(lr), 0.0)
    return lr, float(stats.chi2.sf(lr, 1))


def traffic_light(exceptions_last_250: int) -> str:
    """Basel Committee zones for 250 daily observations at 99%."""
    if exceptions_last_250 <= 4:
        return "green"
    if exceptions_last_250 <= 9:
        return "yellow"
    return "red"


def coverage_tests(loss: np.ndarray, var: np.ndarray, alpha: float) -> CoverageResult:
    """Run all VaR coverage tests on aligned arrays."""
    exc = loss > var
    n = len(exc)
    lr_uc, p_uc = kupiec_pof(exc, alpha)
    lr_ind, p_ind = christoffersen_independence(exc)
    lr_cc = lr_uc + lr_ind
    p_cc = float(stats.chi2.sf(lr_cc, 2))
    last = int(exc[-250:].sum())
    return CoverageResult(
        n_obs=n,
        n_exceptions=int(exc.sum()),
        expected_exceptions=float(n * (1 - alpha)),
        exception_rate=float(exc.mean()),
        kupiec_lr=lr_uc,
        kupiec_p=p_uc,
        christoffersen_lr=lr_ind,
        christoffersen_p=p_ind,
        n_consecutive=int((exc[1:] & exc[:-1]).sum()),
        conditional_lr=lr_cc,
        conditional_p=p_cc,
        traffic_light=traffic_light(last) if alpha >= 0.99 else "n/a",
    )


# ---------------------------------------------------------------------------------------
# Model ranking: FZ0 score and Diebold-Mariano
# ---------------------------------------------------------------------------------------
def fz0_score(loss: np.ndarray, var: np.ndarray, es: np.ndarray, alpha: float) -> np.ndarray:
    """Daily FZ0 loss of a (VaR, ES) forecast pair; lower is better.

    Patton, Ziegel & Chen (2019), eq. 6, rewritten for losses (positive VaR and ES):
    ``1[L > VaR] (L - VaR) / ((1 - alpha) ES) + VaR / ES + log(ES) - 1``. It is strictly
    consistent for the pair, so its mean ranks models on VaR and ES together and, unlike
    an exception count, uses every day of the sample. Differences between models do not
    depend on the currency unit (the ``log`` of a common scale cancels).
    """
    exc = loss > var
    out: np.ndarray = exc * (loss - var) / ((1 - alpha) * es) + var / es + np.log(es) - 1.0
    return out


def diebold_mariano(d: np.ndarray, lags: int | None = None) -> tuple[float, float]:
    """Test that the score differential ``d`` has mean zero; returns (statistic, p-value).

    Newey-West long-run variance with Bartlett weights, ``lags`` defaulting to
    ``floor(T^(1/3))``; two-sided normal p-value.
    """
    x = np.asarray(d, dtype=float)
    t = len(x)
    lags = int(np.floor(t ** (1 / 3))) if lags is None else lags
    u = x - x.mean()
    lrv = float(u @ u) / t
    for k in range(1, lags + 1):
        lrv += 2 * (1 - k / (lags + 1)) * float(u[k:] @ u[:-k]) / t
    if lrv <= 0:
        return float("nan"), float("nan")
    stat = float(x.mean() / np.sqrt(lrv / t))
    return stat, float(2 * stats.norm.sf(abs(stat)))


# ---------------------------------------------------------------------------------------
# Expected Shortfall: Acerbi & Szekely (2014)
# ---------------------------------------------------------------------------------------
def acerbi_szekely_z1(loss: np.ndarray, var: np.ndarray, es: np.ndarray) -> float:
    """Z1: mean of ``loss/ES`` on exception days, minus one.

    Zero under H0, positive if the ES is too small. Tests the ES magnitude *conditional*
    on the VaR being breached (assumes the VaR itself is correct).
    """
    exc = loss > var
    if exc.sum() == 0:
        return float("nan")
    return float(np.mean(loss[exc] / es[exc]) - 1.0)


def acerbi_szekely_z2(loss: np.ndarray, var: np.ndarray, es: np.ndarray, alpha: float) -> float:
    """Z2: ``sum(loss * 1[exc] / ES) / (T (1-alpha))`` minus one.

    Jointly tests the exception frequency and the ES size.
    """
    exc = loss > var
    t = len(loss)
    return float(np.sum(loss * exc / es) / (t * (1 - alpha)) - 1.0)


def simulate_z_pvalues(
    sampler: np.ndarray,
    var: np.ndarray,
    es: np.ndarray,
    alpha: float,
    z1_obs: float,
    z2_obs: float,
) -> tuple[float, float]:
    """One-sided p-values for Z1 and Z2 from simulated losses under H0.

    ``sampler`` has shape (n_sims, T): losses drawn from each day's predictive
    distribution. The p-value is the share of simulations with Z at or below the
    observed value (small = realised tail losses larger than the model allows).
    """
    exc = sampler > var[None, :]
    n_exc = exc.sum(axis=1)
    ratio = np.where(exc, sampler / es[None, :], 0.0)
    with np.errstate(invalid="ignore", divide="ignore"):
        z1 = np.where(n_exc > 0, ratio.sum(axis=1) / np.maximum(n_exc, 1) - 1, np.nan)
        z2 = ratio.sum(axis=1) / (sampler.shape[1] * (1 - alpha)) - 1
    p1 = float(np.nanmean(z1 >= z1_obs)) if not np.isnan(z1_obs) else float("nan")
    p2 = float(np.mean(z2 >= z2_obs))
    return p1, p2


def summarise(results: pd.DataFrame) -> pd.DataFrame:
    """Add a one-word verdict per row: PASS if every p-value >= 0.05, else FAIL."""
    out = results.copy()
    candidates = ("kupiec_p", "christoffersen_p", "conditional_p", "z2_p")
    pcols = [c for c in candidates if c in out.columns]
    out["verdict"] = np.where((out[pcols] >= 0.05).all(axis=1), "PASS", "FAIL")
    return out
