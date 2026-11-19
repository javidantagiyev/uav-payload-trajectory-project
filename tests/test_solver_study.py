"""End-to-end checks for balanced model-by-method comparisons."""

import csv
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def test_solver_experiment_is_balanced_and_writes_reproducible_data(tmp_path):
    module_path = ROOT / "experiments" / "solver_study.py"
    spec = importlib.util.spec_from_file_location("solver_study_experiment", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    config_path = ROOT / "configs" / "baseline.json"
    summary = module.run(config_path, tmp_path)
    assert summary["physical_validation"] is False
    assert summary["status"] == "offline_numerical_verification_only"
    assert len(summary["convergence_estimates"]) == 4

    with (tmp_path / "solver_comparison.csv").open(newline="", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))
    assert len(rows) == 16
    assert {(r["physical_model"], r["method"]) for r in rows} == {
        ("gravity_only", "euler"), ("gravity_only", "rk4"),
        ("quadratic_drag", "euler"), ("quadratic_drag", "rk4"),
    }
    assert {r["requested_max_step_s"] for r in rows} == {"0.1", "0.05", "0.025", "0.0125"}
    assert all(int(r["rhs_evaluations"]) == int(r["steps"]) *
               (1 if r["method"] == "euler" else 4) for r in rows)

    indexed = {(r["physical_model"], r["method"], r["requested_max_step_s"]): r for r in rows}
    for model in ("gravity_only", "quadratic_drag"):
        euler = float(indexed[(model, "euler", "0.1")]["terminal_position_difference_m"])
        rk4 = float(indexed[(model, "rk4", "0.1")]["terminal_position_difference_m"])
        assert rk4 < euler

    with (tmp_path / "observed_orders.csv").open(newline="", encoding="utf-8") as file:
        orders = list(csv.DictReader(file))
    assert len(orders) == 4
    order_index = {(r["physical_model"], r["method"]): r for r in orders}
    assert float(order_index[("gravity_only", "euler")]["observed_terminal_position_order"]) == pytest.approx(1, abs=0.03)
    assert order_index[("gravity_only", "rk4")]["observed_terminal_position_order"] == ""
    assert float(order_index[("quadratic_drag", "rk4")]["observed_terminal_position_order"]) == pytest.approx(4, abs=0.15)

    artifact = json.loads((tmp_path / "study_summary.json").read_text(encoding="utf-8"))
    assert artifact["config_sha256"]
    assert len(artifact["config_sha256"]) == 64
    assert artifact["physical_validation"] is False
    for figure in (
        "gravity_only_trajectories", "quadratic_drag_trajectories",
        "gravity_only_convergence", "quadratic_drag_convergence",
        "accuracy_vs_runtime", "model_assumption_difference",
    ):
        assert (tmp_path / "figures" / (figure + ".png")).stat().st_size > 3000
