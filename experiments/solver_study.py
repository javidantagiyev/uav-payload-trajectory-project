"""Controlled offline Euler/RK4 comparison for gravity-only and quadratic-drag models.

Run from the repository root:
    python experiments/solver_study.py --config configs/baseline.json \
        --output results/solver_study

No physical measurements, aiming, release calculations, or vehicle interfaces.
"""

import argparse
import csv
import hashlib
import json
import platform
import sys
from dataclasses import asdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.physics import Body, analytic_vacuum, integrate, load_scenario, model_rhs
from src.physics.benchmarking import (
    measured_integration,
    observed_convergence_order,
    terminal_state_difference,
)


MODELS = ("gravity_only", "quadratic_drag")
METHODS = ("euler", "rk4")


def _write_csv(path, rows, fields):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _figure_path(figures, filename):
    plt.grid(alpha=0.27, which="both")
    plt.tight_layout()
    plt.savefig(figures / filename, dpi=175)
    plt.close()


def _plot_trajectory(figures, model, reference, curves, shown_step):
    plt.figure(figsize=(7.9, 4.8))
    label = "Analytical gravity solution" if model == "gravity_only" else "Fine-step RK4 reference (numerical)"
    plt.plot(reference.times, reference.positions[:, 2], label=label, linewidth=2.6)
    for method, symbol in (("euler", "--"), ("rk4", ":")):
        trajectory = curves[model][method]
        plt.plot(trajectory.times, trajectory.positions[:, 2], symbol,
                 linewidth=2, label=f"{method.upper()} (maximum dt={shown_step:g} s)")
    plt.xlabel("Elapsed time (s)")
    plt.ylabel("Vertical position z (m)")
    plt.title("Gravity-only numerical comparison" if model == "gravity_only" else
              "Quadratic-drag numerical comparison")
    plt.legend()
    _figure_path(figures, model + "_trajectories.png")


def _plot_convergence(figures, rows, model):
    plt.figure(figsize=(7.8, 4.8))
    for method, marker in (("euler", "o"), ("rk4", "s")):
        records = sorted((r for r in rows if r["physical_model"] == model and r["method"] == method),
                         key=lambda r: r["actual_step_s"])
        xs = [r["actual_step_s"] for r in records]
        ys = [max(r["terminal_position_difference_m"], 1e-16) for r in records]
        plt.loglog(xs, ys, marker=marker, label=method.upper(), linewidth=1.8)
    plt.xlabel("Actual integration step (s)")
    plt.ylabel("Terminal position difference (m)")
    plt.title("Gravity-only: analytical reference" if model == "gravity_only" else
              "Quadratic drag: fine-step RK4 reference")
    plt.legend(fontsize="small")
    if model == "gravity_only":
        plt.text(0.035, 0.40, "RK4 reaches floating-point roundoff;\nits fitted slope is not meaningful.",
                 transform=plt.gca().transAxes, fontsize=9, color="#555555")
    _figure_path(figures, model + "_convergence.png")


def _plot_cost(figures, rows):
    plt.figure(figsize=(8.3, 5.0))
    for model in MODELS:
        for method, marker in (("euler", "o"), ("rk4", "s")):
            records = sorted((r for r in rows if r["physical_model"] == model and r["method"] == method),
                             key=lambda r: r["actual_step_s"], reverse=True)
            x = [r["median_wall_ms"] for r in records]
            y = [max(r["terminal_position_difference_m"], 1e-16) for r in records]
            plt.semilogy(x, y, marker=marker, linewidth=1.6,
                         label=f"{model.replace('_',' ')} — {method.upper()}")
    plt.xlabel("Median complete integration runtime (ms; machine dependent)")
    plt.ylabel("Terminal position difference (m; reference dependent)")
    plt.title("Numerical accuracy versus computational cost")
    plt.legend(fontsize="small")
    _figure_path(figures, "accuracy_vs_runtime.png")


