"""``fxrisk report``: the decision report, assembled from what earlier stages persisted.

The report computes nothing. Every table is read from the DuckDB tables the ``forecast``,
``hedge``, ``backtest`` and ``risk`` stages wrote, every figure already exists in
``reports/figures`` (two more are drawn here from exposure views), and the prose is
templated around those numbers so that a refreshed data set rewrites the argument with the
new figures in it. ``load_report_data`` gathers, ``render_sections`` writes, and the two are
separated so the renderer can be tested on small hand-made frames.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import SupportsFloat, cast

import duckdb
import pandas as pd
from scipy import stats

from fx_treasury_risk import __version__, config, db
from fx_treasury_risk.backtest.var_backtest import method_for_ewma
from fx_treasury_risk.hedge.config import HedgeConfig, load_hedge_config
from fx_treasury_risk.report import plots
from fx_treasury_risk.report.labels import (
    POLICY_LABELS,
    SCENARIO_LABELS,
    TOTAL_LABEL,
    VAR_METHOD_LABELS,
    risk_label,
)
from fx_treasury_risk.report.tables import df_to_markdown, fmt, write_markdown

log = logging.getLogger(__name__)

REPORT_NAME = "decision_report.md"
STRESS_MONTHS = ("2020-03", "2020-04", "2022-09", "2022-10")
SHOW_HORIZONS = (1, 5, 10, 21, 42, 63)


@dataclass
class ReportData:
    """Everything the report prints, as frames in the units the tables show (USD m)."""

    as_of: pd.Timestamp
    hcfg: HedgeConfig
    retrieved_on: str
    quality_overall: str
    quality_summary: pd.DataFrame
    waterfall: pd.DataFrame  # report_waterfall_latest incl. TOTAL row
    entity_latest: pd.DataFrame
    exposure_monthly: pd.DataFrame
    forecast_by_horizon: pd.DataFrame  # calendar_ar1 only
    forecast_latest: pd.DataFrame  # 21-day median and 95% band by ccy
    var_backtest: pd.DataFrame
    risk_21d: pd.DataFrame  # ES at the policy horizon/confidence, all methods, both bases
    stress: pd.DataFrame
    hedge_headline: pd.Series
    recommendation: pd.DataFrame
    reference: pd.DataFrame
    frontier: pd.DataFrame
    policy_summary: pd.DataFrame
    policy_months: pd.DataFrame  # the four stress months, all policies
    policy_by_year: pd.DataFrame
    ratios_mean: pd.Series
    figures: dict[str, Path] = field(default_factory=dict)
    var_selection: pd.DataFrame = field(default_factory=pd.DataFrame)  # 2012-2014 ranking
    policy_comparison: pd.DataFrame = field(default_factory=pd.DataFrame)  # optimizer vs rest


# ----------------------------------------------------------------------------- loading


def _read(con: duckdb.DuckDBPyConnection, name: str) -> pd.DataFrame:
    return con.execute(f"SELECT * FROM {name}").df()


def _load_quality(con: duckdb.DuckDBPyConnection) -> tuple[str, pd.DataFrame]:
    """Overall status and the per-check summary the quality stage stored."""
    if not db.table_exists(con, "quality_checks"):
        return "not run", pd.DataFrame(columns=["check", "status", "summary"])
    checks = _read(con, "quality_checks").rename(columns={"check_name": "check"})
    statuses = set(checks["status"])
    overall = "FAIL" if "FAIL" in statuses else ("WARN" if "WARN" in statuses else "PASS")
    return overall, checks


def _retrieved_on(paths: config.Paths) -> str:
    manifest = paths.cache_dir / "manifest.json"
    if not manifest.exists():
        return "unknown"
    data = json.loads(manifest.read_text(encoding="utf-8"))
    dates = sorted({str(v["retrieved_at"])[:10] for v in data.get("series", {}).values()})
    if not dates:
        return "unknown"
    return dates[-1] if len(dates) == 1 else f"{dates[0]} to {dates[-1]}"


def load_report_data(paths: config.Paths, hcfg: HedgeConfig | None = None) -> ReportData:
    """Read every input of the report from DuckDB and the earlier stages' files."""
    hcfg = hcfg or load_hedge_config()
    con = db.connect(paths)
    try:
        for t in ("hedge_headline", "policy_backtest_summary", "forecast_eval", "risk_results"):
            if not db.table_exists(con, t):
                raise RuntimeError(f"table {t} missing: run the earlier stages (`fxrisk all`)")
        db.execute_file(con, "110_report_views")

        head = _read(con, "hedge_headline").iloc[0]
        as_of = pd.Timestamp(head["as_of"])

        waterfall = _read(con, "report_waterfall_latest").drop(columns="sort_key")
        entity_latest = _read(con, "report_entity_latest")
        exposure_monthly = _read(con, "report_exposure_monthly")

        fe = _read(con, "forecast_eval")
        fe = fe[fe["model"] == "calendar_ar1"]
        by_h = (
            fe.groupby("horizon")[
                ["pinball_pct", "mape_median_pct", "coverage_50", "coverage_80", "coverage_95"]
            ]
            .mean()
            .reset_index()
        )
        skill = fe.groupby("horizon")["skill_vs_naive"].mean().reset_index()
        forecast_by_horizon = by_h.merge(skill, on="horizon")
        forecast_by_horizon = forecast_by_horizon[
            forecast_by_horizon["horizon"].isin([*SHOW_HORIZONS, hcfg.horizon_days])
        ].reset_index(drop=True)

        fl = _read(con, "forecast_latest")
        fl = fl[(fl["model"] == "calendar_ar1") & (fl["horizon"] == hcfg.horizon_days)]
        forecast_latest = fl[["ccy", "target_date", "q025", "q500", "q975"]].rename(
            columns={"q025": "2.5%", "q500": "median", "q975": "97.5%"}
        )

        var_backtest = _read(con, "var_backtest_results")
        var_selection = (
            _read(con, "var_model_selection")
            if db.table_exists(con, "var_model_selection")
            else pd.DataFrame()
        )
        rr = _read(con, "risk_results")
        rr = rr[
            (rr["horizon_days"] == hcfg.horizon_days)
            & (rr["confidence"].sub(hcfg.confidence).abs() < 1e-9)
        ]
        risk_21d = (
            rr.assign(label=rr["method"] + " / " + rr["cov_method"])
            .pivot_table(index="label", columns="basis", values="es_usd", aggfunc="first")
            .div(1e6)
            .reset_index()
        )
        stress = _read(con, "stress_results")
        stress = (
            stress.pivot_table(
                index=["scenario", "kind", "largest_move", "propagated", "implied_moves"],
                columns="basis",
                values="pnl_usd",
                aggfunc="first",
                sort=False,
            )
            .div(1e6)
            .reset_index()
        )

        recommendation = _read(con, "hedge_recommendation")
        reference = _read(con, "hedge_reference")
        frontier = _read(con, "hedge_frontier")

        policy_summary = _read(con, "policy_backtest_summary")
        pm = _read(con, "policy_backtest_monthly")
        pm["month"] = pd.DatetimeIndex(pm["rebalance"]).strftime("%Y-%m")
        policy_months = pm[pm["month"].isin(STRESS_MONTHS)]
        policy_by_year = _read(con, "policy_backtest_by_year")
        overall, qsum = _load_quality(con)
        policy_comparison = (
            _read(con, "policy_comparison")
            if db.table_exists(con, "policy_comparison")
            else pd.DataFrame()
        )
        dec = _read(con, "policy_decisions")
        dec = dec[dec["policy"] == "optimizer"]
        ratio_cols = [c for c in dec.columns if c.startswith("h_")]
        ratios_mean = dec[ratio_cols].mean()
        ratios_mean.index = pd.Index([c[2:] for c in ratio_cols])
    finally:
        con.close()

    return ReportData(
        as_of=as_of,
        hcfg=hcfg,
        retrieved_on=_retrieved_on(paths),
        quality_overall=overall,
        quality_summary=qsum,
        waterfall=waterfall,
        entity_latest=entity_latest,
        exposure_monthly=exposure_monthly,
        forecast_by_horizon=forecast_by_horizon,
        forecast_latest=forecast_latest,
        var_backtest=var_backtest,
        risk_21d=risk_21d,
        stress=stress,
        hedge_headline=head,
        recommendation=recommendation,
        reference=reference,
        frontier=frontier,
        policy_summary=policy_summary,
        policy_months=policy_months,
        policy_by_year=policy_by_year,
        ratios_mean=ratios_mean,
        var_selection=var_selection,
        policy_comparison=policy_comparison,
    )


