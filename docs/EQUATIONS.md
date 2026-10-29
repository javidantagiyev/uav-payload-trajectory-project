# Mathematical Equations

**Project:** Wind-Compensated Ballistic Release System for Precision Payload Delivery from a UAV  
**Scope:** Initial physics model and numerical foundations. Equations will be extended and validated as development progresses.

## 1. Coordinates and state

We use a local **East–North–Up (ENU)** frame, with positions in metres, velocities in m/s, and time in seconds. Positive $z$ points upward.

$$
\mathbf{p}=\begin{bmatrix}x\\y\\z\end{bmatrix},\qquad
\mathbf{v}=\begin{bmatrix}v_x\\v_y\\v_z\end{bmatrix}
$$

The six-dimensional translational state is

$$
\mathbf{s}=\begin{bmatrix}x&y&z&v_x&v_y&v_z\end{bmatrix}^{\mathsf T}.
$$

> **Coordinate note:** Mathisen et al. (2017) formulate their ballistic state in **North–East–Down (NED)** coordinates. Equations below use ENU, so axes and gravitational signs differ from the paper.

## 2. Gravity-only baseline

Newton's second law gives

$$
\mathbf F=m\mathbf a,\qquad
\mathbf a_g=\begin{bmatrix}0\\0\\-g\end{bmatrix},
\qquad g\approx9.81\ \mathrm{m/s^2}.
$$

For constant acceleration, the analytical solution is

$$
\mathbf p(t)=\mathbf p_0+\mathbf v_0t+\tfrac12\mathbf a_gt^2,
$$

$$
\mathbf v(t)=\mathbf v_0+\mathbf a_gt.
$$

These equations provide a reference solution for testing numerical integration when drag and wind are disabled.

## 3. Aerodynamic drag

For a point mass with an approximately constant drag coefficient, use the standard **quadratic drag** model:

$$
\mathbf F_D=-\frac12\rho C_D A\,\|\mathbf v_a\|\,\mathbf v_a.
$$

Here $\rho$ is air density (kg/m³), $C_D$ is the dimensionless drag coefficient, $A$ is reference projected area (m²), and $\mathbf v_a$ is the velocity **relative to the air** (m/s).

Its magnitude is

$$
F_D=\frac12\rho C_D A\,\|\mathbf v_a\|^2.
$$

**Source:** Mathisen et al. (2017), Section 2, drag-force expression and Equations (1)–(2). Equation (5) is written in vector form with the sign convention made explicit.

## 4. Wind and air-relative velocity

Let $\mathbf w$ denote wind velocity in the same ENU frame. Then

$$
\mathbf v_a=\mathbf v-\mathbf w.
$$

Initially, $\mathbf w$ can be treated as a constant vector. More complex wind fields require additional assumptions and validation.

## 5. Combined point-mass dynamics

Under gravity and quadratic drag, the translational differential equations are

$$
\frac{d\mathbf p}{dt}=\mathbf v,
$$

$$
\frac{d\mathbf v}{dt}=
\begin{bmatrix}0\\0\\-g\end{bmatrix}
-\frac{\rho C_D A}{2m}\|\mathbf v-\mathbf w\|(\mathbf v-\mathbf w).
$$

Thus $\dot{\mathbf s}=f(t,\mathbf s)$, using the state defined in Equation (1).

**Source and adaptation:** Mathisen et al. (2017), Section 2, Equations (1)–(3), describe gravity-plus-drag ballistic dynamics and a six-component state. The presentation above is an **ENU vector reformulation**, not a verbatim transcription of their NED equations.

## 6. Numerical integration

For a state derivative $\dot{\mathbf s}=f(t,\mathbf s)$ and time increment $h$:

**Forward Euler**

$$
\mathbf s_{n+1}=\mathbf s_n+h\,f(t_n,\mathbf s_n).
$$

**Fourth-order Runge–Kutta (RK4)**

$$
\begin{aligned}
\mathbf k_1 &= f(t_n,\mathbf s_n),\\
\mathbf k_2 &= f(t_n+h/2,\mathbf s_n+h\mathbf k_1/2),\\
\mathbf k_3 &= f(t_n+h/2,\mathbf s_n+h\mathbf k_2/2),\\
\mathbf k_4 &= f(t_n+h,\mathbf s_n+h\mathbf k_3),\\
\mathbf s_{n+1} &= \mathbf s_n+\frac h6(\mathbf k_1+2\mathbf k_2+2\mathbf k_3+\mathbf k_4).
\end{aligned}
$$

Mathisen et al. (2017, Section 2) explicitly use Euler's method for their ballistic calculation. RK4 is a **proposed numerical alternative for this project**, not a method attributed to that paper.

## 7. Verification quantities

For simulated predictions $\hat{\mathbf p}_i$ and known reference positions $\mathbf p_i$, a basic three-dimensional position error is

$$
e_i=\|\hat{\mathbf p}_i-\mathbf p_i\|.
$$

Across $N$ comparisons, the root-mean-square position error is

$$
\mathrm{RMSE}=\sqrt{\frac1N\sum_{i=1}^{N}e_i^2}.
$$

These are **general evaluation definitions**, not equations reproduced from Mathisen et al. (2017). Validation will distinguish numerical error from model error and uncertainty in simulated observations.

---

## Modeling assumptions (initial)

- Payload represented by a **point mass** with three translational degrees of freedom.
- Gravity is constant and acts downward in ENU.
- First drag model assumes fixed $m$, $C_D$, $A$, and $\rho$.
- Rotational dynamics, changing orientation, and wind variation with height are deferred.
- Analytical gravity-only motion serves as the first verification baseline.
