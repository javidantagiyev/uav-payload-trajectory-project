
from src.physics.ballistic_model import state_derivative
from src.physics.integrators import rk4_step
from src.physics.wind_model import constant_wind


# Initial payload state
initial_state = (
    0.0,    # East position
    0.0,    # North position
    100.0,  # Altitude
    10.0,   # East velocity
    0.0,    # North velocity
    0.0     # Vertical velocity
)


# Physical parameters
mass = 1.0
density = 1.225
drag_coefficient = 0.8
area = 0.02

wind = constant_wind(
    east=2.0,
    north=1.0,
    up=0.0
)


# Define our ballistic model
def model(t, state):
    return state_derivative(
        t,
        state,
        mass=mass,
        density=density,
        drag_coefficient=drag_coefficient,
        area=area,
        wind=wind
    )


# Simulation parameters
time = 0.0
dt = 0.01

state = initial_state


# Perform 100 integration steps
for step in range(100):

    state = rk4_step(
        model,
        time,
        state,
        dt
    )

    time += dt


# Extract final position and velocity
position = state[:3]
velocity = state[3:6]


print("Simulation time:", time)
print("Final position:", position)
print("Final velocity:", velocity)