# ---------------------------------------------------------------------------- rendering


def _num(x: object) -> float:
    """Scalar from a frame cell; pandas types cells as ``object`` or a wide union."""
    return float(cast(SupportsFloat, x))


def _m(x: object) -> str:
    """USD millions with one decimal, sign kept."""
    return f"{_num(x) / 1e6:,.1f}"


def _pct(x: object) -> str:
    return f"{100 * _num(x):.0f}%"


def _ratio_groups(rec: pd.DataFrame) -> tuple[list[str], list[str], list[str]]:
    full = [str(r.ccy) for r in rec.itertuples() if _num(r.hedge_ratio) >= 0.995]
    none = [str(r.ccy) for r in rec.itertuples() if _num(r.hedge_ratio) <= 0.005]
    partial = [
        f"{r.ccy} {_pct(r.hedge_ratio)}"
        for r in rec.itertuples()
        if 0.005 < _num(r.hedge_ratio) < 0.995
    ]
    return full, partial, none


def _policy_row(summary: pd.DataFrame, policy: str) -> pd.Series:
    row = summary[summary["policy"] == policy]
    if row.empty:
        raise KeyError(f"policy {policy} missing from the backtest summary")
    return row.iloc[0]


def _fig(figures: dict[str, Path], key: str, alt: str) -> str:
    path = figures.get(key)
    return f"![{alt}](figures/{path.name})" if path else f"*(figure {key} not generated)*"


