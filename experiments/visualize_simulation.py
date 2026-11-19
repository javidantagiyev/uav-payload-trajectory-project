"""visualize recorded simulator trajectories and attitudes without rerunning physics."""

import argparse
import csv
import json
import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def quaternion_to_rpy(w, x, y, z):
    roll = math.atan2(2 * (w * x + y * z), 1 - 2 * (x * x + y * y))
    pitch = math.asin(max(-1.0, min(1.0, 2 * (w * y - z * x))))
    yaw = math.atan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z))
    return tuple(math.degrees(a) for a in (roll, pitch, yaw))


def run(input_csv, output):
    input_csv = Path(input_csv)
    with input_csv.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    needed = ("time_s", "x_m", "y_m", "z_m", "qw", "qx", "qy", "qz")
    if len(rows) < 2 or not set(needed).issubset(rows[0]):
        raise ValueError("the recording needs at least two 6-dof samples")
    data = {field: [float(row[field]) for row in rows] for field in needed}
    if not all(math.isfinite(v) for samples in data.values() for v in samples):
        raise ValueError("the recording has nonfinite data")
    if any(b <= a for a, b in zip(data["time_s"], data["time_s"][1:])):
        raise ValueError("timestamps must be strictly increasing")
    for w,x,y,z in zip(data["qw"],data["qx"],data["qy"],data["qz"]):
        if abs(w*w+x*x+y*y+z*z-1) > 0.01:
            raise ValueError("recorded quaternions must be unit length")
    rpy = [quaternion_to_rpy(*a) for a in zip(data["qw"],data["qx"],data["qy"],data["qz"])]
    output = Path(output)
    figures = output / "figures"
    figures.mkdir(parents=True, exist_ok=True)

    fig = plt.figure(figsize=(8,6))
    ax = fig.add_subplot(111, projection="3d")
    ax.plot(data["x_m"], data["y_m"], data["z_m"], linewidth=1.5)
    ax.scatter([data["x_m"][0]], [data["y_m"][0]], [data["z_m"][0]], label="first recorded state", s=24)
    ax.set(xlabel="east x (m)", ylabel="north y (m)", zlabel="up z (m)", title="gazebo 6-dof body path")
    ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(figures / "trajectory_3d.png", dpi=170)
    plt.close(fig)

    fig, axs = plt.subplots(2,1,figsize=(8,6),sharex=True)
    for field in ("x_m","y_m","z_m"):
        axs[0].plot(data["time_s"],data[field],label=field)
    for i, label in enumerate(("roll", "pitch", "yaw")):
        axs[1].plot(data["time_s"],[a[i] for a in rpy],label=label)
    axs[0].set_ylabel("position (m)")
    axs[1].set(xlabel="elapsed sim time (s)",ylabel="attitude (deg)")
    for ax in axs:
        ax.grid(alpha=0.25)
        ax.legend()
    fig.tight_layout()
    fig.savefig(figures / "position_attitude.png", dpi=170)
    plt.close(fig)

    summary = {"type":"simulator_recording_summary", "sample_count":len(rows),
               "duration_s":data["time_s"][-1]-data["time_s"][0],
               "start_position_m":[data[k][0] for k in ("x_m","y_m","z_m")],
               "end_position_m":[data[k][-1] for k in ("x_m","y_m","z_m")],
               "source":"recorded simulator CSV; not real-world validation"}
    (output / "recording_summary.json").write_text(json.dumps(summary, indent=2)+"\n",encoding="utf-8")
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=Path("results/simulation_testbed/local_run/rigid_body_6dof.csv"))
    parser.add_argument("--output", type=Path, default=Path("results/simulation_testbed/local_run"))
    args=parser.parse_args()
    print(json.dumps(run(args.input, args.output), indent=2))


if __name__ == "__main__":
    main()
