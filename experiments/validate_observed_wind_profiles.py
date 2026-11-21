"""Evidence-labelled atmospheric model checks on supplied profile observations."""

from pathlib import Path
import argparse
import csv
import json
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.physics.atmospheric_observations import (
    load_profiles, compare_observation_profiles, summarize_errors, sha256_file,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "data/examples/synthetic_wind_tower_6g4.csv"
FIXTURE_META = ROOT / "data/examples/synthetic_wind_tower_6g4.metadata.json"


def write_csv(path, rows):
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def save_plot(fig, path):
    fig.tight_layout()
    fig.savefig(path, dpi=190, bbox_inches="tight")
    plt.close(fig)


def plot_evaluation(fig_dir, profiles, rows, metrics, bounds):
    fig_dir.mkdir(parents=True, exist_ok=True)
    if not rows:
        return []
    created = []
    profile = next((p for p in profiles if len(p) >= 3), None)
    if profile:
        fig, ax = plt.subplots(figsize=(8.5, 5.4))
        ax.plot([np.hypot(p.east_m_s, p.north_m_s) for p in profile],
                [p.height_agl_m for p in profile], "o-", label="profile supplied to evaluator")
        stamp = profile[0].timestamp_utc.isoformat()
        for model in sorted(metrics):
            sub = sorted((r for r in rows if r["model"] == model and
                          r["timestamp_utc"] == stamp), key=lambda r:r["height_agl_m"])
            if sub:
                ax.plot([r["predicted_speed_m_s"] for r in sub],
                        [r["height_agl_m"] for r in sub], ".--", label=model)
        ax.axhspan(bounds[0], bounds[1], color="gray", alpha=.07, label="declared surface-layer domain")
        ax.set(xlabel="Horizontal wind speed (m/s)", ylabel="Height AGL (m)",
               title="Profile comparison (single timestamp, with holdout levels)")
        ax.legend(fontsize=8); ax.grid(alpha=.2)
        save_plot(fig, fig_dir/"01_profile_comparison.png"); created.append("01_profile_comparison.png")

        # The full-height view can hide near-ground structure. Provide a focused
        # second view without changing the data or fitted/declared models.
        fig, ax = plt.subplots(figsize=(8.5, 5.4))
        in_domain = [p for p in profile if bounds[0] <= p.height_agl_m <= bounds[1]]
        ax.plot([np.hypot(p.east_m_s, p.north_m_s) for p in in_domain],
                [p.height_agl_m for p in in_domain], "o-", label="supplied profile")
        for model in sorted(metrics):
            sub = sorted((r for r in rows if r["model"] == model and
                          r["timestamp_utc"] == stamp), key=lambda r:r["height_agl_m"])
            if sub:
                ax.plot([r["predicted_speed_m_s"] for r in sub],
                        [r["height_agl_m"] for r in sub], ".--", label=model)
        ax.set_ylim(bounds[0]-2, bounds[1]+2)
        ax.set(xlabel="Horizontal wind speed (m/s)", ylabel="Height AGL (m)",
               title="Surface-layer detail: held-out levels and model differences")
        ax.legend(fontsize=8); ax.grid(alpha=.2)
        save_plot(fig, fig_dir/"01b_surface_layer_zoom.png"); created.append("01b_surface_layer_zoom.png")

    fig, ax = plt.subplots(figsize=(9, 5))
    for model in sorted(metrics):
        sub = [r for r in rows if r["model"] == model]
        h = sorted(set(r["height_agl_m"] for r in sub))
        ax.plot(h, [np.mean([r["vector_error_m_s"] for r in sub if r["height_agl_m"] == z])
                    for z in h], "o-", label=model)
    ax.set(xlabel="Height AGL (m)", ylabel="Mean wind-vector error magnitude (m/s)",
           title="Holdout error by height (no out-of-domain extrapolation)")
    ax.legend(fontsize=8); ax.grid(alpha=.2)
    save_plot(fig, fig_dir/"02_error_by_height.png"); created.append("02_error_by_height.png")

    fig, ax = plt.subplots(figsize=(9, 5))
    names = sorted(metrics)
    x = np.arange(len(names))
    values = [metrics[n]["vector_rmse_m_s"] for n in names]
    ax.bar(x, values)
    ax.set_xticks(x, labels=names, rotation=20, ha="right")
    ax.set(ylabel="Vector RMSE (m/s)", title="Model error across eligible held-out levels")
    ax.grid(axis="y", alpha=.2)
    save_plot(fig, fig_dir/"03_model_rmse.png"); created.append("03_model_rmse.png")

    fig, ax = plt.subplots(figsize=(9, 5))
    for model in names:
        sub = sorted((r for r in rows if r["model"] == model),
                     key=lambda r:(r["timestamp_utc"],r["height_agl_m"]))
        x = np.arange(len(sub))
        ax.scatter(x, [r["speed_error_m_s"] for r in sub], s=9, alpha=.5, label=model)
    ax.axhline(0, c="gray", lw=1)
    ax.set(xlabel="Eligible sample index (ordered by timestamp and height)",
           ylabel="Signed speed error (m/s)", title="Residual structure: model bias and variability")
    ax.legend(fontsize=8); ax.grid(alpha=.2)
    save_plot(fig, fig_dir/"04_residual_evolution.png"); created.append("04_residual_evolution.png")

    fig, ax = plt.subplots(figsize=(9, 5))
    for model in names:
        sub = [r for r in rows if r["model"] == model and r["direction_error_deg"] is not None]
        if sub:
            ax.scatter([r["height_agl_m"] for r in sub],
                       [r["direction_error_deg"] for r in sub], s=12, alpha=.45, label=model)
    ax.axhline(0, c="gray", lw=1)
    ax.set(xlabel="Height AGL (m)", ylabel="Signed meteorological direction error (degrees)",
           title="Wind veer and direction-model mismatch")
    ax.legend(fontsize=8); ax.grid(alpha=.2)
    save_plot(fig, fig_dir/"05_direction_error.png"); created.append("05_direction_error.png")
    return created


def run(csv_path, meta_path, output_dir, reference_height=10, z0=0.03,
        valid_min=10, valid_max=40, L_values=(None,100.,-100.), seed=2026):
    meta, profiles = load_profiles(csv_path, meta_path)
    rows, excluded = compare_observation_profiles(profiles, reference_height, z0,
                                                 (valid_min, valid_max), L_values)
    if not rows:
        raise ValueError("no eligible holdout levels within declared model domain")
    metrics = summarize_errors(rows, bootstrap_replicates=500, seed=seed)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(output_dir/"holdout_residuals.csv", rows)
    names = plot_evaluation(output_dir/"figures", profiles, rows, metrics,
                            (valid_min, valid_max))
    report = {
        "status":"observational_profile_comparison" if meta["data_kind"] == "observed" else
                 "synthetic_or_reanalysis_profile_comparison_not_field_validation",
        "data_kind_claimed_by_metadata":meta["data_kind"],
        "source_identity_not_independently_authenticated":True,
        "raw_csv_sha256":sha256_file(csv_path),
        "raw_metadata_sha256":sha256_file(meta_path),
        "source":meta, "profile_count":len(profiles), "eligible_rows":len(rows),
        "data_exclusions":excluded,
        "declared_surface_layer_valid_height_agl_m":[valid_min,valid_max],
        "reference_height_agl_m":reference_height, "assumed_roughness_length_m":z0,
        "candidate_obukhov_lengths_m":[x for x in L_values],
        "stability_lengths_externally_assumed_not_estimated":True,
        "candidate_models_are_not_calibrated_to_holdout":True,
        "loo_interpolation_excludes_heldout_height":True,
        "uncertainty_warning":"UTC-day-block bootstrap captures some temporal dependence but cannot remove measurement bias or source limitations",
        "model_metrics":metrics, "figures":names,
        "limitations":[
            "input provenance metadata is declarative, not authenticated",
            "results describe wind-profile agreement only, not UAV performance",
            "no profile extrapolation beyond declared surface-layer domain",
            "reference height measured at same timestamp; other levels held out",
            "roughness and L candidates are assumptions unless independently measured",
            "observations at a single tower/site cannot establish cross-site generality",
            "time-correlated samples must not be treated as independent field replications",
        ],
    }
    (output_dir/"stage4_report.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    return report


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--csv", type=Path, default=FIXTURE)
    p.add_argument("--metadata", type=Path)
    p.add_argument("--out", type=Path, default=ROOT/"results/atmospheric_testbed/6g_stage4")
    p.add_argument("--reference-height", type=float, default=10)
    p.add_argument("--roughness", type=float, default=0.03)
    p.add_argument("--valid-min", type=float, default=10)
    p.add_argument("--valid-max", type=float, default=40)
    p.add_argument("--seed", type=int, default=2026)
    args=p.parse_args()
    if args.metadata is None and args.csv.resolve() != FIXTURE.resolve():
        p.error("--metadata required for non-fixture observations")
    report=run(args.csv,args.metadata or FIXTURE_META,args.out,
               args.reference_height,args.roughness,args.valid_min,args.valid_max,
               seed=args.seed)
    print(json.dumps({"status":report["status"],"profiles":report["profile_count"],
                      "eligible_rows":report["eligible_rows"],
                      "figures":len(report["figures"]),"output":str(args.out),
                      "source_identity_not_independently_authenticated":True},indent=2))


if __name__=="__main__":
    main()