def headline_answer(d: ReportData) -> str:
    """The primary question's answer in one paragraph, every number from the data."""
    h = d.hedge_headline
    full, partial, none = _ratio_groups(d.recommendation)
    carry = -float(h["carry_per_year_usd"])  # positive = the programme earns carry
    spread = float(h["spread_per_year_usd"])
    opt = _policy_row(d.policy_summary, "optimizer")
    unh = _policy_row(d.policy_summary, "unhedged")
    fh = _policy_row(d.policy_summary, "full_hedge")
    parts = []
    if full:
        parts.append(f"hedge {', '.join(full)} in full")
    if partial:
        parts.append(", ".join(partial))
    if none:
        parts.append(f"leave {', '.join(none)} unhedged")
    carry_clause = (
        f"earns about USD {carry / 1e6:.1f}m a year of carry"
        if carry > 0
        else f"costs about USD {-carry / 1e6:.1f}m a year of carry"
    )
    return (
        f"**With a {d.hcfg.horizon_days}-day {d.hcfg.confidence:.0%} Expected Shortfall budget "
        f"of USD {float(h['budget_usd']) / 1e6:.0f}m, {'; '.join(parts)}.** That programme "
        f"{carry_clause} against USD {spread / 1e6:.1f}m of bid-ask spread, and cuts the ES "
        f"of the forecast book from USD {_m(h['unhedged_es_usd'])}m to USD "
        f"{_m(h['residual_es_usd'])}m. Out of sample from {d.hcfg.oos_start.year} with a "
        f"monthly rebalance ({int(opt['n_months'])} months), the policy's annualized P&L "
        f"volatility is USD {_m(opt['daily_vol_annualized_usd'])}m against "
        f"{_m(unh['daily_vol_annualized_usd'])}m unhedged and "
        f"{_m(fh['daily_vol_annualized_usd'])}m for a full hedge; its total P&L is USD "
        f"{_m(opt['total_pnl_usd'])}m ({_m(unh['total_pnl_usd'])}m unhedged, "
        f"{_m(fh['total_pnl_usd'])}m full hedge), its maximum drawdown USD "
        f"{_m(opt['max_drawdown_usd'])}m ({_m(unh['max_drawdown_usd'])}m unhedged). "
        + _var_exceedance_text(d, opt)
        + _significance_text(d)
    )


def _var_exceedance_text(d: ReportData, opt: pd.Series) -> str:
    n = int(opt["n_months"])
    expected = n * (1 - d.hcfg.confidence)
    if "months_loss_gt_var" in opt.index:
        k = int(opt["months_loss_gt_var"])
        text = (
            f"Its monthly loss exceeded its own ex-ante {_pct(d.hcfg.confidence)} VaR in {k} of "
            f"{n} months, against about {expected:.1f} expected if the risk model is right"
        )
        p = float(stats.binom.sf(k - 1, n, 1 - d.hcfg.confidence)) if k > 0 else 1.0
        if p < 0.05:
            return (
                text + f": too many (binomial p = {p:.3f}). The monthly VaR covers the hedged "
                "forecast exposure only, so forecast error and intra-month exposure swings "
                "add risk it does not count."
            )
        return text + f" (binomial p = {p:.2f})."
    k = int(opt["months_loss_gt_budget"])
    return f"{k} of {n} months lost more than the budget."


def _significance_text(d: ReportData) -> str:
    """Whether the optimizer's lead over a full hedge is more than luck, and what it is made of."""
    c = d.policy_comparison
    row = c[c["versus"] == "full_hedge"] if not c.empty else c
    if row.empty:
        return ""
    r = row.iloc[0]
    diff, p = _num(r["total_diff_usd"]), _num(r["p_value"])
    known, spot = _num(r["carry_spread_diff_usd"]), _num(r["spot_diff_usd"])
    lead = "lead over" if diff >= 0 else "shortfall against"
    verdict = "is not statistically distinguishable from zero" if p >= 0.05 else "is significant"
    spot_txt = f"lost USD {-spot / 1e6:.1f}m" if spot < 0 else f"gained USD {spot / 1e6:.1f}m"
    return (
        f" Its USD {abs(diff) / 1e6:.1f}m {lead} a full hedge {verdict} over "
        f"{int(r['n_months'])} months (p = {p:.2f}): it collected USD {known / 1e6:.1f}m more "
        f"carry net of spread, which is known when the forwards are dealt, and {spot_txt} "
        "on the currency risk it left open, which is not."
    )


def _stress_month_table(d: ReportData) -> pd.DataFrame:
    pm = d.policy_months.copy()
    pm["pnl_total"] = pm["pnl_total"] / 1e6
    tbl = pm.pivot_table(index="month", columns="policy", values="pnl_total", aggfunc="first")
    cols = [p for p in POLICY_LABELS if p in tbl.columns]
    tbl = tbl[cols].rename(columns=POLICY_LABELS)
    es = (
        pm[pm["policy"] == "optimizer"]
        .set_index("month")["ex_ante_es_usd"]
        .div(1e6)
        .rename("optimizer ex-ante ES")
    )
    return tbl.join(es).round(2).reset_index()


HEDGING_COST = "hedging cost / yr (+ = cost)"
SUMMARY_DECIMALS = {
    "P&L vol / yr": 1,
    "total P&L": 1,
    HEDGING_COST: 1,
    "max drawdown": 1,
    "worst month": 1,
    "share of months budget binds": 2,
}


def _summary_table(d: ReportData) -> pd.DataFrame:
    """Backtest summary in USD m, with hedging cost as a cost.

    The backtest stores carry and spread as P&L; the report uses one sign convention
    throughout, positive = the hedges cost money.
    """
    s = d.policy_summary.copy()
    out = pd.DataFrame(
        {
            "policy": s["policy"].map(POLICY_LABELS).fillna(s["policy"]),
            "P&L vol / yr": s["daily_vol_annualized_usd"] / 1e6,
            "total P&L": s["total_pnl_usd"] / 1e6,
            HEDGING_COST: -(s["carry_per_year_usd"] + s["spread_per_year_usd"]) / 1e6,
            "max drawdown": s["max_drawdown_usd"] / 1e6,
            "worst month": s["worst_month_usd"] / 1e6,
            f"months losing > USD {d.hcfg.es_budget_usd / 1e6:g}m": s[
                "months_loss_gt_budget"
            ].astype(int),
            "share of months budget binds": s["share_months_binding"],
        }
    )
    if "months_loss_gt_var" in s.columns:
        out.insert(6, "months loss > ex-ante VaR", s["months_loss_gt_var"].astype(int))
    order = {p: i for i, p in enumerate(POLICY_LABELS.values())}
    return out.sort_values("policy", key=lambda c: c.map(order)).reset_index(drop=True)


