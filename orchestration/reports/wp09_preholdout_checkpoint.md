# WP09 pre-holdout implementation checkpoint

Date: 2026-07-13 12:24 IST
Task: T-WP09
State: IMPLEMENTED AND TESTED BEFORE OFFICIAL HOLDOUT TARGET ACCESS
Evidence plane: PHM 2016 CMP offline average-MRR virtual metrology

## Claim boundary

This checkpoint contains implementation and target-blind split evidence only.
It contains no fitted public-data model, no official test or validation MRR
metric, and no public-data validation claim. The target remains
`AVG_REMOVAL_RATE` in `SOURCE_NATIVE_UNIT_UNDECLARED`; the 405 process
predictors remain in proprietary scaled source space. Nothing in this package
bridges those values to the synthetic simulator's SI states or coefficients.

## Implemented protocol

The controlled module implements all six frozen model families: mean, ordinary
linear regression, ridge regression, a dimensionless native-scale
Preston-inspired proxy, histogram gradient-boosted trees, and a
physics-plus-residual tree. Common preprocessing is fitted independently on
each fit role. For raw predictor \(x_j\), the fit-only median \(m_j\) gives

\[
x'_{ij}=\begin{cases}
x_{ij}, & x_{ij}\text{ finite},\\
m_j, & \text{otherwise},
\end{cases}
\qquad
z_{ij}=\mathbb{1}[x_{ij}\text{ is missing}].
\]

Every raw feature receives a missingness indicator. Zero-variance derived
columns are removed using the fit role only. Linear and ridge designs use
fit-only population standardization; tree designs use the same imputed and
screened columns without scaling. No target-driven feature selection exists.

The native-scale physics proxy uses six normalized pressure signals and three
normalized absolute rotation signals from the active-polish input proxy:

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

This is an engineering proxy, not an SI Preston calibration. The hybrid fits
the frozen tree grid to residuals

\[
e_i=y_i-\widehat K_{native}\phi_i,
\qquad
\widehat y_i=\max\left(0,
\widehat K_{native}\phi_i+f_\theta(X_i)\right).
\]

Five deterministic whole-wafer folds tune hyperparameters inside
`TRAIN_CORE` using pooled out-of-fold MAE. The model-family recommendation is
then selected on `MODEL_SELECTION` only. Final development fitting combines
`TRAIN_CORE + MODEL_SELECTION`; `INTERVAL_CALIBRATION` stays disjoint. Its
absolute residuals produce the exact finite-sample split-conformal radius

\[
k=\min\{n,\lceil(n+1)(1-\alpha)\rceil\},
\qquad q=s_{(k)},\qquad \alpha=0.10,
\]

and interval

\[
[L_i,U_i]=[\max(0,\widehat y_i-q),\widehat y_i+q].
\]

Artifacts record fit and calibration split identities, row and group counts,
group hashes, preprocessing-state hashes, physics-state hashes, conformal
radii, raw-negative and clipped counts, runtime versions, and repository-local
paths.

## Target-blind split evidence

The frozen split manifest is
`reports/virtual_metrology/wp09_split_manifest.json`.

| Role | Rows | Whole wafers |
|---|---:|---:|
| TRAIN_CORE | 1,396 | 1,189 |
| MODEL_SELECTION | 299 | 255 |
| INTERVAL_CALIBRATION | 286 | 255 |
| OFFICIAL_TEST_RETAINED | 311 | 302 |
| OFFICIAL_VALIDATION_RETAINED | 275 | 267 |

All ten pairwise wafer-overlap counts are zero. The manifest states
`holdout_targets_accessed: false` and `target_in_feature_files: false`.

- Manifest file SHA-256:
  `7df9d9e1de5c2dbcb015c77fff28e9e6b058b9824b6e5f4a2b266aca0451bb33`
- Deterministic manifest payload SHA-256:
  `44c8851653b39832357e42fba29f5d797ab574dc2e64f3e073c88c686b0ba944`
- Predictor-order SHA-256:
  `591f68e7a01c118f9ff822ba23009b7d6cf50c5f67111df0c33cb9d17ea4ce42`

The official source roles still contain 113/115/34 colliding wafer IDs. The
accepted `training > test > validation` precedence removes later-role
collisions without reassigning rows. Full 424-row source holdouts remain
explicitly collision-contaminated diagnostics.

## One-shot execution guard

The thin script has separate `--prepare-splits` and `--run-one-shot` modes.
The one-shot mode refuses target access unless all of the following hold:

1. `--authorize-holdout-open` is present;
2. the opening marker and final result do not already exist;
3. the committed target-blind manifest replays exactly;
4. the Git worktree is completely clean;
5. the decision, configuration, manifest, module, script, and tests exist in
   `HEAD` and are unchanged;
6. focused synthetic and feature-only tests pass with warnings as errors; and
7. the Git checkpoint remains unchanged after those tests.

Immediately before the target boundary, the script writes a persistent
opening-authorization marker. A failed attempt cannot silently rerun. The
runner then opens every required label table in one noninteractive execution
and performs all primary, label-policy, chronological, feature-ablation,
consumable-ablation, and gap-threshold analyses without user-selected branches.

## Verification

- Focused WP09 suite: 19 passed in 5.63 s with warnings treated as errors.
- Complete repository suite: 192 passed in 52.40 s with warnings treated as
  errors.
- Python syntax preflight: passed.
- Trailing-whitespace scan: passed.
- `git diff --check`: passed.

The focused suite covers strict configuration, all six model families,
fit-only preprocessing, native-proxy limiting behavior, whole-wafer folds,
training-only tuning, split-conformal quantiles, grouped bootstrap equations,
artifact checksums, target-boundary joins using synthetic labels, exclusion
policy scope, real target-free role replay, and explicit CLI authorization.

## Checkpoint disposition

The implementation and split manifest are ready to be committed as the frozen
pre-holdout checkpoint. Only after that commit and a clean-worktree replay may
the already authorized one-shot run open official test and validation MRR
targets. Observed results must not change the frozen models, label policies,
splits, sensitivities, or interpretation gates.
