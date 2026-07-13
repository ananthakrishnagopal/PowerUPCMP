# Failure report

## Task

Run the unchanged frozen WP12 experiment after the scenario-constructor recovery, then verify class feasibility before fitting any model.

## Failed command

```text
env MPLCONFIGDIR=/tmp/semifab-poc-matplotlib conda run -n devkki python scripts/validate_wp12_early_warning.py
```

## Error

```text
ValueError: TRAIN lacks both primary target classes
```

The driver completed the reference, 36 training, 18 calibration, 24 test, six unseen-compound, and six structural-null simulations in memory, built causal features/labels, and stopped at the first class-feasibility assertion. It fitted no model and reported no held-out metric.

## Files changed before failure

The WP12 implementation/configuration/tests and manuscript artifacts existed before this run. The driver created `reports/early_warning/` subdirectories but wrote no dataset, manifest, model, prediction, figure, or validation report because class feasibility is checked before artifact writing.

## Read-only diagnosis

Normal and healthy-service training cases guarantee negative examples. Therefore the missing second class is inferred to be the positive class. No class counts were printed or persisted, and no calibration/test performance was inspected.

The frozen primary event is a persistent active-POLISH MRR departure outside ±5% of an event-disabled paired reference. The current severity generator uses random event starts after 0.5 s and clips duration before the 6 s DRESS boundary. Even its highest nominal severity therefore does not guarantee loss of conditioning support for almost the complete DRESS interval.

A separate read-only limiting-case audit, not a model retry, compared the nominal reference with service loss from 0.0 to 5.99 s:

| Limiting case | Mean POLISH MRR ratio | Minimum POLISH MRR ratio | Disturbed/reference end-DRESS pad activity | Excursion onset step | Positive label rows |
|---|---:|---:|---:|---:|---:|
| Grid interruption | 0.9458899 | 0.9458692 | 0.5011327 / 0.5511877 | 701 | 28 |
| Pump trip | 0.9457804 | 0.9457596 | 0.5010314 / 0.5511877 | 701 | 28 |

Thus the ±5% target is reachable within the frozen equations without changing the CMP model, coupling coefficients, envelope, horizon, or persistence. The experiment failed because the scenario design omitted its physically bounded full-DRESS severity endpoint.

## Likely causes

1. Parameterized severity reached high magnitude but did not include a deterministic start-at-zero/full-DRESS duration anchor.
2. Target and scenario design were frozen together without a training-only limiting-case feasibility check.
3. The WP10 3 s mechanism case was intentionally not forced above the ±5% WP12 target; the ensemble needed separate hold-required endpoints to create positive training examples.

## Recovery options

1. Issue a transparent versioned scenario-design feasibility amendment while retaining the primary target and every model decision: add a start-at-0.0 s, duration-5.99 s endpoint for the highest-severity interruption, pump-trip, valve-restriction, and demand-spike case in TRAIN, CALIBRATION, and TEST; keep all other draws/seeds unchanged; add preflight tests for the anchors and a training-only limiting-case positive label; then rerun the complete experiment from scratch. The amendment must state that no model was fit and no held-out metric was inspected before the change.
2. Tighten the MRR envelope below ±5%. This would tune the target after feasibility failure and is not recommended.
3. Increase a coupling coefficient or change CMP dynamics. This would tune the physics to the prediction task and is not acceptable.
4. Retain the current ensemble, record that the primary target has no positive training class, and mark WP12 unable to fit rather than complete it.

## Recommended option

Option 1. It preserves the scientific target, physics, uncertainty method, model hyperparameters, seeds, and interpretation gate. It adds the missing bounded severity endpoint symmetrically to all preregistered primary splits before any model fitting or held-out result, with an explicit audit trail.

## User decision required

Authorize Option 1 and the versioned scenario-feasibility amendment, or choose another option.

## Resolution

The user authorized Option 1. Experiment revision `1.1-feasibility-amendment` preserves the frozen target/models and adds the configured 0.00--5.99 s endpoint symmetrically to the highest-severity interruption, pump-trip, valve-restriction, and demand-spike case in TRAIN, CALIBRATION, and TEST. Construction and physical-label preflight tests were added before the from-scratch rerun.
