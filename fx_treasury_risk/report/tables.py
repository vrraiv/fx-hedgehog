"""Markdown rendering of DataFrames, shared by the quality, risk and backtest stages."""

from __future__ import annotations

import math
from datetime import date, datetime
from pathlib import Path

import pandas as pd


def fmt(v: object) -> str:
    """Compact scalar formatting for markdown cells."""
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, float):
        if math.isnan(v):
            return ""
        if v != 0 and abs(v) < 1e-3:
            return f"{v:.3g}"
        return f"{v:,.2f}".rstrip("0").rstrip(".")
    if isinstance(v, pd.Timestamp | datetime | date):
        return pd.Timestamp(v).date().isoformat()
    return str(v)


def df_to_markdown(df: pd.DataFrame, index: bool = False) -> str:
    """Render a frame as a GitHub-flavoured markdown table."""
    frame = df.reset_index() if index else df
    cols = [str(c) for c in frame.columns]
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for row in frame.itertuples(index=False):
        lines.append("| " + " | ".join(fmt(v) for v in row) + " |")
    return "\n".join(lines)


def write_markdown(path: Path, title: str, sections: list[tuple[str, str]]) -> None:
    """Write ``# title`` followed by ``## heading`` / body pairs."""
    path.parent.mkdir(parents=True, exist_ok=True)
    parts = [f"# {title}", ""]
    for heading, body in sections:
        parts += [f"## {heading}", "", body, ""]
    path.write_text("\n".join(parts), encoding="utf-8")
