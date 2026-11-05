
"""Evaluation metrics for the ballistic simulation."""

from math import sqrt


def position_error(predicted, actual):
    """Calculate 3D Euclidean position error in meters."""
    if len(predicted) != 3 or len(actual) != 3:
        raise ValueError("Positions must contain exactly 3 values")

    difference = tuple(
        predicted[i] - actual[i]
        for i in range(3)
    )

    return sqrt(sum(value ** 2 for value in difference))


def rmse(errors):
    """Calculate root mean square error."""
    if len(errors) == 0:
        raise ValueError("At least one error is required")

    return sqrt(
        sum(error ** 2 for error in errors) / len(errors)
    )
