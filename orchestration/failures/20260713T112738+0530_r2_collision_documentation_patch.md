# Failure report

## Task

Propagate the validated R2.1 whole-wafer precedence correction into dataset,
modelling, running-paper, LaTeX-manuscript, and evidence-map text.

## Failed command

An `apply_patch` operation targeting five documentation/manuscript files.

## Error

```text
apply_patch verification failed: Failed to find expected lines in
/home/akki/cmp_modelling/docs/running_paper.md
```

The expected paragraph used the wording “has one row per wafer/stage record,
comprising”; the current file instead says “The processed bundle has” inside a
longer paragraph.

## Files changed before failure

The authorized R2.1 implementation and governance changes already present in
the worktree include:

- `src/semifab_poc/data/{splits.py,phm_semantics.py,build_features.py,__init__.py}`;
- `tests/unit/test_splits.py` and `tests/integration/test_phm_pipeline.py`;
- `reports/data/phm_semantic_audit.json` and
  `data/processed/phm_2016_cmp/feature_manifest.yaml`;
- `configs/data/phm_2016_cmp.yaml`;
- the R2/R2.1 decision and validation records; and
- assumptions, claims, data-source, dependency, implementation, charter, risk,
  and task-manifest governance files.

The failed multi-file patch was rejected during context verification. A
read-only `git diff` confirms it made no partial changes to `docs/datasets.md`,
`docs/modeling_notes.md`, `docs/running_paper.md`, `paper/main.tex`, or
`paper/evidence_map.md`. This failure report is the only post-failure mutation.

## Read-only diagnosis

`rg -n -C 5 '1,981 training|processed bundle' docs/running_paper.md` located the
actual paragraph at lines 95--100. Its substantive content matches the intended
patch target; only the surrounding wording differs.

## Likely causes

The patch used a remembered paraphrase from an earlier view instead of the
file's exact current context.

## Recovery options

1. Apply five small file-specific patches using the exact current paragraphs,
   inspect their diffs, and continue the R2.1 manuscript/governance update.
2. Skip the running-paper/manuscript correction, leaving misleading
   whole-wafer implications in user-facing documentation.
3. Revert the otherwise validated R2.1 implementation.

## Recommended option

Option 1. It preserves the validated correction and makes the public-facing
scientific boundary consistent with the generated audit evidence.

## User decision required

Authorize Option 1 before any further mutation.
