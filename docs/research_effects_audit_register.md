# Scientific effects audit register (initial, not complete)

This register tracks relevant physical and numerical effects. A listed effect is **not** a claim it has been modeled, is significant, or needs immediate implementation. It prevents missing effects while protecting the research from indiscriminate model complexity.

| Research domain | Candidate effects and dependencies | Present evidence | Priority and next verification |
|---|---|---|---|
| Simulation clock | wall time, simulation time, initial sample alignment, update rate, dropped messages | 6E wall-clock recorder; 6F simulation-time recorder with gap gates | 6F: controlled 3-run lab, inspect real timestamps |
| Discretization | Euler/RK4, Gazebo step, event handling, interpolation, solver convergence | Existing offline comparisons and step-size scenarios | 6F: convergence against exact free fall; compare time resolutions |
| Gravity / coordinate frames | ENU/NED, body/world, gravity vector, non-inertial effects | existing body and PX4 integration tests | 6F: explain effective acceleration difference without guessing cause |
| Wind field | speed/direction, profile with height, wind shear, vertical wind, gust time history | Python power/log/layer/gust; Gazebo uniform WindEffects | 6G: references, validity assumptions, link to simulator |
| Turbulence | temporal autocorrelation, integral time scale, spatial coherence, spectra, anisotropy | first-order Gauss–Markov only | 6G: compare Dryden/von Kármán against spectral requirements |
| Stratification | pressure, temperature, density, lapse rate, thermal stability | ISA density calculation | 6G: validity domain and non-ISA conditions |
| Surface / terrain | roughness, ground boundary layer, obstacles, building-induced flows, microbursts | simple logarithmic wind; ground contact model | 6G: applicability, not universal parameters |
| External flow | propwash, wake interference, time-varying air-relative motion | not separately validated | 6G/6H: establish whether relevant in studied regime |
| Aerodynamics | Reynolds / Mach regimes, drag coefficient, reference area, orientation, lift/side-force | 3-DOF quadratic drag in Python | 6H: dimensions, correlations, calibration, range |
| 6-DOF rigid body | inertial tensor, CG offset, angular rates, moments, tumbling | Gazebo box with inertias/odometry | 6H: independent rotational verification |
| Contact | collision shape, restitution, friction, numerical penetration, settling | 6E contact matrix | 6H: do not interpret post-contact as free-flight |
| Sensors | IMU/barometer/GNSS/EKF noise, latency, resets, bias, correlated errors | 6A–6D telemetry and stationary jitter | 6J: align clocks/origins and test against truth |
| Uncertainty | bounds, distributions, correlations, model-form error, stochastic seeds, reproducibility | Packages 4/5, teammate Monte Carlo; 6F repeats not seeded | 6I: separation of epistemic and aleatory sources |
| Statistics | means, percentiles, bootstrap validity, effective sample size, multiple comparison | Package 6D block-bootstrap, 6F descriptive SD | 6I: quantitative calibration and convergence |
| External validation | wind observations, aerodynamic measurements, independent numerical references | literature reference only; simulation tests | 6K: no physical-accuracy claims before independent evidence |

Principle: **literature → equation and assumptions → code audit → controlled tests → statistics → limitations**. Domain completion requires explicit evidence on every step, not merely the presence of an implementation.
