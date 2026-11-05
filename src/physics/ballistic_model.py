
"""Ballistic motion model in East-North-Up coordinates."""

from src.physics.gravity import gravity_acceleration
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
    wind=(0.0, 0.0, 0.0)
):
    """Calculate the derivative of the payload state.

    State:
        (x, y, z, vx, vy, vz)

    Returns:
        (vx, vy, vz, ax, ay, az)
    """
    if len(state) != 6:
        raise ValueError("State must contain exactly 6 values")

    if mass <= 0:
        raise ValueError("Mass must be positive")

    vx, vy, vz = state[3:6]

    velocity = (vx, vy, vz)

    relative_velocity = air_velocity(velocity, wind)

    drag = drag_acceleration(
        relative_velocity,
        mass,
        density,
        drag_coefficient,
        area
    )

    gravity = gravity_acceleration()

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
