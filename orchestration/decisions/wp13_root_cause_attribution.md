# Decision: WP13 root-cause attribution and abstention policy

Date: 2026-07-13
Status: FROZEN BEFORE HELD-OUT ATTRIBUTION EXECUTION
Task: T-WP13
Evidence plane: synthetic simulator only

## Decision question

WP13 asks whether arrived, observed utility signals can classify a simulated
initiating disturbance after an early-warning decision. It does not establish
causal proof, diagnose a real tool, validate a physical defect mechanism, or
show controller benefit.

The estimator must answer conservatively. A weak, invalid, out-of-distribution,
conflicting, or compound signature is reported as `UNKNOWN`; it is not forced
into the nearest known class.

## Cause semantics

The primary initiating-cause classes are:

1. `GRID_VOLTAGE_SAG`;
2. `GRID_VOLTAGE_SWELL`;
3. `GRID_INTERRUPTION`;
4. `GRID_FREQUENCY_DEVIATION`;
5. `PUMP_TRIP`;
6. `VALVE_RESTRICTION`;
7. `TOOL_DEMAND_SPIKE`;
8. `THERMAL_EXCURSION`;
9. `PRESSURE_SENSOR_FAULT`; and
10. `FLOW_SENSOR_FAULT`.

`UNKNOWN` is a required output, not a post-processing convenience.
`UPS_TRANSFER` and `VFD_DERATING` remain members of the canonical attribution
vocabulary, but R4 forbids them as declarative initiating causes. WP13 scores
them as intermediate propagation evidence and records their rule-chain IDs.
They are not held-out initiating labels and are never described as causal
proof.

## Online and offline boundary

At decision time \(t_d\), the estimator may consume only observation records
whose arrival time is no later than \(t_d\), the current warning result, and
validated static references. The feature cutoff is therefore

\[
\mathcal O(t_d)=\{o_i:t_{arrival,i}\le t_d\}.
\]

The estimator may not consume latent simulator state, `event_active`, scenario
family, disturbance magnitude, future samples, future MRR, paired nominal MRR,
offline excursion labels, or simulator initiating-cause labels. Event labels
are joined only after an attribution record has been emitted.

The allowed observed channels are grid and UPS voltage/frequency, UPS battery
energy, VFD available output and trip state, motor speed, pump flow, UPW supply
pressure and tool flow, valve position, tool demand, and UPW temperature.
Commands/status fields are treated as observed automation data, not latent
truth. CMP MRR, pad state, coupling state, and scenario flags are explicitly
forbidden.

Primary sensors sample every 0.05 s with 0.05 s delivery delay, 1% packet
loss, 0.005 s timestamp-jitter standard deviation, and the per-channel Gaussian
noise frozen in `configs/models/attribution.yaml`. These are synthetic
instrument assumptions, not measured reliability specifications.

Unknown sensor faults are injected only at the observation boundary. The
physical latent pressure/flow state remains unchanged. Fault quality flags are
not features because a simulator-generated `BIASED` flag would reveal the
label.

## Window features

For signal \(s\), raw value \(x_s\), fixed engineering reference \(\mu_s\),
and fixed scale \(\sigma_s>0\), define

\[
z_s=(x_s-\mu_s)/\sigma_s.
\]

The estimator uses the latest value, short-window mean, least-squares slope,
and missing fraction from a 0.75 s arrived-observation window. Statistical
imputation and scaling for the learned model are fit on TRAIN groups only.
No complete-trace statistic is allowed.

Two model-visible consistency residuals are added. The pressure proxy uses the
nominal return pressure \(P_r\), nominal supply pressure \(P_0\), and measured
pump-flow ratio \(q_p=Q_p/Q_{p,0}\):

\[
\widehat P=P_r+(P_0-P_r)q_p^2,
\qquad
r_P=(P_{obs}-\widehat P)/P_0.
\]

This is an engineering diagnostic approximation motivated by the pump-head
affinity relation; it is not a replacement for the dynamic hydraulic model.
The flow consistency proxy reuses the frozen UPW valve equation:

\[
\widehat Q_t=\min\left(D,\;v\max(P_{obs}-P_r,0)/R_t\right),
\qquad
r_Q=(Q_{obs}-\widehat Q_t)/Q_{t,0}.
\]

Pressure- and flow-sensor-fault rules require a large corresponding residual
while direct physical-event rules are quiet. This reduces, but cannot remove,
fault/plant ambiguity under poor redundancy.

## Residual-rule layer

Every primary cause receives a bounded rule score \(u_c\in[0,1]\). For a
non-negative severity \(d\), the common soft threshold is

\[
\rho(d;a,b)=\operatorname{clip}\left(\frac{d-a}{b-a},0,1\right),
\qquad 0\le a<b.
\]

The direct severities are voltage deficit, voltage excess, near-zero grid
voltage, absolute frequency deviation, VFD trip/motor-speed loss, valve
closure, tool-demand increase, temperature deviation, absolute pressure
residual, and absolute flow residual. Exact thresholds are frozen in
`configs/models/attribution.yaml`.

UPS-transfer evidence combines an upstream voltage/interruption signature with
UPS/grid voltage separation or battery discharge. VFD-derating evidence uses
available-output loss without treating the response as an initiator. Rule
probabilities over the ten initiators plus `UNKNOWN` are a temperature-scaled
softmax of the rule scores. The two propagation scores are retained separately
in the canonical probability mapping with at most 0.10 total probability mass;
the initiating/`UNKNOWN` distribution receives the remaining mass and the
final mapping is normalized. Initiating-class gates use the distribution before
this display allocation.

Each positive rule records a stable identifier such as
`GRID_SAG_TO_UPS_RESPONSE`, `VFD_TO_MOTOR_TO_PUMP_LOSS`, or
`FLOW_REDUNDANCY_RESIDUAL`. These identifiers describe a simulator-consistent
diagnostic chain, not experimental causal proof.

