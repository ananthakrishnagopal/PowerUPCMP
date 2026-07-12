import pandas as pd
import pytest

from semifab_poc.data.phm_cmp import PhmDataError, TIMESERIES_COLUMNS
from semifab_poc.data.phm_semantics import (
    LabelAnomalyPolicy,
    ProcessModeProxy,
    annotate_trace_semantics,
    apply_training_label_policy,
    engineer_phase_aware_features,
)


def _row(
    timestamp: float,
    source_row_index: int,
    *,
    active: bool = False,
    slurry_a: float = 1.0,
) -> dict[str, object]:
    row: dict[str, object] = {column: 0.0 for column in TIMESERIES_COLUMNS}
    row.update(
        {
            "MACHINE_ID": "2",
            "MACHINE_DATA": "4",
            "TIMESTAMP": timestamp,
            "WAFER_ID": "wafer-1",
            "STAGE": "A",
            "CHAMBER": "1",
            "HEAD_ROTATION": 100.0,
            "SOURCE_ROW_INDEX": source_row_index,
            "TRACE_ID": "CMP-training-000",
            "SOURCE_MEMBER": "fixture/CMP-training-000.csv",
            "SPLIT": "training",
        }
    )
    if active:
        row["PRESSURIZED_CHAMBER_PRESSURE"] = 10.0
        row["SLURRY_FLOW_LINE_A"] = slurry_a
        row["WAFER_ROTATION"] = 20.0
    return row


def _phase_fixture() -> pd.DataFrame:
    return pd.DataFrame(
        [
            _row(0.0, 0),
            _row(1.0, 1, active=True, slurry_a=2.0),
            _row(2.0, 2),
            _row(3.0, 3, active=True, slurry_a=4.0),
            _row(4.0, 4),
            _row(20.0, 5),
            _row(21.0, 6),
        ]
    )


def test_source_order_gap_segmentation_and_mode_proxies() -> None:
    annotated = annotate_trace_semantics(_phase_fixture(), gap_threshold_s=10.0)
    assert annotated["SOURCE_ROW_INDEX"].tolist() == list(range(7))
    assert annotated["CONTINUITY_SEGMENT_INDEX"].tolist() == [0, 0, 0, 0, 0, 1, 1]
    assert annotated["LONG_GAP_BEFORE"].tolist() == [False, False, False, False, False, True, False]
    assert annotated["PROCESS_MODE_PROXY"].tolist() == [
        ProcessModeProxy.PREPARE.value,
        ProcessModeProxy.ACTIVE_POLISH.value,
        ProcessModeProxy.TRANSITION_WITHIN_POLISH.value,
        ProcessModeProxy.ACTIVE_POLISH.value,
        ProcessModeProxy.ENDING_OR_CLEANING.value,
        ProcessModeProxy.UNRESOLVED.value,
        ProcessModeProxy.UNRESOLVED.value,
    ]
    assert annotated["TIME_WEIGHT_S"].tolist() == pytest.approx(
        [0.5, 1.0, 1.0, 1.0, 0.5, 0.5, 0.5]
    )


def test_duplicate_timestamp_has_no_duplicate_interval_weight() -> None:
    frame = pd.DataFrame([_row(0.0, 0), _row(0.0, 1), _row(1.0, 2)])
    annotated = annotate_trace_semantics(frame)
    assert annotated["DUPLICATE_TIMESTAMP"].tolist() == [False, True, False]
    assert annotated["TIME_WEIGHT_S"].tolist() == pytest.approx([0.0, 0.5, 0.5])


def test_phase_aware_features_are_time_weighted_and_exclude_absolute_time() -> None:
    result = engineer_phase_aware_features(_phase_fixture())
    assert len(result.frame) == 1
    row = result.frame.iloc[0]
    assert row["ACTIVE_POLISH_PROXY__SLURRY_FLOW_LINE_A__TW_MEAN"] == pytest.approx(3.0)
    assert row["ACTIVE_POLISH_PROXY__ROW_COUNT"] == 2
    assert row["UNRESOLVED_PROXY__ROW_COUNT"] == 2
    assert row["TOTAL_SUPPORTED_DURATION_S"] == pytest.approx(5.0)
    assert "META_GROUP_START_TIMESTAMP" in result.metadata_columns
    assert "META_GROUP_START_TIMESTAMP" not in result.predictor_columns
    assert not any(column == "TIMESTAMP" for column in result.predictor_columns)
    assert result.audit["absolute_timestamp_is_predictor"] is False


def test_phase_annotation_and_features_reject_target_input() -> None:
    labeled = _phase_fixture().assign(AVG_REMOVAL_RATE=72.0)
    with pytest.raises(PhmDataError, match="MRR target"):
        annotate_trace_semantics(labeled)
    with pytest.raises(PhmDataError, match="labels to remain separate"):
        engineer_phase_aware_features(labeled)


def _training_labels() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "WAFER_ID": [
                "2058207580",
                "1834206730",
                "1834206944",
                "1834206972",
                "ordinary",
            ],
            "STAGE": ["A", "A", "A", "A", "A"],
            "AVG_REMOVAL_RATE": [4326.15405, 4202.11245, 4182.41655, 4129.49400, 80.0],
        }
    )


def test_all_preregistered_label_policies_preserve_raw_evidence() -> None:
    labels = _training_labels()
    original = apply_training_label_policy(labels, LabelAnomalyPolicy.ORIGINAL)
    excluded = apply_training_label_policy(
        labels, LabelAnomalyPolicy.EXCLUDE_FOUR_PREREGISTERED
    )
    divided = apply_training_label_policy(
        labels, LabelAnomalyPolicy.HYPOTHETICAL_DIVIDE_FOUR_BY_60
    )
    assert len(original.frame) == 5
    assert len(excluded.frame) == 1
    assert divided.frame.loc[0, "AVG_REMOVAL_RATE"] == pytest.approx(4326.15405 / 60.0)
    assert divided.frame.loc[0, "AVG_REMOVAL_RATE_RAW"] == pytest.approx(4326.15405)
    assert original.audit["primary_policy"] is True
    assert divided.audit["holdout_metrics_used_to_select_policy"] is False


def test_label_policy_rejects_unexpected_source_value() -> None:
    labels = _training_labels()
    labels.loc[0, "AVG_REMOVAL_RATE"] = 72.0
    with pytest.raises(PhmDataError, match="value mismatch"):
        apply_training_label_policy(labels, LabelAnomalyPolicy.ORIGINAL)
