# Parameter sensitivity and uncertainty: preliminary numerical study

## Purpose and scope

This study investigates how uncertainty in **assumed inputs** changes the solution of the repository's established six-state point-mass ordinary differential equation. It is a computational screening experiment, not physical validation. The output is an inert object's **simulated state at a fixed elapsed time**, rather than an impact event, target error, or release recommendation.

The study extends the [controlled numerical-method comparison](numerical_method_comparison.md). That preceding study examined the accuracy of numerical methods for a given equation. Here, RK4 is held fixed while selected **input parameters** are varied.

## Model and experimental conditions

The experiment uses `src/physics/ballistic_model.py` via the shared `model_rhs` function. In East–North–Up (ENU) coordinates, the assumed equation is

\[
\frac{d\mathbf{v}}{dt} = \mathbf{g} - \frac{\rho C_d A}{2m}\|\mathbf{v}-\mathbf{w}\|(\mathbf{v}-\mathbf{w}),
\qquad \frac{d\mathbf{r}}{dt}=\mathbf{v}.
\]

The scenario is imported from [`configs/baseline.json`](../configs/baseline.json). It covers a synthetic **one-second interval** starting at 12 m above the arbitrary ENU origin. It is not calibrated to measured equipment or atmospheric observations. The numerical method is fixed-step RK4 with a maximum step of 0.025 s, checked at 0.0125 s for a subset of cases.

The additional configuration [`configs/uncertainty_study.json`](../configs/uncertainty_study.json) defines eight independently sampled scalar parameters. For each quantity, an *illustrative symmetric half-width* is specified:

| Input | Nominal | Assumed half-width | Interpretation |
|---|---:|---:|---|
| Mass (kg) | 0.400 | 0.040 | Hypothetical ±10% interval |
| Reference area (m²) | 0.020 | 0.003 | Hypothetical ±15% interval |
| Drag coefficient | 0.470 | 0.094 | Hypothetical ±20% interval |
| Air density (kg/m³) | 1.225 | 0.06125 | Hypothetical ±5% interval |
| East wind component (m/s) | 0 | 0.5 | Hypothetical ±0.5 m/s interval |
| North wind component (m/s) | 0 | 0.5 | Hypothetical ±0.5 m/s interval |
| Initial east velocity (m/s) | 1.5 | 0.1 | Hypothetical ±0.1 m/s interval |
| Initial north velocity (m/s) | 0.5 | 0.1 | Hypothetical ±0.1 m/s interval |

**These half-widths are demonstration choices, not measured uncertainties, manufacturer specifications, prior distributions inferred from experiments, or defensible operational error margins.** The assumed constant density, wind, and coefficients are held fixed along each short simulated trajectory. Temporal gusts, correlated inputs, uncertain vertical wind, and uncertain altitude are not included.

## Methods

### One-at-a-time (OAT) screening

For each uncertain scalar input \(p\), two numerical solutions use \(p_0-\delta_p\) and \(p_0+\delta_p\), with all other parameters fixed. We report

\[
S_p = \tfrac12\|\mathbf r_{+}(T)-\mathbf r_{-}(T)\|_2.
\]

This response magnitude has units of meters **for the specified input half-width**. It is not a dimensionless derivative, Sobol index, explained-variance fraction, or measure of a parameter's intrinsic importance. Changing the ranges can change the ranking; this design also omits interactions among inputs.

### Joint independent-uniform Monte Carlo

For each of 256 synthetic parameter combinations, every configured parameter is drawn independently from a uniform interval \([p_0-\delta_p,p_0+\delta_p]\). Pseudorandom draws use the fixed seed `20261118`. The output for each realization is a numerical state at \(T=1\) s; differences are calculated relative to the model's **nominal simulation**, not any measured physical trajectory.

