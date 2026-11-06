"""Project-wide constants and filesystem paths.

Nothing in here reads data. Paths can be redirected with environment variables so tests
and CI can run against a temporary directory:

* ``FXRISK_DATA_DIR``  - directory holding ``cache/`` and the DuckDB file (default ``data/``).
* ``FXRISK_REPORTS_DIR`` - where reports and alerts are written (default ``reports/``).
* ``FXRISK_OFFLINE`` - if set to a truthy value, any attempt to hit the network raises.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path

#: Reporting currency for every USD-translated figure in the system.
REPORTING_CCY = "USD"

#: Exposure currencies in scope for v1 (liquid majors plus a few EM currencies).
EXPOSURE_CCYS: tuple[str, ...] = (
    "EUR",
    "GBP",
    "CAD",
    "JPY",
    "AUD",
    "CHF",
    "MXN",
    "BRL",
    "INR",
    "SGD",
)

#: Stylized legal entities and their functional currencies.
ENTITIES: dict[str, str] = {"US": "USD", "CA": "CAD", "EA": "EUR", "UK": "GBP"}

#: First observation date requested from every source. Five years of history before the
#: 2015 out-of-sample window gives the covariance estimators a reasonable burn-in.
DATA_START = date(2010, 1, 4)

#: Risk horizons in trading days.
RISK_HORIZONS: tuple[int, ...] = (1, 10, 21)

#: Trading days per year used for annualizing (NY FX calendar is ~252 days).
TRADING_DAYS_PER_YEAR = 252

PACKAGE_ROOT = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_ROOT.parent
SQL_DIR = REPO_ROOT / "sql"


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Paths:
    """Resolved filesystem locations for one run."""

    data_dir: Path
    reports_dir: Path

    @property
    def cache_dir(self) -> Path:
        """Directory of cached source series (committed to git)."""
        return self.data_dir / "cache"

    @property
    def db_path(self) -> Path:
        """DuckDB database file; always rebuilt from the cache, never committed."""
        return self.data_dir / "fxrisk.duckdb"

    @property
    def figures_dir(self) -> Path:
        """Where report figures are written."""
        return self.reports_dir / "figures"

    @classmethod
    def from_env(cls) -> Paths:
        """Build paths from environment variables, falling back to the repo layout."""
        data_dir = Path(os.environ.get("FXRISK_DATA_DIR", REPO_ROOT / "data"))
        reports_dir = Path(os.environ.get("FXRISK_REPORTS_DIR", REPO_ROOT / "reports"))
        return cls(data_dir=data_dir, reports_dir=reports_dir)


def offline() -> bool:
    """True when network access is forbidden (``FXRISK_OFFLINE=1``)."""
    return _truthy(os.environ.get("FXRISK_OFFLINE"))


def load_dotenv(path: Path = REPO_ROOT / ".env") -> None:
    """Read ``KEY=VALUE`` lines from a git-ignored ``.env`` into the environment.

    Existing environment variables win; the file never overrides them. Blank lines and
    ``#`` comments are skipped. Deliberately minimal so no dependency is needed.
    """
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip().strip("'\"")
        if key and key not in os.environ:
            os.environ[key] = value


def fred_api_key() -> str | None:
    """FRED API key from the environment or ``.env``, or None (keyless CSV is used)."""
    load_dotenv()
    key = os.environ.get("FRED_API_KEY", "").strip()
    return key or None
