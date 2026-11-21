"""6f summary uses only validated, hash-matched simulator data."""

import csv
import json
from pathlib import Path

import numpy as np
import pytest

from src.physics.environmental_matrix import prepare_worlds
from src.physics.simtime_analysis import (effective_z_acceleration, load_verified_run,
                                          run_statistics, summarize_study, sha256)
from src.physics.simtime_figures import plot_case, plot_overview

ROOT = Path(__file__).resolve().parents[1]


def create_fixture(tmp_path, axis_acc=.2, case_id="baseline", repeats=2):
    worlds = tmp_path / "worlds"
    manifest = prepare_worlds(ROOT / "configs/environment_matrix.json",
                              ROOT / "sim/gazebo/worlds/rigid_body_lab.sdf", worlds)
    case = next(c for c in manifest["cases"] if c["id"] == case_id)
    for i in range(repeats):
        folder = tmp_path / "runs" / case_id / f"run_{i:03d}"
        folder.mkdir(parents=True)
        path = folder / "rigid_body_6dof.csv"
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["time_s", "x_m", "y_m", "z_m", "qw", "qx", "qy", "qz"])
            for t in np.linspace(0, .4, 41):
                writer.writerow([t, .5*axis_acc*t*t + i*1e-5, 0,
                                 2.1 - .5*9.81*t*t, 1, 0, 0, 0])
        status = {"status": "sim_time_window_recorded", "repeat_index": i,
                  "requested_odom_rate_hz": 100,
                  "scenario_source_sha256": case["sdf_sha256"],
                  "trajectory_sha256": sha256(path),
                  "capture": {"status": "sim_time_window_captured", "requested_sim_duration_s": .4}}
        (folder / "run_status.json").write_text(json.dumps(status))
    return worlds, case


def test_synthetic_reference_fit(tmp_path):
    worlds, case = create_fixture(tmp_path)
    data, _ = load_verified_run(tmp_path / "runs/baseline/run_000", case)
    fit = effective_z_acceleration(data)
    assert fit["g_effective_m_s2"] == pytest.approx(9.81, abs=1e-8)
    stats = run_statistics(data, case)
    assert stats["probe_shift_xyz_m"][0] == pytest.approx(.004, abs=1e-7)


def test_repeat_analysis_and_figures(tmp_path):
    worlds, _ = create_fixture(tmp_path)
    out = tmp_path / "out"
    report = summarize_study(worlds / "scenario_manifest.json", tmp_path / "runs", out)
    assert report["verified_runs"] == 2
    assert report["evaluated_cases"] == 1
    assert report["invalid_runs"] == 0
    case = next(c for c in report["cases"] if c["id"] == "baseline")
    assert case["aggregate"]["probe_shift_east_m"]["mean"] == pytest.approx(.004)
    figures = plot_case(case, out / "figures/baseline")
    figures += plot_overview(report, out / "figures")
    assert len(figures) >= 9
    assert all(p.exists() and p.stat().st_size > 0 for p in figures)
    assert (out / "simtime_analysis.csv").exists()


def test_modified_recording_is_not_accepted(tmp_path):
    worlds, case = create_fixture(tmp_path, repeats=1)
    file = tmp_path / "runs/baseline/run_000/rigid_body_6dof.csv"
    file.write_text(file.read_text() + "\n")
    with pytest.raises(ValueError, match="hash"):
        load_verified_run(file.parent, case)
    report = summarize_study(worlds / "scenario_manifest.json", tmp_path / "runs", tmp_path / "out")
    assert report["verified_runs"] == 0
    assert report["invalid_runs"] == 1


def test_fake_success_without_coverage_is_rejected(tmp_path):
    worlds, case = create_fixture(tmp_path, repeats=1)
    folder = tmp_path / "runs/baseline/run_000"
    status_file = folder / "run_status.json"
    status = json.loads(status_file.read_text())
    status["capture"]["requested_sim_duration_s"] = .6
    status_file.write_text(json.dumps(status))
    with pytest.raises(ValueError, match="shorter"):
        load_verified_run(folder, case)


def test_bad_quaternion_fails_quality_gate(tmp_path):
    worlds, case = create_fixture(tmp_path, repeats=1)
    folder = tmp_path / "runs/baseline/run_000"
    file = folder / "rigid_body_6dof.csv"
    lines = file.read_text().splitlines()
    lines[1] = lines[1].replace(",1,0,0,0", ",2,0,0,0")
    file.write_text("\n".join(lines) + "\n")
    status_file = folder / "run_status.json"
    status = json.loads(status_file.read_text())
    status["trajectory_sha256"] = sha256(file)
    status_file.write_text(json.dumps(status))
    with pytest.raises(ValueError, match="nonunit"):
        load_verified_run(folder, case)
