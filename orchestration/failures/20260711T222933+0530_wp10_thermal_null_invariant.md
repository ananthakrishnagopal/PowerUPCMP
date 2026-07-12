# Failure report

## Task

T-WP10 scientific freeze and implementation of the utility-to-CMP coupler.

## Failed command

No shell command failed. The failure was detected during pre-implementation invariant review of the frozen thermal-loop equation:

```text
T_c = T_0 + lambda * (T_upw - T_0)
```

## Error

The decision also placed `T_0` in an uncertainty/sensitivity range. If `T_0` is varied independently of the CMP subsystem's neutral coolant temperature, then `lambda = 0` yields `T_c = T_0` rather than the exact neutral CMP boundary. This contradicts the mandatory zero-link structural-null invariant.

## Files changed before failure

- `orchestration/task_manifest.yaml`: T-WP10 moved through READY to IN_PROGRESS and its scientific blocker was cleared.
- `orchestration/project_status.md`: active task updated to T-WP10.
- `orchestration/reports/wp10_literature_review.md`: local ten-paper evidence review created.
- `orchestration/decisions/wp10_utility_cmp_coupling.md`: initial WP10 freeze decision created; its thermal equation requires correction before implementation.

No source code, runtime configuration, schema, interface, tests, or result artifacts were changed.

## Read-only diagnosis

The hydraulic availability and dressing/slurry topology maps retain their exact nulls. The conflict is isolated to the thermal reference definition. Two physical reference temperatures were conflated:

- `T_cmp,0`: the CMP subsystem's neutral coolant boundary; and
- `T_upw,ref`: the nominal/reference UPW temperature used to express a utility temperature deviation.

The null-preserving map should distinguish them:

```text
T_c = T_cmp,0 + lambda * (T_upw - T_upw,ref)
```

Then `lambda = 0` is exactly neutral for every UPW state, and nominal UPW temperature is neutral for every link strength. The mapped value must still be rejected if it leaves the configured CMP thermal envelope.

## Likely causes

- The same symbol was used for the physical CMP boundary reference and the uncertain upstream utility reference.
- The equation was individually neutral at the nominal default, so the conflict appeared only when the preregistered parameter sensitivity was considered.

## Recovery options

1. Amend the decision to distinguish `T_cmp,0` from `T_upw,ref`, use `T_c = T_cmp,0 + lambda * (T_upw - T_upw,ref)`, and continue implementation.
2. Require the coupling temperature reference to equal the CMP reference and remove it from sensitivity analysis.
3. Remove `THERMAL_LOOP` from WP10 and defer all thermal plumbing to future work.

## Recommended option

Option 1. It preserves both structural nulls, keeps the conditional thermal topology scientifically explicit, and requires no change to the frozen `CmpBoundaryConditions` field set or `DynamicSubsystem` interface.

## User decision required

Authorize the null-preserving thermal-reference correction in Option 1 before WP10 implementation continues.
