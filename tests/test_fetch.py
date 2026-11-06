from collections.abc import Sequence
from datetime import date

import pandas as pd
import pytest

from fx_treasury_risk.data import fetch as fetch_mod
from fx_treasury_risk.data.base import FetchResult
from fx_treasury_risk.data.cache import SeriesCache
from fx_treasury_risk.data.http import OfflineError
from fx_treasury_risk.data.registry import SeriesSpec, by_key

SPECS = [by_key("fred:DEXUSEU"), by_key("fred:DEXUSUK"), by_key("boc:FXUSDCAD")]


def _series(v: float) -> pd.Series:
    return pd.Series([v, v + 0.01], index=pd.to_datetime(["2020-01-01", "2020-01-02"]))


def test_cache_first_then_fetch_then_refresh(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    calls: list[list[str]] = []

    def fake_fred(specs: Sequence[SeriesSpec], start: date) -> dict[str, FetchResult]:
        calls.append([s.series_id for s in specs])
        return {
            s.series_id: FetchResult(_series(1.0), "test://fred")
            for s in specs
            if s.series_id != "DEXUSUK"
        }

    def fake_boc(specs: Sequence[SeriesSpec], start: date) -> dict[str, FetchResult]:
        return {s.series_id: FetchResult(_series(1.3), "test://boc") for s in specs}

    monkeypatch.setitem(fetch_mod.FETCHERS, "fred", fake_fred)
    monkeypatch.setitem(fetch_mod.FETCHERS, "boc", fake_boc)
    cache = SeriesCache(tmp_path)

    out = {o.key: o for o in fetch_mod.fetch_all(cache, SPECS)}
    assert out["fred:DEXUSEU"].status == "fetched" and out["fred:DEXUSEU"].n_obs == 2
    assert out["fred:DEXUSUK"].status == "missing"  # not in the response, nothing cached
    assert out["boc:FXUSDCAD"].status == "fetched"

    out = {o.key: o for o in fetch_mod.fetch_all(cache, SPECS)}
    assert out["fred:DEXUSEU"].status == "cached"
    assert calls[-1] == ["DEXUSUK"]  # only the missing one is retried

    out = {o.key: o for o in fetch_mod.fetch_all(cache, SPECS, refresh=True)}
    assert out["fred:DEXUSEU"].status == "fetched"
    assert sorted(calls[-1]) == ["DEXUSEU", "DEXUSUK"]


def test_failed_fetch_keeps_existing_cache(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    cache = SeriesCache(tmp_path)
    cache.write("fred", "DEXUSEU", _series(1.0), url="test://old")

    def boom(specs: Sequence[SeriesSpec], start: date) -> dict[str, FetchResult]:
        raise ConnectionError("network down")

    monkeypatch.setitem(fetch_mod.FETCHERS, "fred", boom)
    out = {
        o.key: o
        for o in fetch_mod.fetch_all(
            cache, [by_key("fred:DEXUSEU"), by_key("fred:DEXUSUK")], refresh=True
        )
    }
    assert out["fred:DEXUSEU"].status == "cached" and "ConnectionError" in out["fred:DEXUSEU"].error
    assert out["fred:DEXUSUK"].status == "failed"
    assert cache.read("fred", "DEXUSEU").iloc[0] == 1.0


def test_offline_guard_blocks_network(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from fx_treasury_risk.data import http

    monkeypatch.setenv("FXRISK_OFFLINE", "1")
    with pytest.raises(OfflineError):
        http.get("https://example.test/never")
    # fetch_all degrades to a per-series "failed" outcome instead of crashing
    cache = SeriesCache(tmp_path)
    out = fetch_mod.fetch_all(cache, [by_key("fred:DEXUSEU")], sources=["fred"])
    assert out[0].status == "failed" and "FXRISK_OFFLINE" in out[0].error
