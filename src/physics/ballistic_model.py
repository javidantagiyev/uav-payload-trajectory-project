
"""Ballistic motion model in East-North-Up coordinates."""

from src.physics.gravity import G, gravity_acceleration
from src.physics.aerodynamic_drag import (
    air_velocity,
    drag_acceleration
)


def state_derivative(
    t,
    state,
    mass=1.0,
    density=1.225,
    drag_coefficient=0.0,
    area=0.0,
    wind=(0.0, 0.0, 0.0),
    gravity_m_s2=G
):
    """Calculate the derivative of the payload state.

    State:
        (x, y, z, vx, vy, vz)

    density can be a number or a function density(z).
    wind can be a vector or a function wind(t, position).

    Returns:
        (vx, vy, vz, ax, ay, az)
    """
    if len(state) != 6:
        raise ValueError("State must contain exactly 6 values")

    if mass <= 0:
        raise ValueError("Mass must be positive")

    position = tuple(state[0:3])
    vx, vy, vz = state[3:6]

    if callable(density):
        density = density(position[2])

    if callable(wind):
        wind = wind(t, position)

    velocity = (vx, vy, vz)

    relative_velocity = air_velocity(velocity, wind)

    drag = drag_acceleration(
        relative_velocity,
        mass,
        density,
        drag_coefficient,
        area
    )

    gravity = gravity_acceleration(gravity_m_s2)

    acceleration = tuple(
        gravity[i] + drag[i]
        for i in range(3)
    )

    return (
        vx,
        vy,
        vz,
        acceleration[0],
        acceleration[1],
        acceleration[2]
    )


def model_rhs(t, state, body, atmosphere):
    """Adapter from validated scenario objects to the canonical dynamics model."""
    import numpy as np
    return np.asarray(state_derivative(
        t, state, mass=body.mass_kg,
        density=atmosphere.density_kg_m3,
        drag_coefficient=body.drag_coefficient,
        area=body.reference_area_m2,
        wind=atmosphere.wind_m_s,
        gravity_m_s2=atmosphere.gravity_m_s2,
    ), dtype=float)