Reported descriptive statistics include the mean, standard deviation, and 5th, 50th, and 95th percentiles of the **nonnegative 3D terminal-position difference** \(\|\mathbf r_i(T)-\mathbf r_0(T)\|_2\). The 95% bootstrap interval on the estimated 95th percentile uses 400 resamples. It reflects finite-sample variability *under the assumed distributions*, and must not be interpreted as 95% physical coverage or a reliability guarantee.

### Numerical-resolution check

The first 24 seeded parameter realizations are recomputed at a finer RK4 time step. Their terminal states are compared to their coarse-step solutions. This checks whether integration discretization is small relative to parameter-perturbation effects for the selected toy case. It is not an independent reference to nature.

## Generated results (illustrative baseline)

`python experiments/uncertainty_study.py` writes machine-readable outputs and plots into `results/uncertainty_study/`:

| File | Content |
|---|---|
| `one_at_a_time.csv` | Signed position changes and half-span magnitude for every varied input |
| `monte_carlo_samples.csv` | All sampled inputs, fixed-time states, and differences relative to nominal |
| `sampling_stability.csv` | Running sample-size estimates of mean and 95th percentile |
| `resolution_diagnostic.csv` | RK4 differences between two integration step sizes |
| `uncertainty_summary.json` | Assumptions, scenario hashes, seed, summary statistics, OAT ranking, limitations |
| `figures/one_at_a_time_effects.png` | Parameter-range-specific OAT screening |
| `figures/terminal_deviation_distribution.png` | Distribution of simulated 3D differences from nominal |
| `figures/terminal_horizontal_scatter.png` | Sampled terminal ENU east/north coordinates at one fixed time |
| `figures/sampling_stability.png` | Sensitivity of the estimated p95 to sample count |
| `figures/numerical_resolution_check.png` | Difference between coarse- and finer-step RK4 on selected samples |

For the checked-in seed and illustrative input ranges, the 256 samples yield:

- Mean 3D terminal-position difference from nominal: **0.0789 m**.
- Estimated 95th percentile of that difference: **0.1232 m**.
- Bootstrap interval for the *estimated 95th percentile*: **[0.1150 m, 0.1278 m]** under the chosen distributional assumptions.
- Largest OAT half-span effects in this configuration: initial north/east velocity components, roughly **0.097 m** each.
- Largest terminal-position difference between the two tested RK4 step sizes over 24 samples: **5.40 × 10⁻⁹ m**.

These are **not empirical error measurements** and should not be used to infer the project's real-world precision, success probability, or accuracy at another timescale. They show sensitivity under one specified synthetic numerical experiment.

## Structural identifiability limitation

The model's drag acceleration depends on the product/ratio

\[
\gamma = \frac{\rho C_d A}{2m}.
\]

If \(m\) and \(A\) are multiplied by the same positive factor while all other parameters are fixed, the numerical equation of motion is unchanged. Thus, observing motion under this model alone cannot independently recover these two parameters from trajectories: different parameter sets can produce identical dynamics. `tests/test_uncertainty.py` includes a regression check of that invariance.

This limitation matters when interpreting sensitivity rankings and proposing future experimental parameter estimation. Individual variation is useful for screening but does not demonstrate that a parameter can be separately identified from motion observations.

## Reproducibility

From the repository root:

```bash
python -m pip install -r requirements.txt
python -m pytest -q tests
python experiments/uncertainty_study.py --config configs/baseline.json --uncertainty configs/uncertainty_study.json --output results/uncertainty_study
```

The script records SHA-256 hashes of both input JSON files, the RNG seed, scenario assumptions and Python/NumPy versions. Determinism applies to repeated simulations under the same software environment and inputs; minor floating-point differences across environments may remain.

## Research interpretation and next steps

The experiment distinguishes *parameter-driven variation in a specified model* from *numerical integration error*. It does not characterize the actual uncertainty distributions of the application, estimate the model discrepancy, or validate the trajectory against observations.

A future study should derive uncertainty ranges from independent calibration/measurement data, account for dependencies and time variation, test alternative modeling assumptions, and compare independently gathered observations with corresponding predictions. Until then, this sensitivity study is exploratory numerical evidence only.
