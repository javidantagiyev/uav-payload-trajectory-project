# SDP 6G — Atmospheric physics, audit stage 1

**Status:** Preliminary source-to-code audit, 20 November 2026. **Not** a claim of physical validation or completeness. Based on the combined repository snapshot used for 6F; compare against the current `sdev` before implementing changes.

## Scope and evidence hierarchy

1. **Literature statement:** a published equation and its stated applicability.
2. **Code implementation:** what the repository actually computes.
3. **Unit and numerical verification:** whether the implementation reproduces the chosen mathematical formulation.
4. **Simulator integration:** whether the formulation is applied to the actual simulated body.
5. **Physical validation:** agreement with independent atmospheric observations or laboratory measurements.

Successful code tests establish (3) at best. They do not automatically establish (4) or (5). All model comparisons should preserve input units, altitude reference, coordinate convention, time basis, and reported uncertainty.

## A. Existing model-to-source audit

| Model | Code location | Mathematical model / current assumption | Literature check | Status and limitation |
|---|---|---|---|---|
| Standard atmosphere | `src/physics/atmosphere.py:4–36` | `T(h)=T0-Lh`, `p(h)=p0(T/T0)^(g0/(R L))`, `rho(h)=p(h)/(R T(h))` | U.S. Standard Atmosphere (1976); NASA Glenn Research Center, *Earth Atmosphere Equation* | Equation structure and constants are consistent with a simplified, dry tropospheric ISA model. Non-ISA temperatures, humidity, and weather pressure are absent. Distinguish geopotential from geometric height if tighter accuracy is needed. |
| Altitude conversion | `src/physics/atmosphere.py:39–50` | The state height is AGL; ISA height is calculated as `ground_altitude + z` | ISA atmosphere uses reference altitude relative to sea level | Mapping is explicit but relies on a fixed ground datum; verify any simulator world's terrain elevation and frame. |
| Wind direction | `src/physics/wind_model.py:21–63` | Meteorological direction **from**, clockwise from north, is converted to ENU wind **toward** | WMO meteorological convention | Unit tests cover cardinal directions and inverse conversion. Record ENU/NED at simulator interfaces. |
| Power-law mean wind | `src/physics/wind_model.py:66–80` | `w(z)=w_ref(z/z_ref)^alpha`, default `alpha=1/7` | Mathisen et al. (2020), §2.3, eq. (5), uses `p=1/7`, following Touma (1977) | Functional form matches this literature example; `1/7` is not a universal exponent. Code also scales the **vertical** wind component, which the horizontal mean wind-profile citation does not automatically support. |
| Logarithmic mean wind | `src/physics/wind_model.py:83–106` | `w(z)=w_ref ln(z/z0)/ln(z_ref/z0)` above roughness height | Monin–Obukhov neutral surface-layer theory; surface roughness | Code reproduces a neutral log profile, but omits stability correction, displacement height, and layer validity. Extrapolating unchanged to hundreds of metres is not generally justified. Code also applies the multiplier to vertical wind. |
| Layered measured wind | `src/physics/wind_model.py:109–143` | Linear interpolation of ENU components between height samples; constant extrapolation | Standard numerical interpolation, not an atmospheric dynamical law | Reasonable transparent representation of sampled profiles, provided measurements, uncertainty and extrapolation bounds are documented. No temporal evolution unless layers are refreshed externally. |
| Gust | `src/physics/wind_model.py:154–176` | Finite-duration cosine **pulse**: `0.5*A*(1-cos(2*pi*(t-t0)/d))` | Must select a precise reference and required gust shape before claiming standards compliance | Implemented expression is internally coherent and continuous, but it is a pulse rather than an arbitrary measured gust. No spatial structure and no spectral validation. |
| Random fluctuations | `src/physics/wind_model.py:179–224` | Independent-axis stationary AR(1)/Gauss–Markov processes: `a=exp(-V dt/L)`, `u[k+1]=a*u[k]+sigma*sqrt(1-a^2)*N[k]` | NASA (1977), *A technique for simulating turbulence for aerospace vehicle flight simulation studies*, discusses Dryden spectra and integral scales | This is a specified Gauss–Markov model, **not** a validated three-axis Dryden/von Kármán realization. Code tests stationary variance and reproducible seeds, but not target spectral density, axis coherence, or spatial correlation. |
| Turbulent wind field | `src/physics/wind_model.py:227–250` | Same simulated time series is added at all spatial positions; time interpolation via `np.interp` | Atmospheric turbulence is generally spatially varying | A single temporally varying signal is **not** a 3D spatial wind field. `np.interp` holds endpoint values beyond generated duration; establish explicit out-of-range behavior. |
| Simulation wind coupling | 6E Gazebo `WindEffects` worlds vs Python wind functions | Gazebo applies its own simplified wind force model | Gazebo Harmonic `WindEffects` documentation and observed 6E experiments | Wind speed/direction response observed in the 6E rigid-body experiment; no demonstrated application of Python height-dependent or stochastic profiles inside Gazebo. |

## B. Preliminary code findings requiring decisions

**B1 — Vertical-component behavior.** `power_law_wind()` and `log_law_wind()` scale all three ENU components using a near-surface *mean horizontal* wind speed profile. Keep horizontal shear and vertical motions conceptually separate; treating the current behavior as physically verified is not justified. Do not silently change the existing public API without tests and an explicit compatibility decision.

