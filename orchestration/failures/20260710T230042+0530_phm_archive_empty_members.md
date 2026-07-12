# Failure report

## Task

T-DATA-FETCH dry-run validation of the user-supplied PHM CMP archive.

## Failed command

```text
conda run -n devkki python scripts/fetch_data.py
```

Exit code: `2`.

## Error

The validator stopped at the first selected empty CSV:

```text
fetch error: CSV member has no data rows: PHM-Data-Challenge-master/data/2016 PHM Data Challenge/2016 PHM DATA CHALLENGE CMP DATA SET/CMP-data/test/CMP-test-008.csv
```

The member contains the expected 25-column header but no data rows.

## Files changed before failure

- `orchestration/data_sources.yaml` was updated to record the user authorization and archive checksum.
- `src/semifab_poc/data/fetch.py`, `scripts/fetch_data.py`, and `tests/unit/test_fetch_data.py` were created.
- `orchestration/task_manifest.yaml` marked T-DATA-FETCH `IN_PROGRESS`.
- `orchestration/project_status.md` recorded the active fetch task.
- No archive members were extracted and no data/raw files were created.

## Read-only diagnosis

- Archive identity and ZIP CRC integrity passed before CSV validation.
- `CMP-test-008.csv` is 462 bytes and contains only the header row.
- A read-only scan of the selected `CMP-data` test/training subset found 31 header-only files, including multiple test files; the full selected set was not allowed to proceed.
- No answer table or derived experiment was selected before the failure.
- The failure is a source-data schema/content issue, not a network or dependency issue.

## Likely causes

The user-supplied GitHub-derived archive contains empty test traces for some wafer identifiers. These may represent intentionally absent test measurements, a flawed redistribution, or incomplete extraction; their semantics cannot be inferred safely.

## Recovery options

1. User confirms that header-only files should be retained as valid empty traces; revise the canonical loader contract to record them explicitly as missing traces and quantify counts by split.
2. User provides a corrected archive/source in which all required series contain rows.
3. Keep the archive quarantined and use only non-empty training/validation files after a documented exclusion policy; this changes the expected 185-file completeness claim and requires impact analysis.
4. Skip the affected files silently; not permitted.

## Recommended option

Option 1 if the PHM challenge format intentionally permits empty test traces; otherwise Option 2. The project must not silently drop files or impute missing traces.

## User decision required

Confirm how the 31 header-only selected files should be treated, or provide a corrected archive. No extraction occurred.
