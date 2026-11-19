
"""Monte Carlo landing dispersion and sensitivity analysis (SI units)."""

import math

import numpy as np

from src.physics.ballistic_model import state_derivative
from src.physics.simulation import (
    simulate,
    landing_point,
    flight_time
)
from src.physics.wind_model import (
    wind_from_direction,
    power_law_wind
)

PARAMETER_NAMES = (
    "mass",
    "area",
    "drag_coefficient",
    "density",
    "wind_speed",
    "wind_direction",
    "release_x",
    "release_y",
    "release_z",
    "release_vx",
    "release_vy",
    "release_vz",
    "release_delay"
)

POSITIVE_PARAMETERS = ("mass", "area", "drag_coefficient", "density")

# Sampled positive parameters are truncated at this fraction of their nominal value.
MINIMUM_POSITIVE_FRACTION = 0.01

WIND_PROFILES = (None, "power")


def check_parameters(nominal, sigmas):
    """Validate the nominal and sigma dictionaries."""
    for name in PARAMETER_NAMES:
        if name not in nominal:
            raise ValueError("Nominal parameters are missing '" + name + "'")

    for name in POSITIVE_PARAMETERS:
        if nominal[name] <= 0:
            raise ValueError("Parameter '" + name + "' must be positive")

    for name, sigma in sigmas.items():
        if name not in PARAMETER_NAMES:
            raise ValueError("Unknown uncertain parameter '" + name + "'")

        if sigma < 0:
            raise ValueError("Standard deviations cannot be negative")


def sample_parameters(nominal, sigmas, count, seed=None):
    """Draw independent Gaussian parameter sets.

    Parameters missing from sigmas are kept at their nominal value.

    Returns:
        list of dictionaries with the keys of PARAMETER_NAMES.
    """
    check_parameters(nominal, sigmas)

    if count <= 0:
        raise ValueError("Sample count must be positive")

    rng = np.random.default_rng(seed)

    columns = {}

    for name in PARAMETER_NAMES:
        values = nominal[name] + sigmas.get(name, 0.0) * rng.standard_normal(count)

        if name in POSITIVE_PARAMETERS:
            values = np.maximum(values, MINIMUM_POSITIVE_FRACTION * nominal[name])

        if name == "wind_speed":
            values = np.maximum(values, 0.0)

        if name == "wind_direction":
            values = np.mod(values, 360.0)

        columns[name] = values

    return [
        {name: float(columns[name][k]) for name in PARAMETER_NAMES}
        for k in range(count)
    ]


def release_state(params):
    """Return the release state, shifted by the UAV motion during the release delay."""
    position = (params["release_x"], params["release_y"], params["release_z"])
    velocity = (params["release_vx"], params["release_vy"], params["release_vz"])
    delay = params["release_delay"]

    shifted = tuple(position[i] + velocity[i] * delay for i in range(3))

    return shifted + velocity


def build_wind(params, wind_profile=None):
    """Return the wind vector or wind(t, position) for a parameter set.

    wind_profile None gives a constant wind, "power" a power law with
    wind_speed as the value at 10 m.
    """
    if wind_profile not in WIND_PROFILES:
        raise ValueError("Wind profile must be None or 'power'")

    wind = wind_from_direction(params["wind_speed"], params["wind_direction"])

    if wind_profile == "power":
        return power_law_wind(wind)

    return wind


def run_landing(params, step_size=0.02, wind_profile=None):
    """Simulate one drop and return (x, y, flight_time)."""
    wind = build_wind(params, wind_profile)

    def model(t, state):
        return state_derivative(
            t,
            state,
            mass=params["mass"],
            density=params["density"],
            drag_coefficient=params["drag_coefficient"],
            area=params["area"],
            wind=wind
        )

    times, states = simulate(
        model,
        release_state(params),
        step_size=step_size
    )

    x, y = landing_point(states)

    return x, y, flight_time(times)


def monte_carlo_landings(nominal, sigmas, count, seed=None, step_size=0.02,
                         wind_profile=None):
    """Run a Monte Carlo landing study.

    Returns:
        (samples, points) where points is a numpy array (count, 3) of x, y, flight time.
    """
    samples = sample_parameters(nominal, sigmas, count, seed)

    points = np.array([
        run_landing(params, step_size, wind_profile)
        for params in samples
    ])

    return samples, points


