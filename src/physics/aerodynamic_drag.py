
"""Aerodynamic drag equations in ENU coordinates (SI units)."""

from math import sqrt

DEFAULT_AIR_DENSITY = 1.225


def magnitude(v):
    """Calculate the magnitude of a 3D vector."""
    return sqrt(sum(value ** 2 for value in v))


def air_velocity(velocity, wind):
    """Calculate velocity relative to the surrounding air."""
    return tuple(
        velocity[i] - wind[i]
        for i in range(3)
    )


def drag_force(velocity, density=DEFAULT_AIR_DENSITY,
               drag_coefficient=0.0, area=0.0):
    """Calculate aerodynamic drag force.

    velocity must be relative to the surrounding air.
    """
    if density < 0 or drag_coefficient < 0 or area < 0:
        raise ValueError("Drag parameters cannot be negative")

    speed = magnitude(velocity)

    factor = -0.5 * density * drag_coefficient * area * speed

    return tuple(value * factor for value in velocity)


def drag_magnitude(velocity, density=DEFAULT_AIR_DENSITY,
                   drag_coefficient=0.0, area=0.0):
    """Calculate the magnitude of aerodynamic drag."""
    if density < 0 or drag_coefficient < 0 or area < 0:
        raise ValueError("Drag parameters cannot be negative")

    speed = magnitude(velocity)

    return 0.5 * density * drag_coefficient * area * speed ** 2


def drag_acceleration(velocity, mass, density=DEFAULT_AIR_DENSITY,
                      drag_coefficient=0.0, area=0.0):
    """Calculate acceleration caused by aerodynamic drag."""
    if mass <= 0:
        raise ValueError("Mass must be positive")

    force = drag_force(
        velocity,
        density,
        drag_coefficient,
        area
    )

    return tuple(value / mass for value in force)
