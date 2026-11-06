"""Typed view of ``config/flows.yaml``.

The YAML is the single source of truth for the stylized business; this module only
validates it and gives the generator attribute access with the right types.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from fx_treasury_risk import config as cfg

DEFAULT_PATH = cfg.REPO_ROOT / "config" / "flows.yaml"


@dataclass(frozen=True)
class EntityConfig:
    """One legal entity: functional currency and daily volumes by collected currency."""

    name: str
    functional: str
    volumes_per_day: dict[str, float]


@dataclass(frozen=True)
class Regime:
    """A multiplicative volume shock over a date range."""

    name: str
    start: date
    end: date
    multiplier: float


@dataclass(frozen=True)
class FlowConfig:
    """Validated generator configuration."""

    seed: int
    start: date
    end: date
    take_rate: float
    refund_rate: float
    refund_mean_lag_days: int
    refund_max_lag_days: int
    weekly_seasonality: tuple[float, ...]  # Mon..Sun, normalised to mean 1
    annual_profile_by_entity: dict[str, str]
    growth_annual_rate: float
    noise_daily_sigma: float
    noise_ar1: float
    settlement_lag_default: dict[int, float]
    settlement_lag_by_ccy: dict[str, dict[int, float]]
    payout_schedule_by_entity: dict[str, str]
    same_ccy_share_default: float
    same_ccy_share_by_ccy: dict[str, float]
    entities: dict[str, EntityConfig]
    interco_loans_from_us: dict[str, float]
    regimes: tuple[Regime, ...] = field(default_factory=tuple)

    def settlement_lag(self, ccy: str) -> dict[int, float]:
        """Lag distribution (business days -> probability) for a currency."""
        return self.settlement_lag_by_ccy.get(ccy, self.settlement_lag_default)

    def same_ccy_share(self, ccy: str) -> float:
        """Share of merchant payouts made in the collected currency."""
        return self.same_ccy_share_by_ccy.get(ccy, self.same_ccy_share_default)

    @property
    def pairs(self) -> list[tuple[str, str]]:
        """All (entity, currency) pairs with a configured volume."""
        return [(e, c) for e, ent in self.entities.items() for c in ent.volumes_per_day]


def _probs(d: dict[Any, Any]) -> dict[int, float]:
    out = {int(k): float(v) for k, v in d.items()}
    total = sum(out.values())
    if abs(total - 1.0) > 1e-6:
        raise ValueError(f"lag probabilities must sum to 1, got {total}")
    return out


def load_flow_config(path: Path = DEFAULT_PATH) -> FlowConfig:
    """Parse and validate the YAML file."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    weekly = tuple(float(x) for x in raw["weekly_seasonality"])
    if len(weekly) != 7:
        raise ValueError("weekly_seasonality needs 7 values (Mon..Sun)")
    mean_w = sum(weekly) / 7
    weekly = tuple(w / mean_w for w in weekly)

    entities = {
        name: EntityConfig(
            name=name,
            functional=str(e["functional"]),
            volumes_per_day={str(c): float(v) for c, v in e["volumes_per_day"].items()},
        )
        for name, e in raw["entities"].items()
    }
    for name, ent in entities.items():
        if cfg.ENTITIES.get(name) != ent.functional:
            raise ValueError(
                f"entity {name}: functional ccy {ent.functional} disagrees with config.ENTITIES"
            )

    regimes = tuple(
        Regime(str(r["name"]), _as_date(r["start"]), _as_date(r["end"]), float(r["multiplier"]))
        for r in raw.get("regimes", [])
    )
    lag = raw["settlement_lag_days"]
    share = raw["payout"]["same_ccy_share"]
    return FlowConfig(
        seed=int(raw["seed"]),
        start=_as_date(raw["start"]),
        end=_as_date(raw["end"]),
        take_rate=float(raw["take_rate"]),
        refund_rate=float(raw["refund"]["rate"]),
        refund_mean_lag_days=int(raw["refund"]["mean_lag_days"]),
        refund_max_lag_days=int(raw["refund"]["max_lag_days"]),
        weekly_seasonality=weekly,
        annual_profile_by_entity={
            str(k): str(v) for k, v in raw["annual_seasonality"]["profile_by_entity"].items()
        },
        growth_annual_rate=float(raw["growth"]["annual_rate"]),
        noise_daily_sigma=float(raw["noise"]["daily_sigma"]),
        noise_ar1=float(raw["noise"]["ar1"]),
        settlement_lag_default=_probs(lag["default"]),
        settlement_lag_by_ccy={str(c): _probs(d) for c, d in lag.get("by_ccy", {}).items()},
        payout_schedule_by_entity={
            str(k): str(v) for k, v in raw["payout"]["schedule_by_entity"].items()
        },
        same_ccy_share_default=float(share["default"]),
        same_ccy_share_by_ccy={str(c): float(v) for c, v in share.get("by_ccy", {}).items()},
        entities=entities,
        interco_loans_from_us={
            str(k): float(v) for k, v in raw["intercompany"]["loans_from_us"].items()
        },
        regimes=regimes,
    )


def _as_date(v: Any) -> date:
    return v if isinstance(v, date) else date.fromisoformat(str(v))
