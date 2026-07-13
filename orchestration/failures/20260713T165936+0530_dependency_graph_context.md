# Failure report

## Task

Update the work-package dependency graph after separating completed Phase 3 scientific contracts from Phase 4 controller/safety implementation tasks.

## Failed command

An `apply_patch` operation attempted to update the WP15/WP16 nodes, Phase 3 gate, critical path, and stale WP09 status paragraph in `orchestration/dependency_graph.md`.

## Error

```text
apply_patch verification failed: Failed to find expected lines in
/home/akki/cmp_modelling/orchestration/dependency_graph.md
```

The failing context expected the sentence `A physical-machine holdout is not` to begin on its own line. The repository currently wraps `A physical-machine holdout is not` after `1,981/311/275 roles support independent-wafer evaluation.` on the same line.

## Files changed before failure

The dependency-graph patch was atomic and made no partial change. Earlier authorized Phase 3 work remains uncommitted in controller/safety decisions and configs, strict contract code/tests, deterministic validation artifacts, the joint validation report, and governance updates to assumptions, claims, risks, and the task manifest.

## Read-only diagnosis

The failure is a patch-context transport mismatch, not a semantic conflict. A current-context inspection also found that the data-dependency bullet for the simulator-to-final-action path appears twice consecutively in the existing graph. The recovery should remove that duplicate while applying the planned DAG update.

The repository contains no staged or committed partial dependency-graph change from the failed operation.

## Likely causes

1. The patch was prepared from visually wrapped output rather than the exact source-line boundary.
2. The graph contains a pre-existing duplicate bullet that was outside the original patch context.

## Recovery options

1. Reapply the update as small, independently context-verified patches: Mermaid nodes first, then the Phase 3 gate, critical path, WP09 paragraph, and duplicate bullet removal. Run `git diff --check` after each patch.
2. Leave the graph stale and rely only on the task manifest. This would make the Phase 3 checkpoint internally inconsistent.
3. Replace the whole dependency-graph file. This is unnecessarily broad and risks overwriting unrelated wording.

## Recommended option

Option 1. It preserves all existing content outside the reviewed sections and follows the repository's formatting preflight rule.

## User decision required

Authorize Option 1. No further mutation or Phase 3 closure work will proceed until the recovery is approved.
