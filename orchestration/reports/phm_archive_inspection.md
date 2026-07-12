# PHM archive inspection

Inspection date: 2026-07-10  
Initial inspection mode: read-only. Follow-up extraction was performed only after explicit user authorization and successful full validation.

## Candidate archive

- Local path: `PHM-Data-Challenge-master.zip`
- Archive type: ZIP
- Compressed size: `17,399,074` bytes
- Uncompressed size reported by ZIP central directory: `203,033,011` bytes
- ZIP entries: 660 including directories; 657 files
- SHA-256: `976b23102b576ed610db8f89293de333820391c581d88bcbdb6364da212a1eb9`
- Integrity: `unzip -t` passed for all entries.
- User supplied the archive in the repository root; no network transfer was performed by this project.

## CMP contents found

The archive contains the original-looking PHM 2016 CMP data tree:

```text
data/2016 PHM Data Challenge/
├── 2016 PHM DATA CHALLENGE CMP DATA SET/
│   ├── CMP-data/test/CMP-test-000.csv … CMP-test-184.csv
│   ├── CMP-data/training/CMP-training-000.csv … CMP-training-184.csv
│   ├── CMP-test-removalrate.csv
│   └── CMP-training-removalrate.csv
└── 2016 PHM DATA CHALLENGE CMP VALIDATION DATA SET/
    ├── validation/CMP-validation-000.csv … CMP-validation-184.csv
    └── CMP-validation-removalrate.csv
```

Observed counts:

- 185 test time-series CSVs.
- 185 training time-series CSVs.
- 185 validation time-series CSVs.
- Training removal-rate sample columns: `WAFER_ID, STAGE, AVG_REMOVAL_RATE`.
- Time-series sample columns: 25 fields including machine/wafer identifiers, timestamp, stage, pressure, flow, rotation, usage, and status variables.

The archive also includes `PHM16TestValidationAnswers` containing test and validation answer tables. These must be quarantined from training and online features to prevent target leakage. It includes additional derived two-mode/three-mode experiments, processed NumPy arrays, model code, plots, bytecode, and other research outputs; those are not raw PHM measurements and must not be ingested as primary data.

## Licence and provenance finding

The bundled top-level `LICENSE` is an MIT licence with copyright `gdutthu (2020)`, which appears to cover the surrounding repository/code. It does not explicitly grant or identify the licence of the embedded PHM 2016 dataset. The original PHM Society page identifies the challenge and file patterns, but its current ZIP link is unavailable. Therefore the dataset remains:

```text
local candidate: PRESENT
archive integrity: VERIFIED
schema shape: PLAUSIBLE, not yet source-validated
dataset licence: UNVERIFIED
authoritative source: UNVERIFIED
public-data validation status: BLOCKED
```

## Follow-up extraction evidence

- Extracted destination: `data/raw/phm_2016_cmp/original/`.
- Selected members: 558 (185 test, 185 training, 185 validation, and three removal-rate tables).
- Empty traces retained: 58 header-only time-series files, marked `empty_trace: true`.
- Answer tables and derived experiments: excluded.
- Per-member byte sizes and SHA-256 values: recorded in `data/raw/phm_2016_cmp/extraction_manifest.yaml` and independently rechecked after extraction.
- Extraction manifest archive SHA-256 matches `976b23102b576ed610db8f89293de333820391c581d88bcbdb6364da212a1eb9`.

## Required handling decision

Before any public-data publication or redistribution claim, retain the explicit user authorization and dataset-licence caveat. Acceptable provenance evidence is either:

1. an authoritative source and licence statement for this exact archive; or
2. explicit user confirmation that this locally supplied archive may be used for the PoC despite the dataset licence not being separately stated.

The archive is now extracted under that authorization. The next implementation step is the PHM loader and leakage audit; derived experiments and model outputs remain excluded.
