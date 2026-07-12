# Decision: WP08 reduced-order CMP physics model

Date: 2026-07-11  
Status: FROZEN FOR IMPLEMENTATION AND TASK-LOCAL VALIDATION  
Task: T-WP08  
Supersedes: the CMP portion of the withdrawn decision
`20260711_phase_3_cmp_and_utility_model.md`  
Controlled basis: `orchestration/reports/phase_3_cmp_model_redesign.md`

## Decision summary

WP08 will implement a deterministic, fully synthetic, SI-unit CMP subsystem
with explicit process modes, bounded pressure and spindle dynamics,
rotary-offset two-axis kinematics, deterministic area quadrature, normalized
generalized-Preston removal, slurry-delivery dynamics, an interface energy
balance, distinct reversible and irreversible consumable states, and
cumulative removal. It will implement no electrical or UPW gain.

Future WP10 coupling may affect CMP only through the typed boundary variables
frozen here. A no-connection boundary is the neutral default. The PHM public
data model remains a separate native-unit evidence plane and cannot calibrate
these SI coefficients without a documented bridge.

The model is a reduced-order scientific PoC. It does not predict physical
defects, wafer yield, equipment damage, or real production behavior.

## Missing elements found during the freeze review

The approved redesign correctly added process modes, consumables, slurry,
thermal state, and cumulative removal. The implementation freeze adds four
details needed to make those elements numerically and causally usable:

1. platen and head angular speeds are dynamic, slew-limited signed states;
2. generalized velocity exposure is normalized by its nominal power mean, so
   the reference case is exactly one for any frozen positive exponent;
3. process-mode transitions and recovery dwell are explicit rather than
   inferred from signal magnitudes; and
4. each step exposes a thermal energy-balance residual.

Without spindle dynamics, later speed interventions would be instantaneous.
Without power-mean normalization, changing the generalized-Preston exponent
would silently change the configured nominal MRR.

## Evidence-plane boundary

| Quantity | Evidence class | Permitted interpretation |
|---|---|---|
| PHM MRR target | Public measured process output in native, source-undeclared unit | Offline virtual-metrology target only |
| CMP pressure, speed, slurry, temperature, health | Simulated physical state | Synthetic latent process state |
| Instantaneous/cumulative/average MRR | Derived synthetic state | Simulator response, not measured wafer metrology |
| Annular exposure profile | Quality-risk proxy | Mandatory label: “Simulated spatial-uniformity proxy; not experimentally validated WIWNU.” |
| Process discrepancy | Seedable synthetic latent input | Never online-visible |

## Process modes and transition contract

The mode is

\[
\mathcal M\in\{\mathrm{IDLE},\mathrm{PREPARE},\mathrm{POLISH},
\mathrm{DRESS},\mathrm{HOLD},\mathrm{RECOVER},\mathrm{COMPLETE}\}.
\]

The allowed directed transitions are:

| From | Allowed requested modes |
|---|---|
| IDLE | IDLE, PREPARE, HOLD |
| PREPARE | PREPARE, POLISH, DRESS, HOLD, COMPLETE |
| POLISH | POLISH, DRESS, HOLD, COMPLETE |
| DRESS | DRESS, PREPARE, HOLD, COMPLETE |
| HOLD | HOLD, RECOVER, COMPLETE |
| RECOVER | RECOVER, PREPARE, POLISH, HOLD, COMPLETE |
| COMPLETE | COMPLETE |

`COMPLETE` is terminal; a new wafer requires `reset`. `force_hold` overrides a
nonterminal request. Entry to POLISH requires valid utility and sensor
boundary flags. RECOVER accumulates valid dwell only while both flags are true;
PREPARE or POLISH cannot resume before the configured dwell. Only the mode
effective over the current interval controls its dynamics.

Define

\[
\chi_p=\mathbf 1(\mathcal M=\mathrm{POLISH}),\qquad
\chi_d=\mathbf 1(\mathcal M=\mathrm{DRESS}).
\]

Only \(\chi_p=1\) permits material removal or active-polish-time accumulation.
HOLD, RECOVER, IDLE, and COMPLETE command pressure, spindles, and slurry toward
zero; lingering physical states decay according to their dynamics but cannot
remove material.

## Actuator-state dynamics

Mean contact pressure is a bounded state:

\[
\dot P_c=\operatorname{clip}\!\left(
\frac{P_c^*-P_c}{\tau_P},-\dot P^-_{\max},\dot P^+_{\max}
\right).
\]

