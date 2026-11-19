# Simulator Data Interface

## Objective

The evaluation framework is simulator-agnostic. It can ingest time-stamped kinematic states produced by a virtual 3D physics engine or a properly documented physical experiment. The initial application is a passive inert-body trajectory with a fixed initial state, not vehicle guidance.

## Required data contract

| Item | Requirement |
|---|---|
| Coordinate frame | Local east–north–up (ENU), right-handed |
| Position unit | Meters |
| Velocity unit | Meters per second when present |
| Clock | Elapsed seconds from the model initial state |
| CSV | `time_s,x_m,y_m,z_m`; optional complete `vx_m_s,vy_m_s,vz_m_s` |
| Ordering | Strictly increasing timestamps; no duplicates |
| Dataset metadata | JSON with declared provenance and origin |
| Reference source | Prefer simulator ground-truth states rather than noisy sensor estimates for a physics-engine comparison |

Any simulator that uses a different frame, such as north–east–down (NED), must transform coordinates **before export**, with the transform documented and independently tested. The evaluator intentionally rejects unknown frames instead of guessing.

## Recommended dataset separation

**Ground-truth state** is the simulator engine's physical state output. **Sensor output** is a distinct observation with sampling jitter, bias, noise, filtering, and latency. These should not be mixed into one dataset or treated as interchangeable.

A comparison study should begin with ground-truth states under matched model assumptions. Only after that comparison should sensor effects be introduced, with clock synchronization and sampling uncertainty recorded separately.

## Reproducibility checklist

Record simulator name and version, physics engine and configuration, geometry, inertial parameters, environment settings, model initial state, timestep policy, and random seed. Document which values were assumed and which were calibrated against measurements.

The observation metadata's `provenance` field is a declaration. A report should additionally retain the external source logs and calibration documents. Passing a dataset through the parser does not authenticate its provenance.

## Future extension

The existing format is sufficient for direct position/velocity comparisons. A later version may add orientation, angular velocity, wrench measurements, wind fields, sensor timestamps, covariance estimates, and validation-set identifiers. Those additions should use an explicitly versioned schema rather than silently changing this one.
