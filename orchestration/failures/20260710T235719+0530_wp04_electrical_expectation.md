# Failure report

## Task

T-WP04 electrical/UPS model unit and integration tests.

## Failed command

```text
conda run -n devkki python -m pytest
```

Exit code: `1`.

## Error

One new test failed:

```text
tests/unit/test_electrical.py::test_voltage_sag_transfers_then_reaches_battery
assert 0.91394304 == 1.0 ± 0.05
```

Test summary: 32 passed, 1 failed, 33 collected. The existing PHM integration test emitted one pandas FutureWarning but did not fail.

## Files changed before failure

- `orchestration/task_manifest.yaml` closed T-WP03 and promoted plant tasks.
- `orchestration/project_status.md` recorded T-WP04 as active.
- `docs/modeling_notes.md` recorded draft state equations and provenance.
- `src/semifab_poc/simulation/electrical.py` implemented the bounded electrical/UPS model.
- `src/semifab_poc/simulation/__init__.py` exported the model.
- `tests/unit/test_electrical.py` added six electrical tests.
- The T-WP03 loader, report, and running-paper files were already present.

No files were changed after the failing test.

## Read-only diagnosis

- The state-machine transition passed: a 0.70 pu sag enters `TRANSFER` and reaches `BATTERY` after the configured delay.
- The first-order output equation is applied with `dt_s=0.01 s` and `tau_output=0.05 s`; after the tested sequence, the output is 0.91394304 pu while converging toward the 1.0 pu battery target.
- The test expected near-nominal output too early and did not account for the declared first-order lag.
- Other electrical tests passed, including normal convergence, recovery dwell, frequency bounds, invalid timestep/mode rejection, and threshold validation.

## Likely causes

The test expectation was written as if UPS transfer immediately restored nominal voltage, while the modeling notes explicitly define a first-order output response. This is a scientific-test expectation conflict, not a syntax or dependency failure.

## Recovery options

1. Keep the first-order lag and revise the test to assert bounded transient behavior, then add a later-time convergence assertion.
2. Change the model to instantaneous battery output; this would contradict the documented first-order equation and alter disturbance timing.
3. Reduce the output time constant; this is a parameter decision requiring provenance and sensitivity evidence.

## Recommended option

Option 1. Preserve the documented dynamic equation, test the transient range and eventual convergence separately, and record the rationale in `docs/modeling_notes.md`.

## User decision required

Confirm that I may apply Option 1, update the electrical test expectation and detailed modeling note, rerun the full suite, and continue T-WP04.