def radial_miss(points, target):
    """Return the horizontal distance of each landing point from the target (m)."""
    points = np.asarray(points, dtype=float)

    return np.hypot(points[:, 0] - target[0], points[:, 1] - target[1])


def landing_statistics(points, target):
    """Summarise landing dispersion around a target (x, y).

    cep50 and cep95 are the 50th and 95th percentiles of the radial miss.
    """
    points = np.asarray(points, dtype=float)

    if points.ndim != 2 or points.shape[0] < 2 or points.shape[1] < 2:
        raise ValueError("Points must be an array with at least 2 rows of (x, y)")

    miss = radial_miss(points, target)

    return {
        "mean_x": float(np.mean(points[:, 0])),
        "mean_y": float(np.mean(points[:, 1])),
        "std_x": float(np.std(points[:, 0], ddof=1)),
        "std_y": float(np.std(points[:, 1], ddof=1)),
        "cep50": float(np.percentile(miss, 50)),
        "cep95": float(np.percentile(miss, 95)),
        "rms": float(np.sqrt(np.mean(miss ** 2))),
        "fraction_within_10m": float(np.mean(miss <= 10.0))
    }


def confidence_ellipse(points, probability=0.95):
    """Return the Gaussian confidence ellipse of the landing points.

    Returns:
        (center, semi_major, semi_minor, angle_deg), angle of the major axis
        measured counter-clockwise from East.
    """
    if probability <= 0 or probability >= 1:
        raise ValueError("Probability must be between 0 and 1")

    points = np.asarray(points, dtype=float)

    if points.ndim != 2 or points.shape[0] < 3 or points.shape[1] < 2:
        raise ValueError("Points must be an array with at least 3 rows of (x, y)")

    xy = points[:, 0:2]

    center = (float(np.mean(xy[:, 0])), float(np.mean(xy[:, 1])))
    covariance = np.cov(xy, rowvar=False)

    eigenvalues, eigenvectors = np.linalg.eigh(covariance)

    # Chi-square quantile with 2 degrees of freedom.
    scale = math.sqrt(-2.0 * math.log(1.0 - probability))

    semi_major = scale * math.sqrt(max(eigenvalues[1], 0.0))
    semi_minor = scale * math.sqrt(max(eigenvalues[0], 0.0))

    major = eigenvectors[:, 1]
    angle = math.degrees(math.atan2(major[1], major[0])) % 180.0

    return center, semi_major, semi_minor, angle


def sensitivity_ranking(nominal, sigmas, step_size=0.02, wind_profile=None):
    """Rank parameters by one-at-a-time +/- 1 sigma landing shift.

    Returns:
        list of (name, shift_m) sorted from largest to smallest shift.
    """
    check_parameters(nominal, sigmas)

    x0, y0, _ = run_landing(nominal, step_size, wind_profile)

    ranking = []

    for name, sigma in sigmas.items():
        if sigma == 0:
            continue

        shifts = []

        for sign in (1.0, -1.0):
            params = dict(nominal)
            params[name] = nominal[name] + sign * sigma

            x, y, _ = run_landing(params, step_size, wind_profile)
            shifts.append(math.hypot(x - x0, y - y0))

        ranking.append((name, 0.5 * (shifts[0] + shifts[1])))

    ranking.sort(key=lambda item: item[1], reverse=True)

    return ranking


def correlation_ranking(samples, points, target):
    """Rank varied parameters by |Pearson correlation| with the radial miss.

    Returns:
        list of (name, abs_correlation) sorted from largest to smallest.
    """
    if len(samples) != len(points):
        raise ValueError("Samples and points must have the same length")

    miss = radial_miss(points, target)

    ranking = []

    for name in PARAMETER_NAMES:
        values = np.array([params[name] for params in samples])

        if np.max(values) == np.min(values):
            continue

        correlation = np.corrcoef(values, miss)[0, 1]
        ranking.append((name, float(abs(correlation))))

    ranking.sort(key=lambda item: item[1], reverse=True)

    return ranking
