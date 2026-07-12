# Failure report

## Task

Generate deterministic WP10 full-chain, sensitivity, and mismatch evidence with `scripts/validate_wp10_coupling.py`.

## Failed command

```text
conda run -n devkki python scripts/validate_wp10_coupling.py
```

## Error

```text
semifab_poc.simulation.electrical.ElectricalModelError:
battery energy is outside configured bounds
```

The exception occurred in `ElectricalSubsystem.step()` during the declared synthetic degraded-UPS interruption, before any WP10 evidence file was written.

## Files changed before failure

- Corrected the thermal null in `orchestration/decisions/wp10_utility_cmp_coupling.md`.
- Added `src/semifab_poc/simulation/coupling.py`.
- Updated `src/semifab_poc/config.py`, `src/semifab_poc/simulation/__init__.py`, and `src/semifab_poc/data/schema.py`.
- Updated `configs/default.yaml` and added four files under `configs/coupling/`.
- Updated `orchestration/canonical_schema.yaml` and `orchestration/interface_registry.yaml`.
- Updated `scripts/validate_wp08_cmp.py` for the frozen WP08 hash guard.
- Added `tests/unit/test_coupling.py` and `tests/property/test_coupling_properties.py`; updated configuration and interface tests.
- Added `scripts/validate_wp10_coupling.py`.

Focused coupling/config/interface tests passed 35/35 before the evidence run. No `reports/sensitivity/wp10*` artifact exists; the validation script writes only after all scientific checks complete.

## Read-only diagnosis

The synthetic override used 500 J initial capacity, 2500 W load, 10 ms steps, and 0.95 inverter efficiency. Per-step draw is

```text
2500 * 0.01 / 0.95 = 26.315789473684212 J.
```

Nineteen floating-point subtractions from 500 J produce

```text
-1.4921397450962104e-13 J
```

rather than exact zero. The existing depletion branch checks whether required energy is greater than available energy plus `1e-12`. The final difference is smaller than that tolerance, so the code enters the subtraction branch and then validates a tiny negative energy against the hard lower bound. This is an exact-boundary numerical bug in the upstream electrical model, not coupling instability.

## Likely causes

- The comparison uses an absolute tolerance but the subsequent subtraction is not projected to the configured minimum.
- Exact-capacity depletion was not included in the R3 boundary tests; prior tests used a non-exact remainder and transitioned to bypass before subtraction crossed the bound.

## Recovery options

1. Preserve the existing depletion decision and clamp the subtraction result to `minimum_battery_energy_j`; add an exact-multiple boundary test, rerun focused electrical/R3/WP10 tests, regenerate R3 evidence, and then retry WP10 evidence.
2. Change the WP10 synthetic battery capacity to a non-multiple such as 510 J. This avoids the trigger but leaves the upstream invariant bug unresolved.
3. Use a forced-bypass scenario rather than energy depletion. This weakens the intended causal demonstration and also leaves the bug unresolved.

## Recommended option

Option 1. It is a minimal numerical-boundary correction: an exactly exhausted interval ends at the allowed minimum, and the next unsupported interval transitions to bypass. It changes no frozen interface, physical equation, parameter, or primary claim. The R3 regression and evidence must nevertheless be rerun because upstream behavior is touched.

## User decision required

Authorize Option 1: fix exact-boundary battery projection, add regression coverage, rerun R3 validation, and then resume WP10 evidence generation.
