# Failure report

## Task

Validate R2 PHM source-order timing, phase-aware feature engineering, anomaly
policies, and official split isolation against the locally verified dataset.

## Failed command

```text
conda run -n devkki python -m pytest -q tests/integration/test_phm_pipeline.py
```

## Error

```text
FAILED test_real_data_semantic_audit_records_known_timing_and_regime_limits
assert training["negative_timestamp_increment_count"] == 0
E assert 3 == 0

1 failed, 5 passed in 40.15s
```

## Files changed before failure

Validated R1 completion records:

- `orchestration/reports/r1_contract_configuration_validation.md`
- `orchestration/canonical_schema.yaml`
- `orchestration/interface_registry.yaml`
- `docs/modeling_notes.md`
- `data/README.md`
- `orchestration/architecture.md`
- `docs/architecture.md`
- `README.md`
- `docs/running_paper.md`
- `orchestration/task_manifest.yaml`
- `orchestration/project_status.md`
- `orchestration/failures/20260711T103852+0530_r1_schema_registry_patch_context.md`

Unvalidated R2 candidate:

- `orchestration/decisions/r2_phm_semantics.md`
- `src/semifab_poc/data/phm_semantics.py`
- `src/semifab_poc/data/phm_cmp.py`
- `src/semifab_poc/data/splits.py`
- `src/semifab_poc/data/__init__.py`
- `src/semifab_poc/data/audit.py`
- `configs/data/phm_2016_cmp.yaml`
- `tests/unit/test_phm_cmp.py`
- `tests/unit/test_splits.py`
- `tests/integration/test_phm_pipeline.py`

The small R2 unit suite passed 13/13 before the real-data failure. The real-data
integration suite passed five tests and failed one. No full suite was run after
the R2 changes.

## Read-only diagnosis

The R2 implementation deliberately preserves `SOURCE_ROW_INDEX` and computes
timestamp increments in original source order. It correctly found three
training and two validation reversals:

| Split | Trace | Source row | Wafer | Stage | Delta (s) |
|---|---|---:|---|---|---:|
| training | CMP-training-067 | 1044 | 4223773480 | A | -6.0 |
| training | CMP-training-073 | 1625 | -4019511766 | B | -2804.0 |
| training | CMP-training-073 | 1796 | -4019511766 | B | -2820.0 |
| validation | CMP-validation-162 | 150 | 2070207730 | A | -2392.0 |
| validation | CMP-validation-162 | 260 | 2070207730 | A | -2402.666 |

Each reversal starts a new continuity segment and contributes no time weight
across the reversed boundary. Test data contain zero negative increments.

The earlier audit diagnostic that reported zero negatives sorted rows by
timestamp before differencing, which necessarily hid source-order reversals.
The integration test copied that incorrect expectation. This is therefore a
demonstrably incorrect test assertion and an additional real-data quality
finding, not an implementation contradiction or numerical instability.

## Likely causes

1. The prereview timestamp diagnostic sorted by timestamp rather than retaining
   original row order.
2. The R2 test expectation was derived from that sorted diagnostic instead of
   the new source-order contract.
3. Two traces contain repeated timestamp blocks or acquisition-order resets
   that only become visible when `SOURCE_ROW_INDEX` is preserved.

## Recovery options

1. Recommended: correct the real-data expectations to three training, zero
   test, and two validation reversals; add the exact reversal rows to the
   semantic audit; retain the current new-segment/zero-cross-boundary-weight
   behavior; regenerate reports; rerun the integration and full suites.
2. Sort each group by timestamp before semantic processing. This would make the
   test pass but destroy source-order evidence and can interleave acquisition
   blocks, so it is not scientifically acceptable.
3. Drop reversal rows. This would alter raw evidence without an established
   correction rule and is not justified.

## Recommended option

Option 1. The test is demonstrably incorrect, while the implementation follows
the approved R2 source-order and continuity policy.

## User decision required

Authorize option 1 so the test/report expectation can be corrected and R2
validation can resume. Until then, preserve the R2 candidate without further
mutation or test retries.

## Resolution

The user authorized option 1. The semantic report now includes every exact
source-order reversal, and the corrected integration expectations require
three training, zero test, and two validation reversals. The R2 integration
suite passed 6/6, the full repository suite passed 82/82 without warnings, and
the reversal/new-segment behavior is retained. The incorrect-test failure is
resolved.
