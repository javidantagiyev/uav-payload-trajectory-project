# Package 6D integration notes

This is an add-only overlay for the SDP repository after Packages 5, 6, 6A and 6C.
The ZIP paths are relative to the repository root; do not create a nested `package6d/` directory.
Existing physics, wind, uncertainty, visualization, and PX4 recorder files are unchanged.

## Installation

From `~/projects/uav-payload-trajectory-project` in the WSL terminal:

```bash
unzip -n SDP_Package6D_Research_Integration.zip
source .venv/bin/activate
python -m pip install -r requirements-simulation-analysis.txt
python -m pytest -q tests
```

Before running the evaluation, make sure your latest package 6C `gazebo_truth.csv`,
`px4_local_position.csv`, and their matching manifest JSON files are in
`results/multicopter_testbed/local_run/`.

Use the **same source ULog** that was passed to `experiments/export_px4_ulog.py`:

```bash
python experiments/evaluate_stationary_x500.py \
  --ulog /absolute/path/to/the_matching_session.ulg
```

The output `stationary_evaluation.json` and two figures are written inside that run's
`local_run/` directory, which is Git-ignored. The source recordings are not modified.

See `docs/stationary_x500_evaluation.md` for limitations and how to index multiple
independent runs. See `docs/research_reconciliation.md` for model-interface contracts,
confirmed differences, and unresolved scientific choices.

Run `git status --short` and inspect the file list before committing. Stage only the
new files for this package and keep any active teammate changes untouched. Suggested
commit message: `add stationary evaluation and research contracts`.

## Verification

The overlay was tested against the user's uploaded `main` ZIP snapshot plus the locally
available 6A/6C overlays. The reconstructed project passed 302 tests. This does not
prove the current remote `main` branch or your WSL checkout is identical to that snapshot.
The new evaluator itself has not been run against the user's current private ULog file;
its ULog quality gate was unit tested with controlled fixtures.
