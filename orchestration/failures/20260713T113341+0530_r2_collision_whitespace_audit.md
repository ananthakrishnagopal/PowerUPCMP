# Failure report

## Task

Validate the R2.1 whole-wafer precedence documentation and manuscript changes.

## Failed command

```text
git diff --check
```

## Error

```text
orchestration/reports/r2_phm_semantics_validation.md:3: trailing whitespace.
+Date: 2026-07-11; R2.1 precedence correction 2026-07-13 [two trailing spaces]
```

## Files changed before failure

The complete authorized R2.1 implementation, generated audits, tests,
governance correction, and five file-specific public-document/manuscript
corrections are present in the worktree. The immediately preceding
documentation recovery applied successfully and its diff was inspected.

This failure report is the only mutation after the whitespace audit failed.

## Read-only diagnosis

`sed -n '1,7l'` confirms the amended date line ends with two ASCII spaces. They
were copied from the report's existing Markdown hard-break style. Because the
line itself is new, `git diff --check` flags it even though an unchanged Task
line immediately below also uses that historical style. No code, data,
equation, claim, or generated result is affected.

## Likely causes

The new report metadata line retained Markdown hard-break whitespace that is
incompatible with the repository's staged whitespace gate.

## Recovery options

1. Remove the two trailing spaces from only the amended date line, rerun the
   whitespace audit, and continue validation.
2. Reformat the entire report header, creating unrelated whitespace churn.
3. Leave the worktree unable to pass `git diff --check`.

## Recommended option

Option 1. It is the smallest semantic-neutral correction.

## User decision required

Authorize Option 1 before editing the line.
