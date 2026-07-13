# Predictive Supervisory Control of CMP Under Electrical and UPW Disturbances

**Living research paper draft**  
Status: corrective R1--R4, synthetic CMP WP08, declared-topology WP10 coupling, and synthetic WP12 early-warning validation complete; public virtual metrology, attribution, control, and safety results pending<br>
Last updated: 2026-07-13

> This document is maintained throughout implementation and will become the basis of the final technical paper. Every result must link to a reproducible artifact, configuration, code path, and provenance record. Missing evidence is recorded as pending rather than inferred.

## Abstract (draft)

Chemical Mechanical Planarization (CMP) is sensitive to process, consumable,
and utility variation. This work develops a simulation-first proof of concept
for predictive supervisory control of CMP under electrical and ultrapure-water
(UPW) disturbances. The planned causal chain is electrical disturbance →
UPS/VFD response → motor and pump response → UPW pressure/flow/thermal response
→ explicitly configured CMP boundary condition → material-removal-rate (MRR)
excursion → early warning → root-cause attribution → safety-filtered
intervention. The primary measured target is average MRR; the control comparison
will use a deterministic simulator against no-action and fixed-threshold
baselines. The PHM 2016 CMP archive has been locally supplied,
integrity-checked, selectively extracted, and raw-schema audited. A
retrospective scientific audit found that native-unit handling, PHM semantics,
pump/network conservation, observation timing, and scenario validation required
correction before integration. Native-unit contracts and phase-aware,
time-weighted PHM preprocessing, conserved pump/network physics, UPS
energy/frequency states, causal observation delivery, and executable scenario
semantics now pass their corrective gates. The previous direct UPW-to-MRR
multiplier was withdrawn. A reduced-order CMP subsystem with explicit modes,
signed rotary kinematics, dynamic pressure/spindles/slurry, consumable health,
interface energy balance, and cumulative removal now passes its synthetic
scientific and regression gates. A stateless typed coupler now implements
no-connection, dressing-water, thermal-loop, and explicitly synthetic
slurry-support structures. The healthy-UPS 25%/400 ms sag remains an exact
coupling negative control. A separately declared synthetic degraded-UPS
interruption during DRESS propagates through pump/UPW loss into reduced stored
pad activity and a 3.19% reduction in later simulated MRR relative to the
identical no-connection run. Structural, local, global, and mismatch analyses
show that this effect is contingent on synthetic topology and coefficients.
For a separately frozen early-warning experiment, a paired event-disabled
reference defines a ±5% active-POLISH trajectory envelope, 0.25 s persistence,
and a 3 s horizon. On 24 held-out synthetic runs containing only three
independent events, logistic regression achieved PR-AUC 0.9904, detected 3/3
events with 2.71 s median lead, and produced one false-alarm episode; a frozen
gradient-boosted model also detected 3/3 events with PR-AUC 0.9130. These
primary results do not generalize safely: both models alarm severely under an
explicit no-connection topology, and high sensor noise degrades discrimination,
specificity, and uncertainty coverage. No predictive-control efficacy,
real-fab, defect, yield, equipment, or production-control claim is made.

## 1. Research question and scope

**Research question.** Can a predictive supervisory-control layer detect an upcoming CMP process excursion caused by simulated electrical and UPW disturbances, and reduce that excursion relative to no intervention and fixed-threshold control without violating predefined simulation safety constraints?

The primary target is average material-removal rate:

\[
\widehat{MRR}.
\]

Permitted derived outputs include excursion probability, under/over-polish risk proxies, hold requirement, and synthetic spatial-uniformity proxies. Any spatial result must be labelled: **“Simulated spatial-uniformity proxy; not experimentally validated WIWNU.”**

This paper will not claim validated prediction or prevention of scratches, dishing, erosion, corrosion, particle contamination, delamination, cracking, real wafer-yield loss, real equipment damage, real production control, or microsecond production response.

## 2. Planned contributions

1. A typed, provenance-aware CMP/utility data contract that separates measured output, simulated state, observed sensors, excursions, risk proxies, defects, and yield outcomes.
2. A deterministic simulator that exposes the declared electrical → UPS/VFD → pump → UPW → CMP/MRR propagation chain.
3. A leakage-safe PHM CMP virtual-metrology pipeline with grouped splits and explicit empty-trace handling.
4. Early-warning and root-cause methods evaluated against simulator labels without describing feature attribution as causal proof.
5. Baseline and predictive supervisory controllers evaluated under an independent safety filter.
6. Reproducible paired scenario evidence comparing no action, threshold control, and predictive control.

## 3. Data and provenance

### 3.1 PHM CMP archive

The user supplied `PHM-Data-Challenge-master.zip` locally. Archive evidence:

