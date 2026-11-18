"""Offline illustrative parameter-sensitivity and uncertainty experiment.

Run from repository root:
  python experiments/uncertainty_study.py --config configs/baseline.json \
      --uncertainty configs/uncertainty_study.json --output results/uncertainty_study

Only simulated fixed-time motion of an inert point mass is considered.
"""

import argparse
import csv
import hashlib
import json
import platform
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
from src.physics.uncertainty import (
    bootstrap_p95_interval, independent_uniform_draws, load_uncertainty_plan,
    nominal_parameters, one_at_a_time, percentile_summary,
    simulate_terminal_state,
)


def _write_csv(path, rows, fields):
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _save_fig(folder, name):
    plt.grid(alpha=0.25)
    plt.tight_layout()
    plt.savefig(folder / name, dpi=175)
    plt.close()


def _figures(figure_dir, oat_rows, sample_rows, stability_rows, diagnostics):
    ordered = list(reversed(oat_rows))
    plt.figure(figsize=(9, max(4.3, 0.52 * len(ordered) + 1.2)))
    plt.barh([r["parameter"] for r in ordered], [r["position_half_span_m"] for r in ordered])
    plt.xlabel("Half of lower-to-upper terminal 3D position separation (m)")
    plt.title("One-at-a-time screening under specified input ranges")
    _save_fig(figure_dir, "one_at_a_time_effects.png")

    deviations = np.array([r["terminal_3d_deviation_m"] for r in sample_rows])
    plt.figure(figsize=(8.3, 4.9))
    plt.hist(deviations, bins=max(8, min(22, int(np.sqrt(len(deviations)) * 1.4))), edgecolor="white")
    plt.axvline(float(np.quantile(deviations, .95)), linestyle="--", label="Simulated 95th percentile")
    plt.xlabel("3D terminal-position displacement from nominal (m)")
    plt.ylabel("Number of simulated parameter samples")
    plt.title("Joint independent-uniform input uncertainty")
    plt.legend()
    _save_fig(figure_dir, "terminal_deviation_distribution.png")

    px = np.array([r["terminal_x_m"] for r in sample_rows])
    py = np.array([r["terminal_y_m"] for r in sample_rows])
    plt.figure(figsize=(7.5, 5.6))
    plt.scatter(px, py, s=16, alpha=0.55, label="Monte Carlo endpoints")
    plt.scatter([sample_rows[0]["nominal_terminal_x_m"]],
                [sample_rows[0]["nominal_terminal_y_m"]], marker="x", s=110, linewidths=2,
                label="Nominal endpoint")
    plt.xlabel("Terminal east position x (m)")
    plt.ylabel("Terminal north position y (m)")
    plt.title("Horizontal projection at fixed elapsed time")
    plt.axis("equal")
    plt.legend()
    _save_fig(figure_dir, "terminal_horizontal_scatter.png")

    plt.figure(figsize=(8.0, 4.8))
    plt.plot([r["sample_count"] for r in stability_rows],
             [r["p95_terminal_3d_deviation_m"] for r in stability_rows], marker="o")
    plt.xlabel("Number of simulated draws (first n, fixed seed)")
    plt.ylabel("Estimated 95th percentile of 3D deviation (m)")
    plt.title("Finite-sample percentile stability check")
    _save_fig(figure_dir, "sampling_stability.png")

    plt.figure(figsize=(8.0, 4.8))
    plt.plot([r["sample_index"] for r in diagnostics],
             [r["coarse_vs_fine_terminal_position_difference_m"] for r in diagnostics],
             marker="o", linestyle="-")
    plt.xlabel("Selected parameter sample index")
    plt.ylabel("Terminal-position difference, coarse vs fine RK4 (m)")
    plt.title("Numerical-resolution diagnostic (not ground truth)")
    _save_fig(figure_dir, "numerical_resolution_check.png")


