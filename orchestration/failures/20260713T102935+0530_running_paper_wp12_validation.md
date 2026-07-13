# Failure report

## Task

Validate the WP12 integration in `docs/running_paper.md`.

## Failed command

```text
git diff --check
```

## Error

```text
docs/running_paper.md:4: trailing whitespace.
```

## Files changed before failure

The running-paper status, abstract, WP12 mathematical methods/results,
evaluation status, result ledger, limitations, and reproducibility record were
updated. No source code, tests, datasets, or model artifacts changed during
this documentation step.

## Read-only diagnosis

The edited status line retained two spaces intended as a Markdown hard break,
which `git diff --check` rejects. Inspection also found that intended inline
math delimiters around `R_k`, `R_k^{ref}`, `t_d`, `H`, `t_e`, and the conformal
rank were consumed while constructing the patch string, leaving ordinary
parentheses. Display equations and the existing `\(\tilde p\)` delimiter are
intact. The quantitative values agree with the frozen WP12 report.

## Likely causes

The existing document uses trailing-space hard breaks, while the repository
diff gate rejects newly introduced trailing whitespace. JavaScript string
escaping also removed several newly intended `\(` and `\)` delimiters.

## Recovery options

1. Replace the status hard break with `<br>` and replace the affected inline
   expressions with dollar-delimited Markdown math; then rerun
   `git diff --check` and visually inspect the edited section.
2. Keep the mathematics as plain text and only remove the trailing whitespace.
3. Revert the full running-paper integration and rely only on the formal WP12
   report.

## Recommended option

Option 1. It fixes both the objective formatting failure and the visible math
semantics without altering any scientific content.

## User decision required

Resolved. The user authorized option 1. The status line now uses `<br>`, the
affected expressions use explicit dollar-delimited Markdown math, and
`git diff --check` passes.
