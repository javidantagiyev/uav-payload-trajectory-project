"""test coordinate frames, recorder conversion and dataset contracts."""

import csv
from types import SimpleNamespace as S

import pytest

from src.physics.multicopter_telemetry import (
    PX4_COLUMNS, TRUTH_COLUMNS, gazebo_pose_sample, ned_to_enu,
    px4_rows_from_arrays, read_csv, validate_rows, write_csv,
)


def test_ned_to_enu():
    assert ned_to_enu(1, 2, -3) == (2, 1, 3)
    with pytest.raises(ValueError):
        ned_to_enu(1, float("nan"), 2)


def fake_posev(stamped=True, name="x500_0", clock=3):
    stamp = S(sec=clock if stamped else 0, nsec=200000000 if stamped else 0)
    pose = S(name=name, header=S(stamp=S(sec=0, nsec=0)),
             position=S(x=1, y=2, z=3), orientation=S(w=1, x=0, y=0, z=0))
    return S(pose=[pose], header=S(stamp=stamp))


def test_gazebo_pose_extraction():
    row, source = gazebo_pose_sample(fake_posev(), "x500_0")
    assert source == "pose_v_header"
    assert row["sim_time_s"] == pytest.approx(3.2)
    assert row["z_m"] == 3
    assert gazebo_pose_sample(fake_posev(), "other") is None


def test_gazebo_clock_fallback_and_missing_clock():
    msg = fake_posev(stamped=False)
    assert gazebo_pose_sample(msg, "x500_0") is None
    row, source = gazebo_pose_sample(msg, "x500_0", 9.1)
    assert row["sim_time_s"] == 9.1
    assert source == "last_received_sim_clock"


def test_bad_quaternion_rejected():
    msg = fake_posev()
    msg.pose[0].orientation.w = 0.2
    with pytest.raises(ValueError, match="quaternion"):
        gazebo_pose_sample(msg, "x500_0")


def fields():
    return {
        "timestamp": [1_000_000, 1_100_000, 1_200_000],
        "x": [10, 11, 12], "y": [20, 21, 22], "z": [-3, -4, -5],
        "vx": [1, 2, 3], "vy": [4, 5, 6], "vz": [-7, -8, -9],
        "xy_valid": [1, 1, 0], "z_valid": [1, 1, 1],
    }


def test_px4_conversion():
    rows = px4_rows_from_arrays(fields())
    assert rows[0]["enu_x_east_m"] == 20
    assert rows[0]["enu_y_north_m"] == 10
    assert rows[0]["enu_z_up_m"] == 3
    assert rows[0]["enu_vx_east_m_s"] == 4
    assert rows[0]["enu_vz_up_m_s"] == 7
    assert rows[-1]["xy_valid"] == 0
    assert rows[0]["v_xy_valid"] == -1


def test_nonfinite_rows_skipped():
    inp = fields()
    inp["x"][1] = float("nan")
    assert len(px4_rows_from_arrays(inp)) == 2


def test_invalid_timestamps_rejected():
    inp = fields()
    inp["timestamp"] = [1_000_000, 1_000_000, 2_000_000]
    with pytest.raises(ValueError, match="timestamps"):
        px4_rows_from_arrays(inp)


def test_roundtrip_and_csv_rejection(tmp_path):
    rows = px4_rows_from_arrays(fields())
    path = tmp_path / "states.csv"
    write_csv(rows, path, PX4_COLUMNS, "px4_time_s")
    assert read_csv(path, PX4_COLUMNS, "px4_time_s") == rows
    with path.open("a", encoding="utf-8") as f:
        f.write("3,\n")
    with pytest.raises(ValueError):
        read_csv(path, PX4_COLUMNS, "px4_time_s")


def test_truth_timestamp_order(tmp_path):
    a = dict(zip(TRUTH_COLUMNS, (4.0, 1, 2, 3, 1, 0, 0, 0)))
    b = dict(a, sim_time_s=3.0)
    with pytest.raises(ValueError, match="timestamps"):
        write_csv([a, b], tmp_path / "bad.csv", TRUTH_COLUMNS, "sim_time_s")
