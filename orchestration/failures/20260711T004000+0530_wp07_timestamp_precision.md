# Failure report

## Task

Validate T-WP07 deterministic sensor and communication model.

## Failed command

conda run -n devkki python -m pytest tests/unit/test_sensors.py tests/property/test_sensor_state_separation.py -q

## Error

One test failed and five passed. The delay assertion compared floating-point subtraction directly to 0.02. The observed timestamps were 0.998775927324286 and 1.018775927324286, whose difference is conceptually 0.02 but not bitwise equal in binary floating-point arithmetic.

## Files changed before failure

- orchestration/task_manifest.yaml
- src/semifab_poc/simulation/sensors.py
- src/semifab_poc/simulation/__init__.py
- tests/unit/test_sensors.py
- tests/property/test_sensor_state_separation.py

## Read-only diagnosis

The sensor model applies arrival time as observed timestamp plus configured delay. The test failure is a direct-equality precision expectation, not a mismatch in the model relation or a latent-state mutation.

## Likely causes

1. Decimal 0.02 is not represented exactly in binary floating point.
2. The timestamp-jittered observed value makes subtraction expose that representation difference.

## Recovery options

1. Change the assertion to a numeric approximate comparison while retaining the 0.02 second configured delay.
2. Remove timestamp jitter from the combined test, which would reduce coverage of the required explicit jitter behavior.

## Recommended option

Option 1. Use an approximate assertion for delay equality and retain the combined delay and jitter test.

## User decision required

Approve the test-only precision correction. No sensor-model parameter or interface change is proposed.

## Resolution

The user approved the test-only correction on 2026-07-11. The assertion now
uses an approximate comparison for the configured 0.02 s delay. Focused tests
passed 6/6 and the full suite passed 56/56. The sensor model was not changed.
