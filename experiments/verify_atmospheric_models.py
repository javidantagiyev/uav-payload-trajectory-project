"""generate independent atmospheric model-verification diagnostics and figures."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from src.physics import atmosphere, atmospheric_verification as v, wind_model


def _write_csv(path, rows):
    if not rows:
        raise ValueError("cannot export empty dataset")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _plot(path, title, xlabel, ylabel, lines, *, xlim=None, ylim=None,
          vline=None, logy=False):
    fig, ax = plt.subplots(figsize=(9.2, 5.4), dpi=145)
    for x, y, label in lines:
        ax.plot(x, y, label=label, linewidth=1.45)
    ax.set(title=title, xlabel=xlabel, ylabel=ylabel)
    if xlim is not None:
        ax.set_xlim(*xlim)
    if ylim is not None:
        ax.set_ylim(*ylim)
    if vline is not None:
        ax.axvline(vline, linestyle="--", linewidth=1.0, label="reference height")
    if logy:
        ax.set_yscale("log")
    ax.grid(True, alpha=0.26)
    ax.legend(loc="best", frameon=False)
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def run(output, duration_s=900.0, step_s=0.05, seed=2026):
    if duration_s <= 0 or step_s <= 0:
        raise ValueError("duration and step must be positive")
    out = Path(output)
    figures = out / "figures"
    figures.mkdir(parents=True, exist_ok=True)

    ref = v.isa_reference_comparison()
    _write_csv(out / "isa_reference_comparison.csv", ref)
    hydrostatic = [v.hydrostatic_balance(h) for h in (0., 500., 1000., 2000., 5000.)]
    _write_csv(out / "isa_hydrostatic_balance.csv", hydrostatic)
    h = np.linspace(0, 2500, 400)
    rho = np.array([atmosphere.isa_density(z) for z in h])
    reference_h = np.array([r["altitude_m"] for r in ref])
    reference_rho = np.array([r["density_kg_m3"] for r in ref])
    _plot(figures / "01_isa_density.png", "ISA dry-air density | model vs published anchors",
          "altitude above mean sea level (m)", "density (kg/m³)",
          [(h, rho, "repository ISA"), (reference_h, reference_rho, "1976 standard table (line connects anchors)")])

    heights = np.linspace(0.1, 150., 351)
    profile = v.profile_comparison(heights, reference_wind=(4.0, 2.0, 1.0))
    _write_csv(out / "wind_profile_comparison.csv", profile)
    height = np.array([r["height_agl_m"] for r in profile])
    _plot(figures / "02_mean_wind_profiles.png", "Illustrative horizontal mean wind models | no stability correction",
          "height above ground (m)", "eastward mean wind (m/s)",
          [(height, [r["power_east_m_s"] for r in profile], "1/7 power law"),
           (height, [r["log_east_m_s"] for r in profile], "neutral log law (z0=0.03m)")],
          vline=10.0)
    _plot(figures / "03_vertical_component_contract.png", "Audit finding | current code also scales vertical wind",
          "height above ground (m)", "upward wind (m/s)",
          [(height, [r["power_up_m_s"] for r in profile], "current power-law output"),
           (height, [r["log_up_m_s"] for r in profile], "current log-law output"),
           (height, np.ones_like(height), "hypothetical unchanged vertical component")],
          vline=10.0)

    gt = np.linspace(-1.0, 7.0, 801)
    gust = wind_model.discrete_gust((0, 0, 0), (3.0, 0, 0), 1.0, 4.0)
    gw = np.array([gust(float(t), (0, 0, 10))[0] for t in gt])
    _plot(figures / "04_1_cosine_gust.png", "One-cosine pulse | time-local mathematical example",
          "elapsed time (s)", "eastward wind (m/s)",
          [(gt, gw, "pulse: 1–5 s, peak 3 m/s")])

    d = v.stochastic_diagnostics(duration_s=duration_s, step_s=step_s, seed=seed)
    st = d["times"]
    samples = d["series"]
    rows = [{"time_s": float(st[i]), "east_m_s": float(samples[i, 0]),
             "north_m_s": float(samples[i, 1]), "up_m_s": float(samples[i, 2])}
            for i in range(len(st))]
    _write_csv(out / "ar1_timeseries.csv", rows)
    _write_csv(out / "ar1_autocorrelation.csv", [
        {"lag_s": float(t), "empirical_acf": float(s), "theoretical_acf": float(a)}
        for t, s, a in zip(d["lags_s"], d["empirical_acf"], d["theoretical_acf"])])
    _write_csv(out / "ar1_spectrum.csv", [
        {"frequency_hz": float(f), "welch_psd": float(s), "theoretical_ar1_psd": float(a)}
        for f, s, a in zip(d["psd_frequency_hz"], d["psd_sample"], d["psd_ar1_theory"])])
    _plot(figures / "05_ar1_full_duration.png", "Gauss-Markov process | complete simulated duration",
          "simulation time (s)", "fluctuation (m/s)",
          [(st, samples[:, k], label) for k, label in enumerate(("east", "north", "up"))])
    zoom = st <= min(45.0, duration_s)
    _plot(figures / "06_ar1_early_detail.png", "Gauss-Markov process | early time detail",
          "simulation time (s)", "fluctuation (m/s)",
          [(st[zoom], samples[zoom, k], label)
           for k, label in enumerate(("east", "north", "up"))])
    _plot(figures / "07_ar1_acf.png", "Lag correlation | generated AR(1) vs exact discrete theory",
          "time lag (s)", "autocorrelation", [
              (d["lags_s"], d["empirical_acf"], "sample east"),
              (d["lags_s"], d["theoretical_acf"], "theoretical east")])
    keep = d["psd_frequency_hz"] > 0
    _plot(figures / "08_ar1_psd.png", "Spectral density | generated AR(1), not Dryden",
          "frequency (Hz)", "PSD ((m/s)²/Hz)", [
              (d["psd_frequency_hz"][keep], d["psd_sample"][keep], "Welch estimate"),
              (d["psd_frequency_hz"][keep], d["psd_ar1_theory"][keep], "AR(1) formula")],
          logy=True)
    # correlated data converge slower than iid samples.
    checkpoints = np.unique(np.linspace(max(5, len(st)//100), len(st), 200, dtype=int))
    cumulative_mean = np.cumsum(samples[:, 0]) / np.arange(1, len(st)+1)
    _plot(figures / "09_ar1_running_mean.png", "Cumulative sample mean | serial correlation matters",
          "simulation time (s)", "running east mean (m/s)",
          [(st[checkpoints-1], cumulative_mean[checkpoints-1], "running mean"),
           (st[checkpoints-1], np.zeros(len(checkpoints)), "theoretical mean")])

    contract = v.model_contract_findings()
    summary = {
        "status": "verified_mathematical_contracts_not_physical_wind_validation",
        "reference_source": v.ISA_REFERENCE_SOURCE,
        "reference_rows": len(ref),
        "maximum_isa_temperature_abs_error_k": max(abs(r["error_temperature_k"]) for r in ref),
        "maximum_isa_pressure_abs_error_pa": max(abs(r["error_pressure_pa"]) for r in ref),
        "maximum_isa_density_abs_error_kg_m3": max(abs(r["error_density_kg_m3"]) for r in ref),
        "maximum_hydrostatic_residual_pa_m": max(abs(r["residual_pa_m"]) for r in hydrostatic),
        "maximum_power_formula_error_m_s": max(r["power_formula_max_abs_error_m_s"] for r in profile),
        "maximum_log_formula_error_m_s": max(r["log_formula_max_abs_error_m_s"] for r in profile),
        "ar1": d["summary"], "contract_findings": contract,
        "figures_created": len(list(figures.glob("*.png"))),
        "literature_status": "independent_table_plus_equation_consistency_checks",
        "limitations": [
            "wind-profile curve examples are assumptions, not observed atmospheric profiles",
            "no coupling of advanced python wind models to gazebo established",
            "gauss-markov is not a validated dryden or von karman turbulence model",
            "spatial and cross-axis turbulence coherence are unmodeled",
            "no real-weather observations or physical validation included",
        ],
    }
    (out / "atmospheric_verification.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    digest = {str(f.relative_to(out)): hashlib.sha256(f.read_bytes()).hexdigest()
              for f in sorted(out.rglob("*.csv"))}
    (out / "csv_sha256.json").write_text(json.dumps(digest, indent=2) + "\n", encoding="utf-8")
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="results/atmospheric_testbed/6g_stage2")
    parser.add_argument("--duration-s", type=float, default=900.0)
    parser.add_argument("--step-s", type=float, default=0.05)
    parser.add_argument("--seed", type=int, default=2026)
    args = parser.parse_args()
    print(json.dumps(run(args.output, args.duration_s, args.step_s, args.seed), indent=2))


if __name__ == "__main__":
    main()
