# R2 PHM semantics validation

Date: 2026-07-11; R2.1 precedence correction 2026-07-13
Task: T-PHASE12-REMEDIATION, subgate R2  
Disposition: VALIDATED WITH WHOLE-WAFER PRECEDENCE CORRECTION FOR OFFLINE
NATIVE-UNIT VM PREPARATION

## Scope and evidence boundary

R2 corrects PHM source-order, phase, time-weighting, label-anomaly, and split
semantics. The process columns remain proprietary scaled values and the target
remains in its original undeclared/native unit. R2 does not calibrate the SI
simulator, validate a Preston coefficient, or establish an electrical/UPW
causal connection.

The preregistered policy and equations are in
`orchestration/decisions/r2_phm_semantics.md`.

## Source preservation and timestamp evidence

The loader now records `SOURCE_ROW_INDEX` before concatenation. Header-only
traces remain in the extraction inventory but are excluded from pandas
concatenation, eliminating the prior empty-frame FutureWarning without
imputing, deleting, or manufacturing measurements.

Timestamp calculations retain original source order within trace, wafer, and
stage. At a fixed 10 s continuity threshold:

| Split | Rows | Wafer/stage groups | Segments | Zero increments | Negative increments | Gaps >10 s |
|---|---:|---:|---:|---:|---:|---:|
| Training | 672,744 | 1,981 | 4,013 | 2,221 | 3 | 2,004 |
| Test | 156,262 | 424 | 858 | 188 | 0 | 427 |
| Validation | 144,148 | 424 | 856 | 498 | 2 | 424 |

The five negative increments are retained in
`reports/data/phm_semantic_audit.json`. Each starts a new continuity segment;
no time weight crosses the reversed boundary. Zero increments remain duplicate
evidence and contribute no duplicated interval duration.

For valid adjacent increments, centered row support is

\[
w_i=\tfrac12\Delta t_{i-1}^{valid}+\tfrac12\Delta t_{i+1}^{valid}.
\]

Time-weighted signal means and population variances use these supports. Long
gaps, reversals, and duplicate timestamps cannot dominate a feature merely by
their numeric separation or repeated row count.

## Input-only process-mode proxies

An active-polish candidate requires nonzero pressure, slurry, wafer-or-stage
rotation, and head rotation. No target or holdout statistic participates.
Rows are labelled as preparation, active polish, within-polish transition,
ending/cleaning, or unresolved **proxies** according to their position within
each continuity segment.

Groups with no strict active-polish candidate are retained:

| Split | Unresolved wafer/stage groups |
|---|---:|
| Training | 221 |
| Test | 43 |
| Validation | 42 |

The proxy names do not assert measured physical phases. Dressing-water status
is retained as a signal rather than used alone as a phase label.

## Phase-aware feature bundle

`data/processed/phm_2016_cmp/feature_manifest.yaml` records the deterministic
bundle:

| Split | Feature rows | Columns | Predictor columns | Target in feature file |
|---|---:|---:|---:|---|
| Training | 1,981 | 417 | 405 | No |
| Test | 424 | 417 | 405 | No |
| Validation | 424 | 417 | 405 | No |

Each feature file contains group/quality metadata, per-mode coverage, and
time-weighted mean/standard-deviation/minimum/maximum features. Absolute group
timestamps are metadata only and are absent from the predictor-column
contract. Labels are stored in separate native-unit files and join one-to-one
after feature engineering with zero missing or orphan keys in all splits.

The manifest records SHA-256, size, row count, column count, source archive
checksum, split role, feature contract, and label-policy audit for every file.
The bundle builder is `python -m semifab_poc.data.build_features`; the script
wrapper is `scripts/build_phm_features.py`.

## Label anomalies

The implementation verifies the exact keys and original values of the four
4,129--4,326 training labels before any treatment. It generated:

- `ORIGINAL`: 1,981 rows, primary treatment;
- `EXCLUDE_FOUR_PREREGISTERED`: 1,977 rows; and
- `HYPOTHETICAL_DIVIDE_FOUR_BY_60`: 1,981 rows with the original values in a
  separate immutable column.

