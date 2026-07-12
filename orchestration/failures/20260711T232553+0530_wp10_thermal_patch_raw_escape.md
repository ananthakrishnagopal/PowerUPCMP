# Failure report

## Task

Apply the authorized exact-context thermal-reference correction to the WP10 decision.

## Failed command

An `apply_patch` operation constructed with a JavaScript raw template string.

## Error

```text
apply_patch verification failed: Failed to find expected table lines containing
\`NO_CONNECTION\`, \`DRESSING_WATER_SUPPORT\`, \`THERMAL_LOOP\`, and
\`SYNTHETIC_SLURRY_SUPPORT\`.
```

## Files changed before failure

None. Patch verification failed before any write.

## Read-only diagnosis

The raw template correctly preserved LaTeX backslashes but also preserved the backslashes used to escape JavaScript template-literal backticks. Consequently, the patch searched for literal `\`` sequences, while the Markdown file contains ordinary backticks. The exact source block has been re-read and is unchanged.

## Likely causes

- One escaping mechanism was used for two different purposes: preserving LaTeX and delimiting a JavaScript template literal.
- `String.raw` intentionally preserved the backslash before each embedded backtick, making the context invalid.

## Recovery options

1. Use a normal double-quoted JavaScript string, where Markdown backticks need no escaping and LaTeX backslashes are represented explicitly as `\\`.
2. Split the amendment into small patches that match plain prose anchors and replace the entire topology table without using table rows as context.
3. Rewrite the decision file from a verified complete template.

## Recommended option

Option 2, implemented with ordinary double-quoted strings. Small anchor-based patches minimize context sensitivity and preserve all unrelated reviewed content.

## User decision required

Authorize the small anchor-based correction in Option 2.
