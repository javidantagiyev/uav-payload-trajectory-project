"""Unit verification of solver-comparison metrics, independent of plotting."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pytest

from src.physics.benchmarking import (
    measured_integration,
    observed_convergence_order,
    terminal_state_difference,
)
from src.physics.trajectory import Trajectory


def test_terminal_position_and_velocity_metrics_are_separate():
    traj = Trajectory(np.array([0.0, 1.0]), np.array([
        [0., 0., 0., 0., 0., 0.],
        [3., 4., 0., 1., 2., 2.],
    ]))
    position, velocity = terminal_state_difference(traj, [0., 0., 0., 0., 0., 0.])
    assert position == 5.0
    assert velocity == 3.0


@pytest.mark.parametrize("reference", [
    [0., 0.],
    [0., 0., 0., 0., 0., float("nan")],
])
def test_invalid_reference_state_rejected(reference):
    traj = Trajectory(np.array([0.]), np.zeros((1, 6)))
    with pytest.raises(ValueError):
        terminal_state_difference(traj, reference)


@pytest.mark.parametrize("order", [1, 4])
def test_observed_convergence_recovers_synthetic_order(order):
    steps = np.array([0.1, 0.05, 0.025, 0.0125])
    errors = 0.5 * steps ** order
    observed = observed_convergence_order(steps, errors, numerical_floor=1e-14)
    assert observed == pytest.approx(order, abs=1e-10)


def test_roundoff_dominated_differences_are_not_fitted():
    assert observed_convergence_order([0.1, 0.05, 0.025, 0.0125],
                                      [2e-15, 3e-15, 4e-15, 2e-15]) is None


def test_negative_errors_are_rejected():
    with pytest.raises(ValueError):
        observed_convergence_order([0.1, 0.05, 0.025], [1, -0.1, 0.01])


@pytest.mark.parametrize("method,calls", [("euler", 10), ("rk4", 40)])
def test_rhs_cost_is_counted_from_canonical_integrator(method, calls):
    # Linear constant-rate ODE; both integrators have exactly the same solution.
    rhs = lambda t, y: np.array([1., 2., 3., 0., 0., 0.])
    final, runtime_ms, nfev, dt = measured_integration(
        rhs, [0., 0., 0., 0., 0., 0.], 1., 0.1, method, 2)
    np.testing.assert_allclose(final.states[-1, :3], [1., 2., 3.], atol=1e-13)
    assert runtime_ms >= 0
    assert nfev == calls
    assert dt == pytest.approx(0.1)


def test_reject_invalid_repeat_count():
    with pytest.raises(ValueError):
        measured_integration(lambda t, y: y, [0.]*6, 1., 0.1, "euler", True)
