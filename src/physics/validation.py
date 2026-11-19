"""observation records and fixed-time trajectory evaluation."""

import csv
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np


OBSERVATION_COLUMNS = ("time_s", "x_m", "y_m", "z_m")
VELOCITY_COLUMNS = ("vx_m_s", "vy_m_s", "vz_m_s")
METADATA_FIELDS = {
    "dataset_id", "provenance", "source", "reference_frame",
    "units", "time_origin", "description",
}


@dataclass(frozen=True)
class Observations:
    times: np.ndarray
    positions: np.ndarray
    velocities: np.ndarray | None
    metadata: dict


def load_observations(csv_path, metadata_path):
    """load strictly specified enu observations and declared provenance."""
    try:
        metadata = json.loads(Path(metadata_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot load observation metadata: {exc}") from exc
    if not isinstance(metadata, dict) or set(metadata) != METADATA_FIELDS:
        raise ValueError("observation metadata fields are missing or unexpected")
    if metadata["provenance"] not in {"synthetic", "measured"}:
        raise ValueError("provenance must be synthetic or measured")
    if metadata["reference_frame"] != "ENU" or metadata["units"] != "SI":
        raise ValueError("only enu coordinates with si units are supported")
    if metadata["time_origin"] != "elapsed_since_initial_state":
        raise ValueError("time origin must be elapsed_since_initial_state")
    for key in ("dataset_id", "source", "description"):
        if not isinstance(metadata[key], str) or not metadata[key].strip():
            raise ValueError(f"{key} must be nonempty text")

    try:
        with Path(csv_path).open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            fields = reader.fieldnames
            if fields is None:
                raise ValueError("observation csv has no header")
            expected = set(OBSERVATION_COLUMNS)
            if frozenset(fields) not in {frozenset(expected), frozenset(expected | set(VELOCITY_COLUMNS))}:
                raise ValueError("observation csv needs time and position columns, optionally all velocity columns")
            if len(fields) != len(set(fields)):
                raise ValueError("observation csv contains repeated columns")
            rows = []
            for row in reader:
                if len(rows) >= 20000:
                    raise ValueError("observation csv exceeds 20000 rows")
                if None in row or any(value is None or not value.strip() for value in row.values()):
                    raise ValueError("observation csv contains empty or extra values")
                try:
                    values = [float(row[field]) for field in fields]
                except (TypeError, ValueError) as exc:
                    raise ValueError("observation csv contains nonnumeric values") from exc
                if not np.all(np.isfinite(values)):
                    raise ValueError("observation csv contains nonfinite values")
                rows.append({field: float(row[field]) for field in fields})
    except OSError as exc:
        raise ValueError(f"cannot load observation csv: {exc}") from exc

    if len(rows) < 2:
        raise ValueError("observation csv needs at least two rows")
    times = np.array([row["time_s"] for row in rows])
    if times[0] < 0 or not np.all(np.diff(times) > 0):
        raise ValueError("observation times must be nonnegative and strictly increasing")
    positions = np.array([[r[x] for x in OBSERVATION_COLUMNS[1:]] for r in rows])
    velocities = None
    if set(VELOCITY_COLUMNS).issubset(fields):
        velocities = np.array([[r[x] for x in VELOCITY_COLUMNS] for r in rows])
    return Observations(times, positions, velocities, metadata)


def compare_trajectory(trajectory, observations):
    """compare states at observation times without extrapolation."""
    times = np.asarray(trajectory.times, dtype=float)
    states = np.asarray(trajectory.states, dtype=float)
    if times.ndim != 1 or states.shape != (len(times), 6) or len(times) < 2:
        raise ValueError("trajectory must contain time and six-component states")
    if not np.all(np.isfinite(times)) or not np.all(np.isfinite(states)) or not np.all(np.diff(times) > 0):
        raise ValueError("trajectory must be finite and time ordered")
    if observations.times[0] < times[0] - 1e-10 or observations.times[-1] > times[-1] + 1e-10:
        raise ValueError("observation times are outside simulated interval")
    sampled = np.column_stack([np.interp(observations.times, times, states[:, j]) for j in range(6)])
    difference = sampled[:, :3] - observations.positions
    norms = np.linalg.norm(difference, axis=1)
    metrics = {
        "count": len(norms),
        "position_rmse_m": float(np.sqrt(np.mean(norms ** 2))),
        "position_mean_absolute_error_m": float(np.mean(norms)),
        "position_max_error_m": float(np.max(norms)),
        "axis_rmse_m": {
            name: float(np.sqrt(np.mean(difference[:, i] ** 2)))
            for i, name in enumerate(("x", "y", "z"))
        },
        "axis_bias_m": {
            name: float(np.mean(difference[:, i]))
            for i, name in enumerate(("x", "y", "z"))
        },
    }
    if observations.velocities is not None:
        velocity_diff = sampled[:, 3:] - observations.velocities
        metrics["velocity_rmse_m_s"] = float(np.sqrt(np.mean(np.sum(velocity_diff ** 2, axis=1))))

    rows = []
    for i, t in enumerate(observations.times):
        row = {"time_s": float(t)}
        for j, axis in enumerate(("x", "y", "z")):
            row[f"observed_{axis}_m"] = float(observations.positions[i, j])
            row[f"predicted_{axis}_m"] = float(sampled[i, j])
            row[f"residual_{axis}_m"] = float(difference[i, j])
        row["position_error_m"] = float(norms[i])
        rows.append(row)
    return metrics, rows
