# Failure report

## Task

T-WP01 post-install acceptance checks in conda environment `devkki`.

## Failed command

```text
conda run -n devkki python -c "from semifab_poc.config import RuntimeConfig; from pydantic import ValidationError;\\ntry:\\n RuntimeConfig(unexpected_parameter=1)\\nexcept ValidationError:\\n print('strict-config-rejection: PASS')\\nelse:\\n raise SystemExit('strict-config-rejection: FAIL')"
```

Exit code: `1`.

## Error

```text
SyntaxError: unexpected character after line continuation character
```

The shell passed literal backslash-n sequences into Python rather than newline tokens.

## Files changed before failure

- T-WP01 source, tests, documentation, packaging, and the prior failure reports were already present.
- The editable package was successfully installed into the user-selected conda environment `devkki`.
- Test execution may have refreshed `__pycache__` files under the repository.
- No source files were changed after the failed command.

## Read-only diagnosis

- `conda run -n devkki python -m pytest` passed all 6 tests.
- `conda run -n devkki semifab-poc --help` exited successfully and displayed the command.
- `conda run -n devkki python -c "import semifab_poc; print(semifab_poc.__version__)"` printed `0.1.0`.
- The failed command did not import or execute the strict-config assertion because Python rejected its command string during parsing.
- The project test suite already covers unknown-key rejection through `test_unknown_configuration_key_is_rejected`.
- No package, dependency, dataset, network, or scientific-model failure occurred.

## Likely causes

The command was constructed with escaped newlines inside a shell string, producing literal `\\n` characters in the Python `-c` argument.

## Recovery options

1. Treat the passing pytest test as the strict-configuration evidence and leave the malformed redundant command unresolved.
2. Run a corrected standalone check using a shell-safe one-line expression or a temporary local configuration fixture.
3. Add a dedicated CLI integration test for an unknown YAML key and rerun the full suite.

## Recommended option

Option 1. The project’s unit test already verifies strict unknown-key rejection, and all package/install/CLI checks passed. A redundant command should not expand the mutation scope.

## User decision required

Confirm whether to accept the existing pytest coverage as the strict-configuration gate and proceed with T-WP01 status updates, or authorize one corrected standalone check.
