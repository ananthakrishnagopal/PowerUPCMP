# Failure report

## Task

Run the frozen WP12 grouped synthetic ensemble, fit/calibrate the three preregistered early-warning models, and generate held-out evidence.

## Failed command

```text
env MPLCONFIGDIR=/tmp/semifab-poc-matplotlib conda run -n devkki python scripts/validate_wp12_early_warning.py
```

## Error

```text
TypeError: semifab_poc.simulation.chain.ChainScenario() got multiple values
for keyword argument 'event_duration_s'
```

The exception occurred in `scenario_for_family` while constructing the first non-normal training family.

## Files changed before failure

Before the experiment, the WP12 decision/configuration, early-warning target and model module, open-loop chain runner, validation driver, and ten focused tests had been created. The focused tests and syntax gate passed. The parallel manuscript source/PDF was also complete.

The failed experiment created the intended `reports/early_warning/` directories and simulated the paired nominal reference in memory. It wrote no early-warning file, fitted no model, and performed no held-out evaluation.

## Read-only diagnosis

- The local `default` mapping in `scenario_for_family` includes `event_duration_s: 0.0`.
- Every non-normal constructor expands `**default` and also supplies an explicit `event_duration_s`, which Python rejects before calling `ChainScenario`.
- Normal reference construction works because it uses the default duration only.
- The error is deterministic and occurs before model fitting, calibration, target sensitivity, robustness analysis, or inspection of test performance.
- `reports/early_warning/` contains no generated files, so no partial result can be mistaken for accepted evidence.
- The frozen target, scenario ranges, split seeds, model hyperparameters, and interpretation gate have not been changed.

## Likely causes

1. A convenience mapping included a field that was intended to be overridden explicitly for disturbance families.
2. Existing focused tests exercised the chain runner and model logic but did not enumerate construction of every configured scenario family.

## Recovery options

1. Remove `event_duration_s` from the shared constructor mapping, pass `0.0` explicitly for `NORMAL`, retain the already frozen explicit duration for every disturbance family, and add a unit test that constructs and validates every family in TRAIN/CALIBRATION/TEST before rerunning the frozen experiment from the beginning.
2. Replace each constructor with a merged mapping whose later value overrides the default. This is shorter but less explicit and easier to regress.
3. Remove the affected disturbance families. This would change the preregistered experiment and is not acceptable.

## Recommended option

Option 1. It is a narrow implementation correction, adds the missing preflight coverage, and leaves all scientific definitions, seeds, ranges, splits, and model decisions unchanged.

## User decision required

Authorize Option 1 and a from-scratch retry of the unchanged frozen WP12 experiment.

## Resolution

The user authorized Option 1. The shared mapping no longer supplies `event_duration_s`; `NORMAL` passes zero explicitly and each disturbance family passes its frozen duration explicitly. A new preflight test enumerates and validates all primary, unseen-compound, and structural-null scenarios before the experiment retry.
