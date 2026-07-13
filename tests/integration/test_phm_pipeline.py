from pathlib import Path

import pytest

from semifab_poc.data.phm_cmp import (
    join_training_labels,
    load_phm_dataset,
    missingness_report,
    split_training_features,
)
from semifab_poc.data.phm_semantics import (
    LabelAnomalyPolicy,
    apply_training_label_policy,
    build_official_feature_sets,
    join_group_labels,
    semantic_audit_report,
)
from semifab_poc.data.splits import (
    audit_fit_scope,
    chronological_group_split,
    official_group_precedence_split,
    physical_machine_holdout_feasibility,
)


@pytest.fixture(scope="module")
def dataset():
    return load_phm_dataset(Path("data/raw/phm_2016_cmp"), verify_checksums=True)


@pytest.fixture(scope="module")
def official_features(dataset):
    return build_official_feature_sets(dataset)


def test_loader_preserves_all_splits_and_empty_traces(dataset) -> None:
    assert len(dataset.training_timeseries) > 0
    assert len(dataset.test_timeseries) > 0
    assert len(dataset.validation_timeseries) > 0
    assert dataset.trace_inventory.shape[0] == 555
    assert int(dataset.trace_inventory["EMPTY_TRACE"].sum()) == 58
    assert dataset.training_labels.shape == (1981, 5)
    assert dataset.test_labels.shape == (424, 5)
    assert dataset.validation_labels.shape == (424, 5)


def test_training_join_is_many_to_one_and_holdout_labels_are_separate(dataset) -> None:
    result = join_training_labels(dataset)
    assert result.audit["join_validation"] == "many_to_one"
    assert result.audit["missing_label_key_count"] == 0
    assert result.audit["test_and_validation_labels_joined"] is False
    assert result.frame["AVG_REMOVAL_RATE"].notna().all()


def test_missingness_report_and_grouped_feature_split(dataset, official_features) -> None:
    report = missingness_report(dataset)
    assert report["empty_trace_count"] == 58
    assert set(report["splits"]) == {"training", "test", "validation"}
    features = join_group_labels(
        official_features.training, dataset.training_labels, split="training"
    ).frame
    assert len(features) == 1981
    split = split_training_features(features, random_state=17)
    assert split.audit().leakage_free
    assert sum(split.audit().row_counts.values()) == len(features)


def test_phase_aware_features_keep_official_splits_isolated(dataset, official_features) -> None:
    expected = {"training": 1981, "test": 424, "validation": 424}
    for split_name in ("training", "test", "validation"):
        feature_result = getattr(official_features, split_name)
        labels = getattr(dataset, f"{split_name}_labels")
        joined = join_group_labels(feature_result, labels, split=split_name)
        assert len(feature_result.frame) == expected[split_name]
        assert joined.audit["missing_label_key_count"] == 0
        assert joined.audit["orphan_label_key_count"] == 0
        assert "META_GROUP_START_TIMESTAMP" not in feature_result.predictor_columns
        assert feature_result.audit["absolute_timestamp_is_predictor"] is False


def test_official_features_require_wafer_precedence_for_independent_holdouts(
    official_features,
) -> None:
    result = official_group_precedence_split(
        official_features.training.frame,
        official_features.test.frame,
        official_features.validation.frame,
        ["WAFER_ID"],
    )
    assert result.audit.original_overlap_counts == {
        "training_test": 113,
        "training_validation": 115,
        "test_validation": 34,
    }
    assert result.audit.retained_row_counts == {
        "training": 1981,
        "test": 311,
        "validation": 275,
    }
    assert result.audit.retained_group_counts == {
        "training": 1699,
        "test": 302,
        "validation": 267,
    }
    assert result.test["STAGE"].value_counts().sort_index().to_dict() == {
        "A": 190,
        "B": 121,
    }
    assert result.validation["STAGE"].value_counts().sort_index().to_dict() == {
        "A": 169,
        "B": 106,
    }
    assert result.audit.leakage_free


def test_real_data_semantic_audit_records_known_timing_and_regime_limits(dataset) -> None:
    report = semantic_audit_report(dataset)
    training = report["splits"]["training"]
    assert training["zero_timestamp_increment_count"] == 2221
    assert training["negative_timestamp_increment_count"] == 3
    assert training["long_gap_count"] == 2004
    assert training["unresolved_wafer_stage_group_count"] == 221
    assert [
        (row["trace_id"], row["source_row_index"], row["delta_from_previous_s"])
        for row in training["negative_timestamp_increment_rows"]
    ] == [
        ("CMP-training-067", 1044, -6.0),
        ("CMP-training-073", 1625, -2804.0),
        ("CMP-training-073", 1796, -2820.0),
    ]
    assert report["splits"]["test"]["negative_timestamp_increment_count"] == 0
    assert report["splits"]["validation"]["negative_timestamp_increment_count"] == 2
    assert report["machine_split_evidence"]["physical_machine_holdout_feasible"] is False
    assert report["machine_split_evidence"]["machine_data_holdout_feasible"] is False
    assert report["machine_split_evidence"]["machine_data_multi_value_wafer_stage_groups"] == {
        "training": 1979,
        "test": 424,
        "validation": 424,
    }
    assert report["training_label_anomalies"]["count"] == 4
    assert report["training_label_anomalies"]["primary_policy"] == "ORIGINAL"
    precedence = report["official_wafer_precedence_evidence"]
    assert precedence["original_overlap_counts"] == {
        "training_test": 113,
        "training_validation": 115,
        "test_validation": 34,
    }
    assert precedence["retained_row_counts"] == {
        "training": 1981,
        "test": 311,
        "validation": 275,
    }
    assert precedence["leakage_free"] is True


def test_actual_label_policies_and_training_only_fit_scope(dataset, official_features) -> None:
    original = apply_training_label_policy(
        dataset.training_labels, LabelAnomalyPolicy.ORIGINAL
    )
    excluded = apply_training_label_policy(
        dataset.training_labels, LabelAnomalyPolicy.EXCLUDE_FOUR_PREREGISTERED
    )
    divided = apply_training_label_policy(
        dataset.training_labels, LabelAnomalyPolicy.HYPOTHETICAL_DIVIDE_FOUR_BY_60
    )
    assert len(original.frame) == 1981
    assert len(excluded.frame) == 1977
    assert divided.frame["AVG_REMOVAL_RATE"].max() < 200.0

    training = official_features.training.frame
    chronological = chronological_group_split(
        training, ["WAFER_ID"], "META_GROUP_START_TIMESTAMP"
    )
    assert chronological.audit().leakage_free
    assert audit_fit_scope(chronological.train, chronological).training_only
    feasibility = physical_machine_holdout_feasibility(training)
    assert feasibility["values"] == ["2"]
