"""ECB Data Portal loader: euro reference exchange rates and the deposit facility rate.

Exchange rates: dataflow ``EXR``; key ``D.<CCY>.EUR.SP00.A`` = daily, CCY per EUR, spot
reference rate, fixed at 14:15 CET. Registered without the dataflow prefix, and several
currencies are requested at once with ``+``::

    https://data-api.ecb.europa.eu/service/data/EXR/D.USD+GBP.EUR.SP00.A?format=csvdata&startPeriod=2010-01-04

Other dataflows (the deposit facility rate, ``FM.D.U2.EUR.4F.KR.DFR.LEV``) are registered
with the dataflow as the first dot-separated part and fetched one key at a time.

Every ``csvdata`` response has one row per observation with ``KEY`` (dataflow included,
e.g. ``EXR.D.USD.EUR.SP00.A``), ``TIME_PERIOD`` and ``OBS_VALUE`` columns.
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

SERVICE_URL = "https://data-api.ecb.europa.eu/service/data"
BASE_URL = f"{SERVICE_URL}/EXR"


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


def _is_exr(series_id: str) -> bool:
    # exchange rates are registered without their dataflow: "D.USD.EUR.SP00.A"
    return series_id.startswith("D.")


def fetch_many(specs: Sequence[SeriesSpec], start: date) -> dict[str, FetchResult]:
    """Fetch every exchange rate in one request and every other key in one request each."""
    out: dict[str, FetchResult] = {}
    exr = [s for s in specs if _is_exr(s.series_id)]
    if exr:
        ccys = "+".join(_ccy_of(s.series_id) for s in exr)
        url = f"{BASE_URL}/D.{ccys}.EUR.SP00.A"
        resp = http.get(url, params={"format": "csvdata", "startPeriod": start.isoformat()})
        parsed = parse_csvdata(resp.text)
        full_url = f"{url}?format=csvdata&startPeriod={start.isoformat()}"
        out.update(
            {
                s.series_id: FetchResult(parsed[s.series_id], full_url)
                for s in exr
                if s.series_id in parsed
            }
        )
    for s in specs:
        if _is_exr(s.series_id):
            continue
        flow, _, key = s.series_id.partition(".")
        url = f"{SERVICE_URL}/{flow}/{key}"
        resp = http.get(url, params={"format": "csvdata", "startPeriod": start.isoformat()})
        parsed = parse_csvdata(resp.text)
        if s.series_id in parsed:
            full_url = f"{url}?format=csvdata&startPeriod={start.isoformat()}"
            out[s.series_id] = FetchResult(parsed[s.series_id], full_url)
    return out
