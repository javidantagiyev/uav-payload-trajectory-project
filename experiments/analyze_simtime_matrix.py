"""analyze verified 6f simulation-time recordings and produce diagnostic figures."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.physics.simtime_analysis import summarize_study
from src.physics.simtime_figures import plot_case, plot_overview


def main():
    p = argparse.ArgumentParser(description="analyze 6f simulation-time experiment runs")
    p.add_argument("--worlds", type=Path,
                   default=ROOT / "results/environmental_testbed/local_run/worlds")
    p.add_argument("--input", type=Path,
                   default=ROOT / "results/environmental_testbed/simtime_6f")
    p.add_argument("--output", type=Path)
    args = p.parse_args()
    output = args.output or args.input / "analysis"
    report = summarize_study(args.worlds / "scenario_manifest.json", args.input / "runs", output)
    images = []
    for row in report["cases"]:
        if row["status"] == "evaluated":
            images += plot_case(row, output / "figures" / row["id"])
    images += plot_overview(report, output / "figures")
    print(json.dumps({"evaluated_cases": report["evaluated_cases"],
                      "verified_runs": report["verified_runs"],
                      "invalid_runs": report["invalid_runs"],
                      "figures_created": len(images),
                      "output": str(output)}, indent=2))
    if not report["verified_runs"] or report["invalid_runs"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
