"""BIS statistics loader (SDMX REST API v2).

Two dataflows are used:

* ``WS_EER`` - effective exchange rates. Key ``D.N.B.<AREA>`` = daily, nominal, broad basket.
* ``WS_CBPOL`` - central bank policy rates. Key ``D.<AREA>`` = daily, end of period.

Example::

    https://stats.bis.org/api/v2/data/dataflow/BIS/WS_EER/1.0/D.N.B.US+XM?format=csv&startPeriod=2010-01-04

The CSV carries the key dimensions as columns (``FREQ``, ``REF_AREA`` ...) plus
``TIME_PERIOD`` and ``OBS_VALUE``; we rebuild the series id from those columns.
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

BASE_URL = "https://stats.bis.org/api/v2/data/dataflow/BIS"
_FLOW_BY_CATEGORY = {"eer": "WS_EER", "policy_rate": "WS_CBPOL"}
_KEY_COLUMNS = {
    "WS_EER": ["FREQ", "EER_TYPE", "EER_BASKET", "REF_AREA"],
    "WS_CBPOL": ["FREQ", "REF_AREA"],
}


def parse_csv(text: str, flow: str) -> dict[str, pd.Series]:
    """Split a BIS CSV response into one series per key (e.g. ``D.N.B.US``)."""
    df = pd.read_csv(io.StringIO(text))
    key_cols = _KEY_COLUMNS[flow]
    df["_key"] = df[key_cols].astype(str).agg(".".join, axis=1)
    out: dict[str, pd.Series] = {}
    for key, grp in df.groupby("_key"):
        sid = str(key)
        out[sid] = normalize_series(
            pd.Series(grp["OBS_VALUE"].to_numpy(), index=grp["TIME_PERIOD"]), sid
        )
    return out


def fetch_many(specs: Sequence[SeriesSpec], start: date) -> dict[str, FetchResult]:
    """One request per dataflow, all areas joined with ``+``."""
    out: dict[str, FetchResult] = {}
    for category, flow in _FLOW_BY_CATEGORY.items():
        flow_specs = [s for s in specs if s.category == category]
        if not flow_specs:
            continue
        # keys share every dimension but the last (REF_AREA), so join the areas with '+'
        prefix = flow_specs[0].series_id.rsplit(".", 1)[0]
        areas = "+".join(s.series_id.rsplit(".", 1)[1] for s in flow_specs)
        url = f"{BASE_URL}/{flow}/1.0/{prefix}.{areas}"
        resp = http.get(url, params={"format": "csv", "startPeriod": start.isoformat()})
        parsed = parse_csv(resp.text, flow)
        full_url = f"{url}?format=csv&startPeriod={start.isoformat()}"
        for s in flow_specs:
            if s.series_id in parsed:
                out[s.series_id] = FetchResult(parsed[s.series_id], full_url)
    return out
