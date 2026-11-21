"""quality-gated analysis for gazebo simulation-time studies (not physical validation)."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import numpy as np

from src.physics.environmental_evaluation import load_trajectory


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_verified_run(folder, case, requested_duration=None):
    folder = Path(folder)
    status_path = folder / "run_status.json"
    recording = folder / "rigid_body_6dof.csv"
    if not status_path.is_file() or not recording.is_file():
        raise ValueError("missing run status or trajectory")
    status = json.loads(status_path.read_text(encoding="utf-8"))
    if status.get("status") != "sim_time_window_recorded":
        raise ValueError("run did not complete its simulation-time window")
    if status.get("scenario_source_sha256") != case["sdf_sha256"]:
        raise ValueError("run has mismatched scenario hash")
    if status.get("trajectory_sha256") != sha256(recording):
        raise ValueError("trajectory hash mismatch")
    window = status.get("capture", {})
    if window.get("status") != "sim_time_window_captured":
        raise ValueError("invalid capture status")
    if requested_duration is not None and window.get("requested_sim_duration_s") != requested_duration:
        raise ValueError("inconsistent requested duration")
    data = load_trajectory(recording)
    t = data["time_s"]
    rate = float(status["requested_odom_rate_hz"])
    if not np.isclose(t[0], 0, atol=1e-9):
        raise ValueError("trajectory not relative to initial sample")
    if t[-1] + 1e-6 < float(window["requested_sim_duration_s"]):
        raise ValueError("recording shorter than requested sim time")
    if np.max(np.diff(t)) > 3 / rate + 1e-7:
        raise ValueError("sample gap exceeds 3 nominal periods")
    return data, status


def sample_at(data, seconds):
    t = data["time_s"]
    if not t[0] <= seconds <= t[-1]:
        return None
    return np.array([np.interp(seconds, t, data[k]) for k in ("x_m", "y_m", "z_m")])


def effective_z_acceleration(data, cutoff_s=0.30, min_points=12):
    """quadratic z fit; does NOT identify physical gravity in presence of other forces."""
    t = data["time_s"]
    keep = (t >= 0) & (t <= cutoff_s)
    tt = t[keep]
    if len(tt) < min_points or np.ptp(tt) < 0.09:
        return None
    zz = data["z_m"][keep]
    a, b, c = np.polyfit(tt, zz, 2)
    residual = zz - np.polyval([a, b, c], tt)
    return {"fit_cutoff_s": cutoff_s, "g_effective_m_s2": float(-2*a),
            "initial_vertical_velocity_fit_m_s": float(b),
            "fit_rmse_m": float(np.sqrt(np.mean(residual**2))),
            "points": len(tt)}


def run_statistics(data, case, probe_s=0.2):
    t = data["time_s"]
    xyz = np.column_stack([data[k] for k in ("x_m", "y_m", "z_m")])
    probe = sample_at(data, probe_s)
    span = xyz - xyz[0]
    result = {
        "recorded_duration_s": float(t[-1]),
        "sample_count": len(t),
        "median_interval_s": float(np.median(np.diff(t))),
        "maximum_interval_s": float(np.max(np.diff(t))),
        "start_xyz_m": xyz[0].tolist(),
        "end_xyz_m": xyz[-1].tolist(),
        "max_horizontal_shift_m": float(np.max(np.linalg.norm(span[:, :2], axis=1))),
        "probe_elapsed_s": probe_s,
        "probe_xyz_m": probe.tolist() if probe is not None else None,
        "probe_shift_xyz_m": (probe - xyz[0]).tolist() if probe is not None else None,
        "effective_z_acceleration_diagnostic": effective_z_acceleration(data),
        "wind_mode": "gazebo_simple_windeffects_not_quadratic_aerodynamic_drag",
        "odometry_noise_std": case["parameters"]["odometry_noise_std"],
        "physics_ground_truth_status": ("noisy_odometry_not_ground_truth" if
                                        case["parameters"]["odometry_noise_std"] else
                                        "nominal_odometry_unvalidated_as_absolute_truth"),
    }
    return result


def _mean_sd(values):
    a = np.asarray(values, dtype=float)
    return {"mean": float(np.mean(a)), "sample_std": float(np.std(a, ddof=1)) if len(a) > 1 else None,
            "min": float(np.min(a)), "max": float(np.max(a))}


def aggregate_case(runs):
    if not runs:
        raise ValueError("no verified runs")
    x = [r["statistics"]["probe_shift_xyz_m"][0] for r in runs if r["statistics"]["probe_shift_xyz_m"]]
    y = [r["statistics"]["probe_shift_xyz_m"][1] for r in runs if r["statistics"]["probe_shift_xyz_m"]]
    if len(x) != len(runs):
        return {"count": len(runs), "probe_available": False,
                "reason": "requested simulation window does not include the 0.2s probe"}
    return {"count": len(runs), "probe_available": True,
            "probe_shift_east_m": _mean_sd(x),
            "probe_shift_north_m": _mean_sd(y),
            "max_pairwise_probe_east_difference_m": float(np.ptp(x)),
            "max_pairwise_probe_north_difference_m": float(np.ptp(y)),
            "interpretation": "descriptive repeated-run variation; not confidence bounds or wind calibration"}


def summarize_study(scenario_manifest, runs_root, output):
    scenario_manifest, runs_root, output = map(Path, (scenario_manifest, runs_root, output))
    source = json.loads(scenario_manifest.read_text(encoding="utf-8"))
    cases = []
    for case in source["cases"]:
        folders = sorted((runs_root / case["id"]).glob("run_*"))
        row = {"id": case["id"], "parameters": case["parameters"], "runs": [], "invalid_runs": []}
        for folder in folders:
            if not folder.is_dir():
                continue
            try:
                data, status = load_verified_run(folder, case)
                row["runs"].append({"path": str(folder / "rigid_body_6dof.csv"),
                                    "repeat_index": status["repeat_index"],
                                    "statistics": run_statistics(data, case),
                                    "trajectory_sha256": status["trajectory_sha256"]})
            except (ValueError, OSError, KeyError, TypeError) as exc:
                row["invalid_runs"].append({"path": str(folder), "error": str(exc)})
        row["status"] = "evaluated" if row["runs"] else "not_recorded_or_invalid"
        if row["runs"]:
            row["aggregate"] = aggregate_case(row["runs"])
        cases.append(row)
    report = {
        "study_id": source["study_id"],
        "status": "offline_analysis_of_recorded_simulation_only",
        "source_scenario_manifest_sha256": sha256(scenario_manifest),
        "evaluated_cases": sum(bool(c["runs"]) for c in cases),
        "verified_runs": sum(len(c["runs"]) for c in cases),
        "invalid_runs": sum(len(c["invalid_runs"]) for c in cases),
        "analysis": "simulation-time trajectories, repeated-run reproducibility, early-time dynamics",
        "provenance": "gazebo_odometry_not_physical_validation",
        "limitations": [
            "stochastic independence and RNG control not established",
            "sample-to-sample variability does not by itself justify confidence intervals",
            "gazebo WindEffects is not a calibrated atmospheric aerodynamics model",
            "observed vertical acceleration includes non-gravity effects and fit bias",
            "kinematic effects after contact are not free-flight accelerations",
        ],
        "cases": cases,
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "simtime_analysis.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    with (output / "simtime_analysis.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["id", "status", "runs", "invalid_runs", "mean_east_at_0p2s_m",
                                                 "sd_east_at_0p2s_m", "mean_north_at_0p2s_m",
                                                 "sd_north_at_0p2s_m"])
        writer.writeheader()
        for row in cases:
            agg = row.get("aggregate", {})
            east = agg.get("probe_shift_east_m", {})
            north = agg.get("probe_shift_north_m", {})
            writer.writerow({"id": row["id"], "status": row["status"],
                             "runs": len(row["runs"]), "invalid_runs": len(row["invalid_runs"]),
                             "mean_east_at_0p2s_m": east.get("mean"),
                             "sd_east_at_0p2s_m": east.get("sample_std"),
                             "mean_north_at_0p2s_m": north.get("mean"),
                             "sd_north_at_0p2s_m": north.get("sample_std")})
    return report
