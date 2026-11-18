"""Gravity-only analytical reference using the existing gravity module."""

import numpy as np
from .gravity import G, gravity_position, gravity_velocity
from .trajectory import Trajectory


def analytic_vacuum(position0, velocity0, times, gravity_m_s2=G) -> Trajectory:
    """Exact time-series states for constant gravity with no aerodynamic force."""
    p0 = np.asarray(position0, dtype=float)
    v0 = np.asarray(velocity0, dtype=float)
    t = np.asarray(times, dtype=float)
    if p0.shape != (3,) or v0.shape != (3,):
        raise ValueError("position0 and velocity0 must be three-dimensional")
    if t.ndim != 1 or np.any(t < 0) or not np.all(np.isfinite(t)):
        raise ValueError("times must be a finite, nonnegative one-dimensional array")
    if not np.all(np.isfinite(p0)) or not np.all(np.isfinite(v0)):
        raise ValueError("position0 and velocity0 must be finite")
    if not np.isfinite(gravity_m_s2) or gravity_m_s2 <= 0:
        raise ValueError("gravity_m_s2 must be positive and finite")
    states = np.array([
        (*gravity_position(p0, v0, float(time), g=gravity_m_s2),
         *gravity_velocity(v0, float(time), g=gravity_m_s2))
        for time in t
    ], dtype=float).reshape(-1, 6)
    return Trajectory(t, states)
