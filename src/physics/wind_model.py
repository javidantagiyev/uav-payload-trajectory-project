
"""Wind model in East-North-Up coordinates (SI units)."""

import math

import numpy as np

MINIMUM_PROFILE_HEIGHT = 0.1


def constant_wind(east=0.0, north=0.0, up=0.0):
    """Return a constant wind velocity vector in m/s."""
    return (east, north, up)


def wind_magnitude(wind):
    """Calculate wind speed in m/s."""
    return sum(value ** 2 for value in wind) ** 0.5


def wind_from_direction(speed, direction):
    """Return the ENU wind vector for a meteorological wind report.

    direction is where the wind blows FROM, in degrees clockwise from North.
    """
    if speed < 0:
        raise ValueError("Wind speed cannot be negative")

    angle = math.radians(direction)

    return (
        -speed * math.sin(angle),
        -speed * math.cos(angle),
        0.0
    )


def wind_direction(wind):
    """Return the meteorological direction (deg, [0, 360)) the wind blows FROM."""
    direction = math.degrees(math.atan2(-wind[0], -wind[1])) % 360.0

    # Avoid returning 360.0 because of floating point rounding.
    if direction >= 360.0:
        direction = 0.0

    return direction


def headwind_crosswind(wind, heading):
    """Split the horizontal wind into along-track and cross-track parts.

    heading is the UAV track in degrees clockwise from North.

    Returns:
        (along, cross) in m/s. along > 0 is a tailwind,
        cross > 0 pushes to the right of the track.
    """
    angle = math.radians(heading)

    along = wind[0] * math.sin(angle) + wind[1] * math.cos(angle)
    cross = wind[0] * math.cos(angle) - wind[1] * math.sin(angle)

    return along, cross


def power_law_wind(reference_wind, reference_height=10.0, exponent=1 / 7):
    """Return wind(t, position) following the power law w(z) = w_ref (z / z_ref)^alpha."""
    if reference_height <= 0:
        raise ValueError("Reference height must be positive")

    if exponent < 0:
        raise ValueError("Power law exponent cannot be negative")

    def wind(t, position):
        z = max(position[2], MINIMUM_PROFILE_HEIGHT)
        factor = (z / reference_height) ** exponent

        return tuple(reference_wind[i] * factor for i in range(3))

    return wind


def log_law_wind(reference_wind, reference_height=10.0, roughness_length=0.03):
    """Return wind(t, position) following the logarithmic boundary layer profile.

    w(z) = w_ref ln(z / z0) / ln(z_ref / z0), zero for z <= z0.
    """
    if roughness_length <= 0:
        raise ValueError("Roughness length must be positive")

    if reference_height <= roughness_length:
        raise ValueError("Reference height must be above the roughness length")

    reference_log = math.log(reference_height / roughness_length)

    def wind(t, position):
        z = position[2]

        if z <= roughness_length:
            return (0.0, 0.0, 0.0)

        factor = math.log(z / roughness_length) / reference_log

        return tuple(reference_wind[i] * factor for i in range(3))

    return wind


def layered_wind(heights, winds):
    """Return wind(t, position) interpolated linearly between altitude layers.

    heights must be strictly increasing (m); winds is a list of (east, north, up).
    Outside the given range the nearest layer is used.
    """
    if len(heights) == 0:
        raise ValueError("At least one wind layer is required")

    if len(heights) != len(winds):
        raise ValueError("Heights and winds must have the same length")

    for i in range(1, len(heights)):
        if heights[i] <= heights[i - 1]:
            raise ValueError("Heights must be strictly increasing")

    def wind(t, position):
        z = position[2]

        if z <= heights[0]:
            return tuple(winds[0])

        if z >= heights[-1]:
            return tuple(winds[-1])

        for i in range(1, len(heights)):
            if z <= heights[i]:
                fraction = (z - heights[i - 1]) / (heights[i] - heights[i - 1])

                return tuple(
                    winds[i - 1][j] + fraction * (winds[i][j] - winds[i - 1][j])
                    for j in range(3)
                )

    return wind


def base_wind_value(base_wind, t, position):
    """Evaluate a base wind given as a vector or a function wind(t, position)."""
    if callable(base_wind):
        return base_wind(t, position)

    return tuple(base_wind)


def discrete_gust(base_wind, amplitude, start_time, duration):
    """Return wind(t, position) with a "1-cosine" discrete gust added.

    w = base + A / 2 (1 - cos(2 pi (t - t0) / d)) for t0 <= t <= t0 + d.
    amplitude is (east, north, up) in m/s.
    """
    if duration <= 0:
        raise ValueError("Gust duration must be positive")

    if len(amplitude) != 3:
        raise ValueError("Gust amplitude must contain exactly 3 values")

    def wind(t, position):
        base = base_wind_value(base_wind, t, position)

        if t < start_time or t > start_time + duration:
            return base

        shape = 0.5 * (1.0 - math.cos(2.0 * math.pi * (t - start_time) / duration))

        return tuple(base[i] + amplitude[i] * shape for i in range(3))

    return wind


def turbulence_series(intensity, length_scale, airspeed, duration, step, seed=None):
    """Generate a first-order Gauss-Markov turbulence series per axis.

    u_{k+1} = a u_k + sigma sqrt(1 - a^2) n_k, a = exp(-V dt / L).
    intensity is sigma in m/s, one number or (east, north, up).

    Returns:
        (times, series) as numpy arrays, series has shape (len(times), 3).
    """
    if length_scale <= 0:
        raise ValueError("Turbulence length scale must be positive")

    if airspeed <= 0:
        raise ValueError("Airspeed must be positive")

    if duration <= 0 or step <= 0:
        raise ValueError("Duration and step must be positive")

    if np.ndim(intensity) == 0:
        intensity = (intensity, intensity, intensity)

    if len(intensity) != 3:
        raise ValueError("Turbulence intensity must be a number or 3 values")

    sigma = np.array(intensity, dtype=float)

    if np.any(sigma < 0):
        raise ValueError("Turbulence intensity cannot be negative")

    count = int(math.ceil(duration / step)) + 1
    times = step * np.arange(count)

    a = math.exp(-airspeed * step / length_scale)

    rng = np.random.default_rng(seed)
    noise = rng.standard_normal((count, 3))

    series = np.zeros((count, 3))

    # Start from the stationary distribution so there is no warm-up transient.
    series[0] = sigma * noise[0]

    for k in range(1, count):
        series[k] = a * series[k - 1] + sigma * math.sqrt(1.0 - a ** 2) * noise[k]

    return times, series


def turbulent_wind(base_wind, intensity, length_scale, airspeed, duration,
                   step=0.01, seed=None):
    """Return wind(t, position) = base wind + first-order Dryden-like turbulence.

    base_wind can be a vector or a function wind(t, position).
    """
    times, series = turbulence_series(
        intensity,
        length_scale,
        airspeed,
        duration,
        step,
        seed
    )

    def wind(t, position):
        base = base_wind_value(base_wind, t, position)

        return tuple(
            float(base[i] + np.interp(t, times, series[:, i]))
            for i in range(3)
        )

    return wind