def _waterfall_table(d: ReportData) -> pd.DataFrame:
    w = d.waterfall.drop(columns="exposure_date").copy()
    w["ccy"] = w["ccy"].where(~w["ccy"].str.startswith("TOTAL"), TOTAL_LABEL)
    return w.rename(
        columns={
            "gross_usd_m": "gross",
            "net_usd_m": "net",
            "hedge_usd_m": "hedges",
            "net_of_hedges_usd_m": "net of hedges",
        }
    )


def _entity_table(d: ReportData) -> pd.DataFrame:
    return d.entity_latest.rename(
        columns={
            "in_flight_m": "receivables in flight",
            "balance_m": "cash balance",
            "payable_m": "merchant payable",
            "intercompany_m": "intercompany",
            "net_m": "net",
        }
    )


def _forecast_table(d: ReportData) -> pd.DataFrame:
    return d.forecast_by_horizon.rename(
        columns={
            "horizon": "horizon (days)",
            "pinball_pct": "pinball loss, % of exposure",
            "mape_median_pct": "median abs. error, %",
            "coverage_50": "50% interval coverage",
            "coverage_80": "80% interval coverage",
            "coverage_95": "95% interval coverage",
            "skill_vs_naive": "skill vs naive",
        }
    )


def _risk_table(d: ReportData) -> pd.DataFrame:
    r = d.risk_21d.copy()
    r["label"] = r["label"].map(risk_label)
    return r.rename(columns={"label": "model", "net_of_hedges": "net of hedges"})


def _stress_table(d: ReportData) -> pd.DataFrame:
    s = d.stress.copy()
    s["scenario"] = s["scenario"].map(lambda x: SCENARIO_LABELS.get(x, x))
    return s.rename(
        columns={
            "largest_move": "largest move",
            "propagated": "others propagated",
            "implied_moves": "largest implied moves",
            "net_of_hedges": "net of hedges",
        }
    )


def _reference_table(d: ReportData) -> pd.DataFrame:
    r = d.reference
    return pd.DataFrame(
        {
            "policy": r["policy"].map(POLICY_LABELS).fillna(r["policy"]),
            "residual ES (USD m)": r["residual_es_usd"] / 1e6,
            "expected cost (USD m / yr, + = cost)": r["annual_cost_usd"] / 1e6,
        }
    )


def _by_year_table(d: ReportData) -> pd.DataFrame:
    by = d.policy_by_year.copy()
    by["pnl"] = by["pnl_total_usd"] / 1e6
    tbl = by.pivot_table(index="year", columns="policy", values="pnl", aggfunc="first")
    cols = [p for p in POLICY_LABELS if p in tbl.columns]
    tbl = tbl[cols].rename(columns=POLICY_LABELS).round(1)
    breaches = (
        by[by["policy"] == "optimizer"]
        .set_index("year")["months_loss_gt_budget"]
        .astype(int)
        .rename(f"optimizer months losing > USD {d.hcfg.es_budget_usd / 1e6:g}m")
    )
    return tbl.join(breaches).reset_index()


def _recommendation_table(d: ReportData) -> pd.DataFrame:
    r = d.recommendation.copy()
    return r[
        [
            "ccy",
            "exposure_usd_m",
            "hedge_ratio",
            "notional_usd_m",
            "carry_pct_annual",
            "spread_bp",
            "rate_source",
        ]
    ].rename(
        columns={
            "exposure_usd_m": "forecast exposure (USD m)",
            "hedge_ratio": "hedge ratio",
            "notional_usd_m": "forward notional (USD m)",
            "carry_pct_annual": "carry % / yr (+ = costs)",
            "spread_bp": "spread bp",
            "rate_source": "rate source",
        }
    )


def _var_table(d: ReportData) -> pd.DataFrame:
    v = d.var_backtest.copy()
    out = pd.DataFrame(
        {
            "model": v["method"].map(lambda m: VAR_METHOD_LABELS.get(m, m)),
            "confidence": v["confidence"].map(lambda c: f"{c:.0%}"),
            "exceptions": v["n_exceptions"].astype(int),
            "expected": v["expected_exceptions"],
            "Kupiec p": v["kupiec_p"],
            "Christoffersen p": v["christoffersen_p"],
            "traffic light": v["traffic_light"],
            "Acerbi-Szekely Z2 p": v["z2_p"],
            "verdict": v["verdict"],
        }
    )
    if "n_consecutive" in v.columns:
        out.insert(4, "back-to-back", v["n_consecutive"].astype(int))
    return out


def _var_label(method: str) -> str:
    return f"the {VAR_METHOD_LABELS.get(method, method)} model"


def _selection_text(d: ReportData) -> str:
    """How the model was chosen before the test window, and how firm that choice is."""
    s = d.var_selection
    if s.empty or not s["selected"].astype(bool).any():
        return ""
    best = s[s["selected"].astype(bool)].iloc[0]
    rivals = s[~s["selected"].astype(bool) & s["optimizer_compatible"].astype(bool)]
    text = (
        f"The model was chosen before that window opens: over {int(best['sel_n'])} days of "
        "2012-2014, scoring VaR and ES together with the FZ0 loss, "
        f"{_var_label(str(best['method']))} scored best of the models the optimizer can use."
    )
    if not rivals.empty:
        r = rivals.sort_values("sel_fz0").iloc[0]
        p = _num(r["dm_p_vs_selected"])
        verdict = "is not distinguishable from it" if p >= 0.05 else "is significantly worse"
        text += (
            f" The runner-up, {_var_label(str(r['method']))}, {verdict} "
            f"(Diebold-Mariano p = {p:.2f})"
        )
        if _num(r["oos_fz0"]) < _num(best["oos_fz0"]):
            text += ", and scores slightly better after 2015; the choice is kept, not revisited"
        text += "."
    return text


