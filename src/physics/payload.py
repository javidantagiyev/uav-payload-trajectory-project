
"""Payload shapes, ballistic coefficient and terminal velocity (SI units)."""

from math import pi, sqrt

from src.physics.gravity import G


def sphere(mass, diameter, drag_coefficient=0.47):
    """Return parameters of a spherical payload.

    area is the circular cross-section pi * d^2 / 4.
    """
    if mass <= 0:
        raise ValueError("Mass must be positive")

    if diameter <= 0:
        raise ValueError("Diameter must be positive")

    if drag_coefficient <= 0:
        raise ValueError("Drag coefficient must be positive")

    return {
        "shape": "sphere",
        "mass": mass,
        "area": pi * diameter ** 2 / 4,
        "drag_coefficient": drag_coefficient
    }


def box(mass, length, width, height, drag_coefficient=1.05):
    """Return parameters of a box-shaped payload.

    The box falls mostly vertically, so the frontal area is the
    bottom face length * width. height does not change the area.
    """
    if mass <= 0:
        raise ValueError("Mass must be positive")

    if length <= 0 or width <= 0 or height <= 0:
        raise ValueError("Box dimensions must be positive")

    if drag_coefficient <= 0:
        raise ValueError("Drag coefficient must be positive")

    return {
        "shape": "box",
        "mass": mass,
        "area": length * width,
        "drag_coefficient": drag_coefficient
    }


PRESETS = {
    "sphere_1kg": sphere(1.0, 0.15),
    "box_1kg": box(1.0, 0.2, 0.15, 0.1)
}


def ballistic_coefficient(payload):
    """Return the ballistic coefficient m / (Cd * A) in kg/m^2."""
    return payload["mass"] / (payload["drag_coefficient"] * payload["area"])


def terminal_velocity(payload, density=1.225, g=G):
    """Return the terminal fall speed sqrt(2 m g / (rho Cd A)) in m/s."""
    if density <= 0:
        raise ValueError("Density must be positive")

    return sqrt(2 * g * ballistic_coefficient(payload) / density)
