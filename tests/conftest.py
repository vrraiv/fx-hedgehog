"""Shared fixtures: a small, internally consistent synthetic cache.

The mini cache contains three FX sources (FRED, BoC current + legacy, ECB) for EUR, JPY
and CAD built from one set of "true" USD rates, so every SQL conversion can be checked
against a hand-computed number. It also holds two rate series so the rates check runs.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from fx_treasury_risk import config
from fx_treasury_risk.data.cache import SeriesCache
from fx_treasury_risk.data.registry import SeriesSpec, by_key

FIXTURES = Path(__file__).parent / "fixtures"

MINI_KEYS = [
    "fred:DEXUSEU",
    "fred:DEXJPUS",
    "fred:DEXCAUS",
    "fred:DTB3",
    "boc:FXUSDCAD",
    "boc:FXEURCAD",
    "boc:FXJPYCAD",
    "boc:IEXE0101",
    "boc:EUROCAE01",
    "boc:IEXE0701",
    "boc:TB.CDN.90D.MID",
    "ecb:D.USD.EUR.SP00.A",
    "ecb:D.JPY.EUR.SP00.A",
    "ecb:D.CAD.EUR.SP00.A",
]
MINI_SPECS: list[SeriesSpec] = [by_key(k) for k in MINI_KEYS]
MINI_CCYS = ("EUR", "JPY", "CAD")


@dataclass
class MiniTruth:
    """The 'true' rates the mini cache was generated from (USD per FCY)."""

    dates: pd.DatetimeIndex  # NY business days with a FRED print
    usd_per_eur: pd.Series
    usd_per_jpy: pd.Series
    cad_per_usd: pd.Series
    legacy_dates: pd.DatetimeIndex
    current_dates: pd.DatetimeIndex
    legacy_bump: float = 1.0 + 2e-4  # legacy BoC series differ from current by 2 bp


def build_mini_cache(cache_dir: Path, *, fred_gap_dates: list[str] | None = None) -> MiniTruth:
    """Write the synthetic mini cache and return the truth used to build it."""
    dates = pd.bdate_range("2016-12-01", "2017-01-31")
    n = len(dates)
    rng = np.random.default_rng(0)
    usd_per_eur = pd.Series(1.05 * np.exp(np.cumsum(rng.normal(0, 0.004, n))), index=dates)
    usd_per_jpy = pd.Series((1 / 115.0) * np.exp(np.cumsum(rng.normal(0, 0.004, n))), index=dates)
    cad_per_usd = pd.Series(1.33 * np.exp(np.cumsum(rng.normal(0, 0.003, n))), index=dates)

    legacy_dates = dates[dates <= "2017-01-15"]  # legacy ends mid-January in the mini world
    current_dates = dates[dates >= "2017-01-03"]  # current starts 2017-01-03 as at the BoC
    bump = 1.0 + 2e-4

    cache = SeriesCache(cache_dir)
    url = "test://mini"
    fred_dates = dates.drop(pd.to_datetime(fred_gap_dates or []), errors="ignore")
    cache.write("fred", "DEXUSEU", usd_per_eur[fred_dates], url=url)
    cache.write("fred", "DEXJPUS", 1 / usd_per_jpy[fred_dates], url=url)
    cache.write("fred", "DEXCAUS", cad_per_usd[fred_dates], url=url)
    cache.write("fred", "DTB3", pd.Series(0.5, index=dates), url=url)

    cache.write("boc", "FXUSDCAD", cad_per_usd[current_dates], url=url)
    cache.write("boc", "FXEURCAD", (usd_per_eur * cad_per_usd)[current_dates], url=url)
    cache.write("boc", "FXJPYCAD", (usd_per_jpy * cad_per_usd)[current_dates], url=url)
    cache.write("boc", "IEXE0101", (cad_per_usd * bump)[legacy_dates], url=url)
    cache.write("boc", "EUROCAE01", (usd_per_eur * cad_per_usd * bump)[legacy_dates], url=url)
    cache.write("boc", "IEXE0701", (usd_per_jpy * cad_per_usd * bump)[legacy_dates], url=url)
    cache.write("boc", "TB.CDN.90D.MID", pd.Series(0.48, index=dates), url=url)

    cache.write("ecb", "D.USD.EUR.SP00.A", usd_per_eur, url=url)
    cache.write("ecb", "D.JPY.EUR.SP00.A", usd_per_eur / usd_per_jpy, url=url)
    cache.write("ecb", "D.CAD.EUR.SP00.A", usd_per_eur * cad_per_usd, url=url)

    return MiniTruth(
        dates=fred_dates,
        usd_per_eur=usd_per_eur,
        usd_per_jpy=usd_per_jpy,
        cad_per_usd=cad_per_usd,
        legacy_dates=legacy_dates,
        current_dates=current_dates,
        legacy_bump=bump,
    )


@pytest.fixture
def tmp_paths(tmp_path: Path) -> config.Paths:
    return config.Paths(data_dir=tmp_path / "data", reports_dir=tmp_path / "reports")


@pytest.fixture
def mini(tmp_paths: config.Paths) -> MiniTruth:
    return build_mini_cache(tmp_paths.cache_dir)
