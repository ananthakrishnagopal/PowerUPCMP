# Failure report

## Task

Apply the authorized null-preserving thermal-reference amendment to the WP10 coupling decision.

## Failed command

An `apply_patch` operation targeting the decision summary, topology equation, and temperature parameter row in `orchestration/decisions/wp10_utility_cmp_coupling.md`.

## Error

```text
apply_patch verification failed: Failed to find expected lines in
orchestration/decisions/wp10_utility_cmp_coupling.md:
Let \(T_u\) be UPW temperature and \(T_0\) the CMP reference coolant
temperature.
```

## Files changed before failure

None after the user's authorization to correct the thermal null. `apply_patch` verifies all context before writing, so the decision file was not partially modified.

Existing WP10 planning files from the prior authorized work remain as listed in `20260711T222933+0530_wp10_thermal_null_invariant.md`.

## Read-only diagnosis

The source file contains plain parenthesized math in the affected lines:

```text
Let (T_u) be UPW temperature and (T_0) the CMP reference coolant
...
| NO_CONNECTION | (a_d=1, ...) |
```

The patch expected Markdown inline-math delimiters (`\(` and `\)`), so its context did not match. The hydraulic equations elsewhere use display math and are unaffected. The authorized scientific correction itself remains valid.

## Likely causes

- Backslashes in the original generated patch were consumed while constructing the JavaScript string, leaving parentheses in the written Markdown.
- The amendment patch was authored against the intended rendering rather than the exact on-disk bytes.

## Recovery options

1. Apply a targeted patch against the exact plain-parenthesis lines, simultaneously restoring proper inline-math delimiters and introducing distinct `T_cmp,0` and `T_upw,ref` symbols.
2. Rewrite the whole decision file from a verified template.

## Recommended option

Option 1. It is the smallest reversible correction, preserves all unaffected reviewed content, and can use a raw string so Markdown backslashes remain literal.

## User decision required

Authorize the exact-context targeted amendment described in Option 1.
