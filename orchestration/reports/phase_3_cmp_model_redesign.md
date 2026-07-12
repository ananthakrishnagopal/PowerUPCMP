# Phase 3 CMP physics and coupling redesign

Date: 2026-07-11  
Status: user-approved controlled design basis; standalone CMP portion implemented and validated in WP08, coupling/VM/control portions pending  
Replaces: the scientific content proposed in
orchestration/decisions/20260711_phase_3_cmp_and_utility_model.md  
Primary principle: use the smallest model that preserves process modes,
kinematics, contact exposure, consumable health, utility topology, cumulative
removal, units, and uncertainty.

## 1. Why the prior model is withdrawn

The prior proposal used one scalar contact pressure, an incorrect effective
radius/speed relation, linear consumable ages, an algebraic MRR, and a direct
UPW multiplier. It omitted:

- same-direction dual-axis kinematics and center offset;
- the difference between local average of pressure-times-speed and the
  product of mean pressure and mean speed;
- preparation, polish, dressing, hold, and recovery modes;
- reversible pad glazing versus irreversible pad wear;
- dresser effectiveness;
- slurry delivery dynamics;
- interface temperature and frictional heating;
- cumulative thickness removal and stage-average MRR;
- explicit UPW connection topology;
- the native-unit boundary between PHM and the SI simulator;
- structural zero-coupling cases; and
- uncertainty in model form.

Those omissions would make the desired causal-control result mostly an artifact
of selected multipliers.

## 2. Two models, not one

The project needs two linked but non-interchangeable evidence planes.

### 2.1 SI simulation model

The simulation model uses Pa, m/s, m3/s, K, s, and m. It creates synthetic
instantaneous MRR, cumulative removed thickness, process states, and control
outcomes. Its parameters are literature-supported, engineering
approximations, or synthetic assumptions. It is not calibrated by pretending
scaled PHM signals are SI measurements.

### 2.2 PHM virtual-metrology model

The PHM model predicts the original stage-average target in its native numeric
unit. Later literature reports nm/min, but the original source does not state
the target unit. Process columns remain scaled proprietary values. Physics
enters through dimensionless, stage-aware features and train-only calibrated
coefficients.

The simulator and PHM model may share equation structure, feature names, and
qualitative signs. They may not share numerical coefficients without an
explicit calibration bridge.

## 3. CMP process state machine

The CMP subsystem should have explicit modes:

\[
\mathcal{M}\in
\{\mathrm{IDLE},\mathrm{PREPARE},\mathrm{POLISH},
\mathrm{DRESS},\mathrm{HOLD},\mathrm{RECOVER},\mathrm{COMPLETE}\}.
\]

Only POLISH accumulates wafer material removal. DRESS updates pad and dresser
states. HOLD stops removal and retains an auditable reason. RECOVER requires
valid utilities, sensors, and dwell conditions before POLISH resumes.

Define the polish indicator:

\[
\chi_p(t)=
\begin{cases}
1,&\mathcal{M}(t)=\mathrm{POLISH}\\
0,&\text{otherwise}.
\end{cases}
\]

Every MRR equation is multiplied by \(\chi_p\). This prevents preparation,
dressing, and cleaning rows from being treated as active removal.

## 4. Contact pressure and kinematics

### 4.1 Pressure state

The basic simulator uses actual mean contact pressure as a dynamic state:

\[
\frac{dP_c}{dt}
=\operatorname{clip}
\left(
\frac{P_{\mathrm{cmd}}-P_c}{\tau_P},
-\dot P_{\max}^{-},\dot P_{\max}^{+}
\right).
\]

The command, state, and bounds are in Pa. A multi-zone extension may use
carrier-zone pressures \(P_j\) and normalized spatial basis functions
\(w_j(r)\):

\[
p(r,t)=\sum_j w_j(r)P_j(t),\qquad
\frac{1}{A}\int_A p(r,t)\,dA=P_c(t).
\]

PHM air-bag and chamber columns are scaled signals. They can support a learned
effective-load proxy, but none may be declared equal to \(P_c\) in Pa.

### 4.2 Relative velocity field

