# Decision: complete WP12 observation-corruption robustness support

Date: 2026-07-12
Status: FROZEN BEFORE REVISION-1.3 GENERATION
Task: T-WP12
Evidence plane: synthetic simulator only

## Audit finding

Revision 1.2 selected one upper-median TEST scenario per declared family for
each high-noise, high-delay, and high-dropout evaluation. All six selected
scenarios were negative under the primary target. Those runs validly measured
specificity, false-alarm episodes, calibration error, and uncertainty coverage,
but PR-AUC and event recall were undefined. They did not answer whether sensor
corruption causes missed warnings on qualifying synthetic excursions.

## Frozen completion

Revision `1.3-robustness-completion` selects exactly two pre-existing TEST
scenario positions per family:

1. `UPPER_MEDIAN`: index `len(family_runs) // 2`;
2. `MAXIMUM`: the final, highest-severity configured endpoint.

The resulting robustness ensemble contains 12 whole scenarios per corruption
case: two positions for each of six families. The maximum endpoints include
the already declared full-DRESS stress anchors. Under the frozen simulator,
grid-interruption, pump-trip, and valve-restriction anchors supplied primary
events in revision 1.2; the tool-demand anchor did not. The revised robustness
dataset must contain both classes or stop before reporting metrics.

No family, severity, target, feature, model, probability threshold, corruption
magnitude, seed-offset rule, primary TEST group, or interpretation gate changes.
The selection is frozen because the earlier subset lacked event support, not
because of robustness performance. Observation-corruption results remain
descriptive secondary evidence and cannot replace the primary held-out result.

## Reporting corrections in the same revision

Three non-model reporting corrections are frozen before regeneration:

- censor counts are recorded per split and robustness report entries show only
  the split being evaluated;
- grouped bootstrap resamples with one target class contribute to metrics that
  remain defined, such as Brier score and conformal coverage, while PR-AUC and
  event recall retain their smaller valid-repetition counts; and
- the revision-1.1 deterministic probability payload hash is enforced as a
  hard invariant, not merely printed.

The report labels predictor timing as amortized vectorized offline inference.
It is not a streaming controller-latency or production-response measurement.

## Permitted changes from revision 1.2

- observation-robustness row/class counts and metrics;
- split-specific censor-count metadata;
- bootstrap intervals for metrics previously conditioned on two-class draws;
- elapsed-time, latency fields, report/dataset hashes, and the model-comparison
  figure hash if uncertainty summaries are re-rendered.

## Required invariants

- Probability payload SHA-256:
  `5a4fb7011fd6688718455c9692689937caa679ea29c884cdca099835a9830ede`.
- Historical runtime configuration SHA-256:
  `b2b07edbaad458f6f66cf26ce88ffc5deef656a33701a7cccd8da94104d7383f`.
- Primary TEST labels and all non-uncertainty warning metrics.
- Disjoint TRAIN, CALIBRATION, CONFORMAL_CALIBRATION, and TEST whole-run IDs.

## Claim boundary

This extension evaluates synthetic sensor-corruption cases only. It does not
validate real sensor failure distributions, causal attribution, controller
benefit, safety certification, equipment protection, defect prevention, yield,
or production performance.
