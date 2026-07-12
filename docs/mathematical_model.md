# Mathematical model

## 1. Scope and evidence status

This document specifies the reduced-order SI simulator used for the CMP
physical-state plane. The implementation is
[`simulation/cmp.py`](../src/semifab_poc/simulation/cmp.py), and the controlled
scientific decision is
[`wp08_cmp_physics.md`](../orchestration/decisions/wp08_cmp_physics.md).

Every CMP quantity in this model is synthetic simulator state or a derived
synthetic proxy. The PHM 2016 target is a separate public measured process
output in its original source-undeclared native unit. No SI simulator
coefficient is fitted from scaled PHM columns.

The model predicts average material-removal-rate behavior within a synthetic
process envelope. It does not validate scratches, dishing, erosion, corrosion,
particles, delamination, cracking, yield, equipment damage, or production
control. Its annular output is always labelled:

> Simulated spatial-uniformity proxy; not experimentally validated WIWNU.

## 2. State, commands, and boundary values

The immutable latent state includes:

- process mode and transition timers;
- commanded and realized contact pressure;
- commanded and realized signed platen/head angular speeds;
- commanded slurry flow and realized slurry availability;
- dresser command and realized dressing activity;
- pressure--velocity exposure;
- pad surface activity, remaining pad-life proxy, and dresser effectiveness;
- pad--wafer interface temperature and heat-flow terms;
- equivalent-physics and discrepancy-augmented instantaneous MRR;
- cumulative removed thickness, active polish time, and stage-average MRR.

The future utility coupler may supply only the typed boundary values
`dressing_availability`, `slurry_utility_availability`, coolant temperature,
cooling-conductance factor, bounded latent process discrepancy, validity flags,
and force-hold. The neutral default contains no UPW effect. Raw voltage, UPS,
VFD, pump, pressure, flow, or UPW signals are not CMP inputs.

All action and boundary mappings reject unknown keys. This prevents a typo or
undeclared direct coupling from silently changing MRR.

## 3. Process-state machine

The mode is

\[
\mathcal M\in\{\mathrm{IDLE},\mathrm{PREPARE},\mathrm{POLISH},
\mathrm{DRESS},\mathrm{HOLD},\mathrm{RECOVER},\mathrm{COMPLETE}\}.
\]

Define interval indicators

\[
\chi_p=\mathbf 1(\mathcal M=\mathrm{POLISH}),\qquad
\chi_d=\mathbf 1(\mathcal M=\mathrm{DRESS}).
\]

Only POLISH generates material removal and active-polish time. DRESS changes
consumable states without wafer removal. HOLD and RECOVER command the process
actuators toward zero. Entry from RECOVER to PREPARE/POLISH requires a
continuous interval of valid utility and sensor flags. COMPLETE is terminal;
a new wafer requires reset so cumulative states cannot leak between wafers.

The runtime contract remains causal: an action proposed at decision step
\(k\) is effective no earlier than plant step \(k+1\). Within `CmpSubsystem.step`,
the supplied action is already the action effective for the current interval.

## 4. Actuator dynamics

### 4.1 Contact pressure

The mean contact pressure state \(P_c\) follows

\[
\frac{dP_c}{dt}=\operatorname{clip}\left(
\frac{P_c^*-P_c}{\tau_P},-dot P^-_{max},\dot P^+_{max}
\right).
\]

Pressure and pressure slew have units Pa and Pa/s. The WP08 scalar pressure
field is uniform over the wafer. A later carrier-zone model would replace it
with \(p(r,\theta)\) while preserving its area mean; no PHM air-bag column is
declared to be pressure in Pa.

### 4.2 Signed spindle speeds

For platen and head/wafer axes,

\[
\frac{d\omega_j}{dt}=\operatorname{clip}\left(
\frac{\omega_j^*-\omega_j}{\tau_\omega},
-\dot\omega_{max},\dot\omega_{max}
\right),\quad j\in\{p,w\}.
\]

Angular speed is signed and measured in rad/s. This state prevents a later
supervisory speed action from changing the process instantaneously. The
equation is a bounded engineering abstraction, not a tool-spindle servo model.

### 4.3 Slurry availability

For recipe command \(Q_s^*\), reference flow \(Q_{s,0}\), and a typed utility
availability \(a_u\),

\[
a_s^*=\operatorname{clip}\left(\frac{Q_s^*}{Q_{s,0}}a_u,0,1\right),
\]

\[
\tau_s\frac{da_s}{dt}=a_s^*-a_s,qquad Q_s=Q_{s,0}a_s.
\]

