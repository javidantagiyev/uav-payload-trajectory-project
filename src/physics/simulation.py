
"""Trajectory simulation from release until ground impact."""

from src.physics.integrators import (
    euler_step,
    rk4_step
)

INTEGRATORS = {
    "euler": euler_step,
    "rk4": rk4_step
}


def simulate(
    f,
    initial_state,
    step_size=0.01,
    method="rk4",
    ground_level=0.0,
    max_time=300.0
):
    """Integrate payload motion until it reaches the ground.

    f(t, state) must return the state derivative.
    The final state is linearly interpolated to ground level.

    Returns:
        (times, states)
    """
    if method not in INTEGRATORS:
        raise ValueError("Method must be 'euler' or 'rk4'")

    if step_size <= 0:
        raise ValueError("Step size must be positive")

    if initial_state[2] < ground_level:
        raise ValueError("Initial altitude is below ground level")

    step = INTEGRATORS[method]

    t = 0.0
    state = tuple(initial_state)

    times = [t]
    states = [state]

    while state[2] > ground_level:
        if t >= max_time:
            raise RuntimeError("Payload did not land within max_time")

        new_state = step(f, t, state, step_size)
        new_t = t + step_size

        # Interpolate between the last two states to find impact.
        if new_state[2] <= ground_level:
            fraction = (state[2] - ground_level) / (state[2] - new_state[2])

            new_state = tuple(
                state[i] + fraction * (new_state[i] - state[i])
                for i in range(len(state))
            )

            new_t = t + fraction * step_size

        t = new_t
        state = new_state

        times.append(t)
        states.append(state)

    return times, states


def landing_point(states):
    """Return the horizontal landing position (x, y) in meters."""
    return states[-1][0], states[-1][1]


def flight_time(times):
    """Return the total flight time in seconds."""
    return times[-1]
