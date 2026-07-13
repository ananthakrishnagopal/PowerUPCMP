# WP09 public CMP virtual-metrology validation

Date: 2026-07-13<br>
Task: T-WP09<br>
Experiment revision: `1.0-preregistered`<br>
Evidence plane: `PUBLIC_PHM_SOURCE_NATIVE_OFFLINE_AVERAGE_MRR`<br>
Disposition: COMPLETE with limited public-data support and an uncertainty failure

## Executive determination

WP09 provides limited public-data support for offline average material-removal-
rate virtual metrology on the PHM 2016 CMP challenge data. The tree family was
selected on the training-only `MODEL_SELECTION` role before official holdout
targets were opened. On mutually whole-wafer-disjoint, precedence-retained
roles, it achieved:

| Metric | Retained test | Retained final validation |
|---|---:|---:|
| Rows / whole wafers | 311 / 302 | 275 / 267 |
| MAE | 3.1852 | 3.3954 |
| RMSE | 5.1756 | 6.6932 |
| Relative MAE | 3.572% | 3.858% |
| \(R^2\) | 0.9751 | 0.9585 |
| Bias | -0.2941 | -0.2581 |
| Empirical interval coverage | 0.8392 | 0.8473 |
| Mean interval width | 10.6995 | 10.6995 |

All numerical target results are in the original source-native scale whose
unit is not declared. They must not be reported as nm/min, m/s, or any other SI
unit.

The tree reduced MAE relative to the mean baseline by 89.22% on retained test
and 88.57% on retained final validation. The final-validation whole-wafer
bootstrap interval for paired `tree - mean` MAE was
[-28.1911, -24.3631], with median -26.3288. The preregistered C-001 gate
therefore passes.

Two other scientific gates do not pass. The hybrid was worse than the selected
non-hybrid tree on both retained holdouts, and its final-validation paired
`hybrid - tree` interval was entirely positive. Consumable-feature ablation
favoured full features for the tree but favoured removal for ridge, so the
cross-model association gate fails. Neither result may be reframed as a
positive claim.

The tree's nominal 90% split-conformal intervals cover only 83.92% and 84.73%
of retained test and validation rows. Both are below the frozen 0.85 minimum
interpretation coverage. Point prediction is supported within the narrow
offline setting, but the primary uncertainty model fails its preregistered
interpretation gate.

## Claim boundary

The source label `AVG_REMOVAL_RATE` is the measured process output available in
the public challenge. Process-mode fields used by WP09 are derived input
proxies, not measured phases. This work package contains no simulated physical
state, no electrical or UPW causal test, no process-excursion target, no
spatial result, and no controller action.

It does not validate a physical defect, wafer yield, equipment damage,
real-fab generalization, online warning, real production control, or
microsecond response. The dimensionless physics baseline is not the SI WP08
Preston model, and no coefficient crosses between those evidence planes.

## Controlled target access

The scientific decision and strict YAML configuration were committed before
implementation. The tested implementation, synthetic fixtures, target-blind
whole-wafer split manifest, and one-shot guard were then committed as Git
checkpoint `01c59a6172f621ed7f81a01487a5e4358805463c`.

The split manifest stated `holdout_targets_accessed: false`, contained 405
predictors, and had deterministic payload SHA-256
`44c8851653b39832357e42fba29f5d797ab574dc2e64f3e073c88c686b0ba944`.
All ten pairwise whole-wafer role-overlap counts were zero. The one-shot guard
replayed the manifest, verified a completely clean worktree and all required
files in `HEAD`, and reran the focused suite with warnings treated as errors.
All 19 tests passed immediately before target access.

The explicit authorization was consumed at 2026-07-13 06:57:27 UTC. The
runner opened the three preregistered training-label tables and the official
test/validation label tables once into memory, then executed every frozen
primary and sensitivity branch without interaction. No target result changed a
split, model grid, label policy, sensitivity, or interpretation gate.

The full source test and validation tables each contain 424 rows, but the
source partitions reuse 113/115/34 wafer IDs across role pairs. The accepted
`training > test > validation` precedence retained 1,981/311/275 rows from
1,699/302/267 mutually disjoint wafers. Full source holdouts are reported only
as collision-contaminated diagnostics.

## Frozen fitting design

The 1,699 training wafers were assigned from target-free identity with seed
90209:

| Role | Rows | Whole wafers | Purpose |
|---|---:|---:|---|
| TRAIN_CORE | 1,396 | 1,189 | Five-fold grouped tuning |
| MODEL_SELECTION | 299 | 255 | Family recommendation |
| INTERVAL_CALIBRATION | 286 | 255 | Absolute residual intervals |

