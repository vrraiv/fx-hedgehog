"""Figures for the hedge stage and the policy backtest."""

from __future__ import annotations

from pathlib import Path

import matplotlib
import matplotlib.dates as mdates
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt

POLICY_COLOURS = {
    "unhedged": "#8c8c8c",
    "legacy_50": "#d95f02",
    "full_hedge": "#7570b3",
    "optimizer": "#1b9e77",
}


def frontier_plot(
    frontier: pd.DataFrame,
    budget_usd: float,
    chosen: tuple[float, float],
    reference: dict[str, tuple[float, float]],
    path: Path,
) -> Path:
    """Annualized hedging cost against residual 21-day ES, with the budget and reference points."""
    fig, ax = plt.subplots(figsize=(6.4, 4.2))
    ax.plot(
        frontier["residual_es_usd"] / 1e6,
        frontier["annual_cost_usd"] / 1e6,
        color="#1b9e77",
        lw=2,
        label="efficient frontier (optimizer)",
    )
    ax.axvline(budget_usd / 1e6, color="black", ls="--", lw=0.9, label="ES budget")
    ax.scatter(
        [chosen[0] / 1e6], [chosen[1] / 1e6], color="#1b9e77", s=60, zorder=5, label="recommended"
    )
    for name, (es, cost) in reference.items():
        ax.scatter(
            [es / 1e6],
            [cost / 1e6],
            color=POLICY_COLOURS.get(name, "k"),
            s=45,
            zorder=5,
            label=name,
        )
    ax.set_xlabel("residual 21-day 99% Expected Shortfall (USD m)")
    ax.set_ylabel("expected hedging cost, carry + spread (USD m per year)")
    ax.set_title("Cost of risk reduction", fontsize=10)
    ax.axhline(0, color="black", lw=0.5)
    ax.legend(fontsize=8)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def cumulative_pnl_plot(daily: pd.DataFrame, path: Path) -> Path:
    """Cumulative hedged P&L by policy, with the March 2020 and 2022 windows shaded."""
    fig, ax = plt.subplots(figsize=(8.5, 4))
    for policy, g in daily.groupby("policy"):
        g = g.sort_values("date")
        ax.plot(
            g["date"],
            g["pnl_total"].cumsum() / 1e6,
            color=POLICY_COLOURS.get(str(policy), "k"),
            lw=1.4,
            label=str(policy),
        )
    episodes = (("2020-02-20", "2020-04-30", "Mar 2020"), ("2022-01-01", "2022-10-31", "2022"))
    for start, end, label in episodes:
        x0 = float(mdates.date2num(pd.Timestamp(start).to_pydatetime()))  # type: ignore[no-untyped-call]
        x1 = float(mdates.date2num(pd.Timestamp(end).to_pydatetime()))  # type: ignore[no-untyped-call]
        ax.axvspan(x0, x1, color="#dddddd", alpha=0.6, lw=0)
        ax.text(x0, ax.get_ylim()[1], label, fontsize=7, va="top")
    ax.axhline(0, color="black", lw=0.5)
    ax.set_ylabel("cumulative P&L incl. hedge cost (USD m)")
    ax.set_title("Walk-forward policy backtest: cumulative FX P&L of the net exposure", fontsize=10)
    ax.legend(fontsize=8, ncol=4)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def hedge_ratio_plot(ratios: pd.DataFrame, path: Path) -> Path:
    """Optimizer hedge ratios as a currency x month heatmap (rows = currencies)."""
    fig, ax = plt.subplots(figsize=(9, 3.4))
    data = ratios.T.to_numpy(dtype=float)
    im = ax.imshow(data, aspect="auto", cmap="Blues", vmin=0, vmax=1, interpolation="nearest")
    ax.set_yticks(range(len(ratios.columns)))
    ax.set_yticklabels(list(ratios.columns), fontsize=8)
    idx = pd.DatetimeIndex(ratios.index)
    years = sorted(set(idx.year))
    ticks = [int(np.flatnonzero(idx.year == y)[0]) for y in years]
    ax.set_xticks(ticks)
    ax.set_xticklabels([str(y) for y in years], fontsize=8)
    cbar = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02)
    cbar.set_label("hedge ratio", fontsize=8)
    ax.set_title("Optimizer hedge ratios at each monthly rebalance", fontsize=10)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def monthly_pnl_hist(monthly: pd.DataFrame, path: Path, budget_usd: float) -> Path:
    """Distribution of monthly P&L per policy with the ES budget marked as a loss."""
    policies = list(monthly["policy"].unique())
    fig, axes = plt.subplots(
        1, len(policies), figsize=(2.6 * len(policies), 3.0), sharex=True, sharey=True
    )
    axes = np.atleast_1d(axes)
    lo = monthly["pnl_total"].min() / 1e6
    hi = monthly["pnl_total"].max() / 1e6
    bins = np.linspace(lo, hi, 30)
    for ax, policy in zip(axes, policies, strict=True):
        g = monthly[monthly["policy"] == policy]
        ax.hist(g["pnl_total"] / 1e6, bins=bins, color=POLICY_COLOURS.get(policy, "k"), alpha=0.85)
        ax.axvline(-budget_usd / 1e6, color="black", ls="--", lw=0.9)
        ax.set_title(policy, fontsize=9)
        ax.set_xlabel("monthly P&L (USD m)")
    axes[0].set_ylabel("months")
    fig.suptitle("Monthly P&L by policy; dashed line = ES budget as a loss", fontsize=10)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path
