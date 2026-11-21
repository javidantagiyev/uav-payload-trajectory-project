"""audit the existing wind and atmosphere implementations over a test grid."""

import argparse
import csv
import json
from pathlib import Path
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.physics.atmosphere import isa_density, pressure, temperature
from src.physics.wind_model import (discrete_gust, layered_wind, log_law_wind,
                                    power_law_wind, turbulence_series)



def main():
    p = argparse.ArgumentParser()
    p.add_argument("--output", type=Path,
                   default=ROOT / "results/environmental_testbed/local_run/model_diagnostics")
    args = p.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    heights = np.array([0.1, 1, 2, 5, 10, 20, 50, 100, 250, 500], dtype=float)
    reference = (4.0, 2.0, 0.0)
    profiles = {
        "power_1_7": power_law_wind(reference, reference_height=10, exponent=1/7),
        "log_rough_0p03": log_law_wind(reference, reference_height=10, roughness_length=0.03),
        "layered": layered_wind([0, 10, 100, 500],
                                [(1, 1, 0), reference, (6, 3, 0), (8, -2, 0)]),
    }
    rows = []
    for h in heights:
        row = {"height_m": float(h), "isa_temperature_k": temperature(float(h)),
               "isa_pressure_pa": pressure(float(h)), "isa_density_kg_m3": isa_density(float(h))}
        for name, fn in profiles.items():
            v = np.asarray(fn(0.0, (0, 0, float(h))))
            row[f"{name}_speed_m_s"] = float(np.linalg.norm(v))
            row[f"{name}_east_m_s"] = float(v[0])
            row[f"{name}_north_m_s"] = float(v[1])
        rows.append(row)
    with (args.output / "wind_profiles_and_isa.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    time = np.arange(0, 20.01, 0.01)
    gust = discrete_gust(reference, (3, 0, 0), 4, 5)
    gust_east = np.array([gust(float(t), (0, 0, 10))[0] for t in time])
    times, turbulence = turbulence_series((1, 0.5, 0.2), 30, 8, 20, 0.01, seed=2026)
    theoretical_a = float(np.exp(-8 * 0.01 / 30))
    observed_a = float(np.corrcoef(turbulence[:-1, 0], turbulence[1:, 0])[0, 1])
    summary = {
        "status": "offline_physics_model_diagnostics_not_gazebo_run",
        "power_at_reference_10m_m_s": profiles["power_1_7"](0, (0, 0, 10)),
        "log_at_reference_10m_m_s": profiles["log_rough_0p03"](0, (0, 0, 10)),
        "isa_density_0m_kg_m3": isa_density(0),
        "isa_density_500m_kg_m3": isa_density(500),
        "gust_peak_east_m_s": float(max(gust_east)),
        "turbulence_lag1_theoretical": theoretical_a,
        "turbulence_lag1_sample": observed_a,
        "turbulence_seed": 2026,
        "limitations": ["these wind profiles are not yet coupled into gazebo's wind system",
                        "first-order gauss-markov is dryden-like, not a validated dryden spectrum",
                        "reference height and roughness are illustrative assumptions"],
    }
    (args.output / "wind_model_diagnostics.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    fig, ax = plt.subplots(figsize=(8, 5))
    for k in profiles:
        ax.plot([row[f"{k}_speed_m_s"] for row in rows], heights, marker="o", label=k)
    ax.set(xlabel="wind speed (m/s)", ylabel="height above ground (m)",
           title="assumed wind profiles; offline model only")
    ax.grid(alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(args.output / "wind_profiles.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(times, turbulence[:, 0], label="gauss-markov east disturbance")
    ax.plot(time, gust_east - reference[0], label="discrete gust increment")
    ax.set(xlabel="time (s)", ylabel="velocity component (m/s)",
           title="illustrative gust and stochastic fluctuations")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(args.output / "gust_and_turbulence.png", dpi=160)
    plt.close(fig)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
