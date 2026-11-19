"""plot independent gazebo and px4 telemetry timelines without false alignment."""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.physics.multicopter_telemetry import (
    PX4_COLUMNS, TRUTH_COLUMNS, read_csv, write_manifest,
)


def main():
    parser = argparse.ArgumentParser(description="inspect x500 recorder data")
    parser.add_argument("--input", type=Path, default=ROOT / "results/multicopter_testbed/local_run")
    args = parser.parse_args()
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise SystemExit("matplotlib missing from project .venv") from exc

    directory = args.input
    figures = directory / "figures"
    figures.mkdir(parents=True, exist_ok=True)
    summary = {"status": "diagnostic_only", "comparison_performed": False}
    sources = (
        ("gazebo_truth.csv", TRUTH_COLUMNS, "sim_time_s", ("x_m", "y_m", "z_m"), "gazebo"),
        ("px4_local_position.csv", PX4_COLUMNS, "px4_time_s", ("enu_x_east_m", "enu_y_north_m", "enu_z_up_m"), "px4"),
    )
    produced = []
    for filename, columns, time_key, coords, label in sources:
        path = directory / filename
        if not path.exists():
            continue
        rows = read_csv(path, columns, time_key)
        t = [r[time_key] - rows[0][time_key] for r in rows]
        fig, axes = plt.subplots(3, 1, figsize=(9, 7), sharex=True)
        for idx, axis in enumerate(axes):
            axis.plot(t, [r[coords[idx]] for r in rows], linewidth=1.1)
            axis.set_ylabel(("east", "north", "up")[idx] + " (m)")
            axis.grid(alpha=0.3)
        axes[-1].set_xlabel("time since first sample in this source (s)")
        fig.suptitle(f"{label} x500 position — independent timeline")
        fig.tight_layout()
        dest = figures / f"{label}_position_timeline.png"
        fig.savefig(dest, dpi=150)
        plt.close(fig)
        summary[label] = {
            "samples": len(rows), "first_source_time_s": rows[0][time_key],
            "last_source_time_s": rows[-1][time_key],
        }
        produced.append(dest.name)
    if not produced:
        raise SystemExit(f"no telemetry files found in {directory}")
    summary["figures"] = produced
    summary["caution"] = "each timeline has its own zero; direct px4/gazebo position errors are not calculated"
    write_manifest(directory / "telemetry_diagnostics.json", **summary)
    print(f"generated {len(produced)} figure(s) in {figures}")


if __name__ == "__main__":
    main()
