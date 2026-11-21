# Package 6G, stage 3 — bounded atmospheric-model extensions and comparisons

**Evidence level:** equation-to-implementation verification and illustrative synthetic model comparisons. No field validation, no PX4/Gazebo coupling, no certification of atmospheric realism. These modules are **additive** and do not replace `src/physics/wind_model.py` or `src/physics/atmosphere.py`.

## Reproduction

From the repository root, after unzipping the package:

```bash
source .venv/bin/activate
python -m pytest -q tests
python experiments/compare_atmospheric_extensions.py --seed 2026
```

Default outputs under `results/atmospheric_testbed/6g_stage3/` include `stage3_report.json`, five CSV tables and eight PNG figures. All sample parameters are **illustrative and synthetic**, not inferred from local weather or validated for a particular flight altitude.

## Literature-first equation inventory

### 1. Atmospheric stability, roughness, and displacement height

**Source:** Year-long buoy-based observations of the air–sea transition zone off the US west coast (2023), *Earth System Science Data* 15, 5667–5700, Appendix A Eq. (A1), reproducing Businger–Dyer momentum stability corrections: https://essd.copernicus.org/articles/15/5667/2023/ . Also see Monin–Obukhov mean-wind equations in *Wind Energy Science* (2024): https://wes.copernicus.org/articles/9/1727/2024/ .

Define effective height `s = z_AGL - d`, aerodynamic roughness length `z0`, and Monin–Obukhov length `L`:

```
G(s; z0, L) = ln(s/z0) - psi_m(s/L) + psi_m(z0/L)
U_h(z) = U_h(zref) * G(z-d; z0,L) / G(zref-d; z0,L)
```

where the correction is explicitly zero for the neutral case `L=None`, and the following **specific Businger–Dyer formulation** is used:

```
psi_m(zeta) = -6*zeta,                                  zeta >= 0 (stable)
x = (1 - 19.3*zeta)^(1/4),                              zeta < 0  (unstable)
psi_m(zeta) = 2 ln((1+x)/2) + ln((1+x*x)/2)
              - 2 atan(x) + pi/2,                      zeta < 0
```

The small reference correction `psi_m(z0/L)` is retained, guaranteeing zero velocity at the roughness-height boundary under this mathematical form. The relative profile is normalized by the specified horizontal speed at `zref`; it does not independently estimate friction velocity.

**Code:** `src/physics/atmospheric_extensions.py:businger_dyer_psi_m`, `monin_obukhov_horizontal_wind`.

**Model contract:** `reference_horizontal=(east,north)` only; the vertical component is a separate scalar or `(t,position)` callback. The user **must** supply `valid_height_range=(lo,hi)` and the model raises outside the range rather than silently extrapolating to hundreds of metres. Height is **AGL**; temperature-pressure height in ISA is **AMSL** and must not be confused with it.

**Assumptions:** horizontally homogeneous stationary surface layer; direction of *mean horizontal wind* is held constant with height; the field contains no wind veer, time-varying mean direction, rotating Ekman layer, urban wakes, or spatial gradients. `d`, `z0`, and `L` require local measurements/justification. The 1–40 m example domain is **not a universal physical validity rule**. Similarity-theory assumptions often fail above the atmospheric surface layer, particularly under stable stratification. See the 2024 Wind Energy Science paper cited above and Optis, Monahan and Bosveld (2015), https://doi.org/10.1002/we.1883 .

**Verification:** exact published `psi_m` form; neutral `L=None` must reproduce the legacy *horizontal* log-law profile when `d=0`; analytical shear identity `d/ds[ln(s/z0)-psi_m(s/L)] = phi_m(s/L)/s`, with `phi_m=1+6*s/L` stable and `phi_m=(1-19.3*s/L)^(-1/4)` unstable; normalization at `zref` and strict bounds; stable/neutral/unstable parameter sweeps. This checks equations only.

### 2. Moist-air density at specified pressure and temperature

**Source:** Penn State METEO 300, gas laws and virtual temperature (mass-specific humidity and gas-mixture derivation), https://courses.ems.psu.edu/meteo300/node/644 ; see also the gas-mixture treatment of atmospheric measurements in *Atmospheric Measurement Techniques* 15, 95–109 (2022): https://amt.copernicus.org/articles/15/95/2022/amt-15-95-2022.html .

With `q = mass water vapour / mass total moist air` (kg/kg), approximate ideal-gas constants `Rd=287.05 J/(kg K)` and `Rv=461.5 J/(kg K)`:

```
rho = (p/T) * [ (1-q)/Rd + q/Rv ]
Tv = T / [ 1-(1-Rd/Rv)q ]
rho = p / (Rd * Tv)
```

