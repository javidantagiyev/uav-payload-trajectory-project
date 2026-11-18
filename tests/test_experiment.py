import sys
from pathlib import Path as _Path
sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))

"""End-to-end smoke verification: configured experiment writes machine-readable files."""

import csv
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_experiment_writes_expected_artifacts(tmp_path):
    spec = importlib.util.spec_from_file_location("baseline_experiment", ROOT / "experiments/baseline.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    result = module.run(ROOT / "configs/baseline.json", tmp_path)
    assert result["scenario_id"] == "baseline_lab_v1"
    assert (tmp_path / "experiment_summary.json").is_file()
    with (tmp_path / "convergence.csv").open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 8
    assert {r["method"] for r in rows} == {"euler", "rk4"}
    loaded = json.loads((tmp_path / "experiment_summary.json").read_text())
    assert loaded["status"] == "offline_model_verification_only"
    for figure in ("model_comparison", "numerical_convergence", "mechanical_energy"):
        assert (tmp_path / "figures" / f"{figure}.png").stat().st_size > 1000
