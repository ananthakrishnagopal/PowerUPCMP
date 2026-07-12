# Failure report

## Task

T-WP03 final read-only artifact/status inspection after loader and report generation.

## Failed command

```text
ls -lh reports/data/phm_missingness.json configs/data/phm_2016_cmp.yaml src/semifab_poc/data/phm_cmp.py scripts/audit_phm.py 2>/dev/null
```

Exit code: `2`.

## Error

The command included `scripts/audit_phm.py`, which does not exist. The report generator is intentionally implemented as the package module `semifab_poc.data.audit` and is invoked with:

```text
conda run -n devkki python -m semifab_poc.data.audit
```

## Files changed before failure

- T-WP03 loader, audit, configuration, and tests were created.
- `reports/data/phm_missingness.json` was generated successfully.
- No source files were changed after the failed diagnostic command.

## Read-only diagnosis

- `conda run -n devkki python -m pytest` passed all 27 tests, including the real extracted PHM integration tests.
- The audit command completed successfully and wrote `reports/data/phm_missingness.json`.
- The failed command was only a file-listing convenience check; its nonzero exit came from the nonexistent optional wrapper path, not from loader, schema, join, split, or report logic.

## Likely causes

The final inspection command assumed a wrapper script that was not part of the T-WP03 outputs; the implementation uses a module entry point instead.

## Recovery options

1. Treat the passing tests and successful audit command as the T-WP03 evidence and continue status updates.
2. Add a `scripts/audit_phm.py` wrapper, rerun the listing command, and add another file to the task scope.
3. Rerun only a corrected read-only listing command.

## Recommended option

Option 1. The task’s declared outputs require `src/semifab_poc/data/phm_cmp.py`, config, report, and tests; the package audit module satisfies report generation, and all acceptance tests passed.

## User decision required

Confirm whether to accept the successful T-WP03 evidence and proceed with task/status updates, or require an additional wrapper/listing check.
