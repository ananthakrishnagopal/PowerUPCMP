# Failure report

## Task

Update `orchestration/canonical_schema.yaml` from frozen schema 1.0.0 to the
documented R1 schema 2.0.0 implementation candidate.

## Failed command

`apply_patch` combining schema-version, native-unit record, run-provenance,
enumeration, and duplicate-key cleanup edits.

## Error

```text
apply_patch verification failed: Failed to find expected lines in
/home/akki/cmp_modelling/orchestration/canonical_schema.yaml:
      unit: {type: string, required: true}
      unit: {type: string, required: true}
```

No part of the failed patch was applied.

## Files changed before failure

Governance and approval:

- `orchestration/task_manifest.yaml`
- `orchestration/project_status.md`
- `orchestration/reports/phase_3_cmp_model_redesign.md`
- `orchestration/decisions/phase_1_2_remediation.md`

Unvalidated R1 implementation candidate:

- `src/semifab_poc/simulation/base.py`
- `src/semifab_poc/simulation/electrical.py`
- `src/semifab_poc/simulation/drive.py`
- `src/semifab_poc/simulation/pump.py`
- `src/semifab_poc/simulation/upw.py`
- `src/semifab_poc/simulation/sensors.py`
- `src/semifab_poc/simulation/__init__.py`
- `src/semifab_poc/data/schema.py`
- `src/semifab_poc/data/__init__.py`
- `src/semifab_poc/config.py`
- `configs/default.yaml`

No R1 tests have been added or run. These files must not be treated as
validated.

## Read-only diagnosis

Numbered inspection confirms that `canonical_schema.yaml` contains only one
`prediction_record.fields.unit` entry at line 150 and one `fit_scope` mapping
at line 310. A previous combined/truncated terminal display visually repeated
those lines, and the patch incorrectly included duplicate-removal hunks for
duplicates that are not present in the file. The version/native-unit hunks
would otherwise match, but `apply_patch` rejected the whole atomic patch at the
nonexistent duplicate context.

The schema file remains parseable and unchanged at version 1.0.0. This is a
patch-context error, not a schema-design contradiction, test failure,
permission problem, or source-code exception.

## Likely causes

1. A large multi-command inspection output was truncated and repeated adjacent
   context visually.
2. The patch bundled independent valid changes with speculative duplicate-key
   cleanup, so one nonexistent context rejected all changes.

## Recovery options

1. Recommended: apply only the verified schema hunks in small sections, then
   update the interface registry separately, add focused tests, and run import,
   configuration, schema, contract, and full-suite validation in `devkki`.
2. Reconstruct the complete schema file wholesale from code. This is broader
   and risks losing unrelated frozen records.
3. Revert the unvalidated R1 candidate and reconsider the accepted decision.
   No scientific evidence currently requires this.

## Recommended option

Option 1. It is narrow, reversible, and directly addresses the transport error
without changing the approved R1 design.

## User decision required

Authorize recovery option 1. Until then, stop all R1 edits and tests and treat
the current source changes as unvalidated work in progress.

## Resolution

The user authorized option 1. The verified schema and interface changes were
applied as independent patches. The R1 import/configuration smoke check passed,
21 focused tests passed, and the complete suite passed 70/70 with the one known
PHM pandas FutureWarning assigned to R2. Canonical schema and
DynamicSubsystem are frozen at 2.0.0, and R1 is validated. The patch transport
failure is resolved.
