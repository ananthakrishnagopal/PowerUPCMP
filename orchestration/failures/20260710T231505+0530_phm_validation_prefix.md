# Failure report

## Task

T-DATA-FETCH full archive dry-run after the approved empty-trace policy.

## Failed command

```text
conda run -n devkki python scripts/fetch_data.py
```

Exit code: `2`.

## Error

```text
fetch error: validation CSV index set mismatch: expected 0..184, got []
```

## Files changed before failure

- `orchestration/data_sources.yaml` recorded the user-approved empty-trace policy and local archive metadata.
- `src/semifab_poc/data/fetch.py` now retains header-only time-series files as `empty_trace: true`.
- `data/README.md` documents the missing-trace policy.
- `tests/unit/test_fetch_data.py` gained an empty-trace test.
- `orchestration/task_manifest.yaml` remains `IN_PROGRESS` for T-DATA-FETCH.
- No archive members were extracted.

## Read-only diagnosis

- The archive contains validation files at:

  ```text
  PHM-Data-Challenge-master/data/2016 PHM Data Challenge/2016 PHM DATA CHALLENGE CMP VALIDATION DATA SET/validation/CMP-validation-000.csv
  ```

- The registry prefix currently contains an erroneous extra `2016 PHM DATA CHALLENGE CMP DATA SET/` segment before `CMP VALIDATION DATA SET/validation/`.
- Consequently, the validator selected training/test members but selected zero validation members; it correctly rejected the incomplete set before extraction.
- The archive itself is unchanged and the validation path is unambiguous.

## Likely causes

A path transcription error in `orchestration/data_sources.yaml` while recording the archive’s separate validation-tree layout.

## Recovery options

1. Correct the registry prefix to the exact archive path, rerun the full dry-run, and extract only after all 185 validation members and three removal tables validate.
2. Remove validation from the source contract; not acceptable because validation is a required PHM dataset split.
3. Select validation through a broad wildcard; not acceptable because exact source prefixes are required for provenance and exclusion safety.

## Recommended option

Option 1. This is a bounded registry correction supported by direct archive listing evidence.

## User decision required

Confirm that I may correct the single validation-prefix typo, rerun the dry-run, and proceed to extraction if the complete selected set validates.
