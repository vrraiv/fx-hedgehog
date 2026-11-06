"""Bank of Canada Valet API loader.

Docs: https://www.bankofcanada.ca/valet/docs. One request can carry many series, e.g.::

    https://www.bankofcanada.ca/valet/observations/FXUSDCAD,FXEURCAD/json?start_date=2010-01-04

Response shape (abridged)::

    {"observations": [{"d": "2017-01-03", "FXUSDCAD": {"v": "1.3435"}, "FXEURCAD": {"v": "1.4"}}]}

All FX series are quoted as Canadian dollars per one unit of the foreign currency. The
current ``FX*`` series are *daily averages* (start 2017-01-03); the legacy ``IEXE*`` noon
series end 2017-04-28. Where both exist the SQL layer prefers the current vintage.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from typing import Any

import pandas as pd

from fx_treasury_risk.data import http
from fx_treasury_risk.data.base import FetchResult
from fx_treasury_risk.data.cache import normalize_series
from fx_treasury_risk.data.registry import SeriesSpec

BASE_URL = "https://www.bankofcanada.ca/valet/observations"
_BATCH = 20


def parse_observations(payload: dict[str, Any]) -> dict[str, pd.Series]:
    """Turn a Valet ``observations`` JSON document into one series per id.

    Missing or empty values (``{"v": ""}``) are dropped.
    """
    rows: dict[str, dict[str, float]] = {}
    for obs in payload.get("observations", []):
        d = obs["d"]
        for sid, cell in obs.items():
            if sid == "d" or not isinstance(cell, dict):
                continue
            v = cell.get("v")
            if v in (None, ""):
                continue
            rows.setdefault(sid, {})[d] = float(v)
    return {sid: normalize_series(pd.Series(vals), sid) for sid, vals in rows.items()}


def fetch_many(specs: Sequence[SeriesSpec], start: date) -> dict[str, FetchResult]:
    """Fetch all BoC series in batches of up to 20 ids per request."""
    out: dict[str, FetchResult] = {}
    ids = [s.series_id for s in specs]
    for i in range(0, len(ids), _BATCH):
        batch = ids[i : i + _BATCH]
        url = f"{BASE_URL}/{','.join(batch)}/json"
        resp = http.get(url, params={"start_date": start.isoformat()})
        parsed = parse_observations(resp.json())
        for sid in batch:
            if sid in parsed and not parsed[sid].empty:
                out[sid] = FetchResult(parsed[sid], f"{url}?start_date={start.isoformat()}")
    return out
