"""Airflow DAG mirroring the ``fxrisk`` pipeline, one task per CLI stage.

Illustrative: this file shows how the stages would be scheduled in production. It is not
executed in CI (ADR-0014, backlog B7); the CLI stages it wraps are what the test suite and
CI exercise directly. The DAG is kept deliberately thin so that there is exactly one
implementation of each stage, in ``fx_treasury_risk``, and the scheduler only sequences
them. The task order and the stage names are asserted against the CLI in
``tests/test_dag.py`` by parsing this file, so the two cannot drift apart silently.

Operational choices, in the order a treasury would ask about them:

* **Schedule:** 06:30 America/New_York on weekdays. The FRED H.10 noon fixings for day
  ``t`` are published on ``t+1``, so a morning run reports on yesterday's close with every
  source available; BoC Valet and the ECB publish earlier in the day and are already in.
* **Quality gate:** ``quality`` exits 1 on a FAIL and the downstream tasks do not run;
  ``reports/alerts.md`` says why. A WARN (stale series, outlier returns) lets the run
  continue and is surfaced in the report's Data and quality section.
* **Retries:** only the network stage retries (three times, five minutes apart); the
  compute stages are deterministic and a retry would not help.
* **No catch-up:** a missed day is not back-filled because every stage is a full rebuild
  from the cache; the next run produces the same state.
* **Secrets:** ``FRED_API_KEY`` is read from the environment by the loader; in Airflow it
  would come from a Connection or a secrets backend, never from this file.
"""

from __future__ import annotations

import itertools
from datetime import datetime, timedelta

import pendulum
from airflow import DAG
from airflow.operators.bash import BashOperator

# Must match fx_treasury_risk.cli (``fxrisk all``); tests/test_dag.py checks this order.
STAGES = (
    "fetch",
    "quality",
    "flows",
    "exposure",
    "forecast",
    "backtest",
    "hedge",
    "risk",
    "report",
)

REPO = "{{ var.value.get('fxrisk_repo', '/opt/fx-hedgehog') }}"

default_args = {
    "owner": "treasury-risk",
    "depends_on_past": False,
    "email_on_failure": False,
    "retries": 0,
}

with DAG(
    dag_id="fxrisk_daily",
    description="FX treasury risk: data -> exposure -> forecast -> backtest -> hedge -> report",
    schedule="30 6 * * 1-5",
    start_date=datetime(2026, 1, 1, tzinfo=pendulum.timezone("America/New_York")),
    catchup=False,
    max_active_runs=1,
    default_args=default_args,
    tags=["treasury", "fx"],
) as dag:
    tasks = {}
    for stage in STAGES:
        extra = {}
        if stage == "fetch":
            # the only stage that touches the network: refresh and retry
            extra = {"retries": 3, "retry_delay": timedelta(minutes=5)}
            command = f"cd {REPO} && uv run fxrisk fetch --refresh"
        elif stage == "risk":
            command = f"cd {REPO} && uv run fxrisk risk --mc-paths 20000"
        else:
            command = f"cd {REPO} && uv run fxrisk {stage}"
        tasks[stage] = BashOperator(
            task_id=stage,
            bash_command=command,
            env={"UV_LINK_MODE": "copy"},
            append_env=True,
            **extra,
        )

    # strictly linear: each stage reads only what earlier stages wrote
    for upstream, downstream in itertools.pairwise(STAGES):
        tasks[upstream] >> tasks[downstream]