Signed platen and head speeds use the same bounded first-order/slew form:

\[
\dot\omega_j=\operatorname{clip}\!\left(
\frac{\omega_j^*-\omega_j}{\tau_\omega},
-\dot\omega_{\max},\dot\omega_{\max}
\right),\quad j\in\{p,w\}.
\]

The sign carries direction. State and command magnitudes are independently
bounded. These spindle equations are engineering structure with synthetic
time constants, not a CMP-tool servo model.

For commanded slurry flow \(Q_s^*\) and typed utility availability \(a_u\),

\[
a_s^*=\operatorname{clip}\!\left(
\frac{Q_s^*}{Q_{s,0}}a_u,0,1\right),\qquad
\tau_s\dot a_s=a_s^*-a_s,\qquad Q_s=Q_{s,0}a_s.
\]

## Rotary-offset kinematics and quadrature

For wafer-fixed polar position \((r,\theta)\), center offset \(r_{cc}\),
platen speed \(\omega_p\), and head/wafer speed \(\omega_w\), subtracting the
two velocity vectors gives

\[
v_R(r,\theta)=\sqrt{\omega_p^2r_{cc}^2
+(\omega_p-\omega_w)^2r^2
+2\omega_p(\omega_p-\omega_w)r_{cc}r\cos\theta}.
\]

Angular-speed signs are not discarded. Equal co-rotation gives the useful
limiting case \(v_R=|\omega_p r_{cc}|\) everywhere. Zero speeds give zero
relative speed.

The area average of a field \(f\) is

\[
\langle f\rangle_A=\frac{1}{\pi R_w^2}
\int_0^{R_w}\int_0^{2\pi}f(r,\theta)r\,d\theta\,dr.
\]

Implementation uses Gauss--Legendre radial quadrature and periodic midpoint
angular quadrature. The quadrature of the constant field must equal one and
refinement must converge.

## Normalized generalized-Preston exposure

For uniform mean pressure in WP08,

\[
\Phi_{PV}=\left(\frac{P_c}{P_0}\right)^\alpha
\left\langle\left(\frac{v_R}{V_0}\right)^\beta\right\rangle_A.
\]

The reference velocity is not an arbitrary effective radius. It is derived
from the nominal kinematic field:

\[
V_0=\left\langle v_{R,0}^{\beta}\right\rangle_A^{1/\beta},
\quad \alpha>0,\ \beta>0.
\]

Therefore \(\Phi_{PV}=1\) at nominal pressure and speeds for any frozen
positive \(\alpha,\beta\). With \(\alpha=\beta=1\), the equivalent Preston
coefficient is

\[
K_P=\frac{R_0}{P_0V_0},\qquad [K_P]=\mathrm{Pa}^{-1},
\]

and \(R=K_PPV\) has unit m/s. For generalized exponents, \(R_0\) retains m/s
and every exposure factor remains dimensionless.

## Consumable dynamics

The bounded state contains reversible surface activity \(g_p\), irreversible
remaining pad life \(\ell_p\), and dresser effectiveness \(h_d\):

\[
\dot g_p=-\chi_pk_g\Phi_{PV}g_p
+\chi_dk_ca_dh_d(1-g_p),
\]

\[
\dot\ell_p=-\chi_pk_{wp}\Phi_{PV}-\chi_dk_{wd}a_d,
\qquad
\dot h_d=-\chi_dk_da_dh_d.
\]

Here \(a_d\) is dresser command times typed dressing availability. Projection
to [0,1] is explicit. Dressing may increase \(g_p\), but neither \(\ell_p\)
nor \(h_d\) may increase. The pad multiplier is

\[
m_{pad}=m_{p,\min}+(1-m_{p,\min})g_p\ell_p^{\gamma_p}.
\]

All default rates are synthetic assumptions.

## Interface energy balance

The interface state is distinct from UPW temperature:

\[
C_i\dot T_i=\dot Q_f-\dot Q_c-\dot Q_s,
\]

\[
\dot Q_f=\chi_p\eta_f\mu A_cP_c\overline v_R,
\quad
\dot Q_c=UA_0f_{UA}(T_i-T_c),
\quad
\dot Q_s=\rho_sc_{p,s}Q_s(T_i-T_s).
\]

Each term has unit W. The discrete residual is

\[
e_E=C_i\frac{T_i^{k+1}-T_i^k}{\Delta t}
-(\dot Q_f-\dot Q_c-\dot Q_s).
\]