The default has \(a_u=1\). A value derived from UPW is permitted only under a
future explicitly synthetic slurry-support topology. The three PHM slurry
columns remain separate native scaled signals and are not converted to this SI
flow.

## 5. Rotary-offset kinematics

Let the platen center be the origin. The wafer center is at vector
\(\mathbf R_{cc}\), and a wafer-fixed point is \(\mathbf r\). With the axes
parallel, the pad and wafer velocities at that point are

\[
\mathbf v_p=\omega_p\mathbf k\times(\mathbf R_{cc}+\mathbf r),
\qquad
\mathbf v_w=\omega_w\mathbf k\times\mathbf r.
\]

Their relative velocity is \(\mathbf v_R=\mathbf v_p-\mathbf v_w\). At wafer
polar coordinates \((r,\theta)\), its magnitude is

\[
v_R(r,\theta)=\sqrt{
\omega_p^2r_{cc}^2
+(\omega_p-\omega_w)^2r^2
+2\omega_p(\omega_p-\omega_w)r_{cc}r\cos\theta}.
\]

This derivation gives two important checks:

- \(\omega_p=\omega_w=\omega\) gives uniform
  \(v_R=|\omega r_{cc}|\), not zero and not a sum of speed magnitudes;
- \(\omega_p=\omega_w=0\) gives \(v_R=0\).

The area average is

\[
\langle f\rangle_A=\frac{1}{\pi R_w^2}
\int_0^{R_w}\int_0^{2\pi}f(r,\theta)r\,d\theta\,dr.
\]

The implementation uses Gauss--Legendre nodes in \(r\) and periodic midpoint
nodes in \(\theta\). The factor \(r\) is included in every radial weight. A
constant field must integrate to exactly one within floating-point tolerance.

## 6. Generalized pressure--velocity exposure

With uniform WP08 pressure,

\[
\Phi_{PV}=\left(\frac{P_c}{P_0}\right)^\alpha
\left\langle\left(\frac{v_R}{V_0}\right)^\beta\right\rangle_A,
\quad \alpha>0,\ \beta>0.
\]

The reference velocity is a power mean of the nominal field:

\[
V_0=\left\langle v_{R,0}^{\beta}\right\rangle_A^{1/\beta}.
\]

Consequently, \(P_c=P_0\) and nominal speeds produce
\(\Phi_{PV}=1\) for any frozen positive exponent. This avoids an arbitrary
effective radius and avoids changing nominal MRR merely by selecting a
generalized exponent.

For the classical \(\alpha=\beta=1\) case,

\[
K_P=\frac{R_0}{P_0V_0}.
\]

Dimensional analysis gives

\[
[K_P]=\frac{\mathrm{m/s}}{\mathrm{Pa}\,\mathrm{m/s}}
=\mathrm{Pa}^{-1},
\]

so \(K_PPV\) has unit m/s. For generalized exponents, \(R_0\) is retained as
the dimensional reference and \(\Phi_{PV}\) is dimensionless.

## 7. Consumable states

The reduced state distinguishes:

- \(g_p\in[0,1]\), reversible pad-surface activity;
- \(\ell_p\in[0,1]\), irreversible remaining pad-life proxy;
- \(h_d\in[0,1]\), dresser effectiveness.

Their equations are

\[
\frac{dg_p}{dt}=-\chi_pk_g\Phi_{PV}g_p
+\chi_dk_ca_dh_d(1-g_p),
\]

\[
\frac{d\ell_p}{dt}=-\chi_pk_{wp}\Phi_{PV}-\chi_dk_{wd}a_d,
\]

\[
\frac{dh_d}{dt}=-\chi_dk_da_dh_d.
\]

Here \(a_d\in[0,1]\) is dresser command multiplied by typed dressing
availability. Projection to [0,1] is declared reduced-order behavior.
Conditioning can restore \(g_p\), but cannot increase \(\ell_p\) or \(h_d\).
The removal modifier is

\[
m_{pad}=m_{p,min}+(1-m_{p,min})g_p\ell_p^{\gamma_p}.
\]

These bounded states deliberately replace an ambiguous single consumable age.
All default rates are synthetic assumptions pending calibration.

## 8. Interface energy balance

Interface temperature \(T_i\) is not UPW temperature. The lumped energy
balance is

\[
C_i\frac{dT_i}{dt}=\dot Q_f-\dot Q_c-\dot Q_s,
\]

where

\[
\dot Q_f=\chi_p\eta_f\mu A_cP_c\overline v_R,
\]

\[
\dot Q_c=UA_0f_{UA}(T_i-T_c),
\]

\[
\dot Q_s=\rho_sc_{p,s}Q_s(T_i-T_s).
\]

