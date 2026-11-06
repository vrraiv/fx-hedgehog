"""Calibration and example figures for the forecast evaluation (matplotlib, PNG)."""

from __future__ import annotations

from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from fx_treasury_risk.forecast.evaluate import CENTRAL_INTERVALS, REPORT_HORIZONS

#: colour-blind-safe pair for the two models
COLOURS = {"seasonal_naive": "#8c8c8c", "calendar_ar1": "#1f77b4"}


def calibration_plot(evaluation: pd.DataFrame, path: Path) -> Path:
    """Empirical vs nominal central-interval coverage, one panel per report horizon.

    Each point is one currency; the diagonal is perfect calibration. Points below the
    line mean the intervals are too narrow.
    """
    horizons = [h for h in REPORT_HORIZONS if h in set(evaluation["horizon"])]
    fig, axes = plt.subplots(1, len(horizons), figsize=(2.6 * len(horizons), 3.2), sharey=True)
    axes = np.atleast_1d(axes)
    nominal = np.array(sorted(CENTRAL_INTERVALS)) / 100
    for ax, h in zip(axes, horizons, strict=True):
        sub = evaluation[evaluation["horizon"] == h]
        ax.plot([0.4, 1.0], [0.4, 1.0], color="black", lw=0.8, ls="--")
        for model, g in sub.groupby("model"):
            emp = g[[f"coverage_{int(100 * n)}" for n in nominal]].to_numpy()
            for row in emp:
                ax.plot(nominal, row, color=COLOURS.get(str(model), "k"), alpha=0.35, lw=1)
            ax.plot(
                nominal,
                emp.mean(axis=0),
                color=COLOURS.get(str(model), "k"),
                lw=2.2,
                marker="o",
                label=str(model),
            )
        ax.set_title(f"h = {h} days", fontsize=10)
        ax.set_xticks(nominal)
        ax.set_xlabel("nominal coverage")
        ax.set_ylim(0.3, 1.02)
    axes[0].set_ylabel("empirical coverage")
    axes[0].legend(fontsize=8, loc="lower right")
    fig.suptitle(
        "Prediction-interval calibration by horizon (thin lines: currencies; thick: mean)",
        fontsize=10,
    )
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def pinball_plot(evaluation: pd.DataFrame, path: Path) -> Path:
    """Scaled pinball loss by horizon, one panel per currency, both models."""
    ccys = sorted(evaluation["ccy"].unique())
    ncol = 5
    nrow = int(np.ceil(len(ccys) / ncol))
    fig, axes = plt.subplots(nrow, ncol, figsize=(2.6 * ncol, 2.4 * nrow), sharex=True)
    for ax, ccy in zip(np.ravel(axes), ccys, strict=False):
        sub = evaluation[evaluation["ccy"] == ccy]
        for model, g in sub.groupby("model"):
            g = g.sort_values("horizon")
            ax.plot(
                g["horizon"],
                g["pinball_pct"],
                color=COLOURS.get(str(model), "k"),
                lw=1.6,
                label=str(model),
            )
        ax.set_title(ccy, fontsize=10)
        ax.set_ylim(bottom=0)
    for ax in np.ravel(axes)[len(ccys) :]:
        ax.axis("off")
    for ax in np.ravel(axes)[-ncol:]:
        ax.set_xlabel("horizon (trading days)")
    np.ravel(axes)[0].set_ylabel("pinball loss, % of exposure")
    np.ravel(axes)[0].legend(fontsize=8)
    fig.suptitle("Forecast accuracy by horizon (lower is better)", fontsize=10)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def fan_chart(history: pd.Series, forecast: pd.DataFrame, path: Path, title: str) -> Path:
    """Last 120 days of history and the forecast fan (50/80/95 bands) for one currency."""
    fig, ax = plt.subplots(figsize=(8, 3.4))
    hist = history.iloc[-120:]
    ax.plot(hist.index, hist.to_numpy() / 1e6, color="black", lw=1.2, label="actual")
    f = forecast.sort_values("horizon")
    x = pd.DatetimeIndex(f["target_date"])
    for level, alpha in ((95, 0.15), (80, 0.25), (50, 0.4)):
        lo, hi = CENTRAL_INTERVALS[level]
        ax.fill_between(
            x,
            f[f"q{int(lo * 1000):03d}"] / 1e6,
            f[f"q{int(hi * 1000):03d}"] / 1e6,
            color="#1f77b4",
            alpha=alpha,
            lw=0,
            label=f"{level}% band",
        )
    ax.plot(x, f["q500"] / 1e6, color="#1f77b4", lw=1.4, label="median")
    if "actual" in f and f["actual"].notna().any():
        ax.plot(x, f["actual"] / 1e6, color="black", lw=1.0, ls=":", label="realised")
    ax.set_ylabel("net exposure, millions (ccy)")
    ax.set_title(title, fontsize=10)
    ax.legend(fontsize=8, ncol=3)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path
