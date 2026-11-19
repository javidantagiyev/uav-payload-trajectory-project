# Environmental testbed output

The reproducible scenario definitions live in `configs/environment_matrix.json`. The first step is:

```bash
python experiments/prepare_environment_matrix.py
```

This generates worlds and `scenario_manifest.json` in `local_run/worlds/`. Execute a two-case screening run only after verifying your local Gazebo installation:

```bash
python sim/gazebo/scripts/run_environment_batch.py --execute --cases baseline wind_east_4
python experiments/evaluate_environment_matrix.py
```

Each successful case generates `runs/<case>/rigid_body_6dof.csv`, an observation export and provenance file, plus `gazebo_server.log`, `recorder.log`, and `batch_case_status.json`. Missing cases are not counted as successful. The offline wind/atmosphere audit is independent and writes to `local_run/model_diagnostics/`.
