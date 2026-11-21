# Environmental simulation screening — package 6E

## Purpose

This stage establishes *controlled, observable* environmental experiments for the Gazebo Harmonic rigid-body testbed. The objective is to discover which parameters affect the simulated dynamics, whether the effects are numerically repeatable, and whether the simulator has implemented the requested physical mechanism. It is not physical validation, release-optimization research, or evidence that a simulator reproduces outdoor conditions.

The existing 3-DOF Python model, expanded atmosphere / wind implementations, and 6-DOF Gazebo models remain separate, with their distinct assumptions made explicit.

## Implemented experiment matrix

`configs/environment_matrix.json` specifies 20 simulations using one-factor-at-a-time screening or explicitly labeled paired wind-factor changes:

| Group | Parameters changed | Mechanism under test |
| --- | --- | --- |
| Wind magnitude and vector | 2, 4, 8 m/s east; 4 m/s west/north; diagonal; 1 m/s upward | Gazebo `WindEffects`, if loaded and applied |
| Wind-force scaling | 0.5 and 2.0 with 4 m/s east | Sensitivity of the *simulator's approximation*, not aerodynamic drag coefficient |
| Gravity | 9.70 and 9.95 m/s² | Gazebo world gravity |
| Mass / inertia | 0.6 and 2 kg | Body mass and homogeneous-box inertia tensor |
| Orientation | Level initial attitude | Contact response and body orientation |
| Surface interaction | Lower friction, higher restitution | Contact behavior (engine-dependent) |
| Integration | 0.5 and 2 ms steps | Numerical integration / stability |
| Odometry | Gaussian noise 0.01 | Measurement contamination, **not** physics ground truth |

All other baseline values are recorded. The actual wind-force and contact response are implementation-dependent and require inspection of simulator output. A generated SDF file alone **does not constitute a successful runtime test**.

## How the world is constructed

`src/physics/environmental_matrix.py` reads the verified baseline SDF, changes only controlled fields, inserts the built-in Gazebo WindEffects plugin, and enables wind on the dynamic link. It updates all three principal moments of inertia whenever mass changes, assuming a homogeneous rectangular body:

$$I_{xx}=\frac{m}{12}(b^2+c^2),\quad I_{yy}=\frac{m}{12}(a^2+c^2),\quad I_{zz}=\frac{m}{12}(a^2+b^2).$$

The SDF records a world-space ENU wind vector in m/s. Gazebo's built-in wind model applies a simplified mass- and relative-velocity-based force approximation. It is **not** the quadratic $\frac12\rho C_D A |v_r|v_r$ model and **not** a calibrated 6-DOF aerodynamic model. The baseline for this study deliberately includes WindEffects with zero wind. It is not identical to the original rigid-body world, which did not include that system.

The existing Python `wind_model.py` implements height-dependent power/log/layered profiles, discrete gusts, and a first-order Gauss–Markov disturbance. None of these is injected into Gazebo by this package. In particular, do not interpret a Gazebo uniform-wind run as an evaluation of the Python altitude-dependent wind model. An independently developed plugin or coupling layer would be needed for that claim.

## Workflow in WSL

Use the current SDP checkout and activate `.venv` for research scripts:

```bash
cd ~/projects/uav-payload-trajectory-project
source .venv/bin/activate
python experiments/prepare_environment_matrix.py
python experiments/wind_atmosphere_diagnostics.py
python -m pytest -q tests
```

Generate a dry-run plan **without starting Gazebo**:

```bash
python sim/gazebo/scripts/run_environment_batch.py
```

Perform only the first **two** headless runs, with PX4 and other Gazebo windows closed:

```bash
python sim/gazebo/scripts/run_environment_batch.py --execute --cases baseline wind_east_4
```

The runner uses Ubuntu system Python for Gazebo bindings, its own `GZ_PARTITION` for isolation, starts each world paused, subscribes to odometry, unpauses through the official world-control service, and tears down the server after recording. It writes per-run diagnostic logs and explicit failure statuses. If the first two runs succeed, the complete 20-case matrix can be executed with `--all --execute`; it is not necessary to run all at once on a 16 GB laptop.

```bash
python experiments/evaluate_environment_matrix.py
```

For optional visual inspection of a generated world, stop the batch and open one world directly using the already-tested NVIDIA/WSLg environment:

```bash
MESA_D3D12_DEFAULT_ADAPTER_NAME=NVIDIA QT_QPA_PLATFORM=xcb \
  gz sim -v 4 results/environmental_testbed/local_run/worlds/env_wind_east_4.sdf
```

The generated worlds and recording files are under `results/environmental_testbed/local_run/`. Do **not** commit gigabytes of raw runs. Preserve representative manifests, figures, summaries, and scenario hashes before sharing results.

## Quality gates

The evaluator in `src/physics/environmental_evaluation.py` verifies finite values, increasing timestamps, approximately unit quaternions, early initial-state coverage, and enough free-flight samples. It estimates free-flight acceleration from a quadratic fit to height and samples horizontal motion at elapsed 0.2 seconds. A difference between two scenarios is reported as *observed*, not automatically attributed to wind.

If the baseline is missing, comparison is disabled. If wind produces no detectable change, the report says so. It never invents results for unrun scenarios. Contaminated odometry must not be used as physics ground truth.

The experiment is **screening**, not exhaustive coverage, global sensitivity analysis, measured external validation, or a calibration of physical aerodynamic coefficients. One-factor-at-a-time studies can miss interactions. After establishing that the simulator forces are implemented correctly, extend to designed factorial/space-filling experiments, repeated random seeds, correlated environmental inputs, and independent calibration measurements.

## Subsequent research stages

1. Audit the X500 `windy` world and model link settings; prove effective wind coupling before collecting wind-response statistics.
2. Obtain **6-DOF** simulated ground truth and estimator records with verified common origins and timing.
3. Couple altitude/time-varying winds and turbulence to the simulator through a separately verified force model. Compare its response with independent reference experiments under matched configurations.
4. Add sensor models, atmospheric properties, aerodynamic parameter variation, terrain / contact variability, integrator diagnostics, and randomized repeatability tests. Preserve changes to physical assumptions and numerical tolerances as independent experimental variables.
5. Use nested uncertainty studies to distinguish aleatory disturbances, model-form uncertainty, and calibration uncertainty. Hold out entire scenario families when evaluating learned models.

## Primary implementation references

- Gazebo Sim 8 `WindEffects`: https://gazebosim.org/api/sim/8/classgz_1_1sim_1_1systems_1_1WindEffects.html
- Gazebo world-control service: https://gazebosim.org/api/sim/8/reset_simulation.html
- PX4 Gazebo simulator and windy world: https://docs.px4.io/main/en/sim_gazebo_gz/
- PX4 X500 wind-enable issue: https://github.com/PX4/PX4-gazebo-models/issues/121

These support the *software mechanism*. They do not validate experimental assumptions for an outdoor environment.
