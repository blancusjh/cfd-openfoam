# Convección natural: esfera caliente en una habitación

Formulación matemática del problema resuelto en el caso `RoomSphere`
(convección natural, aproximación de Boussinesq, régimen laminar).

---

## 1. Dominio $\Sigma$ y frontera $\partial\Sigma$

El fluido (aire) ocupa el dominio $\Sigma \subset \mathbb{R}^3$: la habitación **menos** la esfera,

$$
\Sigma \;=\; \mathcal{R}\setminus \overline{\mathcal{B}},
\qquad
\mathcal{R} = (-0.3,\,0.3)\times(0,\,1.0)\times(-0.3,\,0.3)\ \text{[m]},
\qquad
\mathcal{B} = \{\,\mathbf{x}\in\mathbb{R}^3 : \lVert \mathbf{x}-\mathbf{x}_c\rVert < R\,\},
$$

con centro de la esfera $\mathbf{x}_c=(0,\,0.3,\,0)$ y radio $R=0.1$ m.

La frontera se parte en cuatro trozos disjuntos,

$$
\partial\Sigma \;=\; \partial\Sigma_{s}\ \cup\ \partial\Sigma_{c}\ \cup\ \partial\Sigma_{f}\ \cup\ \partial\Sigma_{w},
$$



| Parte | Descripción | Definición |
|---|---|---|
| $\partial\Sigma_{s}$ | superficie de la esfera (**caliente**) | $\lVert\mathbf{x}-\mathbf{x}_c\rVert = R$ |
| $\partial\Sigma_{c}$ | techo (**frío**) | $y = 1.0$ |
| $\partial\Sigma_{f}$ | suelo (aislado) | $y = 0$ |
| $\partial\Sigma_{w}$ | paredes laterales (aisladas) | $x=\pm 0.3,\ \ z=\pm 0.3$ |

Denotamos por $\mathbf{n}$ la normal unitaria exterior a $\partial\Sigma$, y por
$\partial_{\mathbf n}(\cdot)=\mathbf{n}\cdot\nabla(\cdot)$ la derivada normal.
El horizonte temporal es $t\in(0,\,t_f\,]$, con $t_f = 30$ s.

---

## 2. Incógnitas

$$
\mathbf{U}:\Sigma\times(0,t_f]\to\mathbb{R}^3\ \text{(velocidad)},\qquad
T:\Sigma\times(0,t_f]\to\mathbb{R}\ \text{(temperatura)},\qquad
p_{rgh}:\Sigma\times(0,t_f]\to\mathbb{R}\ \text{(presión reducida)}.
$$

---

## 3. Ecuaciones de gobierno   (en $\Sigma\times(0,t_f]$)

**Continuidad** (incompresibilidad de Boussinesq):

$$
\nabla\cdot\mathbf{U} = 0
$$

**Cantidad de movimiento** (Navier–Stokes con flotabilidad):

$$
\frac{\partial \mathbf{U}}{\partial t} + (\mathbf{U}\cdot\nabla)\mathbf{U}
= -\frac{1}{\rho_0}\nabla p_{rgh} + \nu\,\nabla^2\mathbf{U}
\;\underbrace{-\,\beta\,(T-T_0)\,\mathbf{g}}_{\text{flotabilidad}}
$$

**Energía** (transporte de temperatura):

$$
\frac{\partial T}{\partial t} + \underbrace{(\mathbf{U}\cdot\nabla)T}_{\text{convección}}
= \underbrace{\alpha\,\nabla^2 T}_{\text{difusión}}
$$

---

## 4. Relaciones constitutivas

$$
\rho = \rho_0\big(1-\beta\,(T-T_0)\big) \quad\text{(estado, Boussinesq)},
\qquad
p = p_{rgh} + \rho\,\mathbf{g}\cdot\mathbf{r} \quad\text{(presión física)},
$$

$$
\nu = \frac{\mu}{\rho_0},\qquad
\alpha = \frac{k}{\rho_0\,c_p} = \frac{\nu}{\mathrm{Pr}},\qquad
\mathbf{g} = -\,g\,\mathbf{e}_y ,
$$

donde $\mathbf{r}$ es el vector de posición y $\mathbf{e}_y$ el versor vertical.

---

## 5. Condición inicial   (en $\Sigma$, $t=0$)

$$
\mathbf{U}(\mathbf{x},0) = \mathbf{0},\qquad
T(\mathbf{x},0) = T_\infty = 300\ \text{K},\qquad
p_{rgh}(\mathbf{x},0) = 0 .
$$

