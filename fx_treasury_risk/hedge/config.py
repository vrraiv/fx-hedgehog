"""Typed view of ``config/hedge.yaml``."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from fx_treasury_risk import config as cfg

DEFAULT_PATH = cfg.REPO_ROOT / "config" / "hedge.yaml"


@dataclass(frozen=True)
class HedgeConfig:
    """Policy parameters."""

    es_budget_usd: float
    horizon_days: int
    confidence: float
    risk_lam: float
    risk_window: int
    forward_tenor_days: int
    bid_ask_bp: dict[str, float]
    min_ticket_usd: float
    oos_start: date
    exposure_input: str
    policies: tuple[str, ...]
    turnover_penalty_bp: float = 0.0

    def spread_vector(self, ccys: list[str]) -> list[float]:
        """Bid-ask spreads in the order of ``ccys`` (missing currencies get the max spread)."""
        default = max(self.bid_ask_bp.values())
        return [float(self.bid_ask_bp.get(c, default)) for c in ccys]


def load_hedge_config(path: Path = DEFAULT_PATH) -> HedgeConfig:
    """Parse and validate the YAML file."""
    raw: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8"))
    rm = raw["risk_model"]
    if rm.get("method") != "parametric_t":
        raise ValueError("only risk_model.method = parametric_t is supported")
    oos = raw["oos_start"]
    return HedgeConfig(
        es_budget_usd=float(raw["es_budget_usd"]),
        horizon_days=int(raw["horizon_days"]),
        confidence=float(raw["confidence"]),
        risk_lam=float(rm["lam"]),
        risk_window=int(rm["window"]),
        forward_tenor_days=int(raw["forward_tenor_days"]),
        bid_ask_bp={str(k): float(v) for k, v in raw["bid_ask_bp"].items()},
        min_ticket_usd=float(raw["min_ticket_usd"]),
        oos_start=oos if isinstance(oos, date) else date.fromisoformat(str(oos)),
        exposure_input=str(raw.get("exposure_input", "forecast")),
        policies=tuple(str(p) for p in raw["policies"]),
        turnover_penalty_bp=float(raw.get("turnover_penalty_bp", 0.0)),
    )
