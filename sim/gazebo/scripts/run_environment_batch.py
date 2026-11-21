"""run isolated headless gazebo environments and record odometry."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def control_command(world):
    return [
        "gz", "service", "-s", f"/world/{world}/control",
        "--reqtype", "gz.msgs.WorldControl",
        "--reptype", "gz.msgs.Boolean",
        "--timeout", "3000", "--req", "pause: false",
    ]


def detect_service(world, env, timeout_s):
    deadline = time.monotonic() + timeout_s
    service = f"/world/{world}/control"
    while time.monotonic() < deadline:
        try:
            result = subprocess.run(["gz", "service", "-l"], env=env,
                                    capture_output=True, text=True, timeout=4)
            if result.returncode == 0 and service in result.stdout.splitlines():
                return True
        except (OSError, subprocess.TimeoutExpired):
            pass
        time.sleep(0.5)
    return False


def stop_process(proc):
    if proc is None or proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)


def run_one(case, output, seconds, timeout):
    case_id = case["id"]
    output.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    # isolate from px4 gazebo and from previous test runs.
    env["GZ_PARTITION"] = f"sdp_env_{os.getpid()}_{case_id}"
    world = case["world_name"]
    server = None
    recorder = None
    result = {"id": case_id, "status": "failed", "partition": env["GZ_PARTITION"],
              "world_sha256": case["sdf_sha256"]}
    started = time.monotonic()
    try:
        with (output / "gazebo_server.log").open("w", encoding="utf-8") as log:
            server = subprocess.Popen(["gz", "sim", "-s", "-v", "2", case["world"]],
                                      stdout=log, stderr=subprocess.STDOUT, env=env)
            if not detect_service(world, env, timeout):
                result["reason"] = "world control service did not appear"
                return result
            record_path = output / "recorder.log"
            with record_path.open("w", encoding="utf-8") as rlog:
                recorder = subprocess.Popen([
                    "/usr/bin/python3", "-u",
                    str(ROOT / "sim/gazebo/scripts/record_odometry.py"),
                    "--output", str(output), "--seconds", str(seconds),
                ], stdout=rlog, stderr=subprocess.STDOUT, env=env)
                time.sleep(1)
                if recorder.poll() is not None:
                    result["reason"] = "recorder exited before start"
                    return result
                unpause = subprocess.run(control_command(world), env=env,
                                         text=True, capture_output=True, timeout=8)
                (output / "unpause_response.txt").write_text(
                    unpause.stdout + unpause.stderr, encoding="utf-8")
                if unpause.returncode != 0 or "true" not in unpause.stdout.lower():
                    result["reason"] = "failed to unpause world"
                    return result
                try:
                    rc = recorder.wait(timeout=seconds + timeout)
                except subprocess.TimeoutExpired:
                    result["reason"] = "recorder timed out"
                    return result
                if rc != 0 or not (output / "rigid_body_6dof.csv").is_file():
                    result["reason"] = "recorder failed or produced no trajectory"
                    return result
                result["status"] = "simulator_run_recorded"
                result["simulator_runtime_verified"] = True
    except (OSError, subprocess.SubprocessError) as exc:
        result["reason"] = str(exc)
    finally:
        stop_process(recorder)
        stop_process(server)
        result["wall_duration_s"] = round(time.monotonic() - started, 3)
        (output / "batch_case_status.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def main():
    p = argparse.ArgumentParser(description="screen gazebo worlds headlessly")
    p.add_argument("--worlds", type=Path,
                   default=ROOT / "results/environmental_testbed/local_run/worlds")
    p.add_argument("--output", type=Path,
                   default=ROOT / "results/environmental_testbed/local_run/runs")
    p.add_argument("--cases", nargs="+", default=["baseline", "wind_east_4"])
    p.add_argument("--all", action="store_true")
    p.add_argument("--execute", action="store_true")
    p.add_argument("--seconds", type=float, default=6)
    p.add_argument("--timeout", type=float, default=30)
    args = p.parse_args()
    if not 3 <= args.seconds <= 60 or not 5 <= args.timeout <= 180:
        p.error("invalid time settings")
    path = args.worlds / "scenario_manifest.json"
    if not path.is_file():
        p.error("generate worlds first with experiments/prepare_environment_matrix.py")
    cases = json.loads(path.read_text(encoding="utf-8"))["cases"]
    selected = cases if args.all else [c for c in cases if c["id"] in args.cases]
    if not selected or (not args.all and set(args.cases) != {c["id"] for c in selected}):
        p.error("unknown case id")
    for c in selected:
        if not Path(c["world"]).is_file():
            p.error(f"missing generated sdf for {c['id']}")
    if not args.execute:
        print(json.dumps({"status": "dry_run_no_simulator_started",
                          "cases": [c["id"] for c in selected],
                          "record_wall_seconds_per_case": args.seconds,
                          "launch": "gazebo headless + system python recorder + unpause service"}, indent=2))
        return
    if shutil.which("gz") is None or not Path("/usr/bin/python3").exists():
        p.error("requires gazebo and ubuntu system python")
    try:
        result = subprocess.run(["/usr/bin/python3", "-c",
                                 "import gz.transport13, gz.msgs10"],
                                capture_output=True, text=True, timeout=10)
        if result.returncode:
            p.error("gazebo python bindings missing: " + result.stderr)
    except subprocess.TimeoutExpired:
        p.error("gazebo python binding import timed out")
    results = []
    for case in selected:
        print("running", case["id"], flush=True)
        result = run_one(case, args.output / case["id"], args.seconds, args.timeout)
        results.append(result)
        print(result["status"], result["id"], result.get("reason", ""), flush=True)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "batch_status.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"recorded": sum(r["status"] == "simulator_run_recorded" for r in results),
                      "attempted": len(results)}, indent=2))
    if any(r["status"] != "simulator_run_recorded" for r in results):
        sys.exit(1)


if __name__ == "__main__":
    main()
