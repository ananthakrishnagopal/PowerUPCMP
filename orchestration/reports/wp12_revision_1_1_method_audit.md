# WP12 revision 1.1 post-run method audit

Date: 2026-07-12
Evidence plane: synthetic simulator only
Disposition: superseded for uncertainty validation; retained as an audit record

## Successful run snapshot

Revision `1.1-feasibility-amendment` completed in 362.4 s after 13 focused tests
passed with warnings treated as errors. Deterministic replay, fit/test group
separation, feature-boundary checks, save/load equality, and the historical
runtime hash all passed.

The primary TEST set contained 1,932 eligible decision rows, 84 positive rows,
and only three independent qualifying excursion runs. Logistic regression was
the strongest learned model:

- PR-AUC: 0.9904009487 versus prevalence 0.0434782609;
- precision: 0.975;
- row recall: 0.9285714286;
- event recall: 3/3;
- median warning lead time: 2.71 s;
- primary false-alarm episodes: 1, or 18.6335 per simulated hour;
- empirical conformal coverage: 0.8680124224; and
- empty prediction-set fraction: 0.1319875776.

The corresponding gradient-boosted model had PR-AUC 0.9130434783, event recall
3/3, median lead time 2.71 s, and empirical coverage 0.8773291925. Both learned
models passed the preregistered synthetic-ensemble gate; the prevalence model
did not.

## Important negative findings

The logistic model produced no true events but severe false-alarm behaviour on
separate robustness sets:

- structural no-connection set: specificity 0.3371, 30 false-alarm episodes,
  2,045.45 false alarms per simulated hour, and uncertainty coverage 0.0114;
- unseen compound set: specificity 0.8409, 10 false-alarm episodes, 681.82 per
  simulated hour, and uncertainty coverage 0.2917;
- high-noise representative subset: specificity 0.0284, 8 false-alarm
  episodes, 545.45 per simulated hour, and coverage 0.0.

High-delay and high-dropout representative subsets were also negative-only;
their specificity values were 0.9053 and 0.9091. These subsets do not measure
event recall. PR-AUC is undefined on all negative-only sets and is recorded as
`null`, not zero.

The primary bootstrap intervals are dominated by only three event groups.
Forty-three of 1,000 grouped resamples contained one target class and could not
define PR-AUC. The result therefore supports only a narrow configured-simulator
claim and is not evidence of broad robustness.

## Methodological defect

The same CALIBRATION rows fitted the sigmoid map and supplied conformal scores.
This violates the intended split-conformal separation because the probability
map is not fixed independently of the score sample. The primary probability
ranking and warning metrics remain valid as held-out simulator results, but the
revision-1.1 uncertainty construction cannot be used as the final WP12
uncertainty evidence.

## Frozen corrective action

Revision 1.2 adds an independent conformal-calibration split while preserving
all existing TEST probabilities. The deterministic probability payload before
the change contains 8,964 rows and has SHA-256
`5a4fb7011fd6688718455c9692689937caa679ea29c884cdca099835a9830ede`.
See `orchestration/decisions/wp12_conformal_separation.md` for the equation,
role separation, impact analysis, and remaining coverage limitations.
