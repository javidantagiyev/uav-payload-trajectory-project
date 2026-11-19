import sys
from pathlib import Path as _Path
sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))

import numpy as np
import pytest

from src.physics import Atmosphere, Body, analytic_vacuum, model_rhs, integrate, mechanical_energy


INITIAL = np.array([0., 0., 12., 1.5, 0.5, 0.])
ATMOSPHERE = Atmosphere()


def test_rk4_gravity_matches_analytic_reference():
    body = Body(0.4, 0.02, 0.)
    rhs = lambda t, y: model_rhs(t, y, body, ATMOSPHERE)
    trajectory = integrate(rhs, INITIAL, 1.0, 0.1)
    exact = analytic_vacuum(INITIAL[:3], INITIAL[3:], trajectory.times)
    np.testing.assert_allclose(trajectory.states, exact.states, rtol=0, atol=1e-12)


def test_euler_has_measurable_position_error_for_gravity():
    body = Body(0.4, 0.02, 0.)
    rhs = lambda t, y: model_rhs(t, y, body, ATMOSPHERE)
    trajectory = integrate(rhs, INITIAL, 1., 0.1, method="euler")
    exact = analytic_vacuum(INITIAL[:3], INITIAL[3:], trajectory.times)
    assert abs(trajectory.positions[-1, 2] - exact.positions[-1, 2]) > 0.1


def test_quadratic_drag_reduces_energy_for_still_air():
    body = Body(0.4, 0.02, 0.47)
    rhs = lambda t, y: model_rhs(t, y, body, ATMOSPHERE)
    trajectory = integrate(rhs, INITIAL, 1., 0.01)
    energies = np.array([mechanical_energy(state, body, ATMOSPHERE) for state in trajectory.states])
    assert np.max(np.diff(energies)) <= 1e-8
    assert energies[-1] < energies[0]


def test_refining_rk4_decreases_quadratic_drag_error():
    body = Body(0.4, 0.02, 0.47)
    rhs = lambda t, y: model_rhs(t, y, body, ATMOSPHERE)
    fine = integrate(rhs, INITIAL, 1., 0.0005)
    coarse = integrate(rhs, INITIAL, 1., 0.1)
    medium = integrate(rhs, INITIAL, 1., 0.05)
    coarse_difference = np.linalg.norm(coarse.states[-1] - fine.states[-1])
    medium_difference = np.linalg.norm(medium.states[-1] - fine.states[-1])
    assert medium_difference < coarse_difference


def test_integrator_rejects_invalid_inputs():
    with pytest.raises(ValueError):
        integrate(lambda t, y: y, [0]*6, 1, 0)
    with pytest.raises(ValueError):
        integrate(lambda t, y: y, [0]*6, 1, 0.1, method="not_a_method")
    with pytest.raises(ValueError):
        integrate(lambda t, y: y, [0]*5, 1, 0.1)
