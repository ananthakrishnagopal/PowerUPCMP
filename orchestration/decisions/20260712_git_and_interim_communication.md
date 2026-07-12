# Decision: Git baseline and interim communication artifacts

Date: 2026-07-12  
Status: AUTHORIZED FOR IMPLEMENTATION  
Scope: repository version control, interim WP10 presentation, and living journal manuscript

## Decision

The validated WP10 repository state will become the first Git baseline before
new presentation or manuscript source is added. The unborn branch will be
renamed from `master` to `main`. Commits will separate the scientific/software
baseline, interim demonstration, and journal manuscript so later review can
identify communication-only changes.

## Tracking boundary

Git will track source, tests, configurations, orchestration records, dataset
manifests, documentation, and reviewed synthetic result artifacts. It will not
track:

- pre-existing user-local `.codex/` or `.agents/` content;
- the user-supplied PHM ZIP or extracted raw members;
- PHM-derived CSV tables while the dataset licence remains unresolved;
- locally supplied paper PDFs;
- caches, environments, compiler intermediates, or transient artifacts.

The raw extraction manifest and processed feature manifest remain trackable
because they record provenance and reproducibility without redistributing the
underlying data tables.

## Interim presentation

The deck will be labelled **Interim scientific demonstration through WP10**.
It may show validated synthetic WP08/WP10 results, structural nulls,
sensitivity, limitations, and the remaining roadmap. It may not represent
early warning, attribution, predictive control, independent safety filtering,
defect prevention, yield improvement, equipment protection, or production
readiness as completed.

One canonical Pandoc Markdown source will generate both PDF and editable PPTX
outputs. Figures will be generated reproducibly from reviewed JSON/CSV
artifacts rather than manually edited.

## Living journal manuscript

A journal-neutral, two-column LaTeX manuscript will be created and compiled to
PDF. Completed methods and results will be written normally; missing Phase 3/4
results will be explicitly marked pending and never inferred. The detailed
Markdown running paper remains the evidence ledger, while the LaTeX manuscript
is the publication-oriented narrative. A target-journal template is deferred
until a journal is selected.

## Scientific status impact

These are communication and reproducibility changes. T-WP10 remains COMPLETE,
T-WP12 remains PLANNED behind its scientific-definition blocker, and no
project claim changes merely because a slide or manuscript renders it.
