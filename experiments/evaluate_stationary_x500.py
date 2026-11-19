"""produce a reproducible stationary x500 estimator stability report."""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.physics.multicopter_telemetry import PX4_COLUMNS, TRUTH_COLUMNS
from src.physics.stationary_evaluation import (
    PX4_PROVENANCE, TRUTH_PROVENANCE, evaluate_stationary,
    file_sha256, load_input, read_reset_quality,
)


def run(directory, output, *, ulog=None, warmup_s=0, seed=42,
        bootstrap_replicates=300, stationary_threshold_m=0.05):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    directory, output = Path(directory), Path(output)
    truth_path = directory / "gazebo_truth.csv"
    px4_path = directory / "px4_local_position.csv"
    truth_manifest_path = directory / "gazebo_truth_manifest.json"
    px4_manifest_path = directory / "px4_local_position_manifest.json"
    truth, truth_manifest = load_input(truth_path, TRUTH_COLUMNS, "sim_time_s",
                                       TRUTH_PROVENANCE, truth_manifest_path)
    estimates, px4_manifest = load_input(px4_path, PX4_COLUMNS, "px4_time_s",
                                        PX4_PROVENANCE, px4_manifest_path)
    if ulog is not None:
        from_log = Path(px4_manifest.get("source_log", "")).resolve()
        if from_log != Path(ulog).resolve():
            raise ValueError("source ulog path does not match px4 manifest")
    quality = read_reset_quality(ulog, expected_px4_rows=estimates) if ulog is not None else None
    report, data = evaluate_stationary(
        truth, estimates, quality=quality, warmup_s=warmup_s,
        seed=seed, bootstrap_replicates=bootstrap_replicates,
        stationary_threshold_m=stationary_threshold_m,
    )
    inputs = {
        "gazebo_truth_csv": file_sha256(truth_path),
        "px4_local_position_csv": file_sha256(px4_path),
        "gazebo_truth_manifest": file_sha256(truth_manifest_path),
        "px4_local_position_manifest": file_sha256(px4_manifest_path),
    }
    if ulog is not None:
        inputs["ulog"] = file_sha256(ulog)
    report["inputs_sha256"] = inputs
    report["model"] = truth_manifest.get("model")
    report["provenance"] = {"gazebo": TRUTH_PROVENANCE, "px4": PX4_PROVENANCE}
    report["config"] = {"warmup_s": warmup_s, "seed": seed,
                        "bootstrap_replicates": bootstrap_replicates,
                        "stationary_threshold_m": stationary_threshold_m}
    output.mkdir(parents=True, exist_ok=True)
    figures = output / "figures"
    figures.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(3, 1, figsize=(10, 7), sharex=True)
    t = data["px4_times"] - data["px4_times"][0]
    for i, name in enumerate(("east", "north", "up")):
        ax[i].plot(t, 100 * data["px4_centered"][:, i], lw=0.7)
        ax[i].set_ylabel(name + " residual (cm)")
        ax[i].grid(alpha=0.3)
    ax[-1].set_xlabel("time from selected px4 interval start (s)")
    fig.suptitle("px4 stationary estimator fluctuations, mean-centered")
    fig.tight_layout()
    fig.savefig(figures / "stationary_px4_jitter.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(3, 1, figsize=(10, 7), sharex=True)
    t = data["truth_times"] - data["truth_times"][0]
    xyz = data["truth_positions"]
    for i, name in enumerate(("east", "north", "up")):
        ax[i].plot(t, 100 * (xyz[:, i] - xyz[0, i]), lw=0.9)
        ax[i].set_ylabel(name + " displacement (cm)")
        ax[i].grid(alpha=0.3)
    ax[-1].set_xlabel("time from gazebo interval start (s)")
    fig.suptitle("gazebo simulated world displacement")
    fig.tight_layout()
    fig.savefig(figures / "stationary_gazebo_displacement.png", dpi=160)
    plt.close(fig)

    (output / "stationary_evaluation.json").write_text(
        json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    return report


def main():
    parser = argparse.ArgumentParser(description="quality-gated stationary x500 analysis")
    parser.add_argument("--input", type=Path,
                        default=ROOT / "results/multicopter_testbed/local_run")
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--ulog", type=Path, default=None,
                        help="finished source ulog enables validity and reset checks")
    parser.add_argument("--warmup-seconds", type=float, default=0.0)
    parser.add_argument("--stationary-threshold-m", type=float, default=0.05)
    parser.add_argument("--bootstrap-replicates", type=int, default=300)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    output = args.output or args.input
    result = run(args.input, output, ulog=args.ulog, warmup_s=args.warmup_seconds,
                 stationary_threshold_m=args.stationary_threshold_m,
                 bootstrap_replicates=args.bootstrap_replicates, seed=args.seed)
    print("status:", result["status"])
    print("px4 selected samples:", result["counts"]["px4_selected"])
    print("3d rms jitter (m):", result["px4"]["rms_3d_jitter_m"])
    print("95th-percentile jitter (m):", result["px4"]["p95_3d_jitter_m"])
    print("no direct gazebo-px4 position rmse was calculated")
    print("saved:", output / "stationary_evaluation.json")


if __name__ == "__main__":
    main()
