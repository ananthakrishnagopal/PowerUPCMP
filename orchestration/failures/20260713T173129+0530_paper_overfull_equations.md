# Failure report

## Task

Build and validate the Phase 3 journal manuscript after adding the frozen
WP15/WP16 mathematical protocol.

## Failed command

`conda run -n devkki make paper`

The command exited successfully, but the final LaTeX log failed the project's
document-layout acceptance condition.

## Error

The final pass reports three overfull display equations:

- line 1195: primary action set, 55.31216 pt too wide;
- line 1208: positive hold gate, 45.3186 pt too wide; and
- line 1291: sensor-freshness predicate, 32.14417 pt too wide.

The final log reports no undefined-reference, undefined-citation, label-change,
or rerun warning. The generated artifact is an 18-page A4 PDF with SHA-256
`996f636780c8f8df7fcde7a087abf302ab4d0d43668cdb2f540712bbaf410a0a`,
but it is not accepted as the reviewed manuscript artifact.

## Files changed before failure

All Phase 3 controller/safety contracts, configuration, code contracts, tests,
deterministic artifacts, governance updates, running-paper updates, and LaTeX
source updates were present before the build. The successful build refreshed
`paper/build/` and `reports/paper/semifab_cmp_poc_draft.pdf`; these generated
outputs are not yet recorded as accepted evidence. `git diff --check` remains
clean.

## Read-only diagnosis

Each overflow is a long single-line mathematical expression placed in one
column of the two-column article. The equations are mathematically valid and
the document compiles; column width, rather than equation semantics, causes
the overflow. All three expressions have natural product/set breakpoints and
can be split with `aligned` without changing symbols, values, claims, labels,
or references.

## Likely causes

- The Markdown equations were transferred to a narrower two-column LaTeX
  layout without explicit line breaks.
- The final build was the first reliable width check for the new equations.

## Recovery options

1. Reformat only the three displays with two-line `aligned` environments,
   rebuild, and require zero overfull/undefined/rerun warnings before visual
   review.
2. Move the entire control subsection to one-column/full-width floats, which
   is a broader layout change.
3. Remove the equations from the journal manuscript and retain them only in
   the modelling ledger, reducing mathematical completeness.

## Recommended option

Option 1. It is local, preserves every equation and scientific claim, and is
the normal two-column typesetting correction.

## User decision required

Authorize Option 1 before any further mutating action.
