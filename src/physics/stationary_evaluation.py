"""quality-gated stationary telemetry analysis without cross-system alignment claims."""

import hashlib
import json
from pathlib import Path

import numpy as np

from .multicopter_telemetry import (
    PX4_COLUMNS, TRUTH_COLUMNS, px4_rows_from_arrays, read_csv,
)


TRUTH_PROVENANCE = "simulator_ground_truth_not_physical_measurement"
PX4_PROVENANCE = "px4_ekf_estimate_not_ground_truth"


def load_input(path, columns, time_key, provenance, manifest_path):
    """read a telemetry file and require matching declared provenance."""
    rows = read_csv(path, columns, time_key)
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    if manifest.get("provenance") != provenance:
        raise ValueError(f"unexpected provenance in {manifest_path}")
    if manifest.get("sample_count") != len(rows):
        raise ValueError(f"manifest sample count does not match {path}")
    if provenance == TRUTH_PROVENANCE:
        q = np.array([[r[k] for k in ("qw", "qx", "qy", "qz")] for r in rows])
        if np.any(np.abs(np.sum(q * q, axis=1) - 1.0) > 0.02):
            raise ValueError("ground-truth quaternions must be normalized")
    return rows, manifest


def verify_px4_export(px4_rows, raw_ulog_fields):
    """ensure the analysis csv matches the ULog field values exactly enough."""
    derived = px4_rows_from_arrays(raw_ulog_fields)
    if len(derived) != len(px4_rows):
        raise ValueError("px4 csv does not match source ulog sample count")
    exported = np.array([[row[key] for key in PX4_COLUMNS] for row in px4_rows], dtype=float)
    source = np.array([[row[key] for key in PX4_COLUMNS] for row in derived], dtype=float)
    if not np.allclose(exported, source, atol=1e-8, rtol=1e-9):
        raise ValueError("px4 csv and source ulog contain different state values")
    return True


def read_reset_quality(ulog_path, expected_px4_rows=None):
    """load px4 estimator validity and reset history from the source ulog."""
    try:
        from pyulog import ULog
    except ImportError as exc:
        raise RuntimeError("install pyulog in the project .venv") from exc
    log = ULog(str(ulog_path))
    records = [m for m in log.data_list if m.name == "vehicle_local_position" and m.multi_id == 0]
    if len(records) != 1:
        raise ValueError("ulog must contain vehicle_local_position instance 0")
    if expected_px4_rows is not None:
        verify_px4_export(expected_px4_rows, records[0].data)
    return reset_quality_from_arrays(records[0].data)


def reset_quality_from_arrays(data):
    """validate timestamps, validity flags, and estimator reset counters."""
    keys = ("timestamp", "xy_valid", "z_valid", "xy_reset_counter", "z_reset_counter")
    if any(key not in data for key in keys):
        raise ValueError("ulog missing required validity or reset fields")
    arrays = {key: np.asarray(data[key]) for key in keys}
    n = len(arrays["timestamp"])
    if n < 2 or any(a.ndim != 1 or len(a) != n for a in arrays.values()):
        raise ValueError("ulog quality arrays must have equal nonzero lengths")
    if any(not np.all(np.isfinite(a)) for a in arrays.values()):
        raise ValueError("ulog quality arrays contain nonfinite values")
    times = arrays["timestamp"].astype(float) * 1e-6
    if times[0] < 0 or np.any(np.diff(times) <= 0):
        raise ValueError("ulog quality timestamps must increase")
    for key in ("xy_valid", "z_valid"):
        if not np.all(np.isin(arrays[key], [0, 1])):
            raise ValueError(f"invalid {key} flags")
    for key in ("xy_reset_counter", "z_reset_counter"):
        if np.any(arrays[key] < 0) or np.any(arrays[key] != np.floor(arrays[key])):
            raise ValueError(f"invalid {key} counters")
    events = {}
    for key in ("xy_reset_counter", "z_reset_counter"):
        indices = np.flatnonzero(np.diff(arrays[key]) != 0) + 1
        events[key] = [float(times[i]) for i in indices]
    return {"time_s": times, "events": events, "flags": {
        key: arrays[key].astype(int) for key in ("xy_valid", "z_valid")
    }}


def _longest_contiguous(indices):
    if not len(indices):
        return np.array([], dtype=int)
    groups = np.split(indices, np.flatnonzero(np.diff(indices) > 1) + 1)
    return max(groups, key=lambda group: (len(group), -int(group[0])))


def _block_bootstrap_ci(positions, t, count, seed, seconds):
    """estimate a descriptive interval using contiguous time blocks."""
    if count <= 0:
        return None
    dt = float(np.median(np.diff(t)))
    if dt <= 0:
        raise ValueError("invalid sampling step")
    block = max(2, int(round(seconds / dt)))
    if len(t) < 3 * block:
        return None
    rng = np.random.default_rng(seed)
    n = len(positions)
    estimates = np.empty(count)
    for i in range(count):
        starts = rng.integers(0, n - block + 1, size=int(np.ceil(n / block)))
        sampled = np.concatenate([positions[j:j + block] for j in starts], axis=0)[:n]
        centered = sampled - sampled.mean(axis=0)
        estimates[i] = np.sqrt(np.mean(np.sum(centered * centered, axis=1)))
    return {
        "lower_m": float(np.percentile(estimates, 2.5)),
        "upper_m": float(np.percentile(estimates, 97.5)),
        "block_duration_s": float(block * dt),
        "replicates": count,
        "interpretation": "approximate block-bootstrap interval; not an absolute accuracy bound",
    }