Common preprocessing fits medians and missing indicators on each fit role,
removes zero-variance derived columns there, and standardizes only linear and
ridge designs. The final tree retained 776 of 810 derived columns. Its final
development fit used 1,444 whole wafers; its calibration role used 286 rows
from 255 disjoint wafers.

For the native physics proxy, active-polish input-proxy values form

\[
P_i^*=\frac{1}{6}\sum_{j=1}^{6}
\frac{\max(0,p_{ij})}{m_j^+},
\qquad
V_i^*=\frac{\max(r_{w,i}^*,r_{s,i}^*)+r_{h,i}^*}{2},
\]

\[
\phi_i=\mathbb{1}[\text{active support}]P_i^*V_i^*,
\qquad
\widehat K_{native}=max\left(0,
\frac{\sum_i\phi_i y_i}{\sum_i\phi_i^2}\right).
\]

The hybrid fits a gradient-boosted residual model to

\[
e_i=y_i-\widehat K_{native}\phi_i,
\qquad
\widehat y_i=\max(0,\widehat K_{native}\phi_i+f_\theta(X_i)).
\]

For calibration residuals \(s_i=|y_i-\widehat y_i|\), the symmetric split-
conformal radius is the exact order statistic

\[
k=\min\{n,\lceil(n+1)(1-0.10)\rceil\},
\qquad q=s_{(k)}.
\]

The selected tree radius was 5.3498 source-native target units. Its reported
interval is

\[
[L_i,U_i]=[\max(0,\widehat y_i-q),\widehat y_i+q].
\]

## Training-only model selection

Five deterministic whole-wafer folds inside `TRAIN_CORE` selected all
hyperparameters. Family recommendation then used only `MODEL_SELECTION` MAE:

| Family | Model-selection MAE | Selected hyperparameters |
|---|---:|---|
| Tree | 17.2200 | absolute loss, 15 leaves, min leaf 20, L2 0.1 |
| Hybrid | 18.5896 | absolute loss, 15 leaves, min leaf 20, L2 1.0 |
| Mean | 41.7068 | none |
| Physics proxy | 45.5632 | nonnegative zero-intercept coefficient |
| Ridge | 46.9161 | alpha 1000 |
| Linear | 89.4856 | ordinary least squares |

The tree was therefore the immutable recommended family before test or final
validation labels were read. All six families were nevertheless refitted and
reported.

## Primary held-out comparison

### Point metrics

| Family | Test MAE | Validation MAE | Test RMSE | Validation RMSE | Test \(R^2\) | Validation \(R^2\) |
|---|---:|---:|---:|---:|---:|---:|
| Mean | 29.5400 | 29.7025 | 33.1515 | 33.1700 | -0.0215 | -0.0196 |
| Linear | 101.2547 | 215.6368 | 413.7734 | 1955.5434 | -158.1325 | -3542.9146 |
| Ridge | 28.4256 | 35.3248 | 47.4487 | 65.0382 | -1.0926 | -2.9200 |
| Physics proxy | 34.0775 | 35.7089 | 61.0857 | 62.1236 | -2.4683 | -2.5765 |
| Tree | **3.1852** | **3.3954** | **5.1756** | **6.6932** | **0.9751** | **0.9585** |
| Hybrid | 4.7226 | 5.9346 | 8.2511 | 11.7036 | 0.9367 | 0.8731 |

### Relative error and intervals

| Family | Test relative MAE | Validation relative MAE | Test coverage | Validation coverage | Interval width |
|---|---:|---:|---:|---:|---:|
| Mean | 31.711% | 32.054% | 0.8521 | 0.8655 | 102.7652 |
| Linear | 95.584% | 213.289% | 0.8939 | 0.8945 | about 234.5 |
| Ridge | 26.684% | 32.667% | 0.9132 | 0.8836 | about 157 |
| Physics proxy | 28.373% | 30.139% | 0.8746 | 0.8873 | about 220 |
| Tree | **3.572%** | **3.858%** | **0.8392** | **0.8473** | **10.6995** |
| Hybrid | 5.050% | 6.523% | 0.9164 | 0.9055 | 23.7746 |

Ordinary least squares is numerically and statistically unsuitable for this
high-dimensional, collinear feature space: 22/23 retained test/validation raw
predictions were negative and clipped, and rare extrapolations produced worst
absolute errors of 5,011 and 29,828. Ridge clipped 6/4 predictions and was much
more stable than OLS, but did not beat the mean consistently. Tree and hybrid
required no nonnegative clipping.

