# Failure report

## Task

Visually inspect representative pages of the successfully generated interim WP10 presentation before committing the deliverable.

## Failed command

The display-only JavaScript orchestration helper loaded seven PNG page previews and attempted to derive page labels with:

```javascript
paths[i].match(/_(\\d+)\\.png$/)[1]
```

## Error

```text
Script failed
TypeError: Cannot read properties of null (reading '1')
    at exec_main.mjs:12:48
```

The presentation build itself completed successfully before this failure. The PDF is a valid 17-page widescreen document, and the PPTX archive passed `unzip -t` with no errors.

## Files changed before failure

Repository changes made before the failed preview helper:

- `Makefile`
- `presentation/README.md`
- `presentation/wp10_demo.md`
- `scripts/generate_communication_figures.py`
- `reports/figures/communication_figure_manifest.json`
- six generated PNG figures under `reports/figures/`
- `reports/presentation/wp10_demo.pdf`
- `reports/presentation/wp10_demo.pptx`

The failed helper made no repository changes. Seven diagnostic page rasters exist only under `/tmp/`.

## Read-only diagnosis

- All seven requested PNG previews exist and are readable-sized files (20--68 KiB).
- `reports/presentation/wp10_demo.pdf` exists (947 KiB); `pdfinfo` reports 17 pages and no encryption.
- `reports/presentation/wp10_demo.pptx` exists (949 KiB); its ZIP container and members passed integrity testing.
- The repository has only the expected uncommitted presentation-related paths plus this failure report.
- The regular-expression literal was over-escaped in the JavaScript helper. It searched for literal backslashes rather than the numeric page suffix, so `match(...)` returned `null`; indexing `[1]` caused the exception.

## Likely causes

1. **Primary:** accidental double escaping in a raw JavaScript regular-expression literal.
2. No evidence indicates corrupt images, a failed renderer, or a presentation-content failure.

## Recovery options

1. Re-run the read-only visual inspection with explicit static page labels and no regular expression.
2. Inspect each PNG in a separate read-only image-view call.
3. Skip visual inspection and rely on the completed structural and text checks; this is less rigorous.

## Recommended option

Option 1. It is the smallest, read-only recovery and removes the failed parsing operation entirely. If visual inspection confirms layout quality, continue with claim checks and the presentation commit.

## User decision required

Authorize the recommended read-only preview retry and continuation of the presentation/manuscript workflow, or choose another recovery option.

## Resolution

Authorized by the user. The retry used explicit static page labels and succeeded. Visual review found two layout-density issues, which were corrected at source and revalidated; the canonical 17-page PDF now passes the representative-page visual review.
