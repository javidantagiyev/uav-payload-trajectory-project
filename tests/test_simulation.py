
import pytest

from src.physics.gravity import G
from src.physics.simulation import (
    simulate,
    landing_point,
    flight_time
)


def gravity_model(t, state):
    return (state[3], state[4], state[5], 0.0, 0.0, -G)


def test_drop_time_matches_analytical():
    times, states = simulate(gravity_model, (0, 0, 100, 0, 0, 0))

    expected = (2 * 100 / G) ** 0.5

    assert flight_time(times) == pytest.approx(expected, rel=1e-6)
    assert states[-1][2] == pytest.approx(0)


def test_landing_point_with_horizontal_velocity():
    times, states = simulate(gravity_model, (0, 0, 100, 10, 5, 0))

    t = (2 * 100 / G) ** 0.5
    x, y = landing_point(states)

    assert x == pytest.approx(10 * t, rel=1e-6)
    assert y == pytest.approx(5 * t, rel=1e-6)


def test_euler_method_lands():
    times, states = simulate(
        gravity_model,
        (0, 0, 50, 0, 0, 0),
        step_size=0.001,
        method="euler"
    )

    expected = (2 * 50 / G) ** 0.5

    assert flight_time(times) == pytest.approx(expected, rel=1e-2)


def test_start_on_ground():
    times, states = simulate(gravity_model, (0, 0, 0, 0, 0, 0))

    assert len(states) == 1


def test_invalid_method():
    with pytest.raises(ValueError):
        simulate(gravity_model, (0, 0, 10, 0, 0, 0), method="rk2")


def test_invalid_step_size():
    with pytest.raises(ValueError):
        simulate(gravity_model, (0, 0, 10, 0, 0, 0), step_size=0)


def test_below_ground():
    with pytest.raises(ValueError):
        simulate(gravity_model, (0, 0, -1, 0, 0, 0))


def test_max_time():
    def floating(t, state):
        return (0, 0, 0, 0, 0, 0)

    with pytest.raises(RuntimeError):
        simulate(floating, (0, 0, 10, 0, 0, 0), max_time=1)
