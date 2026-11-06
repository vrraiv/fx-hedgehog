"""ECB Data Portal loader for euro reference exchange rates.

Dataflow ``EXR``; key ``D.<CCY>.EUR.SP00.A`` = daily, CCY per EUR, spot reference rate,
average. Several currencies can be requested at once with ``+``::

    https://data-api.ecb.europa.eu/service/data/EXR/D.USD+GBP.EUR.SP00.A?format=csvdata&startPeriod=2010-01-04

The CSV has one row per observation with ``KEY`` (``EXR.D.USD.EUR.SP00.A``), ``TIME_PERIOD``
and ``OBS_VALUE`` columns. Reference rates are fixed at 14:15 CET.
"""

from __future__ import annotations

import io
from collections.abc import Sequence
from datetime import date

import pandas as pd

from fx_treasury_risk.data import http
from fx_treasury_risk.data.base import FetchResult
from fx_treasury_risk.data.cache import normalize_series
from fx_treasury_risk.data.registry import SeriesSpec

BASE_URL = "https://data-api.ecb.europa.eu/service/data/EXR"


def parse_csvdata(text: str) -> dict[str, pd.Series]:
    """Split an ECB ``csvdata`` response into one series per key (``EXR.`` prefix removed)."""
    df = pd.read_csv(io.StringIO(text), usecols=["KEY", "TIME_PERIOD", "OBS_VALUE"])
    out: dict[str, pd.Series] = {}
    for key, grp in df.groupby("KEY"):
        sid = str(key).removeprefix("EXR.")
        out[sid] = normalize_series(
            pd.Series(grp["OBS_VALUE"].to_numpy(), index=grp["TIME_PERIOD"]), sid
        )
    return out


def _ccy_of(series_id: str) -> str:
    # "D.USD.EUR.SP00.A" -> "USD"
    return series_id.split(".")[1]


def fetch_many(specs: Sequence[SeriesSpec], start: date) -> dict[str, FetchResult]:
    """Fetch all requested reference rates in a single request."""
    ccys = "+".join(_ccy_of(s.series_id) for s in specs)
    url = f"{BASE_URL}/D.{ccys}.EUR.SP00.A"
    resp = http.get(url, params={"format": "csvdata", "startPeriod": start.isoformat()})
    parsed = parse_csvdata(resp.text)
    full_url = f"{url}?format=csvdata&startPeriod={start.isoformat()}"
    return {
        s.series_id: FetchResult(parsed[s.series_id], full_url)
        for s in specs
        if s.series_id in parsed
    }
