# Decision: WP09 public CMP virtual metrology

Date: 2026-07-13
Status: FROZEN BEFORE OFFICIAL HOLDOUT TARGET ACCESS
Task: T-WP09
Evidence plane: public PHM 2016 CMP data in source-native numeric scale

## Decision question

Which model, uncertainty, split, and sensitivity protocol can defensibly test
average material-removal-rate virtual metrology without importing simulator
units, leaking wafer identity, choosing a label treatment from holdout results,
or converting process-mode proxies into measured phases?

## Scientific boundary

The measured target is `AVG_REMOVAL_RATE`. The original challenge does not
declare its unit, and the 405 process predictors use proprietary scaled values
with hidden factors. WP09 therefore reports target values in
`SOURCE_NATIVE_UNIT_UNDECLARED` and predictors in
`PROPRIETARY_SCALED_SOURCE_SPACE`.

No PHM value is interpreted as Pa, m3/s, rad/s, physical consumable age, or SI
MRR. No WP08 simulator coefficient is transferred to this evidence plane. The
public-data analysis is offline average-MRR virtual metrology; it does not
validate electrical/UPW causality, spatial uniformity, a physical defect,
yield, equipment damage, streaming warning, or control efficacy.

## Immutable input contract

Primary features use `PHM_PHASE_AWARE_OFFLINE_VM_V1` at the preregistered 10 s
continuity threshold. There are 405 target-free predictors. `WAFER_ID`,
`STAGE`, all `META_*` columns, and the target are excluded from the predictor
matrix. `STAGE` is retained only for stratified metrics. Group timestamps are
used only for the chronological stress split.

The five process labels are input-derived proxies, not measured phases:

```text
PREPARE_PROXY
ACTIVE_POLISH_PROXY
TRANSITION_WITHIN_POLISH_PROXY
ENDING_OR_CLEANING_PROXY
UNRESOLVED_PROXY
```

Complete-trace features are eligible only for this offline VM task and must not
enter WP12 or any online controller.

## Whole-wafer role hierarchy

The R2.1 source precedence correction is mandatory. From source group sets

\[
G_{tr},G_{te},G_{va},
\]

the retained roles are

\[
\widetilde G_{tr}=G_{tr},\quad
\widetilde G_{te}=G_{te}\setminus G_{tr},\quad
\widetilde G_{va}=G_{va}\setminus(G_{tr}\cup G_{te}).
\]

This gives 1,981/311/275 wafer-stage rows from 1,699/302/267 mutually disjoint
wafers. Full 424-row test and validation source partitions are reported only as
`OFFICIAL_SOURCE_PARTITION_COLLISION_CONTAMINATED` diagnostics.

No target value was used to define these roles.

## Inner training roles

The 1,699 official-training wafers are assigned from feature identity only with
NumPy PCG64 seed 90209:

```text
TRAIN_CORE:            70% of whole wafers
MODEL_SELECTION:       15% of whole wafers
INTERVAL_CALIBRATION:  15% of whole wafers
```

The existing grouped split primitive determines rounded counts and conserves
all rows. Assignment is materialized and hashed before official test or
validation targets are opened.

Hyperparameters are selected only inside `TRAIN_CORE` using five deterministic
whole-wafer folds. Unique wafer IDs are sorted as strings, permuted by PCG64
seed 90209, and assigned cyclically by permuted rank modulo five. The score is
pooled out-of-fold MAE. Exact ties within `1e-12` use the simpler/lexicographic
configuration declared in YAML.

After hyperparameter selection, all six model families are evaluated on
`MODEL_SELECTION`. The lowest MAE selects one preregistered recommended family;
ties use the fixed simplicity order. This recommendation is frozen before any
official holdout target is read. Every family is still refitted and reported.

For primary held-out evaluation, each model is refitted on
`TRAIN_CORE + MODEL_SELECTION`. `INTERVAL_CALIBRATION` remains disjoint and is
used only for residual-interval calibration. Test is descriptive offline
confirmation; final validation is opened once and is never used for selection.

