# Decision: WP15 predictive supervisory-control contract

Date: 2026-07-13
Status: FROZEN FOR PHASE 4 IMPLEMENTATION
Task: T-WP15
Evidence plane: synthetic simulator only
Upstream decisions: WP08, WP10, WP12, and WP13

## Decision summary

The first predictive supervisor will be a finite, stateful, bounded-action
policy driven by the frozen WP12 logistic warning artifact. It is not
reinforcement learning and it is not described as an optimal controller. Its
primary physical intervention is an early safe hold followed by controlled
recovery and restoration of the interrupted recipe phase.

The primary controller will emit only:

- `NO_ACTION`;
- `ADVISORY_WARNING`;
- `SAFE_HOLD`; and
- `CONTROLLED_RESUME`.

The canonical VFD, valve, downforce, head-speed, and platen-speed adjustments
remain represented and independently bounded, but they are disabled in the
primary PoC controller. Their presence in the vocabulary does not imply that
the current plant has useful compensating authority.

This decision freezes the scientific contract and Phase 4 acceptance tests.
It does not implement the controller, execute an integrated closed-loop run,
or support claims C-004, C-005, or C-006.

## Evidence and claim boundary

Every online decision uses only observations released by decision time, the
current warning output, prior actions/safety decisions, and validated static
configuration. Latent MRR, pad state, coupling state, scenario identity,
initiating-cause truth, and future observations remain forbidden.

The action is supervisory and simulation-only. No action record is a hardware
command, no constraint is an equipment rating, and no result may be called
real production control, equipment protection, defect prevention, or yield
improvement.

## Actuator-authority audit

The validated positive mechanism is a loss of conditioning-water support
during `DRESS`, followed by stored pad-surface-memory loss and later
under-removal during `POLISH`. The current command authority is asymmetric:

| Candidate | Nominal command | Plant hard maximum | Direction available | Primary-mechanism assessment |
|---|---:|---:|---|---|
| VFD command | 1.0 pu | 1.0 pu | decrease only | Cannot overcome voltage derating or raise pump speed above nominal. |
| UPW valve | 1.0 | 1.0 | close only | Cannot increase an already fully open branch. |
| CMP contact pressure | 30 kPa | 60 kPa physical bound | configured action is reduction only | With positive Preston pressure exponent, reduction worsens an under-removal excursion. |
| Head speed | 6 rad/s magnitude | 15 rad/s physical bound | configured action is reduction only | Reduction cannot be assumed to restore under-removal. |
| Platen speed | 8 rad/s magnitude | 15 rad/s physical bound | configured action is reduction only | Reduction cannot be assumed to restore under-removal. |

Increasing CMP pressure or spindle speed could raise the synthetic Preston
term, but no real-tool recipe envelope, film endpoint, spatial metrology, or
calibrated safety evidence supports such compensation. The primary PoC must
not create that authority merely to obtain a favorable controller result.

The defensible intervention is to prevent progression into a vulnerable phase,
wait for observed utility recovery, complete the interrupted conditioning
phase, and then resume through the independent safety state machine.

## Predictor binding and downstream data isolation

The Phase 4 controller binds to:

- warning target `SIM_ACTIVE_POLISH_MRR_TRAJECTORY_V1`;
- horizon 3.0 s;
- decision period 0.10 s;
- model kind `LOGISTIC`;
- artifact SHA-256
  `c95b460397487760a33f64b04bca876b9e51c0108438730f85b0b298c26e7078`;
- metadata SHA-256
  `1677b275263da25a9c2444902289c14212589e7bf91cbc2b620d3a396c9f5c9f`;
- WP12 configuration SHA-256
  `b53730011cb4f3c26173c727ba9fc562e9677a24a422f558a1c3330ab2df1e05`;
- declared topology `DRESSING_WATER_SUPPORT`; and
- exact schema and feature identities stored with the model.

Logistic regression is frozen for controller development because it is the
simpler calibrated model with explicit linear feature structure. This is a
post-WP12 design choice, not a revision of the WP12 comparison and not a claim
that TEST selected a universally superior model. Consequently, every WP12
TRAIN/CALIBRATION/CONFORMAL/TEST/robustness seed is development evidence for
the control study and is prohibited from the new WP18 controller TEST role.

