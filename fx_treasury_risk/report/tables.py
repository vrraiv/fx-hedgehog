"""Markdown rendering of DataFrames, shared by the quality, risk and backtest stages."""

from __future__ import annotations

import math
from collections.abc import Mapping
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
        text = f"{v:,.2f}".rstrip("0").rstrip(".")
        return "0" if text == "-0" else text  # -0.0 and -0.004 both print as 0
    if isinstance(v, pd.Timestamp | datetime | date):
        return pd.Timestamp(v).date().isoformat()
    return str(v)


def fmt_fixed(v: object, decimals: int) -> str:
    """Fixed-decimal formatting of floats with thousands separators.

    ``-0.0`` prints as ``0.0``; integers and non-numbers fall back to :func:`fmt`, so a
    count in a fixed-decimal table still prints as a count.
    """
    if not isinstance(v, float):
        return fmt(v)
    if math.isnan(v):
        return ""
    text = f"{v:,.{decimals}f}"
    return text[1:] if text.startswith("-") and float(text.replace(",", "")) == 0 else text


def df_to_markdown(
    df: pd.DataFrame,
    index: bool = False,
    decimals: int | Mapping[str, int] | None = None,
) -> str:
    """Render a frame as a GitHub-flavoured markdown table.

    ``decimals`` fixes the number of decimals for numeric cells: one value for every
    column, or a mapping from column name to decimals (other columns use :func:`fmt`).
    Without it, numbers are printed compactly with trailing zeros stripped.
    """
    frame = df.reset_index() if index else df
    cols = [str(c) for c in frame.columns]
    if decimals is None:
        per_col: list[int | None] = [None] * len(cols)
    elif isinstance(decimals, int):
        per_col = [decimals] * len(cols)
    else:
        per_col = [decimals.get(c) for c in cols]
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for row in frame.itertuples(index=False):
        cells = [
            fmt(v) if d is None else fmt_fixed(v, d) for v, d in zip(row, per_col, strict=True)
        ]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def write_markdown(path: Path, title: str, sections: list[tuple[str, str]]) -> None:
    """Write ``# title`` followed by ``## heading`` / body pairs."""
    path.parent.mkdir(parents=True, exist_ok=True)
    parts = [f"# {title}", ""]
    for heading, body in sections:
        parts += [f"## {heading}", "", body, ""]
    path.write_text("\n".join(parts), encoding="utf-8")
