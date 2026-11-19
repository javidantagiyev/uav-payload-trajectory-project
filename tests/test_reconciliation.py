"""Cross-check original APIs against the shared experiment interfaces."""

import numpy as np
import pytest

from src.physics import Atmosphere, Body, analytic_vacuum, integrate, model_rhs
from src.physics.ballistic_model import state_derivative
from src.physics.gravity import gravity_position, gravity_velocity
from src.physics.integrators import euler_step, rk4_step


def test_scenario_adapter_matches_existing_ballistic_derivative():
    body = Body(0.5, 0.015, 0.47)
    atmosphere = Atmosphere(1.15, (1.0, -2.0, 0.1), 9.7)
    state = (0, 0, 5, 3, -1, 0.5)
    expected = state_derivative(0, state, mass=body.mass_kg,
                                density=atmosphere.density_kg_m3,
                                drag_coefficient=body.drag_coefficient,
                                area=body.reference_area_m2,
                                wind=atmosphere.wind_m_s,
                                gravity_m_s2=atmosphere.gravity_m_s2)
    np.testing.assert_allclose(model_rhs(0, state, body, atmosphere), expected)


@pytest.mark.parametrize("method,stepper", [("euler", euler_step), ("rk4", rk4_step)])
def test_trajectory_runner_delegates_to_original_stepper(method, stepper):
    state = (0., 0., 5., 1., 0., 0.)
    body = Body(0.5, 0.01, 0.3)
    atm = Atmosphere()
    rhs = lambda t, y: model_rhs(t, y, body, atm)
    expected = stepper(rhs, 0, state, 0.1)
    actual = integrate(rhs, state, 0.1, 0.1, method=method)
    np.testing.assert_allclose(actual.states[-1], expected)


def test_analytical_series_reuses_original_gravity_equations():
    p = (2., -1., 10.)
    v = (1., 2., 0.5)
    gravity = 9.7
    time = 0.4
    exact = analytic_vacuum(p, v, [0., time], gravity)
    expected = (*gravity_position(p, v, time, g=gravity),
                *gravity_velocity(v, time, g=gravity))
    np.testing.assert_allclose(exact.states[-1], expected)
