# Verification and Validation Strategy

## Distinctions

**Numerical verification** asks whether the solver correctly approximates the stated equations. **Physical validation** asks whether those equations and parameters adequately describe measured behavior. **Performance benchmarking** compares computational cost and output differences under specified assumptions.

## Implemented tests

| Verification target | Method | Source |
|---|---|---|
| Gravity-only acceleration and analytical solution | RHS comparison and closed-form reference | `tests/test_physics.py`, `tests/test_integrators.py` |
| Drag opposition in stationary air | Dot-product sign | `tests/test_physics.py` |
| Mechanical-energy behavior | Monotonic decrease under still-air drag | `tests/test_integrators.py` |
| RK4 step-size refinement | Comparison to finer RK4 solution | `tests/test_integrators.py` |
| Parameter validation and schema enforcement | Deliberately invalid inputs | `tests/test_config.py`, `tests/test_physics.py` |
| Output reproducibility and file structure | Execute configured experiment in temporary folder | `tests/test_experiment.py` |

The fine-step RK4 trajectory is an **internal numerical reference only**. Agreement with it cannot independently validate the physics or establish real-world accuracy.

## Required future validation evidence

A later physical validation phase would need independent observation data, measured initial conditions and environmental information, known instrumentation uncertainty, and a separation between calibration and final evaluation datasets. Synthetic reference scenarios must always identify their generating model.

No physical accuracy claim or numerical threshold for field performance can currently be supported by this repository.
