# PX4 X500 wind coupling: verification required

The `PX4_GZ_WORLD=windy` environment is documented by PX4. However, Gazebo Sim's `WindEffects` requires the relevant model links to have wind enabled. A public issue reports that the X500 model may not respond as expected without a `<enable_wind>true</enable_wind>` tag on its base link: https://github.com/PX4/PX4-gazebo-models/issues/121.

**Do not modify the external PX4 source or X500 model on the basis of the world filename alone.** First examine the installed version and the wind-enabled links:

```bash
cd ~/projects/PX4-Autopilot
rg -n 'enable_wind|WindEffects|linear_velocity' Tools/simulation/gz/worlds/windy.sdf Tools/simulation/gz/models/x500_base/model.sdf Tools/simulation/gz/models/x500/model.sdf
```

This is a *read-only audit*; missing matches are informative. If the world and model settings support wind, run a controlled zero-wind versus nonzero-wind comparison, with a verified time and state reference. Merely logging a wind value or observing estimator jitter is insufficient to show that the simulated vehicle experienced the intended aerodynamic forces.

PX4's documented launch command for its built-in windy world is:

```bash
cd ~/projects/PX4-Autopilot
HEADLESS=1 PX4_GZ_WORLD=windy make px4_sitl gz_x500
```

This is a manual diagnostic, **not** part of the generated rigid-body batch and not yet a verified wind-effect benchmark. No flight-control command sequence is added in this package.

The generated scenarios under `results/environmental_testbed/local_run/worlds/` apply only to `inert_body`, not PX4's X500. They must not be called X500 wind-response results.

This package also provides a non-mutating audit:

```bash
python sim/gazebo/scripts/inspect_px4_wind.py
```

It reports whether the world includes the WindEffects system and whether `x500_base/base_link` has wind enabled. The `configuration_ready_for_wind_response_test` field is a *configuration readiness* check, not empirical proof of coupling. The field `physics_wind_response_verified` remains false until a controlled live experiment establishes the effect.
