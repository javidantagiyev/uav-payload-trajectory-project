"""generate gazebo worlds for controlled environmental screening."""

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.physics.environmental_matrix import prepare_worlds



def main():
    p = argparse.ArgumentParser()
    p.add_argument("--config", type=Path, default=ROOT / "configs/environment_matrix.json")
    p.add_argument("--template", type=Path, default=ROOT / "sim/gazebo/worlds/rigid_body_lab.sdf")
    p.add_argument("--output", type=Path, default=ROOT / "results/environmental_testbed/local_run/worlds")
    args = p.parse_args()
    manifest = prepare_worlds(args.config, args.template, args.output)
    print(json.dumps({"case_count": len(manifest["cases"]), "world_dir": str(args.output),
                      "status": manifest["status"]}, indent=2))


if __name__ == "__main__":
    main()
