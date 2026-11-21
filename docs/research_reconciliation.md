# Repository reconciliation and research contracts

## Baseline and scope

This review uses the supplied `main` ZIP snapshot and the locally available Package 6A/6C
add-ons. It is not a comparison against live Git history. The changes in this package are
additive and do not replace existing numerical solvers, uncertainty methods, or the teammate's
atmosphere and wind implementations. Test success is software verification, not field validation.

## Ownership and interface map

| Concern | Existing implementation | Research contract |
|---|---|---|
| Base point-mass dynamics | `src/physics/ballistic_model.py` | `state_derivative` is the shared 6-state RHS; `model_rhs` delegates to it |
| Validated constant parameters | `src/physics/parameters.py` | `Body` and `Atmosphere` use SI units and world ENU vectors |
| Numerical steppers | `src/physics/integrators.py` | `euler_step` and `rk4_step` are the common steppers |
| Fixed-duration traces | `src/physics/trajectory.py` | Keeps the complete trajectory at a fixed endpoint |
| Ground-event integration | `src/physics/simulation.py` | Different event-based API; not interchangeable with fixed-duration results |
| Gravity reference | `src/physics/analytic.py`, `analytical.py` | First provides time-series states; second solves a scalar boundary-time problem |
| Atmosphere | `src/physics/atmosphere.py` | ISA altitude is above mean sea level; local height requires a declared ground elevation |
| Wind profiles | `src/physics/wind_model.py` | Meteorological directions are *from* directions clockwise from north |
| Uncertainty, fixed-time | `src/physics/uncertainty.py`, `robustness.py` | Scenario-driven, declared uniform/beta/triangular assumptions |
| Uncertainty, event-based | `src/physics/monte_carlo.py` | Different Gaussian assumptions and event-based outputs; not directly comparable |
| Generic rigid-body telemetry | `src/physics/simulation_audit.py` | Velocity frame must be explicit, startup artifacts preserved and flagged |
| Gazebo/PX4 records | `src/physics/multicopter_telemetry.py` | Gazebo world pose and PX4 local estimate have different origins and clocks until calibrated |
| Stationary diagnostics | `src/physics/stationary_evaluation.py` | Mean-centered jitter only; provenance, validity, resets and motion must be checked |

## Confirmed architecture facts

- The common point-mass RHS and validated-parameter adapter agree numerically across randomized test cases.
- Event-based and fixed-duration integration answer different questions; their outputs and stopping rules must be labeled, not implicitly compared.
- A body-to-world rotation defined for forward-left-up is **not** the PX4 forward-right-down body convention. A frame transform and orientation definition are required before integration.
- Gazebo rigid-body contact dynamics and PX4 multirotor dynamics do not yet validate the separate aerodynamic point-mass assumptions.
- An independent simulator implementation does not by itself provide physical validation against measured real-world trajectories.

## Open issues requiring explicit research decisions

1. **Uncertainty parameter semantics.** `src/physics/monte_carlo.py` draws Gaussian `release_delay` around zero, allowing negative samples; the accompanying prose calls it a *late* delay. This is inconsistent if the quantity represents a strictly nonnegative latency. Decide between a signed timing error and a nonnegative latency and document the choice. Do not silently clip or modify data.
2. **Gaussian truncation.** Sampling positive mass, area, density and drag parameters via clipping introduces probability mass at the clipping threshold, which is different from sampling a true truncated normal. Quantify the influence if this model is used for inference.
3. **Different uncertainty families.** The event-based Gaussian study and the fixed-time uniform/triangular/beta study cannot be interpreted as an apples-to-apples algorithm comparison. Specify matched scenarios, information assumptions, and outcomes before comparing.
4. **Atmosphere and altitude.** `density_function(ground_altitude)` uses above-sea-level altitude. Cross-module experiments must explicitly distinguish mean-sea-level altitude from local height; standalone `Atmosphere` holds constant density.
5. **Wind-profile range.** A power-law or log-law field is an assumption, not empirical evidence that a profile holds throughout the modeled domain. Record reference height, roughness, altitude range, and measured basis.
6. **Orientation and reference frames.** Teammate release-state code assumes an ENU-aligned forward-left-up body frame at zero angles. PX4 and Gazebo use different, explicit frame conventions; do not reuse angles or offsets without a documented transform.
7. **Model fidelity.** 3-state position plus 3-state velocity is not 6-DOF rigid-body dynamics. Gazebo simulates rotation and inertia, but orientation-dependent aerodynamic coefficients and aerodynamic torques have not been experimentally calibrated.
8. **Timestamp provenance.** Gazebo pose samples are labeled with Gazebo simulation time; PX4 ULog `timestamp` is labeled with PX4 time. Numeric overlap and SITL lockstep make correspondence plausible but are not proof of exact synchronization.
9. **Estimator validity and resets.** The existing 6C CSV has validity bits but no reset history. The new stationarity evaluator reads reset counters from its original ULog when supplied; without that log, output is provisional.
10. **Physical datasets.** There are no independently measured trajectory and environmental observations in these current examples. No centimeter-scale physical error claim follows from the simulation-only baseline.
11. **Documentation drift.** `docs/model_specification.md` currently describes the original fixed-duration baseline and its exclusions. It is not an exhaustive description of all new modules. The root `README.md` has an unfinished status section; update it through a normal reviewed PR rather than overwriting teammate edits.
12. **Result provenance and reproducibility.** Preserve the simulator version, model configuration, source-log hash, scenario parameters, coordinate frames, timing methods, and software revision for each independent session. Never treat time samples from one run as independent experimental replicates.

## Evidence thresholds

- **Numerical verification:** mathematical reference, convergence, invariants, automated tests.
- **Simulation consistency:** independently produced simulator states, recorded settings, correctly qualified time and frame relationships.
- **Estimator stability:** valid stationary window, reset history, centered dispersion, temporal drift, and block-based uncertainty intervals.
- **Physical validation:** independent measurements, calibrated parameters, instrument uncertainty, and held-out evaluation conditions.

Keep this document up to date when the model assumptions change. Passing tests is necessary but not sufficient to claim experimental validity.
