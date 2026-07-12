# Data layout and provenance

The repository contains a selectively extracted, user-supplied PHM 2016 CMP
archive under `raw/phm_2016_cmp`. The source ZIP was not downloaded by this
project. Its ZIP integrity and SHA-256, the 558 selected original members,
their extraction checksums, raw headers, and training-label joins are
verified. The dataset licence is not separately stated; use is limited to the
user's recorded authorization and redistribution is not authorized here.

This evidence does not yet support a public-data model-performance claim. Gate
R2 now provides source-order, continuity-segmented, centered-time-weighted,
process-mode-proxy features and separately stored targets. The original
process columns remain scaled with hidden factors, the original source does
not declare the MRR target unit, and four extreme training labels remain under
three preregistered sensitivity policies. See
`orchestration/reports/r2_phm_semantics_validation.md`.

Directories:

- `raw/` — immutable source/extracted bytes with recorded local authorization,
  selection rules, sizes, and checksums; never overwrite in place.
- `interim/` — validated intermediate tables with provenance links.
- `processed/` — derived model-ready data with split identity and transformation metadata.

The current deterministic processed bundle is
`processed/phm_2016_cmp/feature_manifest.yaml`. It contains target-free offline
feature tables for 1,981 training, 424 test, and 424 validation wafer/stage
groups, separate native-unit label tables, and the three preregistered training
label treatments. Complete-trace features are not streaming-eligible.

Every public raw file must have a manifest containing source owner,
authoritative URL, licence status, access/provision date, expected filename,
byte size, SHA-256, schema version, and local path. Use
`semifab_poc.data.provenance.verify_raw_file` before processing. The verifier
is read-only and does not download, mirror, or mutate files.

Canonical records distinguish measured public process output, simulated latent
state, observed sensor state, model output, process excursion, and quality-risk
proxy. Canonical schema 2.0.0 preserves public native/unknown source values
with `UNIT_UNRESOLVED` and null canonical fields; never coerce PHM signals into
simulator SI units without declared source units and supported conversion
provenance.
Grouped splits must be created before fitted transforms; random row splits
within a wafer, trace, or time block are forbidden. Official test/validation,
wafer-group, temporal-block, and stage reports are required before public
model claims. A physical-machine holdout is infeasible because the archive
contains only machine ID 2; `MACHINE_DATA` is not group-stable and must not be
used to imply machine or stable-regime generalization.

Some redistributed PHM time-series members may contain only the canonical header. These are retained as explicit missing traces (`empty_trace: true`) in the extraction manifest. They are not imputed, treated as measurements, or silently dropped. Removal-rate tables must contain data rows.
