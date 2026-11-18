
"""Gravity equations in East-North-Up coordinates (SI units)."""

G = 9.81


def gravity_acceleration(g=G):
    """Return gravitational acceleration in ENU coordinates."""
    return (0.0, 0.0, -g)


def gravity_position(p0, v0, t, g=G):
    """Calculate position under gravity without aerodynamic drag."""
    return (
        p0[0] + v0[0] * t,
        p0[1] + v0[1] * t,
        p0[2] + v0[2] * t - 0.5 * g * t ** 2,
    )


def gravity_velocity(v0, t, g=G):
    """Calculate velocity under gravity without aerodynamic drag."""
    return (
        v0[0],
        v0[1],
        v0[2] - g * t,
    )
