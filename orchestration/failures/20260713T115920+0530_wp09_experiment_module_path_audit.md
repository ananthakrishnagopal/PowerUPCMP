# Failure report

## Task

Choose the repository location for WP09 experiment orchestration after the
core model and feature-only tests passed.

## Failed command

```text
rg --files src/semifab_poc/evaluation src/semifab_poc | sort | sed -n '1,220p'
```

## Error

```text
rg: src/semifab_poc/evaluation: No such file or directory (os error 2)
```

## Files changed before failure

- `src/semifab_poc/models/virtual_metrology.py`
- `tests/unit/test_virtual_metrology.py`
- `tests/integration/test_vm_evaluation.py`
- the T-WP09 state/status updates in `orchestration/task_manifest.yaml` and
  `orchestration/project_status.md`

These changes passed syntax and whitespace preflight. The 17-test focused WP09
suite passed in 6.30 s. No official holdout MRR target was accessed. This
failure report is the only post-failure mutation.

## Read-only diagnosis

The package currently contains `data`, `models`, and `simulation` modules but
no `src/semifab_poc/evaluation` directory. The command supplied that inferred
nonexistent path as a direct `rg --files` operand even though the valid
`src/semifab_poc` root was also supplied. The existing, task-owned
`src/semifab_poc/models` directory is verified.

## Likely causes

The path-preflight command itself included an unverified candidate directory,
contrary to the newly recorded rule to search from a known existing root.

## Recovery options

1. Continue the bounded WP09 experiment logic in the verified task-owned
   `src/semifab_poc/models/virtual_metrology.py`, with the thin entry point in
   `scripts/validate_wp09_virtual_metrology.py`.
2. Deliberately create a new `evaluation` package and update task ownership and
   architecture before continuing.
3. Pause WP09.

## Recommended option

Option 1. It follows the frozen task ownership, avoids an unnecessary package
decision, and keeps the one-shot runner thin while retaining core logic under
`src/`.

## User decision required

Authorize Option 1 before further implementation.
