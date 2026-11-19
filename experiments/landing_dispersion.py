
"""Monte Carlo landing dispersion study for a 500 m sphere drop (SI units).

Run from the repository root:
    python -m experiments.landing_dispersion
"""

import json
import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.physics.monte_carlo import (
    PARAMETER_NAMES,
    run_landing,
    monte_carlo_landings,
    radial_miss,
    landing_statistics,
    confidence_ellipse,
    sensitivity_ranking,
    correlation_ranking
)

OUTPUT_DIR = Path("results/landing_dispersion")

SAMPLE_COUNT = 500
SEED = 42
STEP_SIZE = 0.02
PROFILES = {"constant": None, "power_law": "power"}

NOMINAL = {
    "mass": 1.0,
    "area": math.pi * 0.075 ** 2,
    "drag_coefficient": 0.47,
    "density": 1.225,
    "wind_speed": 6.0,
    "wind_direction": 270.0,
    "release_x": 0.0,
    "release_y": 0.0,
    "release_z": 500.0,
    "release_vx": 15.0,
    "release_vy": 0.0,
    "release_vz": 0.0,
    "release_delay": 0.0
}

SIGMAS = {
    "drag_coefficient": 0.10 * 0.47,
    "mass": 0.02 * 1.0,
    "density": 0.03 * 1.225,
    "wind_speed": 1.5,
    "wind_direction": 15.0,
    "release_x": 1.5,
    "release_y": 1.5,
    "release_z": 2.0,
    "release_vx": 0.3,
    "release_vy": 0.3,
    "release_vz": 0.3,
    "release_delay": 0.1
}


def run_profile(wind_profile):
    """Run the Monte Carlo study and sensitivity analyses for one wind profile."""
    x, y, t = run_landing(NOMINAL, STEP_SIZE, wind_profile)
    target = (x, y)

    samples, points = monte_carlo_landings(
        NOMINAL,
        SIGMAS,
        SAMPLE_COUNT,
        seed=SEED,
        step_size=STEP_SIZE,
        wind_profile=wind_profile
    )

    center, semi_major, semi_minor, angle = confidence_ellipse(points, 0.95)

    return {
        "nominal_landing": {"x": x, "y": y, "flight_time": t},
        "samples": samples,
        "points": points,
        "statistics": landing_statistics(points, target),
        "ellipse95": {
            "center_x": center[0],
            "center_y": center[1],
            "semi_major": semi_major,
            "semi_minor": semi_minor,
            "angle_deg": angle
        },
        "sensitivity": sensitivity_ranking(NOMINAL, SIGMAS, STEP_SIZE, wind_profile),
        "correlation": correlation_ranking(samples, points, target)
    }


def save_landings(results):
    """Write every sampled parameter set and landing point to CSV."""
    frames = []

    for profile, result in results.items():
        frame = pd.DataFrame(result["samples"], columns=PARAMETER_NAMES)
        frame.insert(0, "profile", profile)
        frame["landing_x"] = result["points"][:, 0]
        frame["landing_y"] = result["points"][:, 1]
        frame["flight_time"] = result["points"][:, 2]

        target = (result["nominal_landing"]["x"], result["nominal_landing"]["y"])
        frame["radial_miss"] = radial_miss(result["points"], target)

        frames.append(frame)

    pd.concat(frames).to_csv(OUTPUT_DIR / "landings.csv", index=False)


def ellipse_outline(ellipse):
    """Return x and y coordinates of the confidence ellipse outline."""
    angles = np.linspace(0, 2 * math.pi, 200)
    theta = math.radians(ellipse["angle_deg"])

    u = ellipse["semi_major"] * np.cos(angles)
    v = ellipse["semi_minor"] * np.sin(angles)

    x = ellipse["center_x"] + u * math.cos(theta) - v * math.sin(theta)
    y = ellipse["center_y"] + u * math.sin(theta) + v * math.cos(theta)

    return x, y


def plot_scatter(results):
    """Plot landing points with the 95% ellipse and CEP circles."""
    figure, axes = plt.subplots(1, len(results), figsize=(12, 6))

    for axis, (profile, result) in zip(axes, results.items()):
        points = result["points"]
        stats = result["statistics"]
        tx = result["nominal_landing"]["x"]
        ty = result["nominal_landing"]["y"]

        axis.scatter(points[:, 0], points[:, 1], s=6, alpha=0.5, label="Landings")
        axis.plot(tx, ty, "k+", markersize=12, label="Target (nominal)")

        ex, ey = ellipse_outline(result["ellipse95"])
        axis.plot(ex, ey, "r-", label="95% ellipse")

        circles = (
            (stats["cep50"], "g--", "CEP50"),
            (stats["cep95"], "m--", "CEP95"),
            (10.0, "k:", "10 m")
        )

        angles = np.linspace(0, 2 * math.pi, 200)

        for radius, style, name in circles:
            axis.plot(
                tx + radius * np.cos(angles),
                ty + radius * np.sin(angles),
                style,
                label=name + " ({:.1f} m)".format(radius)
            )

        axis.set_title(profile.replace("_", " ") + " wind profile")
        axis.set_xlabel("East x (m)")
        axis.set_ylabel("North y (m)")
        axis.set_aspect("equal", adjustable="datalim")
        axis.grid(True, alpha=0.3)
        axis.legend(fontsize=8)

    figure.tight_layout()
    figure.savefig(OUTPUT_DIR / "landing_scatter.png", dpi=150)
    plt.close(figure)


