# Failure report

## Task

Execute the full pytest suite in Phase 4 after implementing T-WP14 (baseline controllers), T-WP15-IMPL (predictive supervisor), and T-WP16-IMPL (safety filter).

## Failed command

`PYTHONPATH=. conda run -n devkki pytest`

## Error

The test suite failed with 14 errors related to a missing `scikit-learn` dependency in the `devkki` environment. Specifically:

```
src/semifab_poc/models/virtual_metrology.py:649: VirtualMetrologyError: WP09 requires the optional scikit-learn model dependency
```
and
```
ModuleNotFoundError: No module named 'sklearn'
```

This occurred during the collection and execution of `tests/integration/test_warning_evaluation.py`, `tests/unit/test_attribution.py`, `tests/unit/test_early_warning.py`, and `tests/unit/test_virtual_metrology.py`. 

All 17 tests added for Phase 4 (WP14, WP15, WP16) passed successfully. The failures are entirely within the pre-existing WP09, WP12, and WP13 machine learning validation tests.

## Files changed before failure

The following new files were created to implement Phase 4 tasks:
- `src/semifab_poc/control/base.py`
- `src/semifab_poc/control/baselines.py`
- `src/semifab_poc/control/predictive.py`
- `src/semifab_poc/control/safety.py`
- `tests/property/test_no_action.py`
- `tests/unit/test_baseline_controllers.py`
- `tests/unit/test_predictive_controller.py`
- `tests/property/test_predictive_action_bounds.py`
- `tests/unit/test_safety_filter.py`
- `tests/property/test_safety_properties.py`

No existing configuration, schema, or simulation source code was modified. `git status --short` shows only the new untracked files, and `git diff --check` is clean.

## Read-only diagnosis

The Phase 3 scientific freeze checkpoint indicates that 224/224 tests were passing in the `devkki` environment prior to this run. The failure suggests one of two scenarios:
1. The `devkki` conda environment is missing `scikit-learn`, which was either unintentionally excluded from the environment definition or recently uninstalled.
2. The WP09/WP12 machine learning tests dynamically skip themselves when `scikit-learn` is absent, but a recent change altered this behavior, or the environment is expected to contain `scikit-learn` for full validation.

Since no `pyproject.toml`, `environment.yml`, or test files in the ML packages were mutated during this phase, the issue originates from the environment's current state relative to the expected test suite dependencies.

## Likely causes

- The `devkki` conda environment used to run the tests does not have `scikit-learn` installed.
- The repository expects `scikit-learn` to be installed for the full test suite to pass, but the environment was partially restored or modified before the Phase 4 commencement.

## Recovery options

1. Install the missing dependency into the `devkki` conda environment (`conda install -n devkki scikit-learn` or `pip install scikit-learn` within the env) and re-run the full test suite.
2. If `scikit-learn` is not meant to be in the base `devkki` environment, conditionally skip the ML tests by marking them or using appropriate pytest skipping mechanisms.

## Recommended option

Option 1. The tests explicitly assert that "WP09 requires the optional scikit-learn model dependency". Installing it ensures all 227+ tests run and validate the full repository state.

## User decision required

Authorize Option 1 (installing `scikit-learn` in `devkki`) or advise on an alternative recovery path before any further mutating actions.
