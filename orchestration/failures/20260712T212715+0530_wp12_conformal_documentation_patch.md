# Failure report

## Task

Record the WP12 revision-1.2 independent-conformal amendment, its mathematics,
the revision-1.1 audit snapshot, and a deterministic probability-payload hash.

## Failed command

```text
apply_patch (multi-file documentation and report-metadata patch)
```

## Error

```text
apply_patch verification failed: Failed to find expected lines in
orchestration/decisions/wp12_early_warning_target.md:
Coverage is a held-out simulator result,
not a real-world guarantee.
```

## Files changed before failure

Earlier successful revision-1.2 preparation had changed:

- `configs/models/early_warning.yaml`
- `src/semifab_poc/models/early_warning.py`
- `scripts/validate_wp12_early_warning.py`
- `tests/unit/test_early_warning.py`
- `tests/unit/test_wp12_scenario_ensemble.py`

The failed multi-file patch changed none of its target files. In particular,
the probability-hash report field, the conformal-separation decision, and the
revision-1.1 method-audit report were not created.

## Read-only diagnosis

The intended context exists semantically, but the patch expected a line break
between `result,` and `not a real-world guarantee.` The repository instead has
`Coverage is a held-out simulator result,` on the preceding wrapped line. The
patch engine verified all contexts before applying any hunk and rejected the
entire patch atomically. Read-only checks confirmed both proposed new files are
absent and the script has no partial probability-hash change.

## Likely causes

The patch was composed against an inaccurately remembered Markdown wrap point
rather than the exact current file context.

## Recovery options

1. Apply separate small patches using the exact inspected context, then run
   static/config tests before any simulation.
2. Omit the amendment documentation and continue with code only.
3. Revert all revision-1.2 preparation and retain the statistically deficient
   revision-1.1 uncertainty result.

## Recommended option

Option 1. It preserves the transparent audit trail and minimizes patch scope.

## User decision required

Resolved. The user authorized option 1. The report-metadata change, primary
decision amendment, mathematical conformal-separation decision, and
revision-1.1 method-audit record were applied as four exact-context patches.
The complete focused WP12 suite then passed with warnings treated as errors:

```text
13 passed in 8.72s
```

No revision-1.2 scientific result had been generated at resolution time.
