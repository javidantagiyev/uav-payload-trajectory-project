"""audit gazebo inert-body odometry while preserving the raw recording."""

import csv
import math
from pathlib import Path

import numpy as np

REQUIRED_COLUMNS = (
    "time_s", "x_m", "y_m", "z_m", "qw", "qx", "qy", "qz",
    "linear_vx_m_s", "linear_vy_m_s", "linear_vz_m_s",
    "angular_wx_rad_s", "angular_wy_rad_s", "angular_wz_rad_s",
)


def load_recording(path):
    with Path(path).open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames or not set(REQUIRED_COLUMNS).issubset(reader.fieldnames):
            raise ValueError("recording is missing required 6-dof columns")
        try:
            rows = [{key: float(row[key]) for key in REQUIRED_COLUMNS} for row in reader]
        except (TypeError, ValueError) as exc:
            raise ValueError("recording contains invalid numeric values") from exc
    if len(rows) < 6:
        raise ValueError("recording must contain at least six samples")
    data = {key: np.array([row[key] for row in rows], dtype=float) for key in REQUIRED_COLUMNS}
    if any(not np.all(np.isfinite(col)) for col in data.values()):
        raise ValueError("recording contains nonfinite values")
    t = data["time_s"]
    if t[0] < 0 or not np.all(np.diff(t) > 0):
        raise ValueError("recording timestamps must be nonnegative and increasing")
    q = np.column_stack([data[k] for k in ("qw", "qx", "qy", "qz")])
    if np.any(np.abs(np.sum(q*q, axis=1) - 1.0) > 0.01):
        raise ValueError("recording contains non-unit quaternions")
    return data


def body_to_world(quaternions_wxyz, body_vectors):
    """rotate body-frame vectors to world-frame vectors with unit quaternions."""
    q = np.asarray(quaternions_wxyz, dtype=float)
    v = np.asarray(body_vectors, dtype=float)
    if q.shape[-1] != 4 or v.shape[-1] != 3 or q.shape[:-1] != v.shape[:-1]:
        raise ValueError("quaternion and vector dimensions are incompatible")
    norm = np.sum(q*q, axis=-1)
    if not np.all(np.isfinite(q)) or not np.all(np.isfinite(v)) or np.any(np.abs(norm-1.0) > 0.01):
        raise ValueError("body-to-world transform requires finite unit quaternions and vectors")
    qw = q[..., :1]
    xyz = q[..., 1:]
    cross = 2.0 * np.cross(xyz, v)
    return v + qw * cross + np.cross(xyz, cross)


def analyse(data, *, free_flight_until_s=0.5, expected_g_m_s2=9.81,
            initial_disagreement_threshold_m_s=2.0, gravity_tolerance_m_s2=0.1,
            position_fit_tolerance_m=0.01, velocity_consistency_tolerance_m_s=0.1):
    """evaluate a declared free-flight window; never infer ground truth accuracy."""
    t = data["time_s"]
    p = np.column_stack([data[k] for k in ("x_m", "y_m", "z_m")])
    q = np.column_stack([data[k] for k in ("qw", "qx", "qy", "qz")])
    v_body = np.column_stack([data[k] for k in ("linear_vx_m_s", "linear_vy_m_s", "linear_vz_m_s")])
    w_body = np.column_stack([data[k] for k in ("angular_wx_rad_s", "angular_wy_rad_s", "angular_wz_rad_s")])
    if not math.isfinite(free_flight_until_s) or free_flight_until_s <= t[0]:
        raise ValueError("free-flight cutoff must be after the first recorded time")
    if not math.isfinite(expected_g_m_s2) or expected_g_m_s2 <= 0:
        raise ValueError("expected gravity must be positive and finite")
    if not all(math.isfinite(x) and x > 0 for x in (
        initial_disagreement_threshold_m_s, gravity_tolerance_m_s2,
        position_fit_tolerance_m, velocity_consistency_tolerance_m_s,
    )):
        raise ValueError("audit tolerances must be finite and positive")

    free = t <= free_flight_until_s + 1e-10
    if np.count_nonzero(free) < 6 or t[free][-1] - t[free][0] < 0.05:
        raise ValueError("free-flight window must include six samples spanning 0.05 s")
    a, b, c = np.polyfit(t[free] - t[0], p[free, 2], 2)
    z_fit = np.polyval((a, b, c), t[free] - t[0])
    g_estimate = float(-2 * a)
    fit_rmse = float(np.sqrt(np.mean((p[free, 2] - z_fit)**2)))

    v_world = body_to_world(q, v_body)
    w_world = body_to_world(q, w_body)
    backward_velocity = np.full_like(v_world, np.nan)
    backward_velocity[1:] = np.diff(p, axis=0) / np.diff(t)[:, None]
    free_comparison = free.copy()
    free_comparison[0] = False
    speed_rmse = float(np.sqrt(np.mean(np.sum(
        (v_world[free_comparison] - backward_velocity[free_comparison])**2, axis=1
    ))))
    initial_disagreement = float(np.linalg.norm(v_world[0] - backward_velocity[1]))
    first_twist_suspect = initial_disagreement > initial_disagreement_threshold_m_s

    lowest_i = int(np.argmin(p[:, 2]))
    rebound = float(np.max(p[lowest_i:, 2]) - p[lowest_i, 2])
    drift = np.linalg.norm(p[:, :2] - p[0, :2], axis=1)
    checks = {
        "free_flight_gravity": abs(g_estimate - expected_g_m_s2) <= gravity_tolerance_m_s2,
        "free_flight_position_fit": fit_rmse <= position_fit_tolerance_m,
        "free_flight_velocity_consistency": speed_rmse <= velocity_consistency_tolerance_m_s,
    }
    summary = {
        "analysis_type": "gazebo_recording_quality_audit",
        "provenance": "simulator_generated_not_physical_measurements",
        "sample_count": len(t),
        "duration_s": float(t[-1] - t[0]),
        "free_flight_window_s": [float(t[free][0]), float(t[free][-1])],
        "free_flight_sample_count": int(np.count_nonzero(free)),
        "expected_gravity_m_s2": float(expected_g_m_s2),
        "estimated_gravity_m_s2": g_estimate,
        "free_flight_height_fit_rmse_m": fit_rmse,
        "free_flight_world_velocity_rmse_m_s": speed_rmse,
        "initial_twist_disagreement_m_s": initial_disagreement,
        "initial_twist_suspect": bool(first_twist_suspect),
        "lowest_height_m": float(p[lowest_i, 2]),
        "time_of_lowest_height_s": float(t[lowest_i]),
        "max_rise_after_lowest_m": rebound,
        "max_horizontal_displacement_m": float(np.max(drift)),
        "checks": {k: bool(v) for k, v in checks.items()},
        "status": "pass" if all(checks.values()) else "review_required",
        "notes": [
            "free-flight cutoff is declared for this world, not automatically detected",
            "raw twist is interpreted in the body frame and rotated using recorded orientation",
            "backward position differences are compared with the end-of-interval twist samples",
            "a flagged first twist sample does not invalidate position observations",
            "numerical consistency with imposed gravity does not establish physical accuracy",
        ],
    }
    if first_twist_suspect:
        summary["notes"].append("first twist sample is inconsistent with recorded displacement")
    return summary, {
        "positions": p, "v_world": v_world, "w_world": w_world,
        "backward_velocity": backward_velocity, "free_mask": free,
        "fit_times": t[free], "fit_heights": z_fit,
        "first_twist_suspect": first_twist_suspect,
    }