The modifier is

\[
m_T=\operatorname{clip}\!\left(
\exp[\beta_T(T_i-T_0)],m_{T,\min},m_{T,\max}\right).
\]

The conservative default is \(\beta_T=0\), hence \(m_T=1\). A nonzero value
is a named synthetic material profile and must be compared with the null case.

## Instantaneous, cumulative, and average removal

Slurry modifier \(m_s=a_s^{\gamma_s}\) uses \(\gamma_s=1\) in the frozen
baseline. The equivalent physical rate is

\[
R_{eq}=\chi_pR_0\Phi_{PV}m_sm_Tm_{pad}m_{recipe}.
\]

With bounded latent process discrepancy \(\epsilon_{proc}\),

\[
R_{true}=\chi_p\operatorname{clip}
(R_{eq}+\epsilon_{proc},0,R_{max}).
\]

The discrepancy is logged simulator truth and forbidden from online inputs.
No additional arbitrary MRR lag is introduced because pressure, spindles,
slurry, temperature, and consumables already provide dynamic states.

\[
H^{k+1}=H^k+\Delta tR_{true}^{k+1},\qquad
t_p^{k+1}=t_p^k+\Delta t\chi_p,
\qquad \overline R=H/\max(t_p,\varepsilon).
\]

HOLD time is not active polish time and cannot be scored as zero-MRR success.

## Frozen default parameter registry

No default numerical value is claimed as tool calibration. “Literature” below
supports an equation form or classical exponent, not the particular synthetic
equipment value.

| Parameter/group | Default | Unit | Allowed bound | Provenance class |
|---|---:|---|---|---|
| wafer radius | 0.15 | m | > 0 | Synthetic assumption |
| center offset | 0.20 | m | > 0 | Synthetic assumption |
| radial/angular quadrature order | 16 / 64 | 1 | >= 4 / >= 8 | Engineering approximation |
| nominal / maximum pressure | 30,000 / 60,000 | Pa | positive; nominal <= maximum | Synthetic assumption |
| pressure time constant | 0.20 | s | > 0 | Synthetic assumption |
| pressure ramp up/down | 100,000 / 200,000 | Pa/s | > 0 | Synthetic assumption |
| nominal platen/head speed | 8 / 6 | rad/s | within signed magnitude bounds | Synthetic assumption |
| maximum platen/head magnitude | 15 / 15 | rad/s | > 0 | Synthetic assumption |
| spindle time constant / slew | 0.15 / 40 | s / rad/s2 | > 0 | Synthetic assumption |
| reference slurry flow / time constant | 1.0e-5 / 0.40 | m3/s / s | > 0 | Synthetic assumption |
| reference MRR | 1.6666666667e-9 | m/s | > 0; equals 100 nm/min | Synthetic assumption |
| maximum MRR | 5.0e-9 | m/s | >= reference | Synthetic assumption |
| pressure / velocity exponent | 1 / 1 | 1 | (0, 3] | Literature-supported classical baseline |
| recipe modifier range | 0.5 to 1.5 | 1 | positive | Synthetic assumption |
| minimum pad modifier / life exponent | 0.25 / 1 | 1 | [0,1] / > 0 | Synthetic assumption |
| glazing / conditioning rate | 2.0e-4 / 2.0e-2 | 1/s | >= 0 | Synthetic assumption |
| polish/dress pad-wear rate | 1.0e-5 / 5.0e-5 | 1/s | >= 0 | Synthetic assumption |
| dresser-wear rate | 2.0e-5 | 1/s | >= 0 | Synthetic assumption |
| interface reference/range | 293.15 / 273.15--353.15 | K | physical positive range | Synthetic assumption |
| interface thermal capacity | 5,000 | J/K | > 0 | Synthetic assumption |
| heat fraction / friction coefficient | 0.8 / 0.05 | 1 | [0,1] / >= 0 | Synthetic assumption |
| nominal cooling conductance | 200 | W/K | > 0 | Synthetic assumption |
| maximum conductance factor | 2 | 1 | >= 1 | Synthetic assumption |
| slurry density / heat capacity | 1,000 / 4,000 | kg/m3 / J/(kg K) | > 0 | Engineering approximation |
| slurry supply temperature | 293.15 | K | interface temperature range | Synthetic assumption |
| temperature sensitivity | 0 | 1/K | [-0.1,0.1] | Synthetic structural-null assumption |
| temperature modifier range | 0.5 to 1.5 | 1 | positive and spanning one | Synthetic assumption |
| maximum discrepancy magnitude | 1.0e-9 | m/s | >= 0 | Synthetic assumption |
| minimum valid recovery dwell | 0.5 | s | > 0 | Synthetic safety assumption |

