# Wind Models and Landing Uncertainty

**Project:** Wind-Compensated Ballistic Release System for Precision Payload Delivery from a UAV  
**Scope:** Wind direction conventions, height-dependent wind profiles, gusts and turbulence, and Monte Carlo landing dispersion.  
**Code:** `src/physics/wind_model.py`, `src/physics/monte_carlo.py`, `experiments/landing_dispersion.py`.

All quantities are SI and expressed in the local **East–North–Up (ENU)** frame of `docs/EQUATIONS.md`. Angles are given in degrees at the user API and converted to radians internally.

## 1. Wind direction and speed

### 1.1 Meteorological convention

Weather reports give the direction $\theta$ the wind blows **from**, measured clockwise from North. For a wind speed $W\ge0$ the ENU wind vector is

$$
\mathbf w=\begin{bmatrix}w_E\\w_N\\w_U\end{bmatrix}
=\begin{bmatrix}-W\sin\theta\\-W\cos\theta\\0\end{bmatrix}.
$$

A north wind ($\theta=0^\circ$) gives $\mathbf w=(0,-W,0)$: it blows towards the south. A west wind ($\theta=270^\circ$) gives $\mathbf w=(W,0,0)$.

The inverse is

$$
\theta=\operatorname{atan2}(-w_E,\,-w_N)\bmod 360^\circ,\qquad \theta\in[0^\circ,360^\circ).
$$

### 1.2 Along-track and cross-track components

For a UAV track $\psi$ (clockwise from North), the unit vectors along the track and to its right are

$$
\hat{\mathbf t}=\begin{bmatrix}\sin\psi\\\cos\psi\end{bmatrix},\qquad
\hat{\mathbf r}=\begin{bmatrix}\cos\psi\\-\sin\psi\end{bmatrix},
$$

so

$$
w_\parallel=w_E\sin\psi+w_N\cos\psi,\qquad
w_\perp=w_E\cos\psi-w_N\sin\psi .
$$

$w_\parallel>0$ is a tailwind (negative is a headwind); $w_\perp>0$ pushes the payload to the right of the track.

## 2. Height-dependent wind profiles

Each profile is returned as a function $\mathbf w(t,\mathbf p)$, which `state_derivative` evaluates at every integration stage. The reference wind $\mathbf w_{\mathrm{ref}}$ is measured at height $z_{\mathrm{ref}}$ (10 m, the standard anemometer height).

### 2.1 Power law

$$
\mathbf w(z)=\mathbf w_{\mathrm{ref}}\left(\frac{z}{z_{\mathrm{ref}}}\right)^{\alpha},
\qquad z\leftarrow\max(z,\,0.1\ \mathrm m).
$$

$\alpha=1/7$ is the classical value for neutral stability over open terrain. The clip at 0.1 m avoids $z\le0$ at the ground interpolation step.

### 2.2 Logarithmic law

The neutral surface-layer profile with roughness length $z_0$ is

$$
\mathbf w(z)=\mathbf w_{\mathrm{ref}}\,
\frac{\ln(z/z_0)}{\ln(z_{\mathrm{ref}}/z_0)},\qquad z>z_0,
$$

and $\mathbf w=\mathbf 0$ for $z\le z_0$. The default $z_0=0.03$ m corresponds to open flat terrain with low grass.

### 2.3 Layered wind

For a forecast or sounding with layers $(z_k,\mathbf w_k)$, $z_1<z_2<\dots<z_n$:

$$
\mathbf w(z)=\mathbf w_k+\frac{z-z_k}{z_{k+1}-z_k}\,(\mathbf w_{k+1}-\mathbf w_k),
\qquad z_k\le z\le z_{k+1},
$$

with $\mathbf w=\mathbf w_1$ below $z_1$ and $\mathbf w=\mathbf w_n$ above $z_n$.

## 3. Gusts and turbulence

### 3.1 Discrete "1-cosine" gust

$$
\mathbf w(t)=\mathbf w_{\mathrm{base}}+\frac{\mathbf A}{2}\left[1-\cos\!\left(\frac{2\pi(t-t_0)}{d}\right)\right],
\qquad t_0\le t\le t_0+d,
$$

and $\mathbf w=\mathbf w_{\mathrm{base}}$ outside the gust. The gust starts and ends smoothly and reaches its peak $\mathbf A$ at $t_0+d/2$. The base wind may be a constant vector or any profile above.

### 3.2 First-order Gauss–Markov turbulence

Each axis is an independent first-order Gauss–Markov (Ornstein–Uhlenbeck) process sampled with step $\Delta t$:

$$
u_{k+1}=a\,u_k+\sigma\sqrt{1-a^2}\;n_k,\qquad
a=\exp\!\left(-\frac{V\Delta t}{L}\right),\qquad n_k\sim\mathcal N(0,1),
$$

where $\sigma$ is the turbulence intensity, $L$ the length scale and $V$ the airspeed. The correlation time is $\tau=L/V$. The first sample is drawn from the stationary distribution $u_0\sim\mathcal N(0,\sigma^2)$, so

$$
\mathbb E[u_k]=0,\qquad \operatorname{Var}[u_k]=\sigma^2,\qquad
\mathbb E[u_k u_{k+m}]=\sigma^2a^{m}.
$$

The series is precomputed with a seeded numpy generator (reproducible), linearly interpolated in time and added to the base wind. Its power spectral density $\Phi(\omega)=2\sigma^2\tau/(1+\omega^2\tau^2)$ equals the Dryden **longitudinal** spectrum, which is why we call it "first-order Dryden-like".

## 4. Monte Carlo landing dispersion

### 4.1 Uncertain parameters

Each run draws an independent Gaussian sample

$$
q_i=\bar q_i+\sigma_i\,\xi_i,\qquad \xi_i\sim\mathcal N(0,1),
$$

for mass, area, $C_D$, $\rho$, wind speed and direction, release position $(x_0,y_0,z_0)$, release velocity $(v_{x0},v_{y0},v_{z0})$ and release delay $\delta$. Mass, area, $C_D$ and $\rho$ are truncated at 1% of the nominal value to stay strictly positive; wind speed is truncated at zero; direction is wrapped to $[0^\circ,360^\circ)$.

The release command is late by $\delta$ while the UAV keeps flying, so the release state is

$$
\mathbf p_0=\mathbf p_{\mathrm{cmd}}+\mathbf v_0\,\delta,\qquad \mathbf v(0)=\mathbf v_0 .
$$

Each sample is integrated with RK4 ($h=0.02$ s) until ground impact, giving the landing point $(x_j,y_j)$ and flight time.

### 4.2 Chosen standard deviations

| Parameter | $\sigma$ | Justification |
|---|---|---|
| $C_D$ | 10% (0.047) | Sphere $C_D$ varies with Reynolds number ($\approx 0.4$–$0.5$ in the subcritical range) and surface finish. |
| Mass | 2% (0.02 kg) | Payload build tolerance; easily weighed, so small. |
| Density | 3% (0.037 kg/m³) | Day-to-day temperature/pressure variation when no local measurement is used. |
| Wind speed | 1.5 m/s | Typical error of a forecast or of a UAV-estimated wind at 6 m/s. |
| Wind direction | 15° | Typical forecast/estimate direction error for moderate winds. |
| Release position | 1.5 m horizontal, 2 m vertical | Consumer GNSS accuracy (vertical worse than horizontal). |
| Release velocity | 0.3 m/s per axis | GNSS/INS velocity accuracy. |
| Release delay | 0.1 s | Servo/latch latency of 50–150 ms; $\sigma=0.1$ s covers this range conservatively. |

### 4.3 Dispersion statistics

With the target $\mathbf p_T=(x_T,y_T)$ (here the nominal landing point) the radial miss is

$$
r_j=\sqrt{(x_j-x_T)^2+(y_j-y_T)^2}.
$$

The **circular error probable** is the radius of the circle around the target that contains a given fraction of landings. We estimate it empirically:

$$
\mathrm{CEP}_{50}=P_{50}(r_j),\qquad \mathrm{CEP}_{95}=P_{95}(r_j).
$$

For a circular Gaussian with standard deviation $\sigma$ per axis and no bias, $r$ follows a Rayleigh distribution, so $\mathrm{CEP}_{50}=\sigma\sqrt{2\ln2}\approx1.177\sigma$ and $\mathrm{CEP}_{95}\approx2.448\sigma$ (used as a test). We also report the RMS miss $\sqrt{\overline{r^2}}$ and the fraction of landings within 10 m.

### 4.4 Confidence ellipse

Let $\boldsymbol\mu$ and $\boldsymbol\Sigma$ be the sample mean and covariance of the landing points, with eigen-decomposition

$$
\boldsymbol\Sigma=\mathbf V\boldsymbol\Lambda\mathbf V^{\mathsf T},\qquad \lambda_1\ge\lambda_2 .
$$