def _model_choice_text(d: ReportData) -> str:
    """Say which model the optimizer uses, how it was chosen and whether it passed."""
    v = d.var_backtest
    at = v[(v["confidence"] - d.hcfg.confidence).abs() < 1e-9]
    level = _pct(d.hcfg.confidence)
    method = method_for_ewma(d.hcfg.risk_lam) or f"t_ewma (lambda {d.hcfg.risk_lam:g})"
    name = _var_label(method)
    parts = [_selection_text(d)]
    s = d.var_selection
    if not s.empty and s["selected"].astype(bool).any():
        chosen = str(s[s["selected"].astype(bool)].iloc[0]["method"])
        if chosen != method:
            parts.append(f"The configuration uses {name}, not the selected model.")
    row = at[at["method"] == method]
    if row.empty:
        parts.append(f"The optimizer uses {name}; it was not backtested in this run.")
        return " ".join(p for p in parts if p)
    r = row.iloc[0]
    if str(r["verdict"]) == "PASS":
        parts.append(f"The optimizer uses {name}, which passes every test at {level}.")
        return " ".join(p for p in parts if p)
    failed = [
        label
        for col, label in (
            ("kupiec_p", "exception count (Kupiec)"),
            ("christoffersen_p", "independence (Christoffersen)"),
            ("z2_p", "ES size (Acerbi-Szekely)"),
        )
        if _num(r[col]) < 0.05
    ]
    none_pass = not (at["verdict"] == "PASS").any()
    lead = f"No model passes every test at {level} on this book. " if none_pass else ""
    text = (
        f"{lead}The optimizer uses {name}, which fails on "
        f"{', '.join(failed) or 'conditional coverage'}: "
        f"{int(r['n_exceptions'])} exceptions against {_num(r['expected_exceptions']):.1f} "
        f"expected (Kupiec p = {_num(r['kupiec_p']):.2f}), Christoffersen p = "
        f"{_num(r['christoffersen_p']):.2f}, Acerbi-Szekely p = {_num(r['z2_p']):.2f}."
    )
    if "n_consecutive" in r.index and _num(r["christoffersen_p"]) < 0.05:
        n = int(r["n_consecutive"])
        text += (
            f" The independence failure rests on {n} exception{'s' if n != 1 else ''} that "
            "came the day after another: the model is right on average but slow to react "
            "inside a shock, so in a stressed week its ES budget is a looser bound than the "
            "table suggests."
        )
    else:
        text += " Its ES budget is therefore a less reliable bound than the table suggests."
    parts.append(text)
    return " ".join(p for p in parts if p)


VAR_DECIMALS = {"expected": 1, "Kupiec p": 2, "Christoffersen p": 2, "Acerbi-Szekely Z2 p": 2}


