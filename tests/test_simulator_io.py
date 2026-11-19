"""test simulator observation schemas and their integration contract."""

import csv
import json
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

from src.physics.simulator_io import RigidBodySample, export_samples, validate_samples
from src.physics.validation import load_observations


def sample(t, x=0.0, angle=0.0):
    return RigidBodySample(
        timestamp_s=t,
        position=(x, 0.1, 2.0),
        quaternion_wxyz=(1.0, 0.0, 0.0, 0.0),
        linear_velocity=(0.0, 0.0, 0.0),
        angular_velocity=(0.0, 0.0, angle),
    )


def test_export_integrates_with_package_5_loader(tmp_path):
    manifest = export_samples([sample(10.0, 0), sample(10.02, 0.1), sample(10.04, 0.2)], tmp_path)
    obs = load_observations(tmp_path / "observations.csv", tmp_path / "observations.json")
    assert obs.times.tolist() == pytest.approx([0, 0.02, 0.04])
    assert obs.positions[:, 0].tolist() == pytest.approx([0, 0.1, 0.2])
    assert obs.velocities is None
    assert obs.metadata["provenance"] == "synthetic"
    assert manifest["sample_count"] == 3
    assert manifest["simulator_run_verified"] is False
    with (tmp_path / "rigid_body_6dof.csv").open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert float(rows[0]["qw"]) == 1.0
    assert float(rows[2]["time_s"]) == pytest.approx(0.04)


@pytest.mark.parametrize("samples", [
    [], [sample(0)], [sample(1), sample(1)], [sample(2), sample(1)],
])
def test_invalid_sample_series(samples):
    with pytest.raises(ValueError):
        validate_samples(samples)


def test_reject_invalid_quaternion():
    bad = RigidBodySample(0.0, (0, 0, 1), (0.5, 0, 0, 0), (0, 0, 0), (0, 0, 0))
    with pytest.raises(ValueError, match="quaternion"):
        bad.validate()


def test_reject_nonfinite_measurement():
    bad = RigidBodySample(float("nan"), (0, 0, 1), (1, 0, 0, 0), (0, 0, 0), (0, 0, 0))
    with pytest.raises(ValueError, match="nonfinite"):
        bad.validate()


def test_odometry_message_adapter_import(tmp_path):
    import importlib.util
    path = Path(__file__).resolve().parents[1] / "sim/gazebo/scripts/record_odometry.py"
    spec = importlib.util.spec_from_file_location("recorder_adapter_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    vec = lambda a,b,c: NS(x=a, y=b, z=c)
    msg = NS(
        header=NS(stamp=NS(sec=5, nsec=500000000)),
        pose=NS(position=vec(1,2,3), orientation=NS(w=1,x=0,y=0,z=0)),
        twist=NS(linear=vec(0.1,0.2,0.3), angular=vec(1,2,3)),
    )
    observed = module.from_odometry(msg)
    assert observed.timestamp_s == pytest.approx(5.5)
    assert observed.position == (1,2,3)
    assert observed.angular_velocity == (1,2,3)


def test_visualization_produces_figures_from_recording(tmp_path):
    import importlib.util
    script = Path(__file__).resolve().parents[1] / "experiments/visualize_simulation.py"
    spec = importlib.util.spec_from_file_location("visualize_simulation_test", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    export_samples([sample(7.0, 0), sample(7.02, 0.2), sample(7.04, 0.3)], tmp_path)
    summary = module.run(tmp_path / "rigid_body_6dof.csv", tmp_path)
    assert summary["sample_count"] == 3
    assert (tmp_path / "figures/trajectory_3d.png").is_file()
    assert (tmp_path / "figures/position_attitude.png").is_file()
    assert (tmp_path / "recording_summary.json").is_file()
