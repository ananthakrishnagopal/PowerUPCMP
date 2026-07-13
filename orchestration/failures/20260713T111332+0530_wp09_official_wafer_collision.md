# Failure report

## Task

WP09 pre-implementation freeze of leakage-safe PHM 2016 CMP virtual-metrology
splits.

## Failed command

No command crashed. A feature-only split audit failed the planned scientific
invariant that every evaluated wafer ID be disjoint from fitted wafer IDs:

```text
official feature-set WAFER_ID overlap audit
```

## Error

The official source partitions reuse wafer IDs:

```text
training/test WAFER_ID overlap:        113
training/validation WAFER_ID overlap:  115
test/validation WAFER_ID overlap:       34
```

All `(WAFER_ID, STAGE)` pairs are disjoint. Every collision is the opposite
stage of the same wafer ID, and timestamps are sequential rather than
overlapping:

```text
training/test:       65 A->B and 48 B->A
training/validation: 48 A->B and 67 B->A
test/validation:     18 A->B and 16 B->A
```

This pattern is consistent with cross-stage information from one wafer being
placed in different official partitions. It is not evidence that wafer IDs are
split-local aliases.

## Files changed before failure

- `orchestration/failures/20260713T110328+0530_wp09_manifest_path_audit.md`
  was created during the preceding, separately authorized manifest-path
  recovery.

No WP09 code, configuration, decision record, split artifact, processed data,
or model result was created or modified. Official test and validation target
values were not inspected.

## Read-only diagnosis

The collision audit read only `WAFER_ID`, `STAGE`, and group timestamp metadata
from the three target-free feature files. It established:

- zero repeated `(WAFER_ID, STAGE)` keys across official partitions;
- every repeated wafer ID occurs in the opposite stage;
- group timestamp order agrees with the A/B direction in every collision; and
- a conservative precedence partition `training > test > validation` would
  retain 311 test rows from 302 wafers and 275 validation rows from 267 wafers.

Under that precedence policy, the retained test set excludes every training
wafer ID, and the retained validation set excludes every training or test wafer
ID. Both retained sets still contain Stage A and Stage B rows.

The processed-file SHA-256 values match `feature_manifest.yaml`; this is a
source split-semantics issue, not file corruption.

## Likely causes

The challenge's official partitions appear to be disjoint by wafer-stage
record rather than by complete wafer. The prior R2 wording described official
role and feature-construction isolation but did not audit cross-partition wafer
identity. Treating the full official partitions as independent whole-wafer
holdouts would therefore overstate generalization and conflict with the
project's grouped-split policy.

## Recovery options

1. Freeze a conservative precedence policy: fit only official training; use
   the 311-row test subset whose wafer IDs are absent from training; and use
   the 275-row final-validation subset whose wafer IDs are absent from both
   training and test. Report the full official partitions only as
   wafer-collision-contaminated descriptive diagnostics. Amend the R2 report,
   risk register, task decision, and tests before model fitting.
2. Use only leakage-safe inner splits of official training for claims and
   decline all official test/validation performance claims.
3. Treat wafer IDs as split-local aliases and retain all official rows. This
   requires authoritative source evidence that is not currently available and
   is therefore not scientifically defensible now.
4. Pause public-data modelling.

## Recommended option

Option 1. It preserves the source-defined official roles while enforcing the
project's stronger whole-wafer rule. It also keeps substantial, stage-diverse
test and final-validation samples. Every exclusion and both full-partition
diagnostics must remain auditable.

## User decision required

Authorize Option 1 before amending split governance or implementing WP09.
