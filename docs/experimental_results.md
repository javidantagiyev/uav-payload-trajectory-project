# Baseline Experiment — Reproducible Results

## Experimental setup

The tracked configuration in `configs/baseline.json` defines one illustrative one-second laboratory-scale scenario with a constant-density atmosphere. The experiment compares exact gravity-only motion, gravity-only Euler/RK4 integration, and numerical integration of the same simple quadratic-drag model. It also performs step-size refinement and an energy-consistency check.

## Initial results

| Quantity | Baseline result | Interpretation |
|---|---:|---|
| Euler gravity-only endpoint difference from exact model | 0.04905 m | Discretization error in an intentionally first-order integrator |
| RK4 gravity-only endpoint difference from exact model | about 3.2 × 10⁻¹⁵ m | Numerical agreement with the gravity-only closed form |
| Drag-model versus gravity-only endpoint difference | about 0.12533 m | Difference in *model outputs*, not measurement error |
| Mechanical energy under still-air drag | approx. 47.588 to 46.253 J | Expected dissipative behavior under the assumed model |

The associated evidence is `results/experiment_summary.json`, `results/convergence.csv` and figures in `results/figures/`. Runtime observations are platform-dependent and are not used to assert general speed rankings without controlled benchmarking.

## Limitations

The experiment does not compare outputs against external observations. It therefore verifies parts of the implementation but **does not establish prediction accuracy for real trajectories**. It also does not cover the project's longer-term conditions or proposed system-level performance objective.

For reproducible execution, follow `docs/reproducibility.md`.
