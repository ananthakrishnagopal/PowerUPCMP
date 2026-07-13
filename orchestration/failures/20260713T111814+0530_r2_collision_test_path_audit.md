# Failure report

## Task

Read-only inspection before implementing the authorized R2 official-wafer
collision remediation.

## Failed command

```text
sed -n '1,100p' src/semifab_poc/data/audit.py; sed -n '520,700p' src/semifab_poc/data/phm_semantics.py; sed -n '1,220p' tests/unit/test_phm_semantics.py
```

## Error

```text
sed: can't read tests/unit/test_phm_semantics.py: No such file or directory
```

## Files changed before failure

- `orchestration/failures/20260713T110328+0530_wp09_manifest_path_audit.md`
- `orchestration/failures/20260713T111332+0530_wp09_official_wafer_collision.md`

No R2 remediation code, test, report, configuration, data, or WP09 artifact was
changed. This failure report is the only new file created after the error.

## Read-only diagnosis

`rg --files tests/unit` confirms the relevant existing files are:

```text
tests/unit/test_phm_cmp.py
tests/unit/test_splits.py
```

There is no separate `test_phm_semantics.py`. Semantic tests are colocated in
the existing PHM and integration test modules.

## Likely causes

The inspection command inferred a conventional filename that this repository
does not use instead of first resolving the path with `rg --files`.

## Recovery options

1. Inspect `tests/unit/test_phm_cmp.py`, then implement the already authorized
   collision remediation in the existing split/PHM test structure.
2. Create a new semantic test module solely to match the assumed name; this
   adds no scientific value and is not recommended.
3. Leave the remediation paused.

## Recommended option

Option 1. Reuse the repository's established test organization and continue
the authorized correction.

## User decision required

Authorize Option 1 before further mutation.