## Typed boundary contract for WP10

`CmpBoundaryConditions` contains only:

- `dressing_availability` in [0,1];
- `slurry_utility_availability` in [0,1];
- `coolant_temperature_k` in the frozen thermal envelope;
- `cooling_conductance_factor` in [0, configured maximum];
- bounded `process_discrepancy_m_s`;
- boolean `utilities_valid`, `sensors_valid`, and `force_hold`.

Neutral/no-connection values are one for availabilities and conductance factor,
reference temperature for coolant, zero discrepancy, true validity flags, and
false force-hold. WP08 never reads voltage, UPS, VFD, pump, pressure, or UPW
signals directly. WP10 must own every mapping from plant state to this boundary.

## Numerical policy

Pressure, spindle, slurry, consumable, cumulative, and thermal states use a
deterministic explicit update. Runtime `dt_s` may not exceed the minimum of the
pressure, spindle, slurry, and worst-case thermal time constants. Bounded
health projection is declared model behavior. Thermal temperature is not
silently clipped: leaving its envelope is a model error. State, action, and
boundary mappings reject unknown keys and nonfinite values.

## Schema and interface impact

This is an additive controlled change:

- canonical schema 2.2.0 -> 2.3.0;
- interface registry 3.0.0 -> 3.1.0;
- `DynamicSubsystem` remains 2.0.0;
- SensorModel and Scenario remain 2.0.0;
- the runtime contract adds a typed CMP boundary but does not change online
  visibility or next-step action timing.

New signals identify mode, commands, exposure, consumable health, interface
temperature, cumulative removal, active time, stage-average MRR, and energy
residual. Legacy age signals remain deprecated. Signed angular-speed ranges
are broadened to encode rotation direction. Configuration hashes for frozen
2.1/2.0 and 2.2/3.0 checkpoints exclude the later CMP section so their recorded
canonical hashes remain reproducible.

## Rejected alternatives

- A direct generic UPW-to-MRR multiplier: no declared physical topology.
- Adding head and platen speed magnitudes: incorrect for co-rotation and
  double-counts kinematics.
- A fixed effective radius: hides geometry and exponent dependence.
- Algebraic actuator commands: creates unrealistically instantaneous control.
- One monotone consumable age: cannot distinguish glazing recovery from wear.
- Equating UPW and interface temperature: assumes plumbing not in evidence.
- Tuning thermal sensitivity from PHM: PHM has no declared temperature signal.
- Treating annular exposure as validated WIWNU: no measured spatial metrology.
- Adding an arbitrary MRR lag: duplicates already explicit dynamic states.

## Acceptance evidence required

1. exact constant-field quadrature and kinematic special cases;
2. quadrature refinement convergence;
3. nominal reference gives exposure one and MRR \(R_0\);
4. inactive, zero-pressure, and zero-speed cases give zero MRR;
5. only POLISH accumulates removal and active time;
6. dressing restores activity but not pad/dresser life;
7. slurry, temperature, health, commands, and MRR remain bounded and finite;
8. every step satisfies the declared thermal residual tolerance;
9. timestep-refined dynamic traces converge;
10. fixed inputs replay deterministically;
11. any spatial result contains the mandatory proxy label; and
12. the full pre-existing suite still passes in conda environment `devkki`.

## Primary literature supporting structure

- Preston, “The Theory and Design of Plate Glass Polishing Machines” (1927),
  empirical pressure--velocity law.
- Hocheng, Tsai, and Tsai, kinematics and velocity-integral experiments,
  https://doi.org/10.1016/S0890-6955(00)00013-4.
- White, Melvin, and Boning, dynamic thermal energy balance with pad/slurry
  measurements, https://doi.org/10.1149/1.1560642.
- Borucki, Witelski, Please, Kramer, and Schwendeman, conditioning/wear surface
  evolution, https://doi.org/10.1023/B:ENGI.0000042116.09084.00.
- Borucki, Charns, and Philipossian, frictional heat and slurry transport,
  https://doi.org/10.1149/1.1808635.
- Chang et al., CMP pad-conditioning model,
  https://doi.org/10.1016/j.mee.2006.11.011.

These sources support the selected state and balance structures. They do not
validate the frozen synthetic parameter values or a specific PHM tool.
