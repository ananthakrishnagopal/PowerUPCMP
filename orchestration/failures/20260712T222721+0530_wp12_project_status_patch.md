# Failure report

## Task

Update `orchestration/project_status.md` after final WP12 validation.

## Failed command

```text
apply_patch (multi-hunk project-status update)
```

## Error

```text
apply_patch verification failed: Failed to find expected lines in
orchestration/project_status.md:
T-WP10 now also passes its declared-topology implementation,
null-control, full-chain, local/global/mismatch sensitivity, historical
reproduction, and validation gates.
```

## Files changed before failure

WP12 source, tests, generated evidence, the formal validation report, claims
matrix, assumptions register, risk register, and task manifest had already been
updated. The failed patch changed no `project_status.md` content.

## Read-only diagnosis

The semantic text exists, but the repository wraps the preceding sentence as
`validation gate. T-WP10 ...` on the same line. The patch expected the T-WP10
sentence to begin at a new context line. The patch engine rejected all hunks
before applying any of them. The pre-existing uncommitted 13:15-to-14:19 status
edit remains untouched.

## Likely causes

The large multi-hunk patch used paragraph context copied without preserving the
exact current line wrap.

## Recovery options

1. Apply small independent patches using exact inspected context, then rerun
   governance link/YAML validation.
2. Leave the stale status file while retaining the completed manifest/report.
3. Replace the entire status document, risking loss of useful historical detail.

## Recommended option

Option 1. It preserves the existing history and minimizes conflict with user
work.

## User decision required

Resolved. The user authorized option 1, and the status document was updated
with small exact-context patches. `git diff --check` passed after recovery;
final governance validation remains part of the WP12 documentation checkpoint.