def render_sections(d: ReportData) -> list[tuple[str, str]]:
    """The report body as ``(heading, markdown)`` pairs, in reading order."""
    h = d.hedge_headline
    figs = d.figures
    opt = _policy_row(d.policy_summary, "optimizer")
    fh = _policy_row(d.policy_summary, "full_hedge")
    cov95_21 = float(
        d.forecast_by_horizon.loc[
            d.forecast_by_horizon["horizon"] == d.hcfg.horizon_days, "coverage_95"
        ].iloc[0]
    )
    skill_21 = float(
        d.forecast_by_horizon.loc[
            d.forecast_by_horizon["horizon"] == d.hcfg.horizon_days, "skill_vs_naive"
        ].iloc[0]
    )
    passing = d.var_backtest[d.var_backtest["verdict"] == "PASS"]
    pass_txt = (
        "; ".join(
            f"{VAR_METHOD_LABELS.get(str(r.method), str(r.method))} at {_num(r.confidence):.0%}"
            for r in passing.itertuples()
        )
        or "none"
    )
    total = d.waterfall[d.waterfall["ccy"].str.startswith("TOTAL")].iloc[0]
    wf = d.waterfall[~d.waterfall["ccy"].str.startswith("TOTAL")]
    wf_date = pd.Timestamp(wf["exposure_date"].iloc[0]).date()
    biggest = wf.iloc[wf["net_usd_m"].abs().argmax()]
    frontier_txt = _frontier_text(d)
    worst_opt = d.policy_months[d.policy_months["policy"] == "optimizer"].sort_values("pnl_total")
    worst_month = worst_opt.iloc[0] if not worst_opt.empty else None

    sections: list[tuple[str, str]] = []

    sections.append(
        (
            "The question and the answer",
            "*For a fixed Expected Shortfall budget at the 21-day horizon, what hedge ratios by "
            "currency minimise expected hedging cost, and how would that policy have performed "
            "out of sample from 2015 to the present, including March 2020 and 2022?*\n\n"
            + headline_answer(d)
            + "\n\n"
            + df_to_markdown(
                _recommendation_table(d),
                decimals={
                    "forecast exposure (USD m)": 1,
                    "hedge ratio": 2,
                    "forward notional (USD m)": 1,
                    "carry % / yr (+ = costs)": 2,
                    "spread bp": 1,
                },
            )
            + "\n\nCarry is the annualized forward discount of the currency against USD "
            "(positive: selling the currency forward costs money; negative: it earns). The "
            "optimizer spends the budget where risk reduction is expensive and hedges "
            "everything that is cheap or free to hedge: "
            + frontier_txt[0].lower()
            + frontier_txt[1:]
            + " The out-of-sample evidence is in the policy section below.",
        )
    )

    sections.append(
        (
            "Data and quality",
            f"Market data: {len(d.quality_summary)} checks on {d.retrieved_on} retrievals, "
            f"overall **{d.quality_overall}** (`reports/quality_report.md`, "
            "`reports/alerts.md`). Sources are FRED H.10 noon rates (primary), Bank of Canada "
            "and ECB crosses (reconciliation and fallback), BIS policy rates and effective "
            "exchange rates, the ECB deposit rate, and US and Canadian retail sales for "
            "the seasonality of the synthetic flows. The flows themselves are generated from "
            "`config/flows.yaml`; no real company's data is used.\n\n"
            + df_to_markdown(d.quality_summary),
        )
    )

    sections.append(
        (
            "Exposure waterfall",
            f"Net open exposure by currency on {wf_date}, USD millions. *Gross* is the "
            "sum of the absolute components (receivables in flight, cash balances, merchant "
            "payables, intercompany loans) across the four entities; *net* nets them within a "
            "currency across entities; *net of hedges* adds the forwards in force on that date "
            "(the optimizer's positions where the policy has dealt, else the legacy 50% "
            f"placeholder). Netting takes the group from USD {total['gross_usd_m']:,.0f}m gross "
            f"to {total['net_usd_m']:,.0f}m of absolute net exposure, and hedges to "
            f"{total['net_of_hedges_usd_m']:,.0f}m. The largest net position is "
            f"{biggest['ccy']} at USD {biggest['net_usd_m']:,.1f}m. A negative net-of-hedges "
            "figure on a month-end is expected: exposure in the synthetic business dips on the "
            "last day of the month when fees are swept and weekly payouts land, while the "
            "forward in force was sized on the average forecast over the whole month and runs "
            "until the next rebalance (ADR-0013; the history figure plots monthly averages for "
            "that reason).\n\n"
            + df_to_markdown(_waterfall_table(d), decimals=1)
            + "\n\n"
            + _fig(figs, "waterfall", "exposure waterfall")
            + "\n\n"
            + _fig(figs, "history", "exposure history")
            + "\n\nBy entity on the same date (USD m; the US parent's intercompany loans are "
            "the subsidiaries' intercompany liabilities):\n\n"
            + df_to_markdown(_entity_table(d), decimals=1),
        )
    )

    sections.append(
        (
            "Exposure forecast and its calibration",
            "The hedge is sized on the forecast of net exposure averaged over the month the "
            "forward covers, not on today's book, because today's receivables will have "
            "settled by then. The model is a calendar-structural regression of log exposure "
            "on weekday, month-end and month-start position, month and trend, with AR(1) "
            "errors (ADR-0011). Rolling-origin evaluation over monthly origins from "
            f"{d.hcfg.oos_start.year - 1} against a seasonal-naive baseline (the value on "
            "the same weekday four weeks earlier):\n\n"
            + df_to_markdown(
                _forecast_table(d),
                decimals={
                    "pinball loss, % of exposure": 1,
                    "median abs. error, %": 1,
                    "50% interval coverage": 2,
                    "80% interval coverage": 2,
                    "95% interval coverage": 2,
                    "skill vs naive": 2,
                },
            )
            + f"\n\nAt the policy horizon the model's skill against the naive is "
            f"{skill_21:.2f} (pinball loss reduced by {_pct(skill_21)}) and its nominal 95% "
            f"interval covers {_pct(cov95_21)} of outcomes. The intervals are therefore too "
            "narrow; the report states that rather than widening them after the fact, and "
            "the hedge policy uses the median, not the band. The skill is also an upper "
            "bound: the regression has the same terms (weekday, month end, month, trend, "
            "AR(1)) the synthetic flows were generated with, so it is correctly specified by "
            "construction; on a real book it would have to find that structure. The "
            "calibration figure shows coverage by horizon and quantile.\n\n"
            + _fig(figs, "calibration", "forecast calibration")
            + f"\n\nLatest {d.hcfg.horizon_days}-day-ahead forecast (currency units):\n\n"
            + df_to_markdown(
                d.forecast_latest.rename(columns={"target_date": "target date"}),
                decimals={"2.5%": 0, "median": 0, "97.5%": 0},
            ),
        )
    )

    sections.append(
        (
            "Risk model: VaR, Expected Shortfall and the coverage verdicts",
            f"Expected Shortfall at {d.hcfg.horizon_days} days / {d.hcfg.confidence:.0%} on "
            f"{d.as_of.date()}, USD m, for every method family in the engine, on the net "
            "exposure and on the exposure net of hedges in force:\n\n"
            + df_to_markdown(_risk_table(d), decimals=1)
            + "\n\nWhich of these to believe is decided by the one-day coverage backtest on "
            f"the net exposure from {d.hcfg.oos_start.year} (Kupiec unconditional coverage, "
            "Christoffersen "
            "independence, Basel traffic light, Acerbi-Szekely Z2 for ES). A verdict of PASS "
            f"needs every p-value at or above 0.05. Passing: {pass_txt}.\n\n"
            + df_to_markdown(_var_table(d), decimals=VAR_DECIMALS)
            + "\n\n"
            + _model_choice_text(d)
            + f" Its tail index is {float(h['nu']):.1f} on the latest window. Multi-day "
            "coverage is not "
            "tested formally because overlapping windows break the tests' independence "
            "assumption (ADR-0010); the 21-day ES is the one-day model scaled by the "
            "square-root of time under the t distribution.",
        )
    )

    sections.append(
        (
            "Stress",
            "Historical replays of five episodes and four hypothetical shocks applied to the "
            f"net exposure on {d.as_of.date()}, P&L in USD m. *Propagated* means the shock is "
            "given to the named currencies and the others move by their Gaussian conditional "
            "expectation under the 1,000-day covariance, listed as the largest implied moves; "
            "otherwise only the named currencies move. Shocks are quoted against USD, so a "
            "conditional move partly expresses broad USD strength or weakness.\n\n"
            + df_to_markdown(_stress_table(d), decimals={"net": 1, "net of hedges": 1}),
        )
    )

    sections.append(
        (
            "Cost of risk reduction: the frontier and the chosen point",
            "The frontier traces the minimum expected hedging cost (carry plus spread, per "
            "year) for every ES budget from zero (full hedge) to the unhedged ES. "
            + frontier_txt
            + " Reference policies at today's exposures:\n\n"
            + df_to_markdown(_reference_table(d), decimals=2)
            + "\n\n"
            + _fig(figs, "frontier", "cost-risk frontier")
            + "\n\nThe optimizer is a convex programme (linear cost, ES of a linear book under "
            "an elliptical distribution is a norm of an affine function of the ratios) solved "
            f"with SLSQP. A {d.hcfg.turnover_penalty_bp:g} bp penalty on the change in notional "
            "since the previous month is added to the objective as a preference for a stable "
            "programme; it reduces month-to-month swings in the ratios without measurably "
            "changing P&L, volatility or cost (ADR-0012).",
        )
    )

    months_txt = ""
    if worst_month is not None:
        months_txt = (
            f" The optimizer's worst of the four was {worst_month['month']} at USD "
            f"{_m(worst_month['pnl_total'])}m against an ex-ante ES of "
            f"{_m(worst_month['ex_ante_es_usd'])}m: the budget bounds the risk of the hedged "
            "*forecast* exposure, not forecast error or intra-month exposure swings, which is "
            f"also why the full hedge keeps USD {_m(fh['daily_vol_annualized_usd'])}m of "
            "annual P&L volatility."
        )
    sections.append(
        (
            "Out-of-sample policy performance, 2015 to the present",
            f"Walk-forward backtest, monthly rebalance from {d.hcfg.oos_start}, one-month "
            "forwards priced by covered interest parity at each origin, hedging the median "
            "forecast averaged over the month each forward covers; P&L marked on the actual "
            "daily exposure path with forward mark-to-market, carry accrual and spread "
            "(ADR-0013). No look-ahead: covariance, tail index, rates and forecasts use data "
            "up to the origin only.\n\n"
            + df_to_markdown(_summary_table(d), decimals=SUMMARY_DECIMALS)
            + "\n\nUSD m. Hedging cost is carry plus bid-ask spread per year, positive when "
            "the hedges cost money, the same convention as the frontier above. Months losing "
            "more than the budget is a plain loss frequency, comparable across policies; the "
            "model test is the count of months beyond each policy's own ex-ante "
            f"{_pct(d.hcfg.confidence)} VaR, about {_pct(1 - d.hcfg.confidence)} of months if "
            "the model is right. A full hedge of the forecast has no ex-ante risk in the "
            "model, so every month it loses counts: its risk is all forecast error."
            + "\n\nMean optimizer hedge ratio over the backtest: "
            + ", ".join(f"{c} {v:.2f}" for c, v in d.ratios_mean.items())
            + ".\n\n"
            + _fig(figs, "cumulative", "cumulative P&L by policy")
            + "\n\n"
            + _fig(figs, "ratios", "optimizer hedge ratios by month")
            + "\n\n**March 2020 and 2022.** Monthly P&L by policy in the four stress months, "
            "USD m:\n\n"
            + df_to_markdown(_stress_month_table(d), decimals=1)
            + "\n\n"
            + months_txt.strip()
            + "\n\n**By year** (total P&L, USD m):\n\n"
            + df_to_markdown(
                _by_year_table(d),
                decimals={label: 1 for label in POLICY_LABELS.values()},
            )
            + "\n\n"
            + _fig(figs, "monthly", "monthly P&L distribution by policy"),
        )
    )

    sections.append(
        (
            "What this model does not know",
            _limitations(d, cov95_21, opt, fh),
        )
    )

    sections.append(
        (
            "Reproducing this report",
            "```bash\nuv sync --all-groups\nuv run fxrisk all      # fetch (cache) -> quality -> "
            "flows -> exposure -> forecast -> backtest -> hedge -> risk -> report\n```\n\n"
            "Every number above is read from the DuckDB tables the stages write "
            "(`data/fxrisk.duckdb`); `fxrisk report` recomputes nothing. Inputs: "
            "`config/flows.yaml` (the stylized business), `config/hedge.yaml` (budget, costs, "
            "policies), `data/cache/` (market data with provenance in `manifest.json`). "
            "Methods: `docs/methodology.md`; decisions: `docs/decisions/`; instrument "
            f"mechanics: `docs/hedging-primer.md`. Package version {__version__}.",
        )
    )
    return sections


