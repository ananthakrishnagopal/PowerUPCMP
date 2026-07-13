# Decision: official PHM wafer-precedence holdouts

Date: 2026-07-13
Status: ACCEPTED AND IMPLEMENTED AS R2.1 CORRECTION
Scope: T-PHASE12-REMEDIATION and T-WP09
User authorization: Option 1 authorized after the feature-only collision audit

## Decision question

Can the PHM source-defined training, test, and validation partitions be treated
as independent whole-wafer partitions for public virtual metrology?

## Evidence found before model fitting

No. The feature files are disjoint by `(WAFER_ID, STAGE)`, but their wafer IDs
overlap:

| Source partitions | Shared wafer IDs |
|---|---:|
| Training and test | 113 |
| Training and validation | 115 |
| Test and validation | 34 |

All collisions contain the opposite stage and have sequential, non-overlapping
group timestamps: training/test contains 65 A-to-B and 48 B-to-A cases;
training/validation contains 48 A-to-B and 67 B-to-A cases; and
test/validation contains 18 A-to-B and 16 B-to-A cases. No authoritative source
states that these are split-local aliases. The conservative interpretation is
therefore that different stages of one wafer were assigned to different source
partitions.

No official test or validation MRR value was read to make this decision.

## Frozen precedence rule

Source role is never reassigned. For group identity (g=\texttt{WAFER_ID}),
define source group sets (G_{tr},G_{te},G_{va}). Retained sets are

\[
\widetilde G_{tr}=G_{tr},\qquad
\widetilde G_{te}=G_{te}\setminus G_{tr},\qquad
\widetilde G_{va}=G_{va}\setminus(G_{tr}\cup G_{te}).
\]

Validation excludes all original test wafer IDs, including test records that
were themselves excluded for colliding with training. Consequently,

\[
\widetilde G_{tr}\cap\widetilde G_{te}
=\widetilde G_{tr}\cap\widetilde G_{va}
=\widetilde G_{te}\cap\widetilde G_{va}=\varnothing.
\]

The retained public-evaluation roles are:

| Role | Wafer/stage rows | Whole wafers | Stage A rows | Stage B rows |
|---|---:|---:|---:|---:|
| Fit/tune training | 1,981 | 1,699 | 1,166 | 815 |
| Offline test | 311 | 302 | 190 | 121 |
| Final validation | 275 | 267 | 169 | 106 |

The full 424-row source test and 424-row source validation partitions may be
reported only as `OFFICIAL_SOURCE_PARTITION_COLLISION_CONTAMINATED`
diagnostics. They cannot support a whole-wafer-independent claim.

## Leakage and selection policy

- Every imputer, scaler, model, coefficient, and hyperparameter is fitted only
  from official training groups and their inner grouped roles.
- Official test and validation targets remain evaluation-only.
- Official test is not used to select a model, feature set, label policy,
  interval method, or claim threshold.
- Final validation is opened only in the preregistered one-shot evaluation.
- Inner training splits and cross-validation also group complete `WAFER_ID`
  values, not wafer/stage rows.
- Full-partition contaminated diagnostics must never replace the retained-set
  primary results, even if they appear better.

## Implementation and evidence

`official_group_precedence_split` applies the rule without reading targets or
reassigning rows. Its audit records original/retained group and row counts,
dropped rows, pairwise overlaps, grouping columns, and interpretation. The
audit is regenerated in:

- `data/processed/phm_2016_cmp/feature_manifest.yaml`; and
- `reports/data/phm_semantic_audit.json`.

The nine processed CSV files retained their exact pre-amendment SHA-256 values;
only the manifest gained split evidence.

## Scientific consequence

Earlier statements that the complete official partitions were whole-wafer
isolated are withdrawn. Feature construction and label joins remain
source-partition isolated, but independent generalization metrics must use the
precedence-retained subsets. This correction narrows the evidence; it does not
alter the measured target, raw data, features, source roles, or primary claim.

## Interface and schema impact

No frozen component interface, public-measurement schema, predictor method
signature, raw file, or feature-column contract changes. This is an additive
split-governance correction.
