# Failure report

## Task

Integrate completed WP09 results into the living Markdown research paper and results ledger.

## Failed command

An `apply_patch` operation attempted three independent edits in `docs/running_paper.md`, including removal of an assumed duplicated `Deterministic scenario engine` ledger row.

## Error

```text
apply_patch verification failed: Failed to find expected lines in
/home/akki/cmp_modelling/docs/running_paper.md:
| Deterministic scenario engine | ... |
| Deterministic scenario engine | ... |
```

The patch was atomic and made no file change.

## Files changed before failure

The following authorized work was completed and remains preserved:

- `reports/virtual_metrology/wp09_holdout_opening.json`
- `reports/virtual_metrology/wp09_validation.json`
- `reports/virtual_metrology/wp09_predictions.csv`
- six checked model artifacts and checksum sidecars under `reports/virtual_metrology/models/`
- three reviewed figures and their manifest under `reports/virtual_metrology/figures/`
- `scripts/generate_wp09_figures.py`
- `orchestration/reports/wp09_virtual_metrology_validation.md`
- WP09 result integration already applied to `paper/main.tex`
- WP09 abstract, status, and Section 6.1 integration already applied to `docs/running_paper.md`

This failure report is the only mutation after the failed patch.

## Read-only diagnosis

The current ledger contains exactly one `Deterministic scenario engine` row. The apparent duplicate came from a prior inspection whose inclusive output ranges overlapped at their shared boundary, causing the same line to be displayed twice. The failed patch incorrectly treated that display artifact as repository content.

`git diff --check` remains clean. The completed one-shot result is unchanged: validation JSON SHA-256 `52d25cf92c4eea24158e0821cd7b7dd60fabe2ec04967443e3417397313bd10c`, deterministic payload SHA-256 `84d4823b7972e289a67f62a4bf1ea348d007ddd0f6285b4dd32d36178da320db`, and prediction CSV SHA-256 `ea3e9e813e8343862340fb42bfc31c784e0f5df9bd15f5b0f707624bb4679826`.

## Likely causes

1. An overlapping read-range display was mistaken for duplicated file content.
2. Three logically independent documentation edits were combined into one patch, so an invalid optional hunk prevented two valid edits from applying.

## Recovery options

1. Resume with three small patches based only on freshly inspected exact contexts: update the evaluation paragraph, replace the pending WP09 ledger row, and leave the single scenario row untouched.
2. Pause manuscript integration and retain the standalone WP09 validation report only.

## Recommended option

Option 1. It preserves the completed evidence, fixes only verified stale text, and directly applies the previously recorded small-patch prevention rule.

## User decision required

Authorize recovery option 1 before any further mutation or manuscript build.
