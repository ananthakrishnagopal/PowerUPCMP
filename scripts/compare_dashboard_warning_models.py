#!/usr/bin/env python3
"""Compare dashboard warning model families on the same synthetic dataset."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

from semifab_poc.models.early_warning import (
    EarlyWarningPredictor,
    ModelKind,
    WarningDataset,
    evaluate_predictions,
    load_early_warning_config,
    split_conformal_quantile,
)

from train_dashboard_warning import CONFIG_PATH, ROOT, build_dataset, progress


OUTPUT_JSON = ROOT / "reports" / "early_warning" / "dashboard_model_comparison.json"
OUTPUT_MD = ROOT / "reports" / "early_warning" / "dashboard_model_comparison.md"
SKLEARN_MODEL_NAMES = {
    "prevalence": ModelKind.PREVALENCE,
    "logistic": ModelKind.LOGISTIC,
    "gradient_boosted": ModelKind.GRADIENT_BOOSTED,
}


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def balanced_sample_weights(labels: np.ndarray) -> np.ndarray:
    labels = np.asarray(labels, dtype=int)
    counts = np.bincount(labels, minlength=2)
    if np.any(counts == 0):
        raise ValueError("balanced weighting requires both classes")
    total = len(labels)
    weights_by_class = total / (2.0 * counts)
    return weights_by_class[labels]


def prediction_sets(
    probabilities: np.ndarray,
    conformal_quantile: float,
) -> tuple[tuple[int, ...], ...]:
    sets = []
    for probability in probabilities:
        row_set: list[int] = []
        if float(probability) <= conformal_quantile + 1.0e-15:
            row_set.append(0)
        if 1.0 - float(probability) <= conformal_quantile + 1.0e-15:
            row_set.append(1)
        sets.append(tuple(row_set))
    return tuple(sets)


def calibrate_probabilities(
    *,
    training_base: np.ndarray,
    calibration_base: np.ndarray,
    calibration_labels: np.ndarray,
    test_base: np.ndarray,
    clip: float,
    random_seed: int,
) -> tuple[np.ndarray, Any]:
    from sklearn.linear_model import LogisticRegression

    def logit(values: np.ndarray) -> np.ndarray:
        bounded = np.clip(np.asarray(values, dtype=float), clip, 1.0 - clip)
        return np.log(bounded / (1.0 - bounded)).reshape(-1, 1)

    # Touch the training score so a schema/finite issue fails before calibration.
    if not np.all(np.isfinite(training_base)):
        raise ValueError("training base probabilities are not finite")
    calibrator = LogisticRegression(C=1.0, max_iter=1000, random_state=random_seed)
    calibrator.fit(logit(calibration_base), calibration_labels)
    probabilities = np.asarray(
        calibrator.predict_proba(logit(test_base))[:, 1],
        dtype=float,
    )
    return probabilities, calibrator


def evaluate_candidate(
    *,
    name: str,
    dataset: WarningDataset,
    probabilities: np.ndarray,
    sets: tuple[tuple[int, ...], ...],
    latency_s: np.ndarray,
    config: Any,
    decision_period_s: float,
    notes: str,
) -> dict[str, Any]:
    test = dataset.subset("TEST")
    metrics = evaluate_predictions(
        test,
        probabilities,
        sets,
        probability_threshold=config.models.probability_threshold,
        horizon_s=2.0,
        decision_period_s=decision_period_s,
        calibration_bins=config.evaluation.calibration_bins,
        latency_s=latency_s,
    )
    return {
        "status": "ok",
        "model": name,
        "notes": notes,
        "test_metrics": metrics,
    }


def fit_builtin_candidate(
    name: str,
    model_kind: ModelKind,
    dataset: WarningDataset,
    config: Any,
    decision_period_s: float,
) -> dict[str, Any]:
    progress(f"[fit] {name}")
    predictor = EarlyWarningPredictor(model_kind, config.features, config.models).fit(dataset)
    test = dataset.subset("TEST")
    probabilities, sets, latency = predictor.predict_features(test.features)
    return evaluate_candidate(
        name=name,
        dataset=dataset,
        probabilities=probabilities,
        sets=sets,
        latency_s=latency,
        config=config,
        decision_period_s=decision_period_s,
        notes="Built-in EarlyWarningPredictor candidate.",
    )


def fit_xgboost_candidate(
    dataset: WarningDataset,
    config: Any,
    decision_period_s: float,
) -> dict[str, Any]:
    try:
        from sklearn.impute import SimpleImputer
        from sklearn.pipeline import Pipeline
        from xgboost import XGBClassifier
    except ImportError as exc:
        return {
            "status": "skipped",
            "model": "xgboost",
            "reason": f"optional dependency unavailable: {exc}",
            "install_hint": "Install xgboost in the training environment to include this candidate.",
        }

    progress("[fit] xgboost")
    training = dataset.subset("TRAIN")
    calibration = dataset.subset("CALIBRATION")
    conformal = dataset.subset("CONFORMAL_CALIBRATION")
    test = dataset.subset("TEST")
    xgb = XGBClassifier(
        n_estimators=200,
        max_depth=3,
        learning_rate=0.05,
        subsample=0.9,
        colsample_bytree=0.9,
        reg_lambda=1.0,
        objective="binary:logistic",
        eval_metric="logloss",
        random_state=config.models.random_seed,
    )
    model = Pipeline((("imputer", SimpleImputer(strategy="median")), ("model", xgb)))
    model.fit(
        training.features,
        training.labels,
        model__sample_weight=balanced_sample_weights(training.labels),
    )

    training_base = np.asarray(model.predict_proba(training.features)[:, 1], dtype=float)
    calibration_base = np.asarray(model.predict_proba(calibration.features)[:, 1], dtype=float)
    conformal_base = np.asarray(model.predict_proba(conformal.features)[:, 1], dtype=float)
    test_base = np.asarray(model.predict_proba(test.features)[:, 1], dtype=float)
    probabilities, calibrator = calibrate_probabilities(
        training_base=training_base,
        calibration_base=calibration_base,
        calibration_labels=calibration.labels,
        test_base=test_base,
        clip=config.models.calibration_probability_clip,
        random_seed=config.models.random_seed,
    )

    def calibrated(values: np.ndarray) -> np.ndarray:
        bounded = np.clip(
            values,
            config.models.calibration_probability_clip,
            1.0 - config.models.calibration_probability_clip,
        )
        logits = np.log(bounded / (1.0 - bounded)).reshape(-1, 1)
        return np.asarray(calibrator.predict_proba(logits)[:, 1], dtype=float)

    conformal_probabilities = calibrated(conformal_base)
    true_probability = np.where(
        conformal.labels == 1,
        conformal_probabilities,
        1.0 - conformal_probabilities,
    )
    conformal_quantile = split_conformal_quantile(
        1.0 - true_probability,
        config.models.conformal_alpha,
    )

    start = time.perf_counter()
    _ = calibrated(test_base)
    elapsed = time.perf_counter() - start
    latency = np.full(len(test.labels), elapsed / max(len(test.labels), 1), dtype=float)
    return evaluate_candidate(
        name="xgboost",
        dataset=dataset,
        probabilities=probabilities,
        sets=prediction_sets(probabilities, conformal_quantile),
        latency_s=latency,
        config=config,
        decision_period_s=decision_period_s,
        notes="Optional XGBoost candidate with separate probability and conformal calibration.",
    )


def format_metric(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:.3f}"
    return str(value)


def write_markdown(summary: dict[str, Any], path: Path) -> None:
    rows = []
    for result in summary["results"]:
        if result["status"] != "ok":
            rows.append(
                "| {model} | skipped | - | - | - | - | - | - | {reason} |".format(
                    model=result["model"],
                    reason=result.get("reason", ""),
                )
            )
            continue
        metrics = result["test_metrics"]
        rows.append(
            "| {model} | ok | {pr_auc} | {precision} | {recall} | {specificity} | "
            "{brier} | {lead} | {notes} |".format(
                model=result["model"],
                pr_auc=format_metric(metrics.get("pr_auc")),
                precision=format_metric(metrics.get("precision")),
                recall=format_metric(metrics.get("recall")),
                specificity=format_metric(metrics.get("specificity")),
                brier=format_metric(metrics.get("brier_score")),
                lead=format_metric(metrics.get("median_warning_lead_time_s")),
                notes=result["notes"],
            )
        )
    content = "\n".join(
        [
            "# Dashboard Warning Model Comparison",
            "",
            "This report compares candidate model families on the same synthetic dashboard-warning dataset.",
            "It is for model-selection justification; it does not replace the dashboard artifact.",
            "",
            f"- Total rows: {summary['rows']}",
            f"- Positive fraction: {summary['positive_fraction']:.3f}",
            f"- Decision period: {summary['decision_period_s']:.3f} s",
            "",
            "| Model | Status | PR-AUC | Precision | Recall | Specificity | Brier | Median lead (s) | Notes |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
            *rows,
            "",
            "Interpretation: prefer the smallest model that provides acceptable row-level "
            "discrimination, calibration, event recall, lead time, and false-alarm behavior "
            "for the intended demo boundary.",
            "",
        ]
    )
    path.write_text(content, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train-count", type=int, default=8)
    parser.add_argument("--calibration-count", type=int, default=4)
    parser.add_argument("--conformal-count", type=int, default=4)
    parser.add_argument("--test-count", type=int, default=4)
    parser.add_argument("--decision-period-s", type=float, default=0.20)
    parser.add_argument(
        "--models",
        nargs="+",
        choices=("prevalence", "logistic", "gradient_boosted", "xgboost"),
        default=("prevalence", "logistic", "gradient_boosted", "xgboost"),
    )
    parser.add_argument("--output-json", type=Path, default=OUTPUT_JSON)
    parser.add_argument("--output-md", type=Path, default=OUTPUT_MD)
    args = parser.parse_args()

    progress("[config] loading dashboard warning configuration")
    config = load_early_warning_config(CONFIG_PATH)
    progress("[dataset] generating shared synthetic comparison dataset")
    dataset = build_dataset(
        config,
        train_count=args.train_count,
        calibration_count=args.calibration_count,
        conformal_count=args.conformal_count,
        test_count=args.test_count,
        decision_period_s=args.decision_period_s,
    )
    progress(
        "[dataset] complete "
        f"rows={len(dataset.labels)} "
        f"positive_fraction={float(np.mean(dataset.labels)):.3f}"
    )

    results = []
    for model_name in args.models:
        if model_name == "xgboost":
            results.append(fit_xgboost_candidate(dataset, config, args.decision_period_s))
        else:
            results.append(
                fit_builtin_candidate(
                    model_name,
                    SKLEARN_MODEL_NAMES[model_name],
                    dataset,
                    config,
                    args.decision_period_s,
                )
            )

    summary = {
        "rows": int(len(dataset.labels)),
        "positive_fraction": float(np.mean(dataset.labels)),
        "decision_period_s": float(args.decision_period_s),
        "models_requested": list(args.models),
        "results": results,
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    write_markdown(summary, args.output_md)
    progress(f"[report] wrote {display_path(args.output_json)}")
    progress(f"[report] wrote {display_path(args.output_md)}")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except BrokenPipeError:
        sys.exit(1)