For a bivariate Gaussian, $d^2=(\mathbf p-\boldsymbol\mu)^{\mathsf T}\boldsymbol\Sigma^{-1}(\mathbf p-\boldsymbol\mu)$ is $\chi^2$ with 2 degrees of freedom, whose CDF is $1-e^{-d^2/2}$. The ellipse containing probability $p$ is $d^2\le k^2$ with

$$
k=\sqrt{-2\ln(1-p)}\qquad(k\approx2.448\ \text{for } p=0.95),
$$

so the semi-axes are $a=k\sqrt{\lambda_1}$, $b=k\sqrt{\lambda_2}$, and the major-axis angle is the direction of the first eigenvector, measured counter-clockwise from East.

### 4.5 Sensitivity

**One-at-a-time (OAT):** from the nominal landing $\mathbf p^{0}$, perturb one parameter by $\pm\sigma_i$ and measure

$$
S_i=\tfrac12\left(\|\mathbf p^{+i}-\mathbf p^{0}\|+\|\mathbf p^{-i}-\mathbf p^{0}\|\right).
$$

**Correlation:** $|\operatorname{corr}(q_i,r)|$ between each sampled parameter and the radial miss across the Monte Carlo runs.

## 5. Results (500 m release, `python -m experiments.landing_dispersion`)

Nominal: release at the origin, 500 m altitude, 15 m/s East; 1 kg sphere, $d=0.15$ m, $A=\pi\,0.075^2$ m², $C_D=0.47$, $\rho=1.225$ kg/m³; wind 6 m/s from 270° (west). $N=500$, seed 42. Outputs are in `results/landing_dispersion/`.

| | Constant wind | Power-law wind ($\alpha=1/7$, 6 m/s at 10 m) |
|---|---|---|
| Nominal landing $x$ | 145.0 m | 175.4 m |
| Flight time | 14.53 s | 14.50 s |
| CEP50 / CEP95 | 15.0 m / 33.0 m | 22.8 m / 50.5 m |
| RMS miss | 18.6 m | 28.9 m |
| Within 10 m | 27.6% | 14.0% |
| 95% ellipse $a\times b$ | 32.3 m × 31.9 m | 50.4 m × 49.1 m |
| Top-3 OAT | direction 12.7 m, speed 12.6 m, $v_{y0}$ 1.9 m | direction 20.1 m, speed 19.4 m, $C_D$ 2.6 m |

The nominal landing points of the two profiles differ by 30.4 m: the power law gives about 10.5 m/s at 500 m, so assuming the 10 m wind applies at all heights would cause a large systematic miss.

Observations:

- Wind speed (along-wind) and wind direction (cross-wind, $\approx W\,t\,\sigma_\theta$) give shifts of similar size, so the ellipse is almost circular and its angle is poorly defined.
- Release position and delay shift the landing one-to-one ($1.5$ m), far below the wind contribution. Better wind knowledge is the main lever for accuracy.
- With constant wind, $C_D$ barely moves the landing point; with the power-law profile it matters more because $C_D$ changes how strongly the payload follows the altitude-varying wind.
- The correlation ranking puts $C_D$ first, unlike OAT. The radial miss is V-shaped in wind speed and direction (both signs increase the miss), so their linear correlation is near zero, whereas a larger $C_D$ makes the payload follow the wind errors more closely and so scales the miss. This is an interaction effect that OAT cannot see.

## 6. Assumptions and limitations

- **Turbulence:** the first-order Gauss–Markov process matches only the Dryden longitudinal spectrum. The full Dryden model uses second-order transfer functions for lateral and vertical components, altitude-dependent $\sigma$ and $L$, and spatial (frozen-turbulence) correlation. The series here depends on time only.
- **Profiles:** power and log laws assume neutral stability and flat homogeneous terrain; they ignore stability effects, wind veer with height and obstacles.
- **Gaussian independence:** all parameters are sampled independently from Gaussians. In reality wind speed and direction errors are correlated, GNSS errors are correlated in time, and some errors (e.g. $C_D$) are better described by bounded distributions. Truncation at 1% of nominal is a numerical safeguard and is never active for the sigmas used.
- **OAT sensitivity** varies one parameter at a time around the nominal and therefore ignores interactions and nonlinearity; the correlation ranking shows such an interaction for $C_D$. Variance-based (Sobol) indices would capture these effects.
- **Target:** the target is the nominal landing point, so CEP measures random dispersion only; any bias in the nominal model (wrong profile, wrong $C_D$) appears as a systematic miss not included in the CEP.
- **Monte Carlo error:** with $N=500$ the empirical CEP95 relies on about 25 points beyond it, so its sampling error is a few percent.
