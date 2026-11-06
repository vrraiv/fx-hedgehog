from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from fx_treasury_risk.data.cache import SeriesCache, normalize_series


def test_normalize_sorts_dedupes_and_drops_nan() -> None:
    s = pd.Series(
        [1.0, np.nan, 3.0, 2.0, 2.5],
        index=["2020-01-03", "2020-01-04", "2020-01-01", "2020-01-02", "2020-01-02"],
    )
    out = normalize_series(s, "X")
    assert list(out.index.strftime("%Y-%m-%d")) == ["2020-01-01", "2020-01-02", "2020-01-03"]
    assert out.loc["2020-01-02"] == 2.5  # last duplicate wins
    assert out.name == "X" and out.index.name == "date" and out.dtype == "float64"


def test_write_then_read_roundtrip_and_manifest(tmp_path: Path) -> None:
    cache = SeriesCache(tmp_path)
    s = pd.Series([1.1, 1.2, 1.3], index=pd.to_datetime(["2020-01-01", "2020-01-02", "2020-01-03"]))
    entry = cache.write("fred", "DEXUSEU", s, url="https://example.test/x", note="n")
    assert cache.has("fred", "DEXUSEU")
    assert entry.n_obs == 3 and entry.first_date == "2020-01-01" and entry.last_date == "2020-01-03"
    assert entry.retrieved_at.endswith("+00:00")
    back = cache.read("fred", "DEXUSEU")
    pd.testing.assert_series_equal(back, normalize_series(s, "DEXUSEU"))
    text = cache.path("fred", "DEXUSEU").read_text()
    assert text.splitlines()[0] == "date,value"
    assert cache.manifest()["fred:DEXUSEU"].sha256 == entry.sha256


def test_refuses_empty_series(tmp_path: Path) -> None:
    cache = SeriesCache(tmp_path)
    with pytest.raises(ValueError):
        cache.write("fred", "EMPTY", pd.Series(dtype=float), url="u")


def test_read_long_stacks_all_series(tmp_path: Path) -> None:
    cache = SeriesCache(tmp_path)
    idx = pd.to_datetime(["2020-01-01", "2020-01-02"])
    cache.write("fred", "A", pd.Series([1.0, 2.0], index=idx), url="u")
    cache.write("boc", "B", pd.Series([3.0, 4.0], index=idx), url="u")
    long = cache.read_long()
    assert len(long) == 4
    assert set(long["source"]) == {"fred", "boc"}
    assert list(long.columns) == ["source", "series_id", "date", "value"]
