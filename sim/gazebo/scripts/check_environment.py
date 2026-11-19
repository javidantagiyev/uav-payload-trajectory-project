"""report simulator prerequisites without changing the host installation."""

import argparse
import json
import platform
import shutil
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=None)
    args = parser.parse_args()
    checks = {"platform": platform.platform(), "python": sys.version.split()[0], "gz_on_path": bool(shutil.which("gz"))}
    if checks["gz_on_path"]:
        try:
            proc = subprocess.run(["gz", "sim", "--versions"], capture_output=True, text=True, timeout=10)
            checks["gazebo_version_output"] = (proc.stdout or proc.stderr).strip()[:400]
            checks["gazebo_version_command_exit"] = proc.returncode
        except (OSError, subprocess.TimeoutExpired) as exc:
            checks["gazebo_version_error"] = str(exc)
    try:
        from gz.transport13 import Node
        from gz.msgs10.odometry_pb2 import Odometry
        checks["gazebo_python_transport"] = True
    except ImportError:
        checks["gazebo_python_transport"] = False
    output = json.dumps(checks, indent=2)
    print(output)
    if args.output:
        from pathlib import Path
        Path(args.output).write_text(output + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
