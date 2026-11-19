"""check shared model conventions without changing either implementation."""

import numpy as np
import pytest

from src.physics.ballistic_model import model_rhs, state_derivative
from src.physics.parameters import Atmosphere, Body
from src.physics.atmosphere import density_function, isa_density
from src.physics.wind_model import wind_from_direction
from src.physics.multicopter_telemetry import ned_to_enu


@pytest.mark.parametrize("seed", [0, 3, 21])
def test_parameter_objects_delegate_to_existing_model(seed):
    rng = np.random.default_rng(seed)
    for _ in range(20):
        state = np.r_[rng.normal(size=2), rng.uniform(1, 20), rng.normal(size=3)]
        body = Body(float(rng.uniform(0.3, 3)), float(rng.uniform(0, .04)),
                    float(rng.uniform(0, 1)))
        atmosphere = Atmosphere(float(rng.uniform(0.9, 1.3)),
                                tuple(rng.normal(size=3)), 9.81)
        original = state_derivative(0, state, mass=body.mass_kg,
                                    density=atmosphere.density_kg_m3,
                                    drag_coefficient=body.drag_coefficient,
                                    area=body.reference_area_m2,
                                    wind=atmosphere.wind_m_s,
                                    gravity_m_s2=atmosphere.gravity_m_s2)
        np.testing.assert_allclose(model_rhs(0, state, body, atmosphere), original,
                                   rtol=1e-13, atol=1e-13)


def test_meteorological_wind_direction_and_world_frames():
    assert wind_from_direction(10, 0) == pytest.approx((0, -10, 0), abs=1e-12)
    assert wind_from_direction(10, 90) == pytest.approx((-10, 0, 0), abs=1e-12)
    assert ned_to_enu(2, 3, -4) == (3, 2, 4)


def test_isothermal_baseline_not_confused_with_altitude_varying_isa():
    density = density_function(0)
    assert density(0) == pytest.approx(isa_density(0))
    assert density(1000) < density(0)
    assert Atmosphere().density_kg_m3 != pytest.approx(density(1000), abs=0.01)