For a rotary platen and wafer with fixed center offset \(r_{cc}\), local radius
\(r\), polar angle \(\theta\), platen speed \(\omega_p\), and wafer speed
\(\omega_w\), the relative-speed magnitude is:

\[
v_R(r,\theta)=
\sqrt{
\omega_p^2r_{cc}^2
+(\omega_p-\omega_w)^2r^2
+2\omega_p(\omega_p-\omega_w)r_{cc}r\cos\theta
}.
\]

The signs of the angular speeds encode rotation direction. Same-direction
rotation therefore does not justify adding speed magnitudes.

The area-mean velocity is:

\[
\overline v_R=
\frac{1}{\pi R_w^2}
\int_0^{R_w}\int_0^{2\pi}
v_R(r,\theta)\,r\,d\theta\,dr.
\]

The implementation should use deterministic quadrature with convergence
tests. A DIRECT_EFFECTIVE_VELOCITY mode may accept \(\overline v_R\) as an
input when geometry is unavailable; it must not invent an effective radius.

### 4.3 Pressure-velocity exposure

The removal driver is an area average:

\[
\Phi_{PV}=
\frac{1}{A}
\int_A
\left(\frac{p(r)}{P_0}\right)^\alpha
\left(\frac{v_R(r)}{V_0}\right)^\beta dA.
\]

In general,
\[
\mathbb{E}[p^\alpha v^\beta]
\ne
\mathbb{E}[p]^\alpha\mathbb{E}[v]^\beta.
\]

The scalar model may use uniform \(p\) but must retain the exposure definition.
The optional annular values are a simulated spatial proxy and must carry the
mandatory WIWNU disclaimer.

## 5. Consumable health states

At minimum, three bounded states are required:

- \(g_p\in[0,1]\): reversible pad-surface activity or glazing state;
- \(\ell_p\in[0,1]\): irreversible remaining pad-life proxy; and
- \(h_d\in[0,1]\): dresser effectiveness.

A bounded reduced-order model is:

\[
\frac{dg_p}{dt}
=-\chi_p k_g\Phi_{PV}g_p
+\chi_d k_c a_d h_d(1-g_p),
\]

\[
\frac{d\ell_p}{dt}
=-\chi_p k_{wp}\Phi_{PV}
-\chi_d k_{wd}a_d,
\]

\[
\frac{dh_d}{dt}
=-\chi_d k_d a_d h_d,
\]

where \(\chi_d=1\) in DRESS mode and \(a_d\in[0,1]\) is realized dressing
availability. Projection keeps all states inside [0,1].

This separates:

- glazing during polishing;
- restoration of surface activity during dressing;
- permanent pad consumption caused by polishing and dressing; and
- deterioration of the dresser itself.

The pad MRR modifier can be:

\[
m_{\mathrm{pad}}
=m_{p,\min}
+\left(1-m_{p,\min}\right)
g_p\,\ell_p^{\gamma_p}.
\]

All default rates remain synthetic until calibrated. The model structure is
supported by pad-wear, glazing, and conditioning literature.

## 6. Slurry and thermal states

### 6.1 Slurry availability

Three PHM slurry lines must remain separate because they represent different
slurry types and have different scales. The simulator uses a recipe-selected
slurry command and a bounded realized availability \(a_s\):

\[
\tau_s\frac{da_s}{dt}
=a_s^*(Q_{s,\mathrm{cmd}},a_u)-a_s,
\qquad a_s\in[0,1].
\]

Here \(a_u\) is a utility availability only when the configured tool topology
states that UPW supports slurry delivery or dilution. Otherwise \(a_u=1\) and
UPW has no slurry-path effect.

A bounded modifier is:

\[
m_s=\operatorname{clip}(a_s^{\gamma_s},m_{s,\min},m_{s,\max}).
\]

### 6.2 Interface temperature

UPW temperature is not assumed equal to the pad-wafer interface temperature.
A reduced energy balance is:

\[
C_i\frac{dT_i}{dt}
=\eta_f\mu A_cP_c\overline v_R
-U A_T(T_i-T_c)
-\rho_s c_{p,s}Q_s(T_i-T_s).
\]

The terms are frictional heat, coolant heat removal, and slurry heat
transport. \(T_c\) equals UPW temperature only for a configured thermal-loop
topology.

A material-profile-specific modifier is:

