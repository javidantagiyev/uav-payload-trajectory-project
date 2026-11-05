
import math
import pytest

from src.physics.integrators import (
    add,
    multiply,
    euler_step,
    rk4_step
)


def test_add():
    assert add((1, 2, 3), (4, 5, 6)) == (5, 7, 9)


def test_multiply():
    assert multiply((1, 2, 3), 2) == (2, 4, 6)


def test_add_different_lengths():
    with pytest.raises(ValueError):
        add((1, 2), (1, 2, 3))


def test_euler_step():
    def f(t, state):
        return (1, 2)

    result = euler_step(f, 0, (0, 0), 0.5)

    assert result == (0.5, 1.0)


def test_rk4_step_constant_derivative():
    def f(t, state):
        return (2, 4)

    result = rk4_step(f, 0, (0, 0), 0.5)

    assert result == pytest.approx((1, 2))


def test_rk4_exponential_accuracy():
    def f(t, state):
        return (state[0],)

    result = rk4_step(f, 0, (1,), 0.1)

    expected = math.exp(0.1)

    assert result[0] == pytest.approx(expected, rel=1e-5)


def test_invalid_euler_step():
    with pytest.raises(ValueError):
        euler_step(lambda t, s: s, 0, (1,), 0)


def test_invalid_rk4_step():
    with pytest.raises(ValueError):
        rk4_step(lambda t, s: s, 0, (1,), -0.1)
