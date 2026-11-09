"""``fxrisk hedge``: recommended hedge ratios today, the cost-vs-risk frontier, figures."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import duckdb
import numpy as np
import pandas as pd

from fx_treasury_risk import config, db
from fx_treasury_risk.hedge import optimizer as opt
from fx_treasury_risk.hedge import plots
from fx_treasury_risk.hedge.config import HedgeConfig, load_hedge_config
from fx_treasury_risk.hedge.rates import forward_table_on
from fx_treasury_risk.report.tables import df_to_markdown, write_markdown
from fx_treasury_risk.risk import covariance as cv
from fx_treasury_risk.risk.returns import fx_returns
from fx_treasury_risk.risk.var_es import fit_student_df

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class HedgeRun:
    """Outputs of one hedge run."""

    as_of: pd.Timestamp
    problem: opt.HedgeProblem
    solution: opt.HedgeSolution
    forwards: pd.DataFrame
    frontier: pd.DataFrame
    exposure_fcy: pd.Series
    exposure_source: str


def _latest_forecast(con: duckdb.DuckDBPyConnection, horizon: int) -> pd.Series | None:
    try:
        df = con.execute(
            "SELECT ccy, q500 FROM forecast_latest WHERE model = 'calendar_ar1' AND horizon = ?",
            [horizon],
        ).df()
    except duckdb.Error:
        return None
    return None if df.empty else df.set_index("ccy")["q500"].astype(float)


def build_problem(
    con: duckdb.DuckDBPyConnection, hcfg: HedgeConfig, as_of: pd.Timestamp | None = None
) -> tuple[opt.HedgeProblem, pd.DataFrame, pd.Series, str, pd.Timestamp]:
    """Assemble the optimizer input for ``as_of`` (default: last FX date)."""
    ccys = list(config.EXPOSURE_CCYS)
    if as_of is None:
        as_of = pd.Timestamp(
            con.execute("SELECT max(obs_date) FROM exposure_group_fx").fetchall()[0][0]
        )
    returns = fx_returns(con, tuple(ccys))
    returns = returns[returns.index <= as_of]
    cov = cv.ewma_cov(returns, hcfg.risk_lam).loc[ccys, ccys].to_numpy()
    fwd = forward_table_on(con, as_of, hcfg.forward_tenor_days, tuple(ccys))
    spot = fwd["spot"]
    forecast = _latest_forecast(con, hcfg.horizon_days)
    if hcfg.exposure_input == "forecast" and forecast is not None:
        expo_fcy = forecast.reindex(ccys)
        source = f"calendar_ar1 median forecast, {hcfg.horizon_days} days ahead"
    else:
        ex = (
            con.execute(
                "SELECT ccy, net_fcy FROM exposure_group_fx WHERE obs_date = ?", [as_of.date()]
            )
            .df()
            .set_index("ccy")["net_fcy"]
        )
        expo_fcy = ex.reindex(ccys).astype(float)
        source = "actual net exposure on the as-of date"
    expo_usd = (expo_fcy * spot).to_numpy(dtype=float)
    hist = returns.dropna().iloc[-hcfg.risk_window :].to_numpy()
    port = -(hist @ expo_usd)
    nu = fit_student_df(port / port.std(ddof=1))
    prob = opt.HedgeProblem(
        ccys=ccys,
        exposure_usd=expo_usd,
        cov_daily=cov,
        horizon_days=hcfg.horizon_days,
        confidence=hcfg.confidence,
        nu=nu,
        es_budget_usd=hcfg.es_budget_usd,
        cost_rate=fwd["carry_pct_annual"].to_numpy(dtype=float) / 100,
        spread_bp=np.array(hcfg.spread_vector(ccys)),
        tenor_days=hcfg.forward_tenor_days,
    )
    return prob, fwd, expo_fcy, source, as_of


def run_hedge(paths: config.Paths, hcfg: HedgeConfig | None = None) -> HedgeRun:
    """Solve today's problem, trace the frontier, write tables and the frontier figure."""
    hcfg = hcfg or load_hedge_config()
    con = db.connect(paths)
    try:
        prob, fwd, expo_fcy, source, as_of = build_problem(con, hcfg)
        # the policy backtest (run before this stage) records the optimizer's ratios at
        # every rebalance; today's recommendation starts from the last of them so the
        # turnover penalty measures change against the position actually in force
        prev = pd.DataFrame()
        if _table_exists(con, "policy_decisions"):
            prev = con.execute(
                "SELECT * FROM policy_decisions WHERE policy = 'optimizer' "
                "ORDER BY rebalance DESC LIMIT 1"
            ).df()
        h_prev = (
            np.array([float(prev.iloc[0][f"h_{c}"]) for c in prob.ccys]) if not prev.empty else None
        )
        sol = opt.optimize_hedge(prob, h_prev, hcfg.turnover_penalty_bp, hcfg.min_ticket_usd)
        front = opt.frontier(prob, n_points=30, min_ticket_usd=hcfg.min_ticket_usd)
        per_year = 365 / prob.tenor_days
        reference = {}
        for name, ratio in (("unhedged", 0.0), ("legacy_50", 0.5), ("full_hedge", 1.0)):
            h = np.full(len(prob.ccys), ratio)
            reference[name] = (
                prob.residual_es(h),
                (prob.carry_cost(h) + prob.spread_cost(h)) * per_year,
            )
        chosen = (sol.residual_es_usd, (sol.carry_cost_usd + sol.spread_cost_usd) * per_year)
        plots.frontier_plot(
            front, hcfg.es_budget_usd, chosen, reference, paths.figures_dir / "hedge_frontier.png"
        )

        rec = pd.DataFrame(
            {
                "exposure_fcy": expo_fcy.round(0),
                "exposure_usd_m": (pd.Series(prob.exposure_usd, index=prob.ccys) / 1e6).round(2),
                "hedge_ratio": sol.ratios.round(3),
                "notional_usd_m": (sol.notional_usd / 1e6).round(2),
                "carry_pct_annual": fwd["carry_pct_annual"].round(2),
                "spread_bp": prob.spread_bp,
                "rate_source": fwd["rate_source"],
                "is_proxy": fwd["is_proxy"],
            }
        )
        headline = pd.DataFrame(
            {
                "as_of": [as_of],
                "exposure_source": [source],
                "unhedged_es_usd": [sol.unhedged_es_usd],
                "residual_es_usd": [sol.residual_es_usd],
                "budget_usd": [hcfg.es_budget_usd],
                "carry_per_year_usd": [sol.carry_cost_usd * per_year],
                "spread_per_year_usd": [sol.spread_cost_usd * per_year],
                "nu": [prob.nu],
                "binding": [sol.binding],
                "horizon_days": [hcfg.horizon_days],
                "confidence": [hcfg.confidence],
                "tenor_days": [hcfg.forward_tenor_days],
            }
        )
        ref_rows = [
            {"policy": k, "residual_es_usd": v[0], "annual_cost_usd": v[1]}
            for k, v in reference.items()
        ] + [{"policy": "optimizer", "residual_es_usd": chosen[0], "annual_cost_usd": chosen[1]}]
        for name, frame in (
            ("hedge_recommendation", rec.reset_index().rename(columns={"index": "ccy"})),
            ("hedge_frontier", front),
            ("hedge_headline", headline),
            ("hedge_reference", pd.DataFrame(ref_rows)),
        ):
            con.register("tmp_df", frame)
            con.execute(f"CREATE OR REPLACE TABLE {name} AS SELECT * FROM tmp_df")
            con.unregister("tmp_df")
        _write_report(paths, hcfg, as_of, prob, sol, rec, front, reference, source)
    finally:
        con.close()
    return HedgeRun(as_of, prob, sol, fwd, front, expo_fcy, source)


