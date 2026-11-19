"""validate and export simulator kinematic samples without simulator dependencies."""

import csv
import json
import math
from dataclasses import dataclass
from pathlib import Path


FULL_COLUMNS = (
    "time_s", "x_m", "y_m", "z_m", "qw", "qx", "qy", "qz",
    "linear_vx_m_s", "linear_vy_m_s", "linear_vz_m_s",
    "angular_wx_rad_s", "angular_wy_rad_s", "angular_wz_rad_s",
)
POSITION_COLUMNS = ("time_s", "x_m", "y_m", "z_m")


@dataclass(frozen=True)
class RigidBodySample:
    timestamp_s: float
    position: tuple[float, float, float]
    quaternion_wxyz: tuple[float, float, float, float]
    linear_velocity: tuple[float, float, float]
    angular_velocity: tuple[float, float, float]

    def validate(self):
        values = (self.timestamp_s, *self.position, *self.quaternion_wxyz,
                  *self.linear_velocity, *self.angular_velocity)
        if not all(math.isfinite(x) for x in values):
            raise ValueError("kinematic sample contains nonfinite values")
        if self.timestamp_s < 0:
            raise ValueError("timestamp must be nonnegative")
        n2 = sum(q * q for q in self.quaternion_wxyz)
        if abs(n2 - 1.0) > 0.01:
            raise ValueError("quaternion is not unit length")


def validate_samples(samples):
    if len(samples) < 2:
        raise ValueError("at least two samples required")
    if len(samples) > 20000:
        raise ValueError("too many samples for the current observation interface")
    previous = None
    for sample in samples:
        sample.validate()
        if previous is not None and sample.timestamp_s <= previous:
            raise ValueError("sample times must be strictly increasing")
        previous = sample.timestamp_s


def export_samples(samples, output, dataset_id="gazebo_inert_body_v1"):
    """write complete 6-dof states and package-5 compatible position observations."""
    samples = list(samples)
    validate_samples(samples)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    t0 = samples[0].timestamp_s
    full_rows = []
    position_rows = []
    for sample in samples:
        row = dict(zip(FULL_COLUMNS, (
            sample.timestamp_s - t0,
            *sample.position,
            *sample.quaternion_wxyz,
            *sample.linear_velocity,
            *sample.angular_velocity,
        )))
        full_rows.append(row)
        position_rows.append({name: row[name] for name in POSITION_COLUMNS})
    for filename, columns, rows in (
        ("rigid_body_6dof.csv", FULL_COLUMNS, full_rows),
        ("observations.csv", POSITION_COLUMNS, position_rows),
    ):
        with (output / filename).open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=columns)
            writer.writeheader()
            writer.writerows(rows)
    metadata = {
        "dataset_id": dataset_id,
        "provenance": "synthetic",
        "source": "gazebo harmonic odometry publisher (nominally noiseless)",
        "reference_frame": "ENU",
        "units": "SI",
        "time_origin": "elapsed_since_initial_state",
        "description": "simulator-generated object odometry; independent physical validation not established",
    }
    (output / "observations.json").write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
    )
    manifest = {
        "schema_version": "6dof.v1",
        "dataset_id": dataset_id,
        "sample_count": len(samples),
        "simulator": "gazebo harmonic",
        "simulator_run_verified": False,
        "clock": "simulator message timestamp; elapsed from first recorded sample",
        "coordinate_frame": "gazebo world assumed ENU for this world definition",
        "quaternion_order": "w,x,y,z",
        "angular_velocity_units": "rad/s",
        "twist_frame": "gazebo odometry publisher; verify frame before using twist as world-relative",
        "position_provenance": "simulated odometry, not physical measurements",
        "limitations": [
            "no aerodynamic force model is installed in the initial world",
            "observation csv intentionally contains no velocity to avoid frame ambiguity",
            "the first recorded sample is not necessarily the initial simulator state",
            "contact model and simulator engine may affect recorded dynamics",
        ],
    }
    (output / "run_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return manifest