The controller must refuse active non-hold proposals when the model, topology,
feature schema, or configuration binding does not match. A safe hold remains
permitted because it moves the simulated process toward the de-energized state.

## Controller state and process-clock semantics

The controller state is

\[
z_k\in\{\mathrm{RUNNING},\mathrm{HOLDING},\mathrm{RECOVERING},
\mathrm{COMPLETE}\}.
\]

It also stores the last final action, hold-entry time, interrupted recipe mode,
and recipe-phase progress. The recipe clock is distinct from wall time:

\[
\dot\tau_{recipe}(t)=
\begin{cases}
1,&z(t)=\mathrm{RUNNING},\\
0,&z(t)\in\{\mathrm{HOLDING},\mathrm{RECOVERING}\}.
\end{cases}
\]

`SAFE_HOLD` therefore pauses phase progress. `CONTROLLED_RESUME` first enters
`RECOVER`; after the frozen dwell, the runtime restores the interrupted phase
and completes its remaining recipe duration. For an interrupted `DRESS`, the
existing CMP transition graph is used without a physical-interface change:

```text
HOLD -> RECOVER -> PREPARE -> DRESS
```

The one-step `PREPARE` routing transition is not counted as completed recipe
progress. If validity is lost during recovery, the state returns to `HOLDING`
and the continuous recovery-dwell timer resets.

This phase-clock contract is essential. A wall-clock schedule that advances
through `DRESS` while held would skip the conditioning work that the hold was
intended to preserve.

## Warning gates and bounded action policy

Let \(p_k\) be the calibrated probability of a persistent excursion within
3.0 s and \(S_k\subseteq\{0,1\}\) its conformal prediction set. Define

\[
g_k^+=\mathbf 1[p_k\ge0.50]
       \mathbf 1[S_k=\{1\}]
       \mathbf 1[u_k=\mathrm{valid}]
       \mathbf 1[a_k=\mathrm{applicable}],
\]

where applicability covers model/config/topology identity, feature cutoff,
freshness, and out-of-distribution checks owned by the safety contract.

The state-dependent proposal policy is:

1. In `RUNNING`, propose `SAFE_HOLD` when \(g_k^+=1\).
2. Otherwise, in `RUNNING`, propose `ADVISORY_WARNING` when
   \(p_k\ge0.30\); propose `NO_ACTION` below 0.30.
3. In `HOLDING`, remain held until the independent filter confirms the full
   restart contract. The controller may then propose `CONTROLLED_RESUME` only
   when \(p_k\le0.20\), \(S_k=\{0\}\), and warning uncertainty is valid.
4. In `RECOVERING`, propose no additional actuation. Loss of validity is
   handled independently by the safety filter and returns the final action to
   hold.
5. In `COMPLETE`, only `NO_ACTION` is permitted.

Attribution is logged in the rationale and dashboard but does not select a
different actuator in the primary controller. WP13 `UNKNOWN` is never treated
as normal, and a feature contribution or rule chain never authorizes action.

## Bounded-search objective

At each eligible decision, the controller considers only the finite actions
allowed by its current state. It uses a lexicographic contract:

1. preserve independent safety feasibility;
2. avoid a confident predicted excursion;
3. preserve recipe completion and cumulative-removal opportunity;
4. minimize hold/recovery/cycle delay; and
5. minimize action transitions.

For auditable tie-breaking within an eligible state, define the dimensionless
surrogate score

\[
J_k(a)=8p_k r(a)
 +\frac{\Delta T_{phase}(a)}{H}
 +\frac{\Delta T_{hold}(a)}{H}
 +0.1\,\mathbf 1[a\ne a_{k-1}],
\qquad H=3.0\ \mathrm{s}.
\]