The function uses the **ideal-mixture relation**, exact within that simplified gas model, rather than the frequently used truncated approximation `Tv ≈ T(1+0.61q)`. `q=0` recovers dry-air ideal-gas density; for fixed p and T, increasing vapour fraction decreases density.

**Code:** `moist_air_density(p, T, q)`.

**Limitations:** no saturation, condensation, liquid water, heat exchange, thermodynamic profile, moisture variation with height, or non-ideal compressibility. The supplied p, T and q must come from measured/specified data; applying constant moisture at altitude is not an atmospheric forecast. The plot uses q from 0–0.01 at fixed ISA sea-level p and T as an illustrative algebraic sensitivity study.

### 3. Tabulated altitude profiles with provenance

**Source:** Standard numerical linear interpolation. **No claim of a physical governing law.** The WMO Guide to Instruments and Methods of Observation, Volume I, Chapter 5, documents surface wind observation practice: https://community.wmo.int/site/knowledge-hub/programmes-and-initiatives/instruments-and-methods-of-observation-programme-imop/guide-instruments-and-methods-of-observation-wmo-no-8-0 .

**Code:** `TabulatedWindProfile(heights_agl_m, winds_enu_m_s, provenance, source_id)`. Each ENU component is independently interpolated between supplied altitudes; no extrapolation. The source provenance must be `synthetic`, `observed`, or `reanalysis`, and requires an explicit nonempty `source_id`. **Labeling as observed is not by itself validation**; checking instrument provenance, calibration, location, timestamp, height datum and uncertainty remains necessary. The example is marked `synthetic`, and permits wind veer via changing E/N components as well as independently observed/specifed vertical wind.

### 4. Bounded time-only Gauss–Markov

**Source:** The existing repository's exact discrete AR(1) process, already equation-verified in stage 2, not a Dryden spectrum. `bounded_gauss_markov_wind` is a thin compatibility wrapper that preserves the process and interpolates within its declared **duration**. It now **raises outside the duration** rather than silently holding the last random fluctuation. The same random temporal series is still shared at all positions, so it **does not represent spatial turbulence**.

### 5. Calm-wind direction

**Code:** `meteorological_direction_or_none`. A zero horizontal wind has **no physically defined direction**. This new API returns `None` when magnitude is below the declared threshold, retaining the original API unmodified.

## Scenario plots and what they mean

1. `01_stability_comparison.png`: horizontal mean wind versus AGL height for stable, neutral, unstable assumptions normalized at 10m.
2. `02_vertical_wind_separation.png`: old incorrectly extrapolated vertical component versus separately specified vertical motion.
3. `03_stability_roughness_sensitivity.png`: speed at 30m under **illustrative** roughness and L assumptions; demonstrates input dependence, not model fidelity.
4. `04_moist_density_at_fixed_p_t.png`: ideal-gas moisture sensitivity at one chosen pressure and temperature.
5. `05_synthetic_tabulated_wind.png`: separate ENU interpolation of a **synthetic** altitude table, including wind-direction change.
6. `06_numerical_derivative_check.png`: independent finite-difference and analytic wind-shear comparison.
7. `07_bounded_ar1_full.png`: full 180s stationary temporal stochastic example, with seed and temporal limitations stated.
8. `08_bounded_ar1_early.png`: early 15s view of the same stochastic realization.

## Compatibility, remaining issues, and gate to next phase

- All new functions live in `atmospheric_extensions.py`; existing physical models and Gazebo worlds are **not modified**.
- The original `wind_model.power_law_wind()` and `.log_law_wind()` still scale all three ENU components. Legacy scripts still use that old contract. **Do not claim that Stage 3 has corrected the production simulator.**
- The surface-layer correction is not automatically valid to a 500m altitude. Avoid extrapolation without measured profiles, independent validation, and a justified atmospheric boundary-layer model.
- The AR(1) wrapper remains time-only; realistic 3D turbulence, Dryden/von Kármán spectral simulation, anisotropic coherence, gust-front dynamics, boundary-layer depth, terrain/building wakes, real meteorological observations, and wind-to-Gazebo integration are not completed.
- Next: obtain public observed wind profiles with documented altitude and timing, compare neutral/MOST/tabulated methods against those observations, quantify generalization error, then define a wind-field-to-Gazebo interface and validate that actual force output corresponds to injected vector and coefficients.

**Research rule:** reject the use of synthetic model agreement as evidence of real-world atmospheric accuracy. Preserve conditions, units, failure cases, and provenance in experiment artifacts.
