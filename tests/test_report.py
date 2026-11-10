"""Decision report: the renderer on hand-made frames, and the loader against a small DuckDB."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import duckdb
import pandas as pd
import pytest

from fx_treasury_risk import config, db
from fx_treasury_risk.hedge.config import HedgeConfig
from fx_treasury_risk.report import decision
from fx_treasury_risk.report.tables import fmt

CCYS = ["EUR", "GBP", "BRL"]


def _hcfg() -> HedgeConfig:
    return HedgeConfig(
        es_budget_usd=4e6,
        horizon_days=21,
        confidence=0.99,
        risk_lam=0.94,
        risk_window=1000,
        forward_tenor_days=30,
        bid_ask_bp={c: 1.0 for c in CCYS},
        min_ticket_usd=0.0,
        oos_start=date(2015, 1, 1),
        exposure_input="forecast",
        policies=("unhedged", "legacy_50", "full_hedge", "optimizer"),
        turnover_penalty_bp=2.0,
    )


def _data(tmp_path: Path) -> decision.ReportData:
    policies = ["unhedged", "legacy_50", "full_hedge", "optimizer"]
    summary = pd.DataFrame(
        {
            "policy": policies,
            "daily_vol_annualized_usd": [20e6, 11e6, 7e6, 8e6],
            "monthly_vol_usd": [6e6, 3e6, 2e6, 2e6],
            "total_pnl_usd": [-36e6, -19e6, -2e6, 9.6e6],
            "carry_per_year_usd": [0, -0.5e6, -1e6, 2.1e6],
            "spread_per_year_usd": [0, -0.3e6, -0.6e6, -0.2e6],
            "max_drawdown_usd": [-72e6, -45e6, -21e6, -19e6],
            "worst_month_usd": [-14e6, -11e6, -8e6, -9e6],
            "months_loss_gt_budget": [39, 21, 2, 5],
            "n_months": [142] * 4,
            "mean_ex_ante_es_usd": [17e6, 9e6, 0, 4e6],
            "share_months_binding": [0, 0, 0, 0.6],
        }
    )
    months = pd.DataFrame(
        [
            {
                "policy": p,
                "rebalance": pd.Timestamp(m),
                "month": m[:7],
                "pnl_total": v,
                "ex_ante_es_usd": 4e6,
            }
            for m in ("2020-03-02", "2022-09-01")
            for p, v in zip(policies, [-10e6, -5e6, 1e6, -5.6e6], strict=True)
        ]
    )
    by_year = pd.DataFrame(
        [
            {
                "policy": p,
                "year": y,
                "pnl_total_usd": 1e6 * (i - 1),
                "monthly_vol_usd": 2e6,
                "worst_month_usd": -3e6,
                "carry_usd": 0.1e6,
                "spread_usd": -0.1e6,
                "months_loss_gt_budget": 1,
            }
            for y in (2015, 2016)
            for i, p in enumerate(policies)
        ]
    )
    rec = pd.DataFrame(
        {
            "ccy": CCYS,
            "exposure_fcy": [1e8, 7e7, 1.5e8],
            "exposure_usd_m": [110.0, 90.0, 28.0],
            "hedge_ratio": [1.0, 1.0, 0.7],
            "notional_usd_m": [-110.0, -90.0, -19.6],
            "carry_pct_annual": [-1.5, -0.3, 9.8],
            "spread_bp": [0.5, 0.7, 8.0],
            "rate_source": ["bis:D.XM", "bis:D.GB", "fred:IRSTCI01BRM156N"],
            "is_proxy": [False, False, False],
        }
    )
    frontier = pd.DataFrame(
        {
            "budget_usd": [0, 2e6, 4e6, 8e6, 12e6],
            "residual_es_usd": [0, 2e6, 4e6, 8e6, 9.8e6],
            "annual_cost_usd": [0.6e6, -0.5e6, -1.7e6, -3.3e6, -3.9e6],
            "mean_ratio": [1, 0.9, 0.8, 0.7, 0.5],
        }
    )
    wf = pd.DataFrame(
        {
            "exposure_date": [pd.Timestamp("2026-10-30")] * 4,
            "ccy": [*CCYS, "TOTAL (abs)"],
            "gross_usd_m": [370.0, 280.0, 29.0, 679.0],
            "net_usd_m": [63.0, 47.0, 20.0, 130.0],
            "hedge_usd_m": [-167.0, -123.0, 0.0, 290.0],
            "net_of_hedges_usd_m": [-104.0, -76.0, 20.0, 200.0],
        }
    )
    head = pd.Series(
        {
            "as_of": pd.Timestamp("2026-10-30"),
            "exposure_source": "calendar_ar1 median forecast, 21 days ahead",
            "unhedged_es_usd": 19.55e6,
            "residual_es_usd": 4e6,
            "budget_usd": 4e6,
            "carry_per_year_usd": -2.13e6,
            "spread_per_year_usd": 0.47e6,
            "nu": 4.9,
            "binding": True,
        }
    )
    fbh = pd.DataFrame(
        {
            "horizon": [1, 21, 63],
            "pinball_pct": [2.0, 2.0, 2.0],
            "mape_median_pct": [7.0, 6.8, 6.9],
            "coverage_50": [0.43, 0.40, 0.42],
            "coverage_80": [0.71, 0.69, 0.69],
            "coverage_95": [0.88, 0.86, 0.83],
            "skill_vs_naive": [0.76, 0.80, 0.77],
        }
    )
    return decision.ReportData(
        as_of=pd.Timestamp("2026-10-30"),
        hcfg=_hcfg(),
        retrieved_on="2026-11-06",
        quality_overall="WARN",
        quality_summary=pd.DataFrame(
            {"check": ["staleness"], "status": ["WARN"], "summary": ["2 series stale"]}
        ),
        waterfall=wf,
        entity_latest=pd.DataFrame(
            {
                "entity": ["US"],
                "ccy": ["EUR"],
                "in_flight_m": [1.0],
                "balance_m": [1.0],
                "payable_m": [-1.0],
                "intercompany_m": [0.0],
                "net_m": [1.0],
            }
        ),
        exposure_monthly=pd.DataFrame(
            {
                "month": pd.to_datetime(["2026-09-01", "2026-10-01"]),
                "gross_usd_m": [1800.0, 1850.0],
                "net_abs_usd_m": [450.0, 470.0],
                "net_of_hedges_abs_usd_m": [180.0, 190.0],
                "n_days": [22, 22],
            }
        ),
        forecast_by_horizon=fbh,
        forecast_latest=pd.DataFrame(
            {
                "ccy": CCYS,
                "target_date": [pd.Timestamp("2026-11-30")] * 3,
                "2.5%": [1e8, 6e7, 1.4e8],
                "median": [1.1e8, 7e7, 1.5e8],
                "97.5%": [1.3e8, 8e7, 1.7e8],
            }
        ),
        var_backtest=pd.DataFrame(
            {
                "basis": ["net", "net"],
                "method": ["t_ewma", "historical"],
                "confidence": [0.99, 0.99],
                "n_exceptions": [34, 30],
                "expected_exceptions": [29.6, 29.6],
                "kupiec_p": [0.42, 0.94],
                "christoffersen_p": [0.40, 0.0],
                "traffic_light": ["green", "green"],
                "z2_p": [0.17, 0.52],
                "verdict": ["PASS", "FAIL"],
            }
        ),
        risk_21d=pd.DataFrame(
            {"label": ["parametric_t / ewma_0.94"], "net": [11.2], "net_of_hedges": [10.6]}
        ),
        stress=pd.DataFrame(
            {
                "scenario": ["covid_2020"],
                "kind": ["historical"],
                "largest_move": ["MXN -17.5%"],
                "propagated": [False],
                "net": [-16.6],
                "net_of_hedges": [11.1],
            }
        ),
        hedge_headline=head,
        recommendation=rec,
        reference=pd.DataFrame(
            {
                "policy": ["unhedged", "full_hedge", "optimizer"],
                "residual_es_usd": [19.55e6, 0, 4e6],
                "annual_cost_usd": [0, 0.63e6, -1.66e6],
            }
        ),
        frontier=frontier,
        policy_summary=summary,
        policy_months=months,
        policy_by_year=by_year,
        ratios_mean=pd.Series([1.0, 0.99, 0.09], index=CCYS),
        figures={"frontier": tmp_path / "hedge_frontier.png"},
    )


def test_headline_answer_reads_the_numbers(tmp_path: Path) -> None:
    text = decision.headline_answer(_data(tmp_path))
    assert "hedge EUR, GBP in full" in text
    assert "BRL 70%" in text
    assert "earns about USD 2.1m a year of carry" in text
    assert "USD 19.6m to USD 4.0m" in text
    assert "5 of 142 months" in text
    assert "(142 months)" in text


def test_headline_answer_states_a_carry_cost_when_positive(tmp_path: Path) -> None:
    d = _data(tmp_path)
    d.hedge_headline["carry_per_year_usd"] = 1.2e6
    assert "costs about USD 1.2m a year of carry" in decision.headline_answer(d)


def test_sections_answer_first_and_figures_referenced(tmp_path: Path) -> None:
    sections = decision.render_sections(_data(tmp_path))
    headings = [h for h, _ in sections]
    assert headings[0].startswith("The question")
    for key in ("Exposure waterfall", "forecast", "VaR", "Stress", "frontier", "Out-of-sample"):
        assert any(key.lower() in h.lower() for h in headings), key
    assert headings[-2] == "What this model does not know"
    body = "\n".join(b for _, b in sections)
    assert "![cost-risk frontier](figures/hedge_frontier.png)" in body
    assert "(figure cumulative not generated)" in body  # missing figures are noted, not fatal
    assert "2020-03" in body and "2022-09" in body
    assert "86%" in body  # the interval coverage is stated


def test_fixed_decimals_and_readable_labels(tmp_path: Path) -> None:
    from fx_treasury_risk.report.tables import df_to_markdown, fmt_fixed

    assert fmt_fixed(1.0, 2) == "1.00" and fmt_fixed(-0.04, 1) == "0.0"
    assert fmt_fixed(1234.5, 1) == "1,234.5" and fmt_fixed(3, 1) == "3"
    md = df_to_markdown(pd.DataFrame({"a": [1.0], "b": [0.5]}), decimals={"a": 2})
    assert "| 1.00 | 0.5 |" in md
    d = _data(tmp_path)
    assert list(decision._risk_table(d)["model"]) == ["Student-t, EWMA 0.94"]
    assert decision._waterfall_table(d)["ccy"].iloc[-1] == decision.TOTAL_LABEL
    # one sign convention: the backtest stores carry as P&L, the report shows it as cost
    s = decision._summary_table(d).set_index("policy")
    raw = d.policy_summary.set_index("policy")
    opt = raw.loc["optimizer"]
    assert s.loc["optimizer", decision.HEDGING_COST] == pytest.approx(
        -(opt["carry_per_year_usd"] + opt["spread_per_year_usd"]) / 1e6
    )


def test_stress_month_table_is_months_by_policy(tmp_path: Path) -> None:
    tbl = decision._stress_month_table(_data(tmp_path))
    assert list(tbl.columns) == [
        "month",
        "unhedged",
        "legacy 50%",
        "full hedge",
        "optimizer",
        "optimizer ex-ante ES",
    ]
    assert tbl.loc[tbl["month"] == "2020-03", "optimizer"].iloc[0] == pytest.approx(-5.6)


def test_fmt_negative_zero() -> None:
    assert fmt(-0.0) == "0" and fmt(0.0) == "0" and fmt(-0.004) == "0"
    assert fmt(-0.0004) == "-0.0004" and fmt(-0.01) == "-0.01"


def test_load_quality_reads_the_stored_checks() -> None:
    con = duckdb.connect()
    assert decision._load_quality(con)[0] == "not run"
    con.execute(
        "CREATE TABLE quality_checks AS SELECT * FROM (VALUES "
        "('a', 'PASS', 'fine'), ('b', 'WARN', 'meh')) AS t(check_name, status, summary)"
    )
    overall, table = decision._load_quality(con)
    assert overall == "WARN"
    assert list(table["check"]) == ["a", "b"] and list(table.columns) == [
        "check",
        "status",
        "summary",
    ]
    con.execute("INSERT INTO quality_checks VALUES ('c', 'FAIL', 'no')")
    assert decision._load_quality(con)[0] == "FAIL"
    con.close()


@pytest.mark.skipif(
    not (config.REPO_ROOT / "data" / "fxrisk.duckdb").exists(),
    reason="full pipeline database not present",
)
def test_load_report_data_from_pipeline_db() -> None:
    """Against the real database when it exists: every frame non-empty, dates consistent."""
    paths = config.Paths.from_env()
    con = db.connect(paths, read_only=True)
    try:
        needed = {"hedge_headline", "policy_backtest_summary", "forecast_eval", "risk_results"}
        have = {
            r[0] for r in con.execute("SELECT table_name FROM information_schema.tables").fetchall()
        }
    finally:
        con.close()
    if not needed <= have:
        pytest.skip("pipeline stages not all run")
    d = decision.load_report_data(paths)
    assert len(d.recommendation) == len(config.EXPOSURE_CCYS)
    assert set(d.policy_summary["policy"]) >= {"unhedged", "optimizer"}
    assert d.hcfg.horizon_days in set(d.forecast_by_horizon["horizon"])
    wf_date = pd.Timestamp(d.waterfall["exposure_date"].iloc[0])
    assert wf_date == d.as_of  # waterfall dated on the last FX date, same as the hedge


def test_report_views_sql_parses(tmp_path: Path) -> None:
    """The report views build on a minimal exposure_group_fx / waterfall / daily_usd."""
    con = duckdb.connect(str(tmp_path / "t.duckdb"))
    con.execute(
        "CREATE TABLE exposure_group_fx AS SELECT * FROM (VALUES "
        "(DATE '2026-10-29','EUR',1.1,100.0,110.0,50.0,55.0,200.0),"
        "(DATE '2026-10-30','EUR',1.1,100.0,110.0,50.0,55.0,200.0)) "
        "t(obs_date,ccy,usd_per_fcy,net_fcy,net_usd,net_of_hedges_fcy,net_of_hedges_usd,gross_usd)"
    )
    con.execute(
        "CREATE TABLE exposure_waterfall_by_ccy AS SELECT * FROM (VALUES "
        "(DATE '2026-10-30','EUR',200.0,110.0,-55.0,55.0,100.0,-50.0,50.0),"
        "(DATE '2026-10-31','EUR',200.0,110.0,-55.0,55.0,100.0,-50.0,50.0)) "
        "t(exposure_date,ccy,gross_usd,net_usd,hedge_usd,net_of_hedges_usd,net_fcy,hedge_fcy,"
        "net_of_hedges_fcy)"
    )
    con.execute(
        "CREATE TABLE exposure_daily_usd AS SELECT DATE '2026-10-30' AS exposure_date, 'US' AS "
        "entity, 'EUR' AS ccy, 1.0 AS in_flight_usd, 1.0 AS balance_usd, -1.0 AS payable_usd, "
        "0.0 AS intercompany_usd, 1.0 AS net_usd"
    )
    db.execute_file(con, "110_report_views")
    wf = con.execute("SELECT * FROM report_waterfall_latest").df()
    assert list(wf["ccy"]) == ["EUR", "TOTAL (abs)"]
    assert pd.Timestamp(wf["exposure_date"].iloc[0]) == pd.Timestamp("2026-10-30")
    monthly = con.execute("SELECT * FROM report_exposure_monthly").df()
    assert len(monthly) == 1 and monthly["n_days"].iloc[0] == 2
    assert monthly["gross_usd_m"].iloc[0] == pytest.approx(200 / 1e6)
    con.close()


def test_model_choice_text_does_not_overclaim(tmp_path: Path) -> None:
    d = _data(tmp_path)
    assert "passes every test at 99%" in decision._model_choice_text(d)
    v = d.var_backtest.copy()
    v.loc[v["method"] == "t_ewma", ["christoffersen_p", "verdict"]] = [0.001, "FAIL"]
    d.var_backtest = v
    text = decision._model_choice_text(d)
    assert text.startswith("No model passes every test at 99%")
    assert "independence (Christoffersen)" in text and "Kupiec" in text  # Kupiec p reported
    assert "exception count" not in text  # Kupiec passed, so not listed as a failure


def test_model_choice_text_reports_the_selection(tmp_path: Path) -> None:
    d = _data(tmp_path)
    d.var_selection = pd.DataFrame(
        {
            "method": ["t_ewma", "t_garch", "historical"],
            "optimizer_compatible": [True, True, False],
            "sel_n": [752, 752, 752],
            "sel_fz0": [14.22, 14.23, 14.20],
            "dm_p_vs_selected": [float("nan"), 0.77, 0.3],
            "selected": [True, False, False],
            "oos_fz0": [14.55, 14.54, 14.6],
        }
    )
    text = decision._model_choice_text(d)
    assert "over 752 days of 2012-2014" in text
    assert "GARCH(1,1) volatilities model, is not distinguishable" in text
    assert "scores slightly better after 2015" in text
    assert "not the selected model" not in text
    d.var_selection.loc[:, "selected"] = [False, True, False]
    assert "The configuration uses the Student-t, EWMA 0.94 model, not the selected" in (
        decision._model_choice_text(d)
    )


def test_headline_states_var_exceedances_and_significance(tmp_path: Path) -> None:
    d = _data(tmp_path)
    d.policy_summary["months_loss_gt_var"] = [12, 3, 70, 2]
    d.policy_comparison = pd.DataFrame(
        {
            "policy": ["optimizer"],
            "versus": ["full_hedge"],
            "n_months": [142],
            "total_diff_usd": [14.2e6],
            "p_value": [0.34],
            "carry_spread_diff_usd": [39.8e6],
            "spot_diff_usd": [-25.6e6],
        }
    )
    text = decision.headline_answer(d)
    assert "ex-ante 99% VaR in 2 of 142 months, against about 1.4 expected" in text
    assert "too many" not in text
    d.policy_summary["months_loss_gt_var"] = [12, 3, 70, 5]
    assert "too many (binomial p = 0.015)" in decision.headline_answer(d)
    assert "USD 14.2m lead over a full hedge is not statistically distinguishable" in text
    assert "USD 39.8m more carry net of spread" in text and "lost USD 25.6m" in text
    table = decision._summary_table(d)
    assert "months losing > USD 4m" in table.columns
    assert "months loss > ex-ante VaR" in table.columns


def test_readable_tables_use_display_names() -> None:
    from fx_treasury_risk.report.tables import df_to_markdown

    df = pd.DataFrame(
        {"policy": ["legacy_50", "new_policy"], "kupiec_p": [0.5, 0.25], "custom": [1, 2]}
    )
    raw = df_to_markdown(df)
    assert "legacy_50" in raw and "kupiec_p" in raw
    text = df_to_markdown(df, decimals={"kupiec_p": 2}, readable=True)
    assert "| policy | Kupiec p | custom |" in text
    assert "| legacy 50% | 0.50 | 1 |" in text
    assert "| new_policy | 0.25 | 2 |" in text  # unknown names are printed as stored


def test_readme_block_is_rendered_from_the_report_data(tmp_path: Path) -> None:
    from fx_treasury_risk.report import readme

    d = _data(tmp_path)
    block = readme.render_results(d)
    assert block.startswith(readme.START) and block.endswith(readme.END)
    assert decision.headline_answer(d) in block  # the same paragraph as the report
    assert "| optimizer |" in block and "skill against the seasonal naive" in block
    text = "intro\n" + readme.START + "\nstale numbers\n" + readme.END + "\noutro\n"
    new = readme.replace_block(text, block)
    assert new.startswith("intro\n") and new.endswith("\noutro\n")
    assert "stale numbers" not in new
    assert readme.replace_block(new, block) == new  # idempotent
    with pytest.raises(ValueError, match="no results markers"):
        readme.replace_block("no markers here", block)
