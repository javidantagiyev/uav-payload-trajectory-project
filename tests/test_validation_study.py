"""end-to-end checks for the independent evaluation interfaces."""

import csv
import json
from pathlib import Path

from experiments.evaluate_observations import run as evaluate
from experiments.robustness_study import run as robustness

ROOT = Path(__file__).resolve().parents[1]


def test_observation_pipeline_writes_artifacts(tmp_path):
    summary = evaluate(
        ROOT / "configs/baseline.json",
        ROOT / "data/examples/synthetic_observations.csv",
        ROOT / "data/examples/synthetic_observations.json",
        tmp_path,
    )
    assert summary["declared_provenance"] == "synthetic"
    assert not summary["provenance_independently_verified"]
    assert summary["metrics"]["position_rmse_m"] > 0
    assert len(list(csv.DictReader((tmp_path / "observation_residuals.csv").open()))) == 11
    assert (tmp_path / "figures/observation_comparison.png").stat().st_size > 1000
    assert (tmp_path / "figures/observation_residuals.png").stat().st_size > 1000


def test_robustness_pipeline_writes_artifacts(tmp_path):
    obj = json.loads((ROOT / "configs/robustness_study.json").read_text())
    obj["sample_count"] = 16
    obj["variants"] = obj["variants"][:2]
    config = tmp_path / "config.json"
    config.write_text(json.dumps(obj))
    result = robustness(
        ROOT / "configs/baseline.json",
        ROOT / "configs/uncertainty_study.json",
        config,
        tmp_path / "outputs",
    )
    output = tmp_path / "outputs"
    assert result["physical_validation"] is False
    assert len(result["scenario_results"]) == 2
    assert len(result["distribution_results"]) == 3
    assert len(list(csv.DictReader((output / "uncertainty_draws.csv").open()))) == 48
    for name in ("scenario_differences.png", "distribution_sensitivity.png", "distribution_ecdf.png"):
        assert (output / "figures" / name).stat().st_size > 1000
