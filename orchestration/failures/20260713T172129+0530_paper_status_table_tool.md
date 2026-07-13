# Failure report

## Task

Update the LaTeX manuscript evidence-status table from the WP13 evidence freeze
to the Phase 3 scientific freeze.

## Failed command

A `functions.exec` JavaScript wrapper intended to call `apply_patch` on
`paper/main.tex`.

## Error

The wrapper raised `TypeError: String.raw(...) is not a function` before the
repository patch tool was invoked.

## Files changed before failure

The two explicitly authorized WP17--WP18 manuscript recovery patches succeeded
and passed `git diff --check`. Earlier Phase 3 contracts, tests, reports,
governance, modelling notes, and manuscript sections remain in the worktree.
This failed wrapper changed no repository file, and the existing diff remains
whitespace-clean.

## Read-only diagnosis

The target caption and row remain unchanged and are present at the inspected
lines. The error arose while evaluating the JavaScript string-construction
expression, before `tools.apply_patch` was called. It is not a LaTeX syntax,
repository-content, model, numerical, data, or permission failure.

## Likely causes

- An unsafe tagged-template construction in the orchestration wrapper was
  parsed differently than intended around LaTeX backslashes.
- The repository patch itself was never evaluated, so no patch-context issue
  is implicated.

## Recovery options

1. Reissue the small exact-context patch using a normally escaped JavaScript
   string, then run `git diff --check`.
2. Leave the evidence-status table stale and continue with other Phase 3
   closure work.
3. Defer all remaining LaTeX synchronization to Phase 4.

## Recommended option

Option 1. It changes only manuscript wording, avoids the failed wrapper form,
and keeps the evidence-status table aligned with authoritative governance.

## User decision required

Authorize Option 1 before any further mutating action.
