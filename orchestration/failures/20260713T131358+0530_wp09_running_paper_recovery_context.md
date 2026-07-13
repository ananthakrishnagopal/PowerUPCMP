# Failure report

## Task

Resume the authorized WP09 running-paper recovery by replacing the evaluation
status paragraph in `docs/running_paper.md`.

## Failed command

An `apply_patch` operation attempted to replace the paragraph beginning with
`All future controller comparisons will use identical scenarios`.

## Error

`apply_patch verification failed: Failed to find expected lines`.

The attempted patch expected a longer metric list ending with grouped-bootstrap
language. The file instead contains a shorter paragraph ending with
`end-to-end runtime/controller latency`, followed by a separate results-summary
sentence.

## Files changed before failure

The failed patch was atomic and changed no files. Existing uncommitted WP09
results, manuscript edits, figures, models, and the earlier failure report were
left untouched.

## Read-only diagnosis

The initial recovery inspection used `rg -C 2`, which showed only the first
lines of the paragraph. The attempted replacement then relied on stale
continuation text from the compacted working summary rather than reading the
entire current paragraph. A fresh `sed -n '616,638p'` inspection confirms the
actual paragraph and shows that `git diff --check` remains clean.

## Likely causes

1. The recovery patch mixed fresh partial context with stale full-paragraph
   context.
2. The running paper had already evolved beyond the paragraph version retained
   in the working summary.

## Recovery options

1. Recommended: use the newly captured complete paragraph verbatim and apply
   one file-specific replacement patch; inspect and patch the results-ledger row
   only afterward in a separate operation.
2. Leave the running-paper status text unchanged and continue only with other
   WP09 documentation.
3. Revert all uncommitted WP09 documentation work after explicit user approval.

## Recommended option

Option 1. It preserves all completed work and removes the stale public-data
status with the smallest reversible edit.

## User decision required

Authorize option 1 before any further mutation.
