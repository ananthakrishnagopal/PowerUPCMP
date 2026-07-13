# Failure report

## Task

Integrate the completed WP13 root-cause-attribution methods, held-out results,
figures, limitations, and provenance into `paper/main.tex`.

## Failed command

An `apply_patch` update containing multiple LaTeX manuscript hunks.

## Error

```text
apply_patch verification failed: Failed to find expected lines in
/home/akki/cmp_modelling/paper/main.tex:
\title{A Simulation-First Framework for Predictive Supervisory Control of CMP under Electrical and Ultrapure-Water Disturbances:\
Public Virtual Metrology, Physics, Coupling, and Synthetic Early Warning}
```

## Files changed before failure

- `orchestration/reports/wp13_attribution_validation.md` was created with the
  frozen method, TEST results, robustness, claim boundary, and hashes.
- `docs/modeling_notes.md` was updated with WP12 and WP13 equations and
  interpretation.
- `docs/running_paper.md` was updated with WP13 methods, results, limitations,
  and reproducibility evidence.
- The expected one-shot result artifacts remain untracked under
  `reports/attribution/`.
- `paper/main.tex` was not changed by the failed patch.

## Read-only diagnosis

`sed -n '14,36l' paper/main.tex` confirms the title line ends with two literal
LaTeX backslashes. The JavaScript string used to transport the patch rendered
the expected context with one literal backslash, so the exact-context check
correctly refused the hunk. `git diff -- paper/main.tex` is empty. This is a
patch-string escaping/context mismatch, not a LaTeX syntax, scientific model,
test, or result-artifact failure.

## Likely causes

1. The patch source did not double-escape both LaTeX backslashes through the
   JavaScript string layer.
2. The attempted patch combined several manuscript regions, making one title
   context mismatch reject the complete operation.

## Recovery options

1. Apply small manuscript patches one region at a time, avoiding the title's
   doubled-backslash line in the first hunk and using freshly inspected exact
   context for every subsequent hunk.
2. Leave the LaTeX/PDF at the WP09/WP12 evidence freeze and close only the
   Markdown/report portion of WP13.
3. Defer all WP13 closure, retaining the current uncommitted report and notes
   until the manuscript transport issue is resolved separately.

## Recommended option

Option 1. It is reversible, preserves all frozen scientific artifacts, keeps
the requested journal manuscript synchronized with the running paper, and
directly addresses the transport mismatch without changing code, models,
configuration, or TEST results.

## User decision required

Authorize option 1 before any further mutation or retry.
