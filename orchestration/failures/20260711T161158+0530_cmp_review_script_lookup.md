# Failure report

## Task

Read-only contract and validation review before T-WP08 CMP-model freeze.

## Failed command

```text
sed -n '1,360p' scripts/validate_r4_timing.py
```

## Error

```text
sed: can't read scripts/validate_r4_timing.py: No such file or directory
```

## Files changed before failure

None in this turn.

## Read-only diagnosis

The R4 validation script exists as
`scripts/validate_r4_timing_scenarios.py`. The failed lookup used an inferred,
shorter filename; it did not indicate missing R4 validation evidence or a
runtime defect. The associated artifacts remain referenced as
`reports/timing/r4_validation.json` and
`reports/timing/r4_sensor_delivery_trace.csv`.

## Likely causes

The inspection command used an incorrect filename rather than discovering the
script path from the repository file list.

## Recovery options

1. Resume the CMP review using the discovered
   `scripts/validate_r4_timing_scenarios.py` path.
2. Skip re-reading that script because the frozen R4 report and artifacts are
   already present.
3. Rename or duplicate the script; this is not recommended because it would
   create unnecessary repository churn.

## Recommended option

Option 1. It is read-only, preserves the existing repository convention, and
allows the CMP contract impact review to continue with direct evidence.

## User decision required

Authorize resuming T-WP08 with the corrected script path.
