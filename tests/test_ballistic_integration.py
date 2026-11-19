
import pytest

from src.physics.gravity import G
from src.physics.ballistic_model import state_derivative
from src.physics.simulation import (
    simulate,
    landing_point,
    flight_time
)


INITIAL_STATE = (0.0, 0.0, 100.0, 10.0, 0.0, 0.0)

MASS = 1.0
DENSITY = 1.225
DRAG_COEFFICIENT = 0.8
AREA = 0.02
WIND = (2.0, 1.0, 0.0)


def make_model(drag_coefficient=DRAG_COEFFICIENT, wind=(0.0, 0.0, 0.0)):
    """Return f(t, state) for the test scenario."""
    def model(t, state):
        return state_derivative(
            t,
            state,
            mass=MASS,
            density=DENSITY,
            drag_coefficient=drag_coefficient,
            area=AREA,
            wind=wind
        )

    return model


def mechanical_energy(state):
    """Return kinetic plus potential energy in joules."""
    speed_squared = sum(value ** 2 for value in state[3:6])

    return 0.5 * MASS * speed_squared + MASS * G * state[2]


def test_drag_free_landing_matches_analytical():
    times, states = simulate(make_model(drag_coefficient=0.0), INITIAL_STATE)

    t = (2 * 100 / G) ** 0.5
    x, y = landing_point(states)

    assert flight_time(times) == pytest.approx(t, rel=1e-6)
    assert x == pytest.approx(10 * t, rel=1e-6)
    assert y == pytest.approx(0)


def test_drag_shortens_landing_distance():
    _, free_states = simulate(make_model(drag_coefficient=0.0), INITIAL_STATE)
    _, drag_states = simulate(make_model(), INITIAL_STATE)

    assert landing_point(drag_states)[0] < landing_point(free_states)[0]


def test_drag_increases_flight_time():
    free_times, _ = simulate(make_model(drag_coefficient=0.0), INITIAL_STATE)
    drag_times, _ = simulate(make_model(), INITIAL_STATE)

    assert flight_time(drag_times) > flight_time(free_times)


def test_tailwind_increases_landing_distance():
    _, calm_states = simulate(make_model(), INITIAL_STATE)
    _, wind_states = simulate(make_model(wind=WIND), INITIAL_STATE)

    calm_x, calm_y = landing_point(calm_states)
    wind_x, wind_y = landing_point(wind_states)

    assert wind_x > calm_x
    assert wind_y > calm_y


def test_energy_never_increases_without_wind():
    _, states = simulate(make_model(), INITIAL_STATE)

    energies = [mechanical_energy(state) for state in states]

    for i in range(1, len(energies)):
        assert energies[i] <= energies[i - 1] + 1e-9


def test_energy_conserved_without_drag():
    _, states = simulate(make_model(drag_coefficient=0.0), INITIAL_STATE)

    # The last state is linearly interpolated to the ground, so allow a small error.
    assert mechanical_energy(states[-1]) == pytest.approx(
        mechanical_energy(states[0]),
        rel=1e-5
    )
