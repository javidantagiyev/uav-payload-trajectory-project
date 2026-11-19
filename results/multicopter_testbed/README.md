# Multicopter simulation recordings

Run `sim/gazebo/scripts/record_x500_truth.py` to capture Gazebo poses, then `experiments/export_px4_ulog.py` to extract PX4 state estimates. `experiments/plot_multicopter_telemetry.py` produces separate diagnostic plots. Outputs default to `results/multicopter_testbed/local_run/` and should not be committed as verified reference data until the originating Gazebo and PX4 installations have been checked.
