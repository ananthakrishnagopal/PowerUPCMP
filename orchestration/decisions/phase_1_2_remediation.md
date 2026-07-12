# Decision record: Phase 1/2 corrective remediation

Date: 2026-07-11  
Status: R1 APPROVED FOR IMPLEMENTATION; R2--R4 PENDING  
Authority: user approval of `phase_3_cmp_model_redesign.md` on 2026-07-11  
Scope: T-PHASE12-REMEDIATION

## Context

The retrospective audit found three R1 contract defects:

1. `PublicMeasurementRecord` validated the public source value using the
   canonical SI unit, so an undeclared/native PHM target could not be stored
   honestly.
2. The frozen stateless `DynamicSubsystem` interface required
   `reset(initial_state, config)` and `observe(state, sensor_model)`, while all
   implemented plant components own validated immutable configuration at
   construction, use `reset(initial_state=None)`, and deliberately delegate
   sensing to a separate `SensorModel`.
3. `configs/default.yaml` was absent and component parameter provenance was
   not carried into the run manifest.

The public schema and interface registry are frozen at version 1.0.0, so these
corrections require the recorded reason, impact analysis, tests, and downstream
documentation mandated by their change-control policies.

## R1 decision

### Canonical schema 2.0.0

`PublicMeasurementRecord` will distinguish:

- the unmodified source value and source-unit declaration status;
- an optional canonical value and canonical SI unit; and
- the exact conversion identifier when conversion is supported.

Source-unit status is one of:

```text
DECLARED
NATIVE_UNDECLARED
UNKNOWN
```

An available native value with no supported conversion uses a non-empty
source-unit label such as `PHM_NATIVE_UNDECLARED`, null canonical value/unit,
and `UNIT_UNRESOLVED`. It is not marked `MISSING`. A canonical value requires a
declared source unit, the canonical signal unit, and a non-empty conversion ID.
Raw values remain immutable and auditable.

`RunManifest` will require `parameter_provenance_ids`, mapping component names
to non-empty configuration provenance IDs. This is a breaking serialized
schema change, so the canonical schema major version becomes 2.0.0. Version 1
records remain historical and are not silently upgraded.

### DynamicSubsystem 2.0.0

The plant interface becomes a stateful-config abstract base:

```python
subsystem = Subsystem(config: ComponentConfig | None = None)
state = subsystem.reset(initial_state: State | None = None)
next_state = subsystem.step(state, action, disturbance, dt_s)
```

Configuration is immutable and validated at construction. `reset` may create a
documented nominal state or validate an explicit state. `step` must return a
new immutable, invariant-valid state and must not mutate its input.

`observe` is removed from the plant contract. Observation requires run ID,
source step, source timestamp, sampling state, and communication state, none of
which belong in a physical subsystem state. The separate versioned
`SensorModel.sample` interface remains the sole latent-to-observed boundary.
This prevents plant implementations from embedding sensor behavior or
inventing incomplete timestamps.

This is a breaking interface correction, so the interface major version
becomes 2.0.0. Electrical, drive, pump, and UPW components will explicitly
inherit the base class without changing their R1 equations.

### Complete default configuration

`RuntimeConfig` will contain:

- runtime identity, schema/interface versions, seed, timestep, duration,
  logging, artifact path, and synthetic-only marker;
- paths to the scenario library and PHM configuration;
- complete electrical, drive, pump, and UPW configurations; and
- a non-empty sensor configuration tuple.

Every component configuration carries a non-empty `provenance_id`. The
repository default YAML explicitly lists every root and nested dataclass field;
it does not depend on hidden component defaults. Unknown nested keys are
rejected. Cross-component validation checks component invariants and the
explicit-Euler timestep limits already enforced by the as-built code. A
canonical JSON serialization has a deterministic SHA-256.

The default remains simulation-only. Its values are engineering approximations
or synthetic assumptions, not measured fab settings.

## Impact analysis

| Consumer | Impact | Required action |
|---|---|---|
| `src/semifab_poc/data/schema.py` | Breaking public/run record fields | Implement explicit source-unit/conversion rules and provenance map validation. |
| `src/semifab_poc/data/__init__.py` | Add exported unit-status enum | Export `SourceUnitStatus`. |
| `src/semifab_poc/simulation/base.py` | Missing | Add generic abstract base v2. |
| Electrical/drive/pump/UPW modules | Structural interface declaration and config provenance only | Inherit base; add/validate provenance ID; do not change equations in R1. |
| `src/semifab_poc/config.py` | Minimal runtime model is incomplete | Add typed nested configs, cross-validation, provenance map, and stable hash. |
| `configs/default.yaml` | Missing | Add a fully explicit safe synthetic baseline. |
| Existing public-record and manifest callers | New required fields | Update tests/callers; reject silent v1 coercion. |
| Sensor model | No signature change in R1 | Retain separate observation boundary; R4 corrects arrival causality later. |
| Pump/UPW/electrical equations | Out of R1 scope | Preserve until R3. |
| PHM phase/timestamp processing | Out of R1 scope | Preserve until R2. |
| Scenario validation/timing | Out of R1 scope | Preserve until R4. |

Repository search found no persisted version-1 run/public measurement artifacts
and only unit-test constructors for the affected records. Therefore an explicit
in-place migration tool is unnecessary at this stage. Any future v1 artifact
must be rejected or migrated by a separately tested converter.

## R1 acceptance tests

1. Interface and schema registries both declare 2.0.0 and document the break.
2. All four plant components instantiate as `DynamicSubsystem` and preserve
   input states across `step`.
3. Sensor observation remains outside the plant base interface.
4. Native PHM MRR can be represented without SI conversion or a `MISSING`
   flag.
5. Canonical conversion requires declared source unit, canonical unit, and
   conversion ID.
6. Run manifests reject missing/blank parameter provenance.
7. The repository default YAML explicitly contains every supported root and
   nested field, loads strictly, and produces a deterministic hash.
8. Unknown root and nested configuration keys are rejected.
9. Focused R1 tests and the complete `devkki` suite pass.

## Claims boundary

R1 validates contracts and configuration behavior only. It does not validate
PHM predictive performance, physical plant parameters, pump/UPW conservation,
sensor timing, CMP physics, utility coupling, or controller efficacy.
