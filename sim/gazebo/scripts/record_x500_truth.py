"""capture simulated gazebo x500 model poses without flight commands."""

import argparse
import sys
import time
from pathlib import Path
from threading import Lock

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from src.physics.multicopter_telemetry import (
    TRUTH_COLUMNS, gazebo_pose_sample, write_csv, write_manifest,
)


def main():
    parser = argparse.ArgumentParser(description="record gazebo x500 world pose")
    parser.add_argument("--model", default="x500_0")
    parser.add_argument("--topic", default="/world/default/pose/info")
    parser.add_argument("--clock-topic", default="/world/default/clock")
    parser.add_argument("--seconds", type=float, default=20.0)
    parser.add_argument("--rate-hz", type=float, default=25.0)
    parser.add_argument("--output", type=Path, default=ROOT / "results/multicopter_testbed/local_run")
    args = parser.parse_args()
    if not (1 <= args.seconds <= 600 and 1 <= args.rate_hz <= 100):
        parser.error("seconds must be 1-600 and rate-hz 1-100")
    try:
        from gz.msgs10.clock_pb2 import Clock
        from gz.msgs10.pose_v_pb2 import Pose_V
        from gz.transport13 import Node
    except ImportError as exc:
        raise SystemExit("gazebo python bindings missing; run with /usr/bin/python3") from exc

    lock = Lock()
    samples = []
    errors = []
    last_clock = [None]
    source_counts = {}
    min_step = 1.0 / args.rate_hz

    def on_clock(msg):
        stamp = msg.sim
        with lock:
            last_clock[0] = float(stamp.sec) + float(stamp.nsec) * 1e-9

    def on_pose(msg):
        with lock:
            try:
                result = gazebo_pose_sample(msg, args.model, last_clock[0])
                if result is None:
                    return
                row, source = result
                if samples and row["sim_time_s"] - samples[-1]["sim_time_s"] < min_step - 1e-8:
                    return
                samples.append(row)
                source_counts[source] = source_counts.get(source, 0) + 1
            except (ValueError, AttributeError) as exc:
                if len(errors) < 5:
                    errors.append(str(exc))

    node = Node()
    if not node.subscribe(Clock, args.clock_topic, on_clock):
        raise SystemExit(f"cannot subscribe to clock topic: {args.clock_topic}")
    if not node.subscribe(Pose_V, args.topic, on_pose):
        raise SystemExit(f"cannot subscribe to pose topic: {args.topic}")
    print(f"recording model {args.model} on {args.topic} for {args.seconds:g} wall seconds")
    start = time.monotonic()
    try:
        while time.monotonic() - start < args.seconds:
            time.sleep(0.1)
    except KeyboardInterrupt:
        pass
    with lock:
        data = list(samples)
        sources = dict(source_counts)
        problems = list(errors)
    if len(data) < 2:
        raise SystemExit(f"no usable poses for {args.model}; check gz topic -l and model name. errors={problems}")
    output = args.output
    write_csv(data, output / "gazebo_truth.csv", TRUTH_COLUMNS, "sim_time_s")
    write_manifest(
        output / "gazebo_truth_manifest.json",
        provenance="simulator_ground_truth_not_physical_measurement",
        simulator="gazebo harmonic", model=args.model, topic=args.topic,
        coordinate_frame="gazebo_world_enu_assumed_verify_world_orientation",
        clock="gazebo_simulation_absolute_seconds",
        timestamp_sources=sources, sample_count=len(data),
        start_sim_time_s=data[0]["sim_time_s"], end_sim_time_s=data[-1]["sim_time_s"],
        recording_errors=problems,
        limitation="pose stream has no velocity; do not claim synchronized px4 comparison without clock and origin checks",
    )
    print(f"saved {len(data)} gazebo samples to {output / 'gazebo_truth.csv'}")
    print(f"timestamp sources: {sources}")


if __name__ == "__main__":
    main()
