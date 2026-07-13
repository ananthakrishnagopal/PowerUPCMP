# Failure report

## Task

Open the frozen WP13 synthetic attribution holdout exactly once after replaying
the committed TRAIN/CALIBRATION payload and preflight checks.

## Failed command

```text
MPLCONFIGDIR=/tmp/semifab-poc-matplotlib \
  conda run -n devkki python scripts/validate_wp13_attribution.py \
  --run-one-shot --authorize-holdout-open
```

## Error

The guard exited with code 2 before TEST construction:

```text
WP13 guard refused execution: committed WP13 preholdout payload does not replay exactly
```

## Files changed before failure

None. Git HEAD remained
`0f72627c321c25af2752bf30b5ac257777dd7d95`, and the worktree was clean.
The guard stopped before writing
`reports/attribution/wp13_holdout_opening.json`; neither that marker nor
`reports/attribution/wp13_validation.json` exists. TEST, compound, robustness,
and pre-event scenarios were not constructed.

## Read-only diagnosis

The current attribution configuration SHA-256 exactly matches the committed
manifest value:

```text
16ee2fb2c1ecc43010148568d5fa32b2aa08d9d75d6de8725a5a1ffd87abe9c8
```

A read-only deterministic rebuild showed that the frozen and replayed complete
preparation payloads have the same recorded deterministic SHA-256:

```text
e8b47b67a37972addedd5dc230005979bcb3d20f3bea76aa1ec07a5d186d3ab9
```

Canonical JSON hashes also match for every field that raw Python equality
reported as unequal. The unequal fields are those containing tuples in the
in-memory rebuild and lists after loading the committed JSON manifest:

- `feature_names`;
- `online_window_fields`;
- the nested TRAIN scenario manifest; and
- the nested CALIBRATION scenario manifest.

For example, `feature_names` has identical canonical content and SHA-256 on
both sides, but JSON loading converts the committed tuple to a list. The guard
compared `replayed_payload != frozen_manifest["preparation_payload"]` directly,
so equivalent JSON content failed because Python list and tuple types are not
equal.

This is a serialization-normalization defect in the preflight guard, not a
scientific-data, configuration, seed, feature, split, or model drift.

## Likely causes

1. `build_preholdout_payload` retains immutable tuples in memory.
2. `write_json_atomic` serializes those tuples as JSON arrays.
3. `json.loads` restores every JSON array as a Python list.
4. The one-shot guard uses raw object equality instead of the already recorded
   canonical JSON digest.

## Recovery options

1. Recommended: change only the guard comparison to canonical JSON equality,
   add a regression test proving that a JSON round trip of the frozen payload
   passes while any value change fails, rerun focused/full tests, commit the
   corrective guard and failure report, then invoke the one-shot command again.
   The existing manifest, models, seeds, thresholds, and scientific policy stay
   frozen.
2. Normalize every tuple to a list inside the payload builder and regenerate
   the pre-holdout manifest and model-artifact record. This is scientifically
   equivalent but rewrites more frozen evidence than necessary.
3. Abandon WP13 held-out execution and retain only calibration evidence.

## Recommended option

Option 1. Canonical comparison is already the declared deterministic contract,
preserves all frozen scientific choices and artifacts, and fixes only the
incorrect representation-sensitive guard. Because no opening marker exists,
the one-shot authorization has not been consumed.

## User decision required

Authorize option 1 before any code change, test run, commit, or second one-shot
invocation.

## Decision received and bounded recovery

The user authorized option 1 by replying `resume`. The guard now compares the
canonical JSON-domain digests rather than representation-sensitive Python
container types. A regression test verifies that a tuple/list JSON round trip
passes and that changing one nested seed value fails. No manifest, model,
configuration, seed, threshold, or scientific policy changed.

After the correction, 23/23 focused tests and 211/211 complete repository tests
pass with warnings treated as errors. The opening marker and TEST result remain
absent pending a clean committed recovery checkpoint.
