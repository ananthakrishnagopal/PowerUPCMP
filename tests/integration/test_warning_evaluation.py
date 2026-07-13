from __future__ import annotations

import warnings
from pathlib import Path

import numpy as np

from scripts.validate_wp12_early_warning import grouped_bootstrap_intervals
from semifab_poc.models.early_warning import (
    WarningDataset,
    evaluate_predictions,
    load_early_warning_config,
)


ROOT = Path(__file__).resolve().parents[2]


def test_warning_metrics_count_alarm_episodes_and_event_lead_time() -> None:
    dataset = WarningDataset(
        feature_names=("x",),
        features=np.zeros((4, 1), dtype=float),
        labels=np.asarray([0, 1, 0, 0], dtype=int),
        run_ids=("event-run", "event-run", "negative-run", "negative-run"),
        split_ids=("TEST", "TEST", "TEST", "TEST"),
        decision_step_indices=np.asarray([1, 2, 1, 2], dtype=int),
        decision_timestamps_s=np.asarray([1.0, 2.0, 1.0, 2.0]),
        first_excursion_timestamps_s=np.asarray([np.nan, 3.0, np.nan, np.nan]),
    )
    probabilities = np.asarray([0.1, 0.8, 0.8, 0.1])
    sets = ((0,), (1,), (0, 1), (0,))
    metrics = evaluate_predictions(
        dataset,
        probabilities,
        sets,
        probability_threshold=0.5,
        horizon_s=3.0,
        decision_period_s=1.0,
        calibration_bins=5,
        latency_s=np.asarray([0.001, 0.001, 0.001, 0.001]),
    )
    assert metrics["event_count"] == 1
    assert metrics["detected_event_count"] == 1
    assert metrics["median_warning_lead_time_s"] == 1.0
    assert metrics["false_alarm_episodes"] == 1
    assert metrics["conformal_coverage"] == 1.0


def test_negative_only_warning_metrics_do_not_assign_pr_auc() -> None:
    dataset = WarningDataset(
        feature_names=("x",),
        features=np.zeros((3, 1), dtype=float),
        labels=np.zeros(3, dtype=int),
        run_ids=("negative-run",) * 3,
        split_ids=("STRUCTURAL_NULL",) * 3,
        decision_step_indices=np.asarray([1, 2, 3], dtype=int),
        decision_timestamps_s=np.asarray([1.0, 2.0, 3.0]),
        first_excursion_timestamps_s=np.full(3, np.nan),
    )
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        metrics = evaluate_predictions(
            dataset,
            np.asarray([0.1, 0.8, 0.9]),
            ((0,), (1,), (1,)),
            probability_threshold=0.5,
            horizon_s=3.0,
            decision_period_s=1.0,
            calibration_bins=5,
        )

    assert caught == []
    assert metrics["positive_count"] == 0
    assert metrics["negative_count"] == 3
    assert metrics["pr_auc"] is None
    assert metrics["specificity"] == 1 / 3
    assert metrics["false_alarm_episodes"] == 1


def test_grouped_bootstrap_keeps_one_class_draws_for_defined_metrics() -> None:
    dataset = WarningDataset(
        feature_names=("x",),
        features=np.zeros((4, 1), dtype=float),
        labels=np.asarray([0, 0, 1, 1], dtype=int),
        run_ids=("negative-run", "negative-run", "event-run", "event-run"),
        split_ids=("TEST",) * 4,
        decision_step_indices=np.asarray([1, 2, 1, 2], dtype=int),
        decision_timestamps_s=np.asarray([0.0, 1.0, 0.0, 1.0]),
        first_excursion_timestamps_s=np.asarray([np.nan, np.nan, 2.0, 2.0]),
    )
    config = load_early_warning_config(
        ROOT / "configs" / "models" / "early_warning.yaml"
    )
    repetitions = 100
    config = config.model_copy(
        update={
            "evaluation": config.evaluation.model_copy(
                update={"grouped_bootstrap_repetitions": repetitions}
            )
        }
    )
    intervals = grouped_bootstrap_intervals(
        dataset,
        np.asarray([0.1, 0.1, 0.9, 0.9]),
        ((0,), (0,), (1,), (1,)),
        np.full(4, 1.0e-6),
        config,
    )

    assert intervals["conformal_coverage"]["valid_repetitions"] == repetitions
    assert intervals["brier_score"]["valid_repetitions"] == repetitions
    assert 0 < intervals["pr_auc"]["valid_repetitions"] < repetitions
