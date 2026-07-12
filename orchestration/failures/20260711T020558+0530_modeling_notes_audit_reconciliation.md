# Failure report

## Task

Reconcile `docs/modeling_notes.md` with the completed Phase 1/2 scientific
audit and the proposed Phase 3 CMP redesign.

## Failed command

`apply_patch` updating the audit disposition, pump/UPW/sensor/scenario notes,
T-WP08 equations, and coupling ledger in `docs/modeling_notes.md`.

## Error

```text
apply_patch verification failed: Failed to find expected lines in
/home/akki/cmp_modelling/docs/modeling_notes.md:
network, clock-synchronisation
system, or production historian.
```

No portion of the failed patch was applied.

## Files changed before failure

- `orchestration/decisions/20260711_phase_3_cmp_and_utility_model.md`
- `orchestration/task_manifest.yaml`
- `orchestration/project_status.md`
- `orchestration/risk_register.md`
- `orchestration/assumptions.yaml`
- `orchestration/data_sources.yaml`
- `orchestration/implementation_plan.md`
- `README.md`
- `docs/running_paper.md`

The previously created audit reports remain unchanged:

- `orchestration/reports/phase_1_2_scientific_audit.md`
- `orchestration/reports/phase_3_cmp_model_redesign.md`

## Read-only diagnosis

The patch used an incomplete wrapping context around the sensor limitation
paragraph. The actual first line is:

```text
approximation; it does not represent a certified network, clock-synchronisation
```

The failed patch expected a line beginning only with
`network, clock-synchronisation`. The file is readable and has not changed
since inspection. This is a patch-transport/context error, not a scientific,
schema, test, permission, or repository-content conflict.

## Likely causes

1. The proposed multi-section patch used a shortened context fragment that did
   not exactly match the Markdown line wrapping.
2. Combining several distant edits in one patch made one context mismatch
   reject the entire otherwise independent update.

## Recovery options

1. Recommended: apply small, independently verified patches at exact section
   headings, then read back the mathematical notation, parse all YAML, validate
   the task graph, and run the full `devkki` test suite.
2. Replace `docs/modeling_notes.md` wholesale after separately preserving its
   as-built component evidence. This is higher risk and unnecessary.
3. Leave the technical ledger stale and rely only on the two audit reports and
   running paper. This creates avoidable contradictory documentation.

## Recommended option

Option 1. It is the narrowest reversible recovery and preserves the historical
component notes while clearly marking them provisional.

## User decision required

Authorize recovery option 1 so the documentation reconciliation and remaining
read-only validation can resume.

## Resolution

The user authorized option 1. The ledger was reconciled through small exact
patches without replacing historical component evidence. Subsequent validation
found eight parseable YAML files, 27 valid task records, 25 resolved assumption
references, an acyclic task graph, zero missing local links across 46 Markdown
files, and 60/60 passing baseline tests in `devkki` with one known pandas
FutureWarning. The transport failure is resolved; scientific remediation gates
R1--R4 remain intentionally open.
