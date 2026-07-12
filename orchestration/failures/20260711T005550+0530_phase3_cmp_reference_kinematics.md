# Failure report

## Task

Pre-implementation scientific review of the frozen T-WP08 CMP reference
kinematics.

## Failed command

Read-only review of the selected Phase 3 decision record:

    rg -n -C 2 "effective spatial|Nominal head|yielding"
    orchestration/decisions/20260711_phase_3_cmp_and_utility_model.md

## Error

The decision record states an effective spatial-average radius of 6.496 mrad
and nominal head and platen speeds of 60 and 90 rad/s while claiming a
relative velocity of 1.0 m/s. The declared relation is:

    V_rel = r_eff (omega_head + omega_platen).

The stated numbers yield 0.9744 in the inconsistent unit mrad times rad/s, not
1.0 m/s. An effective radius must be a length. The nominal relation requires
6.6666667e-3 m, or a different documented speed pair.

## Files changed before failure

- orchestration/decisions/20260711_phase_3_cmp_and_utility_model.md was created
  and received the previously authorized one-line wording correction.
- orchestration/task_manifest.yaml was updated to mark T-WP08 in progress.
- orchestration/project_status.md was updated to start Phase 3.
- orchestration/failures/20260711T005428+0530_phase3_decision_record_patch_context.md
  was added for the prior resolved documentation-patch issue.

No CMP source, test, configuration, dataset, or runtime code was created or
modified. No numerical experiment was run.

## Read-only diagnosis

- The model form is dimensionally valid only when r_eff has unit m.
- With 60 plus 90 rad/s, the reference radius needed for 1.0 m/s is exactly
  1/150 m, or 6.6666667 mm.
- The intended nominal Preston coefficient remains 5.0e-12 Pa^-1 if the
  documented 1.0 m/s reference velocity is retained.
- The error is isolated to the decision-record numerical/unit statement and
  does not change the selected baseline form, parameter provenance, or
  scientific claim boundary.

## Likely causes

1. A preliminary effective-radius estimate was written without checking it
   against the selected nominal angular-speed pair.
2. A length unit was accidentally written as an angular unit.

## Recovery options

1. Correct the decision record to use r_eff = 6.6666667e-3 m with the existing
   60 and 90 rad/s nominal speeds, then implement and test that exact
   reference case.
2. Retain 6.496e-3 m and revise one or both nominal speeds so their sum is
   consistent with 1.0 m/s, then recompute and document the reference case.
3. Defer kinematic derivation and require directly supplied relative velocity.
   This would weaken the explicit head/platen-speed support requested for
   T-WP08.

## Recommended option

Option 1. It is the smallest correction, preserves all selected nominal CMP
values, restores dimensional consistency, and makes the reference test exact.

## User decision required

Authorize correction of the reference effective radius to 6.6666667e-3 m and
resumption of T-WP08 implementation.
