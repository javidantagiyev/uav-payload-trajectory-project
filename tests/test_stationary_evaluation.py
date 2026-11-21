"""test stationary telemetry quality, provenance, and reproducibility."""

import csv
import json
from pathlib import Path

import numpy as np
import pytest

from src.physics.multicopter_telemetry import PX4_COLUMNS, TRUTH_COLUMNS, write_csv
from src.physics.stationary_evaluation import (
    TRUTH_PROVENANCE, PX4_PROVENANCE, evaluate_stationary, load_input,
    reset_quality_from_arrays, verify_px4_export,
)


def fixture_rows(n=500, rate=50, first=20.0, jitter=0.01):
    times = first + np.arange(n) / rate
    truth = []
    px4 = []
    for i, t in enumerate(times):
        truth.append(dict(zip(TRUTH_COLUMNS, (t, 0.0, 0.0, -0.013, 1, 0, 0, 0))))
        a = np.sin(i * 0.23) * jitter
        b = np.cos(i * 0.3) * jitter
        c = np.sin(i * 0.17) * jitter
        enu = (a, b, c)
        ned = (b, a, -c)
        row = dict(zip(PX4_COLUMNS, (
            t, *ned, 0, 0, 0, *enu, 0, 0, 0, 1, 1, 1, 1,
        )))
        px4.append(row)
    return truth, px4


def quality_rows(n=500, rate=50, first=20.0):
    times = first + np.arange(n) / rate
    return {"timestamp": (times * 1e6).astype(int),
            "xy_valid": np.ones(n, dtype=int), "z_valid": np.ones(n, dtype=int),
            "xy_reset_counter": np.full(n, 5, dtype=int),
            "z_reset_counter": np.full(n, 2, dtype=int)}


def test_quality_gated_stationary_metrics():
    truth, px4 = fixture_rows()
    quality = reset_quality_from_arrays(quality_rows())
    report, arrays = evaluate_stationary(truth, px4, quality=quality, min_samples=50,
                                          bootstrap_replicates=40, seed=11)
    assert report["status"] == "qualified_stationary_jitter"
    assert report["counts"]["px4_selected"] == 500
    assert report["gazebo"]["stationary"]
    assert report["direct_position_rmse_computed"] is False
    assert 0.01 < report["px4"]["rms_3d_jitter_m"] < 0.02
    assert report["px4"]["block_bootstrap_rms_interval"] is not None
    assert arrays["px4_times"].shape == (500,)


def test_deterministic_bootstrap():
    a, b = fixture_rows()
    q = reset_quality_from_arrays(quality_rows())
    r1, _ = evaluate_stationary(a, b, quality=q, min_samples=50, bootstrap_replicates=20)
    r2, _ = evaluate_stationary(a, b, quality=q, min_samples=50, bootstrap_replicates=20)
    assert r1 == r2


def test_no_quality_is_provisional():
    truth, px4 = fixture_rows()
    report, _ = evaluate_stationary(truth, px4, min_samples=50, bootstrap_replicates=0)
    assert report["status"] == "descriptive_only"
    assert report["px4"]["block_bootstrap_rms_interval"] is None


def test_reset_restricts_interval():
    truth, px4 = fixture_rows()
    fields = quality_rows()
    fields["xy_reset_counter"][100:] = 6
    quality = reset_quality_from_arrays(fields)
    report, _ = evaluate_stationary(truth, px4, quality=quality,
                                     min_samples=50, bootstrap_replicates=0)
    assert report["counts"]["px4_selected"] < 400
    assert len(report["reset_history"]["xy_reset_counter"]) == 1


def test_invalid_samples_select_contiguous_interval():
    truth, px4 = fixture_rows()
    for row in px4[150:200]:
        row["xy_valid"] = 0
    report, _ = evaluate_stationary(truth, px4, min_samples=50, bootstrap_replicates=0)
    assert report["counts"]["px4_selected"] == 300


