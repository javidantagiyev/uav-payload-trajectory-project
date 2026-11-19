# gazebo odometry data-quality audit

## scope

This study audits a time-stamped 6-DOF inert-body recording from the Package 6 Gazebo test world. It does not establish agreement with physical experiments. The input CSV is preserved unchanged. The audit writes diagnostic figures, an explicit world-frame velocity export, and a JSON summary.

## model and coordinate conventions

The world in `sim/gazebo/worlds/rigid_body_lab.sdf` uses vertical-up coordinates and gravity \(\mathbf g = (0,0,-9.81)\,\mathrm{m/s^2}\). Position and orientation come from the Gazebo odometry publisher. The existing `rigid_body_6dof.csv` column names do not state the twist reference frame; this audit interprets the odometry publisher's linear and angular twist as **body-frame** measurements.

A unit quaternion \(q\) rotates each recorded body-frame velocity into world coordinates:

$$
\mathbf v_{world} = R(q)\,\mathbf v_{body}.
$$

The transformation is performed on both linear and angular velocity. The original odometry CSV is **not overwritten**; explicit world-frame components are exported to `world_frame_twist.csv`.

## checks

1. Reject missing fields, nonfinite values, non-unit quaternions, and repeated or decreasing timestamps.
2. Fit a quadratic to vertical position in the declared contact-free interval (default \(0\) to \(0.5\) simulation seconds). Estimate \(g=-2a\) from \(z(t)=at^2+bt+c\) and report residual error.
3. Compare world-frame odometry velocity with backward differences of world-frame position over the same free-flight interval. A velocity publisher may report the end-of-interval velocity differently from the instantaneous derivative.
4. Test the *first* velocity sample against the first observed position interval. A large disagreement is flagged but does not invalidate subsequent position measurements.
5. Report maximum horizontal displacement, minimum observed height, and rise after that minimum. The latter is a geometric summary, not automatically a coefficient-of-restitution measurement.

For this initial world, the first velocity message may exhibit a startup anomaly. The audit marks it rather than silently deleting data. A clean free-flight gravity fit is a check of **numerical consistency with configured gravity**, not independent physical validation.

The contact-free interval is declared in `configs/simulation_audit.json`. If the world or initial height changes, the interval must be reselected; do not use a window that includes a collision. Pass/fail tolerances are preliminary engineering assertions, not calibration uncertainties.

## reproducible procedure

From the repository root, using the project Python virtual environment:

```bash
python experiments/audit_simulation.py
```

Or explicitly specify a recording and output directory:

```bash
python experiments/audit_simulation.py \
  --input results/simulation_testbed/local_run/rigid_body_6dof.csv \
  --output results/simulation_testbed/local_run
```

The audit generates:

- `results/simulation_testbed/local_run/simulation_audit.json`
- `results/simulation_testbed/local_run/world_frame_twist.csv`
- `results/simulation_testbed/local_run/figures/height_physics_check.png`
- `results/simulation_testbed/local_run/figures/velocity_and_horizontal_check.png`

Re-running the command recreates deleted diagnostic figures. It does not modify the original `rigid_body_6dof.csv` or the Package 5 observation export.

## interpretation and limitations

The first velocity flag warns against using its raw value as an initial-state estimate. Later velocity samples may be useful after frame conversion and time-alignment checks. Physics behavior during contact requires separate checks of collision configuration, friction, restitution, and time-step resolution. This audit is not a substitute for a calibrated real-world experiment. Neither 6-DOF kinematics nor numerical agreement alone establishes fidelity of unmodeled aerodynamics.
