"""Shared types for source loaders."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date

import pandas as pd

from fx_treasury_risk.data.registry import SeriesSpec


@dataclass(frozen=True)
class FetchResult:
    """One freshly downloaded series and where it came from."""

    series: pd.Series
    url: str
    note: str = ""


#: Signature every source loader exposes: specs for *that* source, start date -> results
#: keyed by series_id. Loaders batch requests where the API allows it.
Fetcher = Callable[[Sequence[SeriesSpec], date], dict[str, FetchResult]]
