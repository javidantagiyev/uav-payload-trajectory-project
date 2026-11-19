"""tests for observation schema and time-aligned comparisons."""

import csv
import json
from pathlib import Path

import numpy as np
import pytest

from src.physics import integrate
from src.physics.validation import compare_trajectory, load_observations

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_CSV = ROOT / "data/examples/synthetic_observations.csv"
EXAMPLE_META = ROOT / "data/examples/synthetic_observations.json"


def test_fixture_is_explicitly_synthetic():
    obs = load_observations(EXAMPLE_CSV, EXAMPLE_META)
    assert obs.metadata["provenance"] == "synthetic"
    assert obs.positions.shape == (11, 3)
    assert obs.velocities is None
    assert obs.times[0] == 0.0


def test_invalid_reference_frame_is_rejected(tmp_path):
    data = json.loads(EXAMPLE_META.read_text())
    data["reference_frame"] = "NED"
    metadata = tmp_path / "metadata.json"
    metadata.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="enu"):
        load_observations(EXAMPLE_CSV, metadata)


def test_missing_column_is_rejected(tmp_path):
    file = tmp_path / "bad.csv"
    file.write_text("time_s,x_m,y_m\n0,1,2\n1,2,3\n")
    with pytest.raises(ValueError, match="columns"):
        load_observations(file, EXAMPLE_META)


def test_missing_velocity_component_is_rejected(tmp_path):
    file = tmp_path / "bad.csv"
    file.write_text("time_s,x_m,y_m,z_m,vx_m_s\n0,1,2,3,4\n1,2,3,4,5\n")
    with pytest.raises(ValueError, match="velocity"):
        load_observations(file, EXAMPLE_META)


@pytest.mark.parametrize("times", [[0, 0], [1, 0], [-1, 0]])
def test_bad_time_order_is_rejected(tmp_path, times):
    file = tmp_path / "bad.csv"
    with file.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["time_s", "x_m", "y_m", "z_m"])
        for t in times:
            writer.writerow([t, 1, 2, 3])
    with pytest.raises(ValueError, match="time"):
        load_observations(file, EXAMPLE_META)


def test_nonfinite_values_are_rejected(tmp_path):
    file = tmp_path / "bad.csv"
    file.write_text("time_s,x_m,y_m,z_m\n0,1,2,3\n1,nan,3,4\n")
    with pytest.raises(ValueError, match="nonfinite"):
        load_observations(file, EXAMPLE_META)


def test_metrics_for_known_constant_offset(tmp_path):
    file = tmp_path / "data.csv"
    file.write_text("time_s,x_m,y_m,z_m\n0,1,0,0\n0.5,1.5,0,0\n1,2,0,0\n")
    observations = load_observations(file, EXAMPLE_META)
    rhs = lambda t, state: (state[3], state[4], state[5], 0, 0, 0)
    prediction = integrate(rhs, [0, 0, 0, 1, 0, 0], 1.0, 0.25, "rk4")
    metrics, rows = compare_trajectory(prediction, observations)
    assert metrics["count"] == 3
    assert metrics["position_rmse_m"] == pytest.approx(1)
    assert metrics["axis_bias_m"]["x"] == pytest.approx(-1)
    assert len(rows) == 3


def test_no_extrapolation(tmp_path):
    file = tmp_path / "data.csv"
    file.write_text("time_s,x_m,y_m,z_m\n0,0,0,0\n2,0,0,0\n")
    observations = load_observations(file, EXAMPLE_META)
    prediction = integrate(lambda t, state: (0, 0, 0, 0, 0, 0), [0] * 6, 1.0, 0.2)
    with pytest.raises(ValueError, match="outside"):
        compare_trajectory(prediction, observations)


def test_optional_velocity_metrics(tmp_path):
    file = tmp_path / "data.csv"
    file.write_text("time_s,x_m,y_m,z_m,vx_m_s,vy_m_s,vz_m_s\n0,0,0,0,1,0,0\n1,1,0,0,1,0,0\n")
    observations = load_observations(file, EXAMPLE_META)
    prediction = integrate(lambda t, state: (1, 0, 0, 0, 0, 0), [0, 0, 0, 1, 0, 0], 1.0, 0.1)
    metrics, _ = compare_trajectory(prediction, observations)
    assert metrics["position_rmse_m"] == pytest.approx(0, abs=1e-12)
    assert metrics["velocity_rmse_m_s"] == pytest.approx(0, abs=1e-12)


def test_duplicate_csv_column_is_rejected(tmp_path):
    file = tmp_path / "data.csv"
    file.write_text("time_s,x_m,x_m,z_m\n0,0,0,0\n1,0,0,0\n")
    with pytest.raises(ValueError):
        load_observations(file, EXAMPLE_META)
