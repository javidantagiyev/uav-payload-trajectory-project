# Multicopter telemetry and simulated ground truth

## Purpose

Package 6C records two **independent** streams from a PX4/Gazebo X500 simulation without modifying the flight controller: Gazebo world poses and PX4 EKF local-position estimates. This is an offline diagnostic experiment, not physical validation or a flight-control interface.

## Data definitions

| Stream | Source | Frame | Clock | File |
| --- | --- | --- | --- | --- |
| Physics reference | Gazebo `/world/default/pose/info`, model `x500_0` | Gazebo world (typically ENU) | simulation time, seconds | `gazebo_truth.csv` |
| State estimate | ULog `vehicle_local_position` | NED input, transformed into ENU columns | PX4 timestamp, seconds | `px4_local_position.csv` |

NED to ENU conversion: `(east, north, up) = (ned_y, ned_x, -ned_z)` for both position and velocity. This only rotates axes. It does **not** align the estimator origin to Gazebo's world origin or prove that the clocks agree. The two input CSVs preserve absolute source timestamps. Diagnostic figures separately re-zero each source for readability and **must not be interpreted as synchronized**.

Gazebo's `Pose_V` header may be empty. The recorder uses the model pose header if present, then the message header, then the last received `/world/default/clock` timestamp. The manifest reports which source was used. The clock fallback is approximate and must be checked before comparisons requiring precise synchronization. An object pose is not the same as a measured sensor observation.

PX4 `xy_valid`, `z_valid`, `v_xy_valid` and `v_z_valid` flags are retained when present. Unknown flags are marked `-1`, and invalid numeric samples are skipped. Invalid flags should not be treated as accurate state estimates. A `vehicle_attitude` stream can be added later with explicit FRD/body quaternion semantics.

## WSL2 workflow

All commands below assume these two directories exist:

- `~/projects/PX4-Autopilot`
- `~/projects/uav-payload-trajectory-project`

1. From `~/projects/PX4-Autopilot`, start the physics server and PX4 in the first terminal:

   ```bash
   HEADLESS=1 make px4_sitl gz_x500
   ```

2. Optionally launch the Gazebo GUI in another terminal, keeping the RTX 3050 and WSLg workarounds:

   ```bash
   MESA_D3D12_DEFAULT_ADAPTER_NAME=NVIDIA QT_QPA_PLATFORM=xcb gz sim -g -v 4
   ```

3. Check that the world pose topic exists:

   ```bash
   gz topic -l | grep '/world/default/pose/info'
   gz topic -i -t /world/default/pose/info
   ```

4. From the SDP repository root, record the world pose using system Python (Gazebo bindings are installed there). This records 20 **wall-clock** seconds; if the server is paused, no useful samples will arrive.

   ```bash
   cd ~/projects/uav-payload-trajectory-project
   /usr/bin/python3 sim/gazebo/scripts/record_x500_truth.py --seconds 20
   ```

5. In the PX4 `pxh>` console, inspect estimator updates with `listener vehicle_local_position` and logger state using `logger status`. Stop PX4 cleanly to close its log file. Logs are normally beneath `~/projects/PX4-Autopilot/build/px4_sitl_default/rootfs/log/` (verify with `find`).

   ```bash
   find ~/projects/PX4-Autopilot/build -type f -name '*.ulg' | tail -10
   ```

6. In the SDP repository's `.venv`, install the optional ULog reader and export the chosen completed log. Substitute the **actual log path** from the preceding command:

   ```bash
   source .venv/bin/activate
   python -m pip install pyulog
   python experiments/export_px4_ulog.py /absolute/path/to/your/log.ulg
   python experiments/plot_multicopter_telemetry.py
   python -m pytest -q tests
   ```

The output is in `results/multicopter_testbed/local_run/`. It contains separate CSVs and manifests, an independent position plot for each stream, and `telemetry_diagnostics.json`.

## Initial acceptance conditions

1. The Gazebo recorder captures at least two increasing finite timestamps for `x500_0` and unit quaternions.
2. PX4 ULog contains `vehicle_local_position` instance zero; it exports finite timestamped samples, with validity flags preserved.
3. Both files include the expected columns and source provenance.
4. The plots use separate time axes; no cross-simulator RMSE is reported before origin and clock alignment are calibrated.

## Next verification work

Validate the two clock sources against a common simulation event, establish the PX4 local-origin-to-Gazebo-world transform, compare independently generated stationary and moving state sequences, and quantify discrepancies with validity masks and time-alignment uncertainty. A realistic 3D simulator is not experimental measurement of the physical vehicle.
