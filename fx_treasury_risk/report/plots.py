"""Figures that only the decision report uses: the exposure waterfall and its history."""

from __future__ import annotations

from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt

# One hue in three lightness steps: the three bars are the same quantity (USD exposure)
# at successive stages of netting, so a sequential ramp, not three categorical hues.
STAGE_COLOURS = {"gross": "#c6dbef", "net": "#6baed6", "net of hedges": "#08519c"}


def waterfall_plot(wf: pd.DataFrame, path: Path) -> Path:
    """Gross, net and net-of-hedges exposure by currency on the last date (USD m).

    ``wf`` is ``report_waterfall_latest`` without the TOTAL row. Net and net-of-hedges are
    signed, so a bar below zero means the group is short that currency after hedging.
    """
    df = wf.sort_values("gross_usd_m", ascending=False).reset_index(drop=True)
    n = len(df)
    y = np.arange(n)
    height = 0.26
    fig, ax = plt.subplots(figsize=(7.2, 0.42 * n + 1.4))
    series = (
        ("gross", df["gross_usd_m"]),
        ("net", df["net_usd_m"]),
        ("net of hedges", df["net_of_hedges_usd_m"]),
    )
    for k, (label, values) in enumerate(series):
        ax.barh(
            y + (k - 1) * height,
            values,
            height=height * 0.92,
            color=STAGE_COLOURS[label],
            label=label,
        )
        for yi, v in zip(y + (k - 1) * height, values, strict=True):
            ax.text(
                v + (2 if v >= 0 else -2),
                yi,
                f"{v:,.0f}",
                va="center",
                ha="left" if v >= 0 else "right",
                fontsize=6.5,
                color="#333333",
            )
    ax.set_yticks(y)
    ax.set_yticklabels(df["ccy"], fontsize=8)
    ax.invert_yaxis()
    ax.axvline(0, color="black", lw=0.6)
    ax.set_xlabel("USD millions; positive = long the currency", fontsize=8)
    ax.set_title(
        f"Exposure waterfall on {pd.Timestamp(df['exposure_date'].iloc[0]).date()}", fontsize=10
    )
    ax.legend(fontsize=8, loc="lower right", frameon=False)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.grid(axis="x", color="#e5e5e5", lw=0.6)
    ax.set_axisbelow(True)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def exposure_history_plot(monthly: pd.DataFrame, path: Path) -> Path:
    """Monthly average group gross and |net| exposure, USD m (``report_exposure_monthly``)."""
    fig, ax = plt.subplots(figsize=(8.5, 3.4))
    x = pd.to_datetime(monthly["month"])
    ax.plot(x, monthly["gross_usd_m"], color=STAGE_COLOURS["gross"], lw=2, label="gross")
    ax.plot(x, monthly["net_abs_usd_m"], color=STAGE_COLOURS["net"], lw=2, label="|net|")
    ax.plot(
        x,
        monthly["net_of_hedges_abs_usd_m"],
        color=STAGE_COLOURS["net of hedges"],
        lw=2,
        label="|net of hedges|",
    )
    ax.set_ylabel("USD millions, sum over currencies", fontsize=8)
    ax.set_title("Group exposure, monthly average of daily positions", fontsize=10)
    ax.legend(fontsize=8, ncol=3, frameon=False)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.grid(axis="y", color="#e5e5e5", lw=0.6)
    ax.set_axisbelow(True)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path
