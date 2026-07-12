# Dataset provenance and evaluation policy

Status: raw PHM evidence and corrective Gate R2 semantic pipeline validated;
public virtual-metrology evaluation has not begun.  
Last updated: 2026-07-11

## PHM 2016 CMP source

The user supplied `PHM-Data-Challenge-master.zip` locally. The project did not
download the archive. Recorded evidence:

- archive size: 17,399,074 bytes;
- archive SHA-256:
  `976b23102b576ed610db8f89293de333820391c581d88bcbdb6364da212a1eb9`;
- ZIP CRC check: passed;
- selected original members: 558;
- selected traces: 185 training, 185 test, and 185 validation CSVs;
- selected removal-rate tables: training, test, and validation;
- header-only traces: 58, retained explicitly with no imputation; and
- answer directories, derived experiments, cached files, and processed outputs
  excluded from the raw dataset.

The detailed extraction record is
`data/raw/phm_2016_cmp/extraction_manifest.yaml`. The official challenge page
is <https://phmsociety.org/conference/annual-conference-of-the-phm-society/annual-conference-of-the-prognostics-and-health-management-society-2016/phm-data-challenge-4/>.

The bundled repository has an MIT licence, but no separate licence declaration
for the embedded dataset was found. The user authorized local research use
with that limitation. This project does not assert redistribution rights.

## Original data semantics

The original challenge states that the process columns are scaled by hidden
values. Therefore air-bag pressure, chamber pressure, slurry, rotation, and
consumable fields are useful as native scaled signals but cannot be treated as
Pa, m³/s, rad/s, or physical ages without source-supported conversion.

The original challenge does not explicitly state the MRR target unit. Later
NIST-affiliated work reports nm/min, but this is recorded only as a literature
interpretation. The unconverted PHM target is the primary public-data target
until an authoritative conversion decision exists.

Public PHM measurements and SI simulator states are separate evidence planes.
An SI simulator MRR must not be added to a residual fitted on scaled PHM data.

## Raw loader evidence

The implemented loader validates:

- extraction-manifest membership, size, and SHA-256;
- exact 25-column trace headers;
- exact three-column removal-rate headers;
- trace-set counts and identifiers;
- duplicate label keys;
- training-only many-to-one MRR joins; and
- explicit empty traces.

The training join contains 1,981 wafer/stage label keys with zero missing and
zero orphan training labels. This validates raw loading and join cardinality,
not model readiness.

## Validated R2 time and process-mode semantics

The corrected pipeline preserves file/source row order and retains
`SOURCE_ROW_INDEX`. A new continuity segment starts at a trace boundary, a
non-positive timestamp increment, or an increment above the preregistered
10 s threshold. Five observed negative increments (three training and two
validation), 2,907 zero increments, and 2,855 long gaps are retained as audit
evidence rather than sorted away. No time weight crosses these boundaries.

For a valid row within one continuity segment, centered time support is

\[
w_i = \tfrac{1}{2}\Delta t_{i-1}^{+}
    + \tfrac{1}{2}\Delta t_{i+1}^{+},
\]

where only adjacent positive increments inside the same segment contribute.
This weights summaries by supported duration rather than row density.

Input signals classify rows into
`PREPARE_PROXY`, `ACTIVE_POLISH_PROXY`,
`TRANSITION_WITHIN_POLISH_PROXY`, `ENDING_OR_CLEANING_PROXY`, or
`UNRESOLVED_PROXY`. These are process-mode proxies, not measured phase labels.
The active candidate requires nonzero pressure, slurry, wafer-or-stage
rotation, and head rotation. Complete-trace phase summaries are explicitly
offline-only and are not eligible as streaming features.

The deterministic processed bundle contains 1,981 training, 424 test, and 424
validation wafer/stage rows. Each feature table has 405 predictor columns; the
target is stored separately and absolute timestamps are metadata, not
predictors. All three feature/label key audits have zero missing and zero
orphan keys. Checksums and contracts are in
`data/processed/phm_2016_cmp/feature_manifest.yaml`, and the detailed evidence
is in `reports/data/phm_semantic_audit.json`.

## Training-label anomaly policy

Four training labels are extreme relative to every other split:

| Wafer | Stage | Original | Hypothetical original / 60 |
|---|---|---:|---:|
| 2058207580 | A | 4326.15405 | 72.102568 |
| 1834206730 | A | 4202.11245 | 70.035207 |
| 1834206944 | A | 4182.41655 | 69.706942 |
| 1834206972 | A | 4129.49400 | 68.824900 |

All other training labels are no greater than approximately 163, and official
test/validation maxima are below 164. The raw labels must never be silently
changed. Before model fitting, preregister and report:

1. primary treatment retaining all original labels;
2. sensitivity excluding the four records; and
3. explicitly hypothetical sensitivity dividing only those four by 60.

No treatment may be chosen using official test or validation results.

## Split and fit-scope policy

- Official training data are the only source for model fitting and tuning.
- Official test answers are an offline holdout.
- Official validation answers are the final public holdout.
- Inner development folds group by wafer.
- Whole-wafer grouped and chronological temporal-block development splits are
  required stress tests.
- Stage-separated and mixed-stage results are reported separately.
- Phase thresholds, imputers, scalers, feature selection, physics coefficients,
  and model hyperparameters are fitted on training groups only.
- Absolute timestamp is not a default predictive feature.

A physical-machine holdout is impossible in this archive because the only
observed machine ID is `2`. `MACHINE_DATA` takes values 1--6 but changes within
1,979 of 1,981 training wafer/stage groups and every test and validation group;
it is therefore a descriptive input, not a machine identity or stable regime.
No machine-generalization claim will be made from this dataset.

The authoritative R2 decision and validation evidence are in
[`r2_phm_semantics.md`](../orchestration/decisions/r2_phm_semantics.md) and
[`r2_phm_semantics_validation.md`](../orchestration/reports/r2_phm_semantics_validation.md).
