PYTHON ?= python3
PANDOC ?= pandoc
MPLCONFIGDIR ?= /tmp/semifab-poc-matplotlib
export PYTHONPATH := src
export MPLCONFIGDIR

.PHONY: help test test-unit validate-config package-check figures presentation paper

help:
	@printf '%s\n' \
		'test            Run the complete local pytest suite' \
		'test-unit       Run unit tests only' \
		'validate-config Validate a YAML runtime configuration (CONFIG=path)' \
		'package-check   Verify the package imports without installing optional extras' \
		'figures         Regenerate reviewed WP08/WP10 communication figures' \
		'presentation    Build the interim WP10 PDF and PPTX deck' \
		'paper           Build the journal-neutral LaTeX manuscript PDF'

test:
	$(PYTHON) -m pytest

test-unit:
	$(PYTHON) -m pytest tests/unit

validate-config:
	@test -n "$(CONFIG)" || (printf '%s\n' 'Set CONFIG=path/to/config.yaml' >&2; exit 2)
	$(PYTHON) -m semifab_poc.cli validate-config $(CONFIG)

package-check:
	$(PYTHON) -c "import semifab_poc; print(semifab_poc.__version__)"

figures:
	$(PYTHON) scripts/generate_communication_figures.py

presentation: figures
	mkdir -p reports/presentation presentation/build
	$(PANDOC) presentation/wp10_demo.md --from markdown+tex_math_dollars --slide-level=2 --resource-path=.:presentation:reports/figures -o reports/presentation/wp10_demo.pptx
	$(PANDOC) presentation/wp10_demo.md --from markdown+tex_math_dollars --to beamer --slide-level=2 --resource-path=.:presentation:reports/figures --pdf-engine=xelatex -V aspectratio=169 -o reports/presentation/wp10_demo.pdf

paper:
	$(MAKE) -C paper