The friction term is W because
\(A_cP_c\overline v_R\) has unit
\(\mathrm{m^2\,Pa\,m/s=N\,m/s=W}\). The coolant and slurry terms are also W.
The discrete audit residual is

\[
e_E=C_i\frac{T_i^{k+1}-T_i^k}{\Delta t}
-(\dot Q_f-\dot Q_c-\dot Q_s).
\]

Temperature affects removal through

\[
m_T=\operatorname{clip}\left(
\exp[\beta_T(T_i-T_0)],m_{T,min},m_{T,max}\right).
\]

The default \(\beta_T=0\) is a structural negative control, so thermal state
evolves without changing MRR. Any nonzero profile is explicitly synthetic and
must be compared with the null.

## 9. Removal and accumulated metrology

The default slurry modifier is \(m_s=a_s\). Equivalent removal is

\[
R_{eq}=\chi_pR_0\Phi_{PV}m_sm_Tm_{pad}m_{recipe}.
\]

For bounded latent discrepancy \(\epsilon_{proc}\),

\[
R_{true}=\chi_p\operatorname{clip}
(R_{eq}+\epsilon_{proc},0,R_{max}).
\]

The discrepancy is simulator truth and is never an online predictor or
controller input. There is no separate MRR lag: pressure, spindle, slurry,
thermal, and consumable states already create the retained dynamics.

Using the end-of-step rate over one discrete interval,

\[
H^{k+1}=H^k+\Delta tR_{true}^{k+1},
\]

\[
t_p^{k+1}=t_p^k+\Delta t\chi_p,
\]

\[
\overline R^{k+1}=\frac{H^{k+1}}
{\max(t_p^{k+1},\varepsilon)}.
\]

This separates instantaneous MRR, cumulative thickness, and stage-average
MRR. The PHM target is conceptually analogous only to a stage aggregate and
remains in its native unit. Hold duration never enters \(t_p\), and later
evaluation reports hold/throughput penalties separately.

## 10. Frozen synthetic reference profile

The default configuration uses a 150 mm wafer radius, 0.20 m center offset,
30 kPa nominal contact pressure, signed nominal platen/head speeds of 8/6
rad/s, and 10 mL/s reference slurry flow. Reference MRR is
\(1.6666666667\times10^{-9}\) m/s, or 100 nm/min; maximum simulated MRR is
\(5\times10^{-9}\) m/s.

Those values define a reproducible synthetic experiment. They are not a claim
about the PHM tool, a specific slurry/material stack, or a real fab process.
The complete value/bound/provenance registry is in the controlled decision and
`configs/default.yaml`.

## 11. Numerical method and invariants

Each step uses deterministic explicit updates. `dt_s` may not exceed the
minimum pressure, spindle, slurry, or worst-case thermal time constant.
Temperature is not clipped: leaving its envelope raises a model error. Health
projection is explicit, and cumulative removal is nondecreasing because true
MRR is finite and nonnegative.

Required checks are:

- constant-field and refined quadrature;
- zero-speed and zero-pressure limits;
- exact nominal exposure and reference MRR;
- mode-gated removal and active time;
- bounded pressure, speed, slurry, health, temperature, and MRR;
- dressing recovery with irreversible pad/dresser consumption;
- thermal residual closure;
- timestep refinement;
- deterministic replay;
- exact spatial-proxy label;
- complete parameter-provenance classification.

Machine-readable evidence is generated by
[`validate_wp08_cmp.py`](../scripts/validate_wp08_cmp.py). All internal checks,
48 focused impacted tests, and the 130-test complete suite pass. The validated
results and numerical tolerances are recorded in
[`wp08_cmp_validation.md`](../orchestration/reports/wp08_cmp_validation.md).

## 12. Utility-to-CMP coupling

The implemented coupler is
[`simulation/coupling.py`](../src/semifab_poc/simulation/coupling.py), and its
controlled decision is
[`wp10_utility_cmp_coupling.md`](../orchestration/decisions/wp10_utility_cmp_coupling.md).
It is a stateless map from validated latent `UpwState` to the frozen
`CmpBoundaryConditions`; it is not a dynamic subsystem, sensor model,
predictor, controller, or safety filter.

Let

\[
p=P_s/P_{ref},\qquad q=Q_t/Q_{ref},
\]

and define

\[
R(x;x_0,x_1)=\operatorname{clip}\left(
\frac{x-x_0}{x_1-x_0},0,1\right).
\]

The raw and effective availability values are

\[
a_h=\min\{R(p;p_0,p_1),R(q;q_0,q_1)\},
\]

