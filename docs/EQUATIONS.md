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

---

## 8. ISA atmosphere (troposphere)

Air density changes with altitude. In the troposphere ($-500\ \mathrm m \le h \le 11000\ \mathrm m$ above sea level) the International Standard Atmosphere gives

$$
T(h)=T_0-Lh,
$$

$$
p(h)=p_0\left(\frac{T(h)}{T_0}\right)^{\frac{g_0}{R L}},
$$

$$
\rho(h)=\frac{p(h)}{R\,T(h)},
$$

with $T_0=288.15\ \mathrm K$, $p_0=101325\ \mathrm{Pa}$, $L=0.0065\ \mathrm{K/m}$, $R=287.05\ \mathrm{J/(kg\,K)}$ (specific gas constant of dry air) and $g_0=9.80665\ \mathrm{m/s^2}$. The exponent $g_0/(RL)\approx5.256$ is the same as $g_0M/(R^{*}L)$ written with the universal gas constant $R^{*}$ and molar mass $M$.

The simulation uses height above ground $z$, so the density seen by the payload is

$$
\rho(z)=\rho_{\mathrm{ISA}}(h_g+z),
$$

where $h_g$ is the ground elevation above sea level (Baku: $h_g\approx-28\ \mathrm m$). Reference values: $\rho(0)\approx1.225\ \mathrm{kg/m^3}$, $\rho(1000\ \mathrm m)\approx1.112\ \mathrm{kg/m^3}$.

## 9. Payload parameters, ballistic coefficient and terminal velocity

The drag model needs the frontal (reference) area $A$ and drag coefficient $C_D$:

$$
A_{\mathrm{sphere}}=\frac{\pi d^2}{4},\qquad
A_{\mathrm{box}}=l\,w.
$$

The box is assumed to fall mostly vertically, so its bottom face $l\times w$ is used. Typical values are $C_D\approx0.47$ (sphere) and $C_D\approx1.05$ (box face-on).

The **ballistic coefficient** combines these into one number:

$$
\beta=\frac{m}{C_D A}\quad[\mathrm{kg/m^2}].
$$

A larger $\beta$ means drag slows the payload less. At **terminal velocity** drag balances gravity, $mg=\tfrac12\rho C_D A v_t^2$, so

$$
v_t=\sqrt{\frac{2mg}{\rho C_D A}}=\sqrt{\frac{2g\beta}{\rho}}.
$$

## 10. Release state and attitude rotation

The payload starts from the UAV state, corrected for the mount position, any ejection velocity and the UAV rotation.

**Body frame:** $x_b$ forward, $y_b$ left, $z_b$ up. With zero attitude the body axes coincide with ENU, so the nose points East. Yaw $\psi$ is measured from East, counter-clockwise (towards North). Roll $\phi$, pitch $\theta$ and yaw $\psi$ are applied in Z–Y–X order:

$$
R=R_z(\psi)\,R_y(\theta)\,R_x(\phi),
$$

$$
R_x(\phi)=\begin{bmatrix}1&0&0\0&\cos\phi&-\sin\phi\0&\sin\phi&\cos\phi\end{bmatrix},\quad
R_y(\theta)=\begin{bmatrix}\cos\theta&0&\sin\theta\0&1&0\-\sin\theta&0&\cos\theta\end{bmatrix},\quad
R_z(\psi)=\begin{bmatrix}\cos\psi&-\sin\psi&0\\sin\psi&\cos\psi&0\0&0&1\end{bmatrix}.
$$

$R$ maps a body-frame vector into ENU. With $z_b$ up, a positive pitch lowers the nose and a positive roll lifts the left side.

With mount offset $\mathbf r_b$ and ejection velocity $\mathbf u_b$ (body frame), and UAV angular velocity $\boldsymbol\omega$ (ENU, rad/s), the release state is

$$
\mathbf p_0=\mathbf p_{\mathrm{UAV}}+R\,\mathbf r_b,
$$

$$
\mathbf v_0=\mathbf v_{\mathrm{UAV}}+R\,\mathbf u_b+\boldsymbol\omega\times(R\,\mathbf r_b).
$$

The last term is the lever-arm velocity of the mount point caused by UAV rotation.

## 11. Analytical vertical drop with quadratic drag

For a drop from rest at height $z_0$, with constant density, no wind and purely vertical motion, the dynamics of Section 5 reduce to $\dot v=-g+\frac{g}{v_t^2}v^2$ (with $v\le0$). Its solution is

$$
v(t)=-v_t\tanh\!\left(\frac{gt}{v_t}\right),
$$

$$
z(t)=z_0-\frac{v_t^2}{g}\ln\cosh\!\left(\frac{gt}{v_t}\right).
$$

Setting $z(t)=0$ gives the landing time

$$
t_{\mathrm{land}}=\frac{v_t}{g}\,\operatorname{arcosh}\!\left(\exp\frac{z_0 g}{v_t^2}\right).
$$

For large arguments $\cosh$ and $\exp$ overflow in floating point, so the implementation uses the equivalent forms

$$
\ln\cosh x=x+\ln\!\left(1+e^{-2x}\right)-\ln2,\qquad
\operatorname{arcosh}(e^{a})=a+\ln\!\left(1+\sqrt{1-e^{-2a}}\right),
$$

valid for $x,a\ge0$. This closed-form solution is the reference for checking the Euler and RK4 integrators with drag: halving the step should halve the Euler error (first order) and divide the RK4 error by about 16 (fourth order).

## 12. Ground-impact interpolation

The integrator uses a fixed step $h$, so the last step usually ends below the ground. If $z_n>z_g$ and $z_{n+1}\le z_g$, the impact fraction is

$$
\lambda=\frac{z_n-z_g}{z_n-z_{n+1}},\qquad 0<\lambda\le1,
$$

and the impact time and state are found by linear interpolation:

$$
t_{\mathrm{impact}}=t_n+\lambda h,\qquad
\mathbf s_{\mathrm{impact}}=\mathbf s_n+\lambda\left(\mathbf s_{n+1}-\mathbf s_n\right).
$$

Linear interpolation has a local error of order $h^2$. For RK4 this interpolation error, not the RK4 step itself, limits the landing-point accuracy at larger steps.
