"""Orchestrates ``fxrisk fetch``: cache-first retrieval of every registered series."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Literal

from fx_treasury_risk import config
from fx_treasury_risk.data import bis, boc, ecb, fred, statcan
from fx_treasury_risk.data.base import Fetcher
from fx_treasury_risk.data.cache import SeriesCache
from fx_treasury_risk.data.http import OfflineError
from fx_treasury_risk.data.registry import ALL_SERIES, SeriesSpec, Source

log = logging.getLogger(__name__)

FETCHERS: dict[Source, Fetcher] = {
    "fred": fred.fetch_many,
    "boc": boc.fetch_many,
    "ecb": ecb.fetch_many,
    "bis": bis.fetch_many,
    "statcan": statcan.fetch_many,
}

Status = Literal["cached", "fetched", "failed", "missing"]


@dataclass(frozen=True)
class FetchOutcome:
    """What happened to one series during a fetch run."""

    key: str
    status: Status
    n_obs: int = 0
    last_date: str = ""
    error: str = ""


def fetch_all(
    cache: SeriesCache,
    specs: Sequence[SeriesSpec] = ALL_SERIES,
    *,
    start: date = config.DATA_START,
    refresh: bool = False,
    sources: Sequence[Source] | None = None,
) -> list[FetchOutcome]:
    """Populate the cache for ``specs``.

    Parameters
    ----------
    cache
        Target cache.
    specs
        Series to consider (defaults to the full registry).
    start
        First observation date requested from each source.
    refresh
        If False (default) series already in the cache are left untouched; if True every
        series is re-downloaded. A failed download never destroys an existing cache entry.
    sources
        Optional subset of sources to touch.

    Returns
    -------
    list[FetchOutcome]
        One outcome per spec, in registry order.
    """
    wanted = [s for s in specs if sources is None or s.source in sources]
    outcomes: dict[str, FetchOutcome] = {}
    for source, fetcher in FETCHERS.items():
        todo = [
            s
            for s in wanted
            if s.source == source and (refresh or not cache.has(s.source, s.series_id))
        ]
        for s in wanted:
            if s.source == source and s not in todo:
                e = cache.entry(s.source, s.series_id)
                assert e is not None
                outcomes[s.key] = FetchOutcome(s.key, "cached", e.n_obs, e.last_date)
        if not todo:
            continue
        log.info("fetching %d series from %s", len(todo), source)
        try:
            results = fetcher(todo, start)
        except OfflineError as exc:
            results = {}
            err = str(exc)
        except Exception as exc:
            log.error("fetch from %s failed: %s", source, exc)
            results = {}
            err = f"{type(exc).__name__}: {exc}"
        else:
            err = ""
        for s in todo:
            if s.series_id in results:
                r = results[s.series_id]
                entry = cache.write(s.source, s.series_id, r.series, url=r.url, note=r.note)
                outcomes[s.key] = FetchOutcome(s.key, "fetched", entry.n_obs, entry.last_date)
            elif cache.has(s.source, s.series_id):
                e = cache.entry(s.source, s.series_id)
                assert e is not None
                outcomes[s.key] = FetchOutcome(
                    s.key, "cached", e.n_obs, e.last_date, error=err or "not in response"
                )
            else:
                outcomes[s.key] = FetchOutcome(
                    s.key, "missing" if not err else "failed", error=err or "not in response"
                )
    return [outcomes[s.key] for s in wanted]