def test_moving_truth_is_not_qualified():
    truth, px4 = fixture_rows()
    for i, row in enumerate(truth):
        row["x_m"] = i * 0.001
    report, _ = evaluate_stationary(truth, px4, quality=reset_quality_from_arrays(quality_rows()),
                                     min_samples=50, bootstrap_replicates=0)
    assert report["status"] == "descriptive_only"
    assert not report["gazebo"]["stationary"]


def test_rejects_bad_quality_history_and_nonoverlap():
    truth, px4 = fixture_rows()
    quality = quality_rows()
    quality["timestamp"][9] = quality["timestamp"][8]
    with pytest.raises(ValueError, match="increase"):
        reset_quality_from_arrays(quality)
    px4 = [dict(row, px4_time_s=row["px4_time_s"] + 100) for row in px4]
    with pytest.raises(ValueError, match="overlap"):
        evaluate_stationary(truth, px4, bootstrap_replicates=0)


def test_rejects_unsupported_provenance_and_manifest_count(tmp_path):
    truth, _ = fixture_rows()
    path = tmp_path / "ground_truth.csv"
    manifest = tmp_path / "manifest.json"
    write_csv(truth, path, TRUTH_COLUMNS, "sim_time_s")
    manifest.write_text(json.dumps({"provenance": "measured", "sample_count": len(truth)}))
    with pytest.raises(ValueError, match="provenance"):
        load_input(path, TRUTH_COLUMNS, "sim_time_s", TRUTH_PROVENANCE, manifest)
    manifest.write_text(json.dumps({"provenance": TRUTH_PROVENANCE, "sample_count": 1}))
    with pytest.raises(ValueError, match="sample count"):
        load_input(path, TRUTH_COLUMNS, "sim_time_s", TRUTH_PROVENANCE, manifest)


def test_cli_runner_end_to_end_without_ulog(tmp_path):
    from experiments.evaluate_stationary_x500 import run
    truth, px4 = fixture_rows()
    write_csv(truth, tmp_path / "gazebo_truth.csv", TRUTH_COLUMNS, "sim_time_s")
    write_csv(px4, tmp_path / "px4_local_position.csv", PX4_COLUMNS, "px4_time_s")
    (tmp_path / "gazebo_truth_manifest.json").write_text(json.dumps({
        "provenance": TRUTH_PROVENANCE, "sample_count": len(truth), "model": "x500_0",
    }))
    (tmp_path / "px4_local_position_manifest.json").write_text(json.dumps({
        "provenance": PX4_PROVENANCE, "sample_count": len(px4),
    }))
    report = run(tmp_path, tmp_path, bootstrap_replicates=10)
    assert report["status"] == "descriptive_only"
    assert (tmp_path / "stationary_evaluation.json").exists()
    assert (tmp_path / "figures/stationary_px4_jitter.png").exists()
    assert (tmp_path / "figures/stationary_gazebo_displacement.png").exists()


def test_ulog_csv_consistency_gate():
    _, sample = fixture_rows(n=3)
    fields = {
        "timestamp": [int(r["px4_time_s"] * 1e6) for r in sample],
        "x": [r["ned_x_north_m"] for r in sample],
        "y": [r["ned_y_east_m"] for r in sample],
        "z": [r["ned_z_down_m"] for r in sample],
        "vx": [r["ned_vx_north_m_s"] for r in sample],
        "vy": [r["ned_vy_east_m_s"] for r in sample],
        "vz": [r["ned_vz_down_m_s"] for r in sample],
        "xy_valid": [1, 1, 1], "z_valid": [1, 1, 1],
        "v_xy_valid": [1, 1, 1], "v_z_valid": [1, 1, 1],
    }
    assert verify_px4_export(sample, fields)
    tampered = [dict(row) for row in sample]
    tampered[1]["enu_x_east_m"] += 0.001
    with pytest.raises(ValueError, match="different state values"):
        verify_px4_export(tampered, fields)
