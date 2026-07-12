# R1 contract and configuration validation

Date: 2026-07-11  
Task: T-PHASE12-REMEDIATION, subgate R1  
Disposition: VALIDATED

## Scope

R1 corrects the Phase 1 schema/interface mismatch and supplies a complete,
strict, provenance-aware runtime configuration. It does not change the
electrical, drive, pump, UPW, sensor, or scenario equations.

The approved change and impact analysis are recorded in
`orchestration/decisions/phase_1_2_remediation.md`.

## Canonical schema 2.0.0

`PublicMeasurementRecord` now preserves four distinct facts:

1. the original public numeric value;
2. whether its source unit is declared, native-but-undeclared, or unknown;
3. an optional canonical value/unit; and
4. the explicit conversion ID when a supported conversion exists.

The PHM MRR target can therefore be represented as
`PHM_NATIVE_UNDECLARED`, with `UNIT_UNRESOLVED` and null canonical fields,
without falsely assigning m/s and without marking an available value missing.
Canonical conversion is rejected unless the source unit is declared, the
canonical unit matches the signal catalog, and a conversion ID is supplied.

`RunManifest` now requires at least one non-empty
`parameter_provenance_ids` entry. The change is a deliberate major schema
revision; version-1 records are not silently coerced.

## DynamicSubsystem 2.0.0

`src/semifab_poc/simulation/base.py` defines the common stateful-config
abstract base. Electrical, drive, pump, and UPW subsystems explicitly inherit
it and provide the common methods:

```text
reset(initial_state=None) -> State
step(state, action, disturbance, dt_s) -> State
```

Every component configuration is frozen and carries a validated non-empty
`provenance_id`. Contract tests confirm all four implementations return a new
state without mutating the supplied state.

Observation is deliberately not a plant method. `SensorModel.sample` remains
the sole boundary that owns run ID, source step/time, sampling state,
corruption, and communication state. This resolves the former interface
contradiction without embedding sensor clocks in physical states.

## Complete default configuration

`configs/default.yaml` explicitly lists every root field and every dataclass
field for:

- electrical/UPS;
- VFD/motor;
- reference pump;
- lumped UPW; and
- three default UPW sensors.

Unknown root and nested keys are rejected. Cross-validation checks component
invariants, sensor signal/unit compatibility, unique sensor IDs, and the
existing explicit-Euler timestep bounds. The configuration is synthetic-only
and links the scenario-library and PHM-data configuration paths.

Canonical configuration SHA-256:

```text
4cc229eff2635bc64f8b84815317d6070ce3ba89b27f46af5c64b6fb56e4f3f8
```

The run provenance map contains seven entries: electrical, drive, pump, UPW,
and three sensors.

## Validation evidence

Import/configuration/schema smoke check:

```text
R1_IMPORT_SMOKE_OK
config_sha256=4cc229eff2635bc64f8b84815317d6070ce3ba89b27f46af5c64b6fb56e4f3f8
parameter_provenance_count=7
```

Focused tests:

```text
21 passed
tests/unit/test_config.py
tests/unit/test_schema.py
tests/unit/test_interfaces.py
```

Complete suite:

```text
70 passed, 1 warning in 23.25 s
```

The warning is the pre-existing pandas future-behavior warning for
concatenating empty/all-NA PHM frames. It is an R2 pipeline item, not an R1
failure.

## Acceptance result

| Requirement | Result |
|---|---|
| Versioned schema/interface decision and impact analysis | PASS |
| Native/unknown public units preserved honestly | PASS |
| Conversion provenance enforced | PASS |
| Run parameter provenance required | PASS |
| Four plant classes conform to DynamicSubsystem v2 | PASS |
| Plant input states remain immutable | PASS |
| Observation boundary remains independent | PASS |
| Complete explicit default YAML | PASS |
| Unknown nested keys rejected | PASS |
| Stable configuration hash | PASS |
| Focused and full regression tests | PASS |

## Remaining boundaries

R1 is contract/configuration evidence only. The following remain open:

- R2: PHM phase/timestamp/anomaly/split semantics and the pandas warning;
- R3: frequency/UPS energy, pump/network duty point, hydraulic conservation,
  pump-trip timing, and conductivity-proxy semantics; and
- R4: observation-arrival causality and scenario validation/cause semantics.

No CMP, utility-coupling, prediction, or controller efficacy claim is
supported by R1.