\[
m_T=\operatorname{clip}
\left(
\exp[\beta_T(T_i-T_0)],
m_{T,\min},m_{T,\max}
\right).
\]

\(\beta_T=0\) is a required structural null case. A positive value may be used
for a named synthetic material profile and compared against zero and bounded
mismatch cases. PHM cannot calibrate this term because it has no temperature
signal.

## 7. Instantaneous, cumulative, and average removal

Use a normalized generalized Preston baseline:

\[
R_{\mathrm{eq}}(t)
=\chi_p R_{0,s}
\Phi_{PV}(t)
m_s(t)m_T(t)m_{\mathrm{pad}}(t)m_{\mathrm{recipe}}(t),
\]

where \(R_{0,s}\) is a stage/recipe reference MRR in m/s. Normalization avoids
changing the units of a Preston coefficient when \(\alpha\) and \(\beta\) are
not one.

Required comparisons:

1. classical Preston: \(\alpha=\beta=1\);
2. generalized Preston: bounded \(\alpha,\beta\);
3. Preston plus consumable states;
4. Preston plus consumable and utility-interface states; and
5. physics plus learned residual.

If model discrepancy is included:

\[
R_{\mathrm{true}}=
\operatorname{clip}
\left(R_{\mathrm{eq}}+\epsilon_{\mathrm{proc}},0,R_{\max}\right),
\]

where the seeded process discrepancy is logged and is never visible online.
No arbitrary MRR lag is needed if pressure, slurry, thermal, and consumable
states already provide dynamics.

Cumulative removal and active time are:

\[
\frac{dH}{dt}=R_{\mathrm{true}},\qquad
\frac{dt_p}{dt}=\chi_p,
\qquad
\overline R(t)=\frac{H(t)}{\max(t_p,\varepsilon)}.
\]

This creates three distinct outputs:

- instantaneous simulated MRR \(R_{\mathrm{true}}\);
- cumulative simulated removal \(H\); and
- stage-average simulated MRR \(\overline R\).

The PHM target is analogous only to the third quantity and remains in the
public dataset's native unit.

## 8. Explicit UPW-to-CMP topology

The coupler must not output a generic MRR multiplier. It outputs typed boundary
conditions for a declared connection topology.

### Topology A: dressing-water support

\[
a_d=f_P(P_{\mathrm{UPW}})f_Q(Q_{\mathrm{UPW}}).
\]

UPW disturbance changes conditioning effectiveness, then pad surface activity,
then subsequent-polish MRR. This is the recommended primary topology because
the PHM data contain dressing-water status and the physical pathway is
explicit. It remains simulator-only because no UPW pressure/flow is measured.

### Topology B: thermal loop

\[
T_c=T_{\mathrm{UPW}},\qquad
UA=UA_0 f_Q(Q_{\mathrm{UPW}}).
\]

UPW affects interface temperature through the energy balance, not through a
direct MRR coefficient.

### Topology C: slurry-delivery support

\[
a_u=f_P(P_{\mathrm{UPW}})f_Q(Q_{\mathrm{UPW}}).
\]

This topology is allowed only as an explicitly synthetic tool configuration.
It must not be described as a property of the PHM tool or a generic fab.

### Topology D: no CMP connection

All UPW-to-CMP paths are disabled. The plant may show a UPW disturbance but no
MRR response. This negative control is mandatory.

The topology identifier and every parameter must be in the run manifest.

## 9. Revised utility plant needed by the coupler

A speed-scaled pump curve should replace independent imposed flow and head:

\[
\Delta P_p(Q,n)
=n^2H_{\mathrm{shut},0}
-k_QQ^2,
\qquad n=\omega/\omega_0.
\]

More generally, homologous scaling is:

\[
H(Q,n)=n^2H_0(Q/n).
\]

The network operating point follows the pump curve and the conserved hydraulic
balance. An explicit pressure relief/bypass prevents clipping from destroying
mass. Hydraulic power is:

\[
P_h=\frac{Q\Delta P}{\eta_p}.
\]

The cube law remains a homologous-point check, not an independent output
constraint at every network state.

## 10. PHM physics-informed virtual metrology

Because PHM variables are scaled, the public physics baseline must be in native
target units:

\[
\widehat y_{\mathrm{physics}}
=c_s+a_s\phi_{\mathrm{PV}}(z)
+b_s^\top\phi_{\mathrm{consumable}}(z),
\]

where:

- \(z\) contains phase-specific, time-weighted scaled signals;
- \(\phi_{\mathrm{PV}}\) is a dimensionless pressure/speed exposure proxy;
- \(\phi_{\mathrm{consumable}}\) contains pad/dresser usage and conditioning
  features;
- all coefficients are fit only on training groups; and
- \(s\) denotes stage or an input-derived process regime.

The hybrid model is:

\[
\widehat y
=\widehat y_{\mathrm{physics}}+f_\theta(x),
\]

with the residual learner fit to training residuals only. It is not:

\[
\text{SI simulator MRR}+f_\theta(\text{PHM scaled signals}).
\]

Required baselines are mean, stage mean, linear, ridge, generalized-Preston
proxy, tree ensemble, and physics-plus-residual.

## 11. PHM preprocessing and evaluation

### 11.1 Phase-aware features

For time-weighted signal mean:

\[
\overline x_w
=\frac{\sum_i x_i\Delta t_i}
{\sum_i\Delta t_i}.
\]

Long discontinuities are segmented, not allowed to dominate a duration.
Features should include:

- preparation/ramp duration;
- active-polish duration;
- ending duration;
- phase-specific mean, variance, extrema, slopes, and integrals;
- fractions of missing, zero, duplicated, and discontinuous samples;
- pressure-zone contrasts;
- slurry-line-specific availability;
- speed-exposure proxies;
- dressing-water duty;
- pad/dresser usage and interaction features; and
- machine/chamber/regime identifiers used cautiously.

Complete-trace features are allowed for offline virtual metrology only.
Streaming warning features use observations arrived by each decision cutoff.

### 11.2 Split hierarchy

1. Official training data for fitting/development.
2. Official test answers for one offline holdout.
3. Official validation answers for the final public holdout.
4. Grouped inner folds by wafer.
5. Temporal-block and machine-held-out stress evaluations.
6. Stage-separated and mixed-stage reports.

No preprocessing threshold, imputer, scaler, feature selector, model
hyperparameter, or physics coefficient may use official holdout labels.

### 11.3 Label anomaly policy

Report three preregistered training treatments:

- original labels;
- four labels excluded as anomalies; and
- four labels hypothetically divided by 60.

The original-label result is primary unless authoritative source evidence
supports a correction. Robust losses and metrics supplement, but do not
replace, MAE/RMSE/R2 reporting.

## 12. Early warning and control target

Instantaneous MRR deviation alone is insufficient. Define:

\[
e_R(t)=\frac{R_{\mathrm{true}}(t)-R_{0,s}}{R_{0,s}},
\]

\[
e_H(t)=H(t)+\widehat H_{\mathrm{remaining}}(t)-H_{\mathrm{target}}.
\]

The warning event is:

> Within horizon H, will persistent active-polish MRR leave its configured
> envelope, or will predicted final cumulative removal leave its target
> tolerance?

H must exceed sensing, actuation, and dominant plant delays. Short hydraulic
and longer conditioning/thermal horizons may be modelled separately.

Hold intervals do not count as zero-MRR success. Evaluation separately reports:

- MRR deviation while polishing is active;
- cumulative-removal error;
- hold duration;
- recovery time;
- throughput/time penalty; and
- action effort.

## 13. Uncertainty and identifiability

Three uncertainty layers are required:

1. Predictive residual uncertainty, calibrated on grouped calibration data.
2. Parameter uncertainty for engineering and synthetic coefficients.
3. Structural uncertainty across Preston/generalized forms and UPW topologies,
   including no connection.

Recommended implementation:

- grouped split-conformal prediction intervals for public VM;
- bootstrapped grouped models for epistemic spread;
- deterministic parameter ensembles or Sobol designs for simulator
  sensitivity; and
- high-uncertainty safety rejection/hold behavior.

Every utility coupling range must include zero link strength unless a real tool
topology establishes that the connection exists. Temperature studies include
\(\beta_T=0\). Control success must remain qualified if it disappears under
weak or null coupling.

## 14. Validation matrix

