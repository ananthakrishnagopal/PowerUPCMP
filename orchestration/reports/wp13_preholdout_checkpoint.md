# WP13 pre-holdout checkpoint

Date: 2026-07-13
Task: T-WP13
State: FROZEN, TEST UNOPENED
Evidence plane: synthetic simulator only

## Frozen Git checkpoint

The preregistered configuration, decision record, estimator implementation,
chain extensions, unit/smoke tests, TRAIN/CALIBRATION evidence, fitted model
artifacts, and their checksum sidecars are committed at:

```text
7489bf1d14add57033c685998ced4f75b8b7fc98
```

The Git worktree was clean immediately after this commit. The one-shot runner
will independently require a clean committed worktree and record the exact HEAD
and tracked-file hashes before it creates any TEST scenario.

## Preregistered policy

The frozen policy is in
`orchestration/decisions/wp13_root_cause_attribution.md`; executable settings
are in `configs/models/attribution.yaml`. The primary estimator is the fixed
50/50 geometric hybrid of multinomial logistic and residual-rule probabilities.
Always-UNKNOWN, rule-only, and logistic estimators are mandatory comparators.

`UPS_TRANSFER` and `VFD_DERATING` are propagation evidence only. The online
estimator receives arrived observations and a warning result; it has no field
for simulator initiating labels. Feature contributions and rule chains are not
causal proof. Weak, invalid, missing, OOD, conflicting, or compound evidence
must resolve to `UNKNOWN` under the frozen gates.

## Split and leakage evidence

- TRAIN: 264 decision rows on 88 opaque whole runs.
- CALIBRATION: 132 decision rows on 44 opaque whole runs.
- TRAIN/CALIBRATION run overlap: zero.
- Forbidden feature names: zero.
- Online window fields: `run_id`, `decision_step_index`,
  `decision_timestamp_s`, and `observations` only.
- TEST, compound, robustness, and pre-event audit generated: no.
- Deterministic preparation payload SHA-256:
  `e8b47b67a37972addedd5dc230005979bcb3d20f3bea76aa1ec07a5d186d3ab9`.
- Pre-holdout manifest SHA-256 before commit:
  `74b9dd13ec2cea0f1498d1a1b5f60fae54af5c138d3d09e8326d7dee49c2128c`.
- Calibration report SHA-256:
  `feb1dff4fdfffdcc019fd86988bfd40bb6e2d2cd1f46c22b9e45a9b2c9db60f7`.

The fitted artifact SHA-256 values are:

| Method | SHA-256 |
|---|---|
| Always UNKNOWN | `4bd85ec73ec2cc7e29dbef98fb19d667c8e4fe3a970f3520271299f273de3561` |
| Rule only | `1657e8b605dfa8c9786d7ac8220b37e6cfea52c0f3ac627434bb55b431a374cf` |
| Logistic | `94db649ecf6d2558fb531d32d001816b101ea8a11bb6cf01cb202cde9aeacbf9` |
| Hybrid | `737051f90fac37436d43860b66cc84e97b7ad590d88d5aeed0326bf2014d5bd6` |

All four checksum sidecars reproduce their artifact digests.

## Calibration-only evidence

Calibration results are method-development evidence, not held-out performance:

| Method | Accuracy | Macro recall | UNKNOWN recall | Known coverage | Selective accuracy |
|---|---:|---:|---:|---:|---:|
| Always UNKNOWN | 0.0909 | 0.0909 | 1.0000 | 0.0000 | not applicable |
| Rule only | 0.8864 | 0.8864 | 1.0000 | 0.8750 | 1.0000 |
| Logistic | 0.7727 | 0.7727 | 1.0000 | 0.7750 | 0.9677 |
| Hybrid | 0.8182 | 0.8182 | 1.0000 | 0.8000 | 1.0000 |

The primary hybrid has zero calibration recall for pressure-sensor faults.
This weakness does not authorize threshold, rule, fusion, or model-selection
changes. It is carried forward as an explicit risk. No TEST result has informed
any scientific or implementation choice.

## Tests and governance

- 22/22 focused attribution/chain/scenario tests pass with warnings as errors.
- 210/210 complete repository tests pass with warnings as errors.
- 17 YAML files parse with zero duplicate keys.
- All 29 tasks form an acyclic graph and reference 25 assumptions.
- Before this checkpoint file, 118 Markdown files had 122 valid local links and
  zero missing local links.
- `git diff --check` and the staged whitespace check pass.

## One-shot opening conditions

The runner may open TEST only when all of these hold:

1. this checkpoint and the frozen implementation are committed;
2. the complete worktree is clean;
3. the pre-holdout payload replays exactly;
4. all required artifacts and paths are present in HEAD;
5. focused tests pass again with warnings as errors;
6. the Git checkpoint remains unchanged across preflight; and
7. the explicit `--authorize-holdout-open` flag is supplied.

The runner writes a persistent opening marker before constructing TEST. A
failure after that marker does not permit a silent rerun.

## Claim boundary

Even a successful held-out result can support only conditional diagnostic
attribution inside this synthetic simulator and declared instrument set. It
cannot establish experimental causality, a real-fab diagnostic, defect or
yield prediction, equipment protection, production control, or controller
efficacy.
