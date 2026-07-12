# Failure report

## Task

Validate T-WP05 bounded VFD, motor, and pump dynamics.

## Failed command

`conda run -n devkki python -m pytest tests/unit/test_drive.py tests/unit/test_pump.py tests/property/test_pump_affinity.py -q`

## Error

One test failed (`1 failed, 8 passed`). `test_vfd_command_and_motor_speed_are_bounded` expected the motor speed to be within 1 rad/s of 188.5 rad/s after 100 steps of 0.01 s. The observed speed was 187.03184514982624 rad/s.

## Files changed before failure

- `src/semifab_poc/simulation/drive.py`
- `src/semifab_poc/simulation/pump.py`
- `src/semifab_poc/simulation/__init__.py`
- `tests/unit/test_drive.py`
- `tests/unit/test_pump.py`
- `tests/property/test_pump_affinity.py`

The import-only cleanup in `tests/unit/test_drive.py` removed an unused `UpsMode` import before this test run; no model code was changed after the failure.

## Read-only diagnosis

The drive uses the explicit first-order motor equation

`dω/dt = (ω_target − ω)/τ_m`

with `τ_m = 0.20 s`, `dt = 0.01 s`, and target `ω_target = 188.5 rad/s`. One second is five time constants, so the analytic residual is approximately `exp(-5) × 188.5 = 1.27 rad/s`; the observed explicit-Euler residual of 1.47 rad/s is expected from the discretisation. The state remains bounded and monotonic.

## Likely causes

1. The acceptance assertion assumes a tighter convergence time than the configured five time constants provide.
2. The model or timestep could be changed to converge faster, but that would alter the documented transient assumption and is not necessary for the stated boundedness requirement.

## Recovery options

1. Update the test tolerance to reflect the documented five-time-constant transient, for example ±2 rad/s, or run the convergence test for 120–140 steps.
2. Change the motor time constant or use an exact discrete-time update; this would require a modelling decision and update to `docs/modeling_notes.md`.

## Recommended option

Option 1: retain the documented first-order explicit-Euler model and relax the convergence assertion to a physically justified bound. Add a separate monotonicity/boundedness assertion so the test does not overclaim steady state.

## User decision required

Approve updating the test acceptance bound or test horizon. No further T-WP05 mutation will be performed until directed.

## Resolution

The user approved a retry on 2026-07-11. The first-order model was retained and the convergence-test horizon was extended from 1.0 s to 1.4 s (seven time constants), preserving the original ±1 rad/s assertion. Focused tests then passed 9/9 and the full suite passed 44/44. See `orchestration/reports/wp05_drive_pump_validation.md`.