Here \(r=1\) for continued-running actions and \(r=0\) for the immediate
exposure suppressed by `SAFE_HOLD`; both delay terms are projected over the
same horizon. This is a conservative decision score, not a claim that hold
eliminates the later physical disturbance. The probability gates above remain
hard constraints, so the numeric score cannot create a hold below the frozen
warning threshold or force a resume above the frozen release threshold.

Actual controller evaluation does not use this surrogate as the efficacy
outcome. It measures simulated MRR, cumulative removal, phase completion,
hold/recovery time, and cycle delay directly. The score weights are synthetic
engineering choices and require sensitivity analysis in WP18.

## No hold gaming: evaluation coordinates

Let \(\tau\) denote active-polish progress and let \(R_c(\tau)\) be controller
\(c\)'s simulated MRR at that progress. Controller comparisons use an
event-disabled reference at matched progress, not matched wall time:

\[
E_{IAE,c}=\int_0^{\tau_f}
\left|R_c(\tau)-R_{ref}(\tau)\right|\,d\tau,
\]

\[
E_{peak,c}=\max_{0\le\tau\le\tau_f}
\left|R_c(\tau)-R_{ref}(\tau)\right|,
\]

and, at equal completed recipe scope,

\[
E_{rem,c}=\left|D_c(\tau_f)-D_{ref}(\tau_f)\right|,
\qquad
D_c(\tau_f)=\int_0^{\tau_f}R_c(\tau)\,d\tau.
\]

Every controller run continues until the same recipe phases complete or a
predeclared maximum extension is reached. A held interval has zero removal but
adds hold and cycle-time cost; it cannot shorten the evaluation horizon or be
scored as in-envelope polishing.

## Frozen baselines

`NO_ACTION` preserves all nominal recipe and utility commands and never
requests a mode change.

The required primary threshold comparator is
`PROCESS_MRR_THRESHOLD_HYSTERESIS_V1`. It consumes an arrived synthetic MRR
observation only during `POLISH` and compares it with the event-disabled
reference at matched recipe progress. It requests hold after the same 0.25 s
persistence used to define the WP12 process excursion:

- hold below 0.95 or above 1.05 of the phase-progress reference;
- release only inside [0.97, 1.03]; and
- reject MRR observations older than 0.20 s.

This is the fixed process-threshold controller expected by the demonstration:
it acts after the process envelope crosses, whereas predictive supervision may
act during the preceding conditioning phase. The simulator must generate the
MRR observation through the ordinary sensor boundary; latent MRR is forbidden.

A stronger secondary comparator,
`UTILITY_THRESHOLD_HYSTERESIS_V1`, is mandatory. It requests hold after 0.10 s
when UPS output, motor speed, pump flow, UPW pressure, or tool flow is below
0.90 of reference, when pressure/flow exceeds 1.10, or when temperature differs
by more than 2 K. Release requires [0.95, 1.05], a 1 K thermal band, and 1.0 s
valid dwell. Unlike the independent safety filter, this comparator may elect
to hold during `DRESS`.

Neither threshold policy may read warning probability, attribution, latent
state, or event truth. The primary three-controller claim compares predictive
control with the process-MRR threshold; the utility-threshold result is always
reported beside it so an early direct interlock is not hidden.

## Development limiting-case evidence

The frozen action mechanism was checked before integrated implementation with
the actual WP08 CMP equations, an imposed 0--5.99 s loss of dressing support,
equal six-second `DRESS` completion, equal nine-second active `POLISH`, and no
controller/sensor runtime. The warning-timed hold begins at 4.29 s, obtained
from the 7.00 s excursion onset minus WP12's 2.71 s median lead.

| Development case | Peak relative MRR deviation | Hold duration | Cycle extension |
|---|---:|---:|---:|
| Disturbed no action | 5.526% | 0.00 s | 0.00 s |
| Warning-timed hold | 3.895% | 1.70 s | 2.20 s |
| Immediate utility-threshold hold | 0.087% | 5.89 s | 6.39 s |

The warning-timed hold improves peak, integrated, and cumulative-removal error
relative to no action in this single limiting case, so the mechanism has a
feasible direction. The early utility threshold is substantially better on
MRR but holds much longer. This result is why the utility comparator is
mandatory and why no claim of predictive dominance is frozen in advance. The
artifact is `reports/control/phase3_hold_feasibility.json`; it is development
evidence, not a WP17/WP18 result.

