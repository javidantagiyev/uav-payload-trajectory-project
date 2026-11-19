
import math

import numpy as np
import pytest

from src.physics.gravity import G
from src.physics.monte_carlo import (
    PARAMETER_NAMES,
    sample_parameters,
    release_state,
    run_landing,
    monte_carlo_landings,
    landing_statistics,
    confidence_ellipse,
    sensitivity_ranking,
    correlation_ranking
)


def nominal_parameters():
    return {
        "mass": 1.0,
        "area": math.pi * 0.075 ** 2,
        "drag_coefficient": 0.47,
        "density": 1.225,
        "wind_speed": 6.0,
        "wind_direction": 270.0,
        "release_x": 0.0,
        "release_y": 0.0,
        "release_z": 100.0,
        "release_vx": 15.0,
        "release_vy": 0.0,
        "release_vz": 0.0,
        "release_delay": 0.0
    }


def vacuum_parameters():
    params = nominal_parameters()
    params["drag_coefficient"] = 1e-12
    params["wind_speed"] = 0.0

    return params


def test_sample_parameters_keys_and_count():
    samples = sample_parameters(nominal_parameters(), {"mass": 0.02}, 20, seed=1)

    assert len(samples) == 20
    assert set(samples[0]) == set(PARAMETER_NAMES)


def test_sample_parameters_same_seed():
    sigmas = {"mass": 0.02, "wind_speed": 1.5}

    first = sample_parameters(nominal_parameters(), sigmas, 10, seed=5)
    second = sample_parameters(nominal_parameters(), sigmas, 10, seed=5)

    assert first == second


def test_sample_parameters_statistics():
    samples = sample_parameters(nominal_parameters(), {"wind_speed": 1.5}, 5000, seed=2)
    values = np.array([params["wind_speed"] for params in samples])

    assert np.mean(values) == pytest.approx(6.0, abs=0.1)
    assert np.std(values) == pytest.approx(1.5, rel=0.05)


def test_sample_parameters_without_sigma_keep_nominal():
    samples = sample_parameters(nominal_parameters(), {"mass": 0.02}, 5, seed=3)

    assert all(params["drag_coefficient"] == 0.47 for params in samples)


def test_sample_parameters_stay_positive():
    sigmas = {"mass": 5.0, "area": 1.0, "drag_coefficient": 5.0, "density": 5.0}
    samples = sample_parameters(nominal_parameters(), sigmas, 500, seed=4)

    for name in ("mass", "area", "drag_coefficient", "density"):
        assert min(params[name] for params in samples) > 0


def test_sample_parameters_wind_direction_wraps():
    samples = sample_parameters(nominal_parameters(), {"wind_direction": 200.0}, 500, seed=6)

    assert all(0 <= params["wind_direction"] < 360 for params in samples)


def test_sample_parameters_missing_nominal():
    params = nominal_parameters()
    del params["mass"]

    with pytest.raises(ValueError):
        sample_parameters(params, {}, 5)


def test_sample_parameters_unknown_sigma():
    with pytest.raises(ValueError):
        sample_parameters(nominal_parameters(), {"color": 1.0}, 5)


def test_sample_parameters_negative_sigma():
    with pytest.raises(ValueError):
        sample_parameters(nominal_parameters(), {"mass": -0.1}, 5)


def test_sample_parameters_invalid_count():
    with pytest.raises(ValueError):
        sample_parameters(nominal_parameters(), {}, 0)


def test_sample_parameters_nonpositive_nominal():
    params = nominal_parameters()
    params["density"] = 0.0

    with pytest.raises(ValueError):
        sample_parameters(params, {}, 5)


def test_release_state_shifted_by_delay():
    params = nominal_parameters()
    params["release_delay"] = 0.1

    state = release_state(params)

    assert state == pytest.approx((1.5, 0, 100, 15, 0, 0))


def test_run_landing_matches_vacuum_solution():
    x, y, t = run_landing(vacuum_parameters(), step_size=0.01)

    expected_time = math.sqrt(2 * 100 / G)

    assert t == pytest.approx(expected_time, rel=1e-6)
    assert x == pytest.approx(15 * expected_time, rel=1e-6)
    assert y == pytest.approx(0, abs=1e-9)


def test_run_landing_wind_pushes_downwind():
    calm = nominal_parameters()
    calm["wind_speed"] = 0.0

    x_calm, _, _ = run_landing(calm)
    x_wind, _, _ = run_landing(nominal_parameters())

    assert x_wind > x_calm


def test_run_landing_power_profile_weaker_near_ground():
    # Release at 5 m: the power law gives less wind than the 10 m reference.
    params = nominal_parameters()
    params["release_z"] = 5.0
    params["release_vx"] = 0.0

    x_constant, _, _ = run_landing(params)
    x_power, _, _ = run_landing(params, wind_profile="power")

    assert 0 < x_power < x_constant


def test_run_landing_invalid_profile():
    with pytest.raises(ValueError):
        run_landing(nominal_parameters(), wind_profile="log")


def test_monte_carlo_landings_shape():
    samples, points = monte_carlo_landings(
        nominal_parameters(),
        {"wind_speed": 1.0},
        8,
        seed=1,
        step_size=0.05
    )

    assert len(samples) == 8
    assert points.shape == (8, 3)


