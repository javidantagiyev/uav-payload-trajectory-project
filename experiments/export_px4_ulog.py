"""export px4 estimator local position from a finished ulog recording."""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.physics.multicopter_telemetry import (
    PX4_COLUMNS, px4_rows_from_arrays, write_csv, write_manifest,
)


def extract_ulog(path):
    try:
        from pyulog import ULog
    except ImportError as exc:
        raise SystemExit("install pyulog in project .venv: python -m pip install pyulog") from exc
    ulog = ULog(str(path))
    matches = [msg for msg in ulog.data_list if msg.name == "vehicle_local_position" and msg.multi_id == 0]
    if not matches:
        available = sorted({msg.name for msg in ulog.data_list})
        raise ValueError(f"ulog missing vehicle_local_position instance 0. logged topics: {available[:30]}")
    return px4_rows_from_arrays(matches[0].data)


def main():
    parser = argparse.ArgumentParser(description="convert px4 ulog state estimates to enu csv")
    parser.add_argument("ulog", type=Path, help="finished .ulg log from px4 sitl")
    parser.add_argument("--output", type=Path, default=ROOT / "results/multicopter_testbed/local_run")
    args = parser.parse_args()
    if not args.ulog.is_file():
        parser.error(f"ulog not found: {args.ulog}")
    rows = extract_ulog(args.ulog)
    write_csv(rows, args.output / "px4_local_position.csv", PX4_COLUMNS, "px4_time_s")
    write_manifest(
        args.output / "px4_local_position_manifest.json",
        provenance="px4_ekf_estimate_not_ground_truth",
        source_log=str(args.ulog.resolve()),
        sample_count=len(rows), coordinate_frame_input="NED", coordinate_frame_output="ENU",
        timestamp_source="ulog_vehicle_local_position.timestamp_microseconds_divided_by_1e6",
        time_alignment="not_verified_against_gazebo",
        position_origin="px4_local_estimator_origin_not_calibrated_against_gazebo_world",
        notes="invalid estimate flags retained; invalid or nonfinite numerical rows skipped",
    )
    print(f"saved {len(rows)} px4 estimates to {args.output / 'px4_local_position.csv'}")
    print(f"PX4 time range: {rows[0]['px4_time_s']:.3f} to {rows[-1]['px4_time_s']:.3f} s")


if __name__ == "__main__":
    main()