El aire arranca en reposo y a temperatura ambiente uniforme.

---

## 6. Condiciones de contorno   (en $\partial\Sigma$, $t>0$)

**Velocidad** — no deslizamiento e impenetrabilidad en todas las paredes:

$$
\mathbf{U} = \mathbf{0}
\qquad \text{sobre } \partial\Sigma_{s}\cup\partial\Sigma_{c}\cup\partial\Sigma_{f}\cup\partial\Sigma_{w}.
$$

**Temperatura** — Dirichlet en esfera y techo, Neumann homogénea (adiabática) en suelo y paredes:

$$
\begin{aligned}
T &= T_{s} = 350\ \text{K} && \text{sobre } \partial\Sigma_{s} && \text{(Dirichlet, foco caliente)},\\
T &= T_{\infty} = 300\ \text{K} && \text{sobre } \partial\Sigma_{c} && \text{(Dirichlet, sumidero frío)},\\
\partial_{\mathbf n} T &= 0 && \text{sobre } \partial\Sigma_{f}\cup\partial\Sigma_{w} && \text{(Neumann, aislada)}.
\end{aligned}
$$

**Presión reducida** — Neumann (flujo consistente) en toda la frontera:

$$
\partial_{\mathbf n}\, p_{rgh} = 0
\qquad \text{sobre } \partial\Sigma,
$$

más una **condición de referencia** que fija la constante indeterminada (el problema de
presión es puramente de Neumann en un dominio cerrado):

$$
p_{rgh}(\mathbf{x}_\ast,t) = 0 \quad\text{en un punto de referencia } \mathbf{x}_\ast\in\Sigma .
$$

> En OpenFOAM: $\mathbf U$ con `noSlip`; $T$ con `fixedValue`/`zeroGradient`;
> $p_{rgh}$ con `fixedFluxPressure` (Neumann consistente con el flujo de $\mathbf U$)
> y `pRefCell`/`pRefValue` para la referencia.

---

## 7. Parámetros

| Símbolo | Significado | Valor | Unidad |
|---|---|---|---|
| $\rho_0$ | densidad de referencia | $1.2$ | kg·m⁻³ |
| $T_0$ | temperatura de referencia | $300$ | K |
| $\beta$ | coef. de expansión térmica | $3.3\times10^{-3}$ | K⁻¹ |
| $\mu$ | viscosidad dinámica | $1.8\times10^{-5}$ | Pa·s |
| $\nu=\mu/\rho_0$ | viscosidad cinemática | $1.5\times10^{-5}$ | m²·s⁻¹ |
| $\mathrm{Pr}$ | número de Prandtl | $0.7$ | – |
| $\alpha=\nu/\mathrm{Pr}$ | difusividad térmica | $2.14\times10^{-5}$ | m²·s⁻¹ |
| $g$ | gravedad | $9.81$ | m·s⁻² |
| $T_s$ | temperatura de la esfera | $350$ | K |
| $T_\infty$ | temperatura ambiente | $300$ | K |
| $R$ | radio de la esfera | $0.1$ | m |
| $t_f$ | tiempo final | $30$ | s |

---

## 8. Números adimensionales

Con longitud característica el diámetro $D = 2R = 0.2$ m y salto $\Delta T = T_s-T_\infty = 50$ K:

$$
\mathrm{Ra} = \frac{g\,\beta\,\Delta T\,D^{3}}{\nu\,\alpha}
\;\approx\; 4\times 10^{7},
\qquad
\mathrm{Pr} = \frac{\nu}{\alpha} = 0.7 .
$$

$\mathrm{Ra}\gg\mathrm{Ra}_c\ (\sim 10^{3})$: la flotabilidad domina sobre la difusión
viscosa → régimen de convección desarrollada (pluma térmica + recirculación).

---

## 9. Acoplamiento

Las ecuaciones de momento y energía están acopladas en un lazo de realimentación:

$$
T \ \xrightarrow{\ \text{flotabilidad (mom.)}\ }\ \mathbf{U}
\ \xrightarrow{\ \text{convección (energía)}\ }\ T .
$$

La temperatura genera movimiento (término $-\beta(T-T_0)\mathbf g$); el movimiento
redistribuye la temperatura (término $(\mathbf U\cdot\nabla)T$). Ese lazo es el origen
de la pluma y la circulación, y lo que distingue este problema de la pura ecuación del
calor $\partial_t T = \alpha\nabla^2 T$ (que se recupera si $\mathbf U\equiv\mathbf 0$).
