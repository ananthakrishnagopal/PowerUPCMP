# Dashboard Warning Classifier Training Handoff

This trains a dashboard-specific classifier for the live predictive demo.
It does not replace the original research artifact unless you explicitly wire
the dashboard server to the new file.

## Goal

Train a classifier whose target is aligned with the live dashboard:

```text
recent utility observations -> probability of near-future utility/MRR risk
```

The generated artifact is compatible with `EarlyWarningPredictor.load(...)`.

## Environment

From the repo root:

```bash
conda run -n devkki python scripts/train_dashboard_warning.py
```

If the target machine does not have the repo environment, install the project
dependencies there first using the existing repo setup.

## Fast Smoke Run

Use this to confirm the script works:

```bash
conda run -n devkki python scripts/train_dashboard_warning.py \
  --train-count 2 \
  --calibration-count 2 \
  --conformal-count 2 \
  --test-count 2 \
  --decision-period-s 0.50
```

## Recommended Training Run

Use this for the dashboard artifact:

```bash
conda run -n devkki python scripts/train_dashboard_warning.py \
  --train-count 8 \
  --calibration-count 4 \
  --conformal-count 4 \
  --test-count 4 \
  --decision-period-s 0.20
```

For a stronger artifact on a faster machine:

```bash
conda run -n devkki python scripts/train_dashboard_warning.py \
  --train-count 18 \
  --calibration-count 8 \
  --conformal-count 8 \
  --test-count 8 \
  --decision-period-s 0.10
```

## Model Comparison Run

Use this when you need to justify why the dashboard artifact uses the selected
model family. It trains candidate models on the same generated dataset and
writes a side-by-side report. This comparison does not replace the dashboard
artifact.

```bash
conda run -n devkki python scripts/compare_dashboard_warning_models.py \
  --train-count 8 \
  --calibration-count 4 \
  --conformal-count 4 \
  --test-count 4 \
  --decision-period-s 0.20
```

Compared candidates:

```text
prevalence
logistic
gradient_boosted
xgboost
```

`xgboost` is optional. If the package is not installed, the script records the
candidate as skipped rather than failing the comparison.

Comparison outputs:

```text
reports/early_warning/dashboard_model_comparison.json
reports/early_warning/dashboard_model_comparison.md
```

## Outputs To Copy Back

Copy these files back into the same paths in this repo:

```text
reports/early_warning/models/dashboard_warning.pkl
reports/early_warning/models/dashboard_warning.pkl.json
reports/early_warning/dashboard_warning_metrics.json
```

## Acceptance Criteria

Open `reports/early_warning/dashboard_warning_metrics.json`.

For the demo, look for:

```text
test_metrics.pr_auc meaningfully above prevalence
test_metrics.precision and test_metrics.recall balanced for the scenario
test_metrics.brier_score and test_metrics.expected_calibration_error acceptable
test_metrics.median_warning_lead_time_s positive
latency_mean_s small
```

Then test the live predictive path:

```bash
conda run -n devkki python -m pytest -q tests/integration/test_dashboard.py
```

The dashboard server should then be started with:

```bash
conda run -n devkki python src/semifab_poc/dashboard/server.py
```
