# Failure report

## Task

Reconcile the living paper with the validated T-WP08 CMP implementation and
machine-readable evidence.

## Failed command

An `apply_patch` update spanning the status, abstract, CMP methods, results
ledger, limitations, and reproducibility sections of
`docs/running_paper.md`.

## Error

```text
apply_patch verification failed: Failed to find expected lines in
docs/running_paper.md:
Deterministic quadrature and convergence
tests are required. Any annular output remains a **simulated
```

## Files changed before failure

- `orchestration/task_manifest.yaml`
- `orchestration/project_status.md`
- `orchestration/decisions/wp08_cmp_physics.md`
- `orchestration/canonical_schema.yaml`
- `orchestration/interface_registry.yaml`
- `orchestration/assumptions.yaml`
- `orchestration/risk_register.md`
- `orchestration/claims_matrix.md`
- `orchestration/reports/wp08_cmp_validation.md`
- `configs/default.yaml`
- `configs/checkpoints/r4_default.yaml`
- `src/semifab_poc/config.py`
- `src/semifab_poc/data/schema.py`
- `src/semifab_poc/simulation/__init__.py`
- `src/semifab_poc/simulation/cmp.py`
- `scripts/validate_r4_timing_scenarios.py`
- `scripts/validate_wp08_cmp.py`
- `tests/unit/test_cmp.py`
- `tests/property/test_cmp_properties.py`
- `tests/unit/test_config.py`
- `tests/unit/test_interfaces.py`
- `docs/mathematical_model.md`
- `docs/modeling_notes.md`
- generated `reports/cmp/wp08_validation.json`
- generated `reports/cmp/wp08_reference_trace.csv`

The rejected patch made no partial change to `docs/running_paper.md`.

## Read-only diagnosis

The paper contains the intended sentence with different line wrapping:
`Deterministic quadrature and convergence tests are required.` appears on one
line, while the patch expected a line break after `convergence`. All source,
schema, and test changes had already completed. Focused impacted tests passed
48/48, the deterministic WP08 evidence generator passed every internal check,
and the complete repository suite passed 130/130 in 38.09 s.

This is a documentation patch-context mismatch, not a model, numerical,
schema, interface, or test failure.

## Likely causes

The multi-section patch used context copied from a rendered/wrapped excerpt
rather than the file's exact physical line layout.

## Recovery options

1. Apply smaller, section-local patches using the exact inspected lines.
2. Replace the entire running-paper file, which is unnecessary and risks
   overwriting unrelated content.
3. Leave the paper stale, which violates the user's running-paper request and
   the WP08 closeout protocol.

## Recommended option

Option 1. It is narrow, preserves all existing paper content, and completes
the evidence reconciliation without changing code or scientific results.

## User decision required

Authorize resuming WP08 documentation/governance closeout with small
exact-context patches.
