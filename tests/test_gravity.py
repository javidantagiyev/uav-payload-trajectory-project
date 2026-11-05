
import pytest

from src.physics.gravity import (
    G,
    gravity_acceleration,
    gravity_position,
    gravity_velocity
)


def test_gravity_acceleration():
    assert gravity_acceleration() == (0.0, 0.0, -G)


def test_gravity_position():
    position = gravity_position(
        (0, 0, 100),
        (10, 0, 0),
        2
    )

    assert position[0] == pytest.approx(20)
    assert position[1] == pytest.approx(0)
    assert position[2] == pytest.approx(100 - 0.5 * G * 4)


def test_gravity_velocity():
    velocity = gravity_velocity((10, 0, 5), 2)

    assert velocity[0] == pytest.approx(10)
    assert velocity[1] == pytest.approx(0)
    assert velocity[2] == pytest.approx(5 - G * 2)


def test_gravity_position_at_zero_time():
    position = gravity_position(
        (10, 20, 100),
        (5, 5, 5),
        0
    )

    assert position == (10, 20, 100)


def test_gravity_velocity_at_zero_time():
    velocity = gravity_velocity((10, 20, 5), 0)

    assert velocity == (10, 20, 5)
