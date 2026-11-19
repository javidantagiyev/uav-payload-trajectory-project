# Controlled Numerical-Method Comparison

## Purpose and research scope

This experiment compares two existing numerical solvers (forward Euler and classical fourth-order Runge–Kutta, RK4) under **the same input conditions** and under **each of two explicit physical assumptions**: constant gravity without drag, and constant gravity with quadratic aerodynamic drag. It evaluates numerical convergence, computational effort, and sensitivity to the *choice of mathematical model*. It is not an accuracy claim for real observations.

The experiment reuses the repository's canonical `src/physics/` equations, `src/physics/integrators.py` single-step methods, and `src/physics/trajectory.py` time-stepping function. No parallel physics implementation is introduced.

## Methods

The translational state is $\mathbf y=[x,y,z,v_x,v_y,v_z]^\mathsf T$, expressed in East–North–Up coordinates with SI units. The model has the ordinary differential equation $\dot{\mathbf y}=f(t,\mathbf y)$ with gravitational acceleration and, where selected, quadratic drag using velocity relative to the assumed air velocity. All other inputs are held constant when changing the integration method.

The design is a balanced **2 × 2 comparison**:

| Physical assumption | Euler | RK4 | Reference for numerical difference |
|---|---|---|---|
| Constant gravity, no drag | Included | Included | Exact analytical constant-gravity solution |
| Gravity and quadratic drag | Included | Included | Fine-step RK4 numerical solution for the *same drag model* |

For each pair, the solver is run at maximum time steps of 0.1, 0.05, 0.025, and 0.0125 s, using `configs/baseline.json` (the same input file as the earlier offline verification experiment). Integration always reaches the same final time; if a requested maximum step does not exactly divide the duration, the integrator uses a slightly smaller *actual* step. The table reports both.

Reference solution choice is explicit. The gravity-only reference is analytical. The drag reference is a more finely integrated **numerical approximation**, not a measured trajectory. The comparison metric is the Euclidean terminal position difference $\|\mathbf r_h(T)-\mathbf r_{\mathrm{ref}}(T)\|_2$, together with the separate velocity difference. These are **not landing errors**.

An empirical convergence order is obtained by fitting $\log(E_h)=p\log(h)+b$ to reference differences above a conservative numerical floor. Near machine precision, the experiment reports the slope as *roundoff-limited* rather than fitting meaningless noise. The theoretical global orders for sufficiently smooth problems are Euler 1 and RK4 4.

Computational cost is reported as (i) number of evaluations of the differential equation, calculated from the existing one-step algorithms, and (ii) median wall-clock duration of a complete Python integration across repeated runs, after one warm-up run. Results include memory allocation and trajectory recording overhead. Wall-clock measurements are sensitive to hardware, operating system, Python version, and background load; they are not machine-independent CPU benchmarks.

## Illustrative results from the included baseline configuration

The laboratory-scale synthetic case uses 0.4 kg mass, 0.02 m² reference area, drag coefficient 0.47, uniform 1.225 kg/m³ density, still air, and one second of integration from 12 m initial height. These are assumptions, not estimates from field data.

| Model | Method | Terminal position difference at 0.1 s maximum step | Expected behavior |
|---|---|---:|---|
| Gravity only | Euler | 0.490500 m | Approximately first order |
| Gravity only | RK4 | approximately $2\times10^{-15}\,\mathrm{m}$ | Roundoff-limited because RK4 integrates this constant-acceleration case to machine precision |
| Quadratic drag | Euler | 0.450985 m | Approximately first order |
| Quadratic drag | RK4 | 0.000001121 m | Approximately fourth order under step refinement |

The observed fitted orders in the generated demonstration are approximately 1.00 for gravity-only Euler, 1.00 for drag Euler, and 4.03 for drag RK4. The gravity-only RK4 slope is deliberately left undefined. These values are produced using this specific test scenario and numerical reference. Runtime measurements are provided only in the generated CSV, because they vary across machines.

The separate *model-assumption difference* curve compares a high-resolution gravity-only analytical solution against the high-resolution drag model. It illustrates that two numerically well-solved equations can still produce different results. It does not determine which model represents an actual experiment more faithfully.

## Reproduction from the repository root

Install dependencies and execute:

```bash
python -m pip install -r requirements.txt
python -m pytest -q tests
python experiments/solver_study.py --config configs/baseline.json --output results/solver_study
```

Outputs are `solver_comparison.csv` (16 combinations), `observed_orders.csv` (four comparisons), `study_summary.json` (configuration SHA-256, assumptions, environment, reference descriptions), and six figures in `results/solver_study/figures/`.

For repeat tests without overwriting the committed illustrative outputs, choose a different output directory, e.g. `results/solver_study/local_run`. The existing `.gitignore` excludes `results/**/local_run/`.

## Interpreting the figures

- `gravity_only_trajectories.png` compares Euler and RK4 against the analytical vertical trajectory under identical gravity-only assumptions.
- `quadratic_drag_trajectories.png` compares the same two integrators against the fine RK4 drag reference under identical drag assumptions.
- `gravity_only_convergence.png` shows first-order Euler convergence and an RK4 numerical-precision floor. The near-flat RK4 trace must not be interpreted as poor fourth-order behavior.
- `quadratic_drag_convergence.png` shows error reduction with step refinement under the drag model; unlike the gravity-only case, RK4 differences remain sufficiently large for an empirical slope to be estimated.
- `accuracy_vs_runtime.png` compares numerical differences against measured complete integration time. Cross-machine comparisons of the runtime axis are not warranted.
- `model_assumption_difference.png` shows differences between two physical assumptions even when both references are computed accurately.

## Limitations and research implications

The simulated body is inert and treated as a point mass with fixed aerodynamic parameters. The atmosphere is uniform, and the tests do not include independent observations, calibration, varying winds, rotational dynamics, release-point calculation, or closed-loop vehicle control. The analytical reference establishes numerical correctness under a restricted assumption, not the realism of the drag formulation. Fine RK4 results are numerical approximations, so observed errors below the reference error floor should not be interpreted literally. Solver choice alone cannot fix an incorrect physical model.

This package provides a reproducible baseline for evaluating **numerical-method accuracy versus cost** under controlled assumptions. Research questions about physical parameter sensitivity, uncertainty, and prediction validity require separate independent analysis and, ultimately, observational evidence.
