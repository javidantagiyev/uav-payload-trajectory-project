"""evaluate simulator-recorded trajectories without inventing data."""

import csv
import json
from pathlib import Path

import numpy as np
import pytest

from src.physics.environmental_evaluation import (evaluate_matrix, load_trajectory,
                                                   summarize_case)
from src.physics.environmental_matrix import load_cases, prepare_worlds

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/environment_matrix.json"
TEMPLATE = ROOT / "sim/gazebo/worlds/rigid_body_lab.sdf"


def make_csv(path, ax=0.0, gap=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["time_s", "x_m", "y_m", "z_m", "qw", "qx", "qy", "qz"])
        for t in np.linspace(0, 0.35, 36):
            t = float(t)
            if gap and t > 0.1:
                t -= 0.2
            writer.writerow([t, .5 * ax * t*t, 0, 2.1 - .5 * 9.81 * t*t, 1, 0, 0, 0])


def test_synthetic_fall_is_recognized_without_claiming_gazebo(tmp_path):
    f = tmp_path / "fall.csv"
    make_csv(f)
    data = load_trajectory(f)
    result = summarize_case(data, load_cases(CONFIG)[0][1])
    assert result["status"] == "evaluated_simulator_data"
    assert result["gravity_from_height_fit_m_s2"] == pytest.approx(9.81, abs=1e-7)
    assert result["horizontal_shift_from_initial_at_0p2s_m"] == pytest.approx(0)


def test_nonmonotonic_time_rejected(tmp_path):
    f = tmp_path / "bad.csv"
    make_csv(f, gap=True)
    with pytest.raises(ValueError, match="timestamps"):
        load_trajectory(f)


def test_missing_runs_reported_as_missing_not_success(tmp_path):
    worlds = tmp_path / "worlds"
    prepare_worlds(CONFIG, TEMPLATE, worlds)
    report = evaluate_matrix(worlds / "scenario_manifest.json", tmp_path / "runs", tmp_path / "out")
    assert report["evaluated_count"] == 0
    assert not report["reference_available"]
    assert all(r["status"] == "not_recorded" for r in report["cases"])


def test_detected_difference_not_attributed_to_physics(tmp_path):
    worlds = tmp_path / "worlds"
    prepare_worlds(CONFIG, TEMPLATE, worlds)
    make_csv(tmp_path / "runs/baseline/rigid_body_6dof.csv")
    make_csv(tmp_path / "runs/wind_east_4/rigid_body_6dof.csv", ax=1.0)
    report = evaluate_matrix(worlds / "scenario_manifest.json", tmp_path / "runs", tmp_path / "out")
    assert report["evaluated_count"] == 2
    r = next(r for r in report["cases"] if r["id"] == "wind_east_4")
    assert r["baseline_comparison"] == "detected_difference_not_causally_attributed"
    assert r["horizontal_difference_from_baseline_at_0p2s_m"] == pytest.approx(0.02)
    assert json.loads((tmp_path / "out/environment_evaluation.json").read_text())["reference_available"]


def test_outside_window_is_flagged(tmp_path):
    f = tmp_path / "late.csv"
    make_csv(f)
    rows = list(csv.DictReader(f.open()))
    for row in rows:
        row["z_m"] = "0.1"
    with f.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    result = summarize_case(load_trajectory(f), load_cases(CONFIG)[0][1])
    assert result["status"] == "insufficient_start_or_freeflight_data"
