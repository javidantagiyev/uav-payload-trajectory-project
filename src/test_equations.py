
from equations import (
    gravity_position,
    gravity_velocity,
    air_velocity,
    drag_force,
    drag_magnitude,
    magnitude,
    state_derivative,
    euler_step,
    rk4_step,
    position_error,
    rmse
)


def close_vectors(actual, expected):
    for i in range(len(actual)):
        assert abs(actual[i] - expected[i]) < 0.000001


# TEST 1: Gravity

close_vectors(
    gravity_position((0, 0, 50), (4, 2, 0), 2),
    (8, 4, 30.38)
)

close_vectors(
    gravity_velocity((4, 2, 0), 2),
    (4, 2, -19.62)
)

print("PASS: gravity")


# TEST 2: Wind-relative velocity

close_vectors(
    air_velocity((4, 2, -1), (1, -3, 0)),
    (3, 5, -1)
)

print("PASS: air-relative velocity")


# TEST 3: Aerodynamic drag

force = drag_force(
    (3, 4, 0),
    1.2,
    1.0,
    0.5
)

close_vectors(force, (-4.5, -6, 0))

assert abs(
    magnitude(force) -
    drag_magnitude((3, 4, 0), 1.2, 1.0, 0.5)
) < 0.000001

print("PASS: drag")


# TEST 4: State derivative (gravity only)

state = (0, 0, 50, 4, 2, 0)

close_vectors(
    state_derivative(0, state),
    (4, 2, 0, 0, 0, -9.81)
)

print("PASS: state derivative")


# TEST 5: Euler and RK4

def f(t, state):
    return state_derivative(t, state)


euler_state = state
rk4_state = state

for i in range(20):
    t = i * 0.1

    euler_state = euler_step(
        f, t, euler_state, 0.1
    )

    rk4_state = rk4_step(
        f, t, rk4_state, 0.1
    )


expected = gravity_position(
    (0, 0, 50),
    (4, 2, 0),
    2
)

assert position_error(
    rk4_state[:3], expected
) < 0.000001

assert position_error(
    euler_state[:3], expected
) > 0.01

print("PASS: Euler and RK4")


# TEST 6: Error metrics

assert position_error(
    (3, 4, 0),
    (0, 0, 0)
) == 5

assert abs(
    rmse([3, 4]) ** 2 - 12.5
) < 0.000001

print("PASS: error metrics")


print("\nAll tests passed!")
