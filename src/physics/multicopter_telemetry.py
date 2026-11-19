"""simulated multirotor telemetry conversion and dataset validation."""

import csv
import json
import math
from pathlib import Path


TRUTH_COLUMNS = ("sim_time_s", "x_m", "y_m", "z_m", "qw", "qx", "qy", "qz")
PX4_COLUMNS = (
    "px4_time_s", "ned_x_north_m", "ned_y_east_m", "ned_z_down_m",
    "ned_vx_north_m_s", "ned_vy_east_m_s", "ned_vz_down_m_s",
    "enu_x_east_m", "enu_y_north_m", "enu_z_up_m",
    "enu_vx_east_m_s", "enu_vy_north_m_s", "enu_vz_up_m_s",
    "xy_valid", "z_valid", "v_xy_valid", "v_z_valid",
)


def ned_to_enu(x, y, z):
    """convert north-east-down vectors into east-north-up vectors."""
    values = (float(x), float(y), float(z))
    if not all(math.isfinite(v) for v in values):
        raise ValueError("ned vector must be finite")
    return (values[1], values[0], -values[2])


def gazebo_pose_sample(msg, model_name, clock_time_s=None):
    """extract one world-frame model pose from a gazebo pose_v message."""
    target = next((pose for pose in msg.pose if pose.name == model_name), None)
    if target is None:
        return None
    # some gazebo scene broadcasters provide no pose_v header timestamp
    stamp = target.header.stamp
    if stamp.sec or stamp.nsec:
        t = float(stamp.sec) + float(stamp.nsec) * 1e-9
        source = "model_pose_header"
    elif msg.header.stamp.sec or msg.header.stamp.nsec:
        stamp = msg.header.stamp
        t = float(stamp.sec) + float(stamp.nsec) * 1e-9
        source = "pose_v_header"
    elif clock_time_s is not None:
        t = float(clock_time_s)
        source = "last_received_sim_clock"
    else:
        return None
    p, q = target.position, target.orientation
    row = dict(zip(TRUTH_COLUMNS, (
        t, float(p.x), float(p.y), float(p.z),
        float(q.w), float(q.x), float(q.y), float(q.z),
    )))
    validate_rows([row], TRUTH_COLUMNS, "sim_time_s", min_count=1)
    norm = sum(row[k] ** 2 for k in ("qw", "qx", "qy", "qz"))
    if abs(norm - 1.0) > 0.02:
        raise ValueError("gazebo pose quaternion is not normalized")
    return row, source


def px4_rows_from_arrays(fields):
    """normalize ulog vehicle_local_position arrays without changing their clock."""
    required = ("timestamp", "x", "y", "z", "vx", "vy", "vz")
    absent = [k for k in required if k not in fields]
    if absent:
        raise ValueError(f"vehicle_local_position missing fields: {absent}")
    n = len(fields["timestamp"])
    if n < 2 or any(len(fields[k]) != n for k in required):
        raise ValueError("ulog position arrays have inconsistent lengths")
    for flag in ("xy_valid", "z_valid", "v_xy_valid", "v_z_valid"):
        if flag in fields and len(fields[flag]) != n:
            raise ValueError(f"ulog {flag} length differs from timestamps")
    rows = []
    for i in range(n):
        ned = tuple(float(fields[k][i]) for k in ("x", "y", "z"))
        velocity = tuple(float(fields[k][i]) for k in ("vx", "vy", "vz"))
        if not all(math.isfinite(k) for k in (*ned, *velocity)):
            continue
        enu = ned_to_enu(*ned)
        enu_velocity = ned_to_enu(*velocity)
        row = dict(zip(PX4_COLUMNS, (
            float(fields["timestamp"][i]) / 1e6,
            *ned, *velocity, *enu, *enu_velocity,
            *(int(bool(fields[flag][i])) if flag in fields else -1 for flag in
              ("xy_valid", "z_valid", "v_xy_valid", "v_z_valid")),
        )))
        rows.append(row)
    validate_rows(rows, PX4_COLUMNS, "px4_time_s", min_count=2)
    return rows


def validate_rows(rows, columns, time_key, min_count=2):
    if len(rows) < min_count:
        raise ValueError("too few valid samples")
    previous = None
    for row in rows:
        if set(row) != set(columns):
            raise ValueError("unexpected telemetry columns")
        values = [float(row[k]) for k in columns]
        if not all(math.isfinite(v) for v in values):
            raise ValueError("nonfinite telemetry entry")
        t = float(row[time_key])
        if t < 0 or (previous is not None and t <= previous):
            raise ValueError("telemetry timestamps must strictly increase")
        previous = t
    return True


def write_csv(rows, path, columns, time_key):
    validate_rows(rows, columns, time_key)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    return path


def read_csv(path, columns, time_key):
    with Path(path).open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != list(columns):
            raise ValueError("unexpected telemetry csv header")
        rows = []
        for raw in reader:
            if None in raw or any(value is None or not value.strip() for value in raw.values()):
                raise ValueError("incomplete telemetry csv row")
            rows.append({k: float(raw[k]) for k in columns})
    validate_rows(rows, columns, time_key)
    return rows


def write_manifest(path, **metadata):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
