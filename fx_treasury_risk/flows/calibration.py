"""Annual seasonality factors estimated from public retail-sales series.

For each country the ratio of the not-seasonally-adjusted series to the seasonally
adjusted one is, by construction, the statistical agency's own estimate of the seasonal
factor. Averaging that ratio by calendar month over the sample gives twelve multipliers
with mean one. This is the only data-calibrated input to the synthetic flows.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from fx_treasury_risk.data.cache import SeriesCache

#: (NSA series, SA series) per profile name
RETAIL_SERIES: dict[str, tuple[tuple[str, str], tuple[str, str]]] = {
    "US": (("fred", "RSXFSN"), ("fred", "RSXFS")),
    "CA": (("statcan", "v1446859481"), ("statcan", "v1446859483")),
}
CALIBRATION_START = "2012-01-01"


def monthly_factors(cache: SeriesCache, profile: str) -> np.ndarray:
    """Twelve multiplicative factors (Jan..Dec), mean exactly one."""
    (nsa_src, nsa_id), (sa_src, sa_id) = RETAIL_SERIES[profile]
    ratio = (cache.read(nsa_src, nsa_id) / cache.read(sa_src, sa_id)).dropna()
    ratio = ratio[ratio.index >= pd.Timestamp(CALIBRATION_START)]
    if len(ratio) < 36:
        raise ValueError(
            f"need at least 3 years of retail data for {profile}, got {len(ratio)} months"
        )
    by_month = ratio.groupby(pd.DatetimeIndex(ratio.index).month).mean()
    if len(by_month) != 12:
        raise ValueError(f"retail data for {profile} does not cover all 12 months")
    factors = by_month.sort_index().to_numpy(dtype=float)
    return factors / factors.mean()


def all_profiles(cache: SeriesCache) -> dict[str, np.ndarray]:
    """Factors for every profile in :data:`RETAIL_SERIES`."""
    return {p: monthly_factors(cache, p) for p in RETAIL_SERIES}
