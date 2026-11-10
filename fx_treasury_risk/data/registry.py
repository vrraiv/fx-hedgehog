"""Catalogue of every external series the system uses.

Each :class:`SeriesSpec` records where a series comes from, what it measures and in which
quote convention. The SQL layer joins on this catalogue (as the ``series_catalog`` table) to
convert every FX quote to the house convention, USD per unit of foreign currency.

Quote conventions (``quote`` field):

* ``USD_PER_FCY`` - e.g. FRED ``DEXUSEU`` = US dollars per euro.
* ``FCY_PER_USD`` - e.g. FRED ``DEXJPUS`` = yen per US dollar.
* ``CAD_PER_FCY`` - every Bank of Canada FX series (Canadian dollars per unit of FCY).
* ``FCY_PER_EUR`` - ECB reference rates (units of FCY per euro).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Source = Literal["fred", "boc", "ecb", "bis", "statcan"]
Category = Literal["fx", "policy_rate", "eer", "retail"]
Quote = Literal["USD_PER_FCY", "FCY_PER_USD", "CAD_PER_FCY", "FCY_PER_EUR"]
Frequency = Literal["daily", "monthly"]


@dataclass(frozen=True)
class SeriesSpec:
    """Description of one external time series."""

    source: Source
    series_id: str
    category: Category
    ccy: str
    description: str
    frequency: Frequency = "daily"
    quote: Quote | None = None
    #: free-text unit, e.g. "percent", "CAD per USD", "USD millions"
    unit: str = ""
    #: a series whose last observation is older than this many days at retrieval is stale
    stale_after_days: int = 10
    #: BoC publishes two vintages of its FX series; "legacy" ends 2017-04-28
    vintage: Literal["current", "legacy"] = "current"
    #: only for rates: approximate tenor in months (0 = overnight / policy)
    tenor_months: int = 0

    @property
    def key(self) -> str:
        """Unique key ``source:series_id`` used in the cache manifest."""
        return f"{self.source}:{self.series_id}"


def _fx(
    source: Source,
    series_id: str,
    ccy: str,
    description: str,
    quote: Quote,
    unit: str,
    *,
    vintage: Literal["current", "legacy"] = "current",
    stale_after_days: int = 10,
) -> SeriesSpec:
    return SeriesSpec(
        source,
        series_id,
        "fx",
        ccy,
        description,
        quote=quote,
        unit=unit,
        vintage=vintage,
        stale_after_days=stale_after_days,
    )


# ---------------------------------------------------------------------------------------
# FRED (Federal Reserve Bank of St. Louis). H.10 FX rates are noon buying rates in New York,
# released weekly on Monday for the previous week, hence the 14-day staleness allowance.
# ---------------------------------------------------------------------------------------
_FRED_FX: list[SeriesSpec] = [
    _fx(
        "fred",
        "DEXUSEU",
        "EUR",
        "US dollars per euro (H.10 noon NY)",
        "USD_PER_FCY",
        "USD per EUR",
        stale_after_days=14,
    ),
    _fx(
        "fred",
        "DEXUSUK",
        "GBP",
        "US dollars per pound sterling (H.10)",
        "USD_PER_FCY",
        "USD per GBP",
        stale_after_days=14,
    ),
    _fx(
        "fred",
        "DEXCAUS",
        "CAD",
        "Canadian dollars per US dollar (H.10)",
        "FCY_PER_USD",
        "CAD per USD",
        stale_after_days=14,
    ),
    _fx(
        "fred",
        "DEXJPUS",
        "JPY",
        "Japanese yen per US dollar (H.10)",
        "FCY_PER_USD",
        "JPY per USD",
        stale_after_days=14,
    ),
    _fx(
        "fred",
        "DEXUSAL",
        "AUD",
        "US dollars per Australian dollar (H.10)",
        "USD_PER_FCY",
        "USD per AUD",
        stale_after_days=14,
    ),
    _fx(
        "fred",
        "DEXSZUS",
        "CHF",
        "Swiss francs per US dollar (H.10)",
        "FCY_PER_USD",
        "CHF per USD",
        stale_after_days=14,
    ),
    _fx(
        "fred",
        "DEXMXUS",
        "MXN",
        "Mexican pesos per US dollar (H.10)",
        "FCY_PER_USD",
        "MXN per USD",
        stale_after_days=14,
    ),
    _fx(
        "fred",
        "DEXBZUS",
        "BRL",
        "Brazilian reais per US dollar (H.10)",
        "FCY_PER_USD",
        "BRL per USD",
        stale_after_days=14,
    ),
    _fx(
        "fred",
        "DEXINUS",
        "INR",
        "Indian rupees per US dollar (H.10)",
        "FCY_PER_USD",
        "INR per USD",
        stale_after_days=14,
    ),
    _fx(
        "fred",
        "DEXSIUS",
        "SGD",
        "Singapore dollars per US dollar (H.10)",
        "FCY_PER_USD",
        "SGD per USD",
        stale_after_days=14,
    ),
]


_FRED_RETAIL: list[SeriesSpec] = [
    SeriesSpec(
        "fred",
        "RSXFSN",
        "retail",
        "USD",
        "US advance retail sales ex food services, not seasonally adjusted",
        frequency="monthly",
        unit="USD millions",
        stale_after_days=100,
    ),
    SeriesSpec(
        "fred",
        "RSXFS",
        "retail",
        "USD",
        "US advance retail sales ex food services, seasonally adjusted",
        frequency="monthly",
        unit="USD millions",
        stale_after_days=100,
    ),
]

# ---------------------------------------------------------------------------------------
# Bank of Canada Valet. Current series (FX*) are daily averages and start 2017-01-03; the
# legacy noon series cover 2010-2016 and end 2017-04-28. Both are CAD per unit of FCY.
# ---------------------------------------------------------------------------------------
_BOC_CURRENT = {
    "USD": "FXUSDCAD",
    "EUR": "FXEURCAD",
    "GBP": "FXGBPCAD",
    "JPY": "FXJPYCAD",
    "AUD": "FXAUDCAD",
    "CHF": "FXCHFCAD",
    "MXN": "FXMXNCAD",
    "BRL": "FXBRLCAD",
    "INR": "FXINRCAD",
    "SGD": "FXSGDCAD",
}
_BOC_LEGACY = {
    "USD": "IEXE0101",
    "EUR": "EUROCAE01",
    "GBP": "IEXE1201",
    "JPY": "IEXE0701",
    "AUD": "IEXE1601",
    "CHF": "IEXE1101",
    "MXN": "IEXE2001",
    "BRL": "IEXE2801",
    "INR": "IEXE3001",
    "SGD": "IEXE3701",
}
_BOC_FX: list[SeriesSpec] = [
    _fx(
        "boc",
        sid,
        ccy,
        f"Daily average exchange rate, CAD per {ccy}",
        "CAD_PER_FCY",
        f"CAD per {ccy}",
    )
    for ccy, sid in _BOC_CURRENT.items()
] + [
    _fx(
        "boc",
        sid,
        ccy,
        f"Legacy noon rate, CAD per {ccy} (series ends 2017-04-28)",
        "CAD_PER_FCY",
        f"CAD per {ccy}",
        vintage="legacy",
        stale_after_days=10_000,
    )
    for ccy, sid in _BOC_LEGACY.items()
]
# ---------------------------------------------------------------------------------------
# ECB reference rates, 14:15 CET, units of FCY per euro.
# ---------------------------------------------------------------------------------------
_ECB_FX: list[SeriesSpec] = [
    _fx(
        "ecb",
        f"D.{ccy}.EUR.SP00.A",
        ccy,
        f"ECB reference rate, {ccy} per EUR",
        "FCY_PER_EUR",
        f"{ccy} per EUR",
    )
    for ccy in ("USD", "GBP", "CAD", "JPY", "AUD", "CHF", "MXN", "BRL", "INR", "SGD")
]

# ECB deposit facility rate: the policy rate that has anchored euro money-market rates
# since 2014 (the BIS series for the euro area is the main refinancing rate, which sat
# 40-50 bp above money-market rates through 2015-2022). Dataflow FM, daily.
_ECB_POLICY: list[SeriesSpec] = [
    SeriesSpec(
        "ecb",
        "FM.D.U2.EUR.4F.KR.DFR.LEV",
        "policy_rate",
        "EUR",
        "ECB deposit facility rate",
        unit="percent",
        stale_after_days=45,
    ),
]

# ---------------------------------------------------------------------------------------
# BIS: daily nominal broad effective exchange rates (WS_EER) and daily central bank policy
# rates (WS_CBPOL). Singapore has no policy rate (MAS targets the exchange rate).
# ---------------------------------------------------------------------------------------
_BIS_AREAS = {
    "USD": "US",
    "EUR": "XM",
    "GBP": "GB",
    "CAD": "CA",
    "JPY": "JP",
    "AUD": "AU",
    "CHF": "CH",
    "MXN": "MX",
    "BRL": "BR",
    "INR": "IN",
    "SGD": "SG",
}
_BIS_EER: list[SeriesSpec] = [
    SeriesSpec(
        "bis",
        f"D.N.B.{area}",
        "eer",
        ccy,
        f"BIS nominal effective exchange rate, broad basket, {ccy}",
        unit="index 2020=100",
        stale_after_days=30,
    )
    for ccy, area in _BIS_AREAS.items()
]
_BIS_CBPOL: list[SeriesSpec] = [
    SeriesSpec(
        "bis",
        f"D.{area}",
        "policy_rate",
        ccy,
        f"Central bank policy rate, {ccy} (BIS WS_CBPOL)",
        unit="percent",
        stale_after_days=45,
    )
    for ccy, area in _BIS_AREAS.items()
    if ccy != "SGD"
]

# ---------------------------------------------------------------------------------------
# Statistics Canada table 20-10-0056-01 (monthly retail trade sales; replaces 20-10-0008-01
# from 2017). Vector ids: Canada, total retail trade, unadjusted / seasonally adjusted.
# ---------------------------------------------------------------------------------------
_STATCAN_RETAIL: list[SeriesSpec] = [
    SeriesSpec(
        "statcan",
        "v1446859481",
        "retail",
        "CAD",
        "Canada retail trade sales, unadjusted (table 20-10-0056-01)",
        frequency="monthly",
        unit="CAD thousands",
        stale_after_days=130,
    ),
    SeriesSpec(
        "statcan",
        "v1446859483",
        "retail",
        "CAD",
        "Canada retail trade sales, seasonally adjusted (table 20-10-0056-01)",
        frequency="monthly",
        unit="CAD thousands",
        stale_after_days=130,
    ),
]

ALL_SERIES: tuple[SeriesSpec, ...] = tuple(
    _FRED_FX
    + _FRED_RETAIL
    + _BOC_FX
    + _ECB_FX
    + _ECB_POLICY
    + _BIS_EER
    + _BIS_CBPOL
    + _STATCAN_RETAIL
)

_BY_KEY = {s.key: s for s in ALL_SERIES}
if len(_BY_KEY) != len(ALL_SERIES):  # pragma: no cover - guards a programming error
    raise RuntimeError("duplicate series key in registry")


def by_key(key: str) -> SeriesSpec:
    """Look a series up by ``source:series_id``."""
    return _BY_KEY[key]


def select(
    *,
    source: Source | None = None,
    category: Category | None = None,
    ccy: str | None = None,
) -> list[SeriesSpec]:
    """Filter the registry; ``None`` means no filter on that field."""
    return [
        s
        for s in ALL_SERIES
        if (source is None or s.source == source)
        and (category is None or s.category == category)
        and (ccy is None or s.ccy == ccy)
    ]
