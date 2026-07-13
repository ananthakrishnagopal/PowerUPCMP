# Decision: WP16 independent safety-filter contract

Date: 2026-07-13
Status: FROZEN FOR PHASE 4 IMPLEMENTATION
Task: T-WP16
Evidence plane: synthetic simulator and software constraints only
Upstream decision: `wp15_predictive_supervisory_control.md`

## Decision summary

WP16 will implement a stateful safety filter that is structurally independent
of every controller implementation. It accepts one canonical proposed action,
arrived observations, warning/uncertainty evidence, and a separately loaded
constraint set. It returns an auditable disposition plus exactly one final
action. Only that final action may cross the WP17 actuator boundary.

The filter cannot import a predictive or baseline controller module, trust a
controller's statement that an action is safe, access latent simulator truth,
or use simulator initiating-cause labels. It is a simulation software guard,
not a safety instrumented system and not equipment certification.

## Canonical outcomes

The frozen outcomes retain their existing schema meanings:

| Outcome | Meaning | Final-action rule |
|---|---|---|
| `APPROVED` | Proposal already satisfies every applicable constraint. | Same action semantics, new `FINAL` record. |
| `CLIPPED` | A numeric proposal exceeds a soft magnitude or slew limit but has a unique safe projection. | Projected numeric action. |
| `REJECTED_OUT_OF_ENVELOPE` | Type, target, unit, timing, mode, hard magnitude, or process-envelope condition is invalid. | Last safe command, `NO_ACTION`, or `SAFE_HOLD` according to process state. |
| `REJECTED_SENSOR_INVALID` | Required arrived observations are missing, stale, blocked by quality flags, or mutually inconsistent. | `SAFE_HOLD` in an active recipe; otherwise `NO_ACTION`. |
| `REJECTED_HIGH_UNCERTAINTY` | Prediction is stale, empty/non-singleton when singleton evidence is required, out of applicability, or bound to the wrong artifact/topology/configuration. | `SAFE_HOLD` when an active-risk or resume proposal exists; otherwise `NO_ACTION`. |
| `REPLACED_WITH_HOLD` | A mandatory-hold condition overrides a non-hold proposal. | `SAFE_HOLD`. |

Every decision records the violated constraint IDs, sensor-validity result,
uncertainty/applicability result, process-envelope result, final action ID, and
measured filter latency.

## Evaluation order

The filter applies the following deterministic priority. A later check cannot
erase evidence from an earlier one.

1. Validate proposal schema, stage, canonical type/target/unit, effective step,
   finite value, constraint version, and current observed process mode.
2. Evaluate mandatory-hold triggers. A valid proposed hold is approved; any
   other proposal becomes `REPLACED_WITH_HOLD`.
3. For non-hold actuation, validate sensor completeness, freshness, quality,
   and cross-signal consistency.
4. Validate warning age, uncertainty set, artifact/config/topology binding,
   feature cutoff, and applicability.
5. Validate process-envelope and action/mode compatibility.
6. Apply hard magnitude limits. A proposal outside the physical/canonical
   bound is rejected; a proposal outside only the narrower supervisory bound
   may be clipped.
7. Apply slew limits relative to the last final action. A unique projection may
   be clipped; an ambiguous or direction-reversing projection is rejected.
8. Apply controlled-resume conditions and state transition rules.
9. Emit exactly one final action and commit filter state only after validation.

If a computation, unit, state, or constraint is indeterminate, the filter
fails closed to the applicable hold/no-action fallback and records why.

## Observation-validity contract

For required signal \(s\), let \(o_s^*\) be its latest observation available
at decision time \(t_k\). Freshness is

\[
\operatorname{fresh}_s(k)=
\mathbf 1[o_s^*\ \mathrm{exists}]
\mathbf 1[t_{arrival,s}\le t_k]
\mathbf 1[0\le t_k-t_{source,s}\le A_s].
\]

The configured maximum age \(A_s\) is 0.20 s for electrical, drive, pump,
pressure, and flow signals; 0.50 s for temperature; and 0.10 s for automation
mode/command status. `MISSING`, `DROPPED`, `STUCK`, `BIASED`, `DRIFTING`,
`OUT_OF_RANGE`, `UNIT_UNRESOLVED`, and `INVALID` are blocking flags.
`DELAYED` is acceptable only when the source-age test still passes;
`QUANTISED` and `TIMESTAMP_JITTERED` are evidence but are not independently
blocking.

Required non-hold-actuation signals are:

- UPS output voltage and battery energy;
- VFD available output and trip status;
- motor speed and pump flow;
- UPW supply pressure, tool flow, and temperature; and
- observed automation mode plus the affected command/setpoint.

`SAFE_HOLD` itself remains available when some observations are invalid because
it requests the de-energized CMP mode. Invalid observations never authorize a
resume or a numeric setpoint change.

Cross-signal consistency uses only observed values. The pressure/flow residuals
already frozen for WP13 may provide diagnostic evidence, but an attribution
class or simulator fault flag is never a safety truth source.

## Applicability and warning-uncertainty contract

An active non-hold proposal requires:

- exact warning artifact and metadata hashes from WP15;
- matching warning feature schema and target;
- declared `DRESSING_WATER_SUPPORT` topology and link profile;
- matching static plant/configuration identifiers;
- feature cutoff no later than the action decision;
- prediction age no greater than 0.20 s;
- finite probability in [0, 1]; and
- no feature-range or observation-validity applicability rejection.

A high-risk hold requires calibrated probability at least 0.50 and singleton
positive conformal set `{1}` when those values are valid. If risk is high but
uncertainty/applicability is indeterminate, numeric actuation and resume are
forbidden; the fallback is hold rather than an inferred normal state.

Attribution may be `UNKNOWN` without blocking a generic safe hold. It blocks
any future cause-specific actuation unless separately validated. The primary
WP15 controller has no cause-specific actuation.

## Mandatory-hold conditions

Invalid sensors, timing, commands, or filter execution may request a final hold
in any nonterminal phase. Utility continuation thresholds automatically force
a hold only in `PREPARE` or `POLISH`, where removal is being approached or is
active. During `DRESS`, utility loss is a modelled conditioning-quality risk,
not a validated equipment hazard; the predictive or utility-threshold
controller may propose hold, but the safety filter does not preempt that
comparison. This is a simulation-study boundary, not a real-tool safety rule.

The mandatory conditions are:

- utility or automation observations required for safe continuation are
  invalid beyond the configured grace/persistence interval;
- in `PREPARE` or `POLISH`, a VFD trip is observed;
- in `PREPARE` or `POLISH`, UPS output, motor speed, pump flow, pressure, or
  tool flow crosses its continuation envelope;
- in `PREPARE` or `POLISH`, UPW temperature crosses its continuation envelope;
- a confident WP15 positive warning requests hold;
- a process command or observed mode is inconsistent with the approved recipe;
- action timing would be effective before step \(k+1\); or
- filter execution cannot produce a unique valid final action.

The filter never asserts that a hold prevents a physical defect or equipment
event. It only places the simulated CMP subsystem in its existing `HOLD` mode.

## Frozen supervisory action bounds

The plant's physical bounds remain broader than the deliberately conservative
supervisory envelopes below. All numerical values are synthetic assumptions.

| Action | Target/unit | Supervisory interval | Maximum change per 0.10 s decision | Maximum slew | Primary WP15 enabled |
|---|---|---:|---:|---:|---|
| `VFD_COMMAND_ADJUSTMENT` | `drive.vfd_command`, pu | [0.90, 1.00] | 0.01 | 0.10 pu/s | No |
| `VALVE_ADJUSTMENT` | `upw.valve_position`, 1 | [0.90, 1.00] | 0.01 | 0.10 1/s | No |
| `CMP_DOWNFORCE_REDUCTION` | `cmp.contact_pressure_command`, Pa | [24000, 30000] | 300 | 3000 Pa/s | No |
| `HEAD_SPEED_REDUCTION` | `cmp.head_angular_speed`, rad/s | [4.8, 6.0] | 0.06 | 0.60 rad/s² | No |
| `PLATEN_SPEED_REDUCTION` | `cmp.platen_angular_speed`, rad/s | [6.4, 8.0] | 0.08 | 0.80 rad/s² | No |

The lower numerical bounds are 80 percent of the nominal CMP setpoints or 90
percent of the nominal utility commands. They are not proven safe tool limits.
Phase 4 tests only verify enforcement of these configured simulation limits.

`NO_ACTION`, `ADVISORY_WARNING`, `SAFE_HOLD`, and `CONTROLLED_RESUME` have no
numeric value. Their target/unit pairs are respectively `supervisory.none/1`,
`supervisory.advisory/1`, and `cmp.process_mode/1` for hold/resume.

Numeric reduction actions are allowed only in observed `PREPARE` or `POLISH`
and only when the applicable envelope is normal. Hold is allowed from every
nonterminal mode. Resume is allowed only from `HOLD` and becomes `RECOVER`.

