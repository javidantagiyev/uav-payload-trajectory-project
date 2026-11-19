"""reproducible fixed-time scenario and prior sensitivity study."""

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.physics import load_scenario
from src.physics.robustness import apply_variant, draw_uncertain_parameters, load_robustness_plan
from src.physics.uncertainty import load_uncertainty_plan, nominal_parameters, simulate_terminal_state


def _csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _figure(path):
    plt.grid(alpha=0.25)
    plt.tight_layout()
    plt.savefig(path, dpi=170)
    plt.close()


def run(baseline_path, uncertainty_path, robustness_path, output_path):
    baseline_path = Path(baseline_path)
    uncertainty_path = Path(uncertainty_path)
    robustness_path = Path(robustness_path)
    output = Path(output_path)
    baseline = load_scenario(baseline_path)
    uncertain = load_uncertainty_plan(uncertainty_path, baseline)
    plan = load_robustness_plan(robustness_path)
    if baseline.duration_s / plan.fine_step_s > 500_000:
        raise ValueError("robustness study requests too many numerical steps")

    nominal_parameters_baseline = nominal_parameters(baseline)
    initial_reference = simulate_terminal_state(baseline, nominal_parameters_baseline, plan.fine_step_s)
    scenarios = []
    for variant_id, description, overrides in plan.variants:
        scenario = apply_variant(baseline, overrides)
        params = nominal_parameters(scenario)
        coarse = simulate_terminal_state(scenario, params, plan.step_s)
        fine = simulate_terminal_state(scenario, params, plan.fine_step_s)
        difference = fine[:3] - initial_reference[:3]
        scenarios.append({
            "scenario_id": variant_id,
            "description": description,
            "overrides_json": json.dumps(overrides, sort_keys=True),
            "state_x_m": float(fine[0]),
            "state_y_m": float(fine[1]),
            "state_z_m": float(fine[2]),
            "position_difference_from_nominal_m": float(np.linalg.norm(difference)),
            "coarse_fine_position_difference_m": float(np.linalg.norm(coarse[:3] - fine[:3])),
        })

    distribution_rows = []
    draws_rows = []
    nominal_coarse = simulate_terminal_state(baseline, nominal_parameters_baseline, plan.step_s)
    for dist in plan.distributions:
        draws = draw_uncertain_parameters(plan, uncertain, baseline, dist)
        values = []
        for index, params in enumerate(draws, 1):
            state = simulate_terminal_state(baseline, params, plan.step_s)
            deviation = float(np.linalg.norm(state[:3] - nominal_coarse[:3]))
            values.append(deviation)
            draws_rows.append({
                "distribution": dist,
                "draw_index": index,
                "fixed_time_position_deviation_m": deviation,
            })
        values = np.asarray(values)
        distribution_rows.append({
            "distribution": dist,
            "sample_count": len(values),
            "mean_deviation_m": float(values.mean()),
            "p50_deviation_m": float(np.quantile(values, 0.50)),
            "p95_deviation_m": float(np.quantile(values, 0.95)),
            "maximum_sample_deviation_m": float(values.max()),
        })

    output.mkdir(parents=True, exist_ok=True)
    figs = output / "figures"
    figs.mkdir(exist_ok=True)
    _csv(output / "scenario_comparison.csv", scenarios)
    _csv(output / "distribution_comparison.csv", distribution_rows)
    _csv(output / "uncertainty_draws.csv", draws_rows)

    plt.figure(figsize=(9, 5))
    plt.bar([row["scenario_id"] for row in scenarios],
            [row["position_difference_from_nominal_m"] for row in scenarios])
    plt.xticks(rotation=22, ha="right")
    plt.ylabel("3d position difference from baseline (m)")
    plt.title("fixed-time comparison of assumed physical conditions")
    _figure(figs / "scenario_differences.png")

    plt.figure(figsize=(8, 5))
    names = [r["distribution"] for r in distribution_rows]
    positions = np.arange(len(names))
    plt.bar(positions - 0.17, [r["p50_deviation_m"] for r in distribution_rows], 0.34, label="median")
    plt.bar(positions + 0.17, [r["p95_deviation_m"] for r in distribution_rows], 0.34, label="95th percentile")
    plt.xticks(positions, names)
    plt.ylabel("3d deviation from nominal simulation (m)")
    plt.title("uncertainty prior sensitivity, identical parameter bounds")
    plt.legend()
    _figure(figs / "distribution_sensitivity.png")

    plt.figure(figsize=(8, 5))
    for dist in plan.distributions:
        numbers = sorted(r["fixed_time_position_deviation_m"] for r in draws_rows if r["distribution"] == dist)
        plt.plot(numbers, np.arange(1, len(numbers) + 1) / len(numbers), label=dist)
    plt.xlabel("3d deviation from nominal simulation (m)")
    plt.ylabel("empirical cumulative proportion")
    plt.title("illustrative uncertainty distributions at fixed time")
    plt.legend()
    _figure(figs / "distribution_ecdf.png")

    summary = {
        "study_id": plan.study_id,
        "status": "simulation_only",
        "physical_validation": False,
        "endpoint_definition": "state at fixed elapsed time, not ground impact",
        "scenario_type": "illustrative laboratory-scale inert point mass",
        "baseline_sha256": hashlib.sha256(baseline_path.read_bytes()).hexdigest(),
        "robustness_plan_sha256": hashlib.sha256(robustness_path.read_bytes()).hexdigest(),
        "uncertainty_plan_sha256": hashlib.sha256(uncertainty_path.read_bytes()).hexdigest(),
        "seed": plan.seed,
        "sample_count_per_distribution": plan.sample_count,
        "integration_method": "rk4",
        "step_s": plan.step_s,
        "fine_step_s": plan.fine_step_s,
        "scenario_results": scenarios,
        "distribution_results": distribution_rows,
        "limitations": [
            "all scenarios use hypothetical input assumptions",
            "model comparisons are not independently observed motion",
            "uncertain inputs are constant within each simulation",
            "prior comparisons hold interval limits fixed but change distribution shapes",
            "independent parameter sampling ignores correlations",
            "finite-sample percentiles are descriptive and not field reliability guarantees",
            "no vehicle control, release event, or target optimization",
        ],
    }
    (output / "robustness_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def main():
    parser = argparse.ArgumentParser(description="offline scenario and uncertainty-prior study")
    parser.add_argument("--baseline", type=Path, default=ROOT / "configs/baseline.json")
    parser.add_argument("--uncertainty", type=Path, default=ROOT / "configs/uncertainty_study.json")
    parser.add_argument("--plan", type=Path, default=ROOT / "configs/robustness_study.json")
    parser.add_argument("--output", type=Path, default=ROOT / "results/robustness_study")
    args = parser.parse_args()
    summary = run(args.baseline, args.uncertainty, args.plan, args.output)
    print(json.dumps({"study_id": summary["study_id"], "status": summary["status"],
                      "scenario_count": len(summary["scenario_results"]),
                      "distributions": len(summary["distribution_results"])}, indent=2))


if __name__ == "__main__":
    main()