**B2 — Height domains.** `power_law_wind` clamps at 0.1 m AGL; `log_law_wind` returns zero for `z <= z0`; layered wind uses constant extrapolation. These are **boundary policies**, not universal meteorological truths. Add tests for their effects and make the selected policy visible in experimental metadata.

**B3 — Turbulence validation.** The 6E sample lag-one correlation (~0.998) supports the AR(1) correlation parameter for one scenario. It does not demonstrate a Dryden spectrum, correct integral length scales in all components, physical spatial coherence, or stationarity of actual atmospheric wind.

**B4 — Repeated runs.** The nine 6F verified runs confirm recorder/batch functionality. If they use unchanged deterministic initial states, they test repeatability; they are not nine independent atmospheric realizations. Introduce explicit seed/realization management before estimating stochastic confidence intervals.

**B5 — Atmospheric density:** ISA output near 1.225 kg/m³ at sea level is a useful mathematical check, not evidence of actual weather. The simulation should carry separate `standard_atmosphere` and `observed_atmosphere` provenance.

## C. Verification experiments before expanding the physics

1. **Equation reference tests:** compare ISA temperature, pressure, density at several standard altitudes with reference tables; check units and elevation datums. Compare power/log formulas at reference height and limiting cases.
2. **Wind-profile domain study:** plot power and neutral-log profiles only across justified altitude ranges, mark surfaces/roughness, vary alpha and z0 as assumptions rather than known atmospheric facts, report differences.
3. **Stochastic diagnostics:** for AR(1), verify mean, variance, ACF across multiple lags, PSD against the exact AR(1) PSD (not Dryden), ensemble variability, run-length sensitivity, and seed independence.
4. **Temporal/spatial tests:** check gust continuity and derivatives at boundaries; test wind function at multiple times and locations; explicitly expose absent spatial coherence.
5. **Simulator interface tests:** controlled physical check in Gazebo that a configured wind field reaches the intended body/link; separately validate vector transformations; keep Python vs Gazebo wind engines distinct until interfaced and verified.
6. **Long-duration visualizations:** plots with SI units, full time axis, early transient inset, annotated model assumptions, repeated-seed ensembles only where stochastic inputs differ, and convergence diagnostics.
7. **Independent observation:** compare with public sounding/meteorological profiles where available; disclose measurement scale, terrain, reference height and uncertainty. Simulation agreement alone is not observation-based validation.

## D. Additional important domains to inventory

- **Thermodynamics:** virtual temperature; humidity effects on density; pressure variations; temperature inversions; diurnal and seasonal variability.
- **Atmospheric boundary layer:** roughness, displacement height, stability, low-level jets, turning of wind with height; limits of Monin–Obukhov similarity.
- **Wind variability:** wind shear, veer, vertical convection, spatially coherent gusts, integral time/length scales, anisotropy, intermittency, spectral and cross-spectral properties.
- **Flow interactions:** terrain and building wakes, obstacles, rotor-induced flows, proximity to surfaces, unsteady vortices; evaluate relevance before introducing CFD.
- **Measurement and assimilation:** wind observations, update frequency, time stamps, sensor accuracy, interpolation error, representation error, covariance/correlation.

This is an **inventory**, not a requirement to implement every effect or a statement that each is important in the studied regime. Rank by physical relevance, evidence, identifiability, and feasible validation.

## E. Literature verified for stage 1

- Mathisen, S. G., Leira, F. S., Helgesen, H. H., Gryte, K., & Johansen, T. A. (2020). *Autonomous ballistic airdrop of objects from a small fixed-wing unmanned aerial vehicle*. **Autonomous Robots** 44, 859–875. DOI: 10.1007/s10514-020-09902-3. See §2.3 eq. (5); 1/7-power example attributed to Touma (1977). Local file: `autonomous_ballistic_payload.pdf`.
- U.S. Standard Atmosphere (1976), NOAA/NASA/USAF. NASA/NTRS: https://ntrs.nasa.gov/archive/nasa%20/casi.ntrs.nasa.gov/19770009539.pdf ; see also NASA Glenn: https://www1.grc.nasa.gov/beginners-guide-to-aeronautics/earth-atmosphere-equation-metric/ .
- *Method for Estimation of Surface Roughness and Similarity Function of Wind Speed Vertical Profile*, **Journal of Applied Meteorology** 37 (1998). Log wind profiles require stability treatment beyond neutral conditions: https://journals.ametsoc.org/view/journals/apme/37/5/1520-0450_1998_037_0461_mfeosr_2.0.co_2.xml .
- KNMI: *Limitations and breakdown of Monin-Obukhov similarity theory for wind profile extrapolation under stable stratification* (2015): https://www.knmi.nl/kennis-en-datacentrum/publicatie/limitations-and-breakdown-of-monin-obukhov-similarity-theory-for-wind-profile-extrapolation-under-stable-stratification .
- NASA (1977). *A technique for simulating turbulence for aerospace vehicle flight simulation studies*: https://ntrs.nasa.gov/archive/nasa/casi.ntrs.nasa.gov/19780004071.pdf . NASA source identifies Dryden spectral forms, standard deviations and integral length scales; it does not establish that the repository AR(1) implementation is a Dryden model.

## F. Stage-1 exit conditions

Proceed with expanded atmospheric implementation only after the baseline model contract and assumptions are explicit and equations are cross-checked. Record any mismatch as an issue with severity and supporting evidence. Keep proposed model enhancements separate from fixes needed to reproduce the current mathematics. Do not report physical validity solely from passing pytest or Gazebo's qualitative wind response.
