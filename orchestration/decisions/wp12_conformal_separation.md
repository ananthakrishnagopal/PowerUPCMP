# Decision: independent probability and conformal calibration for WP12

Date: 2026-07-12
Status: FROZEN BEFORE REVISION-1.2 GENERATION
Task: T-WP12
Evidence plane: synthetic simulator only

## Problem found in the revision-1.1 audit

Let the base model be \(f_T\), fitted on whole-run training groups \(T\), and
let the sigmoid map be \(g_C\), fitted on calibration groups \(C\). Revision
1.1 then evaluated nonconformity scores on those same groups \(C\). Thus each
score was computed with a map that had already adapted to its row:

\[
p_i = g_C\!\left(\operatorname{logit}(\operatorname{clip}(f_T(x_i)))\right),
\qquad i\in C.
\]

For binary label \(y_i\), the implemented score was

\[
s_i = 1-p_i \quad\text{if } y_i=1,
\qquad
s_i = p_i \quad\text{if } y_i=0.
\]

Reusing \(C\) to fit \(g_C\) and estimate the score quantile makes the score
sample adaptive. It therefore does not implement the intended split-conformal
separation, irrespective of the observed coverage value.

## Corrected construction

Four disjoint whole-run roles are frozen:

1. \(T\): TRAIN fits the base predictor.
2. \(C_p\): CALIBRATION fits only the sigmoid probability map \(g_{C_p}\).
3. \(C_q\): CONFORMAL_CALIBRATION estimates only the nonconformity quantile.
4. \(E\): TEST is evaluated only after the preceding objects are fixed.

For \(i\in C_q\), define

\[
\tilde p_i = g_{C_p}\!\left(
  \operatorname{logit}(\operatorname{clip}(f_T(x_i)))
\right)
\]

and use the same binary nonconformity score above. With \(n=|C_q|\) eligible
rows and nominal error level \(\alpha=0.10\), the finite-sample `higher`
quantile is

\[
k = \left\lceil (n+1)(1-\alpha) \right\rceil,
\qquad
\hat q = s_{(\min(k,n))}.
\]

For a new calibrated probability \(\tilde p(x)\), the prediction set is

\[
\Gamma(x)=
\{0:\tilde p(x)\leq \hat q\}
\cup
\{1:1-\tilde p(x)\leq \hat q\}.
\]

Empty and two-class sets remain permitted and are reported explicitly.

## Frozen new data role

- Split ID: `CONFORMAL_CALIBRATION`.
- Seed start: 62000.
- Runs per family: 3.
- Families and severity construction: unchanged from revision 1.1.
- Expected count: 18 whole runs.
- Required before fitting: non-empty and both target classes represented.
- Prohibited uses: sigmoid fitting, base-model fitting, model selection, or
  interpretation-gate tuning.

## Impact analysis

Expected to remain exactly invariant:

- target labels for all existing runs;
- existing TRAIN, CALIBRATION, TEST, unseen-compound, and structural-null runs;
- trained base-model parameters;
- sigmoid-calibrator parameters;
- calibrated TEST probabilities and threshold alarms;
- precision, recall, PR-AUC, specificity, Brier score, ECE, event recall,
  warning lead time, and false-alarm episode counts, apart from timing noise in
  latency fields.

Expected to change:

- conformal quantile;
- prediction-set membership;
- marginal coverage, empty-set fraction, two-class-set fraction, and mean set
  size;
- dataset/report hashes, fitted-artifact hashes, and runtime.

The pre-amendment deterministic TEST/robustness probability payload contains
8,964 model rows and has SHA-256
`5a4fb7011fd6688718455c9692689937caa679ea29c884cdca099835a9830ede`.
Revision 1.2 must reproduce that value before it can replace revision 1.1.

## Claim boundary

Even after correction, temporal rows within a run are dependent and the
synthetic severity grid is fixed. Reported coverage is therefore descriptive
for the configured simulator ensemble. It is not a distribution-free claim
for whole runs, a real fab, defects, yield, equipment safety, or production
control.
