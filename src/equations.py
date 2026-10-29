"""Basic physics equations in East-North-Up coordinates (SI units)."""

from math import sqrt

G = 9.81


def add(a, b):
    return tuple(a[i] + b[i] for i in range(len(a)))


def multiply(a, number):
    return tuple(value * number for value in a)


def magnitude(v):
    return sqrt(sum(value ** 2 for value in v))


def gravity_position(p0, v0, t):
    return (
        p0[0] + v0[0] * t,
        p0[1] + v0[1] * t,
        p0[2] + v0[2] * t - 0.5 * G * t ** 2,
    )


def gravity_velocity(v0, t):
    return (v0[0], v0[1], v0[2] - G * t)


def air_velocity(velocity, wind):
    return tuple(velocity[i] - wind[i] for i in range(3))


def drag_force(velocity, density, drag_coefficient, area):
    speed = magnitude(velocity)
    factor = -0.5 * density * drag_coefficient * area * speed
    return multiply(velocity, factor)


def drag_magnitude(velocity, density, drag_coefficient, area):
    speed = magnitude(velocity)
    return 0.5 * density * drag_coefficient * area * speed ** 2


def state_derivative(t, state, mass=1.0, density=1.225,
                     drag_coefficient=0.0, area=0.0, wind=(0, 0, 0)):
    if mass <= 0:
        raise ValueError("Mass must be positive")
    vx, vy, vz = state[3], state[4], state[5]
    relative_velocity = air_velocity((vx, vy, vz), wind)
    drag = drag_force(relative_velocity, density, drag_coefficient, area)
    return (vx, vy, vz,
            drag[0] / mass,
            drag[1] / mass,
            -G + drag[2] / mass)


def euler_step(f, t, state, h):
    if h <= 0:
        raise ValueError("Step size must be positive")
    return add(state, multiply(f(t, state), h))


def rk4_step(f, t, state, h):
    if h <= 0:
        raise ValueError("Step size must be positive")
    k1 = f(t, state)
    k2 = f(t + h / 2, add(state, multiply(k1, h / 2)))
    k3 = f(t + h / 2, add(state, multiply(k2, h / 2)))
    k4 = f(t + h, add(state, multiply(k3, h)))
    total = add(add(k1, multiply(k2, 2)), add(multiply(k3, 2), k4))
    return add(state, multiply(total, h / 6))


def position_error(predicted, actual):
    difference = tuple(predicted[i] - actual[i] for i in range(3))
    return magnitude(difference)


def rmse(errors):
    if len(errors) == 0:
        raise ValueError("At least one error is required")
    return sqrt(sum(error ** 2 for error in errors) / len(errors))
