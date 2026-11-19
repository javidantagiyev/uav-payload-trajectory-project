
from math import sqrt, tanh, cosh, log, acosh, exp

import pytest

from src.physics.gravity import G
from src.physics.ballistic_model import state_derivative
from src.physics.integrators import euler_step, rk4_step
from src.physics.simulation import simulate, flight_time
from src.physics.drag_analytical import (
    vertical_drop_velocity,
    vertical_drop_height,
    vertical_drop_time
)


MASS = 1.0
DENSITY = 1.225
DRAG_COEFFICIENT = 1.0
AREA = 0.02
HEIGHT = 500.0

TERMINAL_SPEED = sqrt(2 * MASS * G / (DENSITY * DRAG_COEFFICIENT * AREA))


def model(t, state):
    return state_derivative(
        t,
        state,
        mass=MASS,
        density=DENSITY,
        drag_coefficient=DRAG_COEFFICIENT,
        area=AREA
    )


def integrate_to(step, h, end_time):
    """Integrate the vertical drop with a fixed step up to end_time."""
    t = 0.0
    state = (0.0, 0.0, HEIGHT, 0.0, 0.0, 0.0)

    for _ in range(round(end_time / h)):
        state = step(model, t, state, h)
        t += h

    return state


def height_error(step, h, end_time=4.0):
    state = integrate_to(step, h, end_time)

    expected = vertical_drop_height(end_time, HEIGHT, TERMINAL_SPEED)

    return abs(state[2] - expected)


def test_velocity_matches_tanh():
    t = 3.0
    expected = -TERMINAL_SPEED * tanh(G * t / TERMINAL_SPEED)

    assert vertical_drop_velocity(t, TERMINAL_SPEED) == pytest.approx(expected)


def test_height_matches_log_cosh():
    t = 3.0
    expected = HEIGHT - TERMINAL_SPEED ** 2 / G * log(cosh(G * t / TERMINAL_SPEED))

    assert vertical_drop_height(t, HEIGHT, TERMINAL_SPEED) == pytest.approx(expected)


def test_drop_time_matches_acosh():
    expected = TERMINAL_SPEED / G * acosh(exp(HEIGHT * G / TERMINAL_SPEED ** 2))

    assert vertical_drop_time(HEIGHT, TERMINAL_SPEED) == pytest.approx(expected)


def test_height_is_zero_at_drop_time():
    t = vertical_drop_time(HEIGHT, TERMINAL_SPEED)

    assert vertical_drop_height(t, HEIGHT, TERMINAL_SPEED) == pytest.approx(0, abs=1e-9)


def test_velocity_approaches_terminal_speed():
    speed = vertical_drop_velocity(1000, TERMINAL_SPEED)

    assert speed == pytest.approx(-TERMINAL_SPEED)


def test_large_arguments_do_not_overflow():
    # cosh(1e4) and exp(1e4) would overflow a float.
    assert vertical_drop_height(1e4, 1e5, 1.0, g=1.0) == pytest.approx(9e4 + log(2))
    assert vertical_drop_time(1e5, 1.0, g=1.0) == pytest.approx(1e5 + log(2))


def test_small_time_matches_free_fall():
    t = 0.01

    assert vertical_drop_height(t, HEIGHT, TERMINAL_SPEED) == pytest.approx(
        HEIGHT - 0.5 * G * t ** 2,
        rel=1e-9
    )


def test_rk4_simulation_matches_analytical_landing():
    times, states = simulate(model, (0, 0, HEIGHT, 0, 0, 0), step_size=0.01)

    expected = vertical_drop_time(HEIGHT, TERMINAL_SPEED)

    assert flight_time(times) == pytest.approx(expected, rel=1e-6)


def test_euler_simulation_close_to_analytical_landing():
    times, states = simulate(
        model,
        (0, 0, HEIGHT, 0, 0, 0),
        step_size=0.01,
        method="euler"
    )

    expected = vertical_drop_time(HEIGHT, TERMINAL_SPEED)

    assert flight_time(times) == pytest.approx(expected, rel=1e-2)


def test_rk4_error_much_smaller_than_euler():
    euler_error = height_error(euler_step, 0.05)
    rk4_error = height_error(rk4_step, 0.05)

    assert rk4_error < euler_error * 1e-4


def test_euler_is_first_order():
    ratio = height_error(euler_step, 0.1) / height_error(euler_step, 0.05)

    assert ratio == pytest.approx(2, rel=0.1)


def test_rk4_is_fourth_order():
    ratio = height_error(rk4_step, 0.1) / height_error(rk4_step, 0.05)

    assert ratio == pytest.approx(16, rel=0.1)


def test_invalid_terminal_speed():
    with pytest.raises(ValueError):
        vertical_drop_velocity(1.0, 0)


def test_invalid_time():
    with pytest.raises(ValueError):
        vertical_drop_height(-1.0, HEIGHT, TERMINAL_SPEED)


def test_invalid_height():
    with pytest.raises(ValueError):
        vertical_drop_time(-1.0, TERMINAL_SPEED)