The dimensionless physics proxy was worse than the mean by 4.54 MAE units on
test and 6.01 on final validation. It supplies an interpretable structural
reference, not a competitive calibrated physical model in this scaled data
plane.

The [model-comparison figure](../../reports/virtual_metrology/figures/wp09_model_comparison.png)
and [final-validation scatter](../../reports/virtual_metrology/figures/wp09_tree_validation_scatter.png)
show the complete comparison and the tree's stage-resolved predictions.

## Grouped-bootstrap and stage evidence

One thousand seeded bootstrap samples resampled whole wafers. For the tree:

| Role | MAE 95% interval | RMSE 95% interval | Relative-MAE 95% interval | \(R^2\) 95% interval |
|---|---|---|---|---|
| Retained test | [2.7786, 3.7366] | [3.7158, 7.4440] | [3.178%, 4.061%] | [0.9495, 0.9873] |
| Retained validation | [2.7839, 4.1083] | [3.7601, 9.3375] | [3.298%, 4.475%] | [0.9208, 0.9869] |

Stage-stratified tree MAE was 3.1267/3.2771 for test A/B and
3.6235/3.0317 for validation A/B. Test coverage was 0.8526 for Stage A and
0.8182 for Stage B; validation coverage was 0.8521 and 0.8396. The uncertainty
shortfall is therefore not confined to only one held-out role or stage.

## Interpretation gates

### C-001: public average-MRR prediction

`SUPPORTED_WITH_LIMITS`. The tree was selected before target access, beat the
mean on both retained holdouts, and had final-validation paired
`tree - mean` MAE bootstrap percentiles [-28.1911, -26.3288, -24.3631]. This
supports only offline average-MRR prediction for the named precedence-retained
PHM roles.

### Public part of C-008: hybrid improvement

`NOT_SUPPORTED`. The strongest non-hybrid family selected on
`MODEL_SELECTION` was the tree. Hybrid MAE was higher by 1.5374 on retained
test and 2.5392 on retained validation. Final-validation paired
`hybrid - tree` percentiles were [1.5017, 2.4968, 3.6496], entirely in the
wrong direction for the frozen gate.

### C-009: consumable-feature association

`NOT_SUPPORTED_ACROSS_FROZEN_MODELS`. Removing the six consumable-usage signal
families increased tree MAE by 0.7852/0.8147 on retained test/validation; its
validation paired `without - full` interval was [0.5967, 1.0559]. In contrast,
removal improved ridge MAE by 3.0500/6.7417, with interval
[-9.4054, -4.1407]. The sign is model-dependent, so the cross-model gate fails.
Even the tree-specific result is only predictive association, never causal
consumable degradation or physical age.

## Preregistered sensitivities

### Training-label treatments

Hyperparameters remained those selected under `ORIGINAL`; official holdout
labels never changed.

| Tree training-label policy | Test MAE | Validation MAE | Test coverage | Validation coverage |
|---|---:|---:|---:|---:|
| ORIGINAL primary | 3.1852 | 3.3954 | 0.8392 | 0.8473 |
| Exclude four preregistered labels | 3.0502 | 3.1003 | 0.8553 | 0.8618 |
| Hypothetical divide four by 60 | 3.0319 | 3.3562 | 0.8714 | 0.8618 |

The primary result remains `ORIGINAL`. The sensitivity outcomes cannot be used
to retroactively select a label policy.

### Continuity threshold and feature-proxy dependence

| Tree variant | Test MAE | Validation MAE | Test coverage | Validation coverage |
|---|---:|---:|---:|---:|
| Primary 10 s / full | 3.1852 | 3.3954 | 0.8392 | 0.8473 |
| 5 s continuity gap | 3.0270 | 3.4687 | 0.9003 | 0.8836 |
| 20 s continuity gap | 3.0823 | 3.3124 | 0.8875 | 0.8727 |
| Active-polish plus global features | 3.2832 | 3.5901 | 0.8746 | 0.8727 |
| Exclude unresolved-proxy features | 3.1788 | 3.4946 | 0.8714 | 0.8618 |

Point MAE remains close across the declared 5/10/20 s continuity choices and
proxy subsets. Coverage is more sensitive and improves in every listed
secondary variant relative to the primary. These secondary outcomes do not
rescue the failed primary uncertainty gate. The
[sensitivity figure](../../reports/virtual_metrology/figures/wp09_tree_sensitivity.png)
shows both the 0.90 nominal level and frozen 0.85 interpretation floor.

### Chronological stress

