
import pytest

from src.physics.atmosphere import (
    T0,
    P0,
    temperature,
    pressure,
    isa_density,
    density_function
)


def test_sea_level_values():
    assert temperature(0) == pytest.approx(T0)
    assert pressure(0) == pytest.approx(P0)
    assert isa_density(0) == pytest.approx(1.225, abs=1e-3)


def test_density_at_1000_m():
    assert isa_density(1000) == pytest.approx(1.112, abs=1e-3)


def test_temperature_lapse_rate():
    assert temperature(1000) == pytest.approx(281.65)


def test_density_decreases_with_altitude():
    assert isa_density(-28) > isa_density(0) > isa_density(500) > isa_density(5000)


def test_density_function_uses_ground_altitude():
    density = density_function(ground_altitude=-28.0)

    assert density(0) == pytest.approx(isa_density(-28.0))
    assert density(528) == pytest.approx(isa_density(500))


def test_density_function_default_is_sea_level():
    density = density_function()

    assert density(100) == pytest.approx(isa_density(100))


def test_altitude_too_high():
    with pytest.raises(ValueError):
        isa_density(12000)


def test_altitude_too_low():
    with pytest.raises(ValueError):
        temperature(-600)


def test_invalid_ground_altitude():
    with pytest.raises(ValueError):
        density_function(ground_altitude=20000)