## Learned and hybrid layers

The statistical comparison is multinomial logistic regression with
training-only median imputation, standardization, balanced class weights,
`C=1`, `lbfgs`, at most 2000 iterations, and fixed seed 20260713. It is trained
only on whole TRAIN runs using offline initiating labels. A scalar softmax
temperature is selected on disjoint CALIBRATION runs from the frozen grid
`[0.50, 0.75, 1.00, 1.25, 1.50, 2.00]` by minimum multiclass log loss, with the
lowest temperature winning ties.

For class \(c\), transformed feature \(\widetilde x_j\), and fitted coefficient
\(\beta_{cj}\), the reported local feature contribution is

\[
a_{cj}=\beta_{cj}\widetilde x_j.
\]

These signed contributions explain the fitted classifier score only. They are
not causal effects and may not be called causal attribution.

The primary hybrid pools learned and rule probabilities geometrically:

\[
s_c=\lambda\log(p_{ML,c}+\epsilon)
 +(1-\lambda)\log(p_{rule,c}+\epsilon),
\qquad
p_{hybrid}=\operatorname{softmax}(s),
\]

with \(\lambda=0.5\) and \(\epsilon=10^{-9}\). `ALWAYS_UNKNOWN`, `RULE_ONLY`,
and `LOGISTIC` remain mandatory comparators. The primary method is `HYBRID`;
no TEST-derived model selection is allowed.

## Mandatory UNKNOWN gates

The final prediction is `UNKNOWN` when any of the following holds:

1. the supplied warning is not positive;
2. warning uncertainty is invalid or the conformal set is not exactly `{1}`;
3. required observations are stale or the aggregate missing fraction exceeds
   0.35;
4. any learned standardized feature magnitude exceeds 8.0;
5. the largest initiating probability is below 0.55;
6. the largest-minus-second-largest initiating probability is below 0.10;
7. confident rule and learned distributions have Jensen-Shannon divergence
   above 0.35; or
8. two distinct initiating rules both score at least 0.70.

The applicable gate is recorded as a rule-chain ID. `UNKNOWN` probability is
raised to at least 0.80 when a gate fires and the full probability mapping is
renormalized. `causal_proof` is a literal `false` for every record.

## Compound-event policy

Simulator truth for overlapping initiators remains an ordered tuple offline.
Because the frozen online record has one `predicted_cause`, the estimator must
abstain on simultaneous strong initiating chains rather than choose one.
Compound evaluation reports abstention rate and truth-set recall at two using
the pre-abstention distribution. It is separate from single-cause accuracy and
cannot inflate it.

## Scenario ensemble and splits

The synthetic diagnostic ensemble extends the existing open-loop chain
additively. It uses the declared `DRESSING_WATER_SUPPORT` topology and
event-scoped observed faults. Each primary class plus normal `UNKNOWN` receives
disjoint whole-run TRAIN, CALIBRATION, and TEST seeds. Multiple windows from a
run stay in one split. The TEST split is not opened until the implementation,
configuration, unit tests, leakage audit, and calibration-only checks pass.

The primary diagnostic evaluation supplies a neutral valid-positive warning
token so cause separability can be assessed independently of WP12 warning
recall. This is explicitly conditional diagnostic capability, not an
end-to-end operational result. A secondary operational evaluation may call the
estimator only at an actual WP12 positive singleton warning; an absent or
uncertain warning must yield `UNKNOWN`. Full online integration remains WP17.

Separate robustness sets cover doubled noise, 0.20 s communication delay, 10%
packet loss, parameter mismatch, an unseen interruption/demand compound, and
pre-event/normal windows. None is folded into the primary TEST metric.

## Frozen evaluation and interpretation gates

Held-out run-group reporting includes confusion matrix, accuracy, macro
precision/recall/F1, per-class support, top-two accuracy, multiclass Brier
score, log loss, expected calibration error, coverage (non-`UNKNOWN` fraction),
selective accuracy, unknown recall, normal false-attribution rate, compound
abstention, truth-set recall at two, earliest correct attribution time, and
latency. Grouped bootstrap summaries use run IDs.

The synthetic usefulness gate requires all of:

- accuracy at least 0.70;
- macro recall at least 0.65;
- accuracy improvement over always-`UNKNOWN` of at least 0.40;
- `UNKNOWN` recall at least 0.80;
- normal false-attribution rate no greater than 0.20;
- selective accuracy at least 0.75;
- non-`UNKNOWN` coverage on known single causes at least 0.60;
- compound abstention at least 0.75; and
- zero forbidden or future features.

Failure of a gate is reported, not tuned away. Passing supports only a bounded
synthetic attribution claim under the declared instrument set, topology,
severity grid, and simulator assumptions.

## Interface and implementation impact

`RootCauseEstimator` remains version 1.0.0. WP13 adds a concrete typed
observation window and attribution record without changing the frozen method
names. The open-loop chain receives additive event families and observed
signals; existing WP12 signal behavior must remain deterministic. The scenario
engine's initiating/propagation distinction is unchanged.

Required tests cover strict configuration, arrived-only cutoffs, forbidden
signal rejection, label hiding, latent/observed fault separation, all canonical
probability keys, propagation-only semantics, deterministic replay, rule
limiting cases, `UNKNOWN` gates, compound abstention, coefficient-based feature
contributions, save/load checksums, grouped splits, and held-out reporting.

## Claims boundary

WP13 evidence is synthetic and simulator-conditional. Feature contributions,
residual agreement, rule chains, and simulator labels are not experimental
causal proof. No result supports a physical-defect, yield, real-fab diagnostic,
equipment-protection, production-control, or controller-efficacy claim.