The 70% early fit, 15% middle calibration, and 15% late evaluation roles
contained 1,384/294/303 rows from 1,189/255/255 whole wafers. The tree's late
MAE was 18.4996, RMSE 239.8355, \(R^2=0.0371\), and coverage 0.8119. Median
absolute error remained 3.1918 and the 95th percentile 14.4747, but one
preregistered extreme training-label case dominated the tail:

```text
WAFER_ID 2058207580, Stage A
target:     4326.15405 source-native
prediction: 152.92713 source-native
abs error:  4173.22692 source-native
```

The late-block target median was 83.3088 and only this row exceeded 500. The
stress result therefore demonstrates both temporal fragility and sensitivity
to the known extreme-label problem. No post-hoc exclusion result was fitted.
Machine generalization remains untestable because the dataset exposes only one
machine identifier.

### Collision-contaminated source diagnostics

On the full non-independent 424-row source partitions, tree MAE was 3.3866 for
test and 3.2938 for validation, versus 3.1852 and 3.3954 on the retained roles.
The mixed direction illustrates why these partitions are diagnostic only.
They are not substituted for the leakage-safe primary evidence.

## Uncertainty interpretation

The primary tree's 90% marginal split-conformal construction missed nominal
coverage by 6.08 and 5.27 percentage points on retained test and validation,
and missed the frozen minimum by 1.08 and 0.27 points. This is a declared
failure, not rounded into success. Likely contributors include distribution
shift, stage heterogeneity, row dependence within two-stage wafers, and the
use of a single symmetric absolute-residual radius. These are hypotheses for
future design, not post-hoc corrections to WP09.

The hybrid's wider intervals exceeded 90% coverage, but that does not make it
the selected predictor: it had materially worse point error and failed the
hybrid-improvement gate. A future uncertainty-focused model may study grouped,
stage-conditional, normalized, or quantile intervals using newly separated
calibration/evaluation data. WP09 itself remains frozen.

## Reproducibility evidence

Primary artifacts:

- [frozen decision](../decisions/wp09_virtual_metrology.md);
- [strict configuration](../../configs/models/virtual_metrology.yaml);
- [pre-holdout checkpoint](wp09_preholdout_checkpoint.md);
- [implementation](../../src/semifab_poc/models/virtual_metrology.py);
- [guarded runner](../../scripts/validate_wp09_virtual_metrology.py);
- [target-blind split manifest](../../reports/virtual_metrology/wp09_split_manifest.json);
- [machine-readable result](../../reports/virtual_metrology/wp09_validation.json);
- [row-aligned predictions](../../reports/virtual_metrology/wp09_predictions.csv);
- [opening marker](../../reports/virtual_metrology/wp09_holdout_opening.json); and
- [figure manifest](../../reports/virtual_metrology/figures/wp09_figure_manifest.json).

Hashes:

| Artifact | SHA-256 |
|---|---|
| Validation JSON | `52d25cf92c4eea24158e0821cd7b7dd60fabe2ec04967443e3417397313bd10c` |
| Deterministic validation payload | `84d4823b7972e289a67f62a4bf1ea348d007ddd0f6285b4dd32d36178da320db` |
| Prediction CSV | `ea3e9e813e8343862340fb42bfc31c784e0f5df9bd15f5b0f707624bb4679826` |
| Split manifest file | `7df9d9e1de5c2dbcb015c77fff28e9e6b058b9824b6e5f4a2b266aca0451bb33` |
| Tree model | `140f395f4735f22edce20df444e36ac96a6ffde9c8006e15707f08dabe404184` |
| Hybrid model | `7107eb17191e860c2c0d0ded66e051ffd0c80b37128c390b8d78877ed2d19f84` |

All six serialized models reload with checksum verification. The run used
CPython 3.13.12, NumPy 2.2.6, pandas 2.3.3, Pydantic 2.12.5, PyYAML 6.0.3,
and scikit-learn 1.8.0 on Linux aarch64. Before target access, the focused suite
passed 19/19 and the full repository passed 192/192 with warnings treated as
errors. Post-result documentation and figure generation do not alter the
frozen validation artifact.

## Final disposition and downstream use

T-WP09 is complete within its narrow public-data claim boundary. The selected
tree may serve as the offline PHM average-MRR benchmark for model comparison,
but it cannot be inserted directly into the SI simulator or a production
controller. Its uncertainty output fails the frozen interpretation floor and
must not be treated as a reliable safety bound.

WP13 attribution may use simulator truth and residual-chain evidence but must
not infer electrical/UPW causes from this PHM model. WP15/WP16 control and
safety decisions must remain on the synthetic simulator evidence plane unless
a future real-fab data contract supplies aligned utility, tool, metrology, and
action records with declared units and topology.
