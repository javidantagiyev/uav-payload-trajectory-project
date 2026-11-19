
"""Compare Euler and RK4 landing accuracy and atmosphere models (SI units)."""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from src.physics.gravity import G
from src.physics.ballistic_model import state_derivative
from src.physics.simulation import (
    simulate,
    landing_point,
    flight_time
)
from src.physics.atmosphere import density_function
from src.physics.payload import PRESETS

OUTPUT_DIR = Path("results/method_comparison")

RELEASE_HEIGHT = 500.0
UAV_SPEED = 15.0
INITIAL_STATE = (0.0, 0.0, RELEASE_HEIGHT, UAV_SPEED, 0.0, 0.0)

# Ground elevation of Baku above sea level.
GROUND_ALTITUDE = -28.0
SEA_LEVEL_DENSITY = 1.225

STEP_SIZES = [0.2, 0.1, 0.05, 0.02, 0.01, 0.005]
REFERENCE_STEP = 0.0005


def make_model(payload, density):
    """Return f(t, state) for a payload and a density value or function."""
    def model(t, state):
        return state_derivative(
            t,
            state,
            mass=payload["mass"],
            density=density,
            drag_coefficient=payload["drag_coefficient"],
            area=payload["area"]
        )

    return model


def vacuum_landing():
    """Return the analytical gravity-only landing (x, flight_time)."""
    t = (2 * RELEASE_HEIGHT / G) ** 0.5

    return UAV_SPEED * t, t


def landing_error(states, reference_states):
    """Return the horizontal distance between two landing points in meters."""
    x, y = landing_point(states)
    x_ref, y_ref = landing_point(reference_states)

    return ((x - x_ref) ** 2 + (y - y_ref) ** 2) ** 0.5


def convergence_rows(name, model):
    """Run Euler and RK4 for every step size against a fine RK4 reference."""
    _, reference_states = simulate(model, INITIAL_STATE, step_size=REFERENCE_STEP)

    rows = []

    for method in ["euler", "rk4"]:
        for step_size in STEP_SIZES:
            times, states = simulate(
                model,
                INITIAL_STATE,
                step_size=step_size,
                method=method
            )

            x, y = landing_point(states)

            rows.append({
                "payload": name,
                "method": method,
                "step_size": step_size,
                "landing_x": x,
                "landing_y": y,
                "flight_time": flight_time(times),
                "landing_error": landing_error(states, reference_states)
            })

    return rows


def plot_convergence(table):
    """Save a log-log plot of landing error against step size."""
    plt.figure(figsize=(7, 5))

    for (name, method), group in table.groupby(["payload", "method"]):
        plt.loglog(
            group["step_size"],
            group["landing_error"],
            marker="o",
            label=f"{name} {method}"
        )

    plt.xlabel("Step size (s)")
    plt.ylabel("Landing error vs RK4 reference (m)")
    plt.title("Landing point convergence, 500 m release")
    plt.grid(alpha=0.3, which="both")
    plt.legend()
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "landing_convergence.png", dpi=150)
    plt.close()


def plot_trajectories(trajectories):
    """Save the side view x-z of every trajectory."""
    plt.figure(figsize=(8, 5))

    for label, states in trajectories.items():
        plt.plot(
            [state[0] for state in states],
            [state[2] for state in states],
            label=label
        )

    plt.xlabel("East x (m)")
    plt.ylabel("Height above ground z (m)")
    plt.title("Side view: vacuum, constant density and ISA")
    plt.grid(alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "trajectories.png", dpi=150)
    plt.close()


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    isa = density_function(GROUND_ALTITUDE)

    rows = []
    summary = []
    trajectories = {}

    vacuum_x, vacuum_time = vacuum_landing()

    _, vacuum_states = simulate(
        make_model(PRESETS["sphere_1kg"], 0.0),
        INITIAL_STATE,
        step_size=0.01
    )
    trajectories["vacuum"] = vacuum_states

    for name, payload in PRESETS.items():
        rows += convergence_rows(name, make_model(payload, isa))

        constant_times, constant_states = simulate(
            make_model(payload, SEA_LEVEL_DENSITY),
            INITIAL_STATE,
            step_size=REFERENCE_STEP
        )

        isa_times, isa_states = simulate(
            make_model(payload, isa),
            INITIAL_STATE,
            step_size=REFERENCE_STEP
        )

        trajectories[f"{name} constant density"] = constant_states
        trajectories[f"{name} ISA"] = isa_states

        constant_x = landing_point(constant_states)[0]
        isa_x = landing_point(isa_states)[0]

        summary.append({
            "payload": name,
            "vacuum_x": vacuum_x,
            "constant_x": constant_x,
            "isa_x": isa_x,
            "drag_effect": vacuum_x - isa_x,
            "isa_effect": isa_x - constant_x,
            "vacuum_time": vacuum_time,
            "isa_time": flight_time(isa_times)
        })

    table = pd.DataFrame(rows)
    table.to_csv(OUTPUT_DIR / "landing_convergence.csv", index=False)

    plot_convergence(table)
    plot_trajectories(trajectories)

    errors = table.pivot_table(
        index="step_size",
        columns=["payload", "method"],
        values="landing_error"
    ).sort_index(ascending=False)

    pd.set_option("display.float_format", "{:.3e}".format)
    print("Landing error vs RK4 reference at 0.0005 s (m):")
    print(errors)

    pd.set_option("display.float_format", "{:.2f}".format)
    print()
    print("Landing x (m) and flight time (s), 500 m release at 15 m/s:")
    print(pd.DataFrame(summary).to_string(index=False))


if __name__ == "__main__":
    main()