## Continuation and release envelopes

Ratios use the frozen synthetic references: UPS output 1.0 pu, motor speed
188.5 rad/s, pump flow \(2.0\times10^{-4}\) m³/s, supply pressure 300 kPa,
tool flow \(1.0\times10^{-4}\) m³/s, and temperature 293.15 K.

The utility continuation envelope uses a 0.10 s persistence interval and is
an automatic safety-filter hold only in `PREPARE` or `POLISH`:

- UPS output, motor speed, pump flow, pressure, or tool flow below 0.90 of
  reference;
- pressure or flow above 1.10 of reference; or
- absolute UPW temperature deviation above 2.0 K.

The release envelope is narrower and must hold continuously for 1.0 s:

- UPS output, motor speed, pump flow, pressure, and tool flow in [0.95, 1.05]
  of reference;
- absolute UPW temperature deviation no greater than 1.0 K;
- VFD not tripped;
- every required signal valid and fresh; and
- no process-envelope inconsistency.

Observed battery energy must also exceed

\[
E_{min}=1.25\frac{P_{load}}{\eta_{inv}}(H+\tau_{recover}),
\]

where \(H=3.0\) s and \(\tau_{recover}=0.5\) s. This is a synthetic reserve
check, not a battery-health or ride-through guarantee.

## Controlled-resume state machine

The restart sequence is:

```text
RUNNING --mandatory/proposed hold--> HOLD
HOLD --release conditions stable--> RECOVER
RECOVER --0.50 s valid dwell--> RESTORE_INTERRUPTED_PHASE
RECOVER --any invalidity--> HOLD
```

Additional frozen conditions are:

- minimum hold time 0.50 s;
- direct release-envelope dwell 1.00 s;
- warning probability no greater than 0.20 with singleton set `{0}` for a
  continuous 0.50 s before resume;
- action effective no earlier than the next simulation step;
- recipe clock frozen throughout `HOLD` and `RECOVER`; and
- no automatic transition out of terminal `COMPLETE`.

If warning inference is unavailable after an action-induced schedule shift,
the process remains held. Phase 4 may update known phase-clock features through
the frozen recipe-progress contract, but it may not bypass uncertainty to
force a resume.

## Final-action invariant

For every decision \(d_k\), define \(a_k^F\) as the emitted final action. The
required software property is

\[
\forall k:\quad a_k^F\in\mathcal A_{canonical}
\land a_k^F\in\mathcal C_k
\land t_{effective}(a_k^F)\ge t_{k+1},
\]

where \(\mathcal C_k\) is the independently evaluated constraint set. If no
non-hold action belongs to \(\mathcal C_k\), a canonical hold/no-action
fallback must still exist. A missing final action is always an implementation
failure.

## Required Phase 4 tests

- safety module has no import or callback dependency on controller modules;
- all six canonical outcomes are reachable;
- every outcome emits one valid final action and constraint evidence;
- hold remains reachable with missing or stale critical sensors;
- invalid sensors cannot authorize numeric actuation or resume;
- empty/non-singleton uncertainty cannot authorize resume;
- topology/config/artifact mismatch is rejected;
- hard magnitude violations reject and soft violations clip uniquely;
- slew projection is deterministic and within both per-step and per-second
  limits;
- action/mode incompatibilities reject;
- hold and release hysteresis prevent chatter;
- minimum hold, direct-recovery dwell, warning-clear dwell, battery reserve,
  and CMP recovery dwell are all enforced;
- recovery invalidity returns to hold and resets dwell;
- fixed seeds replay identical safety decisions;
- property-based action sweeps produce zero final constraint violations; and
- latency is measured against the WP15 budget.

## Interface and schema impact analysis

`SafetyFilter` remains version 1.0.0. Its independence requirement, method
signature, six outcomes, and final-action requirement are unchanged. The
canonical schema already contains all required action, safety-decision,
observation, quality-flag, mode, and signal vocabularies. No schema or physical
subsystem interface change is required.

The Phase 4 runtime must serialize the constraint-set version/hash and expose
observed automation status through ordinary `ObservationRecord` instances.
This is additive runtime wiring, not access to latent CMP truth.

## Claim boundary

Passing WP16 can support only claim C-006: the implemented software filter kept
final simulated actions inside its declared synthetic constraints for the
tested cases. It cannot establish functional safety, safe real-tool limits,
equipment protection, regulatory compliance, production readiness, or
prevention of any physical defect or yield loss.
