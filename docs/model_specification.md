# Model Specification and Scope

## Research context

The submitted SDP research report organizes the study around physical-model fidelity, uncertainty, comparative performance under equivalent input information, and evaluation of feasible initial conditions (Section 1.2). The present implementation addresses the numerical foundations of the first and third questions; it is not a complete implementation of all research questions.

## Assumptions and units

The state is $\mathbf{s}=[x,y,z,v_x,v_y,v_z]^{\mathsf T}$. The coordinate frame is **local Cartesian**, with $z$ positive upward. Positions are measured in metres, velocities in metres per second, time in seconds. All vectors, including the atmospheric velocity, use the same frame. There is no global geographic frame or terrain transformation.

The simplified point-mass equation is

$$
\frac{d\mathbf p}{dt}=\mathbf v,
$$

$$
\frac{d\mathbf v}{dt}=
\begin{bmatrix}0\\0\\-g\end{bmatrix}
-\frac{\rho C_D A}{2m}\lVert\mathbf v-\mathbf w\rVert(\mathbf v-\mathbf w).
$$

The assumptions are: constant gravitational acceleration, constant density, constant aerodynamic coefficient, fixed reference area, constant atmospheric velocity, and no rotational dynamics. The scenario parameters are explicit in `configs/baseline.json` and are illustrative rather than measurements.

For $C_D=0$ (or zero air density or reference area), the analytical gravity-only reference is

$$
\mathbf p(t)=\mathbf p_0+\mathbf v_0 t+\frac12\begin{bmatrix}0\\0\\-g\end{bmatrix}t^2,
$$

$$
\mathbf v(t)=\mathbf v_0+\begin{bmatrix}0\\0\\-g\end{bmatrix}t.
$$

## Excluded effects

The implementation does not model orientation-dependent aerodynamics, lift, rotational motion, changing atmospheric fields, turbulence, separation transients, geometry changes, ground contact, uncertainty propagation, vehicle dynamics, sensor fusion, or physical release hardware. The numerical experiment stops at a fixed time; it does not detect events or determine impact/release points.

## Validity of conclusions

The current simulations demonstrate mathematical and numerical consistency under **specified assumptions**. They do not establish the accuracy of an actual payload model. The project's longer-term nominal operating conditions and accuracy objective are not evaluated in these illustrative scenarios.