def _table_exists(con: duckdb.DuckDBPyConnection, name: str) -> bool:
    return bool(
        con.execute(
            "SELECT 1 FROM information_schema.tables WHERE table_name = ?", [name]
        ).fetchall()
    )


def _write_report(
    paths: config.Paths,
    hcfg: HedgeConfig,
    as_of: pd.Timestamp,
    prob: opt.HedgeProblem,
    sol: opt.HedgeSolution,
    rec: pd.DataFrame,
    front: pd.DataFrame,
    reference: dict[str, tuple[float, float]],
    source: str,
) -> None:
    per_year = 365 / prob.tenor_days
    head = pd.DataFrame(
        {
            "quantity": [
                "unhedged ES (USD m)",
                "ES budget (USD m)",
                "residual ES with recommended hedges (USD m)",
                "expected carry cost per year (USD m)",
                "spread cost per year (USD m)",
                "tail index nu",
                "budget binding",
            ],
            "value": [
                round(sol.unhedged_es_usd / 1e6, 3),
                round(hcfg.es_budget_usd / 1e6, 3),
                round(sol.residual_es_usd / 1e6, 3),
                round(sol.carry_cost_usd * per_year / 1e6, 3),
                round(sol.spread_cost_usd * per_year / 1e6, 3),
                round(prob.nu, 2),
                "yes" if sol.binding else "no",
            ],
        }
    )
    ref = pd.DataFrame(
        [
            {
                "policy": k,
                "residual_es_usd_m": round(v[0] / 1e6, 3),
                "annual_cost_usd_m": round(v[1] / 1e6, 3),
            }
            for k, v in reference.items()
        ]
        + [
            {
                "policy": "optimizer",
                "residual_es_usd_m": round(sol.residual_es_usd / 1e6, 3),
                "annual_cost_usd_m": round(
                    (sol.carry_cost_usd + sol.spread_cost_usd) * per_year / 1e6, 3
                ),
            }
        ]
    )
    fr = front[["budget_usd", "residual_es_usd", "annual_cost_usd", "mean_ratio"]].copy()
    fr[["budget_usd", "residual_es_usd", "annual_cost_usd"]] = (
        fr[["budget_usd", "residual_es_usd", "annual_cost_usd"]] / 1e6
    ).round(3)
    fr = fr.rename(
        columns={
            "budget_usd": "budget_usd_m",
            "residual_es_usd": "residual_es_usd_m",
            "annual_cost_usd": "annual_cost_usd_m",
        }
    )
    write_markdown(
        paths.reports_dir / "hedge_recommendation.md",
        f"Hedge recommendation as of {as_of.date()}",
        [
            (
                "Setup",
                f"Exposure input: {source}. Risk model: Student-t with EWMA({hcfg.risk_lam}) "
                f"covariance at {hcfg.horizon_days} days / {hcfg.confidence:.0%}. Forwards: "
                f"{hcfg.forward_tenor_days}-day tenor priced by CIP.",
            ),
            ("Headline", df_to_markdown(head)),
            ("Recommended hedge ratios by currency", df_to_markdown(rec, index=True)),
            ("Reference policies at today's exposures", df_to_markdown(ref)),
            ("Frontier (every other point)", df_to_markdown(fr.iloc[::2])),
            ("Figure", "![frontier](figures/hedge_frontier.png)"),
        ],
    )