def test_monte_carlo_without_uncertainty_is_nominal():
    samples, points = monte_carlo_landings(nominal_parameters(), {}, 3, seed=1, step_size=0.05)
    x, y, t = run_landing(nominal_parameters(), step_size=0.05)

    assert points[:, 0] == pytest.approx([x, x, x])
    assert points[:, 2] == pytest.approx([t, t, t])


def test_landing_statistics_known_points():
    points = np.array([[3, 4], [0, 0], [-3, -4], [0, 0]])

    stats = landing_statistics(points, (0, 0))

    assert stats["mean_x"] == pytest.approx(0)
    assert stats["mean_y"] == pytest.approx(0)
    assert stats["cep50"] == pytest.approx(2.5)
    assert stats["rms"] == pytest.approx(math.sqrt(12.5))
    assert stats["fraction_within_10m"] == pytest.approx(1.0)


def test_landing_statistics_fraction_within_10m():
    points = np.array([[5, 0], [20, 0]])

    assert landing_statistics(points, (0, 0))["fraction_within_10m"] == pytest.approx(0.5)


def test_landing_statistics_invalid_points():
    with pytest.raises(ValueError):
        landing_statistics(np.array([[1, 2]]), (0, 0))


def test_cep_of_circular_gaussian():
    rng = np.random.default_rng(0)
    points = rng.normal(0, 2.0, size=(20000, 2))

    stats = landing_statistics(points, (0, 0))

    # Rayleigh distribution: CEP50 = 1.1774 sigma, CEP95 = 2.4477 sigma.
    assert stats["cep50"] == pytest.approx(1.1774 * 2.0, rel=0.03)
    assert stats["cep95"] == pytest.approx(2.4477 * 2.0, rel=0.03)


def test_confidence_ellipse_axes_and_angle():
    rng = np.random.default_rng(1)
    points = np.column_stack((
        rng.normal(10, 4.0, 20000),
        rng.normal(-5, 1.0, 20000)
    ))

    center, semi_major, semi_minor, angle = confidence_ellipse(points, 0.95)

    scale = math.sqrt(-2 * math.log(0.05))

    assert center == pytest.approx((10, -5), abs=0.1)
    assert semi_major == pytest.approx(scale * 4.0, rel=0.03)
    assert semi_minor == pytest.approx(scale * 1.0, rel=0.03)
    assert min(angle, 180 - angle) == pytest.approx(0, abs=1)


def test_confidence_ellipse_rotated():
    rng = np.random.default_rng(2)
    along = rng.normal(0, 3.0, 20000)
    across = rng.normal(0, 0.5, 20000)

    points = np.column_stack((along - across, along + across)) / math.sqrt(2)

    _, _, _, angle = confidence_ellipse(points)

    assert angle == pytest.approx(45, abs=1)


def test_confidence_ellipse_coverage():
    rng = np.random.default_rng(3)
    points = rng.multivariate_normal((0, 0), [[4, 1.5], [1.5, 2]], size=20000)

    center, semi_major, semi_minor, angle = confidence_ellipse(points, 0.95)

    theta = math.radians(angle)
    dx = points[:, 0] - center[0]
    dy = points[:, 1] - center[1]
    u = dx * math.cos(theta) + dy * math.sin(theta)
    v = -dx * math.sin(theta) + dy * math.cos(theta)

    inside = (u / semi_major) ** 2 + (v / semi_minor) ** 2 <= 1

    assert np.mean(inside) == pytest.approx(0.95, abs=0.01)


def test_confidence_ellipse_invalid_probability():
    with pytest.raises(ValueError):
        confidence_ellipse(np.zeros((5, 2)), probability=1.0)


def test_confidence_ellipse_invalid_points():
    with pytest.raises(ValueError):
        confidence_ellipse(np.zeros((2, 2)))


def test_sensitivity_ranking_order():
    sigmas = {"wind_speed": 1.5, "release_x": 0.1, "mass": 0.0}

    ranking = sensitivity_ranking(nominal_parameters(), sigmas, step_size=0.05)

    assert [name for name, _ in ranking] == ["wind_speed", "release_x"]
    assert ranking[1][1] == pytest.approx(0.1, rel=1e-6)


def test_sensitivity_ranking_unknown_parameter():
    with pytest.raises(ValueError):
        sensitivity_ranking(nominal_parameters(), {"color": 1.0})


def test_correlation_ranking():
    samples, points = monte_carlo_landings(
        nominal_parameters(),
        {"wind_speed": 1.5, "release_vy": 0.01},
        40,
        seed=3,
        step_size=0.05
    )

    # Target far upwind, so the radial miss grows monotonically with wind speed.
    x, y, _ = run_landing(nominal_parameters(), step_size=0.05)
    ranking = correlation_ranking(samples, points, (x - 100, y))

    assert [name for name, _ in ranking] == ["wind_speed", "release_vy"]
    assert 0 <= ranking[0][1] <= 1


def test_correlation_ranking_length_mismatch():
    with pytest.raises(ValueError):
        correlation_ranking([nominal_parameters()], np.zeros((2, 3)), (0, 0))
