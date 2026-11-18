"""End-to-end reproducibility checks for the offline sensitivity study."""

import csv
import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load_experiment():
    path = ROOT / "experiments" / "uncertainty_study.py"
    spec = importlib.util.spec_from_file_location("uncertainty_experiment", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_study_produces_all_artifacts_and_reproducible_statistics(tmp_path):
    study = _load_experiment()
    plan = json.loads((ROOT / "configs" / "uncertainty_study.json").read_text())
    plan["sample_count"] = 32
    plan["diagnostic_sample_count"] = 4
    plan_path = tmp_path / "small_plan.json"
    plan_path.write_text(json.dumps(plan), encoding="utf-8")
    config = ROOT / "configs" / "baseline.json"
    output = tmp_path / "run_one"
    summary = study.run(config, plan_path, output)
    assert summary["physical_validation"] is False
    assert summary["monte_carlo_sample_count"] == 32
    assert summary["input_scenario_sha256"]
    assert summary["uncertainty_config_sha256"]
    assert len(summary["one_at_a_time_ranked"]) == 8
    assert summary["bootstrap_p95_estimator_interval_95pct_m"][0] <= summary["bootstrap_p95_estimator_interval_95pct_m"][1]

    for name, count in (("one_at_a_time", 8), ("monte_carlo_samples", 32),
                        ("resolution_diagnostic", 4)):
        with (output / f"{name}.csv").open(newline="", encoding="utf-8") as file:
            rows = list(csv.DictReader(file))
        assert len(rows) == count
    stability = list(csv.DictReader((output / "sampling_stability.csv").open(newline="", encoding="utf-8")))
    assert [int(row["sample_count"]) for row in stability] == [16, 32]

    with (output / "monte_carlo_samples.csv").open(newline="", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))
    values = np.array([float(row["terminal_3d_deviation_m"]) for row in rows])
    assert np.quantile(values, .95) == pytest.approx(summary["terminal_3d_deviation_statistics_m"]["p95"])

    for name in ("one_at_a_time_effects", "terminal_deviation_distribution",
                 "terminal_horizontal_scatter", "sampling_stability", "numerical_resolution_check"):
        assert (output / "figures" / f"{name}.png").stat().st_size > 4000
    recorded = json.loads((output / "uncertainty_summary.json").read_text())
    assert recorded == summary

    # No hidden random-state dependence: identical configuration and seed reproduce results.
    second = study.run(config, plan_path, tmp_path / "run_two")
    assert second == summary
    assert (tmp_path / "run_two" / "monte_carlo_samples.csv").read_bytes() == (output / "monte_carlo_samples.csv").read_bytes()
