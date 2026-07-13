# Reproduction Guide

## Overview
This document specifies the steps to install the system and reproduce the WP18 Evaluation results and generate the technical report.

## Installation
The system depends on Python 3.11+. We recommend a conda environment:
```bash
conda create -n devkki python=3.11
conda activate devkki
pip install -e .[models,dashboard]
```

## Running the PoC Simulator and Controllers
You can reproduce the evaluation by running the experiment generation script. This script initiates the local smoke tests and dumps the summary artifact.
```bash
PYTHONPATH=. conda run -n devkki python scripts/run_experiments.py
```
This produces `reports/evaluation/primary_test.csv` using the pre-seeded simulation faults.

## Generating the Dashboard and Report
To view the results visually:
```bash
PYTHONPATH=. conda run -n devkki python src/semifab_poc/dashboard/server.py
```
And then navigate to `http://localhost:8080`.

To generate the technical report:
```bash
PYTHONPATH=. conda run -n devkki python scripts/generate_technical_report.py
```
This will parse the output artifacts and create `reports/technical_report.html`.
