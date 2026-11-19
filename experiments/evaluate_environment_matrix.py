"""evaluate environmental gazebo runs with explicit missing-run status."""

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.physics.environmental_evaluation import evaluate_matrix

BASE = ROOT / "results/environmental_testbed/local_run"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--manifest", type=Path, default=BASE / "worlds/scenario_manifest.json")
    p.add_argument("--runs", type=Path, default=BASE / "runs")
    p.add_argument("--output", type=Path, default=BASE)
    args = p.parse_args()
    result = evaluate_matrix(args.manifest, args.runs, args.output)
    print(json.dumps({"evaluated": result["evaluated_count"],
                      "total": result["experiment_count"], "output": str(args.output)}, indent=2))


if __name__ == "__main__":
    main()
