"""FRED loader (Federal Reserve Bank of St. Louis).

Two transports, chosen at runtime:

* With ``FRED_API_KEY`` set: the official JSON API
  ``https://api.stlouisfed.org/fred/series/observations``.
* Without a key: the public CSV download behind every FRED chart,
  ``https://fred.stlouisfed.org/graph/fredgraph.csv?id=DEXUSEU``. This is not a documented
  API; it is used only so the cache can be refreshed by a reviewer without registering,
  and the committed cache is the primary path for CI (see ADR-0004).

Missing values are published as ``"."`` and are dropped.
"""

from __future__ import annotations

import io
from collections.abc import Sequence
from datetime import date
from typing import Any

import pandas as pd

from fx_treasury_risk import config
from fx_treasury_risk.data import http
from fx_treasury_risk.data.base import FetchResult
from fx_treasury_risk.data.cache import normalize_series
from fx_treasury_risk.data.registry import SeriesSpec

API_URL = "https://api.stlouisfed.org/fred/series/observations"
CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"


def parse_fredgraph_csv(text: str, series_id: str) -> pd.Series:
    """Parse the ``observation_date,<ID>`` CSV served by ``fredgraph.csv``."""
    df = pd.read_csv(io.StringIO(text), na_values=["."])
    date_col = df.columns[0]
    if series_id not in df.columns:
        raise ValueError(f"column {series_id!r} not in FRED CSV columns {list(df.columns)}")
    return normalize_series(pd.Series(df[series_id].to_numpy(), index=df[date_col]), series_id)


def parse_api_json(payload: dict[str, Any], series_id: str) -> pd.Series:
    """Parse the ``observations`` array returned by the FRED JSON API."""
    obs = payload.get("observations", [])
    s = pd.Series({o["date"]: o["value"] for o in obs if o.get("value") not in (None, ".")})
    return normalize_series(s, series_id)


def fetch_many(specs: Sequence[SeriesSpec], start: date) -> dict[str, FetchResult]:
    """Fetch each FRED series (the API has no multi-series endpoint)."""
    key = config.fred_api_key()
    out: dict[str, FetchResult] = {}
    for spec in specs:
        sid = spec.series_id
        if key:
            params = {
                "series_id": sid,
                "api_key": key,
                "file_type": "json",
                "observation_start": start.isoformat(),
            }
            resp = http.get(API_URL, params=params)
            series = parse_api_json(resp.json(), sid)
            url = f"{API_URL}?series_id={sid}&observation_start={start.isoformat()}"  # key redacted
            note = "FRED JSON API"
        else:
            params = {"id": sid, "cosd": start.isoformat()}
            resp = http.get(CSV_URL, params=params)
            series = parse_fredgraph_csv(resp.text, sid)
            url = f"{CSV_URL}?id={sid}&cosd={start.isoformat()}"
            note = "FRED keyless CSV download"
        if not series.empty:
            out[sid] = FetchResult(series, url, note)
    return out
