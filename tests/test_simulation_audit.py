"""test simulator odometry audit without requiring gazebo runtime."""

import csv
import importlib.util
import math
from pathlib import Path

import numpy as np
import pytest

from src.physics.simulation_audit import analyse, body_to_world, load_recording


def recording(tmp_path, n=100):
    p = tmp_path / "rigid_body_6dof.csv"
    columns = (
        "time_s", "x_m", "y_m", "z_m", "qw", "qx", "qy", "qz",
        "linear_vx_m_s", "linear_vy_m_s", "linear_vz_m_s",
        "angular_wx_rad_s", "angular_wy_rad_s", "angular_wz_rad_s",
    )
    with p.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(columns)
        for i in range(n):
            t = i * 0.01
            z = 2.1 - 0.1*t - 4.905*t*t
            previous_t = (i - 1) * 0.01
            previous_z = 2.1 - 0.1*previous_t - 4.905*previous_t*previous_t
            vz = (z - previous_z) / 0.01 if i else 220.0
            writer.writerow((t, 0, 0, z, 1, 0, 0, 0, 0, 0, vz, 0, 0, 0))
    return p


def test_body_frame_velocity_rotates_to_world():
    theta = math.pi / 2
    q = np.array([[math.cos(theta / 2), 0, 0, math.sin(theta / 2)]])
    result = body_to_world(q, np.array([[2.0, 0.0, 0.0]]))
    assert result[0] == pytest.approx([0, 2.0, 0], abs=1e-12)


def test_recovers_gravity_and_flags_initial_sample(tmp_path):
    data = load_recording(recording(tmp_path))
    summary, aux = analyse(data)
    assert summary["status"] == "pass"
    assert summary["estimated_gravity_m_s2"] == pytest.approx(9.81, abs=1e-8)
    assert summary["free_flight_world_velocity_rmse_m_s"] < 1e-8
    assert summary["initial_twist_suspect"] is True
    assert summary["initial_twist_disagreement_m_s"] > 200
    assert np.isnan(aux["backward_velocity"][0, 2])


def test_rejects_unfit_window(tmp_path):
    data = load_recording(recording(tmp_path))
    with pytest.raises(ValueError, match="free-flight window"):
        analyse(data, free_flight_until_s=0.02)


def test_rejects_nonmonotonic_time_and_bad_quaternion(tmp_path):
    path = recording(tmp_path)
    lines = path.read_text().splitlines()
    lines[3] = lines[2]
    path.write_text("\n".join(lines) + "\n")
    with pytest.raises(ValueError, match="timestamps"):
        load_recording(path)
    path = recording(tmp_path)
    lines = path.read_text().splitlines()
    fields = lines[2].split(",")
    fields[4] = "0.5"
    lines[2] = ",".join(fields)
    path.write_text("\n".join(lines) + "\n")
    with pytest.raises(ValueError, match="quaternions"):
        load_recording(path)


def test_recreates_figures_and_preserves_input(tmp_path):
    source = recording(tmp_path)
    raw_bytes = source.read_bytes()
    module_path = Path(__file__).resolve().parents[1] / "experiments/audit_simulation.py"
    spec = importlib.util.spec_from_file_location("simulator_audit_runner_test", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    result = module.run(source, tmp_path)
    assert result["status"] == "pass"
    first = tmp_path / "figures/height_physics_check.png"
    second = tmp_path / "figures/velocity_and_horizontal_check.png"
    assert first.exists() and second.exists()
    assert (tmp_path / "world_frame_twist.csv").exists()
    assert (tmp_path / "simulation_audit.json").exists()
    first.unlink()
    module.run(source, tmp_path)
    assert first.exists()
    assert source.read_bytes() == raw_bytes