def run(config_path, output_path):
    config_path = Path(config_path)
    output = Path(output_path)
    scenario = load_scenario(config_path)
    if len(set(scenario.convergence_steps_s)) != len(scenario.convergence_steps_s):
        raise ValueError("convergence step sizes must be distinct")
    output.mkdir(parents=True, exist_ok=True)
    figures = output / "figures"
    figures.mkdir(exist_ok=True)

    initial = np.asarray(scenario.initial_state, dtype=float)
    atmosphere = scenario.atmosphere
    bodies = {
        "gravity_only": Body(scenario.body.mass_kg, scenario.body.reference_area_m2, 0.0),
        "quadratic_drag": scenario.body,
    }
    rhs = {
        model: (lambda t, y, body=body: model_rhs(t, y, body, atmosphere))
        for model, body in bodies.items()
    }

    fine_drag = integrate(rhs["quadratic_drag"], initial, scenario.duration_s,
                          scenario.reference_step_s, method="rk4")
    exact_end = analytic_vacuum(initial[:3], initial[3:],
                                np.array([0.0, scenario.duration_s]), atmosphere.gravity_m_s2)
    references = {
        "gravity_only": exact_end.states[-1],
        "quadratic_drag": fine_drag.states[-1],
    }
    coarse_step = max(scenario.convergence_steps_s)
    curves = {model: {} for model in MODELS}
    rows = []
    for model in MODELS:
        for method in METHODS:
            for requested_step in sorted(scenario.convergence_steps_s, reverse=True):
                traj, ms, nfev, actual_step = measured_integration(
                    rhs[model], initial, scenario.duration_s,
                    requested_step, method, scenario.timing_repetitions)
                pos_err, vel_err = terminal_state_difference(traj, references[model])
                rows.append({
                    "physical_model": model,
                    "method": method,
                    "requested_max_step_s": float(requested_step),
                    "actual_step_s": actual_step,
                    "steps": len(traj.times) - 1,
                    "rhs_evaluations": nfev,
                    "terminal_position_difference_m": pos_err,
                    "terminal_velocity_difference_m_s": vel_err,
                    "median_wall_ms": ms,
                    "reference_type": "analytical_gravity" if model == "gravity_only" else "fine_step_rk4_drag",
                })
                if requested_step == coarse_step:
                    curves[model][method] = traj

    orders = []
    for model in MODELS:
        for method in METHODS:
            series = [r for r in rows if r["physical_model"] == model and r["method"] == method]
            observed = observed_convergence_order(
                [r["actual_step_s"] for r in series],
                [r["terminal_position_difference_m"] for r in series],
            )
            orders.append({
                "physical_model": model,
                "method": method,
                "theoretical_global_order": 1 if method == "euler" else 4,
                "observed_terminal_position_order": observed,
                "interpretation": "roundoff_or_reference_floor" if observed is None else "measured_slope",
            })

    _write_csv(output / "solver_comparison.csv", rows, list(rows[0]))
    _write_csv(output / "observed_orders.csv", orders, list(orders[0]))

    gravity_dense = analytic_vacuum(initial[:3], initial[3:], fine_drag.times,
                                    atmosphere.gravity_m_s2)
    _plot_trajectory(figures, "gravity_only", gravity_dense, curves, coarse_step)
    _plot_trajectory(figures, "quadratic_drag", fine_drag, curves, coarse_step)
    for model in MODELS:
        _plot_convergence(figures, rows, model)
    _plot_cost(figures, rows)

    model_difference = np.linalg.norm(gravity_dense.positions - fine_drag.positions, axis=1)
    plt.figure(figsize=(7.9, 4.8))
    plt.plot(fine_drag.times, model_difference, linewidth=2.2)
    plt.xlabel("Elapsed time (s)")
    plt.ylabel("3D position difference (m)")
    plt.title("Difference between assumed gravity-only and drag models")
    _figure_path(figures, "model_assumption_difference.png")

    summary = {
        "status": "offline_numerical_verification_only",
        "scenario_id": scenario.scenario_id,
        "description": "Controlled two-model by two-solver numerical comparison",
        "model_labels": list(MODELS),
        "solver_labels": list(METHODS),
        "config_path_for_run": str(config_path),
        "config_sha256": hashlib.sha256(config_path.read_bytes()).hexdigest(),
        "input_parameters": {
            "initial_state": list(scenario.initial_state),
            "duration_s": scenario.duration_s,
            "body": asdict(scenario.body),
            "atmosphere": asdict(scenario.atmosphere),
            "convergence_steps_s": list(scenario.convergence_steps_s),
            "reference_step_s": scenario.reference_step_s,
            "timing_repetitions": scenario.timing_repetitions,
        },
        "references": {
            "gravity_only": "exact analytical constant-gravity state at final time",
            "quadratic_drag": "RK4 numerical state at final time, finer fixed step; not ground truth",
        },
        "drag_minus_gravity_model_terminal_position_difference_m": float(model_difference[-1]),
        "convergence_estimates": orders,
        "runtime_caveat": "Wall-clock timing includes Python, trajectory storage and allocation; measurements depend on hardware and load.",
        "roundoff_caveat": "Near-zero numerical differences and their fitted slopes are not interpretable as convergence orders.",
        "physical_validation": False,
        "python_version": platform.python_version(),
        "numpy_version": np.__version__,
        "limitations": ["synthetic short-duration inert-body case", "constant atmosphere and coefficients",
                        "no independent observations", "no event/intersection prediction", "no operational guidance"],
    }
    (output / "study_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def main():
    parser = argparse.ArgumentParser(description="Compare numerical methods under controlled physical assumptions")
    parser.add_argument("--config", type=Path, default=ROOT / "configs" / "baseline.json")
    parser.add_argument("--output", type=Path, default=ROOT / "results" / "solver_study")
    args = parser.parse_args()
    summary = run(args.config, args.output)
    print(f"Scenario: {summary['scenario_id']}")
    for record in summary["convergence_estimates"]:
        value = record["observed_terminal_position_order"]
        label = "roundoff-limited" if value is None else f"{value:.3f}"
        print(f"{record['physical_model']:15s} {record['method']:5s} observed order: {label}")
    print(f"Files generated: {args.output}")


if __name__ == "__main__":
    main()
