PDFLATEX ?= pdflatex
BIBTEX ?= bibtex
BUILD_DIR := build
REPORT_DIR := ../reports/paper
REPORT_PDF := $(REPORT_DIR)/semifab_cmp_poc_draft.pdf

.PHONY: all

all: $(REPORT_PDF)

$(REPORT_PDF): main.tex references.bib evidence_map.md
	mkdir -p $(BUILD_DIR) $(REPORT_DIR)
	$(PDFLATEX) -interaction=nonstopmode -halt-on-error -output-directory=$(BUILD_DIR) main.tex
	BIBINPUTS=.: $(BIBTEX) $(BUILD_DIR)/main
	$(PDFLATEX) -interaction=nonstopmode -halt-on-error -output-directory=$(BUILD_DIR) main.tex
	$(PDFLATEX) -interaction=nonstopmode -halt-on-error -output-directory=$(BUILD_DIR) main.tex
	cp $(BUILD_DIR)/main.pdf $(REPORT_PDF)
