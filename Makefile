PYTHON ?= python3
export PYTHONPATH := src

.PHONY: help test test-unit validate-config package-check

help:
	@printf '%s\n' \
		'test            Run the complete local pytest suite' \
		'test-unit       Run unit tests only' \
		'validate-config Validate a YAML runtime configuration (CONFIG=path)' \
		'package-check   Verify the package imports without installing optional extras'

test:
	$(PYTHON) -m pytest

test-unit:
	$(PYTHON) -m pytest tests/unit

validate-config:
	@test -n "$(CONFIG)" || (printf '%s\n' 'Set CONFIG=path/to/config.yaml' >&2; exit 2)
	$(PYTHON) -m semifab_poc.cli validate-config $(CONFIG)

package-check:
	$(PYTHON) -c "import semifab_poc; print(semifab_poc.__version__)"
