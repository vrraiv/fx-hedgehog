"""``fxrisk forecast``: rolling-origin evaluation, latest forecast, figures and tables."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import duckdb
import pandas as pd

from fx_treasury_risk import config, db
from fx_treasury_risk.forecast import evaluate as ev
from fx_treasury_risk.forecast import plots
from fx_treasury_risk.forecast.models import MAX_HORIZON, MODELS
from fx_treasury_risk.report.tables import df_to_markdown, write_markdown

log = logging.getLogger(__name__)

OOS_START = pd.Timestamp("2015-01-01")
WINDOW = 750


@dataclass(frozen=True)
class ForecastRun:
    """Outputs of one forecast run."""

    forecasts: pd.DataFrame  # every origin x model x horizon, with actuals
    evaluation: pd.DataFrame  # per ccy x model x horizon
    latest: pd.DataFrame  # forecasts from the last date (no actuals yet)


def load_exposure_series(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Group net exposure in currency units, wide: index = FX date, columns = ccy."""
    df = con.execute(
        "SELECT obs_date, ccy, net_fcy FROM exposure_group_fx ORDER BY obs_date, ccy"
    ).df()
    wide = df.pivot(index="obs_date", columns="ccy", values="net_fcy")
    wide.index = pd.DatetimeIndex(wide.index)
    wide.columns.name = None
    return wide[[c for c in config.EXPOSURE_CCYS if c in wide.columns]]


def run_forecast(
    paths: config.Paths,
    oos_start: pd.Timestamp = OOS_START,
    models: tuple[str, ...] = tuple(MODELS),
    horizon: int = MAX_HORIZON,
) -> ForecastRun:
    """Evaluate the models on monthly origins since ``oos_start`` and store everything."""
    con = db.connect(paths)
    try:
        y = load_exposure_series(con)
        calendar = pd.DatetimeIndex(y.index)
        origins = ev.monthly_origins(calendar, oos_start, horizon)
        log.info(
            "%d monthly origins from %s to %s", len(origins), origins[0].date(), origins[-1].date()
        )
        frames = []
        for ccy in y.columns:
            frames.append(
                ev.rolling_origin_forecasts(
                    y[ccy].rename(ccy), calendar, origins, models, horizon, WINDOW
                )
            )
            log.info("forecasts done for %s", ccy)
        forecasts = pd.concat(frames, ignore_index=True)
        evaluation = ev.evaluate(forecasts)
        latest_frames = []
        for ccy in y.columns:
            for name in models:
                f = MODELS[name](y[ccy].rename(ccy), calendar, horizon, WINDOW).to_frame()
                f["ccy"] = ccy
                latest_frames.append(f)
        latest = pd.concat(latest_frames, ignore_index=True)

        for name, frame in (
            ("forecast_results", forecasts),
            ("forecast_eval", evaluation),
            ("forecast_latest", latest),
        ):
            con.register("tmp_df", frame)
            con.execute(f"CREATE OR REPLACE TABLE {name} AS SELECT * FROM tmp_df")
            con.unregister("tmp_df")

        _write_outputs(paths, y, forecasts, evaluation, latest)
    finally:
        con.close()
    return ForecastRun(forecasts, evaluation, latest)


def _write_outputs(
    paths: config.Paths,
    y: pd.DataFrame,
    forecasts: pd.DataFrame,
    evaluation: pd.DataFrame,
    latest: pd.DataFrame,
) -> None:
    figs = paths.figures_dir
    plots.calibration_plot(evaluation, figs / "forecast_calibration.png")
    plots.pinball_plot(evaluation, figs / "forecast_pinball.png")
    example_ccy = "EUR" if "EUR" in y.columns else str(y.columns[0])
    last_origin = forecasts["origin"].max()
    ex = forecasts[
        (forecasts.ccy == example_ccy)
        & (forecasts.model == "calendar_ar1")
        & (forecasts.origin == last_origin)
    ]
    plots.fan_chart(
        y[example_ccy][y.index <= last_origin],
        ex,
        figs / "forecast_example.png",
        f"{example_ccy} net exposure: calendar_ar1 forecast from "
        f"{pd.Timestamp(last_origin).date()} with realised path",
    )
    head = ev.headline(evaluation)
    head[["pinball_pct", "mape_median_pct", "skill_vs_naive"]] = head[
        ["pinball_pct", "mape_median_pct", "skill_vs_naive"]
    ].round(3)
    head[["coverage_50", "coverage_80", "coverage_95"]] = head[
        ["coverage_50", "coverage_80", "coverage_95"]
    ].round(3)
    per_ccy = evaluation[evaluation["horizon"] == 21][
        [
            "ccy",
            "model",
            "pinball_pct",
            "mape_median_pct",
            "coverage_50",
            "coverage_80",
            "coverage_95",
            "skill_vs_naive",
        ]
    ].round(3)
    lat = latest[(latest.model == "calendar_ar1") & (latest.horizon == 21)][
        ["ccy", "target_date", "q025", "q500", "q975"]
    ]
    lat = lat.rename(columns={"q025": "2.5%", "q500": "median", "q975": "97.5%"})
    n_origins = forecasts["origin"].nunique()
    first_origin = pd.Timestamp(forecasts["origin"].min()).date()
    last_origin_d = pd.Timestamp(forecasts["origin"].max()).date()
    write_markdown(
        paths.reports_dir / "forecast_eval.md",
        "Exposure forecast evaluation",
        [
            (
                "Setup",
                f"{n_origins} monthly origins from {first_origin} to {last_origin_d}, horizons "
                f"1-{MAX_HORIZON} trading days, training window {WINDOW} days. Pinball loss is "
                "averaged over the 2.5/10/25/50/75/90/97.5 quantiles and scaled by the mean "
                "actual. Coverage is the share of actuals inside the central 50/80/95% "
                "intervals. Skill is 1 - pinball / pinball of the seasonal naive.",
            ),
            ("By horizon, averaged over currencies", df_to_markdown(head)),
            ("At 21 days, by currency", df_to_markdown(per_ccy)),
            (
                "Latest 21-day-ahead forecast of net exposure (currency units), calendar_ar1",
                df_to_markdown(lat),
            ),
            (
                "Figures",
                "![calibration](figures/forecast_calibration.png)\n\n![pinball](figures/forecast_pinball.png)\n\n![example](figures/forecast_example.png)",
            ),
        ],
    )
