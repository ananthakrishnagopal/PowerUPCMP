"""Phase-aware, native-unit semantics for the PHM 2016 CMP dataset."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Any

import numpy as np
import pandas as pd

from .phm_cmp import LabelJoinResult, PhmDataError, PhmDataset, TIMESERIES_COLUMNS
from .splits import official_group_precedence_split


TRACE_GROUP_COLUMNS = ("TRACE_ID", "WAFER_ID", "STAGE")
FEATURE_GROUP_COLUMNS = ("WAFER_ID", "STAGE")
PRESSURE_COLUMNS = (
    "PRESSURIZED_CHAMBER_PRESSURE",
    "MAIN_OUTER_AIR_BAG_PRESSURE",
    "CENTER_AIR_BAG_PRESSURE",
    "RETAINER_RING_PRESSURE",
    "RIPPLE_AIR_BAG_PRESSURE",
    "EDGE_AIR_BAG_PRESSURE",
)
SLURRY_COLUMNS = ("SLURRY_FLOW_LINE_A", "SLURRY_FLOW_LINE_B", "SLURRY_FLOW_LINE_C")
PROCESS_ROTATION_COLUMNS = ("WAFER_ROTATION", "STAGE_ROTATION")
PROCESS_SIGNAL_COLUMNS = tuple(
    column
    for column in TIMESERIES_COLUMNS
    if column
    not in {
        "MACHINE_ID",
        "MACHINE_DATA",
        "TIMESTAMP",
        "WAFER_ID",
        "STAGE",
        "CHAMBER",
    }
)


class ProcessModeProxy(str, Enum):
    PREPARE = "PREPARE_PROXY"
    ACTIVE_POLISH = "ACTIVE_POLISH_PROXY"
    TRANSITION_WITHIN_POLISH = "TRANSITION_WITHIN_POLISH_PROXY"
    ENDING_OR_CLEANING = "ENDING_OR_CLEANING_PROXY"
    UNRESOLVED = "UNRESOLVED_PROXY"


class LabelAnomalyPolicy(str, Enum):
    ORIGINAL = "ORIGINAL"
    EXCLUDE_FOUR_PREREGISTERED = "EXCLUDE_FOUR_PREREGISTERED"
    HYPOTHETICAL_DIVIDE_FOUR_BY_60 = "HYPOTHETICAL_DIVIDE_FOUR_BY_60"


PREREGISTERED_LABEL_ANOMALIES: dict[tuple[str, str], float] = {
    ("2058207580", "A"): 4326.15405,
    ("1834206730", "A"): 4202.11245,
    ("1834206944", "A"): 4182.41655,
    ("1834206972", "A"): 4129.49400,
}


@dataclass(frozen=True)
class FeatureEngineeringResult:
    frame: pd.DataFrame
    predictor_columns: tuple[str, ...]
    metadata_columns: tuple[str, ...]
    audit: dict[str, Any]


@dataclass(frozen=True)
class LabelPolicyResult:
    frame: pd.DataFrame
    audit: dict[str, Any]


@dataclass(frozen=True)
class OfficialFeatureSets:
    training: FeatureEngineeringResult
    test: FeatureEngineeringResult
    validation: FeatureEngineeringResult


def _require_columns(frame: pd.DataFrame, columns: tuple[str, ...]) -> None:
    missing = sorted(set(columns) - set(frame.columns))
    if missing:
        raise PhmDataError(f"PHM semantic frame missing columns: {missing}")


def annotate_trace_semantics(
    frame: pd.DataFrame,
    *,
    gap_threshold_s: float = 10.0,
) -> pd.DataFrame:
    """Add source-order timing, continuity, support weights, and mode proxies.

    The function uses process inputs only. It never reads an MRR target.
    """

    if not math.isfinite(gap_threshold_s) or gap_threshold_s <= 0.0:
        raise PhmDataError("gap_threshold_s must be finite and positive")
    required = TRACE_GROUP_COLUMNS + (
        "SOURCE_ROW_INDEX",
        "TIMESTAMP",
        "HEAD_ROTATION",
    ) + PRESSURE_COLUMNS + SLURRY_COLUMNS + PROCESS_ROTATION_COLUMNS
    _require_columns(frame, required)
    if "AVG_REMOVAL_RATE" in frame.columns:
        raise PhmDataError("phase annotation must not receive the MRR target")

    result = frame.copy()
    result["_INPUT_ORDER"] = np.arange(len(result), dtype=np.int64)
    result = result.sort_values(
        [*TRACE_GROUP_COLUMNS, "SOURCE_ROW_INDEX"], kind="mergesort"
    ).reset_index(drop=True)
    timestamps = pd.to_numeric(result["TIMESTAMP"], errors="coerce")
    if not np.isfinite(timestamps.to_numpy(dtype=float)).all():
        raise PhmDataError("TIMESTAMP must contain finite numeric values")
    result["TIMESTAMP"] = timestamps

    trace_groups = result.groupby(list(TRACE_GROUP_COLUMNS), sort=False, dropna=False)
    delta_previous = trace_groups["TIMESTAMP"].diff()
    delta_next = trace_groups["TIMESTAMP"].shift(-1) - result["TIMESTAMP"]
    result["TIMESTAMP_DELTA_FROM_PREVIOUS_S"] = delta_previous
    result["DUPLICATE_TIMESTAMP"] = delta_previous.eq(0.0)
    result["NEGATIVE_TIMESTAMP_INCREMENT"] = delta_previous.lt(0.0)
    result["LONG_GAP_BEFORE"] = delta_previous.gt(gap_threshold_s)

    first_in_trace_group = trace_groups.cumcount().eq(0)
    segment_boundary = (
        first_in_trace_group
        | result["NEGATIVE_TIMESTAMP_INCREMENT"]
        | result["LONG_GAP_BEFORE"]
    )
    result["CONTINUITY_SEGMENT_INDEX"] = (
        segment_boundary.groupby(
            [result[column] for column in TRACE_GROUP_COLUMNS], sort=False, dropna=False
        ).cumsum()
        - 1
    ).astype(int)

    valid_previous = delta_previous.where(
        delta_previous.gt(0.0) & delta_previous.le(gap_threshold_s), 0.0
    ).fillna(0.0)
    valid_next = delta_next.where(
        delta_next.gt(0.0) & delta_next.le(gap_threshold_s), 0.0
    ).fillna(0.0)
    result["TIME_WEIGHT_S"] = 0.5 * valid_previous + 0.5 * valid_next

    pressure_on = result.loc[:, PRESSURE_COLUMNS].abs().max(axis=1).gt(0.0)
    slurry_on = result.loc[:, SLURRY_COLUMNS].abs().max(axis=1).gt(0.0)
    process_rotation_on = (
        result.loc[:, PROCESS_ROTATION_COLUMNS].abs().max(axis=1).gt(0.0)
    )
    head_rotation_on = result["HEAD_ROTATION"].abs().gt(0.0)
    active_candidate = pressure_on & slurry_on & process_rotation_on & head_rotation_on
    result["ACTIVE_POLISH_CANDIDATE"] = active_candidate

    segment_columns = [*TRACE_GROUP_COLUMNS, "CONTINUITY_SEGMENT_INDEX"]
    segment_groups = result.groupby(segment_columns, sort=False, dropna=False)
    result["_SEGMENT_ROW_INDEX"] = segment_groups.cumcount()
    active_position = result["_SEGMENT_ROW_INDEX"].where(active_candidate)
    grouped_positions = active_position.groupby(
        [result[column] for column in segment_columns], sort=False, dropna=False
    )
    first_active = grouped_positions.transform("min")
    last_active = grouped_positions.transform("max")
    has_active = first_active.notna()
    row_position = result["_SEGMENT_ROW_INDEX"]
    result["PROCESS_MODE_PROXY"] = np.select(
        [
            ~has_active,
            active_candidate,
            row_position.lt(first_active),
            row_position.gt(last_active),
        ],
        [
            ProcessModeProxy.UNRESOLVED.value,
            ProcessModeProxy.ACTIVE_POLISH.value,
            ProcessModeProxy.PREPARE.value,
            ProcessModeProxy.ENDING_OR_CLEANING.value,
        ],
        default=ProcessModeProxy.TRANSITION_WITHIN_POLISH.value,
    )

    result = result.sort_values("_INPUT_ORDER", kind="mergesort")
    return result.drop(columns=["_INPUT_ORDER", "_SEGMENT_ROW_INDEX"]).reset_index(drop=True)


def _unique_or_multiple(series: pd.Series) -> str:
    values = sorted({str(value) for value in series.dropna()})
    if not values:
        return "MISSING"
    return values[0] if len(values) == 1 else "MULTIPLE"


def engineer_phase_aware_features(
    timeseries: pd.DataFrame,
    *,
    gap_threshold_s: float = 10.0,
) -> FeatureEngineeringResult:
    """Create one native-unit, offline-VM feature row per wafer and stage."""

    if "AVG_REMOVAL_RATE" in timeseries.columns:
        raise PhmDataError("feature engineering requires labels to remain separate")
    annotated = annotate_trace_semantics(timeseries, gap_threshold_s=gap_threshold_s)
    keys = list(FEATURE_GROUP_COLUMNS)
    groups = annotated.groupby(keys, sort=True, dropna=False)
    base = groups.size().rename("ROW_COUNT").to_frame()
    base["META_TRACE_COUNT"] = groups["TRACE_ID"].nunique()
    segment_key = (
        annotated["TRACE_ID"].astype(str)
        + "#"
        + annotated["CONTINUITY_SEGMENT_INDEX"].astype(str)
    )
    segment_frame = annotated.loc[:, keys].copy()
    segment_frame["SEGMENT_KEY"] = segment_key
    base["META_CONTINUITY_SEGMENT_COUNT"] = segment_frame.groupby(keys)[
        "SEGMENT_KEY"
    ].nunique()
    base["META_GROUP_START_TIMESTAMP"] = groups["TIMESTAMP"].min()
    base["META_GROUP_END_TIMESTAMP"] = groups["TIMESTAMP"].max()
    base["META_MACHINE_ID"] = groups["MACHINE_ID"].agg(_unique_or_multiple)
    base["META_MACHINE_DATA"] = groups["MACHINE_DATA"].agg(_unique_or_multiple)
    base["META_CHAMBER"] = groups["CHAMBER"].agg(_unique_or_multiple)
    base["META_MACHINE_ID_NUNIQUE"] = groups["MACHINE_ID"].nunique()
    base["META_MACHINE_DATA_NUNIQUE"] = groups["MACHINE_DATA"].nunique()
    base["META_CHAMBER_NUNIQUE"] = groups["CHAMBER"].nunique()
    base["DUPLICATE_TIMESTAMP_COUNT"] = groups["DUPLICATE_TIMESTAMP"].sum()
    base["NEGATIVE_TIMESTAMP_INCREMENT_COUNT"] = groups[
        "NEGATIVE_TIMESTAMP_INCREMENT"
    ].sum()
    base["LONG_GAP_COUNT"] = groups["LONG_GAP_BEFORE"].sum()
    total_support = groups["TIME_WEIGHT_S"].sum()
    base["TOTAL_SUPPORTED_DURATION_S"] = total_support

    feature_blocks: list[pd.DataFrame] = []
    for mode in ProcessModeProxy:
        mode_prefix = mode.value
        mode_rows = annotated.loc[annotated["PROCESS_MODE_PROXY"] == mode.value]
        mode_groups = mode_rows.groupby(keys, sort=True, dropna=False)
        row_count = mode_groups.size().reindex(base.index, fill_value=0)
        duration = mode_groups["TIME_WEIGHT_S"].sum().reindex(base.index, fill_value=0.0)
        coverage = pd.DataFrame(
            {
                f"{mode_prefix}__ROW_COUNT": row_count,
                f"{mode_prefix}__ROW_FRACTION": row_count / base["ROW_COUNT"],
                f"{mode_prefix}__DURATION_S": duration,
                f"{mode_prefix}__DURATION_FRACTION": np.where(
                    total_support.gt(0.0), duration / total_support, 0.0
                ),
            },
            index=base.index,
        )
        feature_blocks.append(coverage)

        supported = mode_rows.loc[mode_rows["TIME_WEIGHT_S"] > 0.0]
        if supported.empty:
            empty_columns = [
                f"{mode_prefix}__{signal}__{statistic}"
                for signal in PROCESS_SIGNAL_COLUMNS
                for statistic in ("TW_MEAN", "TW_STD", "MIN", "MAX")
            ]
            feature_blocks.append(pd.DataFrame(np.nan, index=base.index, columns=empty_columns))
            continue
        supported_groups = supported.groupby(keys, sort=True, dropna=False)
        weights = supported["TIME_WEIGHT_S"]
        weight_sum = supported_groups["TIME_WEIGHT_S"].sum()

        weighted = supported.loc[:, PROCESS_SIGNAL_COLUMNS].mul(weights, axis=0)
        weighted_squared = supported.loc[:, PROCESS_SIGNAL_COLUMNS].pow(2).mul(weights, axis=0)
        for column in keys:
            weighted[column] = supported[column]
            weighted_squared[column] = supported[column]
        sum_wx = weighted.groupby(keys, sort=True, dropna=False)[
            list(PROCESS_SIGNAL_COLUMNS)
        ].sum(min_count=1)
        sum_wx2 = weighted_squared.groupby(keys, sort=True, dropna=False)[
            list(PROCESS_SIGNAL_COLUMNS)
        ].sum(min_count=1)
        means = sum_wx.div(weight_sum, axis=0)
        variances = sum_wx2.div(weight_sum, axis=0) - means.pow(2)
        standard_deviations = variances.clip(lower=0.0).pow(0.5)
        minimums = supported_groups[list(PROCESS_SIGNAL_COLUMNS)].min()
        maximums = supported_groups[list(PROCESS_SIGNAL_COLUMNS)].max()

        statistics = pd.concat(
            {
                "TW_MEAN": means,
                "TW_STD": standard_deviations,
                "MIN": minimums,
                "MAX": maximums,
            },
            axis=1,
        ).reindex(base.index)
        statistics.columns = [
            f"{mode_prefix}__{signal}__{statistic}"
            for statistic, signal in statistics.columns
        ]
        feature_blocks.append(statistics)

    frame = pd.concat([base, *feature_blocks], axis=1).reset_index()
    metadata_columns = tuple(
        column
        for column in frame.columns
        if column in FEATURE_GROUP_COLUMNS or column.startswith("META_")
    )
    predictor_columns = tuple(
        column for column in frame.columns if column not in metadata_columns
    )
    unresolved_groups = int(
        (frame[f"{ProcessModeProxy.ACTIVE_POLISH.value}__ROW_COUNT"] == 0).sum()
    )
    audit = {
        "feature_contract": "PHM_PHASE_AWARE_OFFLINE_VM_V1",
        "gap_threshold_s": gap_threshold_s,
        "group_columns": list(FEATURE_GROUP_COLUMNS),
        "group_count": int(len(frame)),
        "predictor_column_count": len(predictor_columns),
        "metadata_columns": list(metadata_columns),
        "absolute_timestamp_is_predictor": False,
        "unresolved_group_count": unresolved_groups,
        "process_mode_values": [mode.value for mode in ProcessModeProxy],
        "spatial_or_defect_claim": False,
    }
    return FeatureEngineeringResult(frame, predictor_columns, metadata_columns, audit)


def join_group_labels(
    features: FeatureEngineeringResult,
    labels: pd.DataFrame,
    *,
    split: str,
) -> LabelJoinResult:
    """Join labels after feature construction for offline evaluation only."""

    _require_columns(labels, ("WAFER_ID", "STAGE", "AVG_REMOVAL_RATE"))
    keys = list(FEATURE_GROUP_COLUMNS)
    label_view = labels.loc[:, keys + ["AVG_REMOVAL_RATE"]]
    if label_view.duplicated(keys).any():
        raise PhmDataError(f"duplicate {split} label keys")
    feature_keys = features.frame.loc[:, keys]
    missing = feature_keys.merge(label_view.loc[:, keys], on=keys, how="left", indicator=True)
    missing_count = int((missing["_merge"] == "left_only").sum())
    orphan = label_view.loc[:, keys].merge(feature_keys, on=keys, how="left", indicator=True)
    orphan_count = int((orphan["_merge"] == "left_only").sum())
    if missing_count:
        raise PhmDataError(f"{split} feature keys without labels: {missing_count}")
    joined = features.frame.merge(label_view, on=keys, how="left", validate="one_to_one")
    return LabelJoinResult(
        joined,
        {
            "split": split,
            "join_stage": "after_feature_engineering",
            "join_validation": "one_to_one",
            "feature_key_count": int(len(feature_keys)),
            "label_key_count": int(len(label_view)),
            "missing_label_key_count": missing_count,
            "orphan_label_key_count": orphan_count,
        },
    )


def build_official_feature_sets(
    dataset: PhmDataset,
    *,
    gap_threshold_s: float = 10.0,
) -> OfficialFeatureSets:
    """Engineer each official split independently without label access."""

    return OfficialFeatureSets(
        training=engineer_phase_aware_features(
            dataset.training_timeseries, gap_threshold_s=gap_threshold_s
        ),
        test=engineer_phase_aware_features(
            dataset.test_timeseries, gap_threshold_s=gap_threshold_s
        ),
        validation=engineer_phase_aware_features(
            dataset.validation_timeseries, gap_threshold_s=gap_threshold_s
        ),
    )


def apply_training_label_policy(
    labels: pd.DataFrame,
    policy: LabelAnomalyPolicy,
) -> LabelPolicyResult:
    """Apply one preregistered training-label treatment with an exact audit."""

    _require_columns(labels, ("WAFER_ID", "STAGE", "AVG_REMOVAL_RATE"))
    if labels.duplicated(["WAFER_ID", "STAGE"]).any():
        raise PhmDataError("training labels contain duplicate keys")
    result = labels.copy()
    result["AVG_REMOVAL_RATE_RAW"] = result["AVG_REMOVAL_RATE"]
    keys = list(zip(result["WAFER_ID"].astype(str), result["STAGE"].astype(str)))
    index_by_key = {key: index for key, index in zip(keys, result.index)}
    matched_indices: list[Any] = []
    for key, expected in PREREGISTERED_LABEL_ANOMALIES.items():
        if key not in index_by_key:
            raise PhmDataError(f"preregistered anomaly key is missing: {key}")
        index = index_by_key[key]
        observed = float(result.at[index, "AVG_REMOVAL_RATE"])
        if not math.isclose(observed, expected, rel_tol=0.0, abs_tol=1.0e-8):
            raise PhmDataError(
                f"preregistered anomaly value mismatch for {key}: {observed} != {expected}"
            )
        matched_indices.append(index)

    if policy is LabelAnomalyPolicy.EXCLUDE_FOUR_PREREGISTERED:
        result = result.drop(index=matched_indices).copy()
    elif policy is LabelAnomalyPolicy.HYPOTHETICAL_DIVIDE_FOUR_BY_60:
        result.loc[matched_indices, "AVG_REMOVAL_RATE"] = (
            result.loc[matched_indices, "AVG_REMOVAL_RATE"] / 60.0
        )
    elif policy is not LabelAnomalyPolicy.ORIGINAL:
        raise PhmDataError(f"unsupported label anomaly policy: {policy}")

    audit = {
        "policy": policy.value,
        "primary_policy": policy is LabelAnomalyPolicy.ORIGINAL,
        "input_row_count": int(len(labels)),
        "output_row_count": int(len(result)),
        "matched_preregistered_key_count": len(matched_indices),
        "raw_label_preserved": True,
        "holdout_metrics_used_to_select_policy": False,
    }
    return LabelPolicyResult(result.reset_index(drop=True), audit)


def _timestamp_quantiles(delta: pd.Series) -> dict[str, float | None]:
    positive = delta.loc[delta.gt(0.0)]
    if positive.empty:
        return {name: None for name in ("p50", "p90", "p99", "p99_5", "p99_9", "max")}
    probabilities = {"p50": 0.5, "p90": 0.9, "p99": 0.99, "p99_5": 0.995, "p99_9": 0.999, "max": 1.0}
    return {name: float(positive.quantile(probability)) for name, probability in probabilities.items()}


def semantic_audit_report(
    dataset: PhmDataset,
    *,
    gap_threshold_s: float = 10.0,
) -> dict[str, Any]:
    """Return JSON-safe timing, mode, label, and regime evidence."""

    report: dict[str, Any] = {
        "dataset_id": "PHM_2016_CMP",
        "public_target": "AVG_REMOVAL_RATE",
        "original_target_unit_status": "NOT_DECLARED_BY_ORIGINAL_SOURCE",
        "process_signal_units": "PROPRIETARY_SCALED_WITH_HIDDEN_FACTORS",
        "gap_threshold_s": gap_threshold_s,
        "phase_labels_are": "INPUT_ONLY_PROCESS_MODE_PROXIES_NOT_MEASURED_PHASES",
        "absolute_timestamp_is_predictor": False,
        "splits": {},
    }
    all_machine_ids: set[str] = set()
    all_machine_data: set[str] = set()
    for split in ("training", "test", "validation"):
        frame = getattr(dataset, f"{split}_timeseries")
        annotated = annotate_trace_semantics(frame, gap_threshold_s=gap_threshold_s)
        all_machine_ids.update(map(str, annotated["MACHINE_ID"].dropna().unique()))
        all_machine_data.update(map(str, annotated["MACHINE_DATA"].dropna().unique()))
        active_by_group = annotated.groupby(list(FEATURE_GROUP_COLUMNS))[
            "ACTIVE_POLISH_CANDIDATE"
        ].any()
        segment_count = len(
            annotated.loc[
                :,
                [*TRACE_GROUP_COLUMNS, "CONTINUITY_SEGMENT_INDEX"],
            ].drop_duplicates()
        )
        mode_counts = annotated["PROCESS_MODE_PROXY"].value_counts()
        delta = annotated["TIMESTAMP_DELTA_FROM_PREVIOUS_S"]
        negative_rows = annotated.loc[
            annotated["NEGATIVE_TIMESTAMP_INCREMENT"],
            [
                "TRACE_ID",
                "SOURCE_ROW_INDEX",
                "WAFER_ID",
                "STAGE",
                "TIMESTAMP",
                "TIMESTAMP_DELTA_FROM_PREVIOUS_S",
                "CONTINUITY_SEGMENT_INDEX",
            ],
        ]
        report["splits"][split] = {
            "row_count": int(len(annotated)),
            "wafer_stage_group_count": int(len(active_by_group)),
            "continuity_segment_count": int(segment_count),
            "zero_timestamp_increment_count": int(delta.eq(0.0).sum()),
            "negative_timestamp_increment_count": int(delta.lt(0.0).sum()),
            "negative_timestamp_increment_rows": [
                {
                    "trace_id": str(row.TRACE_ID),
                    "source_row_index": int(row.SOURCE_ROW_INDEX),
                    "wafer_id": str(row.WAFER_ID),
                    "stage": str(row.STAGE),
                    "timestamp": float(row.TIMESTAMP),
                    "delta_from_previous_s": float(row.TIMESTAMP_DELTA_FROM_PREVIOUS_S),
                    "continuity_segment_index": int(row.CONTINUITY_SEGMENT_INDEX),
                }
                for row in negative_rows.itertuples(index=False)
            ],
            "long_gap_count": int(delta.gt(gap_threshold_s).sum()),
            "positive_timestamp_increment_quantiles_s": _timestamp_quantiles(delta),
            "mode_row_count": {
                mode.value: int(mode_counts.get(mode.value, 0)) for mode in ProcessModeProxy
            },
            "unresolved_wafer_stage_group_count": int((~active_by_group).sum()),
            "supported_duration_s": float(annotated["TIME_WEIGHT_S"].sum()),
        }

    training_labels = dataset.training_labels
    anomaly_rows = []
    for (wafer_id, stage), expected in PREREGISTERED_LABEL_ANOMALIES.items():
        row = training_labels.loc[
            training_labels["WAFER_ID"].astype(str).eq(wafer_id)
            & training_labels["STAGE"].astype(str).eq(stage)
        ]
        anomaly_rows.append(
            {
                "wafer_id": wafer_id,
                "stage": stage,
                "expected_original": expected,
                "observed_original": float(row.iloc[0]["AVG_REMOVAL_RATE"]) if len(row) == 1 else None,
                "hypothetical_divide_by_60": expected / 60.0,
            }
        )
    report["training_label_anomalies"] = {
        "count": len(anomaly_rows),
        "rows": anomaly_rows,
        "policies": [policy.value for policy in LabelAnomalyPolicy],
        "primary_policy": LabelAnomalyPolicy.ORIGINAL.value,
        "holdout_selection_forbidden": True,
        "maximum_other_training_label": float(
            training_labels.loc[
                ~training_labels.set_index(["WAFER_ID", "STAGE"]).index.isin(
                    PREREGISTERED_LABEL_ANOMALIES
                ),
                "AVG_REMOVAL_RATE",
            ].max()
        ),
    }
    official_group_frames = {
        split: getattr(dataset, f"{split}_timeseries")
        .loc[:, list(FEATURE_GROUP_COLUMNS)]
        .drop_duplicates()
        .reset_index(drop=True)
        for split in ("training", "test", "validation")
    }
    precedence = official_group_precedence_split(
        official_group_frames["training"],
        official_group_frames["test"],
        official_group_frames["validation"],
        ["WAFER_ID"],
    )
    report["official_wafer_precedence_evidence"] = precedence.audit.to_dict()
    training_machine_data_counts = dataset.training_timeseries.groupby(
        list(FEATURE_GROUP_COLUMNS)
    )["MACHINE_DATA"].nunique()
    test_machine_data_counts = dataset.test_timeseries.groupby(
        list(FEATURE_GROUP_COLUMNS)
    )["MACHINE_DATA"].nunique()
    validation_machine_data_counts = dataset.validation_timeseries.groupby(
        list(FEATURE_GROUP_COLUMNS)
    )["MACHINE_DATA"].nunique()
    report["machine_split_evidence"] = {
        "machine_ids": sorted(all_machine_ids),
        "physical_machine_holdout_feasible": len(all_machine_ids) > 1,
        "machine_data_values": sorted(all_machine_data),
        "machine_data_holdout_feasible": False,
        "machine_data_multi_value_wafer_stage_groups": {
            "training": int(training_machine_data_counts.gt(1).sum()),
            "test": int(test_machine_data_counts.gt(1).sum()),
            "validation": int(validation_machine_data_counts.gt(1).sum()),
        },
        "machine_data_interpretation": "DESCRIPTIVE_INPUT_NOT_MACHINE_OR_REGIME_GENERALIZATION",
    }
    return report
