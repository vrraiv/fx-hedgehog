"""Forward pricing from covered interest parity, in the repo's notation.

All rates are annualized simple rates in percent unless stated; ``days`` is the tenor in
calendar days; day counts are 360 or 365 as recorded in ``rates_short``.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


def simple_yield_from_discount(discount_pct: float, days: int, day_count: int = 360) -> float:
    """Convert a bank-discount rate (US T-bills) to a simple money-market yield.

    A bill quoted at discount ``d`` costs ``1 - d * days / 360`` per unit of face value;
    the simple yield on that price is ``y = d / (1 - d * days / 360)``.
    """
    d = discount_pct / 100
    return 100 * d / (1 - d * days / day_count)


def forward_rate(
    spot: float,
    r_usd_pct: float,
    r_fcy_pct: float,
    days: int,
    day_count_usd: int = 360,
    day_count_fcy: int = 360,
) -> float:
    """Outright forward, USD per FCY, by covered interest parity with simple rates.

    ``F = S * (1 + r_usd * tau_usd) / (1 + r_fcy * tau_fcy)`` where each ``tau`` uses its
    own market's day count. Holding dollars at ``r_usd`` must equal converting to FCY,
    earning ``r_fcy``, and converting back at ``F`` agreed today.
    """
    tau_usd = days / day_count_usd
    tau_fcy = days / day_count_fcy
    return spot * (1 + r_usd_pct / 100 * tau_usd) / (1 + r_fcy_pct / 100 * tau_fcy)


def forward_points(spot: float, forward: float, pip: float = 1e-4) -> float:
    """``F - S`` in pips (default pip = 0.0001 of the quote)."""
    return (forward - spot) / pip


def hedge_cost_rate(spot: float, forward: float, days: int) -> float:
    """Annualized cost of hedging a *long* FCY exposure, as a fraction of notional.

    Selling forward at ``F`` instead of spot ``S`` gives up ``S - F`` per unit of FCY over
    ``days``; annualized on 365 days. Positive = hedging costs money (``r_fcy > r_usd``).
    For a short exposure (bought forward) the sign flips; the optimizer handles that
    through the sign of the exposure.
    """
    return (spot - forward) / spot * 365 / days


@dataclass(frozen=True)
class ForwardQuote:
    """One currency's forward quote and the rates behind it."""

    ccy: str
    spot: float
    forward: float
    days: int
    r_usd_pct: float
    r_fcy_pct: float
    rate_source: str
    is_proxy: bool
    is_fallback: bool

    @property
    def points(self) -> float:
        """Forward points in pips (0.0001)."""
        return forward_points(self.spot, self.forward)

    @property
    def cost_rate(self) -> float:
        """Annualized hedge cost rate for a long exposure (fraction of notional)."""
        return hedge_cost_rate(self.spot, self.forward, self.days)


def instrument_days(tenor_months: int) -> int:
    """Calendar days to maturity of the instrument a rate is quoted on (3 months -> 91).

    The discount-to-yield conversion depends on the *bill's* maturity, not on the tenor of
    the forward being priced: a 13-week bill quoted at discount ``d`` has a simple yield
    ``d / (1 - d * 91/360)`` whatever the rate is later used for.
    """
    return round(tenor_months * 365 / 12)


def usd_simple_rate(rate_pct: float, basis: str, days: int, day_count: int) -> float:
    """Apply the discount-to-yield conversion if the series is quoted on a discount basis.

    ``days`` is the maturity of the quoted instrument (see :func:`instrument_days`).
    """
    return (
        simple_yield_from_discount(rate_pct, days, day_count) if basis == "discount" else rate_pct
    )


def forward_table(
    spots: pd.Series,
    rates: pd.DataFrame,
    days: int,
) -> pd.DataFrame:
    """Forward quotes for every currency in ``spots`` from one date's ``rates_short`` rows.

    Parameters
    ----------
    spots
        ``usd_per_fcy`` by currency.
    rates
        Rows of ``rates_short`` for one date, indexed by ``ccy`` (must include USD).
    days
        Tenor in calendar days.
    """
    recs: dict[str, dict[str, object]] = {
        str(k): {str(c): v for c, v in row.items()} for k, row in rates.to_dict("index").items()
    }

    def simple(row: dict[str, object]) -> float:
        bill = instrument_days(int(str(row["tenor_months"])))
        return usd_simple_rate(
            float(str(row["rate_pct"])), str(row["basis"]), bill, int(str(row["day_count"]))
        )

    usd = recs["USD"]
    dc_usd = int(str(usd["day_count"]))
    r_usd = simple(usd)
    rows = []
    for ccy, spot in spots.items():
        r = recs[str(ccy)]
        dc_fcy = int(str(r["day_count"]))
        r_fcy = simple(r)
        fwd = forward_rate(float(spot), r_usd, r_fcy, days, dc_usd, dc_fcy)
        q = ForwardQuote(
            ccy=str(ccy),
            spot=float(spot),
            forward=fwd,
            days=days,
            r_usd_pct=r_usd,
            r_fcy_pct=r_fcy,
            rate_source=f"{r['source']}:{r['series_id']}",
            is_proxy=bool(r["is_proxy"]),
            is_fallback=bool(r["is_fallback"]),
        )
        rows.append(
            {
                "ccy": q.ccy,
                "spot": q.spot,
                "forward": q.forward,
                "points_pips": q.points,
                "r_usd_pct": q.r_usd_pct,
                "r_fcy_pct": q.r_fcy_pct,
                "carry_pct_annual": 100 * q.cost_rate,
                "rate_source": q.rate_source,
                "is_proxy": q.is_proxy,
                "is_fallback": q.is_fallback,
            }
        )
    out = pd.DataFrame(rows).set_index("ccy")
    out["carry_pct_annual"] = np.round(out["carry_pct_annual"], 4)
    return out