def plot_histogram(results):
    """Plot the radial miss distance distributions."""
    figure, axis = plt.subplots(figsize=(8, 5))

    for profile, result in results.items():
        target = (result["nominal_landing"]["x"], result["nominal_landing"]["y"])
        miss = radial_miss(result["points"], target)

        axis.hist(miss, bins=40, alpha=0.5, label=profile.replace("_", " "))

    axis.set_xlabel("Radial miss from nominal landing point (m)")
    axis.set_ylabel("Count")
    axis.grid(True, alpha=0.3)
    axis.legend()

    figure.tight_layout()
    figure.savefig(OUTPUT_DIR / "miss_histogram.png", dpi=150)
    plt.close(figure)


def plot_sensitivity(results):
    """Plot one-at-a-time sensitivity as horizontal bars."""
    figure, axes = plt.subplots(1, len(results), figsize=(12, 5))

    for axis, (profile, result) in zip(axes, results.items()):
        ranking = result["sensitivity"][::-1]

        axis.barh(
            [name for name, _ in ranking],
            [shift for _, shift in ranking]
        )

        axis.set_title(profile.replace("_", " ") + " wind profile")
        axis.set_xlabel("Landing shift for +/- 1 sigma (m)")
        axis.grid(True, axis="x", alpha=0.3)

    figure.tight_layout()
    figure.savefig(OUTPUT_DIR / "sensitivity.png", dpi=150)
    plt.close(figure)


def save_summary(results):
    """Write the summary statistics to JSON."""
    constant = results["constant"]["nominal_landing"]
    power = results["power_law"]["nominal_landing"]

    summary = {
        "sample_count": SAMPLE_COUNT,
        "seed": SEED,
        "step_size": STEP_SIZE,
        "nominal": NOMINAL,
        "sigmas": SIGMAS,
        "profiles": {},
        "nominal_landing_difference_m": math.hypot(
            power["x"] - constant["x"],
            power["y"] - constant["y"]
        )
    }

    for profile, result in results.items():
        summary["profiles"][profile] = {
            "nominal_landing": result["nominal_landing"],
            "statistics": result["statistics"],
            "ellipse95": result["ellipse95"],
            "sensitivity_oat": dict(result["sensitivity"]),
            "correlation_with_miss": dict(result["correlation"])
        }

    with open(OUTPUT_DIR / "summary.json", "w", encoding="utf-8") as file:
        json.dump(summary, file, indent=2)

    return summary


def print_summary(summary):
    """Print the key results."""
    for profile, data in summary["profiles"].items():
        landing = data["nominal_landing"]
        stats = data["statistics"]
        ellipse = data["ellipse95"]

        print("\n=== " + profile + " wind profile ===")
        print("Nominal landing: x = {:.2f} m, y = {:.2f} m, t = {:.2f} s".format(
            landing["x"], landing["y"], landing["flight_time"]
        ))
        print("Mean landing:    x = {:.2f} m, y = {:.2f} m".format(
            stats["mean_x"], stats["mean_y"]
        ))
        print("Std:             x = {:.2f} m, y = {:.2f} m".format(
            stats["std_x"], stats["std_y"]
        ))
        print("CEP50 = {:.2f} m, CEP95 = {:.2f} m, RMS = {:.2f} m".format(
            stats["cep50"], stats["cep95"], stats["rms"]
        ))
        print("Within 10 m: {:.1%}".format(stats["fraction_within_10m"]))
        print("95% ellipse: semi-major = {:.2f} m, semi-minor = {:.2f} m, angle = {:.1f} deg".format(
            ellipse["semi_major"], ellipse["semi_minor"], ellipse["angle_deg"]
        ))
        print("OAT sensitivity (m):")

        for name, shift in data["sensitivity_oat"].items():
            print("  {:<18s} {:8.2f}".format(name, shift))

    print("\nNominal landing difference constant vs power law: {:.2f} m".format(
        summary["nominal_landing_difference_m"]
    ))


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    results = {
        profile: run_profile(wind_profile)
        for profile, wind_profile in PROFILES.items()
    }

    save_landings(results)
    plot_scatter(results)
    plot_histogram(results)
    plot_sensitivity(results)

    summary = save_summary(results)
    print_summary(summary)

    print("\nResults saved to " + str(OUTPUT_DIR))


if __name__ == "__main__":
    main()
