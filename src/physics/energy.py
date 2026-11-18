"""Mechanical energy diagnostic for the translational model."""
import numpy as np
from .parameters import Body, Atmosphere


def mechanical_energy(state, body: Body, atmosphere: Atmosphere) -> float:
    """Return kinetic plus gravitational energy (J), with zero at z=0."""
    state = np.asarray(state, dtype=float)
    if state.shape != (6,) or not np.all(np.isfinite(state)):
        raise ValueError("state must contain six finite components")
    return float(0.5 * body.mass_kg * np.dot(state[3:], state[3:]) + body.mass_kg * atmosphere.gravity_m_s2 * state[2])
