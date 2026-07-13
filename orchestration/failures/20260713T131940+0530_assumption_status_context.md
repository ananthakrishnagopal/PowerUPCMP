# Failure report

## Task

Reconcile the assumptions register with completed WP09 evidence.

## Failed command

An `apply_patch` operation updated the register version, A-002 evidence, A-003
evidence, and attempted to change A-022 from `REQUIRES_VALIDATION` to
`ACCEPTED_FOR_POC`.

## Error

The status-only hunk matched the earlier A-005 status line instead of A-022.
A-005 was therefore changed to `ACCEPTED_FOR_POC`, while A-022 remained
`REQUIRES_VALIDATION`. The surrounding evidence-text edits applied as intended.

## Files changed before failure

- `orchestration/assumptions.yaml`: intended version and evidence-text changes
  plus the unintended A-005 status change.
- Earlier authorized WP09 documentation and governance edits remain present and
  pass `git diff --check`.

## Read-only diagnosis

The patch used an under-contextualized one-line hunk containing only
`status: REQUIRES_VALIDATION`. That value occurs in multiple assumption
records, so patch matching selected the first compatible occurrence. Fresh
inspection confirms A-005 is now incorrectly `ACCEPTED_FOR_POC` and A-022 is
still `REQUIRES_VALIDATION`.

## Likely causes

1. The status hunk did not include the assumption ID or statement.
2. Multiple records share the same status value.
3. A successful patch application was not sufficient evidence that the intended
   YAML record changed; the immediate record-level verification caught it.

## Recovery options

1. Recommended: apply two separate, full-record-context patches. Restore A-005
   to `REQUIRES_VALIDATION`, then change A-022 to `ACCEPTED_FOR_POC`. Verify
   both records and parse the YAML before any other edit.
2. Restore A-005 only and leave A-022 unresolved, retaining its updated WP09
   validation text.
3. Revert every assumptions-register change from this WP09 closeout.

## Recommended option

Option 1. A-005 still requires integrated closed-loop validation, while the
specific A-022 phase-separation assumption now has its planned R2/WP09 evidence.

## User decision required

Authorize option 1 before any further mutation.
