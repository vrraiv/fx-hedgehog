"""Stress tests: historical replays and hypothetical shocks.

*Historical replay* applies the actual log change of every currency over a named window
to today's exposures. *Hypothetical* scenarios shock a subset of currencies and propagate
the shock to the others by their conditional expectation under a Gaussian model with the
EWMA covariance: ``E[r_O | r_S] = Sigma_OS Sigma_SS^{-1} r_S``. That is the documented
correlation assumption; the alternative of shocking only the named currencies is also
reported (``propagate=False``) so the reader can see what the assumption adds.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import numpy as np
import pandas as pd

from fx_treasury_risk.risk import covariance as cv
from fx_treasury_risk.risk.var_es import pnl_from_log_returns


@dataclass(frozen=True)
class HistoricalWindow:
    """A named episode; the shock is ln(S_end / S_start) per currency."""

    name: str
    start: date
    end: date
    note: str


HISTORICAL_WINDOWS: tuple[HistoricalWindow, ...] = (
    HistoricalWindow(
        "chf_depeg_2015",
        date(2015, 1, 14),
        date(2015, 1, 16),
        "SNB removes the EUR/CHF floor, 15 Jan 2015",
    ),
    HistoricalWindow(
        "brexit_2016", date(2016, 6, 23), date(2016, 6, 27), "UK referendum result, 24-27 Jun 2016"
    ),
    HistoricalWindow(
        "covid_2020", date(2020, 3, 6), date(2020, 3, 20), "dash for dollars, March 2020"
    ),
    HistoricalWindow(
        "usd_surge_2022",
        date(2022, 8, 1),
        date(2022, 9, 27),
        "Fed hiking cycle, DXY peak 27 Sep 2022",
    ),
    HistoricalWindow(
        "taper_tantrum_2013",
        date(2013, 5, 22),
        date(2013, 8, 30),
        "EM selloff after Bernanke's taper remarks (BRL, INR)",
    ),
)


@dataclass(frozen=True)
class HypotheticalShock:
    """Named currencies move by the given log-return; others follow by conditional expectation."""

    name: str
    shocks: dict[str, float]  # ccy -> log return of usd_per_fcy (negative = currency weakens)
    note: str


HYPOTHETICAL_SHOCKS: tuple[HypotheticalShock, ...] = (
    HypotheticalShock(
        "usd_up_10", {}, "every exposure currency weakens 10% against USD, no propagation needed"
    ),
    HypotheticalShock(
        "em_selloff_15",
        {"BRL": -0.15, "MXN": -0.15, "INR": -0.10},
        "EM selloff; majors follow conditionally",
    ),
    HypotheticalShock(
        "eur_down_10", {"EUR": -0.10}, "euro-specific shock; others follow conditionally"
    ),
    HypotheticalShock(
        "jpy_up_10", {"JPY": 0.10}, "yen safe-haven rally; others follow conditionally"
    ),
)


def replay_returns(prices: pd.DataFrame, window: HistoricalWindow) -> pd.Series:
    """Log change of each currency from the last price on/before ``start`` to ``end``."""
    px = prices.sort_index()
    p0 = px[px.index <= pd.Timestamp(window.start)].iloc[-1]
    p1 = px[px.index <= pd.Timestamp(window.end)].iloc[-1]
    return pd.Series(np.log(p1.to_numpy(dtype=float) / p0.to_numpy(dtype=float)), index=px.columns)


def conditional_shock(
    shocks: dict[str, float], cov: pd.DataFrame, propagate: bool = True
) -> pd.Series:
    """Full shock vector: named currencies as given, others by conditional expectation."""
    ccys = [str(c) for c in cov.index]
    named = [c for c in ccys if c in shocks]
    others = [c for c in ccys if c not in shocks]
    values: dict[str, float] = dict.fromkeys(ccys, 0.0)
    values.update({c: shocks[c] for c in named})
    if propagate and named and others:
        sigma = cov.to_numpy()
        i_s = [ccys.index(c) for c in named]
        i_o = [ccys.index(c) for c in others]
        s_os = sigma[np.ix_(i_o, i_s)]
        s_ss = sigma[np.ix_(i_s, i_s)]
        r_s = np.array([shocks[c] for c in named])
        r_o = s_os @ np.linalg.solve(s_ss, r_s)
        values.update(dict(zip(others, (float(x) for x in r_o), strict=True)))
    return pd.Series([values[c] for c in ccys], index=ccys, dtype=float)


def stress_table(
    exposure_usd: pd.Series,
    prices: pd.DataFrame,
    returns: pd.DataFrame,
    lam: float = 0.94,
) -> pd.DataFrame:
    """Historical replays and hypothetical shocks, one row each, P&L in USD."""
    ccys = list(exposure_usd.index)
    cov = cv.ewma_cov(returns[ccys].dropna(), lam)
    rows: list[dict[str, object]] = []
    for w in HISTORICAL_WINDOWS:
        shock = replay_returns(prices[ccys], w)
        pnl = pnl_from_log_returns(exposure_usd, shock.to_numpy()[None, :])[0]
        worst = str(shock.abs().idxmax())
        rows.append(
            {
                "scenario": w.name,
                "kind": "historical",
                "window": f"{w.start} to {w.end}",
                "note": w.note,
                "pnl_usd": float(pnl),
                "largest_move": f"{worst} {100 * shock[worst]:+.1f}%",
                "propagated": False,
            }
        )
    for h in HYPOTHETICAL_SHOCKS:
        if h.name == "usd_up_10":
            shock = pd.Series(-0.10, index=ccys)
            variants = [(shock, False)]
        else:
            variants = [
                (conditional_shock(h.shocks, cov, True), True),
                (conditional_shock(h.shocks, cov, False), False),
            ]
        for shock, propagated in variants:
            pnl = pnl_from_log_returns(exposure_usd, shock.to_numpy()[None, :])[0]
            top = str(shock.abs().idxmax())
            rows.append(
                {
                    "scenario": h.name,
                    "kind": "hypothetical",
                    "window": "",
                    "note": h.note,
                    "pnl_usd": float(pnl),
                    "largest_move": f"{top} {100 * shock[top]:+.1f}%",
                    "propagated": propagated,
                }
            )
    return pd.DataFrame(rows)
