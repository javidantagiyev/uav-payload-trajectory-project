"""record a complete simulated-time window of inert-body odometry."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from threading import Lock

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from src.physics.simtime_protocol import SimTimeWindow
from src.physics.simulator_io import export_samples
from sim.gazebo.scripts.record_odometry import from_odometry


def main():
    p = argparse.ArgumentParser(description="capture a simulation-time window of gazebo odometry")
    p.add_argument("--topic", default="/sdp/inert_body/odometry")
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--duration-s", required=True, type=float)
    p.add_argument("--rate-hz", type=float, default=100)
    p.add_argument("--max-samples", type=int, default=20000)
    p.add_argument("--wall-timeout-s", type=float, default=120)
    p.add_argument("--start-limit-s", type=float, default=0.1)
    args = p.parse_args()
    try:
        capture = SimTimeWindow(args.duration_s, args.rate_hz, args.max_samples,
                                args.start_limit_s)
    except ValueError as exc:
        p.error(str(exc))
    if not 5 <= args.wall_timeout_s <= 1200:
        p.error("wall-timeout-s must be in [5,1200]")

    try:
        from gz.msgs10.odometry_pb2 import Odometry
        from gz.transport13 import Node
    except ImportError as exc:
        raise SystemExit("requires gazebo harmonic system python /usr/bin/python3") from exc

    args.output.mkdir(parents=True, exist_ok=True)
    ready_flag = args.output / "recorder_ready.flag"
    ready_flag.unlink(missing_ok=True)
    lock = Lock()

    def callback(msg):
        try:
            item = from_odometry(msg)
            with lock:
                capture.ingest(item)
        except (ValueError, AttributeError, TypeError) as exc:
            with lock:
                capture._reject(f"decoder: {exc}")

    node = Node()
    if not node.subscribe(Odometry, args.topic, callback):
        raise SystemExit(f"failed subscription: {args.topic}")
    ready_flag.write_text("ready\n", encoding="utf-8")
    print(f"ready {args.topic} / requested sim duration {args.duration_s}s", flush=True)

    deadline = time.monotonic() + args.wall_timeout_s
    interrupted = False
    try:
        while time.monotonic() < deadline:
            with lock:
                if capture.reached or capture.failure:
                    break
            time.sleep(0.01)
    except KeyboardInterrupt:
        interrupted = True

    with lock:
        report = capture.report(wall_timeout=not interrupted and time.monotonic() >= deadline)
        samples = list(capture.samples)
    report["interrupted"] = interrupted
    (args.output / "capture_status.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    ready_flag.unlink(missing_ok=True)
    if report["status"] != "sim_time_window_captured":
        print(json.dumps(report, indent=2), file=sys.stderr, flush=True)
        raise SystemExit(2)
    manifest = export_samples(samples, args.output)
    manifest.update({
        "simulator_run_verified": True,
        "recording_protocol": "simtime_window_6f",
        "capture": report,
        "position_provenance": "gazebo_odometry_not_independently_verified_ground_truth",
    })
    (args.output / "run_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    main()
