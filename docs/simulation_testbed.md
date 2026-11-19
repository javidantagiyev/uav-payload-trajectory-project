# 3d physics testbed and data provenance

## Objective

Establish a reproducible external physics environment for nonoperational 6-DOF rigid-body behavior and simulated sensor recording. The current implementation uses Gazebo Harmonic as a reference physics engine and keeps the Python point-mass model as a separate mathematical model. The models are not assumed identical.

## Architecture

1. `sim/gazebo/worlds/rigid_body_lab.sdf` defines the physical scene and inertial properties.
2. Gazebo's physics system evolves translation, rotation, and collision responses.
3. Gazebo's IMU and 3D odometry publisher provide simulated telemetry.
4. `sim/gazebo/scripts/record_odometry.py` subscribes to odometry messages and saves time-series records.
5. `src/physics/simulator_io.py` validates timestamps, quaternions, and outputs a Package 5-compatible observation pair.
6. `experiments/evaluate_observations.py` can consume the observation pair after initial-state synchronization and model-assumption matching.

## Physics definition

The demonstrator is a homogeneous rectangular rigid body of mass $m=1.2\,\mathrm{kg}$, with side lengths $a=0.48\,\mathrm{m}$, $b=0.30\,\mathrm{m}$, and $c=0.20\,\mathrm{m}$. Its principal moments of inertia are computed as

$$
I_{xx}=\frac{m(b^2+c^2)}{12},\qquad
I_{yy}=\frac{m(a^2+c^2)}{12},\qquad
I_{zz}=\frac{m(a^2+b^2)}{12}.
$$

World coordinates use a right-handed local ENU convention with $+z$ upward. Pose orientation is stored as a unit quaternion $(w,x,y,z)$, avoiding Euler-angle singularities in recorded orientation. Mechanical evolution is delegated to the Gazebo physics engine; no original 6-DOF integrator is claimed.

## Reproducibility and verification

The SDF specifies gravity, integration step size, geometry, inertial tensor, contact coefficients, and sensor reporting rates. The Python layer validates metadata and time-series format. Static tests verify these properties; a live Gazebo run is required to establish working dynamic behavior and determine effective physics settings. Record simulator version, operating system, graphics mode, and raw topic logs where available.

An independent physics engine provides useful cross-checking, but agreeing models can share incorrect assumptions. Physical validation still requires independent measurements. **Any data exported by this package has `provenance: synthetic`** and must never be presented as measured field evidence.

## Scope and next steps

The current stage is a physically simulated, free rigid-body testbed plus a separate PX4 SITL vehicle launch path. It does not yet provide coupled vehicle-object interaction, configurable aerodynamic forces or torques, or external measurement calibration. Those require additional modeling and verification against evidence.
