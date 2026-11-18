# Software Architecture

## Design principles

The offline research component is deliberately separated from the existing `src/physics/` modules in the parent repository. This prevents namespace collisions, avoids duplicate top-level entry points, and allows comparison against the existing code without silently replacing it.

The component has a strict dependency direction:

```text
configs/*.json
       |
       v
config.py -----------+-------> physics.py
       |              |              ^
       v              v              |
experiments/baseline.py -----> integrators.py
       |              \------> analytic.py
       |              \------> mechanical_energy (physics.py)
       v
results/{*.json,*.csv,figures/*.png}

                    tests/ ----> public modules and experiment runner
```

`src/sdp_sim/physics.py` defines dataclasses for body and atmosphere, the dynamics right-hand-side, and mechanical energy. `integrators.py` provides fixed-step Euler and RK4 time integration. `analytic.py` provides a gravity-only exact solution for solver verification. `config.py` parses and checks scenario JSON. `experiments/baseline.py` orchestrates a controlled comparison and emits research artifacts.

## Public interfaces

- `Body(mass_kg, reference_area_m2, drag_coefficient)`
- `Atmosphere(density_kg_m3, wind_m_s, gravity_m_s2)`
- `gravity_and_drag(t, state, body, atmosphere)`
- `integrate(rhs, state0, duration_s, max_step_s, method='rk4')`
- `analytic_vacuum(position0, velocity0, times, gravity_m_s2=9.81)`
- `load_scenario(path)`

Inputs are SI units. States are NumPy arrays, except for configuration values stored as Python tuples. Integrator output is a `Trajectory` containing `times` and `states`; the object exposes `positions` and `velocities` views.

## Repository integration

This component lives at `research/offline_dynamics/` relative to the parent repository. The parent repository may already have a `docs/`, `src/physics/`, `tests/`, `README.md`, `requirements.txt`, and `compare_integrators.py`. **None of these are overwritten** by this component. Package installation is performed from the component directory via `pip install -e .`. Parent-wide consolidation should happen only after reviewing the existing modules' implementations and tests.

The optional CI workflow `.github/workflows/offline-dynamics-ci.yml` runs tests from the component directory when related files change. It does not alter repository-wide workflows.

## Design boundaries

The numerical simulator is not attached to an autopilot, remote target coordinates, or a hardware release mechanism. There are no APIs for flight control or automatic payload deployment. Expanded models and independent physical validation may be developed later as separately reviewed research components.