def _frontier_text(d: ReportData) -> str:
    fr = d.frontier.sort_values("budget_usd")
    full = fr.iloc[0]
    budget = float(d.hedge_headline["budget_usd"])
    at_budget = fr.iloc[(fr["budget_usd"] - budget).abs().argmin()]
    # the frontier flattens where the budget stops binding
    slack = fr[fr["residual_es_usd"] < fr["budget_usd"] - 1e-6]
    flat_txt = ""
    if not slack.empty:
        flat_txt = (
            f" Beyond a budget of about USD {float(slack['budget_usd'].iloc[0]) / 1e6:.0f}m the "
            "constraint stops binding and the policy is simply 'hedge every currency whose "
            "forward earns carry', which is the cheapest book regardless of risk."
        )
    return (
        f"A full hedge costs USD {float(full['annual_cost_usd']) / 1e6:.2f}m a year for zero "
        f"residual ES, while at the USD {budget / 1e6:.0f}m budget the cost is USD "
        f"{float(at_budget['annual_cost_usd']) / 1e6:.2f}m a year (negative = the programme "
        f"earns carry).{flat_txt}"
    )


def _limitations(d: ReportData, cov95: float, opt: pd.Series, fh: pd.Series) -> str:
    items = [
        "**The business is synthetic.** Volumes, settlement lags, payout cadences and the "
        "2020 regimes are stylized and calibrated only to public retail-sales seasonality "
        "(ADR-0008). The *method* transfers to a real book; the numbers do not.",
        "**The ES budget covers the hedged forecast exposure only.** Forecast error and "
        "intra-month exposure variation are outside it: the model sees no risk in a full "
        "hedge of the forecast, yet that policy keeps USD "
        f"{_m(fh['daily_vol_annualized_usd'])}m of annual P&L volatility (ADR-0013). "
        + _var_exceedance_text(d, opt)
        + " A budget meant to bound realized monthly loss would need to be set lower, or the "
        "policy would need an intra-month adjustment rule (backlog B17).",
        f"**Forecast intervals are too narrow.** The nominal 95% band covers {_pct(cov95)} at "
        f"the {d.hcfg.horizon_days}-day horizon (ADR-0011, backlog B16). The policy uses the "
        "median, so this affects the risk statement, not the hedge sizes. Its skill is "
        "flattered too: the model has the generator's own terms, a correct specification a "
        "real book would not hand it.",
        "**Carry is an expected cost under a random-walk spot.** Realized hedging cost in the "
        "backtest includes the spot move and can have either sign; the carry signal itself "
        "is not a forecast of returns (hedging primer, section 3).",
        "**Forwards only.** No options, no cross-currency basis, no NDF basis for BRL and "
        "INR; one-way spreads are stylized round numbers from `config/hedge.yaml` (hedging "
        "primer, section 5; backlog B3, B4, B18).",
        "**Forwards are priced off central-bank policy rates**, the ECB deposit rate for the "
        "euro area, so carry ignores rate changes expected within the month; one- and "
        "three-month OIS rates would be better but are not freely available. The SGD rate is "
        "a flagged USD proxy, so SGD carry is zero by construction (ADR-0015, backlog B1, B2).",
        "**Coverage is tested at one day.** The 21-day ES is a scaled one-day model; the "
        "overlapping-window tests at longer horizons have too little power to be decisive "
        "(ADR-0010, backlog B11).",
        "**One risk model inside the optimizer, and it does not pass every test.** The "
        "Student-t EWMA model was chosen on the coverage backtest over the same 2015-2026 "
        "period the policy is evaluated on, and on the current book its exceptions "
        "cluster. The engine reports every model so the choice can be revisited.",
        "**Fixing-time mismatches** between sources (noon New York, 14:15 CET, Bank of "
        "Canada daily average) are reconciled within tolerance, not modelled (ADR-0005).",
        "**Weekday calendar, no holidays**, for settlement and payouts (backlog B9).",
    ]
    return "\n".join(f"* {i}" for i in items)


