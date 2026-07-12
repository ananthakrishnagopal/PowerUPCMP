# Failure report

## Task

Final WP10 claims/risk/status audit and frozen-artifact compatibility check before the COMPLETE transition.

## Failed command

No executable command returned nonzero. The failure was detected by comparing the regenerated R3 validation artifact against the frozen SHA-256 recorded in `orchestration/reports/r3_plant_physics_validation.md`.

## Error

Expected frozen R3 validation JSON SHA-256:

```text
02ba8166715c1022d54685d96ded8b85c196dbd0dbc6b29ea544dd4b085eddb7
```

Current regenerated SHA-256:

```text
803ae18501194865338016cd426eb0a1c7a53dcc49bc686aeefa3faba87913cb
```

The R3 physical reference trace remains exactly unchanged at
`5191cbdcbf36c8709d92ed0de9662104c3ba6adfdd030ac45a661020ea17fdd0`.

## Files changed before failure

Since recovery from the exact-depletion failure:

- corrected exact-boundary battery projection in `src/semifab_poc/simulation/electrical.py`;
- added the exact-depletion unit regression;
- regenerated `reports/plant/r3_validation.json` and its unchanged reference trace;
- generated WP10 JSON and two CSV evidence artifacts under `reports/sensitivity/`;
- added WP10 integration and regression tests;
- added/updated WP10 validation, mathematical-model, modeling-ledger, running-paper, README, architecture, assumptions, claims, risk, manifest, and status documentation;
- ran 35 adjacent plant tests, 50 WP10-impacted tests, 153 full tests, WP08 reproduction, strict configuration validation, and governance successfully.

T-WP10 is VALIDATED but has not been marked COMPLETE.

## Read-only diagnosis

The regenerated R3 report identifies itself as schema/interface 2.1.0/2.0.0, but its `parameter_provenance` mapping now contains later components:

```text
cmp: synthetic-cmp-reduced-order-v1
coupling: synthetic-utility-cmp-coupling-v1
```

`RuntimeConfig.parameter_provenance_ids` currently returns all fields present in the additive current Python model regardless of the loaded historical schema/interface pair. Runtime hashing already excludes later sections for old pairs, but the provenance property did not apply the same compatibility rule. This changed report metadata without changing R3 physics or its trace.

The required historical key sets are:

- schema 2.1/interface 2.0 and schema 2.2/interface 3.0: electrical, drive, pump, UPW, and sensors only;
- schema 2.3/interface 3.1: those components plus CMP, but not coupling;
- schema 2.4/interface 3.2: all current components including coupling.

## Likely causes

- Coupling provenance was added additively to the property without version-aware serialization.
- Existing tests protected canonical configuration hashes but did not assert historical provenance key sets or the R3 validation JSON hash after report regeneration.

## Recovery options

1. Make `parameter_provenance_ids` version-aware using the same component-introduction boundaries as `runtime_config_sha256`; add key-set tests for all four supported pairs; regenerate R3 and require the original JSON and trace hashes; rerun R4/WP08/WP10 reproduction plus the full suite and governance.
2. Accept a new R3 JSON hash and revise the historical report. This would falsely imply that CMP/coupling were part of the R3 schema and is not scientifically acceptable.
3. Stop regenerating old artifacts. This leaves the compatibility bug in run manifests and future reproduction flows.

## Recommended option

Option 1. It restores truthful historical provenance without changing any current component, equation, interface field, coupling result, or physical trace.

## User decision required

Authorize Option 1 and require exact restoration of the frozen R3 report hash before WP10 can move from VALIDATED to COMPLETE.
