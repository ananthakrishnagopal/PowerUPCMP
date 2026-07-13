# Failure report

## Task

Add WP13 figure provenance and revise the figure evidence boundary in
`paper/evidence_map.md`.

## Failed command

A two-hunk `apply_patch` assembled from a JavaScript line array.

## Error

```text
apply_patch verification failed: invalid hunk at line 12,
Expected update hunk to start with a @@ context marker, got: 'NaN'
```

## Files changed before failure

- The complete WP13 LaTeX methods/results integration and remaining manuscript
  discussion, limitations, reproducibility, status-table, and conclusion edits
  are present in `paper/main.tex`.
- The evidence-map freeze, claim boundary, and WP13 quantitative traceability
  rows were updated successfully.
- The attempted evidence-map figure-provenance hunk did not apply.
- `git diff --check` passes for all currently modified manuscript files.

## Read-only diagnosis

The inspected figure-provenance section is unchanged from the prior WP12
freeze. The combined patch was malformed during JavaScript array assembly and
was rejected by the patch parser before changing the file. The unexpected
`NaN` token indicates that one intended patch line was evaluated as a
JavaScript expression rather than preserved as text. This is a patch transport
problem, not a Markdown, scientific-result, test, or LaTeX-build failure.

## Likely causes

1. A line in the multi-hunk JavaScript array lost its string representation
   before joining.
2. Combining two hunks made the transport error harder to localize.

## Recovery options

1. Apply each evidence-map change as a single independent hunk using a
   verified literal string with no JavaScript-sensitive document syntax.
2. Leave figure provenance at the WP12 freeze while retaining the otherwise
   completed WP13 manuscript content.
3. Revert all WP13 manuscript changes and defer the journal-paper update.

## Recommended option

Option 1. The remaining change is small and documentary. One-hunk literal
patches directly avoid the observed multi-hunk assembly error.

## User decision required

Authorize option 1 before any further mutation or retry.
