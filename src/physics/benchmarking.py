"""Numerical verification and measured cost for the shared six-state ODE solvers.

Metrics compare solutions of a chosen mathematical model. They are not physical
validation, experimental trajectory accuracy, or release-point calculations.
"""

from statistics import median
from time import perf_counter

import numpy as np

from .trajectory import integrate


DERIVATIVE_CALLS_PER_STEP = {"euler": 1, "rk4": 4}


def terminal_state_difference(trajectory, reference_state):
    """Euclidean terminal position/velocity differences against a supplied reference.

    The reference must come from independently specified calculation or a finer
    simulation. The function makes no claim that the reference is ground truth.
    """
    ref = np.asarray(reference_state, dtype=float)
    actual = np.asarray(trajectory.states[-1], dtype=float)
    if ref.shape != (6,) or actual.shape != (6,):
        raise ValueError("reference and terminal state must have six components")
    if not np.all(np.isfinite(ref)) or not np.all(np.isfinite(actual)):
        raise ValueError("reference and terminal state must be finite")
    return (float(np.linalg.norm(actual[:3] - ref[:3])),
            float(np.linalg.norm(actual[3:] - ref[3:])))


def observed_convergence_order(step_sizes_s, errors, numerical_floor=1e-11):
    """Fit log(error) to log(step); return None if roundoff dominates.

    Requires at least three distinct, finite, positive points above the specified
    conservative numerical floor. A fitted slope is not a validation metric.
    """
    step = np.asarray(step_sizes_s, dtype=float)
    error = np.asarray(errors, dtype=float)
    if step.ndim != 1 or error.shape != step.shape or len(step) < 3:
        raise ValueError("at least three paired step sizes and errors are required")
    if not np.all(np.isfinite(step)) or np.any(step <= 0):
        raise ValueError("step sizes must be finite and positive")
    if not np.all(np.isfinite(error)) or np.any(error < 0):
        raise ValueError("errors must be finite and nonnegative")
    if not np.isfinite(numerical_floor) or numerical_floor <= 0:
        raise ValueError("numerical_floor must be finite and positive")
    reliable = error > numerical_floor
    if np.count_nonzero(reliable) < 3:
        return None
    x = np.log(step[reliable])
    if len(np.unique(x)) < 3:
        return None
    return float(np.polyfit(x, np.log(error[reliable]), deg=1)[0])


def measured_integration(rhs, initial_state, duration_s, maximum_step_s,
                         method, repetitions):
    """Warm up once, then measure complete Python trajectory integration.

    Timings include allocation and trajectory storage. They are machine dependent.
    Derivative call counts are determined from the canonical fixed-step routines.
    """
    if isinstance(repetitions, bool) or not isinstance(repetitions, int) or not 1 <= repetitions <= 100:
        raise ValueError("repetitions must be an integer from 1 to 100")
    if method not in DERIVATIVE_CALLS_PER_STEP:
        raise ValueError("unknown numerical integration method")
    integrate(rhs, initial_state, duration_s, maximum_step_s, method=method)
    times_ms = []
    result = None
    for _ in range(repetitions):
        start = perf_counter()
        result = integrate(rhs, initial_state, duration_s, maximum_step_s, method=method)
        times_ms.append(1000.0 * (perf_counter() - start))
    steps = len(result.times) - 1
    derivative_evaluations = steps * DERIVATIVE_CALLS_PER_STEP[method]
    actual_step_s = float(result.times[1] - result.times[0])
    return result, float(median(times_ms)), derivative_evaluations, actual_step_s
