# Failure report

## Task

T-DATA-FETCH full archive dry-run after the user-approved registry-prefix correction.

## Failed command

```text
conda run -n devkki python scripts/fetch_data.py
```

Exit code: `2`.

## Error

```text
fetch error: selected member is not a recognized CMP raw file: PHM-Data-Challenge-master/data/2016 PHM Data Challenge/2016 PHM DATA CHALLENGE CMP VALIDATION DATA SET/validation/CMP-validation-000.csv
```

## Files changed before failure

- `orchestration/data_sources.yaml` was corrected with the user-approved validation prefix.
- Earlier T-DATA-FETCH implementation, tests, and failure reports remain present.
- No archive members were extracted.

## Read-only diagnosis

- The corrected registry prefix now selects the validation members.
- The output mapper in `src/semifab_poc/data/fetch.py` expects a separate path segment `/CMP VALIDATION DATA SET/validation/`.
- The actual archive directory is one segment named `2016 PHM DATA CHALLENGE CMP VALIDATION DATA SET/validation/`; therefore the mapper rejects the selected member before CSV validation.
- A direct string check confirmed the mapper substring is absent from the actual archive name.

## Likely causes

The archive uses a different validation-directory naming convention from the one encoded in the mapper. The registry prefix and mapper were corrected independently and are not yet aligned.

## Recovery options

1. Correct the mapper to match the exact archive directory and rerun the dry-run.
2. Drop validation members; not acceptable because validation is a required dataset split.
3. Use a broad path rewrite; not acceptable because extraction provenance must remain explicit.

## Recommended option

Option 1. This is a bounded path-mapping correction supported by the exact archive member name.

## User decision required

Confirm that I may correct the validation output mapper, rerun the complete dry-run, and proceed to extraction if all selected members validate.
