# ADR-0004: Committed CSV cache with a JSON manifest; keyless FRED fallback

**Status:** accepted, 2026-11-05

## Context

CI must pass on a clean checkout with no API key. Reports must be auditable: every number
traceable to a source and a retrieval time. The author wants the data to be inspectable
without tooling.

## Decision

* **Format:** one CSV per series (`date,value`), under `data/cache/<source>/<id>.csv`,
  plus `data/cache/manifest.json` recording for each series the source URL, UTC retrieval
  timestamp, first/last date, row count and SHA-256 of the file. Values are written with
  10 significant digits. Total size is 4.5 MB for 78 series over 2010-2026; CSV diffs
  are readable in pull requests, which matters for the weekly refresh job (milestone 4).
* **Cache-first:** `fxrisk fetch` downloads only series missing from the cache;
  `--refresh` re-downloads everything. A failed download never overwrites a cached file.
* **Offline guard:** `FXRISK_OFFLINE=1` makes any network attempt raise; CI sets it.
* **FRED without a key:** the loader uses the official JSON API when `FRED_API_KEY` is
  set and otherwise the public CSV download behind every FRED chart
  (`fred.stlouisfed.org/graph/fredgraph.csv?id=...`). That endpoint is undocumented but
  has been stable for over a decade; it is used only so a reviewer can refresh without
  registering. The manifest `note` field records which transport produced each file.
* **Retrieval date in reports:** the README and the decision report print the manifest's
  newest retrieval date.

## Consequences

* The repository carries data; a refresh produces a reviewable diff.
* Parquet can replace CSV later without changing the loader interface (backlog B6).
