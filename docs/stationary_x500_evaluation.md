# Stationary X500: quality-gated reproducible evaluation

## Purpose

This experiment evaluates *PX4's local estimator stability while Gazebo indicates the
simulated X500 is stationary*. It does not measure absolute position accuracy, physics-model
fidelity, or payload trajectory accuracy.

The required inputs are the two CSV recordings and their manifests from Package 6C:

- `gazebo_truth.csv` and `gazebo_truth_manifest.json`
- `px4_local_position.csv` and `px4_local_position_manifest.json`
- the original matching `.ulg` file, if available, for estimator validity and reset history

The quality gate validates the CSV schema, timestamps, manifest sample counts, provenance
labels, Gazebo quaternions, nominal overlapping time interval, PX4 validity flags,
reset-counter changes, and actual Gazebo stationary displacement. When the source ULog is
provided, the evaluator excludes samples preceding the last reset plus a one-second guard
within the candidate interval, then uses the longest continuous valid PX4 segment.

## Run

From the SDP repository root, with `.venv` active:

```bash
python experiments/evaluate_stationary_x500.py \
  --ulog /absolute/path/to/the/original_px4_session.ulg
```

The ULog path must be the same path recorded in `px4_local_position_manifest.json`.
Without `--ulog`, the analysis still runs, but its status is `descriptive_only` because
reset history cannot be checked from the Package 6C CSV alone.

For a separate archived run:

```bash
python experiments/evaluate_stationary_x500.py \
  --input results/multicopter_testbed/sessions/session_01 \
  --output results/multicopter_testbed/sessions/session_01/analysis \
  --ulog /path/to/session_01.ulg
```

Each run produces `stationary_evaluation.json` and two figures under `figures/`.
The report includes SHA-256 hashes of the source files, the selected window, source sample
counts, PX4 mean-centered RMS and percentile jitter, axis standard deviations, linear drift
slopes, time-step diagnostics, and an approximate block-bootstrap interval.

The 95% bootstrap interval uses contiguous time blocks to account partially for temporal
correlation; it should not be interpreted as a 95% confidence interval for physical position
accuracy. With short recordings, the code may omit the bootstrap interval.

## Experiment validity

`qualified_stationary_jitter` requires a stationary Gazebo trace, a compatible source ULog
with checked reset history, and enough continuously valid PX4 estimates. It **does not** mean
that the two systems have calibrated coordinate origins or independently verified clock
synchronization.

`descriptive_only` means the analysis can describe each stream but is missing at least one
of the stricter stationary-quality conditions.

The numeric overlap between Gazebo time and ULog time is used to select a *candidate* interval;
there is **no** interpolation or direct point-by-point error calculation. A stationary test
cannot identify a constant time offset. Do not subtract PX4 position from Gazebo position or
call the difference RMSE without a separately verified clock and origin transform.

## Scaling experiments

After collecting separate sessions, index their reports with:

```bash
python experiments/summarize_stationary_runs.py \
  results/multicopter_testbed/sessions/*/analysis/stationary_evaluation.json \
  --output results/multicopter_testbed/local_run/stationary_session_index.csv
```

Each row represents one experiment, not one telemetry sample. Duplicate input hashes are
rejected. Compare runs with recorded software versions, conditions, and uncertainty settings;
never pool all within-run samples and present them as independent experiments.