def run(config_path, uncertainty_path, output_path):
    config_path = Path(config_path)
    uncertainty_path = Path(uncertainty_path)
    output_path = Path(output_path)
    scenario = load_scenario(config_path)
    plan = load_uncertainty_plan(uncertainty_path, scenario)

    nominal = nominal_parameters(scenario)
    nominal_state = simulate_terminal_state(scenario, nominal, plan.integration_step_s)
    nominal_state_fine = simulate_terminal_state(scenario, nominal, plan.diagnostic_step_s)
    oat_rows = one_at_a_time(scenario, plan, nominal, nominal_state)
    draws = independent_uniform_draws(plan, nominal)

    samples = []
    for index, parameters in enumerate(draws, start=1):
        terminal = simulate_terminal_state(scenario, parameters, plan.integration_step_s)
        difference = terminal[:3] - nominal_state[:3]
        row = {"sample_index": index}
        row.update(parameters)
        row.update({
            "terminal_x_m": float(terminal[0]),
            "terminal_y_m": float(terminal[1]),
            "terminal_z_m": float(terminal[2]),
            "terminal_vx_m_s": float(terminal[3]),
            "terminal_vy_m_s": float(terminal[4]),
            "terminal_vz_m_s": float(terminal[5]),
            "nominal_terminal_x_m": float(nominal_state[0]),
            "nominal_terminal_y_m": float(nominal_state[1]),
            "nominal_terminal_z_m": float(nominal_state[2]),
            "delta_x_m": float(difference[0]),
            "delta_y_m": float(difference[1]),
            "delta_z_m": float(difference[2]),
            "terminal_3d_deviation_m": float(np.linalg.norm(difference)),
            "terminal_horizontal_deviation_m": float(np.linalg.norm(difference[:2])),
        })
        samples.append(row)

    stability_rows = []
    values = np.array([r["terminal_3d_deviation_m"] for r in samples], dtype=float)
    counts = sorted({n for n in (16, 32, 64, 128, 256, 512, plan.sample_count) if n <= plan.sample_count})
    for n in counts:
        stability_rows.append({
            "sample_count": n,
            "p95_terminal_3d_deviation_m": float(np.quantile(values[:n], .95)),
            "mean_terminal_3d_deviation_m": float(values[:n].mean()),
        })

    diagnostics = []
    for i in range(plan.diagnostic_sample_count):
        fine = simulate_terminal_state(scenario, draws[i], plan.diagnostic_step_s)
        coarse = np.array([
            samples[i]["terminal_x_m"], samples[i]["terminal_y_m"],
            samples[i]["terminal_z_m"], samples[i]["terminal_vx_m_s"],
            samples[i]["terminal_vy_m_s"], samples[i]["terminal_vz_m_s"],
        ])
        diagnostics.append({
            "sample_index": i + 1,
            "coarse_vs_fine_terminal_position_difference_m": float(np.linalg.norm(coarse[:3] - fine[:3])),
            "coarse_vs_fine_terminal_velocity_difference_m_s": float(np.linalg.norm(coarse[3:] - fine[3:])),
        })

    output_path.mkdir(parents=True, exist_ok=True)
    figure_dir = output_path / "figures"
    figure_dir.mkdir(exist_ok=True)
    _write_csv(output_path / "one_at_a_time.csv", oat_rows, list(oat_rows[0]))
    _write_csv(output_path / "monte_carlo_samples.csv", samples, list(samples[0]))
    _write_csv(output_path / "sampling_stability.csv", stability_rows, list(stability_rows[0]))
    _write_csv(output_path / "resolution_diagnostic.csv", diagnostics, list(diagnostics[0]))
    _figures(figure_dir, oat_rows, samples, stability_rows, diagnostics)

    p95_interval = bootstrap_p95_interval(values, plan.seed)
    terminal_xyz = np.array([[r["terminal_x_m"], r["terminal_y_m"], r["terminal_z_m"]]
                             for r in samples])
    resolution_diffs = np.array([r["coarse_vs_fine_terminal_position_difference_m"] for r in diagnostics])
    summary = {
        "study_id": plan.study_id,
        "status": "illustrative_offline_parameter_uncertainty_only",
        "physical_validation": False,
        "model": "constant-parameter ENU point-mass with quadratic relative-air-speed drag",
        "reference_condition": "nominal simulated state at the same fixed elapsed time",
        "statistical_model": "independent uniform uncertainty intervals; illustrative and uncalibrated",
        "nominal_state_at_fixed_time": [float(x) for x in nominal_state],
        "nominal_state_coarse_fine_position_difference_m": float(np.linalg.norm(nominal_state[:3] - nominal_state_fine[:3])),
        "input_scenario_sha256": hashlib.sha256(config_path.read_bytes()).hexdigest(),
        "uncertainty_config_sha256": hashlib.sha256(uncertainty_path.read_bytes()).hexdigest(),
        "random_seed": plan.seed,
        "monte_carlo_sample_count": plan.sample_count,
        "sampling_assumption": "independent scalar uniform draws, fixed within each trajectory",
        "integration_method": "rk4",
        "integration_step_s": plan.integration_step_s,
        "diagnostic_step_s": plan.diagnostic_step_s,
        "diagnostic_sample_count": plan.diagnostic_sample_count,
        "uncertainty_half_widths": {name: width for name, width in plan.parameters},
        "nominal_parameter_values": nominal,
        "one_at_a_time_ranked": oat_rows,
        "terminal_3d_deviation_statistics_m": percentile_summary(values),
        "terminal_horizontal_deviation_statistics_m": percentile_summary(
            [r["terminal_horizontal_deviation_m"] for r in samples]),
        "terminal_xyz_statistics_m": {
            name: percentile_summary(terminal_xyz[:, i])
            for i, name in enumerate(("x", "y", "z"))
        },
        "bootstrap_p95_estimator_interval_95pct_m": list(p95_interval),
        "bootstrap_interval_qualification": "Monte Carlo quantile-estimator resampling interval only, conditional on the chosen illustrative input distributions; not a physical coverage guarantee.",
        "numerical_resolution_check": {
            "comparison": "same parameter draw under RK4 at two step sizes",
            "maximum_terminal_position_difference_m": float(resolution_diffs.max()),
            "median_terminal_position_difference_m": float(np.median(resolution_diffs)),
            "ratio_max_numerical_difference_to_p95_input_deviation": float(resolution_diffs.max() / np.quantile(values, .95)) if np.quantile(values, .95) > 0 else None,
        },
        "python_version": platform.python_version(),
        "numpy_version": np.__version__,
        "limitations": [
            "synthetic laboratory-scale scenario, not measured air-drop data",
            "uncertainty widths are hypotheses, not sensor calibration or measured error statistics",
            "parameter uncertainties assume independence and uniform distributions",
            "parameters are fixed in time, so gusts and temporal correlations are excluded",
            "3D deviations are from a nominal simulation, not real-world prediction errors",
            "bootstrap intervals describe estimator variability under assumed distributions, not physical reliability",
            "the one-at-a-time ranking depends on chosen interval widths and excludes interactions",
            "numerical refinement check compares numerical approximations rather than physical truth",
            "no ground impact, target location, release event, or operational control",
        ],
    }
    (output_path / "uncertainty_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def main():
    parser = argparse.ArgumentParser(description="Illustrative offline uncertainty and sensitivity study")
    parser.add_argument("--config", type=Path, default=ROOT / "configs" / "baseline.json")
    parser.add_argument("--uncertainty", type=Path, default=ROOT / "configs" / "uncertainty_study.json")
    parser.add_argument("--output", type=Path, default=ROOT / "results" / "uncertainty_study")
    args = parser.parse_args()
    summary = run(args.config, args.uncertainty, args.output)
    stats = summary["terminal_3d_deviation_statistics_m"]
    print(f"Study: {summary['study_id']}")
    print(f"Simulated draws: {summary['monte_carlo_sample_count']}")
    print(f"3D deviation from nominal, p95: {stats['p95']:.6f} m (illustrative)")
    print(f"Largest OAT response: {summary['one_at_a_time_ranked'][0]['parameter']}")
    print(f"Artifacts: {args.output}")


if __name__ == "__main__":
    main()