## Common preprocessing

For each raw predictor (x_j), non-finite values are treated as missing. On a
fit role only, record the median (m_j), define

\[
x'_{ij}=\begin{cases}
x_{ij}, & x_{ij}\text{ finite},\\
m_j, & \text{otherwise},
\end{cases}
\qquad
z_{ij}=\mathbb{1}[x_{ij}\text{ missing}],
\]

and append one missing indicator for every raw predictor. Derived columns with
zero variance on the fit role are removed and recorded. A feature with no
finite fit value is a hard error rather than a silent constant substitute.

Linear and ridge models standardize retained derived columns with fit-only mean
and population standard deviation. Tree and hybrid residual models use the same
imputed, indicator-augmented, zero-variance-screened matrix without scaling.
Every data-driven family in a role shares one fitted preprocessor and identical
rows. No correlation, univariate target screening, recursive elimination, or
holdout-derived feature selection is allowed.

All final point predictions are projected onto the physically minimal
nonnegative target domain:

\[
\widehat y_i=\max(0,\widehat y_i^{raw}).
\]

Raw negative counts and clipping counts are reported.

## Training-label policies

The policies remain immutable:

1. `ORIGINAL` is primary;
2. `EXCLUDE_FOUR_PREREGISTERED` is a sensitivity; and
3. `HYPOTHETICAL_DIVIDE_FOUR_BY_60` is a separately labelled hypothetical
   sensitivity.

Only official-training labels change. Official test and validation labels are
never altered. Hyperparameters and the recommended-family rule are selected
under `ORIGINAL` only, then reused unchanged for both sensitivities. No policy
may be selected from test or validation performance.

## Model families

### 1. Mean predictor

\[
\widehat y_i=\overline y_{fit}.
\]

This is the minimum statistical reference.

### 2. Ordinary linear regression

On the common standardized design matrix (X), fit an intercept and ordinary
least-squares coefficients:

\[
(\widehat\beta_0,\widehat\beta)
=\arg\min_{\beta_0,\beta}\sum_i(y_i-\beta_0-X_i\beta)^2.
\]

### 3. Ridge regression

\[
(\widehat\beta_0,\widehat\beta)
=\arg\min_{\beta_0,\beta}
\sum_i(y_i-\beta_0-X_i\beta)^2+\alpha\|\beta\|_2^2,
\]

with unpenalized intercept and the fixed alpha grid in configuration.

### 4. Dimensionless Preston-inspired native-scale baseline

This is not the SI WP08 Preston model. It uses only active-polish proxy means
and a fitted native-scale coefficient.

For six pressure channels (j\in\mathcal P), let (m_j^+) be the fit-only
median among finite positive active-proxy means. For a record with positive
active-proxy duration, define

\[
p^*_{ij}=\frac{\max(0,p_{ij})}{m_j^+},\qquad
P_i^*=\frac{1}{|\mathcal P|}\sum_{j\in\mathcal P}p^*_{ij}.
\]

Missing active values in an otherwise active record use their fit median, so
their normalized value is one. A record with no active-proxy support receives
zero exposure rather than an imputed nominal polish state.

Normalize absolute wafer, stage, and head rotation by their fit-only positive
medians. With (r_w^*,r_s^*,r_h^*), define the declared relative-speed proxy

\[
V_i^*=\frac{\max(r_{w,i}^*,r_{s,i}^*)+r_{h,i}^*}{2},
\qquad
\phi_i=\mathbb{1}[\text{active support}]P_i^*V_i^*.
\]

The lack of radii, directions, and physical units prevents a true relative
surface velocity calculation; (V_i^*) is an engineering proxy. Fit a
nonnegative, zero-intercept native coefficient

