"""summarize simulator recordings without assuming ideal sensor physics."""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path

import numpy as np


def load_trajectory(path):
    path = Path(path)
    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    required = ("time_s", "x_m", "y_m", "z_m", "qw", "qx", "qy", "qz")
    if len(rows) < 10 or not all(col in rows[0] for col in required):
        raise ValueError("missing or insufficient 6-dof samples")
    columns = {k: np.array([float(r[k]) for r in rows], dtype=float) for k in required}
    if not all(np.all(np.isfinite(arr)) for arr in columns.values()):
        raise ValueError("nonfinite recording values")
    t = columns["time_s"]
    if np.any(np.diff(t) <= 0) or t[0] < 0:
        raise ValueError("timestamps must increase")
    qnorm = np.sqrt(sum(columns[k]**2 for k in ("qw", "qx", "qy", "qz")))
    if np.max(np.abs(qnorm - 1)) > 0.01:
        raise ValueError("nonunit orientations")
    return columns


def summarize_case(data, case):
    t = data["time_s"] - data["time_s"][0]
    xyz = np.column_stack([data[k] for k in ("x_m", "y_m", "z_m")])
    h = np.asarray(case["size_xyz_m"], dtype=float)[2]
    in_air = xyz[:, 2] > max(0.55, h / 2 + 0.2)
    first = np.flatnonzero(in_air)
    quality = {
        "samples": len(t),
        "duration_s": float(t[-1]),
        "median_sample_interval_s": float(np.median(np.diff(t))),
        "max_sample_interval_s": float(np.max(np.diff(t))),
        "start_height_m": float(xyz[0, 2]),
        "quaternion_unit": True,
        "initial_state_captured": bool(xyz[0, 2] >= case["initial_xyz_rpy"][2] - 0.1),
        "freeflight_samples": int(len(first)),
    }
    if not quality["initial_state_captured"] or len(first) < 12 or t[-1] < 0.25:
        return {"status": "insufficient_start_or_freeflight_data", "quality": quality}
    start_t = t[first[0]]
    cutoff = min(start_t + 0.32, t[first[-1]])
    segment = first[t[first] <= cutoff]
    if len(segment) < 12 or np.ptp(t[segment]) < 0.11:
        return {"status": "insufficient_freeflight_segment", "quality": quality}
    c = np.polyfit(t[segment], xyz[segment, 2], 2)
    g_fit = -2 * float(c[0])
    probe_t = 0.2
    if probe_t > t[first[-1]]:
        return {"status": "freeflight_too_short", "quality": quality}
    xy_probe = [float(np.interp(probe_t, t, xyz[:, i])) for i in (0, 1)]
    # do not infer drag coefficients from the simplified windeffects force.
    return {
        "status": "evaluated_simulator_data",
        "quality": quality,
        "gravity_from_height_fit_m_s2": g_fit,
        "horizontal_position_at_0p2s_m": xy_probe,
        "horizontal_shift_from_initial_at_0p2s_m": float(np.linalg.norm(np.asarray(xy_probe) - xyz[0, :2])),
        "z_at_0p2s_m": float(np.interp(probe_t, t, xyz[:, 2])),
        "maximum_angular_pose_change_rad": float(2 * np.arccos(np.clip(np.abs(
            data["qw"] * data["qw"][0] + data["qx"] * data["qx"][0] +
            data["qy"] * data["qy"][0] + data["qz"] * data["qz"][0]
        ), 0, 1)).max()),
    }


def evaluate_matrix(scenario_manifest, runs, output):
    scenario_manifest = Path(scenario_manifest)
    runs = Path(runs)
    output = Path(output)
    source = json.loads(scenario_manifest.read_text(encoding="utf-8"))
    results = []
    for case in source["cases"]:
        case_id = case["id"]
        trajectory = runs / case_id / "rigid_body_6dof.csv"
        if not trajectory.is_file():
            results.append({"id": case_id, "status": "not_recorded"})
            continue
        try:
            data = load_trajectory(trajectory)
            row = summarize_case(data, case["parameters"])
        except (ValueError, OSError) as exc:
            row = {"status": "invalid_recording", "reason": str(exc)}
        results.append({"id": case_id, **row})
    reference = next((r for r in results if r["id"] == "baseline" and
                      r["status"] == "evaluated_simulator_data"), None)
    for row in results:
        if row["id"] == "baseline" or row["status"] != "evaluated_simulator_data":
            continue
        if reference is None or not row["quality"]["initial_state_captured"]:
            row["baseline_comparison"] = "reference_unavailable"
            continue
        diff = np.asarray(row["horizontal_position_at_0p2s_m"]) - np.asarray(
            reference["horizontal_position_at_0p2s_m"])
        row["horizontal_difference_from_baseline_at_0p2s_m"] = float(np.linalg.norm(diff))
        row["baseline_comparison"] = (
            "detected_difference_not_causally_attributed" if np.linalg.norm(diff) > 0.001
            else "no_difference_above_1mm_threshold"
        )
    report = {
        "study_id": source["study_id"],
        "provenance": "gazebo_simulated_odometry_only",
        "experiment_count": len(results),
        "evaluated_count": sum(r["status"] == "evaluated_simulator_data" for r in results),
        "reference_available": reference is not None,
        "comparison_policy": "same elapsed time and starting state; 1mm reporting threshold; not physical validation",
        "limitations": [
            "windeffects is a simplified wind force, not calibrated aerodynamic drag",
            "the built-in gazebo wind field is not the altitude-dependent python wind-profile model",
            "one-factor screening is not a full factorial or global sensitivity analysis",
            "noisy odometry is not ground truth",
            "simulator runtime verification is required for each generated world",
        ],
        "cases": results,
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "environment_evaluation.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    with (output / "environment_evaluation.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["id", "status", "gravity_from_height_fit_m_s2",
                                                 "horizontal_shift_from_initial_at_0p2s_m",
                                                 "horizontal_difference_from_baseline_at_0p2s_m",
                                                 "baseline_comparison"], extrasaction="ignore")
        writer.writeheader()
        for row in results:
            writer.writerow(row)
    return report
