
"""International Standard Atmosphere for the troposphere (SI units)."""

T0 = 288.15
P0 = 101325.0
LAPSE_RATE = 0.0065
R_SPECIFIC = 287.05
G0 = 9.80665

MIN_ALTITUDE = -500.0
MAX_ALTITUDE = 11000.0


def check_altitude(altitude):
    """Raise ValueError if the altitude is outside the troposphere model."""
    if altitude < MIN_ALTITUDE or altitude > MAX_ALTITUDE:
        raise ValueError("Altitude must be between -500 m and 11000 m")


def temperature(altitude):
    """Return ISA air temperature in kelvin at an altitude above sea level."""
    check_altitude(altitude)

    return T0 - LAPSE_RATE * altitude


def pressure(altitude):
    """Return ISA air pressure in pascals at an altitude above sea level."""
    exponent = G0 / (R_SPECIFIC * LAPSE_RATE)

    return P0 * (temperature(altitude) / T0) ** exponent


def isa_density(altitude):
    """Return ISA air density in kg/m^3 at an altitude above sea level."""
    return pressure(altitude) / (R_SPECIFIC * temperature(altitude))


def density_function(ground_altitude=0.0):
    """Return density(z) for state_derivative.

    z is height above ground in meters.
    ground_altitude is the ground elevation above sea level (Baku is about -28 m).
    """
    check_altitude(ground_altitude)

    def density(z):
        return isa_density(ground_altitude + z)

    return density