# ---------------------------------------------------------------------------- pipeline


def run_report(paths: config.Paths, hcfg: HedgeConfig | None = None) -> Path:
    """Draw the two exposure figures, assemble the report, write ``reports/decision_report.md``."""
    data = load_report_data(paths, hcfg)
    figs = paths.figures_dir
    wf = data.waterfall[~data.waterfall["ccy"].str.startswith("TOTAL")]
    data.figures = {
        "waterfall": plots.waterfall_plot(wf, figs / "exposure_waterfall.png"),
        "history": plots.exposure_history_plot(
            data.exposure_monthly, figs / "exposure_history.png"
        ),
        "calibration": figs / "forecast_calibration.png",
        "frontier": figs / "hedge_frontier.png",
        "cumulative": figs / "policy_cumulative_pnl.png",
        "ratios": figs / "policy_hedge_ratios.png",
        "monthly": figs / "policy_monthly_pnl.png",
    }
    missing = [k for k, p in data.figures.items() if not p.exists()]
    for k in missing:
        log.warning("figure %s missing (%s); the report will note it", k, data.figures[k])
        del data.figures[k]
    out = paths.reports_dir / REPORT_NAME
    write_markdown(
        out,
        f"FX hedging decision report as of {data.as_of.date()}",
        [
            (
                "Summary",
                f"Generated {pd.Timestamp.now(tz='UTC').strftime('%Y-%m-%d %H:%M UTC')} from "
                f"market data retrieved {data.retrieved_on}; data quality "
                f"**{data.quality_overall}**; ES budget USD "
                f"{fmt(data.hcfg.es_budget_usd / 1e6)}m at {data.hcfg.horizon_days} days / "
                f"{data.hcfg.confidence:.0%}; exposure input: "
                f"{data.hedge_headline['exposure_source']}.",
            ),
            *render_sections(data),
        ],
    )
    log.info("decision report written: %s", out)
    return out
