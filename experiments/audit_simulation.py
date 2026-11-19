"""audit 6-dof simulator recordings and generate diagnostic plots."""

import argparse
import csv
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.physics.simulation_audit import analyse, load_recording


def run(input_csv, output, *, config=None):
    settings = config or {}
    data = load_recording(input_csv)
    summary, aux = analyse(
        data,
        free_flight_until_s=settings.get("free_flight_until_s", 0.5),
        expected_g_m_s2=settings.get("expected_g_m_s2", 9.81),
        initial_disagreement_threshold_m_s=settings.get("initial_disagreement_threshold_m_s", 2.0),
        gravity_tolerance_m_s2=settings.get("gravity_tolerance_m_s2", 0.1),
        position_fit_tolerance_m=settings.get("position_fit_tolerance_m", 0.01),
        velocity_consistency_tolerance_m_s=settings.get("velocity_consistency_tolerance_m_s", 0.1),
    )
    output = Path(output)
    figures = output / "figures"
    figures.mkdir(parents=True, exist_ok=True)

    t = data["time_s"]
    fig, ax = plt.subplots(figsize=(8, 4.4))
    ax.plot(t, data["z_m"], label="gazebo height")
    ax.plot(aux["fit_times"], aux["fit_heights"], "--", label="free-flight quadratic fit")
    ax.axvline(settings.get("free_flight_until_s", 0.5), linestyle=":", color="grey", label="fit window ends")
    ax.set(xlabel="simulation time (s)", ylabel="body center height (m)", title="vertical motion and free-flight consistency")
    ax.grid(alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(figures / "height_physics_check.png", dpi=170)
    plt.close(fig)

    fig, axs = plt.subplots(2, 1, figsize=(8, 6), sharex=True)
    comparison = aux["free_mask"].copy()
    comparison[0] = False
    axs[0].plot(t[comparison], aux["v_world"][comparison, 2], label="odometry world v_z")
    axs[0].plot(t[comparison], aux["backward_velocity"][comparison, 2], "--", label="position difference v_z")
    axs[0].set(ylabel="vertical velocity (m/s)", title="free-flight velocity consistency")
    horizontal_cm = np.linalg.norm(aux["positions"][:, :2] - aux["positions"][0, :2], axis=1) * 100
    axs[1].plot(t, horizontal_cm, label="horizontal displacement")
    axs[1].set(xlabel="simulation time (s)", ylabel="displacement (cm)")
    for ax in axs:
        ax.grid(alpha=0.25)
        ax.legend()
    fig.tight_layout()
    fig.savefig(figures / "velocity_and_horizontal_check.png", dpi=170)
    plt.close(fig)

    columns = (
        "time_s", "world_vx_m_s", "world_vy_m_s", "world_vz_m_s",
        "world_wx_rad_s", "world_wy_rad_s", "world_wz_rad_s",
        "backward_vx_m_s", "backward_vy_m_s", "backward_vz_m_s",
        "twist_quality_flag",
    )
    with (output / "world_frame_twist.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(columns)
        for i, time in enumerate(t):
            writer.writerow((
                time, *aux["v_world"][i], *aux["w_world"][i],
                *aux["backward_velocity"][i],
                "suspect_initialization" if i == 0 and aux["first_twist_suspect"] else "unflagged",
            ))
    (output / "simulation_audit.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def main():
    parser = argparse.ArgumentParser(description="audit gazebo inert-body motion")
    parser.add_argument("--config", type=Path, default=ROOT / "configs/simulation_audit.json")
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    settings = json.loads(args.config.read_text(encoding="utf-8"))
    input_csv = args.input or ROOT / settings["source"]
    output = args.output or ROOT / settings["output"]
    print(json.dumps(run(input_csv, output, config=settings), indent=2))


if __name__ == "__main__":
    main()
