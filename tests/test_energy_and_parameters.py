import sys
from pathlib import Path as _Path
sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))

import numpy as np
import pytest

from src.physics import Atmosphere, Body, model_rhs, mechanical_energy


def test_gravity_only_acceleration():
    body = Body(0.4, 0.02, 0)
    state = np.array([0, 0, 10, 1, 2, 3], dtype=float)
    derivative = model_rhs(0, state, body, Atmosphere())
    np.testing.assert_allclose(derivative, [1, 2, 3, 0, 0, -9.81], atol=1e-14)


def test_stationary_air_drag_opposes_relative_motion():
    body = Body(0.4, 0.02, 0.47)
    state = np.array([0, 0, 10, 3, -4, 0], dtype=float)
    atmosphere = Atmosphere()
    derivative = model_rhs(0, state, body, atmosphere)
    drag_only = derivative[3:] - [0, 0, -atmosphere.gravity_m_s2]
    assert np.dot(drag_only, state[3:]) < 0


def test_zero_atmospheric_density_means_gravity_only():
    body = Body(0.4, 0.02, 0.47)
    atmosphere = Atmosphere(density_kg_m3=0)
    derivative = model_rhs(0, [1, 2, 10, 3, 4, 5], body, atmosphere)
    np.testing.assert_allclose(derivative[3:], [0, 0, -9.81], atol=1e-14)


def test_gravity_only_energy_at_single_time():
    body = Body(2, 0, 0)
    atmosphere = Atmosphere()
    state = [0, 0, 2, 3, 0, 0]
    assert mechanical_energy(state, body, atmosphere) == pytest.approx(9 + 2 * 9.81 * 2)


@pytest.mark.parametrize("params", [(0, 0.01, 0.5), (-1, 0.01, 0.5), (1, -1, 0.5), (1, 1, -1)])
def test_invalid_body_rejected(params):
    with pytest.raises(ValueError):
        Body(*params)


def test_invalid_wind_rejected():
    with pytest.raises(ValueError):
        Atmosphere(wind_m_s=(0.0, 0.0))