\[
a_{eff}=1-\lambda(1-a_h),\qquad 0\le\lambda\le1.
\]

The pressure and flow indicators are not multiplied because both arise from
the same hydraulic network; the minimum represents a limiting service and
avoids double penalization. This bottleneck/ramp model is an engineering
approximation. The numerical references, thresholds, and link strength are
synthetic assumptions.

The topology map is

\[
\mathcal C_{none}: (a_d,a_s,T_c,f_{UA})=(1,1,T_{c,0},1),
\]

\[
\mathcal C_{dress}: a_d=a_{eff},
\]

\[
\mathcal C_{thermal}:
T_c=T_{c,0}+\lambda(T_u-T_{u,ref}),\quad f_{UA}=a_{eff},
\]

\[
\mathcal C_{slurry}: a_s=a_{eff}.
\]

Unlisted fields retain neutral values. `NO_CONNECTION` requires exactly zero
link strength. Zero link yields an exact neutral boundary in every connected
topology. The corrected thermal equation distinguishes the CMP coolant
reference \(T_{c,0}\) from upstream UPW reference \(T_{u,ref}\), so zero link
and nominal upstream temperature are independent exact nulls. Mapped
temperature leaving the CMP envelope raises an error rather than being
silently clipped.

The primary connected structure is delayed dressing-water support:

\[
a_d(t)\longrightarrow g_p(t_{dress,end})
\longrightarrow m_{pad}(t_{polish})
\longrightarrow R_{eq}(t_{polish}).
\]

Therefore a DRESS disturbance cannot generate MRR while DRESS is active; it
changes later POLISH behavior through pad-state memory. The water-quality
deviation proxy is absent from every topology equation.

The healthy-UPS 25%/400 ms sag keeps \(a_h=a_{eff}=1\) and produces an exact
CMP negative control. In the separately declared synthetic 3 s interruption
with a degraded 500 J UPS, dressing availability reaches zero. End-of-DRESS
pad activity changes from 0.5511876609 in the null case to 0.5216572820 in the
connected case; later mean MRR changes from 1.0198314108e-9 to
9.8727270376e-10 m/s. These are model outputs under synthetic assumptions, not
calibrated material or equipment responses.

Task-local local/global/mismatch sensitivity and exact trace hashes are in
[`wp10_coupling_validation.md`](../orchestration/reports/wp10_coupling_validation.md).

## 13. Structural limitations

- Pressure is uniform; carrier-zone pressure and edge mechanics are omitted.
- The model does not resolve pad asperities, particles, chemistry, pattern
  density, slurry hydrodynamics, or reaction kinetics.
- Friction coefficient and heat partition are constants.
- Thermal state is lumped and has no radial conduction field.
- Consumable health variables are reduced proxies, not measured pad metrology.
- Spindle dynamics do not represent a manufacturer servo or torque limit.
- The default thermal path is structurally decoupled from MRR.
- The repository runtime defaults to no connection; the connected topologies
  are synthetic experiments and actual PHM-tool plumbing remains unknown.
- Annular exposure is not experimentally validated WIWNU.
- No physical-defect, yield, equipment, or production claim follows from MRR.

## 14. Supporting primary literature

- F. W. Preston, “The Theory and Design of Plate Glass Polishing Machines”
  (1927), empirical pressure--velocity relationship.
- H. Hocheng, H. Y. Tsai, and M. S. Tsai, rotary kinematics and experimental
  nonuniformity analysis, https://doi.org/10.1016/S0890-6955(00)00013-4.
- D. White, J. Melvin, and D. Boning, dynamic CMP thermal energy balance and
  measurements, https://doi.org/10.1149/1.1560642.
- L. J. Borucki et al., pad-conditioning and wear surface evolution,
  https://doi.org/10.1023/B:ENGI.0000042116.09084.00.
- L. Borucki, L. Charns, and A. Philipossian, frictional heat and slurry heat
  transport, https://doi.org/10.1149/1.1808635.
- O. Chang et al., mathematical CMP conditioning model,
  https://doi.org/10.1016/j.mee.2006.11.011.
- M. Bahr et al., slurry availability, residual rinse-water mixing, and
  removal-rate response, https://doi.org/10.3390/mi8060170.
- N.-H. Kim et al., DI-water conditioning-temperature effects on pad state and
  subsequent oxide polishing, https://doi.org/10.1016/j.mee.2005.07.080.
- C. Mudhivarthi et al., slurry-flow and water-conditioning-temperature
  effects, https://doi.org/10.1149/1.2177007.

These sources support equation structure and limiting-case reasoning. They do
not calibrate the frozen synthetic parameter values.