All audits state that holdout metrics were not used to choose a treatment. The
maximum remaining ordinary training label is 162.6417.

## Split and leakage evidence

- Official training, test, and validation feature construction runs
  independently before labels are joined.
- The source partitions are not whole-wafer independent: 113 training/test,
  115 training/validation, and 34 test/validation wafer IDs recur in the
  opposite stage. No `(WAFER_ID, STAGE)` key repeats.
- The accepted `training > test > validation` precedence rule retains
  1,981/311/275 rows from 1,699/302/267 mutually disjoint wafers. Full 424-row
  test and validation source partitions are explicitly collision-contaminated
  diagnostics and cannot support independent-wafer claims.
- Inner random development splits retain whole wafers.
- Chronological stress splits retain whole wafers and use group-start time as
  split metadata, not a predictor.
- Fit-scope auditing rejects any fitted transform whose group set is not a
  subset of training or overlaps validation/test.
- Physical machine holdout is infeasible because all rows have `MACHINE_ID=2`.
- `MACHINE_DATA` is also unsuitable as a replacement holdout: 1,979/1,981
  training groups and every test/validation group contain multiple values.
- Stage-separated, combined-stage, chronological, and trace stress evaluations
  remain available without making a machine-generalization claim.

## Validation evidence

```text
R2 synthetic unit suite:       13 passed
R2 real-data integration:       6 passed
Complete repository suite:     82 passed in 36.83 s
Warnings:                       0
R2.1 focused correction suite:  16 passed in 36.88 s
Post-correction complete suite: 173 passed in 49.71 s
```

The regenerated nine processed CSV files preserve their exact pre-correction
SHA-256 values. The additive feature manifest hash is
`40c0d9121f87517eba8bb2d100ff49c17357f348d0821756f59a5c87da98707c`,
and the regenerated semantic-audit hash is
`c4eeede30caa8a24f0c2dbdfcc3a5cb4465cc703193ed7ba6921fa83a0a88732`.
Governance parses 15 YAML files with zero duplicate keys, an acyclic 29-task
DAG, 25 assumptions, 105 Markdown files, 98 valid local links, and zero missing
links. The amended 13-page manuscript rebuild passes its severe-warning audit.

The earlier one-test failure was resolved under the failure policy after
source-order inspection proved the test expectation wrong. The implementation
and report now preserve all five timestamp reversals.

## Acceptance result

| Requirement | Result |
|---|---|
| Missing unit test file supplied | PASS |
| Source row order preserved | PASS |
| Duplicate/gap/reversal evidence reported | PASS |
| Centered time weighting tested | PASS |
| Input-only mode proxy tested | PASS |
| Unresolved groups retained | PASS |
| Target excluded from feature construction | PASS |
| Official source roles and labels constructed separately | PASS |
| Cross-partition wafer collisions measured | PASS |
| Precedence-retained evaluation subsets wafer-disjoint | PASS |
| Four anomaly policies exact and audited | PASS |
| Wafer and chronological group splits leakage-free | PASS |
| Fit scope audited | PASS |
| Machine/MACHINE_DATA infeasibility explicit | PASS |
| Reproducible processed bundle and checksums | PASS |
| Focused and full tests | PASS |

## Remaining limitations

- Proxy phases have not been compared with authoritative row-level phase
  labels because none are supplied.
- The 10 s gap threshold is an engineering rule and requires sensitivity
  analysis if downstream model rankings depend on it.
- Feature dimensionality and missing-mode behavior require train-only
  preprocessing and model ablation in WP09.
- The retained test and validation subsets are smaller than the source
  partitions; full-partition diagnostics are not independent-wafer evidence.
- No PHM accuracy or uncertainty result exists yet.
- Dataset licensing remains limited to recorded local user authorization.
- R3 plant physics and R4 timing/scenario corrections remain open.
