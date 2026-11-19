
from math import pi, sqrt

import pytest

from src.physics.gravity import G
from src.physics.payload import (
    sphere,
    box,
    PRESETS,
    ballistic_coefficient,
    terminal_velocity
)


def test_sphere_parameters():
    payload = sphere(1.0, 0.2)

    assert payload["shape"] == "sphere"
    assert payload["mass"] == 1.0
    assert payload["area"] == pytest.approx(pi * 0.01)
    assert payload["drag_coefficient"] == 0.47


def test_box_uses_bottom_face():
    payload = box(2.0, 0.3, 0.2, 0.5)

    assert payload["shape"] == "box"
    assert payload["area"] == pytest.approx(0.06)
    assert payload["drag_coefficient"] == 1.05


def test_presets():
    assert PRESETS["sphere_1kg"]["area"] == pytest.approx(pi * 0.15 ** 2 / 4)
    assert PRESETS["box_1kg"]["area"] == pytest.approx(0.03)


def test_ballistic_coefficient():
    payload = box(1.5, 0.1, 0.1, 0.1, drag_coefficient=1.0)

    assert ballistic_coefficient(payload) == pytest.approx(150)


def test_terminal_velocity():
    payload = box(1.0, 0.1, 0.2, 0.1, drag_coefficient=1.0)

    expected = sqrt(2 * 1.0 * G / (1.225 * 1.0 * 0.02))

    assert terminal_velocity(payload) == pytest.approx(expected)


def test_terminal_velocity_higher_in_thin_air():
    payload = PRESETS["sphere_1kg"]

    assert terminal_velocity(payload, density=1.0) > terminal_velocity(payload)


def test_invalid_sphere_mass():
    with pytest.raises(ValueError):
        sphere(0, 0.1)


def test_invalid_sphere_diameter():
    with pytest.raises(ValueError):
        sphere(1.0, -0.1)


def test_invalid_sphere_drag_coefficient():
    with pytest.raises(ValueError):
        sphere(1.0, 0.1, drag_coefficient=0)


def test_invalid_box_mass():
    with pytest.raises(ValueError):
        box(-1.0, 0.1, 0.1, 0.1)


def test_invalid_box_dimensions():
    with pytest.raises(ValueError):
        box(1.0, 0.1, 0, 0.1)


def test_invalid_box_drag_coefficient():
    with pytest.raises(ValueError):
        box(1.0, 0.1, 0.1, 0.1, drag_coefficient=-1)


def test_invalid_density():
    with pytest.raises(ValueError):
        terminal_velocity(PRESETS["box_1kg"], density=0)
