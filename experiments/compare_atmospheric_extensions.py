"""stage 3 bounded atmospheric-model comparisons (offline; not gazebo)."""

from pathlib import Path
import argparse
import csv
import hashlib
import json
import sys

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# Use the same root-import convention as other standalone experiments.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.physics import atmosphere, wind_model
from src.physics.atmospheric_extensions import (
    TabulatedWindProfile, businger_dyer_psi_m, bounded_gauss_markov_wind,
    moist_air_density, monin_obukhov_horizontal_wind,
)


REFERENCE_WIND = (4.0, 2.0)
REFERENCE_HEIGHT = 10.0
Z0 = 0.03
VALID_RANGE = (1.0, 40.0)


def _write_csv(path, columns, rows):
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def _save(fig, directory, name):
    fig.savefig(directory / name, dpi=185, bbox_inches="tight")
    plt.close(fig)


def _wind(L=None, z0=Z0, vertical=0):
    return monin_obukhov_horizontal_wind(
        REFERENCE_WIND, REFERENCE_HEIGHT, z0, VALID_RANGE,
        obukhov_length=L, vertical_wind=vertical)


def _file_digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(output_dir, seed=2026):
    output_dir = Path(output_dir)
    figures = output_dir / "figures"
    figures.mkdir(parents=True, exist_ok=True)
    heights = np.linspace(VALID_RANGE[0], VALID_RANGE[1], 250)
    curves = {
        "neutral": _wind(),
        "stable_L_100m": _wind(100),
        "unstable_L_minus100m": _wind(-100),
    }

    # (1) controlled mean-wind profiles. Exact same 10m reference in every case.
    rows = []
    for z in heights:
        for name, model in curves.items():
            e, n, up = model(0, (0, 0, float(z)))
            rows.append({"height_agl_m": float(z), "case": name,
                         "east_m_s": e, "north_m_s": n,
                         "up_m_s": up,
                         "horizontal_speed_m_s": float(np.hypot(e, n))})
    _write_csv(output_dir / "mean_wind_profiles.csv", list(rows[0]), rows)
    fig, ax = plt.subplots(figsize=(8.5, 5))
    for name in curves:
        subset = [r for r in rows if r["case"] == name]
        ax.plot([r["horizontal_speed_m_s"] for r in subset],
                [r["height_agl_m"] for r in subset], label=name)
    ax.axhline(REFERENCE_HEIGHT, ls="--", c="gray", lw=1, label="10 m reference")
    ax.set(xlabel="Mean horizontal wind speed (m/s)",
           ylabel="Height above ground (m)",
           title="Businger–Dyer illustrative surface-layer profile")
    ax.legend()
    ax.grid(alpha=.2)
    fig.tight_layout()
    _save(fig, figures, "01_stability_comparison.png")

    # (2) horizontal-vs-vertical model contract.
    neutral_3 = _wind(vertical=1.0)
    legacy = wind_model.log_law_wind((4, 2, 1), 10, Z0)
    new_up = [neutral_3(0, (0, 0, float(z)))[2] for z in heights]
    old_up = [legacy(0, (0, 0, float(z)))[2] for z in heights]
    fig, ax = plt.subplots(figsize=(8.5, 5))
    ax.plot(heights, new_up, label="new: separately specified vertical wind")
    ax.plot(heights, old_up, label="legacy: vertical wind scaled by log law")
    ax.set(xlabel="Height AGL (m)", ylabel="Upward wind (m/s)",
           title="Contract difference: horizontal shear is not vertical shear")
    ax.legend()
    ax.grid(alpha=.2)
    fig.tight_layout()
    _save(fig, figures, "02_vertical_wind_separation.png")

    # (3) sensitivity to empirical z0 and stability, normalized at 10m.
    roughnesses = (.005, .03, .1, .5)
    stabilities = [None, -300, -100, -50, 50, 100, 300]
    sensitivity_rows = []
    grid = np.zeros((len(roughnesses), len(stabilities)))
    for i, z0 in enumerate(roughnesses):
        for j, L in enumerate(stabilities):
            model = _wind(L=L, z0=z0)
            at30 = model(0, (0, 0, 30))
            speed = float(np.hypot(at30[0], at30[1]))
            grid[i, j] = speed
            sensitivity_rows.append({"roughness_length_m": z0,
                                     "obukhov_length_m": "neutral" if L is None else L,
                                     "height_agl_m": 30, "horizontal_speed_m_s": speed})
    _write_csv(output_dir / "wind_parameter_sensitivity.csv",
               list(sensitivity_rows[0]), sensitivity_rows)
    fig, ax = plt.subplots(figsize=(9, 5))
    im = ax.imshow(grid, aspect="auto")
    ax.set_yticks(range(len(roughnesses)), labels=[str(x) for x in roughnesses])
    ax.set_xticks(range(len(stabilities)),
                  labels=["neutral" if x is None else str(x) for x in stabilities])
    for i in range(len(roughnesses)):
        for j in range(len(stabilities)):
            ax.text(j, i, f"{grid[i,j]:.2f}", va="center", ha="center", color="white" if grid[i,j] < (grid.min()+grid.max())/2 else "black", fontsize=9)
    ax.set(xlabel="Obukhov length L (m)", ylabel="Roughness length z0 (m)",
           title="Illustrative horizontal speed at 30 m; all profiles equal at 10 m")
    fig.colorbar(im, ax=ax, label="Horizontal speed (m/s)")
    fig.tight_layout()
    _save(fig, figures, "03_stability_roughness_sensitivity.png")

    # (4) gas-mixture density at specified, fixed T and p (not a weather forecast).
    q_values = np.linspace(0, .01, 150)
    p, temp = atmosphere.pressure(0), atmosphere.temperature(0)
    densities = [moist_air_density(p, temp, float(q)) for q in q_values]
    moist_rows = [{"specific_humidity_kg_kg": float(q),
                   "density_kg_m3": float(r),
                   "relative_change_from_dry_pct": float(100*(r/densities[0]-1))}
                  for q, r in zip(q_values, densities)]
    _write_csv(output_dir / "moist_air_density.csv", list(moist_rows[0]), moist_rows)
    fig, ax = plt.subplots(figsize=(8.5,5))
    ax.plot(1000*q_values, densities)
    ax.set(xlabel="Specific humidity (g water / kg moist air)",
           ylabel="Air density (kg/m³)",
           title="Ideal moist-air density at fixed ISA sea-level pressure and temperature")
    ax.grid(alpha=.2)
    fig.tight_layout()
    _save(fig, figures, "04_moist_density_at_fixed_p_t.png")

    # (5) a synthetic altitude table demonstrates veer and vertical input.
    # It is explicitly not a retrieved observation.
    table = TabulatedWindProfile(
        (5, 10, 20, 40),
        ((1, 2, .0), (4, 2, .0), (2, 5, .25), (-1, 6, .1)),
        "synthetic", "6g-stage3-illustrative-table-v1")
    z_tab = np.linspace(5, 40, 176)
    xyz = np.array([table(0, (0, 0, float(z))) for z in z_tab])
    tab_rows = [{"height_agl_m": float(z), "east_m_s": float(a),
                 "north_m_s": float(b), "up_m_s": float(c)}
                for z, (a,b,c) in zip(z_tab, xyz)]
    _write_csv(output_dir / "tabulated_synthetic_wind.csv", list(tab_rows[0]), tab_rows)
    fig, ax = plt.subplots(figsize=(8.5,5))
    ax.plot(z_tab, xyz[:,0], label="east")
    ax.plot(z_tab, xyz[:,1], label="north")
    ax.plot(z_tab, xyz[:,2], label="up")
    ax.axvline(5, color="gray", ls=":", lw=1)
    ax.axvline(40, color="gray", ls=":", lw=1)
    ax.set(xlabel="Height AGL (m)", ylabel="Wind component (m/s)",
           title="Synthetic tabulated field: altitude-dependent direction and vertical motion")
    ax.legend()
    ax.grid(alpha=.2)
    fig.tight_layout()
    _save(fig, figures, "05_synthetic_tabulated_wind.png")

    # (6) numerical-gradient consistency with differentiated similarity law.
    z_vals = np.linspace(1.5, 39, 160)
    deriv_rows = []
    for L in (100., -100.):
        for z in z_vals:
            dz = 1e-3
            f = lambda zz: np.log(zz/Z0) - businger_dyer_psi_m(zz/L)
            numeric = (f(z+dz)-f(z-dz))/(2*dz)
            theoretical = (1 + 6*z/L)/z if L > 0 else (1-19.3*z/L)**(-.25)/z
            deriv_rows.append({"height_agl_m": float(z), "obukhov_length_m": L,
                               "numeric_shear_per_m": float(numeric),
                               "analytical_shear_per_m": float(theoretical),
                               "absolute_difference_per_m": float(abs(numeric-theoretical))})
    _write_csv(output_dir / "wind_shear_identity.csv", list(deriv_rows[0]), deriv_rows)
    fig, ax = plt.subplots(figsize=(8.5, 5))
    for L in (100., -100.):
        subset = [r for r in deriv_rows if r["obukhov_length_m"] == L]
        ax.semilogy([r["height_agl_m"] for r in subset],
                    [max(r["absolute_difference_per_m"], 1e-16) for r in subset],
                    label=f"L = {L:g} m")
    ax.set(xlabel="Height AGL (m)", ylabel="Absolute derivative discrepancy (1/m)",
           title="Numerical derivative vs. Businger–Dyer analytic shear")
    ax.legend()
    ax.grid(alpha=.2)
    fig.tight_layout()
    _save(fig, figures, "06_numerical_derivative_check.png")

    # (7) explicitly bounded stochastic process; random seed is demonstrative.
    ar1 = bounded_gauss_markov_wind((0, 0, 0), (.4,.35,.15), 40, 10, 180, .05, seed)
    times = np.arange(0, 180.00001, .05)
    fluctuations = np.array([ar1(float(t), (0,0,10)) for t in times])
    for end, filename, title in [
        (180, "07_bounded_ar1_full.png", "Full 180 s seeded AR(1) series; time-only, not Dryden"),
        (15, "08_bounded_ar1_early.png", "Early-time detail of the same AR(1) series"),
    ]:
        fig, ax = plt.subplots(figsize=(11, 4.7))
        for j, label in enumerate(("east", "north", "up")):
            ax.plot(times, fluctuations[:,j], alpha=.8, lw=.65 if end == 180 else 1, label=label)
        ax.set_xlim(0, end)
        ax.set(xlabel="Model time (s)", ylabel="Wind fluctuation (m/s)", title=title)
        ax.legend(ncol=3)
        ax.grid(alpha=.2)
        fig.tight_layout()
        _save(fig, figures, filename)

    files = sorted(output_dir.glob("*.csv"))
    expected_figures = [
        "01_stability_comparison.png",
        "02_vertical_wind_separation.png",
        "03_stability_roughness_sensitivity.png",
        "04_moist_density_at_fixed_p_t.png",
        "05_synthetic_tabulated_wind.png",
        "06_numerical_derivative_check.png",
        "07_bounded_ar1_full.png",
        "08_bounded_ar1_early.png",
    ]
    assert all((figures / n).exists() for n in expected_figures)
    summary = {
        "status": "offline_equation_comparisons_not_gazebo_or_field_validation",
        "new_models_change_legacy_api": False,
        "surface_layer_valid_height_agl_m_illustrative_not_universal": list(VALID_RANGE),
        "reference_wind_enu_horizontal_m_s": list(REFERENCE_WIND),
        "surface_layer_businger_dyer_coefficients": {"stable": 6.0, "unstable": 19.3},
        "wind_30m_horizontal_m_s": {key: float(np.linalg.norm(model(0,(0,0,30))[:2]))
                                      for key,model in curves.items()},
        "dry_air_density_at_sea_level_kg_m3": float(densities[0]),
        "moist_air_density_at_sea_level_q_0p01_kg_m3": float(moist_air_density(p,temp,.01)),
        "max_wind_shear_derivative_absolute_difference_per_m": max(r["absolute_difference_per_m"] for r in deriv_rows),
        "synthetic_tabulated_profile_not_observed": True,
        "ar1_seed": seed,
        "ar1_generated_samples": len(times),
        "ar1_is_not_dryden_or_spatial_turbulence": True,
        "figure_count": len(expected_figures),
        "figure_names": expected_figures,
        "csv_sha256": {x.name: _file_digest(x) for x in files},
        "limitations": [
            "all examples use illustrative atmospheric conditions, not weather measurements",
            "monin-obukhov similarity assumes a restricted surface layer and cannot be extrapolated to 500m by default",
            "roughness, displacement, and obukhov length require site-specific evidence",
            "horizontal mean wind direction is constant in the similarity profile; veer is not represented",
            "vertical wind is independent input, not generated by similarity theory",
            "no spatial turbulence, atmospheric observations, or gazebo coupling is implemented",
        ],
    }
    (output_dir / "stage3_report.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("results/atmospheric_testbed/6g_stage3"))
    parser.add_argument("--seed", type=int, default=2026)
    args = parser.parse_args()
    print(json.dumps(run(args.output_dir, args.seed), indent=2))


if __name__ == "__main__":
    main()
