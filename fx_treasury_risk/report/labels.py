"""Display names for the identifiers and column names the stages store.

The database keeps machine-friendly names (``legacy_50``, ``t_ewma``, ``kupiec_p``); every
report shows the names below. One table serves the stage reports and the decision
report, so the same thing is never called two names. Anything not listed is printed as
stored, so a new method, scenario or column never breaks a report.
"""

from __future__ import annotations

import pandas as pd

POLICY_LABELS = {
    "unhedged": "unhedged",
    "legacy_50": "legacy 50%",
    "full_hedge": "full hedge",
    "optimizer": "optimizer",
}
RISK_METHOD_LABELS = {
    "historical": "historical simulation",
    "parametric_normal": "normal",
    "parametric_t": "Student-t",
    "monte_carlo_t": "Monte Carlo, t copula",
}
COV_LABELS = {
    "none": "",
    "sample": "sample covariance",
    "ledoit_wolf": "Ledoit-Wolf",
    "ewma_0.94": "EWMA 0.94",
    "ewma_0.97": "EWMA 0.97",
}
VAR_METHOD_LABELS = {
    "historical": "historical simulation",
    "normal_sample": "normal, sample covariance",
    "normal_ewma": "normal, EWMA 0.94",
    "t_ewma": "Student-t, EWMA 0.94",
    "t_ewma97": "Student-t, EWMA 0.97",
    "t_garch": "Student-t, GARCH(1,1) volatilities",
}
FORECAST_MODEL_LABELS = {
    "seasonal_naive": "seasonal naive",
    "calendar_ar1": "calendar regression, AR(1) errors",
}
SCENARIO_LABELS = {
    "chf_depeg_2015": "CHF floor removed, Jan 2015",
    "brexit_2016": "Brexit vote, Jun 2016",
    "covid_2020": "Dash for dollars, Mar 2020",
    "usd_surge_2022": "USD surge, Aug-Sep 2022",
    "taper_tantrum_2013": "Taper tantrum, May-Aug 2013",
    "usd_up_10": "USD +10% against all",
    "em_selloff_15": "EM selloff (BRL, MXN -15%, INR -10%)",
    "eur_down_10": "EUR -10%",
    "jpy_up_10": "JPY +10%",
}
BASIS_LABELS = {"net": "net", "net_of_hedges": "net of hedges"}
TOTAL_LABEL = "total (absolute values)"


def risk_label(label: str) -> str:
    """``"parametric_t / ewma_0.94"`` -> ``"Student-t, EWMA 0.94"``."""
    method, _, cov = label.partition(" / ")
    m = RISK_METHOD_LABELS.get(method, method)
    c = COV_LABELS.get(cov, cov)
    return f"{m}, {c}" if c else m


# Values, by the column they appear in.
VALUE_LABELS: dict[str, dict[str, str]] = {
    "policy": POLICY_LABELS,
    "versus": POLICY_LABELS,
    "method": {**RISK_METHOD_LABELS, **VAR_METHOD_LABELS},
    "model": FORECAST_MODEL_LABELS,
    "scenario": SCENARIO_LABELS,
    "basis": BASIS_LABELS,
}

# Column headers. Amounts are USD millions wherever a report section says so.
COLUMN_LABELS = {
    # exposure forecast
    "horizon": "horizon (days)",
    "pinball_pct": "pinball loss, % of exposure",
    "mape_median_pct": "median abs. error, %",
    "coverage_50": "50% interval coverage",
    "coverage_80": "80% interval coverage",
    "coverage_95": "95% interval coverage",
    "skill_vs_naive": "skill vs naive",
    "target_date": "target date",
    # hedge recommendation
    "exposure_fcy": "exposure (currency units)",
    "exposure_usd_m": "exposure (USD m)",
    "hedge_ratio": "hedge ratio",
    "notional_usd_m": "forward notional (USD m)",
    "carry_pct_annual": "carry (% / yr, + = cost)",
    "spread_bp": "spread (bp)",
    "rate_source": "rate source",
    "is_proxy": "proxy rate",
    "budget_usd_m": "ES budget (USD m)",
    "residual_es_usd_m": "residual ES (USD m)",
    "annual_cost_usd_m": "expected cost (USD m / yr, + = cost)",
    "mean_ratio": "mean hedge ratio",
    # policy backtest
    "daily_vol_annualized_usd_m": "P&L vol / yr",
    "monthly_vol_usd_m": "monthly P&L vol",
    "monthly_vol_usd": "monthly P&L vol",
    "total_pnl_usd_m": "total P&L",
    "pnl_total_usd": "total P&L",
    "carry_per_year_usd_m": "carry / yr (+ = earned)",
    "spread_per_year_usd_m": "spread / yr (- = paid)",
    "carry_usd": "carry (+ = earned)",
    "spread_usd": "spread (- = paid)",
    "max_drawdown_usd_m": "max drawdown",
    "worst_month_usd_m": "worst month",
    "worst_month_usd": "worst month",
    "months_loss_gt_budget": "months losing > budget",
    "months_loss_gt_var": "months loss > ex-ante VaR",
    "n_months": "months",
    "mean_ex_ante_es_usd_m": "mean ex-ante ES",
    "share_months_binding": "share of months budget binds",
    "total_diff_usd": "total P&L difference",
    "mean_monthly_diff_usd": "mean monthly difference",
    "t_stat": "t",
    "p_value": "p",
    "carry_spread_diff_usd": "carry + spread difference",
    "spot_diff_usd": "spot difference",
    "spot_p_value": "spot p",
    "pnl_unhedged": "exposure P&L",
    "pnl_hedge_mtm": "hedge mark-to-market",
    "pnl_carry": "carry",
    "pnl_spread": "spread",
    "pnl_total": "total P&L",
    "ex_ante_var_usd": "ex-ante VaR",
    "ex_ante_es_usd": "ex-ante ES",
    # risk tables
    "label": "method",
    "largest_move": "largest move",
    "implied_moves": "largest implied moves",
    "propagated": "others propagated",
    # VaR / ES backtest
    "optimizer_compatible": "usable by the optimizer",
    "sel_n": "days",
    "sel_exceptions": "exceptions",
    "sel_fz0": "FZ0 score, 2012-2014",
    "oos_fz0": "FZ0 score, 2015 on",
    "dm_stat_vs_selected": "DM statistic vs selected",
    "dm_p_vs_selected": "DM p vs selected",
    "oos_start": "from",
    "oos_end": "to",
    "n_obs": "days",
    "n_exceptions": "exceptions",
    "expected_exceptions": "expected",
    "n_consecutive": "back-to-back",
    "kupiec_p": "Kupiec p",
    "christoffersen_p": "Christoffersen p",
    "conditional_p": "conditional coverage p",
    "traffic_light": "traffic light",
    "z1": "Z1",
    "z1_p": "Z1 p",
    "z2": "Z2",
    "z2_p": "Z2 p",
    "fz0": "FZ0 score",
}


def readable(df: pd.DataFrame) -> pd.DataFrame:
    """A copy of ``df`` with display names for known identifier values and columns."""
    out = df.copy()
    for col, mapping in VALUE_LABELS.items():
        if col in out.columns:
            out[col] = out[col].map(lambda v, m=mapping: m.get(v, v) if isinstance(v, str) else v)
    if "label" in out.columns:
        out["label"] = out["label"].map(lambda v: risk_label(v) if isinstance(v, str) else v)
    return out.rename(columns=COLUMN_LABELS)
