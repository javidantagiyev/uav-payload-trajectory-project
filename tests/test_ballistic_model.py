
import pytest

from src.physics.ballistic_model import state_derivative


def test_state_derivative_without_drag():
    state = (0, 0, 100, 10, 5, 0)

    result = state_derivative(
        0,
        state,
        mass=1,
        drag_coefficient=0,
        area=0
    )

    assert result == pytest.approx(
        (10, 5, 0, 0, 0, -9.81)
    )


def test_state_derivative_with_drag():
    state = (0, 0, 100, 10, 0, 0)

    result = state_derivative(
        0,
        state,
        mass=2,
        density=1.225,
        drag_coefficient=0.8,
        area=0.02
    )

    assert result[3] < 0
    assert result[4] == pytest.approx(0)
    assert result[5] == pytest.approx(-9.81)


def test_state_derivative_with_wind():
    state = (0, 0, 100, 5, 0, 0)

    result = state_derivative(
        0,
        state,
        mass=1,
        density=1.225,
        drag_coefficient=0.8,
        area=0.02,
        wind=(5, 0, 0)
    )

    # No relative horizontal air velocity.
    assert result[3] == pytest.approx(0)


def test_invalid_state_length():
    with pytest.raises(ValueError):
        state_derivative(0, (0, 0, 100))


def test_invalid_mass():
    with pytest.raises(ValueError):
        state_derivative(
            0,
            (0, 0, 100, 0, 0, 0),
            mass=0
        )