## Latency budget

The decision period is 100 ms. On the declared development workstation, Phase
4 must measure separately:

- streaming feature and warning latency;
- attribution latency;
- controller-only latency;
- safety-filter latency; and
- end-to-end decision latency.

The preregistered software budgets are 10 ms at the 95th percentile for the
controller alone and 50 ms at the 95th percentile for the complete prediction,
attribution, controller, and filter path. A miss produces a logged safe fallback
and fails the latency gate. These are workstation PoC budgets, not production
real-time guarantees.

## Paired evaluation freeze

WP18 will allocate new, whole-run seed ranges beginning at 130000 for controller
development, 230000 for primary TEST, and 330000 for robustness. Primary TEST
contains at least eight independent runs for each of:

- normal operation;
- the healthy 25 percent, 400 ms voltage-sag negative control;
- hold-required grid interruption/degraded UPS;
- pump trip;
- valve restriction; and
- tool-demand spike.

No WP12 or WP13 run ID or seed may enter controller TEST. Tuning is confined to
controller-development runs. The required no-action, process-threshold, and
predictive controllers plus the utility-threshold comparator share identical
exogenous traces, initial states, static parameter realizations, child seed
maps, and observation corruptions within a paired run.

The predictive controller supports a bounded efficacy claim only if all of the
following hold on the primary paired TEST set:

1. versus no action, both median paired \(E_{peak}\) and \(E_{IAE}\) reductions
   are positive and their run-group bootstrap 95 percent lower bounds are
   non-negative;
2. versus the primary process-MRR threshold control, at least one median relative reduction in
   \(E_{peak}\) or \(E_{IAE}\) is at least 5 percent while the other is not
   worse by more than 5 percent;
3. median cumulative-removal error is not worse than threshold by more than
   5 percent;
4. at least 80 percent of primary hold-required paired runs are non-worse than
   no action on both peak and integrated MRR error;
5. the hold rate on normal and healthy-sag negative controls is no greater than
   5 percent;
6. every controller reaches equal recipe completion within a maximum 10 s
   extension or is reported as a failed completion;
7. all hold, recovery, cycle-time, and action-effort metrics are reported; and
8. no final action violates a WP16 constraint.

The same metrics are reported against the utility-threshold comparator. It is
not silently substituted for the primary process-threshold gate, and a worse
predictive result must remain visible as an important practical limitation.

Failure is reported without changing thresholds, weights, test seeds, or the
comparison tolerance.

## Required Phase 4 tests

- no latent, future, scenario, or cause-truth access;
- proposal effective no earlier than step \(k+1\);
- exact four-action primary vocabulary;
- direct numerical setpoint actions disabled in the primary policy;
- deterministic reset and replay;
- high-confidence positive warning proposes hold;
- moderate warning proposes advisory only;
- controller cannot self-approve an action;
- hold freezes recipe progress;
- controlled resume restores and completes the interrupted phase;
- invalid recovery returns to hold;
- score and threshold boundary cases;
- controller and end-to-end latency measurement; and
- absence of reinforcement-learning dependencies and terminology.

## Interface impact analysis

`Controller` remains version 1.0.0 and continues to return a proposed canonical
`ActionRecord` without plant mutation. The canonical action vocabulary and
record fields are unchanged. Recipe-clock state belongs to the future WP17
runtime/process supervisor; it does not alter `DynamicSubsystem`,
`CmpBoundaryConditions`, `Predictor`, or `SafetyFilter` signatures.

The runtime must expose observed automation mode and command records to online
control. Existing canonical signal IDs already cover CMP mode and commands, so
no schema change is required.

## Open limitation

The hold/phase-restoration mechanism is a synthetic supervisory hypothesis.
It may still fail to recover enough conditioning before polish, may increase
cycle time unacceptably, or may be inferior to fixed threshold control. That is
an empirical WP17/WP18 question. Phase 3 freezes the test; it does not assume
the favorable answer.
