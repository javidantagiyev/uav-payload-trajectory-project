
import math

from src.physics.integrators import (
    euler_step,
    rk4_step
)


# Differential equation: dy/dt = y
def model(t, state):
    return (state[0],)


# Initial conditions
initial_state = (1.0,)
initial_time = 0.0
step_size = 0.1


# Calculate using Euler
euler_result = euler_step(
    model,
    initial_time,
    initial_state,
    step_size
)


# Calculate using RK4
rk4_result = rk4_step(
    model,
    initial_time,
    initial_state,
    step_size
)


# Calculate the exact analytical solution
exact_result = math.exp(step_size)


# Display results
print("Euler result:", euler_result[0])
print("RK4 result:", rk4_result[0])
print("Exact result:", exact_result)

print("\nErrors:")

print(
    "Euler error:",
    abs(euler_result[0] - exact_result)
)

print(
    "RK4 error:",
    abs(rk4_result[0] - exact_result)
)
