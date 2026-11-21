# Package 6F: simulation-time experiments and research-grade reporting

## Purpose and scientific boundary

6F extends the **existing 6E Gazebo Harmonic inert-body environment matrix**. It collects fixed **simulation-time** windows, performs isolated repeat runs, retains run/world fingerprints, and produces chronological plots of position, free-flight fit diagnostics, and response differences. It is research *infrastructure*, not new aerodynamic physics, a true atmospheric wind field, or physical validation.

**What is controlled:** one generated SDF world per case, odometry publisher rate, requested elapsed simulation-time window, and number of repeats. Each repeat starts a fresh isolated Gazebo process. Every run records scenario parameters, SDF hashes, wall-clock runtime, recording timestamps, gaps, and data SHA-256.

**What is not yet controlled:** Gazebo stochastic seeds, physics substep scheduling after the final odometry record, and absolute alignment of first recorded odometry with world zero. The recorder reports the *first absolute simulator timestamp* so late starts are observable. Repeats on nominally deterministic cases are for reproducibility assessment—not independent Monte Carlo draws. The output is **simulated odometry**, not physical ground truth.

## Source and software literature

- Gazebo Sim Harmonic: world control with `/world/<world>/control` and `gz.msgs.WorldControl` (https://gazebosim.org/docs/harmonic/sdf_worlds/).
- Gazebo 8 OdometryPublisher: emits 3D pose and timestamped odometry; reporting cadence is configured in SDF (https://gazebosim.org/api/sim/8/classgz_1_1sim_1_1systems_1_1OdometryPublisher.html).
- Existing 6E matrix (`configs/environment_matrix.json`) and its SDF generator (`src/physics/environmental_matrix.py`) are **our configuration sources**. The model is Gazebo's simplified `WindEffects`; **it is not** our Python `power_law_wind`, `log_law_wind`, `layered_wind`, or a validated spectral turbulence model.

## Read before running

Use the same WSL Ubuntu 22.04 / Gazebo Harmonic environment already verified in 6E. Close separate PX4/Gazebo instances for clarity. Python analysis uses the SDP virtual environment; Gazebo Transport recorder uses `/usr/bin/python3` because the bindings were installed for system Python.

**Do not overwrite 6E files.** The 6F package is additive and uses its own `simtime_6f` output directory.

### 1. Prepare worlds and confirm tests

```bash
cd ~/projects/uav-payload-trajectory-project
source .venv/bin/activate
python experiments/prepare_environment_matrix.py
python -m pytest -q tests
```

### 2. Dry-run without starting Gazebo

```bash
python sim/gazebo/scripts/run_simtime_matrix.py \
  --cases baseline wind_east_4 wind_west_4 --repeats 3 --duration-s 3 --rate-hz 100
```

### 3. First live reproducibility experiment (3 cases × 3 runs)

```bash
python sim/gazebo/scripts/run_simtime_matrix.py --execute \
  --cases baseline wind_east_4 wind_west_4 \
  --repeats 3 --duration-s 3 --rate-hz 100
```

Each run writes into `results/environmental_testbed/simtime_6f/runs/<case>/run_<index>/`. The script requires the requested simulation-time coverage and checks sample gaps. A wall-clock timeout / incomplete sample limit is a **failure**, not a successful recording.

If the experiment is interrupted, existing run directories are intentionally protected from overwrite. Inspect failed statuses, then remove only a clearly failed run folder if you decide to rerun it. `--skip-existing` accepts only previously verified runs with matching parameters and CSV hashes.

### 4. Analyze and generate figures

```bash
python experiments/analyze_simtime_matrix.py
```

Outputs under `results/environmental_testbed/simtime_6f/analysis/`:

- `simtime_analysis.json`: complete status, run hashes, descriptive statistics, quality limits.
- `simtime_analysis.csv`: compact per-case comparison at 0.2 seconds.
- `figures/<case>/x_m_full.png`, `y_m_full.png`, `z_m_full.png`: long views in simulation seconds.
- `figures/<case>/*_early.png`: first 0.4 seconds, showing transient physics.
- `figures/<case>/horizontal_path.png`: 2D motion with correct length units.
- `figures/<case>/repeat_variability.png`: mean and **sample SD** among repeats; **not a confidence band**.
- `figures/<case>/effective_acceleration_diagnostic.png`: vertical quadratic-fit sensitivity to 0.12/0.18/0.24/0.30s windows, with configured gravitational acceleration drawn separately.
- `figures/wind_response_0p2s.png`: signed E/N displacement across recorded cases. This includes parameter combinations, so do not interpret the entire chart as a pure wind-speed relationship.

### 5. Extend durations and recording resolution

Try 5 seconds at 100 Hz, or 3 seconds at 200 Hz, **in separate fresh output directories** via `--output` to preserve comparisons. The maximum exported sample count is 20,000, including the first and terminal samples; the tool fails early if duration × rate exceeds its cap. Increasing the observation rate does **not** improve physics integration resolution: that is separately governed by `physics_step_s` in the 6E case matrix.

The inert body makes contact with the ground quickly. Extending a single falling-object scenario to 120 seconds mostly measures *post-contact stability*, not 120 seconds of aerodynamic free flight. For 30–120-second **X500 estimator drift** studies, use the established PX4/Gazebo recorder and extend its experiment-duration protocol in a separate iteration. Never label PX4 local estimates as truth before frame and clock calibration.

## Interpretation gates

1. **Numerical verification:** accuracy against mathematical reference cases under controlled assumptions; not proof of real-world accuracy.
2. **Simulator mechanism:** changing wind must change observed signed motion consistently; repeatability alone does not validate physical wind-force magnitude.
3. **Statistical repeatability:** deterministic runs can be compared via maximum between-run differences. Do not claim statistical confidence intervals or Monte Carlo convergence without controlled independent random inputs.
4. **Physical validity:** wind force, aerodynamics, and contact dynamics require independent validation. Gazebo's `WindEffects` force scaling is not equivalent to the coefficient of drag, density, or frontal area.
5. **Height fits:** `g_effective` from observed height includes all modeled forces and biases. It is not a direct gravimeter. The previously observed ~8.29 m/s² result remains an open diagnosis, not an inferred gravity setting.

## Limitations requiring follow-up

- Precise WorldControl **stepping** and output barriers, rather than a continuously unpaused simulator, would reduce temporal overshoot and message-backlog risks. 6F bounds *recorded simulation time* and gaps; it does not promise exact physics stopping at the final timestamp.
- No random seed orchestration or independent turbulence realizations: intentional restriction rather than fabricated stochastic studies.
- No Gazebo coupling to altitude-dependent wind or Dryden/von Kármán turbulence.
- No guaranteed truth/measurement separation for noisy odometry; dedicated simulator truth vs sensor topic is required.
- Cross-case normalization, common initial-state alignment, and independent model-form validation remain future experiments.

## Next phase: 6G atmospheric model audit

Read primary meteorological and turbulence references; inventory lapse-rate, stability, shear, surface roughness, spatial coherence, gust spectra, density variability, and boundary-layer assumptions. For each model record its equation, units, validity range, reference, source implementation, numerical validation, and simulator coupling status **before adding more atmospheric components**.
