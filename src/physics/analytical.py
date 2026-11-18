from math import sqrt, isfinite
from src.physics.gravity import G


def gravity_impact_time(height, vertical_velocity = 0.0):
    if not isfinite(height) or not isfinite(vertical_velocity) or height < 0:
        raise ValueError("Invalid initial conditions")

    if height == 0 and vertical_velocity <= 0:
        return 0.0

    return (vertical_velocity + sqrt(vertical_velocity ** 2 + 2 * G * height)) / G
