"""run isolated 6f experiments with odometry simulation-time stopping."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from sim.gazebo.scripts.run_environment_batch import (control_command,
                                                      detect_service, stop_process)


def prepare_rate_world(source: Path, target: Path, rate_hz: int):
    """override only the odometry publisher rate; preserve original sdf."""
    root = ET.parse(source)
    plugin = root.find("world/model[@name='inert_body']/plugin[@name='gz::sim::systems::OdometryPublisher']")
    if plugin is None or plugin.find("odom_publish_frequency") is None:
        raise ValueError("missing inert-body odometry publisher")
    physics_step = root.find("world/physics/max_step_size")
    if physics_step is None or rate_hz > 1 / float(physics_step.text) + 1e-9:
        raise ValueError("odometry rate exceeds physics update rate")
    plugin.find("odom_publish_frequency").text = str(rate_hz)
    ET.indent(root.getroot(), "  ")
    target.parent.mkdir(parents=True, exist_ok=True)
    root.write(target, encoding="unicode", xml_declaration=True)
    return hashlib.sha256(target.read_bytes()).hexdigest()


def run_case(case, run_index, output, duration_s, rate_hz, timeout_s, startup_s):
    output.mkdir(parents=True, exist_ok=False)
    env = os.environ.copy()
    env["GZ_PARTITION"] = f"sdp_6f_{os.getpid()}_{case['id']}_{run_index:03d}"
    world = case["world_name"]
    report = {
        "case_id": case["id"],
        "repeat_index": run_index,
        "status": "failed",
        "gazebo_partition": env["GZ_PARTITION"],
        "requested_duration_sim_s": duration_s,
        "requested_odom_rate_hz": rate_hz,
        "seed_policy": "no_explicit_gazebo_rng_seed; repeats do not imply independent samples",
        "scenario_parameters": case["parameters"],
        "scenario_source_sha256": case["sdf_sha256"],
        "simulator_recording_provenance": "gazebo_odometry_not_physical_ground_truth",
    }
    server = None
    recorder = None
    started = time.monotonic()
    try:
        source = Path(case["world"])
        if hashlib.sha256(source.read_bytes()).hexdigest() != case["sdf_sha256"]:
            raise ValueError("source sdf differs from scenario manifest")
        derived = output / "world_with_rate.sdf"
        report["effective_world_sha256"] = prepare_rate_world(source, derived, rate_hz)
        with (output / "gazebo_server.log").open("w", encoding="utf-8") as log:
            server = subprocess.Popen(["gz", "sim", "-s", "-v", "2", str(derived)],
                                      stdout=log, stderr=subprocess.STDOUT, env=env)
            if not detect_service(world, env, startup_s):
                raise RuntimeError("gazebo world control service not found")
            with (output / "recorder.log").open("w", encoding="utf-8") as rec_log:
                recorder = subprocess.Popen([
                    "/usr/bin/python3", "-u",
                    str(ROOT / "sim/gazebo/scripts/record_odometry_simtime.py"),
                    "--output", str(output),
                    "--duration-s", str(duration_s),
                    "--rate-hz", str(rate_hz),
                    "--wall-timeout-s", str(timeout_s),
                ], stdout=rec_log, stderr=subprocess.STDOUT, env=env)
                ready = output / "recorder_ready.flag"
                deadline = time.monotonic() + startup_s
                while time.monotonic() < deadline and not ready.exists():
                    if recorder.poll() is not None:
                        raise RuntimeError("recorder exited before becoming ready")
                    time.sleep(0.05)
                if not ready.exists():
                    raise RuntimeError("recorder did not signal ready")
                command = subprocess.run(control_command(world), env=env,
                                         capture_output=True, text=True, timeout=8)
                (output / "unpause_response.txt").write_text(
                    command.stdout + command.stderr, encoding="utf-8")
                if command.returncode != 0 or "true" not in command.stdout.lower():
                    raise RuntimeError("gazebo refused to unpause")
                try:
                    rc = recorder.wait(timeout=timeout_s + 8)
                except subprocess.TimeoutExpired as exc:
                    raise RuntimeError("recorder process exceeded wall timeout") from exc
                if rc != 0:
                    raise RuntimeError(f"recorder returned {rc}; see recorder.log and capture_status.json")
                capture_path = output / "capture_status.json"
                if not capture_path.exists():
                    raise RuntimeError("missing capture status")
                capture = json.loads(capture_path.read_text(encoding="utf-8"))
                if capture.get("status") != "sim_time_window_captured":
                    raise RuntimeError("incomplete simulation-time capture")
                report["capture"] = capture
                if not (output / "rigid_body_6dof.csv").is_file():
                    raise RuntimeError("missing 6dof csv")
                report["trajectory_sha256"] = hashlib.sha256(
                    (output / "rigid_body_6dof.csv").read_bytes()).hexdigest()
                report["status"] = "sim_time_window_recorded"
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        report["reason"] = str(exc)
    finally:
        stop_process(recorder)
        stop_process(server)
        report["wall_duration_s"] = round(time.monotonic() - started, 3)
        (output / "run_status.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main():
    p = argparse.ArgumentParser(description="6f simulation-time batch studies")
    p.add_argument("--worlds", type=Path,
                   default=ROOT / "results/environmental_testbed/local_run/worlds")
    p.add_argument("--output", type=Path,
                   default=ROOT / "results/environmental_testbed/simtime_6f")
    p.add_argument("--cases", nargs="+", default=["baseline", "wind_east_4"])
    p.add_argument("--all", action="store_true")
    p.add_argument("--execute", action="store_true")
    p.add_argument("--repeats", type=int, default=3)
    p.add_argument("--duration-s", type=float, default=2.0)
    p.add_argument("--rate-hz", type=int, default=100)
    p.add_argument("--wall-timeout-s", type=float, default=120)
    p.add_argument("--startup-timeout-s", type=float, default=30)
    p.add_argument("--skip-existing", action="store_true")
    args = p.parse_args()
    if not (1 <= args.repeats <= 50):
        p.error("repeats must be 1..50")
    if not (0 < args.duration_s <= 180 and 1 <= args.rate_hz <= 500):
        p.error("unsupported duration or rate")
    if args.duration_s * args.rate_hz + 3 > 20000:
        p.error("legacy trajectory exporter supports at most 20,000 samples")
    if not (5 <= args.wall_timeout_s <= 1200 and 5 <= args.startup_timeout_s <= 180):
        p.error("invalid wall-time limits")
    source = args.worlds / "scenario_manifest.json"
    if not source.is_file():
        p.error("generate worlds first: python experiments/prepare_environment_matrix.py")
    manifest = json.loads(source.read_text(encoding="utf-8"))
    options = manifest["cases"]
    selected = options if args.all else [c for c in options if c["id"] in args.cases]
    if not selected or (not args.all and set(args.cases) != {c["id"] for c in selected}):
        p.error("unknown case")
    for case in selected:
        if not Path(case["world"]).is_file():
            p.error(f"missing world {case['world']}")
    plan = {
        "status": "dry_run_no_simulator_started" if not args.execute else "running",
        "cases": [c["id"] for c in selected],
        "repeats_per_case": args.repeats,
        "duration_sim_s": args.duration_s,
        "rate_hz": args.rate_hz,
        "total_runs": len(selected) * args.repeats,
        "warning": "repeats test reproducibility; no controlled gazebo random seeds",
    }
    if not args.execute:
        print(json.dumps(plan, indent=2))
        return
    if shutil.which("gz") is None or not Path("/usr/bin/python3").exists():
        p.error("requires gazebo and ubuntu system python")
    probe = subprocess.run(["/usr/bin/python3", "-c", "import gz.transport13, gz.msgs10"],
                           capture_output=True, text=True, timeout=12)
    if probe.returncode != 0:
        p.error("gazebo python bindings unavailable: " + probe.stderr)
    args.output.mkdir(parents=True, exist_ok=True)
    results = []
    for case in selected:
        for i in range(args.repeats):
            folder = args.output / "runs" / case["id"] / f"run_{i:03d}"
            if folder.exists():
                if args.skip_existing:
                    status_file = folder / "run_status.json"
                    if status_file.is_file():
                        existing = json.loads(status_file.read_text(encoding="utf-8"))
                        if (existing.get("status") == "sim_time_window_recorded"
                                and existing.get("requested_duration_sim_s") == args.duration_s
                                and existing.get("requested_odom_rate_hz") == args.rate_hz
                                and existing.get("scenario_source_sha256") == case["sdf_sha256"]):
                            trajectory = folder / "rigid_body_6dof.csv"
                            if (trajectory.is_file() and
                                    hashlib.sha256(trajectory.read_bytes()).hexdigest() ==
                                    existing.get("trajectory_sha256")):
                                print("skip verified", case["id"], i, flush=True)
                                results.append(existing)
                                continue
                p.error(f"output already exists: {folder}; no overwrite allowed")
            print("running", case["id"], i, flush=True)
            result = run_case(case, i, folder, args.duration_s, args.rate_hz,
                              args.wall_timeout_s, args.startup_timeout_s)
            results.append(result)
            print(result["status"], case["id"], i, result.get("reason", ""), flush=True)
    study = {**plan, "status": "completed_batch", "runs": results,
             "recorded": sum(r["status"] == "sim_time_window_recorded" for r in results)}
    (args.output / "batch_manifest.json").write_text(json.dumps(study, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"recorded": study["recorded"], "attempted": len(results)}, indent=2))
    if study["recorded"] != len(results):
        sys.exit(1)


if __name__ == "__main__":
    main()
