# Reproducibility Protocol

1. Use Python 3.10+ and install from `research/offline_dynamics/` with `python -m pip install -e ".[dev]"`.
2. Execute `python -m pytest -q`. Unit and integration tests must pass before interpreting generated plots.
3. Execute `python experiments/baseline.py --config configs/baseline.json --output results/local_run`.
4. Review the generated `experiment_summary.json`, `convergence.csv`, and PNG figures. Input assumptions are stored in the JSON summary and configuration file.
5. Keep independently obtained measurements and calibration information separate from illustrative simulation outputs.

The scenario is deterministic, but **runtime numbers are not deterministic**. They depend on Python, operating system, processor load, and installed package versions. The dependency ranges in `pyproject.toml` specify compatibility minima, not a fully pinned environment.

## Files and provenance

- `configs/baseline.json`: source of experiment parameters
- `src/sdp_sim/`: numerical implementation under test
- `tests/`: assertions required for acceptance
- `results/`: illustrative generated outputs included for inspection

Any future alteration to assumptions, coefficients, or integrator implementations should be accompanied by tests and a recorded change to the experiment configuration or output provenance.
