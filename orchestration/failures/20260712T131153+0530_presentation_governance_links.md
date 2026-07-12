# Failure report

## Task

Run the repository governance validator against the new presentation artifacts before committing them.

## Failed command

```text
conda run -n devkki python scripts/validate_governance.py
```

## Error

```text
ValueError: missing local Markdown links: [
  ('presentation/wp10_demo.md', 'reports/figures/system_architecture_wp10.png'),
  ('presentation/wp10_demo.md', 'reports/figures/wp08_reference_trace.png'),
  ('presentation/wp10_demo.md', 'reports/figures/wp10_negative_control.png'),
  ('presentation/wp10_demo.md', 'reports/figures/wp10_positive_chain.png'),
  ('presentation/wp10_demo.md', 'reports/figures/wp10_delayed_mrr_result.png'),
  ('presentation/wp10_demo.md', 'reports/figures/wp10_global_sensitivity.png')
]
```

Exit status: `1`.

## Files changed before failure

The presentation source, figure generator, generated figures, PDF/PPTX outputs, Makefile target, and three earlier validation failure records existed before this command. The failed governance validator changed no repository file.

## Read-only diagnosis

- All six referenced figures exist under the repository-level `reports/figures/` directory.
- `scripts/validate_governance.py` resolves local Markdown targets relative to the Markdown file's parent directory, which is the portable Markdown convention.
- From `presentation/wp10_demo.md`, `reports/figures/...` incorrectly resolves to `presentation/reports/figures/...`.
- The correct relative targets from that source file are `../reports/figures/...`.
- Pandoc had resolved the root-relative-looking strings only because the build runs from the repository root with an explicit resource path; that does not make the Markdown links portable or governance-compliant.

## Likely causes

1. The slide source was authored using build-working-directory paths rather than document-relative paths.
2. The successful Pandoc build masked the portability defect because its resource search path included the repository root.

## Recovery options

1. Change the six image targets in `presentation/wp10_demo.md` from `reports/figures/...` to `../reports/figures/...`, rebuild both outputs, and rerun governance validation.
2. Weaken or special-case the governance validator to accept repository-working-directory paths; this would reduce portability and is not recommended.
3. Duplicate generated figures under `presentation/`; this would introduce unnecessary copies and provenance risk.

## Recommended option

Option 1. It corrects the source paths to standard document-relative semantics without changing figures, claims, or scientific inputs. Rebuild and visually spot-check the affected slides, then rerun governance and the complete tests.

## User decision required

Authorize Option 1 and continuation, or choose another recovery option.

## Resolution

The user authorized Option 1. The six slide image targets were changed to document-relative `../reports/figures/...` paths. Rebuild and validation outcomes are recorded by the subsequent command logs and repository commit.
