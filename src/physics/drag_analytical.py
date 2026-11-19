
"""Analytical vertical drop from rest with quadratic drag (SI units)."""

# Assumes constant density, no wind and no horizontal motion.
# Velocity is negative (downward) in ENU.

from math import log, exp, sqrt

from src.physics.gravity import G


def check_terminal_speed(terminal_speed):
    """Raise ValueError if the terminal speed is not positive."""
    if terminal_speed <= 0:
        raise ValueError("Terminal speed must be positive")


def log_cosh(x):
    """Return ln(cosh(x)) for x >= 0 without overflow."""
    return x + log(1 + exp(-2 * x)) - log(2)


def acosh_exp(a):
    """Return acosh(exp(a)) for a >= 0 without overflow."""
    return a + log(1 + sqrt(1 - exp(-2 * a)))


def vertical_drop_velocity(t, terminal_speed, g=G):
    """Return vertical velocity -vt * tanh(g t / vt) in m/s."""
    check_terminal_speed(terminal_speed)

    if t < 0:
        raise ValueError("Time cannot be negative")

    x = g * t / terminal_speed

    # tanh written with exp(-2x) so it never overflows.
    return -terminal_speed * (1 - exp(-2 * x)) / (1 + exp(-2 * x))


def vertical_drop_height(t, z0, terminal_speed, g=G):
    """Return height z0 - (vt^2 / g) * ln(cosh(g t / vt)) in meters."""
    check_terminal_speed(terminal_speed)

    if t < 0:
        raise ValueError("Time cannot be negative")

    return z0 - terminal_speed ** 2 / g * log_cosh(g * t / terminal_speed)


def vertical_drop_time(z0, terminal_speed, g=G):
    """Return the time to fall from height z0 to the ground in seconds."""
    check_terminal_speed(terminal_speed)

    if z0 < 0:
        raise ValueError("Release height cannot be negative")

    a = z0 * g / terminal_speed ** 2

    return terminal_speed / g * acosh_exp(a)
