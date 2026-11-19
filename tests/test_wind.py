
import math

import numpy as np
import pytest

from src.physics.wind_model import (
    constant_wind,
    wind_magnitude,
    wind_from_direction,
    wind_direction,
    headwind_crosswind,
    power_law_wind,
    log_law_wind,
    layered_wind,
    discrete_gust,
    turbulence_series,
    turbulent_wind
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


def test_north_wind_blows_south():
    wind = wind_from_direction(5, 0)

    assert wind == pytest.approx((0, -5, 0))


def test_west_wind_blows_east():
    wind = wind_from_direction(6, 270)

    assert wind == pytest.approx((6, 0, 0))


def test_negative_wind_speed():
    with pytest.raises(ValueError):
        wind_from_direction(-1, 90)


def test_wind_direction_inverse():
    for direction in (0, 45, 90, 135, 180, 225, 270, 315, 359):
        wind = wind_from_direction(7, direction)

        assert wind_direction(wind) == pytest.approx(direction)


def test_wind_direction_range():
    direction = wind_direction(wind_from_direction(3, -10))

    assert 0 <= direction < 360
    assert direction == pytest.approx(350)


def test_tailwind_and_headwind():
    wind = wind_from_direction(5, 270)

    along, cross = headwind_crosswind(wind, 90)
    assert along == pytest.approx(5)
    assert cross == pytest.approx(0)

    along, cross = headwind_crosswind(wind, 270)
    assert along == pytest.approx(-5)


def test_crosswind_to_the_right():
    # Flying north, a west wind pushes the payload east (right of track).
    along, cross = headwind_crosswind(wind_from_direction(4, 270), 0)

    assert along == pytest.approx(0)
    assert cross == pytest.approx(4)


def test_power_law_at_reference_height():
    wind = power_law_wind((6, 0, 0))

    assert wind(0, (0, 0, 10)) == pytest.approx((6, 0, 0))


def test_power_law_value():
    wind = power_law_wind((6, 0, 0), reference_height=10, exponent=1 / 7)

    assert wind(0, (0, 0, 500))[0] == pytest.approx(6 * 50 ** (1 / 7))


def test_power_law_clips_low_height():
    wind = power_law_wind((6, 0, 0))

    assert wind(0, (0, 0, -5)) == pytest.approx(wind(0, (0, 0, 0.1)))


def test_power_law_invalid_height():
    with pytest.raises(ValueError):
        power_law_wind((6, 0, 0), reference_height=0)


def test_power_law_invalid_exponent():
    with pytest.raises(ValueError):
        power_law_wind((6, 0, 0), exponent=-0.1)


def test_log_law_at_reference_height():
    wind = log_law_wind((0, 4, 0))

    assert wind(0, (0, 0, 10)) == pytest.approx((0, 4, 0))


def test_log_law_value():
    wind = log_law_wind((4, 0, 0), reference_height=10, roughness_length=0.03)

    expected = 4 * math.log(100 / 0.03) / math.log(10 / 0.03)

    assert wind(0, (0, 0, 100))[0] == pytest.approx(expected)


def test_log_law_zero_below_roughness():
    wind = log_law_wind((4, 0, 0), roughness_length=0.03)

    assert wind(0, (0, 0, 0.02)) == (0.0, 0.0, 0.0)


def test_log_law_invalid_roughness():
    with pytest.raises(ValueError):
        log_law_wind((4, 0, 0), roughness_length=0)


def test_log_law_invalid_reference_height():
    with pytest.raises(ValueError):
        log_law_wind((4, 0, 0), reference_height=0.01, roughness_length=0.03)


def test_layered_wind_interpolation():
    wind = layered_wind([0, 100, 300], [(0, 0, 0), (4, 2, 0), (8, 0, 0)])

    assert wind(0, (0, 0, 50)) == pytest.approx((2, 1, 0))
    assert wind(0, (0, 0, 200)) == pytest.approx((6, 1, 0))


def test_layered_wind_constant_outside_range():
    wind = layered_wind([10, 100], [(1, 0, 0), (5, 0, 0)])

    assert wind(0, (0, 0, 0)) == pytest.approx((1, 0, 0))
    assert wind(0, (0, 0, 1000)) == pytest.approx((5, 0, 0))


def test_layered_wind_empty():
    with pytest.raises(ValueError):
        layered_wind([], [])


def test_layered_wind_length_mismatch():
    with pytest.raises(ValueError):
        layered_wind([0, 100], [(1, 0, 0)])


def test_layered_wind_not_increasing():
    with pytest.raises(ValueError):
        layered_wind([100, 100], [(1, 0, 0), (2, 0, 0)])


def test_discrete_gust_shape():
    wind = discrete_gust((2, 0, 0), (4, 0, -2), start_time=1.0, duration=2.0)

    assert wind(0.5, (0, 0, 10)) == pytest.approx((2, 0, 0))
    assert wind(1.0, (0, 0, 10)) == pytest.approx((2, 0, 0))
    assert wind(2.0, (0, 0, 10)) == pytest.approx((6, 0, -2))
    assert wind(3.0, (0, 0, 10)) == pytest.approx((2, 0, 0))
    assert wind(4.0, (0, 0, 10)) == pytest.approx((2, 0, 0))


def test_discrete_gust_on_profile():
    base = power_law_wind((6, 0, 0))
    wind = discrete_gust(base, (0, 3, 0), start_time=0.0, duration=2.0)

    assert wind(1.0, (0, 0, 10)) == pytest.approx((6, 3, 0))


def test_discrete_gust_invalid_duration():
    with pytest.raises(ValueError):
        discrete_gust((0, 0, 0), (1, 0, 0), start_time=0, duration=0)


def test_discrete_gust_invalid_amplitude():
    with pytest.raises(ValueError):
        discrete_gust((0, 0, 0), (1, 0), start_time=0, duration=1)


def test_turbulence_statistics():
    times, series = turbulence_series(
        intensity=1.5,
        length_scale=50,
        airspeed=15,
        duration=2000,
        step=0.1,
        seed=1
    )

    assert np.mean(series, axis=0) == pytest.approx((0, 0, 0), abs=0.3)
    assert np.std(series, axis=0) == pytest.approx((1.5, 1.5, 1.5), rel=0.1)


def test_turbulence_same_seed():
    first = turbulence_series(1.0, 50, 15, 10, 0.1, seed=7)[1]
    second = turbulence_series(1.0, 50, 15, 10, 0.1, seed=7)[1]
    third = turbulence_series(1.0, 50, 15, 10, 0.1, seed=8)[1]

    assert np.array_equal(first, second)
    assert not np.array_equal(first, third)


def test_turbulence_per_axis_intensity():
    series = turbulence_series((2.0, 2.0, 0.0), 50, 15, 100, 0.1, seed=3)[1]

    assert np.all(series[:, 2] == 0)


def test_turbulent_wind_adds_base():
    wind = turbulent_wind((5, 0, 0), 0.0, 50, 15, 10, step=0.1, seed=1)

    value = wind(3.33, (0, 0, 100))

    assert value == pytest.approx((5, 0, 0))
    assert all(type(component) is float for component in value)


def test_turbulent_wind_interpolates_series():
    times, series = turbulence_series(1.0, 50, 15, 10, 0.1, seed=2)
    wind = turbulent_wind((0, 0, 0), 1.0, 50, 15, 10, step=0.1, seed=2)

    assert wind(0.25, (0, 0, 0))[0] == pytest.approx(
        0.5 * (series[2, 0] + series[3, 0])
    )


def test_turbulent_wind_with_profile():
    base = power_law_wind((6, 0, 0))
    wind = turbulent_wind(base, 0.0, 50, 15, 10, step=0.1, seed=1)

    assert wind(1.0, (0, 0, 10)) == pytest.approx((6, 0, 0))


def test_turbulence_invalid_length_scale():
    with pytest.raises(ValueError):
        turbulence_series(1.0, 0, 15, 10, 0.1)


def test_turbulence_invalid_airspeed():
    with pytest.raises(ValueError):
        turbulence_series(1.0, 50, 0, 10, 0.1)


def test_turbulence_invalid_step():
    with pytest.raises(ValueError):
        turbulence_series(1.0, 50, 15, 10, 0)


def test_turbulence_invalid_intensity_length():
    with pytest.raises(ValueError):
        turbulence_series((1.0, 1.0), 50, 15, 10, 0.1)


def test_turbulence_negative_intensity():
    with pytest.raises(ValueError):
        turbulence_series(-1.0, 50, 15, 10, 0.1)
