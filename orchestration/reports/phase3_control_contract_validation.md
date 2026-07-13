# Phase 3 predictive-control and safety-contract validation

Date: 2026-07-13
Tasks: T-WP14 design dependency, T-WP15 scientific contract, T-WP16 scientific contract
Evidence plane: synthetic simulator and configuration/software contracts only
Disposition: frozen for bounded Phase 4 implementation

## Executive determination

Phase 3 now freezes the controller objective, usable action set, process-clock
semantics, baselines, safety constraints, restart logic, latency budgets, new
evaluation seeds, and paired comparison gates. Thirteen focused tests pass and
the machine-readable contract audit passes all 21 checks.

This is a design and feasibility result. No predictive controller or safety
filter has yet been implemented in the WP17 runtime, so claims C-004, C-005,
and C-006 remain planned.

## Key review finding

The primary validated causal mechanism is conditioning-service loss during
`DRESS`, stored pad-activity loss, and later under-removal. The nominal VFD and
UPW valve commands are already at their maxima. The permitted CMP numerical
actions are reductions, and the frozen Preston exponents are positive.
Consequently, VFD/valve/downforce/head/platen actions cannot be presented as
validated compensation for this under-removal mechanism.

The primary controller is therefore limited to `NO_ACTION`,
`ADVISORY_WARNING`, `SAFE_HOLD`, and `CONTROLLED_RESUME`. Numeric actions remain
canonical and independently bounded but disabled. The intervention hypothesis
is to pause recipe progress before vulnerable polishing, wait for observed
recovery, finish the interrupted conditioning phase, and then resume.

## Frozen controller contract

The controller binds to the WP12 logistic artifact, target
`SIM_ACTIVE_POLISH_MRR_TRAJECTORY_V1`, 3.0 s horizon, 0.10 s decision cadence,
and declared `DRESSING_WATER_SUPPORT` topology. Exact model, metadata, and
configuration hashes are checked before use.

For calibrated probability \(p_k\) and conformal set \(S_k\), a hold proposal
requires

\[
p_k\ge0.50,\qquad S_k=\{1\},
\]

with valid uncertainty and applicability. Probability at least 0.30 creates an
advisory below the hold gate. Controlled resume requires

\[
p_k\le0.20,\qquad S_k=\{0\},
\]

plus the independent recovery contract.

The finite action tie-break score is

\[
J_k(a)=8p_kr(a)
+\frac{\Delta T_{phase}(a)}{3.0\ \mathrm{s}}
+\frac{\Delta T_{hold}(a)}{3.0\ \mathrm{s}}
+0.1\mathbf 1[a\ne a_{k-1}].
\]

At the frozen hold threshold, continued running scores 4.0 and projected hold
scores 2.1. At the frozen resume threshold, resume scores 1.7 and another full
horizon of hold scores 2.0. These are internally consistent synthetic
tie-breaks, not an optimal-control or physical-benefit result.

## Process clock and anti-gaming rule

Recipe progress follows wall time only in `RUNNING` and is frozen in `HOLDING`
and `RECOVERING`. An interrupted `DRESS` is restored through the already valid
route:

```text
HOLD -> RECOVER -> PREPARE -> DRESS
```

Every paired run must complete the same recipe scope or be reported as a failed
completion after the frozen 10 s extension. MRR is compared at matched
active-polish progress, and cumulative-removal error, hold time, recovery time,
cycle extension, and action effort are mandatory. Holding cannot shorten the
evaluation horizon or turn zero removal into a successful MRR observation.

## Comparator correction from feasibility review

A CMP-only development limiting case used the actual WP08 equations, an
imposed 0--5.99 s loss of dressing availability, and equal completed DRESS and
POLISH durations.

| Case | End-DRESS pad activity | Peak relative MRR deviation | Mean MRR ratio | Hold | Cycle extension |
|---|---:|---:|---:|---:|---:|
| Event-disabled reference | 0.551188 | 0.000% | 1.000000 | 0.00 s | 0.00 s |
| Disturbed no action | 0.500090 | 5.526% | 0.944762 | 0.00 s | 0.00 s |
| Warning-timed hold at 4.29 s | 0.515157 | 3.895% | 0.961057 | 1.70 s | 2.20 s |
| Utility-threshold hold at 0.10 s | 0.550379 | 0.087% | 0.999126 | 5.89 s | 6.39 s |

The warning-timed hold improves peak, integrated, and cumulative-removal error
relative to no action in this one limiting case. The immediate utility
threshold is far better on MRR because a complete service loss is directly
visible long before a three-second process warning, but it holds much longer.

