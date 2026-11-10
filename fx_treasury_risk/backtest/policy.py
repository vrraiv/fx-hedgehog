"""Walk-forward hedge-policy backtest with monthly rebalancing (ADR-0013).

At each rebalance date (first NY business day of the month) the policy sees only data up
to the previous trading day, the *origin*:

* exposure to hedge: the median forecast of net exposure per currency from the
  ``calendar_ar1`` model at that origin, averaged over the trading days of the month the
  forward covers (``exposure_input: forecast``; see ``hedge/sizing.py``), or the actual
  exposure at the origin (``actual``);
* risk model: EWMA(lambda) covariance of daily log returns up to the origin and a
  Student-t tail index fitted on the trailing window;
* prices: spot at the origin and the CIP forward for the tenor to the next rebalance.

Over the following month the realised P&L is computed daily from the *actual* exposure
path (so forecast error flows into the result), the forward's mark-to-market and carry,
and the spread paid on the notional dealt. Policies compared: unhedged, legacy 50%,
full hedge, optimizer.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import duckdb
import numpy as np
import pandas as pd

from fx_treasury_risk import config, db
from fx_treasury_risk.hedge import optimizer as opt
from fx_treasury_risk.hedge import plots
from fx_treasury_risk.hedge.config import HedgeConfig, load_hedge_config
from fx_treasury_risk.hedge.forwards import forward_rate, hedge_cost_rate
from fx_treasury_risk.hedge.rates import rates_wide
from fx_treasury_risk.hedge.sizing import holding_month_by_origin
from fx_treasury_risk.report.tables import df_to_markdown, write_markdown
from fx_treasury_risk.risk import covariance as cv
from fx_treasury_risk.risk.returns import fx_returns
from fx_treasury_risk.risk.var_es import fit_student_df

log = logging.getLogger(__name__)

STATIC_RATIOS = {"unhedged": 0.0, "legacy_50": 0.5, "full_hedge": 1.0}
PNL_COLS = ["pnl_unhedged", "pnl_hedge_mtm", "pnl_carry", "pnl_spread", "pnl_total"]


@dataclass(frozen=True)
class MarketData:
    """Everything the backtest needs, aligned on the FX calendar (returns index)."""

    calendar: pd.DatetimeIndex
    prices: np.ndarray  # usd_per_fcy, n x k
    returns: np.ndarray  # daily log returns, n x k
    exposure_fcy: np.ndarray  # actual net exposure in currency units, n x k
    rates: pd.DataFrame  # short rates in percent, date x ccy (USD included)
    forecast_fcy: pd.DataFrame  # holding-month average median forecast, origin x ccy
    day_count: dict[str, int]
    ccys: list[str]

    def pos(self, date: pd.Timestamp) -> int:
        """Row index of a calendar date."""
        return int(np.flatnonzero(self.calendar == date)[0])


def load_market_data(con: duckdb.DuckDBPyConnection, ccys: list[str]) -> MarketData:
    """Pull prices, returns, exposure, rates and stored forecasts from DuckDB."""
    returns = fx_returns(con, tuple(ccys)).dropna()
    calendar = pd.DatetimeIndex(returns.index)
    px = con.execute("SELECT obs_date, ccy, usd_per_fcy FROM fx_usd_master_filled").df()
    prices = px.pivot(index="obs_date", columns="ccy", values="usd_per_fcy")
    prices.index = pd.DatetimeIndex(prices.index)
    ex = con.execute("SELECT obs_date, ccy, net_fcy FROM exposure_group_fx").df()
    exposure = ex.pivot(index="obs_date", columns="ccy", values="net_fcy")
    exposure.index = pd.DatetimeIndex(exposure.index)
    rates = rates_wide(con)
    dc = con.execute("SELECT DISTINCT ccy, day_count FROM rates_short").df()
    day_count = {str(r["ccy"]): int(r["day_count"]) for r in dc.to_dict("records")}
    fc = con.execute(
        "SELECT origin, target_date, ccy, q500 FROM forecast_results WHERE model = 'calendar_ar1'"
    ).df()
    forecast = holding_month_by_origin(fc)
    return MarketData(
        calendar=calendar,
        prices=prices.reindex(calendar)[ccys].to_numpy(dtype=float),
        returns=returns[ccys].to_numpy(dtype=float),
        exposure_fcy=exposure.reindex(calendar, method="ffill")[ccys].to_numpy(dtype=float),
        rates=rates,
        forecast_fcy=forecast,
        day_count=day_count,
        ccys=ccys,
    )


def rebalance_dates(calendar: pd.DatetimeIndex, start: pd.Timestamp) -> pd.DatetimeIndex:
    """First trading day of each month from ``start``."""
    cal = pd.DatetimeIndex(calendar)
    month = cal.year * 100 + cal.month
    pos = pd.Series(np.arange(len(cal)), index=cal).groupby(month.to_numpy()).min().to_numpy()
    firsts = cal[pos]
    return pd.DatetimeIndex(firsts[firsts >= start])


def month_pnl(
    md: MarketData,
    t_origin: int,
    t_start: int,
    t_end: int,
    notional_fcy: np.ndarray,
    forward: np.ndarray,
    spread_cost_usd: float,
) -> dict[str, np.ndarray]:
    """Daily P&L components over rows ``t_start..t_end-1`` for a hedge dealt at ``t_origin``.

    * unhedged: exposure held at the prior close times the spot move;
    * hedge mark-to-market: notional times the spot move (forward delta of one);
    * carry: ``notional * (S_0 - F)`` earned over the tenor, accrued evenly per day;
    * spread: paid on the first day.
    Sum over the month of mtm + carry equals ``notional * (S_T - F)``: the forward's payoff.
    """
    px = md.prices[t_start:t_end]
    px_prev = np.vstack([md.prices[t_origin][None, :], px[:-1]])
    expo_prev = np.vstack(
        [md.exposure_fcy[t_origin][None, :], md.exposure_fcy[t_start : t_end - 1]]
    )
    move = px - px_prev
    n = t_end - t_start
    unhedged = (expo_prev * move).sum(axis=1)
    mtm = (move * notional_fcy[None, :]).sum(axis=1)
    carry_total = float(np.sum(notional_fcy * (md.prices[t_origin] - forward)))
    carry = np.full(n, carry_total / n)
    spread = np.zeros(n)
    spread[0] = -spread_cost_usd
    return {
        "pnl_unhedged": unhedged,
        "pnl_hedge_mtm": mtm,
        "pnl_carry": carry,
        "pnl_spread": spread,
        "pnl_total": unhedged + mtm + carry + spread,
    }


def run_policy_backtest(
    paths: config.Paths, hcfg: HedgeConfig | None = None
) -> dict[str, pd.DataFrame]:
    """Run every policy month by month; store daily, monthly and summary tables."""
    hcfg = hcfg or load_hedge_config()
    ccys = list(config.EXPOSURE_CCYS)
    k = len(ccys)
    con = db.connect(paths)
    try:
        md = load_market_data(con, ccys)
        cal = md.calendar
        rebal = rebalance_dates(cal, pd.Timestamp(hcfg.oos_start))
        rebal = rebal[rebal < cal[-1]]
        cov_path = cv.ewma_cov_path(
            pd.DataFrame(md.returns, index=cal, columns=ccys), hcfg.risk_lam
        )
        spreads = np.array(hcfg.spread_vector(ccys))
        dc_usd = md.day_count["USD"]
        prev_ratio = np.zeros(k)
        daily_frames: list[pd.DataFrame] = []
        decisions: list[dict[str, Any]] = []
        for i, d in enumerate(rebal):
            t_start = md.pos(d)
            t_origin = t_start - 1
            t_end = md.pos(rebal[i + 1]) if i + 1 < len(rebal) else len(cal)
            if t_end <= t_start:
                continue
            origin = cal[t_origin]
            tenor = int((cal[t_end - 1] - origin).days)
            spot = md.prices[t_origin]
            if hcfg.exposure_input == "forecast" and origin in md.forecast_fcy.index:
                expo_fcy = md.forecast_fcy.reindex(columns=ccys).loc[origin].to_numpy(dtype=float)
            else:
                expo_fcy = md.exposure_fcy[t_origin]
            expo_usd = expo_fcy * spot
            cov = cov_path[t_origin]
            hist = md.returns[max(0, t_origin - hcfg.risk_window + 1) : t_origin + 1]
            port = -(hist @ expo_usd)
            sd = float(port.std(ddof=1))
            nu = fit_student_df(port / sd) if sd > 0 else 5.0
            rate_row = md.rates.loc[[origin]].to_dict("records")[0]
            r_usd = float(rate_row["USD"])
            fwd = np.array(
                [
                    forward_rate(
                        float(spot[j]), r_usd, float(rate_row[c]), tenor, dc_usd, md.day_count[c]
                    )
                    for j, c in enumerate(ccys)
                ]
            )
            cost_rate = np.array(
                [hedge_cost_rate(float(spot[j]), float(fwd[j]), tenor) for j in range(k)]
            )
            prob = opt.HedgeProblem(
                ccys=ccys,
                exposure_usd=expo_usd,
                cov_daily=cov,
                horizon_days=hcfg.horizon_days,
                confidence=hcfg.confidence,
                nu=nu,
                es_budget_usd=hcfg.es_budget_usd,
                cost_rate=cost_rate,
                spread_bp=spreads,
                tenor_days=tenor,
            )
            for policy in hcfg.policies:
                if policy == "optimizer":
                    sol = opt.optimize_hedge(
                        prob, prev_ratio, hcfg.turnover_penalty_bp, hcfg.min_ticket_usd
                    )
                    h = sol.ratios.to_numpy(dtype=float)
                    prev_ratio = h
                    binding = sol.binding
                else:
                    h = np.full(k, STATIC_RATIOS[policy])
                    binding = False
                notional_fcy = -h * expo_fcy
                spread_cost = float(np.sum(spreads / 1e4 * np.abs(h * expo_usd)))
                pnl = month_pnl(md, t_origin, t_start, t_end, notional_fcy, fwd, spread_cost)
                frame = pd.DataFrame(pnl)
                frame.insert(0, "policy", policy)
                frame.insert(0, "date", cal[t_start:t_end])
                frame["rebalance"] = d
                daily_frames.append(frame)
                decisions.append(
                    {
                        "rebalance": d,
                        "origin": origin,
                        "policy": policy,
                        "ex_ante_es_usd": prob.residual_es(h),
                        "unhedged_es_usd": prob.residual_es(np.zeros(k)),
                        "carry_cost_usd": prob.carry_cost(h),
                        "spread_cost_usd": spread_cost,
                        "binding": binding,
                        "nu": nu,
                        "tenor_days": tenor,
                        **{f"expo_{c}": float(expo_fcy[j]) for j, c in enumerate(ccys)},
                        **{f"h_{c}": float(h[j]) for j, c in enumerate(ccys)},
                    }
                )
            if i % 24 == 0:
                log.info("policy backtest: %s done", d.date())
        daily = pd.concat(daily_frames, ignore_index=True)
        dec = pd.DataFrame(decisions)
        monthly = _monthly(daily, dec)
        summary = _summary(daily, monthly, hcfg.es_budget_usd)
        by_year = _by_year(monthly, hcfg.es_budget_usd)
        for name, frame in (
            ("policy_backtest_daily", daily),
            ("policy_backtest_monthly", monthly),
            ("policy_backtest_summary", summary),
            ("policy_backtest_by_year", by_year),
            ("policy_decisions", dec),
        ):
            con.register("tmp_df", frame)
            con.execute(f"CREATE OR REPLACE TABLE {name} AS SELECT * FROM tmp_df")
            con.unregister("tmp_df")
        _store_optimizer_positions(con, dec, ccys)
        _write_outputs(paths, hcfg, daily, monthly, summary, by_year, dec, ccys)
    finally:
        con.close()
    return {
        "daily": daily,
        "monthly": monthly,
        "summary": summary,
        "by_year": by_year,
        "decisions": dec,
    }


def _monthly(daily: pd.DataFrame, dec: pd.DataFrame) -> pd.DataFrame:
    m = daily.groupby(["policy", "rebalance"], as_index=False)[PNL_COLS].sum()
    keep = ["policy", "rebalance", "ex_ante_es_usd", "unhedged_es_usd", "binding"]
    return m.merge(dec[keep], on=["policy", "rebalance"])


def max_drawdown(pnl: np.ndarray) -> float:
    """Largest fall of cumulative P&L from its running peak, starting from zero.

    The peak includes the starting point (cumulative P&L of zero before the first day),
    so a book that loses from day one has a drawdown equal to its lowest cumulative P&L.
    Returned as a non-positive number.
    """
    cum = np.concatenate([[0.0], np.cumsum(pnl)])
    return float((cum - np.maximum.accumulate(cum)).min())


def _summary(daily: pd.DataFrame, monthly: pd.DataFrame, budget: float) -> pd.DataFrame:
    rows = []
    years = (daily["date"].max() - daily["date"].min()).days / 365.25
    for policy, g in daily.groupby("policy"):
        g = g.sort_values("date")
        m = monthly[monthly["policy"] == policy]
        rows.append(
            {
                "policy": policy,
                "daily_vol_annualized_usd": float(g["pnl_total"].std(ddof=1) * np.sqrt(252)),
                "monthly_vol_usd": float(m["pnl_total"].std(ddof=1)),
                "total_pnl_usd": float(g["pnl_total"].sum()),
                "carry_per_year_usd": float(g["pnl_carry"].sum() / years),
                "spread_per_year_usd": float(g["pnl_spread"].sum() / years),
                "max_drawdown_usd": max_drawdown(g["pnl_total"].to_numpy(dtype=float)),
                "worst_month_usd": float(m["pnl_total"].min()),
                "months_loss_gt_budget": int((m["pnl_total"] < -budget).sum()),
                "n_months": len(m),
                "mean_ex_ante_es_usd": float(m["ex_ante_es_usd"].mean()),
                "share_months_binding": float(m["binding"].mean()),
            }
        )
    return pd.DataFrame(rows)


def _by_year(monthly: pd.DataFrame, budget: float) -> pd.DataFrame:
    m = monthly.copy()
    m["year"] = pd.DatetimeIndex(m["rebalance"]).year
    m["breach"] = (m["pnl_total"] < -budget).astype(int)
    return m.groupby(["policy", "year"], as_index=False).agg(
        pnl_total_usd=("pnl_total", "sum"),
        monthly_vol_usd=("pnl_total", "std"),
        worst_month_usd=("pnl_total", "min"),
        carry_usd=("pnl_carry", "sum"),
        spread_usd=("pnl_spread", "sum"),
        months_loss_gt_budget=("breach", "sum"),
    )


def _store_optimizer_positions(
    con: duckdb.DuckDBPyConnection, dec: pd.DataFrame, ccys: list[str]
) -> None:
    """Write the optimizer's group-level notionals into hedge_positions (source='optimizer').

    A row is written for every currency and month, including zero notionals, so that the
    legacy placeholder never fills a month the optimizer has decided on. Positions run
    from the rebalance date to the next rebalance date (exclusive). ``exposure_group_fx``
    is rebuilt afterwards so its net-of-hedges columns include them.
    """
    o = dec[dec["policy"] == "optimizer"].sort_values("rebalance").to_dict("records")
    rows: list[tuple[Any, ...]] = []
    for i, r in enumerate(o):
        rebalance = pd.Timestamp(r["rebalance"])
        if i + 1 < len(o):
            maturity = pd.Timestamp(o[i + 1]["rebalance"])
        else:
            maturity = rebalance + pd.Timedelta(days=int(r["tenor_days"]) + 3)
        for c in ccys:
            notional = -float(r[f"h_{c}"]) * float(r[f"expo_{c}"])
            rows.append((rebalance.date(), maturity.date(), "GROUP", c, notional, "optimizer"))
    con.execute("DELETE FROM hedge_positions WHERE source = 'optimizer'")
    if rows:
        con.executemany("INSERT INTO hedge_positions VALUES (?, ?, ?, ?, ?, ?)", rows)
    # exposure_group_fx is a materialised table: rebuild it so the net-of-hedges basis
    # used by the hedge, risk and report stages reflects the positions just written
    db.execute_file(con, "090_exposure_group")
    log.info("stored %d optimizer hedge positions; exposure_group_fx rebuilt", len(rows))


def _write_outputs(
    paths: config.Paths,
    hcfg: HedgeConfig,
    daily: pd.DataFrame,
    monthly: pd.DataFrame,
    summary: pd.DataFrame,
    by_year: pd.DataFrame,
    dec: pd.DataFrame,
    ccys: list[str],
) -> None:
    figs = paths.figures_dir
    plots.cumulative_pnl_plot(daily, figs / "policy_cumulative_pnl.png")
    ratios = dec[dec["policy"] == "optimizer"].set_index("rebalance")[[f"h_{c}" for c in ccys]]
    ratios.columns = pd.Index(ccys)
    plots.hedge_ratio_plot(ratios, figs / "policy_hedge_ratios.png")
    plots.monthly_pnl_hist(monthly, figs / "policy_monthly_pnl.png", hcfg.es_budget_usd)

    s = summary.copy()
    money = [c for c in s.columns if c.endswith("_usd")]
    s[money] = (s[money] / 1e6).round(3)
    s = s.rename(columns={c: c.replace("_usd", "_usd_m") for c in money})
    s["share_months_binding"] = s["share_months_binding"].round(2)

    ep = monthly.copy()
    ep["month"] = pd.DatetimeIndex(ep["rebalance"]).strftime("%Y-%m")
    ep = ep[ep["month"].isin(["2020-03", "2020-04", "2022-09", "2022-10"])]
    ep = ep[["policy", "month", *PNL_COLS, "ex_ante_es_usd"]].copy()
    for c in [*PNL_COLS, "ex_ante_es_usd"]:
        ep[c] = (ep[c] / 1e6).round(3)

    by = by_year.copy()
    for c in ["pnl_total_usd", "monthly_vol_usd", "worst_month_usd", "carry_usd", "spread_usd"]:
        by[c] = (by[c] / 1e6).round(3)
    ratio_table = pd.concat(
        [ratios.mean().round(3).to_frame("mean").T, ratios.iloc[-1].round(3).to_frame("latest").T]
    )
    write_markdown(
        paths.reports_dir / "policy_backtest.md",
        "Hedge-policy backtest",
        [
            (
                "Setup",
                f"Monthly rebalance from {hcfg.oos_start} to "
                f"{pd.Timestamp(daily['date'].max()).date()}; ES budget USD "
                f"{hcfg.es_budget_usd / 1e6:.1f}m at {hcfg.horizon_days} days / "
                f"{hcfg.confidence:.0%}; exposure input = {hcfg.exposure_input}; one-month "
                "forwards priced by CIP at the origin; spreads from config/hedge.yaml charged "
                "on the notional dealt. P&L is the FX P&L of the group net exposure plus hedge "
                "mark-to-market, carry and spread; operating P&L is excluded.",
            ),
            ("Summary by policy (USD m)", df_to_markdown(s)),
            (
                "Optimizer hedge ratios: mean over the backtest and at the last rebalance",
                df_to_markdown(ratio_table, index=True),
            ),
            ("Stress months (USD m)", df_to_markdown(ep)),
            ("By year (USD m)", df_to_markdown(by)),
            (
                "Figures",
                "![cumulative](figures/policy_cumulative_pnl.png)\n\n"
                "![ratios](figures/policy_hedge_ratios.png)\n\n"
                "![monthly](figures/policy_monthly_pnl.png)",
            ),
        ],
    )
