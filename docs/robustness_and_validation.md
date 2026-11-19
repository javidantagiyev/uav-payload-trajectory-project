# Robustness and Observation Evaluation

## Scope

This study extends the repository's verified, fixed-time, six-state ENU point-mass model. It addresses two different questions:

1. **Robustness to assumptions:** how do simulated states and uncertainty summaries change when the assumed physical parameters or input distributions change?
2. **Readiness for independent comparison:** can the same software evaluate its trajectories against separately supplied observations with explicit units, time convention, and provenance?

The included observation example is synthetic. The study does **not** establish measured prediction accuracy, real-world reliability, or a field-validated digital twin. No target, release decision, vehicle control, or impact-event prediction is included.

## Methods

### Scenario robustness

The reference model is the repository's nominal laboratory-scale scenario in `configs/baseline.json`. The scenario plan `configs/robustness_study.json` specifies six labeled cases: nominal, reduced density, increased density, lateral wind, increased drag coefficient, and gravity-only. Changes are explicit values, not observations.

Each scenario uses the same initial state, duration, numerical method, and coordinate convention. The analysis records the simulated position at the *same fixed elapsed time* and its difference from the nominal scenario:

$$
D_j = \left\| \mathbf{p}_j(T)-\mathbf{p}_0(T) \right\|_2.
$$

Two RK4 time-step resolutions are also compared in each case:

$$
\delta_j = \left\|\mathbf{p}_{j,h}(T)-\mathbf{p}_{j,h/5}(T)\right\|_2.
$$

Here $D_j$ represents a change of modeling assumptions, whereas $\delta_j$ is a numerical-resolution diagnostic. Neither is a measured physical error.

### Uncertainty-distribution assumptions

Package 4 used independent uniform ranges. Package 5 holds the same parameter half-widths and nominal values fixed but compares three hypothetical symmetric distributions:

- Uniform over each specified interval.
- Triangular, with its peak at the nominal value.
- Rescaled $\mathrm{Beta}(2,2)$, concentrated toward the nominal value.

The experiments use a fixed random seed, 128 samples per distribution, and RK4 with the same numerical resolution. The descriptive output is the mean, median, 95th sample percentile, and maximum *simulated deviation from the nominal simulation*. The 95th percentile is **not** a 95% real-world prediction interval.

Different prior assumptions can produce different conclusions even with identical lower and upper parameter limits. The rankings here are specific to the illustrative one-second model and the chosen hypothetical intervals.

## Illustrative results

| Input distribution | 95th percentile of 3D deviation from nominal simulation |
|---|---:|
| Uniform | 0.11756 m |
| Triangular | 0.09276 m |
| Rescaled Beta(2,2) | 0.09519 m |

For the scenario variations, the largest change among the six cases was the gravity-only assumption, at approximately 0.12533 m difference from the nominal quadratic-drag model after one second. That is a model-assumption difference, not an error against reality.

The numerical-resolution comparison produced very small differences relative to the scenario differences in these particular runs, but this does not generalize without further study.

## Independent observation interface

The reusable loader `src/physics/validation.py` requires a CSV file with the following four columns:

```text
time_s,x_m,y_m,z_m
```

An optional complete group of `vx_m_s,vy_m_s,vz_m_s` is allowed. Times must be strictly increasing, finite, nonnegative, and within the predicted interval. Partial velocity columns, missing values, nonfinite numbers, and extra columns are rejected. The parser does not automatically transform frames or units.

Each observation CSV must have a JSON metadata file containing `dataset_id`, `provenance`, `source`, `reference_frame`, `units`, `time_origin`, and `description`. Supported conventions are **ENU**, **SI**, and `elapsed_since_initial_state`.

Provenance is *declared by the data supplier*, not independently certified by the code. The synthetic example has `"provenance": "synthetic"`, and its small deterministic offsets are invented solely to exercise the comparison pipeline.

The evaluator samples the numerical model at observation times by linear interpolation and computes:

$$
\mathrm{RMSE}_{3D} = \sqrt{\frac{1}{N}\sum_{i=1}^{N}
\left\|\hat{\mathbf p}(t_i)-\mathbf p_{\mathrm{obs}}(t_i)\right\|_2^2}.
$$

It also reports per-axis RMSE and bias, mean absolute position difference, and maximum position difference. Velocity RMSE is reported only if complete velocity observations are supplied.

### Synthetic example result

The included fixture is generated independently from an analytical gravity-only trajectory with small deterministic artificial offsets. With the same gravity-only assumptions, the numerical model yields approximately **0.01013 m position RMSE** against this synthetic fixture. This measures fixture agreement only. It must not be described as physical accuracy.

## Reproduction

From the repository root, with dependencies from `requirements.txt` installed:

```powershell
python -m pytest -q tests
python experiments/robustness_study.py
python experiments/evaluate_observations.py
```

The study writes to:

```text
results/robustness_study/
    scenario_comparison.csv
    distribution_comparison.csv
    uncertainty_draws.csv
    robustness_summary.json
    figures/

results/observation_example/
    observation_residuals.csv
    evaluation_summary.json
    figures/
```

To avoid overwriting the committed reference outputs, pass `--output results/robustness_study/local_run` or `--output results/observation_example/local_run`. Such transient `local_run` directories are ignored by Git.

The observation evaluator also accepts `--scenario`, `--observations`, `--metadata`, `--model`, `--step`, and `--output`. Observations must describe the same initial coordinate system and time base as the configured scenario.

## Limitations and interpretation

- The scenario values and input intervals are illustrative, not calibrated from a physical test.
- All uncertain parameters remain constant over each simulated trajectory; time-varying disturbances and correlated uncertainty are excluded.
- The model is a six-state point mass; it does not include object orientation, detailed geometry, or full rigid-body aerodynamic forces.
- Simulation agreement does not prove physical fidelity. Comparing against another simulator also cannot replace measurement-based calibration and validation.
- Synthetic data is not independent experimental evidence, even when its numerical construction differs from the ODE integrator.
- A measured-data record should document instrument calibration, sensor location, sampling rates, coordinate transformations, clock synchronization, and measurement uncertainty before quantitative interpretation.

The next integration stage is a simulator-agnostic 3D testbed with separate **ground truth** and **simulated sensor** records. This interface is designed to accept those observations without rewriting the physics modules.
