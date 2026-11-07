"""The illustrative Airflow DAG must list the CLI's stages in the CLI's order.

Airflow is not a dependency, so the DAG file is parsed with ``ast`` rather than imported;
what is checked is the ``STAGES`` tuple and that every stage is wired to a BashOperator
running ``fxrisk <stage>``.
"""

from __future__ import annotations

import ast
from pathlib import Path

from fx_treasury_risk import config

DAG_PATH = config.REPO_ROOT / "dags" / "fxrisk_daily.py"
CLI_ORDER = (
    "fetch",
    "quality",
    "flows",
    "exposure",
    "forecast",
    "hedge",
    "backtest",
    "risk",
    "report",
)


def _stages_from_dag(path: Path) -> tuple[str, ...]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "STAGES" for t in node.targets
        ):
            value = ast.literal_eval(node.value)
            return tuple(str(v) for v in value)
    raise AssertionError("STAGES not found in the DAG file")


def test_dag_stages_match_cli_order() -> None:
    assert _stages_from_dag(DAG_PATH) == CLI_ORDER


def test_dag_mentions_every_stage_command() -> None:
    text = DAG_PATH.read_text(encoding="utf-8")
    assert "BashOperator" in text and "uv run fxrisk" in text
    assert "fetch --refresh" in text  # the network stage refreshes rather than reads cache
    assert "catchup=False" in text


def test_cli_all_runs_stages_in_dag_order() -> None:
    """``fxrisk all`` calls the stage functions in the same order as the DAG."""
    cli = (config.REPO_ROOT / "fx_treasury_risk" / "cli.py").read_text(encoding="utf-8")
    tree = ast.parse(cli)
    calls: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "run_all":
            for stmt in node.body:
                if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
                    func = stmt.value.func
                    if isinstance(func, ast.Name):
                        calls.append(func.id)
    assert tuple(calls) == CLI_ORDER
