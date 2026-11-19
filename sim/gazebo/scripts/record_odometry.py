"""record gazebo odometry into the repository's documented observation schema."""

import argparse
import json
import sys
import time
from pathlib import Path
from threading import Lock

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from src.physics.simulator_io import RigidBodySample, export_samples


def from_odometry(msg):
    """extract pose and twist from a gazebo odometry protobuf message."""
    stamp = msg.header.stamp
    return RigidBodySample(
        timestamp_s=float(stamp.sec) + float(stamp.nsec) * 1e-9,
        position=(msg.pose.position.x, msg.pose.position.y, msg.pose.position.z),
        quaternion_wxyz=(
            msg.pose.orientation.w,
            msg.pose.orientation.x,
            msg.pose.orientation.y,
            msg.pose.orientation.z,
        ),
        linear_velocity=(msg.twist.linear.x, msg.twist.linear.y, msg.twist.linear.z),
        angular_velocity=(msg.twist.angular.x, msg.twist.angular.y, msg.twist.angular.z),
    )


def main():
    parser = argparse.ArgumentParser(description="record inert-body 6-dof gazebo odometry")
    parser.add_argument("--topic", default="/sdp/inert_body/odometry")
    parser.add_argument("--output", type=Path, default=ROOT / "results/simulation_testbed/local_run")
    parser.add_argument("--seconds", type=float, default=15)
    parser.add_argument("--max-samples", type=int, default=1500)
    args = parser.parse_args()
    if not (0 < args.seconds <= 300 and 2 <= args.max_samples <= 20000):
        parser.error("seconds must be in (0,300] and max-samples in [2,20000]")

    try:
        from gz.msgs10.odometry_pb2 import Odometry
        from gz.transport13 import Node
    except ImportError as exc:
        raise SystemExit(
            "gazebo harmonic python transport is missing; use ubuntu system python3, "
            "not the windows or project virtual environment. see sim/gazebo/README.md"
        ) from exc

    records = []
    errors = []
    lock = Lock()

    def on_message(msg):
        try:
            sample = from_odometry(msg)
            sample.validate()
            with lock:
                if len(records) < args.max_samples and (
                    not records or sample.timestamp_s > records[-1].timestamp_s
                ):
                    records.append(sample)
        except (ValueError, AttributeError) as exc:
            with lock:
                if len(errors) < 5:
                    errors.append(str(exc))

    node = Node()
    if not node.subscribe(Odometry, args.topic, on_message):
        raise SystemExit(f"cannot subscribe to {args.topic}; check gazebo topic list")

    print(f"subscribed to {args.topic}. start or unpause gazebo. recording for {args.seconds:g} wall seconds.")
    start = time.monotonic()
    try:
        while time.monotonic() - start < args.seconds:
            time.sleep(0.05)
            with lock:
                if len(records) >= args.max_samples:
                    break
    except KeyboardInterrupt:
        pass
    with lock:
        captured = list(records)
        seen_errors = list(errors)
    if len(captured) < 2:
        raise SystemExit(
            f"only {len(captured)} valid samples received; ensure world is running and topic is publishing. "
            f"sample errors: {seen_errors}"
        )
    manifest = export_samples(captured, args.output)
    manifest["simulator_run_verified"] = True
    manifest["recording_errors"] = seen_errors
    (args.output / "run_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"samples": len(captured), "output": str(args.output), "first_time_s": captured[0].timestamp_s,
                      "last_time_s": captured[-1].timestamp_s}, indent=2))


if __name__ == "__main__":
    main()
