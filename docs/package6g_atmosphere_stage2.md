# Package 6G — Atmospheric model verification, stage 2

**Evidence status:** independently checked mathematical contracts, not real-atmosphere validation, numerical flow validation, or a Gazebo/PX4 wind-coupling test. This package is additive: it does not change the original physics equations or the existing simulation pipeline.

## How to run

From the project root:

```bash
source .venv/bin/activate
python -m pytest -q tests
python experiments/verify_atmospheric_models.py --duration-s 900 --step-s 0.05 --seed 2026
```

Default output: `results/atmospheric_testbed/6g_stage2/`, excluded from version control. The default run generates 9 figures, tabular diagnostics, a structured JSON report, and input/output CSV digests. Shortening the experiment reduces statistical precision; longer runtime does not make a synthetic field physically validated.

## Literature, equations, tests, and claims

| Model | Independent source | Equation being verified | Verification | Scope and restrictions |
|---|---|---|---|---|
| Dry tropospheric standard atmosphere | *U.S. Standard Atmosphere (1976)*, example table hosted by New Mexico State University | `T=T0-Lh`, `P=P0(T/T0)^(g/(R L))`, `rho=P/(R T)` | Published anchors at 0, 1000, 2000m for temperature, pressure, density; finite-difference hydrostatic balance | Standardized dry reference, not observed humidity/temperature/pressure; the table and code use slightly different rounded constants |
| Power-law mean wind | Mathisen et al. (2020), §2.3, eq. (5), citing Touma (1977) | `U(z)=Uref(z/zref)^alpha`, with example `alpha=1/7` | Independent analytic factor for several heights and component checks | Empirical near-surface horizontal mean wind; exponent depends on atmospheric and surface conditions |
| Neutral logarithmic wind | WMO *Guide to Meteorological Instruments and Methods of Observation*, section on urban wind observations (neutral case); Optis et al. (2015) | `U(z)/Uref=ln(z/z0)/ln(zref/z0)` in the idealized neutral, zero-displacement case | Independent analytic factors; reference normalization, roughness policy | Validity depends on surface-layer assumptions, terrain, roughness, atmospheric stability; caution extrapolating to hundreds of metres |
| Layer interpolation | Standard piecewise linear numerical interpolation | `U(z)=(1-a)Ui+aUi+1` | Exact midpoint and extrapolation-policy tests | The interpolation is not itself atmospheric physics; no spatial or temporal dynamics inferred |
| One-cosine gust | Implemented pulse definition, not established standard gust certification | `u(t)=u_base+A/2[1-cos(2pi(t-t0)/d)]` for its window | Boundary values, maximum amplitude, smooth boundary derivatives | Standalone temporal pulse; no spatial gust coherence or measured turbulence |
| Stationary Gauss–Markov / AR(1) turbulence | Exact discrete-time AR(1) algebra (not Dryden) | `u[k+1]=a*u[k]+sigma*sqrt(1-a²)*eps[k]`, `a=exp(-V dt/L)` | Theoretical-vs-sample ACF, discrete AR(1) spectrum vs Welch estimate, PSD-integrated variance, seed repeatability | Independent axes, time-only frozen spatial field, endpoint-held extrapolation, no validated Dryden/von Kármán spectrum |

**Reference:** NMSU USSA1976 rounded table: https://atmos.nmsu.edu/planetary_datasets/earth_temppres.html

**Reference:** Mathisen et al., *Autonomous ballistic airdrop of objects from a small fixed-wing unmanned aerial vehicle*, *Autonomous Robots* 44 (2020), §2.3 eq. (5), DOI: 10.1007/s10514-020-09902-3. See `autonomous_ballistic_payload.pdf` in the research materials.

**Reference:** KNMI summary of Optis, Monahan, and Bosveld, *Limitations and breakdown of Monin–Obukhov similarity theory for wind profile extrapolation under stable stratification*, *Wind Energy* (2015), DOI: 10.1002/we.1883: https://www.knmi.nl/kennis-en-datacentrum/publicatie/limitations-and-breakdown-of-monin-obukhov-similarity-theory-for-wind-profile-extrapolation-under-stable-stratification

**Reference:** WMO urban wind-profile measurement guidance: https://www.weather.gov/media/epz/mesonet/CWOP-WMO8.pdf

## Exact AR(1) spectral derivation

For a stationary discrete AR(1) process with `a=exp(-V dt/L)` and marginal variance `sigma²`, the white innovation variance is `sigma²(1-a²)`. Its two-sided frequency-domain power spectral density is

```
S2(f) = sigma²(1-a²) dt / (1+a²-2a cos(2 pi f dt))
```

where `f` lies within the Nyquist band. Double this for the one-sided density at positive interior frequencies, but not at zero or Nyquist. Its integral over the one-sided band is `sigma²`. The experimental script verifies this formula directly, compares an empirical Welch PSD to the *AR(1)* target, and never labels it a validated Dryden spectrum.

Autocorrelation at lag `k`: `R(k)/R(0)=a^k`. The nominal integral-correlation time is `L/V`. A first-order effective sample-size approximation for the sample mean is `N_eff≈N(1-a)/(1+a)`; use cautiously because finite sample windows and detrending affect the estimate.

## Findings not silently corrected

1. **Vertical-wind misuse:** current `power_law_wind` and `log_law_wind` scale the upward component as well as horizontal wind, despite their literature motivation being horizontal *mean* wind. This stage only documents and tests the actual behavior; do not silently change existing wind APIs.
2. **Low-height domain:** power law clamps to 0.1m, logarithmic wind is zero for `z<=z0`, and layered wind clamps outside measured layers. These are code boundary policies, not universal physical boundary conditions.
3. **No spatial turbulence:** `turbulent_wind(t,p1)==turbulent_wind(t,p2)` when the base is spatially constant, regardless of distance. This is a shared time series rather than a 3D turbulence field.
4. **Temporal endpoint:** turbulent wind holds its last simulated perturbation value outside the series duration, because `numpy.interp` clamps endpoints.
5. **Calm wind direction:** the direction of a zero horizontal wind has no physical definition, although the current numeric function returns an arbitrary degree value.
6. **Hydrostatic agreement:** numerical consistency is not validation of real atmospheric profiles. The ground elevation datum must be recorded separately from height above ground.

## Nine figures

`01_isa_density.png` — dry ISA reference and tabulated anchors.

`02_mean_wind_profiles.png` — assumed power and neutral-log horizontal shear versus altitude.

`03_vertical_component_contract.png` — explicit vertical-component scaling finding.

`04_1_cosine_gust.png` — temporal pulse shape, onset, peak, termination.

`05_ar1_full_duration.png` — complete three-axis synthetic time series.

`06_ar1_early_detail.png` — zoomed early-time fluctuations.

`07_ar1_acf.png` — empirical versus expected lag correlation.

`08_ar1_psd.png` — synthetic spectrum versus exact AR(1) spectrum (not Dryden).

`09_ar1_running_mean.png` — long-run convergence diagnostic.

## Required before stage 3

1. Decide a backward-compatible wind API separating horizontal mean wind from independently specified vertical motion.
2. Select a documented surface-layer validity envelope and height datum rather than extrapolating the neutral log law indefinitely.
3. Add measured or site-specific profiles as a separate input/provenance path; synthetic wind is not measured weather.
4. Specify physically appropriate temporal/spatial turbulence and atmospheric-stability models from primary literature before implementing them.
5. Verify the actual wind vectors and forces injected into Gazebo, not just the Python field outputs.

The correct scientific conclusion from these tests is that **the implemented simplified equations match their declared mathematical forms**, not that the selected simplifications are accurate for every environmental condition.
