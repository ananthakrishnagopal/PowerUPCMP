# Decision: remove TEST-driven model selection from WP12 secondary analyses

Date: 2026-07-12
Status: FROZEN BEFORE REVISION-1.4 GENERATION
Task: T-WP12
Evidence plane: synthetic simulator only

## Audit finding

Revisions 1.1 through 1.3 compared the prevalence, logistic, and
gradient-boosted predictors on TEST, selected the learned model with maximum
TEST PR-AUC, and then used that model for target-sensitivity and
observation-corruption analyses. Hyperparameters and primary results were not
tuned, but those secondary results were conditional on a TEST-derived model
choice. Calling them model-independent robustness evidence would therefore be
incorrect.

## Frozen correction

Revision `1.4-no-test-selection` performs every target sensitivity and every
observation-corruption evaluation separately for all three frozen model
families. No TEST metric selects a predictor for any downstream calculation.
The timeline figure displays all three probability trajectories on the same
held-out run.

The report may state which learned model has the largest TEST PR-AUC only under
the key `descriptive_best_learned_model_by_test_pr_auc`, accompanied by
`used_for_downstream_selection: false`. This is a descriptive observed result,
not model selection or a preregistered winner claim.

## Additional metric-domain correction

Sample recall is undefined when a bootstrap or robustness sample contains no
positive rows. Precision is undefined when no positive prediction is made, and
specificity is undefined when no negative rows exist. Revision 1.4 records
these cases as `null`, retains explicit confusion counts, and computes each
bootstrap interval from only repetitions where that metric is defined. Brier
score and conformal coverage continue to use all repetitions.

## Invariants

- Frozen probability payload SHA-256 remains
  `5a4fb7011fd6688718455c9692689937caa679ea29c884cdca099835a9830ede`.
- Primary TEST probabilities, labels, threshold alarms, and non-timing metrics
  remain unchanged.
- Model fits, calibration roles, target, features, scenario seeds, robustness
  selection, and useful-warning gates remain unchanged.

## Claim boundary

The correction removes one source of analysis leakage but does not increase the
number of independent primary events, validate real sensor distributions, or
support controller, defect, yield, equipment, or production claims.