- compressed size: 17,399,074 bytes;
- uncompressed size: 203,033,011 bytes;
- SHA-256: `976b23102b576ed610db8f89293de333820391c581d88bcbdb6364da212a1eb9`;
- ZIP integrity: all members passed CRC testing;
- selected original members: 558 (185 training, 185 test, 185 validation time-series files and three removal-rate tables);
- header-only time-series files retained: 58, represented as `empty_trace: true` with no imputation;
- answer tables and derived experiments excluded from extracted raw data.

The bundled repository `LICENSE` is MIT-licensed, but a separate licence for the embedded PHM dataset is not stated. The user explicitly authorized local research use despite that caveat. This authorization is recorded in [`data_sources.yaml`](../orchestration/data_sources.yaml) and the extraction manifest. Public redistribution and licence claims remain out of scope.

The official PHM challenge page describes the average-removal-rate objective and original CMP filename patterns: [PHM Society 2016 CMP challenge](https://phmsociety.org/conference/annual-conference-of-the-phm-society/annual-conference-of-the-prognostics-and-health-management-society-2016/phm-data-challenge-4/).

### 3.2 Data pipeline evidence

The loader validates the extraction manifest, per-file size and SHA-256, exact 25-column time-series headers, three-column removal-rate headers, trace counts, identifier presence, duplicate label keys, and train-only many-to-one label joins. Test and validation labels remain separate for offline evaluation and are not joined into training features.

R2 additionally preserves source row order, segments discontinuities, applies
centered time-support weights, derives input-only process-mode proxies, and
keeps targets separate until audited one-to-one joins. The processed bundle has
1,981 training, 424 test, and 424 validation wafer/stage records, each with 405
target-free predictor columns. All three joins have zero missing and zero orphan
keys. Complete-trace features are explicitly offline-only.

Current audits: [`phm_missingness.json`](../reports/data/phm_missingness.json),
[`phm_semantic_audit.json`](../reports/data/phm_semantic_audit.json), and
[`feature_manifest.yaml`](../data/processed/phm_2016_cmp/feature_manifest.yaml).

### 3.3 Semantics discovered by retrospective audit

The original challenge states that the process columns are scaled using
hidden factors. It does not explicitly declare the MRR target unit. A later
NIST-affiliated study reports MRR in nm/min; this is retained as a literature
interpretation rather than treated as an original-source unit declaration.
Consequently, PHM virtual metrology remains in the original target's native
numeric unit, while the synthetic simulator uses SI units. No numerical
coefficient may cross that boundary without a separately documented
calibration bridge.

Challenge-specific research describes preparation, main polishing, ending,
and post-CMP cleaning phases. R2 deliberately avoids claiming measured phase
labels: it derives five input-only process-mode proxies. Source-order continuity
segments break at trace boundaries, non-positive increments, and gaps above
10 s. Within each segment, the supported duration of row \(i\) is

\[
w_i=\tfrac{1}{2}\Delta t_{i-1}^{+}
   +\tfrac{1}{2}\Delta t_{i+1}^{+}.
\]

This prevents duplicate timestamps, reversals, or long gaps from receiving or
bridging fictitious duration. The audit retained three negative increments in
training, two in validation, 2,907 zero increments, and 2,855 long gaps. It
found 221/43/42 unresolved wafer/stage groups in training/test/validation.

Four training targets lie between 4,129.494 and 4,326.154, whereas all other
training targets are at most approximately 163 and the test/validation maxima
are below 164. Dividing only those four values by 60 gives 68.825--72.103, but
there is no authoritative basis to perform that correction silently. The
preregistered policy is therefore:

1. retain original labels for the primary result;
2. report a sensitivity excluding the four labels; and
3. report an explicitly hypothetical sensitivity dividing only the four by
   60.

No treatment may be selected from official holdout performance. All three
treatments are materialized without changing raw labels. Official training is
fit/tuning-only, test is an offline holdout, and validation is the final public
holdout; inner folds retain whole wafers and chronological blocks. A physical
machine holdout is infeasible because all records use machine ID 2.
`MACHINE_DATA` changes within nearly every wafer/stage group and cannot support
a machine- or stable-regime-generalization claim. The full decision and
validation evidence are in
[`r2_phm_semantics.md`](../orchestration/decisions/r2_phm_semantics.md) and
[`r2_phm_semantics_validation.md`](../orchestration/reports/r2_phm_semantics_validation.md).

## 4. System architecture and runtime

The runtime follows this ordered update sequence:

1. scenario disturbance;
2. electrical and UPS state;
3. VFD/motor state;
4. pump state;
5. UPW hydraulic/thermal state;
6. utility-to-CMP coupling;
7. true CMP state and MRR;
8. observed sensor generation;
9. streaming features;
10. prediction and uncertainty;
11. root-cause estimate;
12. controller proposal;
13. independent safety filter;
14. approved action and audit log.

Online consumers may see observations available by the decision timestamp, prior predictions/actions, and validated static configuration. They may not see latent truth, future observations, offline excursion labels, or simulator cause labels.

R4 defines three clocks:

\[
t_{source}=t_k,\qquad
t_{reported}=\max(0,t_{source}+\epsilon_{clock}),\qquad
t_{arrival}=t_{source}+d_{comm}.
\]

Reported jitter does not alter source or arrival. Generated observations are
queued, and the online set at decision time \(t_d\) contains only records with
\(t_{arrival}\le t_d\). Declarative initiating causes are separate from
propagation states such as UPS transfer and VFD derating.

## 5. Mathematical model (utility plant and standalone CMP validated synthetically)

### 5.1 Two evidence planes

The SI simulator and PHM virtual-metrology model share qualitative structure,
not numerical calibration. The simulator uses Pa, m/s, m³/s, K, s, and m. The
public model predicts the PHM stage-average target in its unconverted native
numeric unit using dimensionless proxies fitted on training groups only. An SI
physics prediction must never be added directly to a residual learned from
scaled PHM signals.

### 5.2 CMP modes and contact exposure

The implemented CMP state machine contains IDLE, PREPARE, POLISH, DRESS, HOLD,
RECOVER, and COMPLETE. With \(\chi_p=1\) only in POLISH, all material-removal
equations are gated by \(\chi_p\). Contact pressure follows a slew-bounded
first-order response. For platen angular speed \(\omega_p\), wafer angular
speed \(\omega_w\), center offset \(r_{cc}\), and local wafer coordinates
\((r,\theta)\), the relative-speed magnitude is

\[
v_R(r,\theta)=
\sqrt{\omega_p^2r_{cc}^2
+(\omega_p-\omega_w)^2r^2
+2\omega_p(\omega_p-\omega_w)r_{cc}r\cos\theta}.
\]

The signs of angular speeds encode direction; same-direction rotation does not
justify adding speed magnitudes. The generalized pressure--velocity exposure
is an area integral,

\[
\Phi_{PV}=\frac{1}{A}\int_A
\left(\frac{p(r)}{P_0}\right)^\alpha
\left(\frac{v_R(r)}{V_0}\right)^\beta dA,
\]

because the average of local pressure--speed exposure is not generally the
product of the separate averages. Deterministic quadrature and convergence
tests pass. Any annular output remains a **simulated
spatial-uniformity proxy; not experimentally validated WIWNU**.

### 5.3 Consumables, slurry, thermal state, and removal

The minimum consumable state contains reversible pad-surface activity
\(g_p\), irreversible remaining pad-life proxy \(\ell_p\), and dresser
effectiveness \(h_d\), each bounded in \([0,1]\):

\[
\dot g_p=-\chi_p k_g\Phi_{PV}g_p
+\chi_d k_c a_d h_d(1-g_p),
\]

\[
\dot\ell_p=-\chi_p k_{wp}\Phi_{PV}-\chi_d k_{wd}a_d,
\qquad
\dot h_d=-\chi_d k_d a_dh_d.
\]

Dressing can restore surface activity but cannot restore remaining pad life.
A bounded slurry-availability state preserves recipe-selected slurry lines.
The interface temperature \(T_i\) is distinct from UPW temperature and follows
the reduced energy balance

\[
C_i\dot T_i=\eta_f\mu A_cP_c\overline v_R
-UA_T(T_i-T_c)-\rho_sc_{p,s}Q_s(T_i-T_s).
\]

The implemented normalized generalized-Preston equivalent removal rate is

\[
R_{eq}=\chi_p R_{0,s}\Phi_{PV}
m_s m_T m_{pad}m_{recipe},
\]

with all modifiers dimensionless and bounded. Cumulative removal and active
polish time are explicit states:

\[
\dot H=R_{true},\qquad \dot t_p=\chi_p,\qquad
\overline R=H/\max(t_p,\varepsilon).
\]

This separates instantaneous simulated MRR, cumulative simulated removed
thickness, and stage-average simulated MRR. It also prevents a controller from
appearing successful merely by holding the process and reporting zero
instantaneous removal.

The frozen nominal power-mean velocity is 1.6070416183328249 m/s. At 30 kPa
and 8/6 rad/s platen/head speeds, nominal exposure is one and
\(R_0=1.6666666666667\times10^{-9}\) m/s (100 nm/min). The classical derived
coefficient is \(3.4570078908840606\times10^{-14}\) Pa⁻¹. A deterministic
1 s PREPARE, 5 s POLISH, 1 s HOLD trace accumulates 8.276153498157771 nm only
during POLISH. Its maximum absolute thermal-energy residual is
\(1.4188941577231162\times10^{-8}\) W. With the default
\(\beta_T=0\), coolant-temperature differences affect interface temperature
but have exactly zero MRR effect. These results validate the declared
synthetic structure and numerics, not a real CMP recipe.

### 5.4 Utility connection topology

The implemented coupler outputs typed boundary conditions for a declared tool
topology, not a generic MRR multiplier. The structures are:

- dressing-water support, where UPW availability changes conditioning and
  therefore later pad surface activity;
- a thermal loop, where UPW affects coolant temperature/conductance in the
  interface energy balance;
- an explicitly synthetic slurry-delivery support topology; and
- no CMP connection, which is a mandatory structural negative control.

Every structural ensemble includes zero link strength unless real tool
plumbing establishes otherwise. The R3-validated healthy-UPS 25 percent,
400 ms sag is a negative control: it changes tool flow by zero and supply
pressure by at most 1.119 kPa (0.373% nominal). It must not be converted into a
large excursion by tuning a gain.

For normalized pressure (p=P_s/P_{ref}), flow (q=Q_t/Q_{ref}), and bounded
ramp (R),

\[
a_h=\min\{R(p;p_0,p_1),R(q;q_0,q_1)\},
\qquad a_{eff}=1-\lambda(1-a_h).
\]

The minimum treats pressure and flow as correlated hydraulic indicators and
avoids multiplying the same disturbance twice. The function is an engineering
approximation; every numerical threshold/reference/link value is a synthetic
assumption. The thermal map separates neutral CMP and upstream references:

\[
T_c=T_{c,0}+\lambda(T_u-T_{u,ref}).
\]

Thus zero link is exactly neutral. The water-quality proxy has no CMP effect,
and the coupler cannot set process discrepancy or force a hold.

The local literature corpus supports qualitative water-conditioning,
pad-memory, slurry/rinse, and thermal pathways, but it does not establish the
PHM tool plumbing or calibrate header thresholds. The primary connected
experiment is therefore explicitly synthetic and acts only during DRESS. A
3 s interruption with a degraded 500 J UPS reduces end-of-DRESS pad activity
from 0.5511876609 to 0.5216572820. After utilities recover and POLISH begins,
mean simulated MRR is 9.8727270376e-10 rather than 1.0198314108e-9 m/s, a
3.1926% decrease. MRR is zero during DRESS, so the later change is mediated by
stored pad state. This is not real-tool calibration.

The full redesign basis, uncertainty layers, scenario matrix, and validation
requirements are recorded in
[`phase_3_cmp_model_redesign.md`](../orchestration/reports/phase_3_cmp_model_redesign.md).
The CMP decision, equations, and evidence are now frozen in
[`wp08_cmp_physics.md`](../orchestration/decisions/wp08_cmp_physics.md),
[`mathematical_model.md`](mathematical_model.md), and
[`wp08_cmp_validation.md`](../orchestration/reports/wp08_cmp_validation.md).
The topology decision, literature review, equations, sensitivity, and traces
are recorded in
[`wp10_utility_cmp_coupling.md`](../orchestration/decisions/wp10_utility_cmp_coupling.md),
[`wp10_literature_review.md`](../orchestration/reports/wp10_literature_review.md),
and
[`wp10_coupling_validation.md`](../orchestration/reports/wp10_coupling_validation.md).

### 5.5 Validated synthetic utility plant

R3 implements a speed-scaled pump curve rather than independent flow and head:

\[
H_p(Q,n,d)=dH_{shut}n^2-k_QQ^2,
\qquad
k_Q=(H_{shut}-H_{ref})/Q_{ref}^2.
\]

Flow is solved at the current network differential pressure; a check valve
excludes reverse flow above shutoff head. The supply node solves

\[
\frac{C_h(P_s^{k+1}-P_s^k)}{\Delta t}
=Q_p^k-Q_t(P_s^{k+1})-Q_r(P_s^{k+1})-Q_{rel}(P_s^{k+1}),
\]

with explicit tool, return, relief, and storage terms and no pressure clip.
Every step checks the resulting discrete mass residual. Thermal flushing uses
pump inflow in a well-mixed energy balance. The former emitted S/m conductivity
proxy is replaced with a dimensionless synthetic deviation index.

UPS output frequency and battery energy/load are explicit. During
transfer/battery operation,

\[
E_b^{k+1}=E_b^k-P_L\Delta t/\eta_{inv};
\]

depletion or overload enters bypass rather than creating energy. The 10 ms
hydraulic solution differs from a 0.5 ms reference by 36.19 Pa (0.0121% of
nominal) for the preregistered 0.70-pu speed test. Pump-trip pressure decays
from 300 to 290.244 kPa on the first step and monotonically thereafter;
generated balance residuals stay below \(1.0\times10^{-12}\) m³/s. These are
synthetic numerical-validation results, not real-equipment calibration. Full
evidence is in
[`r3_plant_physics_validation.md`](../orchestration/reports/r3_plant_physics_validation.md).

## 6. Models and supervisory methods

### 6.1 Public-data virtual metrology (pending)

The WP09 PHM comparison remains pending. Its frozen candidate families are a
training-target mean, linear and ridge regression, a dimensionally compatible
native-unit physics-inspired baseline, a tree ensemble, and a
physics-plus-residual model. Training transformations must stay inside grouped
folds, and no SI simulator coefficient may be added to the source-undeclared
PHM target unit.

### 6.2 WP12 synthetic early-warning target

WP12 is complete for one preregistered simulator target. Let $R_k$ be the
disturbed true simulated instantaneous average MRR and $R_k^{ref}$ the paired
event-disabled reference at the same step. The reference uses the same initial
state, schedule, topology, and static plant parameters; only the initiating
event is disabled. The point-violation indicator is

\[
v_k = \mathbf{1}[m_k=\mathrm{POLISH}]
      \mathbf{1}[R_k^{ref}>10^{-12}\ \mathrm{m/s}]
      \mathbf{1}[R_k<0.95R_k^{ref}\ \lor\ R_k>1.05R_k^{ref}].
\]

At the 0.01 s simulator step, an event requires

\[
n_p=\left\lceil\frac{0.25\ \mathrm{s}}{0.01\ \mathrm{s}}\right\rceil=25
\]

consecutive active-POLISH violating intervals. Its stored onset is the first
interval of the subsequently persistent departure. This mode gate prevents
zero MRR during DRESS, PREPARE, HOLD, RECOVER, IDLE, or COMPLETE from becoming
an under-polish event.

At eligible 0.10 s decision time $t_d$, with horizon $H=3.0$ s,

\[
y(t_d)=\mathbf{1}[t_d<t_e\le t_d+H],
\]

where $t_e$ is the first accepted episode onset. The future-truth label is
created offline and is never a feature. Rows are censored, rather than labelled
negative, if the complete horizon is unavailable, the horizon lacks 0.25 s of
contiguous active POLISH, or an event has already begun.

### 6.3 Causal features, fitting roles, and uncertainty

Only observations satisfying

\[
t_{arrival}\le t_d,\qquad k_{source}\le k_d
\]

enter the 65-feature vector. The eight channels are grid voltage, UPS output
voltage, UPS battery energy, motor speed, pump flow, UPW supply pressure, tool
flow, and UPW temperature. Each normalized channel contributes the latest
value and age, 0.5 s mean/minimum/slope/missing fraction, and history minimum.
UPS output, pressure, and tool flow also use the causal history deficit

\[
D_j(t_d)=\int_0^{t_d}\max(0,0.95-z_j(t))\,dt.
\]

Known synthetic recipe schedule indicators and static battery/load ratios are
allowed configuration. MRR, latent pad activity, coupling availability, event
family/magnitude, initiating cause, and future truth are prohibited. Median
imputation and scaling are fitted on TRAIN only.

Whole runs are disjoint across TRAIN, sigmoid CALIBRATION, independent
CONFORMAL_CALIBRATION, and TEST. Their eligible/positive row counts are
2,988/84, 1,404/84, 1,404/84, and 1,932/84, respectively. The 84 positive TEST
rows arise from three event-bearing runs with 28 warning decisions each, not 84
independent events. The frozen models are a training-prevalence constant,
balanced logistic regression, and balanced histogram gradient boosting; TEST
does not tune hyperparameters or select a model for secondary analysis.

For calibrated probability \(\tilde p\), independent conformal rows use

\[
s_i=\begin{cases}1-\tilde p_i,&y_i=1,\\
\tilde p_i,&y_i=0,
\end{cases}
\]

and the nominal 90% finite-sample quantile is the
$\lceil(n_q+1)(1-0.10)\rceil$-th ordered score. Prediction sets may be empty
or contain both classes. Because rows within a run are dependent and severity
grids are fixed, coverage is an empirical row-level simulator diagnostic, not
a run-wise or real-world guarantee.

### 6.4 Held-out warning result and failure modes

| Metric | Prevalence | Logistic | Gradient boosted |
|---|---:|---:|---:|
| PR-AUC (TEST prevalence 0.04348) | 0.04348 | 0.99040 | 0.91304 |
| Precision | Undefined | 0.97500 | 0.91304 |
| Row recall | 0.00000 | 0.92857 | 1.00000 |
| Specificity | 1.00000 | 0.99892 | 0.99567 |
| Brier score | 0.04186 | 0.00321 | 0.00678 |
| Event recall | 0/3 | 3/3 | 3/3 |
| Median warning lead | Undefined | 2.71 s | 2.71 s |
| False-alarm episodes | 0 | 1 | 1 |
| Conformal coverage | 0.95652 | 0.92961 | 0.87733 |
| Empty-set fraction | 0.00000 | 0.07039 | 0.12267 |

Both learned models pass the frozen primary synthetic gate, but that gate has
no false-alarm acceptance threshold and only three independent events. One
false-alarm episode over 193.2 eligible simulated seconds equals 18.63 per
eligible simulated hour; this denominator is not a real-fab operating rate.
Whole-run bootstrap intervals resample the same 24 configured TEST runs and do
not create additional mechanisms.

The negative diagnostics are scientifically decisive. Under severe upstream
events with explicit `NO_CONNECTION`, no MRR event occurs, yet logistic and
gradient boosting raise 30 and 9 false-alarm episodes and achieve specificity
0.3371 and 0.2860. Under high synthetic noise, logistic PR-AUC/precision/
specificity/coverage are 0.6002/0.1019/0.0657/0.0959; gradient boosting yields
0.5283/0.5283/0.9053/0.7671. Thus the models frequently identify upstream
severity rather than proving a downstream CMP connection. They cannot be used
as topology-independent alarms. Complete equations, revisions, sensitivities,
and artifacts are in
[`wp12_early_warning_validation.md`](../orchestration/reports/wp12_early_warning_validation.md).

### 6.5 Attribution, controllers, and safety (pending)

WP13 attribution, WP14 baselines, the WP15 predictive supervisor, and the WP16
independent safety filter remain pending. Planned controllers are no action,
fixed threshold/hysteresis, safe hold, controlled resume, and bounded
predictive supervisory control. Reinforcement learning is excluded from this
PoC. The WP12 runner is open loop and proposes or applies no action.

## 7. Evaluation status and remaining plan

WP12 reports held-out row and event metrics, whole-run bootstrap intervals,
target-definition sensitivities, named noise/delay/dropout corruptions, an
unseen-compound diagnostic, and a structural no-connection diagnostic. These
are open-loop warning evaluations; amortized vectorized prediction timing is
not a controller or production-latency result.

All future controller comparisons will use identical scenarios, initial
states, parameter draws, observation corruptions, and seed maps. Remaining
metrics include public-data MRR MAE/RMSE/relative error/R² and interval
coverage; paired pressure/flow violations, MRR excursion, cumulative-removal
error, hold duration, recovery time, action magnitude, safety rejections,
attribution accuracy, and end-to-end runtime/controller latency.

Results will report mean, median, standard deviation, 5th percentile, 95th percentile, and worst case where applicable.

## 8. Results ledger

| Result | Evidence | Status |
|---|---|---|
| Archive integrity | `data/raw/phm_2016_cmp/extraction_manifest.yaml` | Verified |
| Original CMP member selection | 558 selected; answers/derived outputs excluded | Verified |
| Empty-trace handling | 58 explicit empty traces; no imputation | Verified |
| PHM raw schema and label join | `reports/data/phm_missingness.json`; raw-loader tests | Verified |
| Electrical/UPS response model | output voltage/frequency, load, energy, charge, depletion, overload, transfer/recovery | R3 validated synthetic behavior; no waveform/equipment claim |
| VFD/motor/pump response model | bounded drive plus speed-scaled pump curve and check-valve operating point | R3 validated synthetic behavior; no manufacturer calibration |
| UPW hydraulic/thermal/proxy model | implicit conserved compliance, explicit relief, pump-inflow thermal balance, dimensionless proxy | R3 validated synthetic behavior; no distributed hydraulics or measured chemistry claim |
| Sensor/communication model | source/reported/arrival clocks, queued exact-once delivery, deterministic corruption | R4 validated synthetic behavior; no physical network claim |
| Deterministic scenario engine | strict versioned mappings, executable profiles, bounded targets, interval/cause policy | R4 validated synthetic behavior; no measured fault-rate claim |
| Retrospective Phase 1/2 scientific audit | `orchestration/reports/phase_1_2_scientific_audit.md` | Complete; four corrective gates opened |
| R1 schema/interface/configuration correction | `orchestration/reports/r1_contract_configuration_validation.md`; 21 focused tests | Validated contract behavior; canonical schema and DynamicSubsystem frozen at 2.0.0 |
| R2 PHM semantic correction | `orchestration/reports/r2_phm_semantics_validation.md`; 13 focused + 6 real-data integration tests; 82/82 full suite | Validated preprocessing behavior; no public model-performance claim |
| R3 plant-physics correction | `orchestration/reports/r3_plant_physics_validation.md`; 52 focused tests; 94/94 full suite | Validated synthetic equations/invariants; no CMP or controller claim |
| R4 online/scenario timing correction | `orchestration/reports/r4_online_scenario_timing_validation.md`; 45 focused tests; 107/107 full suite | Validated causal software visibility and scenario semantics |
| Standalone reduced-order CMP physics | `orchestration/reports/wp08_cmp_validation.md`; 48 focused and 130/130 full tests | Validated synthetic equations/invariants; no real-tool calibration, utility propagation, or controller claim |
| Utility-to-CMP topology | `orchestration/reports/wp10_coupling_validation.md`; local/global/mismatch artifacts | Validated synthetic declared-topology behavior; no real-tool plumbing or calibration claim |
| Synthetic early-warning target and models | `orchestration/reports/wp12_early_warning_validation.md`; 16 focused and 170/170 full tests | Validated only on the named simulator ensemble; three independent TEST events; structural-null and high-noise failures prohibit topology-independent use |
| Public-data virtual-metrology accuracy | Future model evaluation artifact | Pending |
| Electrical → UPW → CMP causal propagation | `reports/sensitivity/wp10_positive_chain_trace.csv` | Validated only for the declared synthetic degraded-UPS/DRESS topology; no causal claim for a real fab |
| Early-warning performance | `reports/early_warning/wp12_validation.json`; TEST predictions and figures | Logistic PR-AUC 0.9904 and GBT 0.9130; both detect 3/3 synthetic events with 2.71 s median lead; no controller or real-fab claim |
| Root-cause attribution | Future simulator-label evaluation | Pending |
| Predictive-control improvement | Future paired controller report | Pending |
| Safety-filter constraint compliance | Future runtime audit | Pending |

## 9. Limitations and threats to validity

- The PHM dataset licence is not separately stated; use is limited to recorded local authorization.
- The PHM target unit is not declared by the original challenge source, and
  process-column scaling factors are hidden.
- PHM process-mode proxies are inferred from scaled inputs rather than measured
  phases; 306 official wafer/stage groups remain unresolved across the splits.
- Four extreme training labels require all three preregistered sensitivity
  reports; the hypothetical divide-by-60 policy is not a factual correction.
- A physical-machine generalization test is impossible with only machine ID 2.
- The PHM dataset does not validate the electrical/UPW disturbance causal chain.
- The electrical/UPS model is a lumped engineering approximation with constant
  efficiency and synthetic capacity/load values, not a waveform,
  electrochemistry, protection, or equipment-certification model.
- The pump curve is synthetic and omits manufacturer data, efficiency maps,
  BEP, shaft loss at runout, cavitation, NPSH, and motor-load feedback.
- The UPW model has one supply compliance and an exogenous return boundary; it
  omits distributed inertia and water hammer. Its dimensionless water-quality
  deviation is not measured chemistry, contamination, a defect, or yield.
- Sensor sampling anchors on the first supplied source state, and delay/jitter/
  corruption parameters are synthetic; queue delivery is not evidence of real
  instrument, clock, broker, historian, or network reliability.
- Scenario profiles, ranges, timings, magnitudes, and initiating-cause labels
  are synthetic definitions, not measured fab fault statistics or causal proof.
- CMP pressure is spatially uniform; spindle, slurry, thermal, glazing, wear,
  and dresser dynamics are reduced-order states with synthetic parameter
  values rather than calibrated tool/material physics.
- The default CMP temperature coefficient is zero. The annular exposure result
  is a simulated spatial-uniformity proxy, not measured or experimentally
  validated WIWNU.
- Utility-to-CMP pathway existence has partial qualitative literature support,
  but every numerical coefficient is synthetic and every transfer function is
  an engineering approximation. Global results show material dependence on
  link strength and threshold/reference ranges; actual tool plumbing is unknown.
- Empty traces are retained but do not provide measured process evidence.
- Simulator truth supports internal evaluation, not real-fab causal proof.
- WP12 primary TEST evidence contains only three independent event-bearing
  runs. Its 84 positive rows are repeated decision opportunities around those
  events, and the positive endpoints require nearly full-DRESS synthetic
  service loss near the target's feasibility boundary.
- The early-warning models false-alarm severely under no-connection and unseen
  compound shifts. High synthetic noise particularly damages logistic
  discrimination, specificity, and empirical conformal coverage.
- Split probability and conformal calibration use independent whole runs, but
  time rows are dependent and the fixed severity grid is not an iid fab
  sample. Empty conformal sets occur on 7.04% of logistic and 12.27% of
  gradient-boosted primary rows and must become a WP16 invalid/high-uncertainty
  condition.
- Static schedule, capacity, and load fields are known in the synthetic
  experiment; real deployment would require independently audited availability
  and consistency. WP12 vectorized offline latency is not streaming-control
  latency.
- No physical defect, yield, equipment-damage, or production-control labels are available.
- Temporal resolution and software latency must not be represented as production real-time guarantees.

## 10. Reproducibility record

- Environment: conda environment `devkki`.
- Package installation: editable local install with no optional dependencies.
- R1 suite: 21 focused contract/configuration/schema tests and 70/70 complete
  tests passed in `devkki`. The explicit default configuration SHA-256 is
  `4cc229eff2635bc64f8b84815317d6070ce3ba89b27f46af5c64b6fb56e4f3f8`.
- R2 suite: 13 focused semantic/split tests, 6 real-data integration tests, and
  82/82 complete tests passed with zero warnings. Processed-bundle manifest
  hash: `ff465151aa621a197aac2d253dd36879dfd39e57cfb29913b5788e3b112ece48`.
  R1/R2 do not validate a VM model.
- R3 suite: 52 focused contract/unit/property/integration tests and 94/94
  complete tests passed. Canonical runtime-config hash:
  `6a47eefbefee0fa3084b3f4f2e780d0aa430bf3cad1f3dbb64a988398bbbaf97`.
  Validation JSON and healthy-UPS trace are under `reports/plant/`.
- R4 suite: 45 focused schema/config/interface/sensor/scenario/replay tests and
  107/107 complete tests passed. Canonical runtime-config hash:
  `7a66469391268dae6e0458255ff88b263e6bf84965e87c93a7b04676caf4fd86`.
  Validation JSON and sensor-delivery trace are under `reports/timing/`.
  R1--R4 do not validate CMP or control performance.
- WP08 suite: 48 focused CMP/contract tests and 130/130 complete tests passed.
  Canonical runtime-config hash:
  `99d7876eb76d561de97ed577d77da30e929c70276070bb6f84df0fb9c9e91670`.
  The 700-row trace hash is
  `902fa4283ef8cf2150efef14aa08ca6f478aad55503e6d9b111584c33175626e`;
  validation JSON and trace are under `reports/cmp/`. WP08 does not validate a
  public VM model, utility connection, defect, yield, or controller efficacy.
- WP10 task-local suite: 50/50 impacted coupling/electrical/config/interface/
  integration/regression tests pass; the complete suite passes 154/154 in
  43.92 s. Current schema/interface versions are
  2.4.0/3.2.0 and runtime hash is
  `b2b07edbaad458f6f66cf26ce88ffc5deef656a33701a7cccd8da94104d7383f`.
  The connected negative-control trace hash is
  `f8359518903a8def6e02d03a8bc73123cc8a32dc5c32ed39dabc26745bfc3f20`;
  positive no-connection/connected hashes are
  `3560cb28a4cc8e87d778146f2cf0964290d733da2a0b59bee283659644ae41fc`
  and
  `19f440b2fd31959c619c31b851003ac496ff4d3b66c1643a6c6fbbb4951dfa10`.
  WP10 does not validate public VM, a real utility connection, early warning,
  attribution, safety, or controller efficacy.
- WP12 suite: 16/16 focused tests and 170/170 complete repository tests passed
  with warnings treated as errors. Final experiment revision:
  `1.4-no-test-selection`. WP12 configuration hash:
  `b53730011cb4f3c26173c727ba9fc562e9677a24a422f558a1c3330ab2df1e05`;
  eligible dataset hash:
  `fabe232a503320c59e9a201b62731adc8bf4c6b1f5fd5ee57bb30091a30b43fa`;
  deterministic probability-payload hash:
  `5a4fb7011fd6688718455c9692689937caa679ea29c884cdca099835a9830ede`.
  The payload intentionally excludes measured latency and conformal sets.
- Dataset archive and extraction checksums: recorded above and in the extraction manifest.
- Current source status: Git branch `main`; validated WP10 baseline commit
  `51ba07a` and interim WP10 demonstration commit `bf5fa99` precede the
  uncommitted WP12 checkpoint recorded in this draft.
- WP12 reproduction commands:

  ```text
  conda run -n devkki python -m pytest -q -W error
  env MPLCONFIGDIR=/tmp/semifab-poc-matplotlib conda run -n devkki python scripts/validate_wp12_early_warning.py
  conda run -n devkki python scripts/validate_governance.py
  ```

  Simulator, controller, report, and dashboard reproduction commands will be
  expanded as later work packages become available.

## 11. Pending paper updates

At each completed work package, update the abstract status, methods, results ledger, assumptions, limitations, and reproducibility record. Before finalization, replace all pending sections only with evidence-backed artifacts and run the claims audit against `orchestration/claims_matrix.md`.
