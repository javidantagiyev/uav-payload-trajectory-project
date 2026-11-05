
import pytest

from src.physics.aerodynamic_drag import (
    magnitude,
    air_velocity,
    drag_force,
    drag_magnitude,
    drag_acceleration
)


def test_vector_magnitude():
    assert magnitude((3, 4, 0)) == pytest.approx(5)


def test_air_velocity():
    result = air_velocity(
        (10, 5, 0),
        (3, 2, 0)
    )

    assert result == (7, 3, 0)


def test_drag_force_direction():
    force = drag_force(
        (10, 0, 0),
        1.225,
        0.8,
        0.02
    )

    assert force[0] < 0
    assert force[1] == pytest.approx(0)
    assert force[2] == pytest.approx(0)


def test_drag_magnitude():
    result = drag_magnitude(
        (10, 0, 0),
        1.225,
        0.8,
        0.02
    )

    expected = 0.5 * 1.225 * 0.8 * 0.02 * 100

    assert result == pytest.approx(expected)


def test_zero_relative_velocity():
    force = drag_force(
        (0, 0, 0),
        1.225,
        0.8,
        0.02
    )

    assert force == pytest.approx((0, 0, 0))


def test_drag_acceleration():
    acceleration = drag_acceleration(
        (10, 0, 0),
        2,
        1.225,
        0.8,
        0.02
    )

    assert acceleration[0] < 0
    assert acceleration[1] == pytest.approx(0)
    assert acceleration[2] == pytest.approx(0)


def test_invalid_drag_parameters():
    with pytest.raises(ValueError):
        drag_force((10, 0, 0), -1, 0.8, 0.02)


def test_invalid_mass():
    with pytest.raises(ValueError):
        drag_acceleration((10, 0, 0), 0)
