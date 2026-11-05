
import pytest

from src.physics.wind_model import (
    constant_wind,
    wind_magnitude
)


def test_constant_wind():
    wind = constant_wind(3, 4, 0)

    assert wind == (3, 4, 0)


def test_zero_wind():
    wind = constant_wind()

    assert wind == (0, 0, 0)


def test_wind_magnitude():
    assert wind_magnitude((3, 4, 0)) == pytest.approx(5)


def test_vertical_wind():
    assert wind_magnitude((0, 0, 10)) == pytest.approx(10)