def evaluate_stationary(truth_rows, px4_rows, *, quality=None, warmup_s=0.0,
                        reset_guard_s=1.0, stationary_threshold_m=0.05,
                        min_samples=100, bootstrap_replicates=300,
                        bootstrap_block_s=1.0, seed=42):
    """describe stable estimator jitter without identifying unknown frame origins."""
    if warmup_s < 0 or reset_guard_s < 0 or stationary_threshold_m <= 0:
        raise ValueError("invalid analysis thresholds")
    if min_samples < 3 or bootstrap_replicates < 0 or bootstrap_block_s <= 0:
        raise ValueError("invalid sampling or bootstrap settings")
    tt = np.array([r["sim_time_s"] for r in truth_rows])
    tp = np.array([r["px4_time_s"] for r in px4_rows])
    xyz_truth = np.array([[r[k] for k in ("x_m", "y_m", "z_m")] for r in truth_rows])
    xyz_px4 = np.array([[r[k] for k in (
        "enu_x_east_m", "enu_y_north_m", "enu_z_up_m")]
        for r in px4_rows])
    start = max(float(tt[0]) + warmup_s, float(tp[0]))
    stop = min(float(tt[-1]), float(tp[-1]))
    if stop <= start:
        raise ValueError("no nominal numeric timestamp overlap")
    tm = (tt >= start) & (tt <= stop)
    pm = (tp >= start) & (tp <= stop)
    truth = xyz_truth[tm]
    if len(truth) < 2:
        raise ValueError("insufficient gazebo samples in nominal overlap")
    truth_center = np.mean(truth, axis=0)
    truth_radius = np.linalg.norm(truth - truth_center, axis=1)
    truth_max = float(np.max(truth_radius))
    stationary = truth_max <= stationary_threshold_m

    flags = np.array([
        r["xy_valid"] == 1 and r["z_valid"] == 1 for r in px4_rows
    ])
    reset_events = {"xy_reset_counter": [], "z_reset_counter": []}
    post_reset_start = start
    checked_quality = quality is not None
    if quality is not None:
        tq = quality["time_s"]
        if tq[0] > start + 1e-4 or tq[-1] < stop - 1e-4:
            raise ValueError("ulog quality series does not cover candidate interval")
        for key, events in quality["events"].items():
            reset_events[key] = [float(t) for t in events if start <= t <= stop]
        all_events = reset_events["xy_reset_counter"] + reset_events["z_reset_counter"]
        if all_events:
            post_reset_start = max(all_events) + reset_guard_s
        q_idx = np.searchsorted(tq, tp, side="right") - 1
        in_bounds = q_idx >= 0
        q_idx = np.clip(q_idx, 0, len(tq) - 1)
        flags = flags & in_bounds & (
            quality["flags"]["xy_valid"][q_idx] == 1
        ) & (quality["flags"]["z_valid"][q_idx] == 1)
    candidate = pm & (tp >= post_reset_start)
    available = np.flatnonzero(candidate & flags)
    chosen = _longest_contiguous(available)
    if len(chosen) < min_samples:
        raise ValueError("too few consecutive valid px4 samples in selected interval")
    selected = xyz_px4[chosen]
    times = tp[chosen]
    mean = np.mean(selected, axis=0)
    centered = selected - mean
    radial = np.linalg.norm(centered, axis=1)
    elapsed = times - times[0]
    slopes = np.polyfit(elapsed, selected, 1)[0]
    rms = float(np.sqrt(np.mean(radial * radial)))
    ci = _block_bootstrap_ci(selected, times, bootstrap_replicates, seed, bootstrap_block_s)
    warnings = ["clock correspondence not verified by a dynamic synchronization experiment",
                "position origins not calibrated; no gazebo-px4 positional error computed"]
    if not checked_quality:
        warnings.append("ulog reset-counter history unavailable; interval quality is provisional")
    if not stationary:
        warnings.append("gazebo motion exceeds stationary threshold")
    if sum(map(len, reset_events.values())):
        warnings.append("estimator reset occurred in nominal interval; pre-reset samples excluded")
    return {
        "status": "qualified_stationary_jitter" if stationary and checked_quality else "descriptive_only",
        "simulation_only": True,
        "clock_alignment": "numeric_overlap_only_not_verified",
        "coordinate_origin_alignment": "not_calibrated",
        "direct_position_rmse_computed": False,
        "candidate_interval_s": [start, stop],
        "selected_px4_interval_s": [float(times[0]), float(times[-1])],
        "counts": {
            "gazebo_in_interval": int(tm.sum()),
            "px4_in_interval": int(pm.sum()),
            "px4_valid_before_reset_gate": int(np.sum(pm & flags)),
            "px4_selected": int(len(chosen)),
        },
        "gazebo": {
            "stationary": bool(stationary),
            "mean_position_world_enu_m": truth_center.tolist(),
            "maximum_deviation_from_mean_m": truth_max,
            "threshold_m": stationary_threshold_m,
        },
        "px4": {
            "mean_position_local_enu_m": mean.tolist(),
            "std_per_axis_m": np.std(selected, axis=0).tolist(),
            "rms_3d_jitter_m": rms,
            "p95_3d_jitter_m": float(np.percentile(radial, 95)),
            "p99_3d_jitter_m": float(np.percentile(radial, 99)),
            "drift_slope_enu_m_s": slopes.tolist(),
            "median_sample_interval_s": float(np.median(np.diff(times))),
            "max_sample_interval_s": float(np.max(np.diff(times))),
            "block_bootstrap_rms_interval": ci,
        },
        "reset_history": reset_events,
        "quality_history_checked": bool(checked_quality),
        "warnings": warnings,
    }, {"truth_times": tt[tm], "truth_positions": truth,
        "px4_times": times, "px4_positions": selected, "px4_centered": centered}


def file_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for data in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(data)
    return digest.hexdigest()
