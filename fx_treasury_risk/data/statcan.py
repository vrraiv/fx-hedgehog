"""Statistics Canada Web Data Service loader (retail trade, table 20-10-0056-01).

Endpoint: ``POST https://www150.statcan.gc.ca/t1/wds/rest/getDataFromVectorsAndLatestNPeriods``
with body ``[{"vectorId": 1446859481, "latestN": 300}]``. Each result carries
``vectorDataPoint`` rows with ``refPer`` (first day of the month) and ``value``.

Values are in thousands of Canadian dollars (``scalarFactorCode`` 3). The table starts in
2017-01, which is enough to calibrate annual seasonality for the synthetic flows.
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

URL = "https://www150.statcan.gc.ca/t1/wds/rest/getDataFromVectorsAndLatestNPeriods"


def parse_vectors(payload: list[dict[str, Any]]) -> dict[str, pd.Series]:
    """Parse the WDS response into one series per vector id (``v<id>``)."""
    out: dict[str, pd.Series] = {}
    for item in payload:
        if item.get("status") != "SUCCESS":
            continue
        obj = item["object"]
        sid = f"v{obj['vectorId']}"
        points = {
            p["refPer"]: p["value"]
            for p in obj.get("vectorDataPoint", [])
            if p.get("value") is not None
        }
        out[sid] = normalize_series(pd.Series(points), sid)
    return out


def fetch_many(specs: Sequence[SeriesSpec], start: date) -> dict[str, FetchResult]:
    """Fetch all vectors in one POST; ``latestN`` is sized to cover ``start`` to today."""
    months = (date.today().year - start.year) * 12 + (date.today().month - start.month) + 2
    body = [{"vectorId": int(s.series_id.lstrip("v")), "latestN": months} for s in specs]
    resp = http.post_json(URL, body)
    parsed = parse_vectors(resp.json())
    return {
        s.series_id: FetchResult(
            parsed[s.series_id][parsed[s.series_id].index >= pd.Timestamp(start)], URL
        )
        for s in specs
        if s.series_id in parsed
    }