### Units and limiting cases

- inactive process, zero pressure, or zero relative speed gives zero MRR;
- all nominal states give \(R_{0,s}\);
- cumulative removal is non-decreasing only during active polish;
- pad remaining life and dresser health never increase;
- dressing can restore surface activity but not remaining pad life;
- no-connection topology gives no UPW-induced MRR change;
- no spatial output lacks the mandatory proxy label.

### Dynamics and conservation

- pump/system operating point satisfies the pump curve;
- hydraulic mass-balance residual is within numerical tolerance;
- pump-trip pressure decays through compliance;
- thermal energy residual is audited;
- event and process transitions use integer step boundaries;
- dt, dt/2, and dt/4 traces converge under declared tolerances.

### Data and leakage

- PHM native units and hidden scaling are explicit;
- phase segmentation never uses MRR labels;
- full-trace features cannot enter streaming prediction;
- official holdout labels are isolated;
- wafer, time, and machine overlaps are audited;
- all outlier policies are reported.

### Control and safety

- healthy UPS is a negative-control scenario;
- all controllers see identical exogenous traces and observations;
- actions take effect no earlier than the next step;
- sensor arrivals never precede source generation;
- no final action violates the frozen envelope;
- hold cannot trivially win without time/throughput penalty.

## 15. Recommended scenario suite

1. Healthy UPS, 25 percent sag, 400 ms: expected small downstream response.
2. Degraded UPS transfer or overload: electrical-to-pump transient.
3. Pump trip: hydraulic recovery and hold/resume.
4. Valve restriction: demand-side pressure/flow event.
5. Tool-demand spike: shared-header disturbance.
6. Dressing-window sag under topology A: incomplete conditioning and next
   wafer MRR risk.
7. Thermal-loop disturbance under topology B.
8. Synthetic slurry-support disturbance under topology C.
9. No-connection topology D negative control.
10. Compound electrical plus demand event.

The primary control-efficacy scenario should be selected before controller
tuning and should not be chosen solely because it produces the largest gain.

## 16. Implementation order after remediation

1. Correct schema/interface/configuration contracts.
2. Correct PHM semantic pipeline and reports.
3. Correct pump/UPW conservation and timing.
4. Correct sensor/scenario causality and validation.
5. Implement CMP process modes and kinematics.
6. Implement consumable, slurry, thermal, and cumulative-removal states.
7. Implement typed utility topology and negative controls.
8. Validate sensitivity and identifiability.
9. Implement public physics baseline and residual models.
10. Freeze warning, controller, and safety objectives.

## 17. Sources supporting the redesign

- Preston, The Theory and Design of Plate Glass Polishing Machines, 1927.
- Tseng and Wang, pressure and speed dependences:
  https://doi.org/10.1149/1.1837417
- Tseng, relative-velocity roles:
  https://doi.org/10.1149/1.1391872
- Lee and Jeong, wafer-scale MRR profile:
  https://doi.org/10.1016/j.ijmachtools.2011.01.007
- Fu et al., pad/slurry/contact model:
  https://doi.org/10.1109/66.964328
- Borucki, polish-rate decay:
  https://doi.org/10.1023/A:1020305108358
- Chang et al., CMP conditioning:
  https://doi.org/10.1016/j.mee.2006.11.011
- Kim et al., friction and thermal phenomena:
  https://doi.org/10.1016/S0924-0136(02)00820-8
- Lin and Wu, parameter experiments:
  https://doi.org/10.1016/S0890-6955(01)00089-X
- Yu et al., physics-informed MRR prediction:
  https://doi.org/10.1016/j.wear.2019.02.012
- Rahman et al., physics-informed multi-task PHM modelling:
  https://doi.org/10.1109/ICPHM61352.2024.10627679
- Li et al., challenge-specific phases and run types:
  https://doi.org/10.2991/iceea-18.2018.26

## 18. Approval disposition

The user approved this report as the controlled design basis on 2026-07-11.
The prior direct-modifier decision remains withdrawn and the four Phase 1/2
remediation gates are open in order. Approval authorizes controlled impact
analysis and implementation; it does not freeze numerical parameters, waive
acceptance tests, or reactivate T-WP08 before R1--R4 pass.
