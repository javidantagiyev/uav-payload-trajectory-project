"""evaluate a simulated trajectory against externally provided time series."""

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.physics import Body, integrate, load_scenario, model_rhs
from src.physics.validation import compare_trajectory, load_observations


def run(scenario_path, observation_path, metadata_path, output_path, model="gravity_only", step_s=0.01):
    if model not in {"gravity_only", "quadratic_drag"}:
        raise ValueError("model must be gravity_only or quadratic_drag")
    scenario = load_scenario(scenario_path)
    observations = load_observations(observation_path, metadata_path)
    body = scenario.body if model == "quadratic_drag" else Body(
        scenario.body.mass_kg, scenario.body.reference_area_m2, 0.0)
    rhs = lambda t, state: model_rhs(t, state, body, scenario.atmosphere)
    trajectory = integrate(rhs, scenario.initial_state, scenario.duration_s, step_s, "rk4")
    metrics, rows = compare_trajectory(trajectory, observations)

    output = Path(output_path)
    output.mkdir(parents=True, exist_ok=True)
    figures = output / "figures"
    figures.mkdir(exist_ok=True)
    with (output / "observation_residuals.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    plt.figure(figsize=(8, 4.7))
    plt.plot([r["time_s"] for r in rows], [r["observed_z_m"] for r in rows], "o", label="reported observations")
    plt.plot(trajectory.times, trajectory.positions[:, 2], label="modeled z")
    plt.xlabel("elapsed time (s)")
    plt.ylabel("vertical position z (m)")
    plt.title("observation comparison (check provenance)")
    plt.legend()
    plt.grid(alpha=0.25)
    plt.tight_layout()
    plt.savefig(figures / "observation_comparison.png", dpi=175)
    plt.close()

    plt.figure(figsize=(8, 4.7))
    plt.plot([r["time_s"] for r in rows], [r["position_error_m"] for r in rows], "o-")
    plt.xlabel("elapsed time (s)")
    plt.ylabel("3d model-to-observation difference (m)")
    plt.title("observation residual magnitude (check provenance)")
    plt.grid(alpha=0.25)
    plt.tight_layout()
    plt.savefig(figures / "observation_residuals.png", dpi=175)
    plt.close()

    summary = {
        "dataset_id": observations.metadata["dataset_id"],
        "declared_provenance": observations.metadata["provenance"],
        "declared_source": observations.metadata["source"],
        "provenance_independently_verified": False,
        "model": model,
        "method": "rk4",
        "step_s": float(step_s),
        "metrics": metrics,
        "observation_sha256": hashlib.sha256(Path(observation_path).read_bytes()).hexdigest(),
        "metadata_sha256": hashlib.sha256(Path(metadata_path).read_bytes()).hexdigest(),
        "scenario_sha256": hashlib.sha256(Path(scenario_path).read_bytes()).hexdigest(),
        "qualifications": [
            "the input dataset may be synthetic; review declared provenance",
            "the calculation compares reported observations and predictions at identical times",
            "linear interpolation of numerical states may contribute small discrepancies",
            "observations must use the same initial reference frame, units, and clock origin",
            "simulation agreement alone is not physical model validation",
            "no fitting, calibration, release optimization, or vehicle control is performed",
        ],
    }
    (output / "evaluation_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def main():
    parser = argparse.ArgumentParser(description="trajectory observation evaluation")
    parser.add_argument("--scenario", type=Path, default=ROOT / "configs/baseline.json")
    parser.add_argument("--observations", type=Path, default=ROOT / "data/examples/synthetic_observations.csv")
    parser.add_argument("--metadata", type=Path, default=ROOT / "data/examples/synthetic_observations.json")
    parser.add_argument("--output", type=Path, default=ROOT / "results/observation_example")
    parser.add_argument("--model", choices=("gravity_only", "quadratic_drag"), default="gravity_only")
    parser.add_argument("--step", type=float, default=0.01)
    args = parser.parse_args()
    summary = run(args.scenario, args.observations, args.metadata, args.output, args.model, args.step)
    print(json.dumps({"dataset": summary["dataset_id"], "provenance": summary["declared_provenance"],
                      "position_rmse_m": summary["metrics"]["position_rmse_m"]}, indent=2))


if __name__ == "__main__":
    main()
