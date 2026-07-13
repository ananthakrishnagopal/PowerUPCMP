# Failure report

## Task

Update the LaTeX evidence-status table after integrating WP13 methods and
results into `paper/main.tex`.

## Failed command

An `apply_patch` call transported through a JavaScript `String.raw` template.

## Error

```text
TypeError: String.raw(...) is not a function
```

## Files changed before failure

- The LaTeX preamble, title, evidence boundary, abstract, introduction, claims
  boundary, results-section heading, and full WP13 methods/results subsection
  were updated successfully.
- `paper/main.tex` currently has 143 insertions and 35 deletions relative to
  HEAD.
- The evidence-status-table hunk did not apply.
- The previously recorded report, modeling notes, running paper, and WP13
  result artifacts remain present.

## Read-only diagnosis

The patch text contained LaTeX's double-backtick opening quotation around the
word `Protocol`. Those literal backtick characters terminated the JavaScript
raw-template string before the patch ended, so JavaScript attempted to invoke
the preceding string as a function. The error occurred before `apply_patch`
received or changed the status-table hunk. The inspected table remains at the
WP09/WP12 freeze and still labels WP13 as a protocol.

## Likely causes

1. A raw JavaScript template was used for patch text containing literal
   backtick characters.
2. Patch transport syntax was not isolated from document syntax.

## Recovery options

1. Continue with one small hunk at a time using a backtick-free context or a
   line-array transport that does not interpret document backticks.
2. Revert the already applied LaTeX WP13 edits and leave the PDF at the prior
   evidence freeze.
3. Retain the partial LaTeX work uncommitted and defer manuscript completion.

## Recommended option

Option 1. The applied manuscript content is scientifically consistent with
the frozen artifacts, while the failure is limited to transport syntax. Small
backtick-free hunks avoid both known escaping failure modes.

## User decision required

Authorize option 1 before any further mutation or retry.