\[
\widehat K_{native}
=\max\left(0,\frac{\sum_i\phi_i y_i}{\sum_i\phi_i^2}\right),
\qquad
\widehat y_i=\widehat K_{native}\phi_i.
\]

The denominator must be finite and positive. Units are
`SOURCE_NATIVE_TARGET_PER_DIMENSIONLESS_EXPOSURE`, not a Preston coefficient in
SI units.

### 5. Histogram gradient-boosted trees

Use scikit-learn `HistGradientBoostingRegressor`, fixed 300-iteration budget,
learning rate 0.05, disabled early stopping, fixed seed, and the preregistered
loss/leaf/minimum-leaf/L2 grid. Disabling internal early stopping avoids an
uncontrolled row-level validation split.

### 6. Physics-plus-residual model

Fit the native-scale physics term on the fit role, define residuals

\[
e_i=y_i-\widehat K_{native}\phi_i,
\]

fit an independently tuned histogram-gradient model (f_\theta(X_i)), and
predict

\[
\widehat y_i
=\max\left(0,\widehat K_{native}\phi_i+f_\theta(X_i)\right).
\]

The tree grid is the same declared grid but is tuned separately on residual
MAE. This hybrid is still a native-scale statistical model, not a calibrated
digital twin.

## Split-conformal residual intervals

For a model fitted on development groups, compute absolute residual scores on
the disjoint interval-calibration wafers:

\[
s_i=|y_i-\widehat y_i|.
\]

At \(\alpha=0.10\), with \(n\) calibration rows, use the finite-sample order
statistic rank

\[
k=\min\{n,\lceil(n+1)(1-\alpha)\rceil\},
\qquad q=s_{(k)}.
\]

The symmetric interval is

\[
[L_i,U_i]=[\max(0,\widehat y_i-q),\widehat y_i+q].
\]

Coverage is reported overall and by stage with interval width. Wafer grouping
protects role independence, but the fixed challenge partitions and possible
distribution shift mean nominal 90% coverage is descriptive, not a real-world
or conditional guarantee.

## Metrics

For error (e_i=\widehat y_i-y_i) and denominator floor
\(\epsilon=10^{-12}\), report:

\[
\mathrm{MAE}=\frac1n\sum_i|e_i|,
\qquad
\mathrm{RMSE}=\sqrt{\frac1n\sum_i e_i^2},
\]

\[
\mathrm{RelMAE}=\frac1n\sum_i
\frac{|e_i|}{\max(|y_i|,\epsilon)},
\qquad
\mathrm{Bias}=\frac1n\sum_i e_i,
\]

and the standard coefficient of determination (R^2). Absolute and relative
error distributions include mean, median, standard deviation, 5th percentile,
95th percentile, and worst case. Also report interval coverage/mean width,
negative raw predictions, clipped predictions, offline batch latency, and
throughput.

Every retained test and validation result is reported overall, Stage A, and
Stage B. Uncertainty intervals for metrics use 1,000 seeded bootstrap resamples
of whole `WAFER_ID` groups and report 2.5th/50th/97.5th percentiles. Paired
model differences resample the same groups and rows.

## Preregistered stress and ablation analyses

All analyses below are secondary and cannot replace the 10 s/full-feature/
`ORIGINAL` primary result.

### Chronological training stress

Order official-training wafers by minimum `META_GROUP_START_TIMESTAMP` and use
70% early fit, 15% middle interval calibration, and 15% late evaluation. Reuse
primary hyperparameters; do not tune on the late block. Report all six models.

### Gap-threshold sensitivity

Rebuild feature bundles from immutable raw data at 5 s and 20 s. Reuse the
10 s-selected hyperparameters and R2.1 precedence. Report all six models under
`ORIGINAL` so model-rank dependence on the engineering continuity rule is
visible. Generated CSVs remain local derived data; manifests and summaries are
evidence.

### Proxy/missing-mode ablation

Using `ORIGINAL` and 10 s features, compare frozen ridge and tree models on:

- `FULL`: all 405 predictors;
- `ACTIVE_ONLY`: five global quality predictors plus the 80
  `ACTIVE_POLISH_PROXY` predictors; and
- `NO_UNRESOLVED`: full predictors excluding the 80 `UNRESOLVED_PROXY`
  predictors.

This tests dependence on proxy construction; it does not identify true phases.

### Consumable/tool-state association

For frozen ridge and tree models, compare `FULL` with a matrix excluding all
per-proxy statistics for source fields:

```text
USAGE_OF_BACKING_FILM
USAGE_OF_DRESSER
USAGE_OF_POLISHING_TABLE
USAGE_OF_DRESSER_TABLE
USAGE_OF_MEMBRANE
USAGE_OF_PRESSURIZED_SHEET
```

Report paired grouped-bootstrap MAE differences. A positive performance
contribution may be described only as an association with the named source
features. It is not causal consumable degradation and the hidden scaling does
not establish physical age.

## Interpretation gates

Claim C-001 may move from blocked to limited public-data support only if the
recommended model, selected before holdout access, has lower MAE than the mean
baseline on both precedence-retained test and final validation, and the final
validation 95% grouped-bootstrap interval for paired MAE difference
`recommended - mean` lies entirely below zero.

The public part of C-008 may state that the hybrid improves on the strongest
non-hybrid baseline only if that baseline is selected on `MODEL_SELECTION`, the
hybrid has lower MAE on both retained holdouts, and the final-validation paired
95% interval for `hybrid - baseline` lies entirely below zero.

C-009 remains an association claim and requires directionally consistent
consumable-ablation results on both retained holdouts plus a final-validation
paired interval entirely above zero for `without - full`. Failure or ambiguity
is reported without changing models, labels, splits, or gates.

Empirical conformal coverage below 0.85 on either retained holdout is a stated
uncertainty failure. No result establishes conditional, production, or
real-world coverage.

## One-shot holdout opening rule

Official test and validation targets may be loaded only after:

1. this decision and its YAML configuration are committed;
2. the feature-only role/split manifest is materialized and hashed;
3. model, preprocessing, interval, metric, and serialization tests pass on
   synthetic fixtures; and
4. the execution script is frozen to run every primary and preregistered
   sensitivity without interactive model selection.

The first target-reading execution generates all results in one nonadaptive
run. A technical failure follows the project failure policy, but no observed
holdout result may change a scientific choice.

## Required artifacts

```text
configs/models/virtual_metrology.yaml
src/semifab_poc/models/virtual_metrology.py
scripts/validate_wp09_virtual_metrology.py
tests/unit/test_virtual_metrology.py
tests/integration/test_vm_evaluation.py
reports/virtual_metrology/
orchestration/reports/wp09_virtual_metrology_validation.md
```

The results artifact must preserve configuration, code/runtime versions,
source/feature hashes, split-group hashes, selected hyperparameters,
recommended-family evidence, fit-scope audits, conformal calibration counts,
metrics, sensitivities, latency, and the complete claim boundary.

## Interface and schema impact

The frozen `Predictor` 1.0 method semantics are implemented without changing
their signatures. The module uses an offline native-scale observation window
and records its feature cutoff as the complete wafer-stage trace. No
`DynamicSubsystem`, sensor, scenario, controller, safety, canonical signal, SI
boundary, or public-measurement schema changes.

## Sources and evidentiary use

- PHM Society 2016 CMP challenge: source objective and filenames.
- Preston (1927): structural proportionality of removal to pressure and
  relative speed; used only as qualitative form.
- Rahman et al. (2024), DOI 10.1109/ICPHM61352.2024.10627679, official NIST
  publisher record: qualitative support for physics-informed PHM MRR modelling.
  No coefficient, unit conversion, architecture, or reported score is copied.

The literature does not bridge proprietary PHM scales to the WP08 SI simulator.
