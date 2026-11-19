# 3d simulation testbed (package 6)

This directory contains an independent, physically simulated rigid-body experiment in Gazebo Harmonic and a separate optional PX4 SITL vehicle setup. The experiment is designed for nonoperational 6-degree-of-freedom research, software verification, and observation data interchange.

## Supported environment

Use Ubuntu 22.04 or 24.04, either installed directly or through WSL2 on Windows 11. Install Gazebo Harmonic using the official guide: https://gazebosim.org/docs/harmonic/install_ubuntu/. In WSL2, run from the Ubuntu terminal, not PowerShell. GUI support depends on WSLg / graphics drivers.

Gazebo's Python transport bindings are provided by the Ubuntu packages compatible with Gazebo Harmonic, including `python3-gz-transport13` and `python3-gz-msgs10` where available. Run the recorder using **Ubuntu's `/usr/bin/python3`**, because Python packages installed by `apt` are not generally visible to a project virtual environment.

Check your environment:

```bash
python3 sim/gazebo/scripts/check_environment.py
```

## Stage a: 6-dof passive-body world

Terminal 1, at the repository root:

```bash
bash sim/gazebo/scripts/run_lab.sh
```

The world starts paused so the recorder can subscribe before the object begins moving. Open terminal 2 and start recording, then click **play** in Gazebo.

The world contains a free rigid box with declared mass, principal moments of inertia, collision geometry, contact parameters, gravity, and an IMU. Its initial orientation is nonzero and it can translate and rotate after contact. An odometry plugin publishes a nominally noiseless 3D pose and twist at 100 Hz.

Terminal 2, while the world is running:

```bash
gz topic -l
gz topic -i -t /sdp/inert_body/odometry
/usr/bin/python3 sim/gazebo/scripts/record_odometry.py --seconds 15 --output results/simulation_testbed/local_run
```

The recorder writes `rigid_body_6dof.csv`, `observations.csv`, `observations.json`, and `run_manifest.json` in the chosen output folder. It uses simulation message timestamps; if the scene is paused, no new valid frames are emitted. Start recording early enough to capture the dynamics of interest, and log the Gazebo version in the study record.

After recording, generate figures and a JSON summary using the project Python interpreter with Matplotlib installed:

```bash
python experiments/visualize_simulation.py --input results/simulation_testbed/local_run/rigid_body_6dof.csv --output results/simulation_testbed/local_run
```

This produces `figures/trajectory_3d.png`, `figures/position_attitude.png`, and `recording_summary.json`. The figures come from the actual recorded simulation, not an embedded demonstration dataset.

The exported `observations.csv` and `observations.json` match the Package 5 loader schema (ENU positions and elapsed time). **They are simulated observations, not experimental measurements.** The full 6-DOF file also stores the reported quaternion and twist. Do not interpret twist in the world frame without confirming the publisher's twist-frame convention.

For exploratory comparison with the existing gravity-only model, match the initial time/pose exactly and compare only the *free-flight interval before collision*. The initial world includes no aerodynamic drag model, so do not interpret a drag-model discrepancy as a solver error. The first recorded frame may occur after Gazebo has advanced; check time alignment before running the evaluation pipeline. The current CSV exporter does not synchronize initial states automatically.

## Stage b: px4 vehicle simulation (separate launch path)

PX4 SITL provides an off-the-shelf quadrotor flight dynamics model and simulated flight-controller telemetry. Follow the PX4 WSL2 setup: https://docs.px4.io/main/en/dev_setup/dev_env_windows_wsl . Clone and set up `PX4-Autopilot` **outside** this repository, in your Ubuntu home folder. From its root:

```bash
make px4_sitl gz_x500
```

For machines with limited graphics performance, run:

```bash
HEADLESS=1 make px4_sitl gz_x500
```

See https://docs.px4.io/main/en/sim_gazebo_gz/ for vehicle and world selection. This stage establishes a separately simulated multicopter and does not automate navigation, release, or real-vehicle actions. It does not yet spawn or control that vehicle inside the rigid-body lab world. PX4 integration and telemetry-frame reconciliation are subsequent work.

## Troubleshooting

- `gz: command not found`: Gazebo Harmonic has not been installed in the current Linux environment.
- `no module named gz`: Use the Ubuntu system Python interpreter and check Gazebo Python transport bindings.
- No odometry messages: Confirm the world name and `/sdp/inert_body/odometry` with `gz topic -l`; ensure simulation is unpaused.
- The object rests on the floor before recording: restart the world, then begin recording promptly. This stage deliberately does not introduce a custom reset/control plugin.
- WSL GUI runs poorly: Use the standard PX4 `HEADLESS=1` option for its separate vehicle scenario; the SDF world can also be started with `gz sim -s -r ...` for server-only runs.

## Known limitations

The SDF provides 6-DOF **mechanical capability**, not proven aerodynamic fidelity. The object is a rigid rectangular box with specified mass and inertia. It uses engine contact and collision behavior and a default gravity field. No calibration, drag/tumbling aerodynamic moments, wind fields, or measured material data are claimed. The IMU is simulated and not a substitute for real sensor calibration. This package has not been executed in Gazebo in the build environment; static SDF and Python tests are included, and a real local run is the next acceptance step.