The required three-controller comparison therefore uses a downstream arrived
MRR threshold as its fixed-threshold baseline: ±5% relative to the nominal
phase-progress trajectory with 0.25 s persistence. That is the expected
"action after process threshold crossing" comparator. The upstream utility
threshold remains a mandatory fourth comparator. It may not be omitted, and a
worse predictive result against it must be reported.

This correction was made from a declared Phase 3 development analysis before
any new controller TEST seeds or closed-loop result existed. It does not alter
WP12 evidence or retroactively select a warning model from its TEST ranking.

## Independent safety contract

The safety filter retains all six canonical outcomes and must emit exactly one
final action. It cannot import or call controller implementation. It validates
proposal schema/timing, arrived sensor freshness/quality, model and topology
binding, prediction uncertainty, action/mode compatibility, magnitude, slew,
process envelope, and restart conditions.

Blocking sensor flags are `MISSING`, `DROPPED`, `STUCK`, `BIASED`, `DRIFTING`,
`OUT_OF_RANGE`, `UNIT_UNRESOLVED`, and `INVALID`. Delay is allowed only within
the configured source-age limit. Hold remains reachable under invalid sensing;
invalid sensing cannot authorize numeric actuation or resume.

The utility continuation envelope is [0.90, 1.10] of reference with a 2 K
thermal band. It automatically holds only in `PREPARE` or `POLISH`. During
`DRESS`, utility loss is a modelled conditioning-quality risk rather than a
validated equipment hazard, so a controller may choose hold without the safety
filter preempting the scientific comparison.

Release requires [0.95, 1.05], a 1 K thermal band, 1.0 s continuous validity,
0.50 s warning-clear dwell, minimum 0.50 s hold, and 0.50 s CMP recovery dwell.
The synthetic observed-battery reserve is

\[
1.25\frac{2500\ \mathrm{W}}{0.95}(3.0+0.5)\ \mathrm{s}
=11513.16\ \mathrm{J},
\]

which is positive and below the configured 3.6 MJ capacity.

## Paired success gates

New controller seed ranges begin at 130000 for development, 230000 for primary
TEST, and 330000 for robustness. No WP12/WP13 seed enters controller TEST.
Every primary family receives at least eight independent TEST runs.

Predictive control must improve both median peak and integrated MRR error
against no action with non-negative grouped-bootstrap lower bounds. Against the
primary process-MRR threshold, one MRR metric must improve by at least 5% while
the other and cumulative-removal error are not worse by more than 5%. At least
80% of hold-required runs must be non-worse than no action on both MRR metrics;
negative-control hold rate must not exceed 5%; every result must report cycle
and hold costs; and final constraint violations must be zero.

The utility-threshold comparator receives the identical evaluation but is
reported separately from the primary gate. Thresholds and seeds are not changed
after TEST access if a gate fails.

## Evidence

- `orchestration/decisions/wp15_predictive_supervisory_control.md`
- `orchestration/decisions/wp16_independent_safety_filter.md`
- `configs/controllers/predictive.yaml`
- `configs/controllers/baselines.yaml`
- `configs/controllers/safety.yaml`
- `src/semifab_poc/control/contracts.py`
- `tests/unit/test_control_contracts.py`
- `scripts/validate_phase3_control_contracts.py`
- `scripts/analyze_phase3_hold_feasibility.py`
- `reports/control/phase3_control_contract_validation.json`
- `reports/control/phase3_hold_feasibility.json`

Artifact SHA-256 values:

- predictive contract: `219849ca3aa0abdaccd48db22f81f6ecc4c94ccc3851b757e701cc23a140f265`;
- baseline contract: `d527490e53bc4d665f833a4c78eb6403c4db60fa16aee2d7932b7eafcc9794ec`;
- safety contract: `032bb745401e1b4b8203f5466c213662b61b79fd591c673122ee11612400707c`;
- contract validation: `86e3ab72eedc9898c6f93e9e0a8d29001b6e2fe94d407404f1c15cd66abf3d7a`;
- hold feasibility: `170687de5333fc5a7d8943258d196f979760379b5607a171bb1ce1e2da2da136`.

Focused verification command:

```bash
conda run -n devkki python -m pytest -q -W error tests/unit/test_control_contracts.py
```

Result: 13 passed.

## Claim boundary

The artifacts show that the Phase 3 controller/safety design is explicit,
strictly validated, internally consistent, bounded by current synthetic plant
authority, and has one feasible CMP limiting case. They do not demonstrate an
integrated controller, safety-filter enforcement, robustness, controller
latency, superiority to either threshold comparator, real equipment safety,
physical-defect prevention, yield benefit, or production readiness.
