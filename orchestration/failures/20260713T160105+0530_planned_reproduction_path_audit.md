# Failure report

## Task

Audit WP13 reproduction instructions and stale documentation paths before the
closure commit.

## Failed command

```text
rg -n -i 'wp13|attribution' docs/reproduction.md Makefile paper/README.md
```

## Error

```text
rg: docs/reproduction.md: No such file or directory (os error 2)
```

## Files changed before failure

- WP13 implementation, TEST artifacts, reports, claims, risks, manifest, status,
  running paper, journal manuscript, evidence map, and user-facing README are
  complete within the frozen synthetic boundary.
- The final post-documentation suite passes 211/211 in 60.24 s with warnings
  treated as errors.
- Governance passes for 17 YAML files, 29 acyclic tasks, 25 assumptions, and
  134 valid links across 125 Markdown files with none missing.
- The reviewed 17-page PDF and its clean final LaTeX log are preserved.

## Read-only diagnosis

`docs/reproduction.md` is listed in `docs/README.md` and as a T-WP20 output, but
T-WP20 is not implemented. The same documentation map also lists the absent
planned files `docs/assumptions_and_limitations.md` and
`docs/real_fab_data_contract.md`, followed by a general statement that planned
documents are created only with their work packages. Thus the failed command
incorrectly assumed a planned WP20 output already existed. Current reproduction
commands live in the root README, Makefiles, validation drivers, and manuscript
records. This does not invalidate WP13 tests or results.

## Likely causes

1. The audit command treated a planned task-manifest output as a current file.
2. The documentation map does not label each absent entry inline as planned,
   making the phase status less obvious.

## Recovery options

1. Keep `docs/reproduction.md` scoped to WP20, label the three absent map
   entries explicitly as planned, and audit the existing WP13 commands instead.
2. Implement `docs/reproduction.md` now, partially advancing WP20 beyond the
   current WP13 closure scope.
3. Leave the map unchanged and omit the failed path from the WP13 audit.

## Recommended option

Option 1. It preserves phase scope, removes ambiguity for readers, and avoids
creating a nominal final reproduction guide before WP15--WP18 exist.

## User decision required

Authorize option 1 before any further mutation or retry.
