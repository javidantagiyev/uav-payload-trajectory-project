
"""Wind model in East-North-Up coordinates (SI units)."""


def constant_wind(east=0.0, north=0.0, up=0.0):
    """Return a constant wind velocity vector in m/s."""
    return (east, north, up)


def wind_magnitude(wind):
    """Calculate wind speed in m/s."""
    return sum(value ** 2 for value in wind) ** 0.5
