# Failure report

## Task

Create the journal-neutral two-column LaTeX manuscript source and correct one Markdown hard-break marker in the manuscript evidence map.

## Failed command

One large `apply_patch` operation attempted to add `paper/main.tex` and update `paper/evidence_map.md`.

## Error

```text
apply_patch verification failed: invalid hunk at line 50,
'ultrapure-water (UPW) pressure/flow/thermal response, a declared CMP boundary,'
is not a valid hunk header. Valid hunk headers: '*** Add File: {path}',
'*** Delete File: {path}', '*** Update File: {path}'
```

## Files changed before failure

Before the rejected operation, the manuscript task had been transitioned to `IN_PROGRESS`, and these files were successfully created:

- `paper/Makefile`
- `paper/README.md`
- `paper/evidence_map.md`
- `paper/references.bib`
- updates to `orchestration/project_status.md` and `orchestration/task_manifest.yaml`

The failed operation was rejected before application. It did not create `paper/main.tex` and did not modify `paper/evidence_map.md`.

## Read-only diagnosis

- `paper/main.tex` does not exist.
- The four previously created paper files are present and readable.
- The working tree contains only the expected manuscript-task changes.
- In an `Add File` patch, every content line must start with `+`. One wrapped abstract line in the large patch lacked that prefix, so the parser treated it as an invalid hunk header.
- There is no evidence of filesystem, LaTeX, scientific-content, or repository corruption.

## Likely causes

1. A single missing patch-line prefix in a long manually composed file-addition hunk.
2. The size of the monolithic patch made visual verification of every prefix unnecessarily fragile.

## Recovery options

1. Add `paper/main.tex` through several smaller `apply_patch` operations: create a bounded initial section, then append independently reviewed sections using explicit update hunks. Correct the evidence-map break in a separate small patch.
2. Retry the same monolithic patch after repairing the missing prefix; this retains the original fragility.
3. Shorten the manuscript substantially; this would not meet the requested thorough journal-paper draft.

## Recommended option

Option 1. Smaller atomic patches reduce syntax risk, make mathematical/scientific review easier, and still comply with the repository rule that all manual file edits use `apply_patch`.

## User decision required

Authorize Option 1 and continuation, or choose another recovery option.

## Resolution

The user authorized Option 1. The manuscript source is being created through bounded `apply_patch` sections with an explicit insertion marker, and the evidence-map hard break was corrected separately.
