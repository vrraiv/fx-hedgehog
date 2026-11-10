"""On-disk cache of source series: one CSV per series plus a JSON manifest.

Layout::

    data/cache/
      manifest.json                 retrieval metadata, one entry per series
      fred/DEXUSEU.csv              date,value
      boc/FXUSDCAD.csv
      ...

The cache is committed to git so that CI and anyone cloning the repo can run the whole
pipeline without network access or API keys. The manifest records *when* and *from where*
each series was retrieved, which is what makes a report auditable: every number can be
traced to a source URL and a retrieval timestamp.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

MANIFEST_NAME = "manifest.json"
_CSV_FLOAT_FORMAT = "%.10g"


@dataclass(frozen=True)
class CacheEntry:
    """Provenance record for one cached series."""

    source: str
    series_id: str
    url: str
    retrieved_at: str  # ISO-8601, UTC
    first_date: str  # YYYY-MM-DD
    last_date: str  # YYYY-MM-DD
    n_obs: int
    sha256: str
    note: str = ""

    @property
    def key(self) -> str:
        """``source:series_id``."""
        return f"{self.source}:{self.series_id}"

    @property
    def retrieved_date(self) -> pd.Timestamp:
        """Retrieval timestamp as a tz-naive UTC pandas Timestamp (date precision)."""
        return pd.Timestamp(self.retrieved_at).tz_convert(None).normalize()

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> CacheEntry:
        """Rebuild from a manifest record."""
        return cls(**{k: d[k] for k in cls.__dataclass_fields__ if k in d})


def normalize_series(s: pd.Series, name: str) -> pd.Series:
    """Coerce a raw series into the cache format.

    Index becomes a sorted, unique, tz-naive ``DatetimeIndex`` named ``date`` (time part
    dropped); values become ``float64`` with NaNs removed; ``name`` is set to the series id.
    """
    idx = pd.to_datetime(s.index, errors="coerce")
    out = pd.Series(
        pd.to_numeric(s.to_numpy(), errors="coerce"), index=idx, name=name, dtype="float64"
    )
    out = out[np.asarray(~pd.isna(out.index))]
    out.index = pd.DatetimeIndex(out.index).normalize()
    out = out.dropna()
    out = out[~out.index.duplicated(keep="last")].sort_index()
    out.index.name = "date"
    return out


class SeriesCache:
    """Read/write access to the cache directory and its manifest."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._manifest_path = self.root / MANIFEST_NAME

    # ---- paths -----------------------------------------------------------------------
    def path(self, source: str, series_id: str) -> Path:
        """CSV path for a series (created lazily on write)."""
        return self.root / source / f"{series_id}.csv"

    # ---- manifest --------------------------------------------------------------------
    def manifest(self) -> dict[str, CacheEntry]:
        """All manifest entries keyed by ``source:series_id``."""
        if not self._manifest_path.exists():
            return {}
        raw = json.loads(self._manifest_path.read_text(encoding="utf-8"))
        return {k: CacheEntry.from_dict(v) for k, v in raw.get("series", {}).items()}

    def _save_manifest(self, entries: dict[str, CacheEntry]) -> None:
        payload = {
            "format": 1,
            "updated_at": _now_iso(),
            "series": {k: asdict(entries[k]) for k in sorted(entries)},
        }
        tmp = self._manifest_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8", newline="\n")
        tmp.replace(self._manifest_path)

    def entry(self, source: str, series_id: str) -> CacheEntry | None:
        """Manifest entry for a series, or None if absent."""
        return self.manifest().get(f"{source}:{series_id}")

    def has(self, source: str, series_id: str) -> bool:
        """True if both the CSV and its manifest entry exist."""
        return self.path(source, series_id).exists() and self.entry(source, series_id) is not None

    # ---- data ------------------------------------------------------------------------
    def read(self, source: str, series_id: str) -> pd.Series:
        """Load a cached series as a float series indexed by date."""
        path = self.path(source, series_id)
        if not path.exists():
            raise FileNotFoundError(f"no cached data for {source}:{series_id} at {path}")
        df = pd.read_csv(path, parse_dates=["date"])
        return normalize_series(pd.Series(df["value"].to_numpy(), index=df["date"]), series_id)

    def write(
        self, source: str, series_id: str, series: pd.Series, *, url: str, note: str = ""
    ) -> CacheEntry:
        """Write a series to CSV and record its provenance in the manifest."""
        s = normalize_series(series, series_id)
        if s.empty:
            raise ValueError(f"refusing to cache empty series {source}:{series_id}")
        path = self.path(source, series_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        csv_text = s.rename("value").to_csv(
            index=True,
            index_label="date",
            date_format="%Y-%m-%d",
            float_format=_CSV_FLOAT_FORMAT,
            lineterminator="\n",
        )
        # newline="\n": on Windows, text mode would turn every line ending into CRLF, and
        # DuckDB's multi-file CSV reader takes the line ending from the first file it reads
        path.write_text(csv_text, encoding="utf-8", newline="\n")
        entry = CacheEntry(
            source=source,
            series_id=series_id,
            url=url,
            retrieved_at=_now_iso(),
            first_date=s.index[0].strftime("%Y-%m-%d"),
            last_date=s.index[-1].strftime("%Y-%m-%d"),
            n_obs=len(s),
            sha256=hashlib.sha256(csv_text.encode("utf-8")).hexdigest(),
            note=note,
        )
        entries = self.manifest()
        entries[entry.key] = entry
        self._save_manifest(entries)
        return entry

    def read_long(self) -> pd.DataFrame:
        """Every cached series stacked in long form: ``source, series_id, date, value``."""
        frames = []
        for entry in self.manifest().values():
            s = self.read(entry.source, entry.series_id)
            frames.append(
                pd.DataFrame(
                    {
                        "source": entry.source,
                        "series_id": entry.series_id,
                        "date": s.index,
                        "value": s.to_numpy(),
                    }
                )
            )
        if not frames:
            return pd.DataFrame(
                {"source": [], "series_id": [], "date": pd.to_datetime([]), "value": []}
            )
        return pd.concat(frames, ignore_index=True)


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()
