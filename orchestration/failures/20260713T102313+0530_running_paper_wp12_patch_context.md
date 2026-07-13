# Failure report

## Task

Integrate the validated WP12 result into `docs/running_paper.md`.

## Failed command

```text
apply_patch (status/date and abstract update)
```

## Error

```text
apply_patch verification failed: Failed to find expected lines in
docs/running_paper.md:
Structural, local, global, and mismatch analyses
show that this effect is contingent on synthetic topology and coefficients.
No predictive-control efficacy,
real-fab, defect, yield, or production-control claim is made.
```

## Files changed before failure

The authorized recovery had already updated `orchestration/project_status.md`
and resolved its prior failure report. This running-paper patch was atomic and
changed no `docs/running_paper.md` content.

## Read-only diagnosis

The intended abstract text exists, but the first sentence begins on the same
line as the preceding sentence: `identical no-connection run. Structural, ...`.
The patch expected `Structural, ...` to start a new context line, so verification
rejected the complete patch. `git diff --check` still passes.

## Likely causes

Patch context was copied from rendered prose rather than preserving the exact
Markdown line boundary.

## Recovery options

1. Apply two small exact-context patches: first the status/date lines, then the
   exact abstract tail beginning with `identical no-connection run.`.
2. Leave the running paper at its stale WP10 evidence freeze while retaining
   the completed formal WP12 report.
3. Replace the full abstract, which is less conservative and risks losing
   reviewed wording.

## Recommended option

Option 1. It is bounded, preserves reviewed prose, and incorporates WP12 without
changing scientific claims elsewhere.

## User decision required

Resolved. The user authorized option 1. Both small exact-context patches
applied successfully; the running-paper status/date and abstract now reflect
the bounded WP12 result.
