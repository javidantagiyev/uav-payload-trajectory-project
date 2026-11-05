
import pytest

from src.physics.evaluation import (
    position_error,
    rmse
)


def test_position_error():
    predicted = (3, 4, 0)
    actual = (0, 0, 0)

    assert position_error(predicted, actual) == pytest.approx(5)


def test_zero_position_error():
    position = (10, 20, 30)

    assert position_error(position, position) == 0


def test_rmse():
    errors = [1, 2, 3]

    expected = (14 / 3) ** 0.5

    assert rmse(errors) == pytest.approx(expected)


def test_rmse_single_value():
    assert rmse([5]) == pytest.approx(5)


def test_rmse_empty_list():
    with pytest.raises(ValueError):
        rmse([])


def test_position_error_invalid_dimensions():
    with pytest.raises(ValueError):
        position_error((1, 2), (1, 2, 3))
