"""Reproducible offline verification experiment with optional JSON configuration."""

import argparse
import csv
import json
import sys
from pathlib import Path
from time import perf_counter

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.physics import Body, analytic_vacuum, model_rhs, integrate, load_scenario, mechanical_energy

def run(config_path: Path, output: Path) -> dict:
    scenario = load_scenario(config_path)
    output.mkdir(parents=True, exist_ok=True)
    figures = output / "figures"
    figures.mkdir(parents=True, exist_ok=True)

    initial = np.array(scenario.initial_state, dtype=float)
    duration = scenario.duration_s
    body = scenario.body
    atmosphere = scenario.atmosphere
    no_drag = Body(body.mass_kg, body.reference_area_m2, 0.0)

    def rhs_drag(t, y):
        return model_rhs(t, y, body, atmosphere)

    def rhs_vacuum(t, y):
        return model_rhs(t, y, no_drag, atmosphere)

    base_step = scenario.maximum_step_s
    exact = analytic_vacuum(initial[:3], initial[3:], np.linspace(0, duration, int(np.ceil(duration / base_step)) + 1), atmosphere.gravity_m_s2)
    euler_vacuum = integrate(rhs_vacuum, initial, duration, base_step, method="euler")
    rk4_vacuum = integrate(rhs_vacuum, initial, duration, base_step, method="rk4")
    drag_traj = integrate(rhs_drag, initial, duration, base_step, method="rk4")
    fine = integrate(rhs_drag, initial, duration, scenario.reference_step_s, method="rk4")

    vacuum_euler_end_error = float(np.linalg.norm(euler_vacuum.positions[-1] - exact.positions[-1]))
    vacuum_rk4_end_error = float(np.linalg.norm(rk4_vacuum.positions[-1] - exact.positions[-1]))
    drag_vs_vacuum_end_difference = float(np.linalg.norm(drag_traj.positions[-1] - exact.positions[-1]))

    rows = []
    for method in ("euler", "rk4"):
        for step in scenario.convergence_steps_s:
            observations = []
            for _ in range(scenario.timing_repetitions):
                start = perf_counter()
                result = integrate(rhs_drag, initial, duration, step, method=method)
                observations.append((perf_counter() - start) * 1000.0)
            rows.append({
                "method": method,
                "max_step_s": step,
                "final_position_difference_vs_fine_rk4_m": float(np.linalg.norm(result.positions[-1] - fine.positions[-1])),
                "final_velocity_difference_vs_fine_rk4_m_s": float(np.linalg.norm(result.velocities[-1] - fine.velocities[-1])),
                "median_runtime_ms": float(np.median(observations)),
            })

    with (output / "convergence.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    energy = np.array([mechanical_energy(state, body, atmosphere) for state in drag_traj.states])
    summary = {
        "status": "offline_model_verification_only",
        "scenario_id": scenario.scenario_id,
        "scenario_description": scenario.description,
        "config": {"initial_state": list(scenario.initial_state), "duration_s": duration,
                   "body": vars(body), "atmosphere": vars(atmosphere),
                   "numerics": {"maximum_step_s": base_step,
                                "reference_step_s": scenario.reference_step_s,
                                "convergence_steps_s": list(scenario.convergence_steps_s),
                                "timing_repetitions": scenario.timing_repetitions}},
        "vacuum_euler_position_error_vs_analytic_m": vacuum_euler_end_error,
        "vacuum_rk4_position_error_vs_analytic_m": vacuum_rk4_end_error,
        "drag_vs_vacuum_endpoint_difference_m": drag_vs_vacuum_end_difference,
        "drag_run_energy_initial_j": float(energy[0]),
        "drag_run_energy_final_j": float(energy[-1]),
        "benchmark_reference": "fine RK4 integration, not an independent physical observation",
        "limitations": ["no independent field measurements", "uniform atmosphere",
                        "constant Cd and area", "no rotational dynamics", "no UAV control or targeting"],
    }
    (output / "experiment_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    plt.figure(figsize=(7.4, 4.5))
    plt.plot(exact.times, exact.positions[:, 2], label="gravity-only: analytical", linewidth=2.3)
    plt.plot(euler_vacuum.times, euler_vacuum.positions[:, 2], ":", label=f"gravity-only: Euler, dt≤{base_step:g}")
    plt.plot(drag_traj.times, drag_traj.positions[:, 2], "--", label=f"quadratic drag: RK4, dt≤{base_step:g}")
    plt.xlabel("Time (s)")
    plt.ylabel("Vertical position z (m)")
    plt.title("Model-assumption comparison: offline illustrative case")
    plt.grid(alpha=0.25)
    plt.legend()
    plt.tight_layout()
    plt.savefig(figures / "model_comparison.png", dpi=165)
    plt.close()

    plt.figure(figsize=(7.4, 4.5))
    for method, marker in (("euler", "o"), ("rk4", "s")):
        series = [r for r in rows if r["method"] == method]
        plt.loglog([r["max_step_s"] for r in series],
                   [r["final_position_difference_vs_fine_rk4_m"] for r in series],
                   marker=marker, label=method.upper())
    plt.xlabel("Maximum integration step (s)")
    plt.ylabel("Final-position difference from fine RK4 (m)")
    plt.title("Numerical refinement using identical physical assumptions")
    plt.grid(True, alpha=0.25, which="both")
    plt.legend()
    plt.tight_layout()
    plt.savefig(figures / "numerical_convergence.png", dpi=165)
    plt.close()

    plt.figure(figsize=(7.4, 4.5))
    plt.plot(drag_traj.times, energy)
    plt.xlabel("Time (s)")
    plt.ylabel("Mechanical energy K + U (J)")
    plt.title("Consistency check: dissipative drag in still air")
    plt.grid(alpha=0.25)
    plt.tight_layout()
    plt.savefig(figures / "mechanical_energy.png", dpi=165)
    plt.close()

    return summary


def main():
    parser = argparse.ArgumentParser(description="Offline dynamics verification experiment")
    parser.add_argument("--config", type=Path, default=ROOT / "configs/baseline.json", help="scenario JSON path")
    parser.add_argument("--output", type=Path, default=ROOT / "results", help="output directory")
    args = parser.parse_args()
    summary = run(args.config, args.output)
    print(f"Scenario: {summary['scenario_id']}")
    print(f"Euler endpoint error vs analytical gravity case: {summary['vacuum_euler_position_error_vs_analytic_m']:.8f} m")
    print(f"RK4 endpoint error vs analytical gravity case:   {summary['vacuum_rk4_position_error_vs_analytic_m']:.3e} m")
    print(f"Drag vs gravity-only model endpoint difference: {summary['drag_vs_vacuum_endpoint_difference_m']:.6f} m")
    print(f"Results saved under: {args.output}")


if __name__ == "__main__":
    main()
