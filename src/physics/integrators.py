
"""Numerical integration methods for the physics simulation."""


def add(a, b):
    """Add two vectors or state arrays."""
    if len(a) != len(b):
        raise ValueError("Vectors must have the same length")

    return tuple(a[i] + b[i] for i in range(len(a)))


def multiply(a, number):
    """Multiply a vector or state array by a scalar."""
    return tuple(value * number for value in a)


def euler_step(f, t, state, h):
    """Perform one Euler integration step."""
    if h <= 0:
        raise ValueError("Step size must be positive")

    return add(state, multiply(f(t, state), h))


def rk4_step(f, t, state, h):
    """Perform one fourth-order Runge-Kutta integration step."""
    if h <= 0:
        raise ValueError("Step size must be positive")

    k1 = f(t, state)
    k2 = f(t + h / 2, add(state, multiply(k1, h / 2)))
    k3 = f(t + h / 2, add(state, multiply(k2, h / 2)))
    k4 = f(t + h, add(state, multiply(k3, h)))

    total = add(
        add(k1, multiply(k2, 2)),
        add(multiply(k3, 2), k4)
    )

    return add(state, multiply(total, h / 6))
