# Failure report

## Task

Audit the exact staged presentation commit with `git diff --cached --check` before creating the commit.

## Failed command

```text
git diff --cached --check
```

## Error

```text
orchestration/failures/20260712T131654+0530_presentation_commit_whitespace.md:17: trailing whitespace.
+Last updated: 2026-07-12 13:15 IST [two trailing spaces]
```

Exit status: `2`.

## Files changed before failure

Twenty intended presentation-related files were staged, including the deck sources and outputs, figure generator and manifest, status/manifest updates, and five earlier failure reports. No commit was created. The staged audit was read-only and changed neither the working tree nor the index.

## Read-only diagnosis

- The project-status source had already been corrected and passed the unstaged `git diff --check` gate.
- Its failure report reproduced the original offending line verbatim inside a fenced code block, including the two literal trailing spaces.
- Git's whitespace checker correctly applies to fenced-code content as well as ordinary Markdown.
- The scientific artifacts and presentation outputs are unaffected.

## Likely causes

1. Preserving the original diagnostic text verbatim inadvertently preserved the whitespace defect being documented.
2. The earlier unstaged check occurred before the failure report itself was included in the checked index.

## Recovery options

1. Replace the two literal spaces in the earlier failure report with a visible marker such as `[two trailing spaces]`, update governance counts, stage the correction and this report, and rerun both working-tree and staged clean-diff checks.
2. Exclude or relax whitespace checks for failure reports; this would weaken a useful repository gate.
3. Leave the failure report untracked; this would violate the failure-record policy.

## Recommended option

Option 1. It preserves the exact meaning of the diagnostic without embedding invalid invisible whitespace and keeps the clean-diff policy uniform.

## User decision required

Authorize Option 1 and continuation, or choose another recovery option.

## Resolution

The user authorized Option 1. The earlier report now represents the invisible characters with `[two trailing spaces]`; no literal trailing whitespace remains in that diagnostic line.
