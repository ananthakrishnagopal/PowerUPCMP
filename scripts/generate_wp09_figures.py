#!/usr/bin/env python3
"""Generate deterministic WP09 figures from the frozen one-shot artifacts."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[1]
RESULTS_PATH = ROOT / "reports" / "virtual_metrology" / "wp09_validation.json"
PREDICTIONS_PATH = (
    ROOT / "reports" / "virtual_metrology" / "wp09_predictions.csv"
)
OUTPUT_DIR = ROOT / "reports" / "virtual_metrology" / "figures"
MANIFEST_PATH = OUTPUT_DIR / "wp09_figure_manifest.json"
EXPECTED_RESULTS_SHA256 = (
    "52d25cf92c4eea24158e0821cd7b7dd60fabe2ec04967443e3417397313bd10c"
)
EXPECTED_PREDICTIONS_SHA256 = (
    "ea3e9e813e8343862340fb42bfc31c784e0f5df9bd15f5b0f707624bb4679826"
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_evidence() -> tuple[dict[str, Any], pd.DataFrame]:
    if sha256_file(RESULTS_PATH) != EXPECTED_RESULTS_SHA256:
        raise ValueError("WP09 result hash differs from the frozen one-shot artifact")
    if sha256_file(PREDICTIONS_PATH) != EXPECTED_PREDICTIONS_SHA256:
        raise ValueError("WP09 prediction hash differs from the frozen one-shot artifact")
    results = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
    predictions = pd.read_csv(
        PREDICTIONS_PATH,
        dtype={"WAFER_ID": str, "STAGE": str},
    )
    if results["target_unit_status"] != "SOURCE_NATIVE_UNIT_UNDECLARED":
        raise ValueError("WP09 figures require the source-native target boundary")
    return results, predictions


def save_png_atomic(figure: plt.Figure, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    figure.savefig(
        temporary,
        format="png",
        dpi=220,
        bbox_inches="tight",
        facecolor="white",
        metadata={"Software": "semifab-poc WP09 figure generator"},
    )
    os.replace(temporary, path)
    plt.close(figure)


def model_comparison(results: dict[str, Any]) -> Path:
    families = ("mean", "linear", "ridge", "physics", "tree", "hybrid")
    labels = ("Mean", "Linear", "Ridge", "Physics\nproxy", "Tree", "Hybrid")
    roles = (
        "OFFICIAL_TEST_RETAINED",
        "OFFICIAL_VALIDATION_RETAINED",
    )
    primary = results["primary_original_10s_full_features"]
    test_mae = [primary[family][roles[0]]["overall"]["mae"] for family in families]
    validation_mae = [
        primary[family][roles[1]]["overall"]["mae"] for family in families
    ]

    figure, axis = plt.subplots(figsize=(9.2, 4.8))
    positions = np.arange(len(families), dtype=float)
    width = 0.36
    test_bars = axis.bar(
        positions - width / 2,
        test_mae,
        width,
        label="Retained test",
        color="#2f6f9f",
    )
    validation_bars = axis.bar(
        positions + width / 2,
        validation_mae,
        width,
        label="Retained final validation",
        color="#d57932",
    )
    axis.set_yscale("log")
    axis.set_xticks(positions, labels)
    axis.set_ylabel("MAE (source-native target scale; unit undeclared)")
    axis.set_title("WP09 leakage-safe average-MRR model comparison")
    axis.grid(axis="y", which="both", alpha=0.25)
    axis.legend(frameon=False, ncol=2)
    for bars in (test_bars, validation_bars):
        axis.bar_label(bars, fmt="%.2f", padding=2, fontsize=8)
    axis.text(
        0.01,
        0.02,
        "Whole-wafer precedence-retained roles; lower is better",
        transform=axis.transAxes,
        fontsize=8,
        color="#444444",
    )
    figure.tight_layout()
    path = OUTPUT_DIR / "wp09_model_comparison.png"
    save_png_atomic(figure, path)
    return path


def validation_scatter(results: dict[str, Any], predictions: pd.DataFrame) -> Path:
    selection = predictions.loc[
        predictions["ANALYSIS"].eq("PRIMARY_tree")
        & predictions["ROLE"].eq("ORIGINAL:OFFICIAL_VALIDATION_RETAINED")
    ].copy()
    if len(selection) != 275 or set(selection["STAGE"]) != {"A", "B"}:
        raise ValueError("tree validation prediction selection is incomplete")
    metrics = results["primary_original_10s_full_features"]["tree"][
        "OFFICIAL_VALIDATION_RETAINED"
    ]["overall"]

    figure, axis = plt.subplots(figsize=(6.1, 5.4))
    colors = {"A": "#2f6f9f", "B": "#d57932"}
    for stage in ("A", "B"):
        rows = selection.loc[selection["STAGE"].eq(stage)]
        axis.scatter(
            rows["TARGET_NATIVE"],
            rows["PREDICTION_NATIVE"],
            s=23,
            alpha=0.72,
            color=colors[stage],
            edgecolor="none",
            label=f"Stage {stage} (n={len(rows)})",
        )
    minimum = float(
        min(selection["TARGET_NATIVE"].min(), selection["PREDICTION_NATIVE"].min())
    )
    maximum = float(
        max(selection["TARGET_NATIVE"].max(), selection["PREDICTION_NATIVE"].max())
    )
    padding = 0.04 * (maximum - minimum)
    limits = (minimum - padding, maximum + padding)
    axis.plot(limits, limits, linestyle="--", color="#333333", linewidth=1.2)
    axis.set_xlim(limits)
    axis.set_ylim(limits)
    axis.set_aspect("equal", adjustable="box")
    axis.set_xlabel("Measured average MRR (source-native; unit undeclared)")
    axis.set_ylabel("Predicted average MRR (same source-native scale)")
    axis.set_title("Tree model: retained final validation")
    axis.grid(alpha=0.20)
    axis.legend(frameon=False)
    axis.text(
        0.03,
        0.96,
        f"MAE={metrics['mae']:.3f}\n$R^2$={metrics['r2']:.3f}",
        transform=axis.transAxes,
        va="top",
        fontsize=9,
        bbox={"facecolor": "white", "edgecolor": "#bbbbbb", "alpha": 0.9},
    )
    figure.tight_layout()
    path = OUTPUT_DIR / "wp09_tree_validation_scatter.png"
    save_png_atomic(figure, path)
    return path


def robustness_summary(results: dict[str, Any]) -> Path:
    test_role = "OFFICIAL_TEST_RETAINED"
    validation_role = "OFFICIAL_VALIDATION_RETAINED"
    primary = results["primary_original_10s_full_features"]["tree"]
    variants: list[tuple[str, dict[str, Any], dict[str, Any]]] = [
        ("Primary\n10 s full", primary[test_role], primary[validation_role]),
    ]
    label_results = results["label_policy_sensitivities"]
    variants.extend(
        [
            (
                "Exclude four\ntraining labels",
                label_results["EXCLUDE_FOUR_PREREGISTERED"]["tree"][test_role],
                label_results["EXCLUDE_FOUR_PREREGISTERED"]["tree"][validation_role],
            ),
            (
                "Hypothetical\n/60 labels",
                label_results["HYPOTHETICAL_DIVIDE_FOUR_BY_60"]["tree"][test_role],
                label_results["HYPOTHETICAL_DIVIDE_FOUR_BY_60"]["tree"][validation_role],
            ),
        ]
    )
    gap_results = results["gap_threshold_sensitivities"]
    variants.extend(
        [
            (
                "5 s gap",
                gap_results["5.0"]["models"]["tree"][test_role],
                gap_results["5.0"]["models"]["tree"][validation_role],
            ),
            (
                "20 s gap",
                gap_results["20.0"]["models"]["tree"][test_role],
                gap_results["20.0"]["models"]["tree"][validation_role],
            ),
        ]
    )
    proxy_results = results["proxy_missing_mode_ablation"]
    variants.extend(
        [
            (
                "Active-only\nfeatures",
                proxy_results["ACTIVE_ONLY"]["tree"][test_role],
                proxy_results["ACTIVE_ONLY"]["tree"][validation_role],
            ),
            (
                "No unresolved\nproxy",
                proxy_results["NO_UNRESOLVED"]["tree"][test_role],
                proxy_results["NO_UNRESOLVED"]["tree"][validation_role],
            ),
        ]
    )
    positions = np.arange(len(variants), dtype=float)
    test_mae = [item[1]["overall"]["mae"] for item in variants]
    validation_mae = [item[2]["overall"]["mae"] for item in variants]
    test_coverage = [item[1]["overall"]["interval_coverage"] for item in variants]
    validation_coverage = [
        item[2]["overall"]["interval_coverage"] for item in variants
    ]

    figure, (mae_axis, coverage_axis) = plt.subplots(
        2,
        1,
        figsize=(10.2, 7.1),
        sharex=True,
        gridspec_kw={"height_ratios": (1.0, 1.0)},
    )
    width = 0.36
    mae_axis.bar(
        positions - width / 2,
        test_mae,
        width,
        label="Retained test",
        color="#2f6f9f",
    )
    mae_axis.bar(
        positions + width / 2,
        validation_mae,
        width,
        label="Retained final validation",
        color="#d57932",
    )
    mae_axis.set_ylabel("MAE (source-native)")
    mae_axis.set_title("Tree-model preregistered sensitivity summary")
    mae_axis.grid(axis="y", alpha=0.25)
    mae_axis.legend(frameon=False, ncol=2)

    coverage_axis.bar(
        positions - width / 2,
        test_coverage,
        width,
        color="#2f6f9f",
    )
    coverage_axis.bar(
        positions + width / 2,
        validation_coverage,
        width,
        color="#d57932",
    )
    coverage_axis.axhline(
        0.90,
        color="#333333",
        linestyle="--",
        linewidth=1.1,
        label="Nominal 90%",
    )
    coverage_axis.axhline(
        0.85,
        color="#a22c29",
        linestyle=":",
        linewidth=1.4,
        label="Frozen interpretation floor",
    )
    coverage_axis.set_ylim(0.80, 0.92)
    coverage_axis.set_ylabel("Empirical interval coverage")
    coverage_axis.set_xticks(positions, [item[0] for item in variants])
    coverage_axis.grid(axis="y", alpha=0.25)
    coverage_axis.legend(frameon=False, ncol=2, loc="lower right")
    figure.tight_layout()
    path = OUTPUT_DIR / "wp09_tree_sensitivity.png"
    save_png_atomic(figure, path)
    return path


def write_manifest(paths: list[Path]) -> None:
    payload = {
        "schema_version": "1.0.0",
        "evidence_plane": "PUBLIC_PHM_SOURCE_NATIVE_OFFLINE_AVERAGE_MRR",
        "inputs": {
            str(RESULTS_PATH.relative_to(ROOT)): sha256_file(RESULTS_PATH),
            str(PREDICTIONS_PATH.relative_to(ROOT)): sha256_file(PREDICTIONS_PATH),
        },
        "outputs": {
            str(path.relative_to(ROOT)): sha256_file(path) for path in paths
        },
        "claim_boundary": (
            "Offline precedence-retained PHM average-MRR evidence in an "
            "undeclared source-native target scale; no SI, real-fab, physical-defect, "
            "yield, causal-utility, or control-efficacy claim."
        ),
    }
    temporary = MANIFEST_PATH.with_suffix(MANIFEST_PATH.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, MANIFEST_PATH)


def main() -> int:
    results, predictions = load_evidence()
    paths = [
        model_comparison(results),
        validation_scatter(results, predictions),
        robustness_summary(results),
    ]
    write_manifest(paths)
    print(
        json.dumps(
            {
                "manifest": str(MANIFEST_PATH.relative_to(ROOT)),
                "figures": [str(path.relative_to(ROOT)) for path in paths],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
