"""Leakage-safe synthetic early warning for future active-polish MRR excursions.

The module implements the frozen Predictor 1.0 contract without importing or
mutating plant components. Future simulator truth is used only by the offline
label generator; online features consume arrived ``ObservationRecord`` values.
"""

from __future__ import annotations

import hashlib
import json
import math
import pickle
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from semifab_poc.data.schema import ObservationRecord


class EarlyWarningError(ValueError):
    """Raised when warning configuration, data, or artifact state is invalid."""


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, validate_assignment=True)


class TargetConfig(_StrictModel):
    target_id: str = Field(min_length=1)
    lower_relative_fraction: float = Field(gt=0.0)
    upper_relative_fraction: float = Field(gt=0.0)
    persistence_s: float = Field(gt=0.0)
    horizon_s: float = Field(gt=0.0)
    decision_period_s: float = Field(gt=0.0)
    full_horizon_required: bool
    require_active_polish_opportunity: bool
    pre_onset_only: bool
    reference_policy: str = Field(min_length=1)
    minimum_reference_mrr_m_s: float = Field(gt=0.0)

    @model_validator(mode="after")
    def validate_band(self) -> TargetConfig:
        if self.lower_relative_fraction >= 1.0:
            raise ValueError("lower_relative_fraction must be below one")
        if self.upper_relative_fraction <= 1.0:
            raise ValueError("upper_relative_fraction must exceed one")
        if self.decision_period_s > self.horizon_s:
            raise ValueError("decision_period_s cannot exceed horizon_s")
        return self


class FeatureConfig(_StrictModel):
    short_window_s: float = Field(gt=0.0)
    history_start_s: float = Field(ge=0.0)
    maximum_observation_age_s: float = Field(gt=0.0)
    allowed_signal_ids: tuple[str, ...] = Field(min_length=1)
    statistics: tuple[str, ...] = Field(min_length=1)
    integrated_deficit_signal_ids: tuple[str, ...]
    forbidden_signal_ids: tuple[str, ...]
    include_phase_indicators: bool
    include_time_to_polish_start: bool
    include_known_battery_capacity_and_load: bool

    @model_validator(mode="after")
    def validate_features(self) -> FeatureConfig:
        if len(set(self.allowed_signal_ids)) != len(self.allowed_signal_ids):
            raise ValueError("allowed_signal_ids must be unique")
        if set(self.allowed_signal_ids) & set(self.forbidden_signal_ids):
            raise ValueError("allowed and forbidden signal IDs must be disjoint")
        if not set(self.integrated_deficit_signal_ids) <= set(self.allowed_signal_ids):
            raise ValueError("deficit signals must be included in allowed_signal_ids")
        supported = {
            "latest",
            "age",
            "short_mean",
            "short_min",
            "short_slope",
            "missing_fraction",
            "history_min",
        }
        if set(self.statistics) != supported:
            raise ValueError(f"statistics must contain exactly {sorted(supported)}")
        return self


class SensorEnsembleConfig(_StrictModel):
    sample_period_s: float = Field(gt=0.0)
    delay_s: float = Field(ge=0.0)
    packet_loss_probability: float = Field(ge=0.0, le=1.0)
    timestamp_jitter_std_s: float = Field(ge=0.0)
    noise_by_signal: dict[str, float]

    @model_validator(mode="after")
    def validate_noise(self) -> SensorEnsembleConfig:
        if any(not math.isfinite(value) or value < 0.0 for value in self.noise_by_signal.values()):
            raise ValueError("sensor noise values must be finite and non-negative")
        return self


class SimulationConfig(_StrictModel):
    dt_s: float = Field(gt=0.0)
    duration_s: float = Field(gt=0.0)
    plant_warmup_s: float = Field(ge=0.0)
    dress_end_s: float = Field(gt=0.0)
    polish_start_s: float = Field(gt=0.0)
    full_dress_anchor_start_s: float = Field(ge=0.0)
    full_dress_anchor_end_s: float = Field(gt=0.0)
    topology: str = Field(min_length=1)
    link_strength: float = Field(ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_schedule(self) -> SimulationConfig:
        if not self.dress_end_s < self.polish_start_s < self.duration_s:
            raise ValueError("simulation schedule must satisfy DRESS < POLISH < duration")
        if not (
            self.full_dress_anchor_start_s < self.full_dress_anchor_end_s
            and self.full_dress_anchor_end_s <= self.dress_end_s
        ):
            raise ValueError("full-DRESS anchor must lie inside the DRESS interval")
        if self.dt_s > self.dress_end_s:
            raise ValueError("simulation dt is too large for the process schedule")
        return self


class RunsPerFamilyConfig(_StrictModel):
    training: int = Field(gt=0)
    calibration: int = Field(gt=0)
    conformal_calibration: int = Field(gt=0)
    test: int = Field(gt=0)
    unseen_compound: int = Field(gt=0)
    structural_null: int = Field(gt=0)


class SplitConfig(_StrictModel):
    train_seed_start: int = Field(ge=0)
    calibration_seed_start: int = Field(ge=0)
    conformal_calibration_seed_start: int = Field(ge=0)
    test_seed_start: int = Field(ge=0)
    unseen_compound_seed_start: int = Field(ge=0)
    structural_null_seed_start: int = Field(ge=0)
    runs_per_family: RunsPerFamilyConfig
    primary_families: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_seeds(self) -> SplitConfig:
        starts = {
            self.train_seed_start,
            self.calibration_seed_start,
            self.conformal_calibration_seed_start,
            self.test_seed_start,
            self.unseen_compound_seed_start,
            self.structural_null_seed_start,
        }
        if len(starts) != 6:
            raise ValueError("split seed starts must be distinct")
        return self


class LogisticConfig(_StrictModel):
    c: float = Field(gt=0.0)
    max_iter: int = Field(gt=0)
    class_weight: str


class GradientBoostedConfig(_StrictModel):
    max_iter: int = Field(gt=0)
    learning_rate: float = Field(gt=0.0)
    max_leaf_nodes: int = Field(gt=1)
    min_samples_leaf: int = Field(gt=1)
    l2_regularization: float = Field(ge=0.0)


class ModelConfig(_StrictModel):
    random_seed: int = Field(ge=0)
    probability_threshold: float = Field(gt=0.0, lt=1.0)
    conformal_alpha: float = Field(gt=0.0, lt=1.0)
    calibration_probability_clip: float = Field(gt=0.0, lt=0.5)
    sigmoid_calibration_c: float = Field(gt=0.0)
    logistic: LogisticConfig
    gradient_boosted: GradientBoostedConfig


class TargetSensitivityConfig(_StrictModel):
    relative_deviation_fractions: tuple[float, ...]
    horizon_s: tuple[float, ...]
    persistence_s: tuple[float, ...]


class EvaluationConfig(_StrictModel):
    calibration_bins: int = Field(gt=1)
    observation_robustness_family_positions: tuple[str, ...]
    grouped_bootstrap_repetitions: int = Field(gt=0)
    grouped_bootstrap_seed: int = Field(ge=0)
    useful_pr_auc_margin_over_prevalence: float = Field(ge=0.0, le=1.0)
    useful_minimum_event_recall: float = Field(ge=0.0, le=1.0)
    useful_minimum_median_lead_time_s: float = Field(ge=0.0)
    useful_minimum_conformal_coverage: float = Field(ge=0.0, le=1.0)
    target_sensitivities: TargetSensitivityConfig

    @model_validator(mode="after")
    def validate_observation_robustness_positions(self) -> EvaluationConfig:
        if self.observation_robustness_family_positions != (
            "UPPER_MEDIAN",
            "MAXIMUM",
        ):
            raise ValueError(
                "observation robustness positions must be UPPER_MEDIAN then MAXIMUM"
            )
        return self


class EarlyWarningConfig(_StrictModel):
    schema_version: str = Field(min_length=1)
    experiment_revision: str = Field(min_length=1)
    target: TargetConfig
    features: FeatureConfig
    sensors: SensorEnsembleConfig
    simulation: SimulationConfig
    splits: SplitConfig
    models: ModelConfig
    evaluation: EvaluationConfig

    @model_validator(mode="after")
    def validate_cross_contract(self) -> EarlyWarningConfig:
        if self.schema_version != "1.0.0":
            raise ValueError("only early-warning schema 1.0.0 is supported")
        if set(self.features.allowed_signal_ids) != set(self.sensors.noise_by_signal):
            raise ValueError("each allowed warning signal requires one sensor noise entry")
        if self.target.persistence_s < self.simulation.dt_s:
            raise ValueError("persistence must span at least one simulation step")
        if self.target.horizon_s >= self.simulation.duration_s:
            raise ValueError("horizon must be shorter than the run duration")
        return self


def load_early_warning_config(path: str | Path) -> EarlyWarningConfig:
    """Load strict WP12 configuration without accepting unknown keys."""

    config_path = Path(path)
    try:
        payload = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise EarlyWarningError(f"cannot load early-warning configuration: {exc}") from exc
    if not isinstance(payload, dict):
        raise EarlyWarningError("early-warning configuration root must be a mapping")
    try:
        return EarlyWarningConfig.model_validate(payload)
    except Exception as exc:
        raise EarlyWarningError(f"invalid early-warning configuration: {exc}") from exc


def normalization_for_warning_runtime(
    *,
    scenario_battery_capacity_j: float,
    runtime: Any,
) -> dict[str, tuple[float, float]]:
    """Return the frozen WP12 online feature normalization map."""

    if not math.isfinite(scenario_battery_capacity_j) or scenario_battery_capacity_j <= 0.0:
        raise EarlyWarningError("scenario battery capacity must be finite and positive")
    return {
        "electrical.grid_voltage": (0.0, 1.0),
        "electrical.ups_output_voltage": (0.0, 1.0),
        "electrical.ups_battery_energy": (0.0, scenario_battery_capacity_j),
        "drive.motor_angular_speed": (0.0, runtime.drive.nominal_motor_speed_rad_s),
        "pump.volumetric_flow": (0.0, runtime.pump.reference_flow_m3_s),
        "upw.supply_pressure": (0.0, runtime.upw.nominal_supply_pressure_pa),
        "upw.tool_flow": (0.0, runtime.upw.nominal_tool_demand_m3_s),
        "upw.temperature": (runtime.upw.nominal_temperature_k, 10.0),
    }


def split_conformal_quantile(scores: Sequence[float], alpha: float) -> float:
    """Return the exact finite-sample split-conformal order statistic."""

    values = np.asarray(scores, dtype=float)
    if values.ndim != 1 or len(values) == 0 or not np.all(np.isfinite(values)):
        raise EarlyWarningError("conformal scores must be a non-empty finite vector")
    if not math.isfinite(alpha) or not 0.0 < alpha < 1.0:
        raise EarlyWarningError("conformal alpha must lie strictly within (0, 1)")
    rank = min(len(values), math.ceil((len(values) + 1) * (1.0 - alpha)))
    return float(np.partition(values, rank - 1)[rank - 1])


class CensorReason(str, Enum):
    INCOMPLETE_FUTURE_HORIZON = "INCOMPLETE_FUTURE_HORIZON"
    NO_ACTIVE_POLISH_OPPORTUNITY = "NO_ACTIVE_POLISH_OPPORTUNITY"
    POST_EXCURSION_ONSET = "POST_EXCURSION_ONSET"


@dataclass(frozen=True)
class ExcursionLabel:
    run_id: str
    decision_step_index: int
    decision_timestamp_s: float
    target_id: str
    horizon_s: float
    excursion_within_horizon: bool
    first_excursion_step_index: int | None
    first_excursion_timestamp_s: float | None
    envelope_id: str


@dataclass(frozen=True)
class LabelingResult:
    labels: tuple[ExcursionLabel, ...]
    censor_counts: Mapping[CensorReason, int]
    episode_onset_step_indices: tuple[int, ...]


def _persistent_episode_onsets(
    violation: np.ndarray,
    active_polish: np.ndarray,
    dt_s: float,
    persistence_s: float,
) -> tuple[int, ...]:
    required_steps = max(1, math.ceil(persistence_s / dt_s - 1.0e-12))
    onsets: list[int] = []
    start: int | None = None
    for index, (is_violation, is_active) in enumerate(
        zip(violation, active_polish, strict=True)
    ):
        if bool(is_violation) and bool(is_active):
            if start is None:
                start = index
            if index - start + 1 == required_steps:
                onsets.append(start)
        else:
            start = None
    return tuple(onsets)


def _has_active_opportunity(
    active: np.ndarray,
    start_exclusive: int,
    end_inclusive: int,
    required_steps: int,
) -> bool:
    count = 0
    for value in active[start_exclusive + 1 : end_inclusive + 1]:
        count = count + 1 if bool(value) else 0
        if count >= required_steps:
            return True
    return False


def generate_excursion_labels(
    *,
    run_id: str,
    timestamps_s: Sequence[float],
    true_mrr_m_s: Sequence[float],
    reference_mrr_m_s: Sequence[float],
    process_modes: Sequence[str],
    decision_step_indices: Sequence[int],
    config: TargetConfig,
    trace_step_indices: Sequence[int] | None = None,
) -> LabelingResult:
    """Generate eligible future labels and explicit censor counts offline."""

    timestamps = np.asarray(timestamps_s, dtype=float)
    true_mrr = np.asarray(true_mrr_m_s, dtype=float)
    reference_mrr = np.asarray(reference_mrr_m_s, dtype=float)
    modes = np.asarray(process_modes, dtype=object)
    if not run_id:
        raise EarlyWarningError("run_id must be non-empty")
    if len(timestamps) < 2 or not (
        len(timestamps) == len(true_mrr) == len(reference_mrr) == len(modes)
    ):
        raise EarlyWarningError("truth/reference arrays must have equal length >= 2")
    if not np.all(np.isfinite(timestamps)) or not np.all(np.diff(timestamps) > 0.0):
        raise EarlyWarningError("timestamps must be finite and strictly increasing")
    if not np.all(np.isfinite(true_mrr)) or not np.all(np.isfinite(reference_mrr)):
        raise EarlyWarningError("MRR arrays must be finite")
    trace_steps = (
        np.arange(len(timestamps), dtype=int)
        if trace_step_indices is None
        else np.asarray(trace_step_indices, dtype=int)
    )
    if len(trace_steps) != len(timestamps) or not np.all(np.diff(trace_steps) > 0):
        raise EarlyWarningError("trace step indices must be unique and strictly increasing")
    position_by_step = {int(step): position for position, step in enumerate(trace_steps)}
    dt_values = np.diff(timestamps)
    dt_s = float(np.median(dt_values))
    if not np.allclose(dt_values, dt_s, rtol=0.0, atol=max(1.0e-12, dt_s * 1.0e-9)):
        raise EarlyWarningError("label generation requires a regular time grid")

    active = modes == "POLISH"
    reference_valid = reference_mrr >= config.minimum_reference_mrr_m_s
    below = true_mrr < config.lower_relative_fraction * reference_mrr
    above = true_mrr > config.upper_relative_fraction * reference_mrr
    violation = active & reference_valid & (below | above)
    onsets = _persistent_episode_onsets(violation, active, dt_s, config.persistence_s)
    required_steps = max(1, math.ceil(config.persistence_s / dt_s - 1.0e-12))
    horizon_steps = math.floor(config.horizon_s / dt_s + 1.0e-12)
    envelope_id = (
        f"{config.target_id}:{config.lower_relative_fraction:.6g}:"
        f"{config.upper_relative_fraction:.6g}:{config.persistence_s:.6g}s"
    )

    labels: list[ExcursionLabel] = []
    censor_counts = {reason: 0 for reason in CensorReason}
    for decision_step in decision_step_indices:
        decision_index = position_by_step.get(int(decision_step))
        if decision_index is None:
            raise EarlyWarningError("decision step index is outside the trace")
        end_index = decision_index + horizon_steps
        if config.full_horizon_required and end_index >= len(timestamps):
            censor_counts[CensorReason.INCOMPLETE_FUTURE_HORIZON] += 1
            continue
        end_index = min(end_index, len(timestamps) - 1)
        if config.require_active_polish_opportunity and not _has_active_opportunity(
            active,
            decision_index,
            end_index,
            required_steps,
        ):
            censor_counts[CensorReason.NO_ACTIVE_POLISH_OPPORTUNITY] += 1
            continue
        prior_onset = next((onset for onset in onsets if onset <= decision_index), None)
        if config.pre_onset_only and prior_onset is not None:
            censor_counts[CensorReason.POST_EXCURSION_ONSET] += 1
            continue
        future_onset = next(
            (onset for onset in onsets if decision_index < onset <= end_index),
            None,
        )
        labels.append(
            ExcursionLabel(
                run_id=run_id,
                decision_step_index=int(decision_step),
                decision_timestamp_s=float(timestamps[decision_index]),
                target_id=config.target_id,
                horizon_s=config.horizon_s,
                excursion_within_horizon=future_onset is not None,
                first_excursion_step_index=(
                    None if future_onset is None else int(trace_steps[future_onset])
                ),
                first_excursion_timestamp_s=(
                    None if future_onset is None else float(timestamps[future_onset])
                ),
                envelope_id=envelope_id,
            )
        )
    return LabelingResult(
        tuple(labels),
        censor_counts,
        tuple(int(trace_steps[position]) for position in onsets),
    )


@dataclass(frozen=True)
class WarningObservationWindow:
    run_id: str
    decision_step_index: int
    decision_timestamp_s: float
    observations: tuple[ObservationRecord, ...]
    process_mode: str
    polish_start_s: float
    normalization_by_signal: Mapping[str, tuple[float, float]]
    sensor_sample_period_s: float
    battery_capacity_ratio: float
    ups_load_ratio: float


@dataclass(frozen=True)
class FeatureVector:
    names: tuple[str, ...]
    values: np.ndarray
    feature_cutoff_step_index: int
    feature_cutoff_timestamp_s: float


class StreamingFeatureExtractor:
    """Create causal window and DRESS-history features from arrived records."""

    interface_version = "1.0.0"

    def __init__(self, config: FeatureConfig) -> None:
        self.config = config

    @staticmethod
    def _normalize(value: float, offset_scale: tuple[float, float]) -> float:
        offset, scale = offset_scale
        if not math.isfinite(offset) or not math.isfinite(scale) or scale <= 0.0:
            raise EarlyWarningError("normalization offset/scale must be finite with positive scale")
        return (value - offset) / scale

    def transform(self, window: WarningObservationWindow) -> FeatureVector:
        if not window.run_id or window.decision_step_index < 0:
            raise EarlyWarningError("warning window identity must be valid")
        if not math.isfinite(window.decision_timestamp_s) or window.decision_timestamp_s < 0.0:
            raise EarlyWarningError("decision timestamp must be finite and non-negative")
        if not math.isfinite(window.sensor_sample_period_s) or window.sensor_sample_period_s <= 0.0:
            raise EarlyWarningError("sensor sample period must be finite and positive")
        allowed = set(self.config.allowed_signal_ids)
        forbidden = set(self.config.forbidden_signal_ids)
        records_by_signal: dict[str, list[ObservationRecord]] = {
            signal_id: [] for signal_id in self.config.allowed_signal_ids
        }
        for record in window.observations:
            if record.run_id != window.run_id:
                raise EarlyWarningError("observation run_id does not match the window")
            if record.arrival_timestamp_s > window.decision_timestamp_s + 1.0e-12:
                raise EarlyWarningError("future-arrival observation crossed the feature cutoff")
            if record.signal_id in forbidden:
                raise EarlyWarningError(f"forbidden warning signal supplied: {record.signal_id}")
            if record.signal_id not in allowed:
                raise EarlyWarningError(f"unregistered warning signal supplied: {record.signal_id}")
            if record.source_step_index is None or record.source_timestamp_s is None:
                raise EarlyWarningError("online warning observations require source identity")
            if record.source_step_index > window.decision_step_index:
                raise EarlyWarningError("future source step crossed the feature cutoff")
            records_by_signal[record.signal_id].append(record)

        names: list[str] = []
        values: list[float] = []
        short_start = window.decision_timestamp_s - self.config.short_window_s
        history_start = self.config.history_start_s
        expected_short = max(
            1,
            math.floor(self.config.short_window_s / window.sensor_sample_period_s + 1.0e-12)
            + 1,
        )

        for signal_id in self.config.allowed_signal_ids:
            if signal_id not in window.normalization_by_signal:
                raise EarlyWarningError(f"missing normalization for {signal_id}")
            records = sorted(
                records_by_signal[signal_id],
                key=lambda item: (
                    float(item.source_timestamp_s),
                    item.sample_index,
                ),
            )
            history = [
                record
                for record in records
                if record.source_timestamp_s is not None
                and history_start - 1.0e-12
                <= record.source_timestamp_s
                <= window.decision_timestamp_s + 1.0e-12
            ]
            short = [
                record
                for record in history
                if record.source_timestamp_s is not None
                and record.source_timestamp_s >= short_start - 1.0e-12
            ]
            valid_history = [record for record in history if isinstance(record.value, (int, float))]
            valid_short = [record for record in short if isinstance(record.value, (int, float))]
            normalized_history = np.asarray(
                [
                    self._normalize(float(record.value), window.normalization_by_signal[signal_id])
                    for record in valid_history
                ],
                dtype=float,
            )
            normalized_short = np.asarray(
                [
                    self._normalize(float(record.value), window.normalization_by_signal[signal_id])
                    for record in valid_short
                ],
                dtype=float,
            )
            short_times = np.asarray(
                [float(record.source_timestamp_s) for record in valid_short], dtype=float
            )

            if valid_history:
                latest_record = valid_history[-1]
                latest = float(normalized_history[-1])
                age = window.decision_timestamp_s - float(latest_record.source_timestamp_s)
            else:
                latest = math.nan
                age = 2.0 * self.config.maximum_observation_age_s
            if len(normalized_short) >= 2 and float(np.ptp(short_times)) > 1.0e-12:
                centered_time = short_times - float(np.mean(short_times))
                slope = float(
                    np.dot(centered_time, normalized_short - float(np.mean(normalized_short)))
                    / np.dot(centered_time, centered_time)
                )
            else:
                slope = math.nan
            statistics = {
                "latest": latest,
                "age": age,
                "short_mean": (
                    float(np.mean(normalized_short)) if len(normalized_short) else math.nan
                ),
                "short_min": (
                    float(np.min(normalized_short)) if len(normalized_short) else math.nan
                ),
                "short_slope": slope,
                "missing_fraction": min(
                    1.0,
                    max(0.0, 1.0 - len(valid_short) / expected_short),
                ),
                "history_min": (
                    float(np.min(normalized_history)) if len(normalized_history) else math.nan
                ),
            }
            for statistic in self.config.statistics:
                names.append(f"{signal_id}:{statistic}")
                values.append(float(statistics[statistic]))

            if signal_id in self.config.integrated_deficit_signal_ids:
                if len(normalized_history) >= 2:
                    history_times = np.asarray(
                        [float(record.source_timestamp_s) for record in valid_history], dtype=float
                    )
                    deficit = np.maximum(0.0, 0.95 - normalized_history)
                    area = float(np.trapezoid(deficit, history_times))
                else:
                    area = 0.0
                names.append(f"{signal_id}:history_deficit_area_s")
                values.append(area)

        if self.config.include_phase_indicators:
            for phase in ("DRESS", "PREPARE", "POLISH"):
                names.append(f"phase:{phase}")
                values.append(float(window.process_mode == phase))
        if self.config.include_time_to_polish_start:
            names.append("schedule:time_to_polish_over_horizon")
            values.append(
                max(0.0, window.polish_start_s - window.decision_timestamp_s)
                / max(1.0e-12, window.polish_start_s)
            )
        if self.config.include_known_battery_capacity_and_load:
            for name, value in (
                ("static:battery_capacity_ratio", window.battery_capacity_ratio),
                ("static:ups_load_ratio", window.ups_load_ratio),
            ):
                if not math.isfinite(value) or value < 0.0:
                    raise EarlyWarningError(f"{name} must be finite and non-negative")
                names.append(name)
                values.append(float(value))
        vector = np.asarray(values, dtype=float)
        if len(vector) != len(names):
            raise AssertionError("feature name/value length mismatch")
        return FeatureVector(
            names=tuple(names),
            values=vector,
            feature_cutoff_step_index=window.decision_step_index,
            feature_cutoff_timestamp_s=window.decision_timestamp_s,
        )


@dataclass(frozen=True)
class WarningDataset:
    feature_names: tuple[str, ...]
    features: np.ndarray
    labels: np.ndarray
    run_ids: tuple[str, ...]
    split_ids: tuple[str, ...]
    decision_step_indices: np.ndarray
    decision_timestamps_s: np.ndarray
    first_excursion_timestamps_s: np.ndarray

    def validate(self) -> None:
        rows = len(self.labels)
        if self.features.ndim != 2 or self.features.shape != (rows, len(self.feature_names)):
            raise EarlyWarningError("warning feature matrix shape does not match metadata")
        if not (
            len(self.run_ids)
            == len(self.split_ids)
            == len(self.decision_step_indices)
            == len(self.decision_timestamps_s)
            == len(self.first_excursion_timestamps_s)
            == rows
        ):
            raise EarlyWarningError("warning dataset columns must have equal length")
        if rows == 0 or len(set(self.feature_names)) != len(self.feature_names):
            raise EarlyWarningError("warning dataset must be non-empty with unique features")
        if not set(np.unique(self.labels)) <= {0, 1}:
            raise EarlyWarningError("warning labels must be binary")
        if not np.all(np.isfinite(self.decision_timestamps_s)):
            raise EarlyWarningError("decision timestamps must be finite")
        split_by_group: dict[str, str] = {}
        for run_id, split_id in zip(self.run_ids, self.split_ids, strict=True):
            prior = split_by_group.setdefault(run_id, split_id)
            if prior != split_id:
                raise EarlyWarningError("one run_id cannot cross dataset splits")

    def subset(self, split_id: str) -> WarningDataset:
        self.validate()
        mask = np.asarray([value == split_id for value in self.split_ids], dtype=bool)
        if not np.any(mask):
            raise EarlyWarningError(f"dataset contains no rows for split {split_id!r}")
        indices = np.flatnonzero(mask)
        return WarningDataset(
            feature_names=self.feature_names,
            features=self.features[mask].copy(),
            labels=self.labels[mask].copy(),
            run_ids=tuple(self.run_ids[index] for index in indices),
            split_ids=tuple(self.split_ids[index] for index in indices),
            decision_step_indices=self.decision_step_indices[mask].copy(),
            decision_timestamps_s=self.decision_timestamps_s[mask].copy(),
            first_excursion_timestamps_s=self.first_excursion_timestamps_s[mask].copy(),
        )


class ModelKind(str, Enum):
    PREVALENCE = "PREVALENCE"
    LOGISTIC = "LOGISTIC"
    GRADIENT_BOOSTED = "GRADIENT_BOOSTED"


@dataclass(frozen=True)
class Prediction:
    probability: float
    predicted_excursion: bool
    conformal_prediction_set: tuple[int, ...]
    uncertainty_valid: bool
    feature_cutoff_step_index: int
    feature_cutoff_timestamp_s: float
    latency_s: float


class EarlyWarningPredictor:
    """Calibrated warning predictor conforming to frozen Predictor 1.0."""

    interface_version = "1.0.0"
    artifact_version = "1.0.0"

    def __init__(
        self,
        model_kind: ModelKind,
        feature_config: FeatureConfig,
        model_config: ModelConfig,
    ) -> None:
        self.model_kind = ModelKind(model_kind)
        self.feature_config = feature_config
        self.model_config = model_config
        self.extractor = StreamingFeatureExtractor(feature_config)
        self.feature_names: tuple[str, ...] | None = None
        self.base_model: Any = None
        self.calibrator: Any = None
        self.training_prevalence: float | None = None
        self.conformal_quantile: float | None = None
        self.fit_group_sha256: str | None = None

    @staticmethod
    def _sklearn() -> dict[str, Any]:
        try:
            from sklearn.compose import ColumnTransformer
            from sklearn.ensemble import HistGradientBoostingClassifier
            from sklearn.impute import SimpleImputer
            from sklearn.linear_model import LogisticRegression
            from sklearn.pipeline import Pipeline
            from sklearn.preprocessing import StandardScaler
        except ImportError as exc:
            raise EarlyWarningError(
                "WP12 requires the optional scikit-learn models dependency"
            ) from exc
        return {
            "ColumnTransformer": ColumnTransformer,
            "HistGradientBoostingClassifier": HistGradientBoostingClassifier,
            "SimpleImputer": SimpleImputer,
            "LogisticRegression": LogisticRegression,
            "Pipeline": Pipeline,
            "StandardScaler": StandardScaler,
        }

    @staticmethod
    def _logit(probabilities: np.ndarray, clip: float) -> np.ndarray:
        bounded = np.clip(np.asarray(probabilities, dtype=float), clip, 1.0 - clip)
        return np.log(bounded / (1.0 - bounded)).reshape(-1, 1)

    @staticmethod
    def _balanced_sample_weights(labels: np.ndarray) -> np.ndarray:
        labels = np.asarray(labels, dtype=int)
        counts = np.bincount(labels, minlength=2)
        if np.any(counts == 0):
            raise EarlyWarningError("training labels require both classes")
        total = len(labels)
        weights_by_class = total / (2.0 * counts)
        return weights_by_class[labels]

    @staticmethod
    def _repair_sklearn_pickle_compatibility(model: Any) -> Any:
        """Patch known sklearn minor-version pickle attribute drift."""

        steps = getattr(model, "steps", ())
        estimators = [estimator for _, estimator in steps] if steps else [model]
        for estimator in estimators:
            if (
                estimator.__class__.__name__ == "SimpleImputer"
                and hasattr(estimator, "_fit_dtype")
                and not hasattr(estimator, "_fill_dtype")
            ):
                estimator._fill_dtype = estimator._fit_dtype
        return model

    def _base_probabilities(self, features: np.ndarray) -> np.ndarray:
        if self.training_prevalence is None:
            raise EarlyWarningError("predictor is not fitted")
        if self.model_kind is ModelKind.PREVALENCE:
            return np.full(len(features), self.training_prevalence, dtype=float)
        if self.base_model is None:
            raise EarlyWarningError("base model is not fitted")
        return np.asarray(self.base_model.predict_proba(features)[:, 1], dtype=float)

    def _calibrated_probabilities(self, features: np.ndarray) -> np.ndarray:
        if self.calibrator is None:
            raise EarlyWarningError("probability calibrator is not fitted")
        base = self._base_probabilities(features)
        logits = self._logit(base, self.model_config.calibration_probability_clip)
        return np.asarray(self.calibrator.predict_proba(logits)[:, 1], dtype=float)

    def fit(self, dataset: WarningDataset) -> EarlyWarningPredictor:
        """Fit on disjoint base, probability-calibration, and conformal groups."""

        dataset.validate()
        training = dataset.subset("TRAIN")
        probability_calibration = dataset.subset("CALIBRATION")
        conformal_calibration = dataset.subset("CONFORMAL_CALIBRATION")
        role_groups = {
            "training": set(training.run_ids),
            "probability_calibration": set(probability_calibration.run_ids),
            "conformal_calibration": set(conformal_calibration.run_ids),
        }
        role_group_sets = list(role_groups.values())
        if any(
            left & right
            for index, left in enumerate(role_group_sets)
            for right in role_group_sets[index + 1 :]
        ):
            raise EarlyWarningError("predictor fit-role run groups overlap")
        for split in (training, probability_calibration, conformal_calibration):
            if len(np.unique(split.labels)) != 2:
                raise EarlyWarningError("each predictor fit-role split requires both classes")
        self.feature_names = training.feature_names
        if any(
            split.feature_names != self.feature_names
            for split in (probability_calibration, conformal_calibration)
        ):
            raise EarlyWarningError("predictor fit-role feature schemas differ")
        self.training_prevalence = float(np.mean(training.labels))
        sk = self._sklearn()
        imputer = sk["SimpleImputer"](strategy="median", keep_empty_features=True)
        if self.model_kind is ModelKind.LOGISTIC:
            base = sk["LogisticRegression"](
                C=self.model_config.logistic.c,
                max_iter=self.model_config.logistic.max_iter,
                class_weight=self.model_config.logistic.class_weight,
                random_state=self.model_config.random_seed,
            )
            self.base_model = sk["Pipeline"](
                (("imputer", imputer), ("scaler", sk["StandardScaler"]()), ("model", base))
            )
            self.base_model.fit(training.features, training.labels)
        elif self.model_kind is ModelKind.GRADIENT_BOOSTED:
            config = self.model_config.gradient_boosted
            base = sk["HistGradientBoostingClassifier"](
                max_iter=config.max_iter,
                learning_rate=config.learning_rate,
                max_leaf_nodes=config.max_leaf_nodes,
                min_samples_leaf=config.min_samples_leaf,
                l2_regularization=config.l2_regularization,
                random_state=self.model_config.random_seed,
            )
            self.base_model = sk["Pipeline"]((("imputer", imputer), ("model", base)))
            weights = self._balanced_sample_weights(training.labels)
            self.base_model.fit(training.features, training.labels, model__sample_weight=weights)
        elif self.model_kind is not ModelKind.PREVALENCE:
            raise EarlyWarningError(f"unsupported model kind: {self.model_kind}")

        calibration_base = self._base_probabilities(probability_calibration.features)
        self.calibrator = sk["LogisticRegression"](
            C=self.model_config.sigmoid_calibration_c,
            max_iter=1000,
            random_state=self.model_config.random_seed,
        )
        calibration_logits = self._logit(
            calibration_base,
            self.model_config.calibration_probability_clip,
        )
        self.calibrator.fit(calibration_logits, probability_calibration.labels)

        # Conformal scores must be evaluated after the base predictor and
        # probability calibrator are fixed. Reusing probability-calibration
        # rows would make the nonconformity scores adaptive to those rows and
        # invalidate the intended split-conformal construction.
        conformal_base = self._base_probabilities(conformal_calibration.features)
        conformal_logits = self._logit(
            conformal_base,
            self.model_config.calibration_probability_clip,
        )
        conformal_probabilities = np.asarray(
            self.calibrator.predict_proba(conformal_logits)[:, 1], dtype=float
        )
        true_probability = np.where(
            conformal_calibration.labels == 1,
            conformal_probabilities,
            1.0 - conformal_probabilities,
        )
        scores = 1.0 - true_probability
        self.conformal_quantile = split_conformal_quantile(
            scores,
            self.model_config.conformal_alpha,
        )
        group_payload = json.dumps(
            {
                "training": sorted(set(training.run_ids)),
                "probability_calibration": sorted(
                    set(probability_calibration.run_ids)
                ),
                "conformal_calibration": sorted(set(conformal_calibration.run_ids)),
                "features": self.feature_names,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        self.fit_group_sha256 = hashlib.sha256(group_payload).hexdigest()
        return self

    def _prediction_sets(self, probabilities: np.ndarray) -> tuple[tuple[int, ...], ...]:
        if self.conformal_quantile is None:
            raise EarlyWarningError("conformal uncertainty is not fitted")
        sets: list[tuple[int, ...]] = []
        for probability in probabilities:
            members: list[int] = []
            if float(probability) <= self.conformal_quantile + 1.0e-15:
                members.append(0)
            if 1.0 - float(probability) <= self.conformal_quantile + 1.0e-15:
                members.append(1)
            sets.append(tuple(members))
        return tuple(sets)

    def predict_features(
        self,
        features: np.ndarray,
    ) -> tuple[np.ndarray, tuple[tuple[int, ...], ...], np.ndarray]:
        """Predict a prepared matrix for deterministic offline evaluation."""

        matrix = np.asarray(features, dtype=float)
        if matrix.ndim != 2 or self.feature_names is None:
            raise EarlyWarningError("predictor must be fitted before matrix prediction")
        if matrix.shape[1] != len(self.feature_names):
            raise EarlyWarningError("prediction feature width differs from fitted schema")
        start = time.perf_counter()
        probabilities = self._calibrated_probabilities(matrix)
        elapsed = time.perf_counter() - start
        latency = np.full(len(matrix), elapsed / max(1, len(matrix)), dtype=float)
        return probabilities, self._prediction_sets(probabilities), latency

    def predict(self, observation_window: WarningObservationWindow) -> Prediction:
        """Predict from arrived observations without mutating the input window."""

        vector = self.extractor.transform(observation_window)
        if self.feature_names is None or vector.names != self.feature_names:
            raise EarlyWarningError("observation feature schema differs from fitted predictor")
        probability, prediction_sets, latency = self.predict_features(vector.values.reshape(1, -1))
        prediction_set = prediction_sets[0]
        return Prediction(
            probability=float(probability[0]),
            predicted_excursion=bool(
                probability[0] >= self.model_config.probability_threshold
            ),
            conformal_prediction_set=prediction_set,
            uncertainty_valid=len(prediction_set) > 0,
            feature_cutoff_step_index=vector.feature_cutoff_step_index,
            feature_cutoff_timestamp_s=vector.feature_cutoff_timestamp_s,
            latency_s=float(latency[0]),
        )

    def save(self, path: str | Path) -> None:
        """Atomically write a local model payload plus checksum metadata."""

        if self.feature_names is None or self.calibrator is None:
            raise EarlyWarningError("cannot save an unfitted predictor")
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "artifact_version": self.artifact_version,
            "model_kind": self.model_kind.value,
            "feature_config": self.feature_config.model_dump(mode="json"),
            "model_config": self.model_config.model_dump(mode="json"),
            "feature_names": self.feature_names,
            "base_model": self.base_model,
            "calibrator": self.calibrator,
            "training_prevalence": self.training_prevalence,
            "conformal_quantile": self.conformal_quantile,
            "fit_group_sha256": self.fit_group_sha256,
        }
        payload_bytes = pickle.dumps(payload, protocol=pickle.HIGHEST_PROTOCOL)
        checksum = hashlib.sha256(payload_bytes).hexdigest()
        metadata = {
            "artifact_version": self.artifact_version,
            "sha256": checksum,
            "model_kind": self.model_kind.value,
            "fit_group_sha256": self.fit_group_sha256,
        }
        temporary = destination.with_suffix(destination.suffix + ".tmp")
        temporary.write_bytes(payload_bytes)
        temporary.replace(destination)
        metadata_path = destination.with_suffix(destination.suffix + ".json")
        metadata_temporary = metadata_path.with_suffix(metadata_path.suffix + ".tmp")
        metadata_temporary.write_text(
            json.dumps(metadata, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        metadata_temporary.replace(metadata_path)

    @classmethod
    def load(cls, path: str | Path) -> EarlyWarningPredictor:
        """Load a checksum-verified compatible local predictor artifact."""

        source = Path(path)
        metadata_path = source.with_suffix(source.suffix + ".json")
        try:
            payload_bytes = source.read_bytes()
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise EarlyWarningError(f"cannot load predictor artifact: {exc}") from exc
        checksum = hashlib.sha256(payload_bytes).hexdigest()
        if checksum != metadata.get("sha256"):
            raise EarlyWarningError("predictor artifact checksum mismatch")
        try:
            payload = pickle.loads(payload_bytes)
        except Exception as exc:
            raise EarlyWarningError(f"invalid predictor payload: {exc}") from exc
        version = str(payload.get("artifact_version", ""))
        if version.split(".", 1)[0] != cls.artifact_version.split(".", 1)[0]:
            raise EarlyWarningError("incompatible predictor artifact major version")
        predictor = cls(
            ModelKind(payload["model_kind"]),
            FeatureConfig.model_validate(payload["feature_config"]),
            ModelConfig.model_validate(payload["model_config"]),
        )
        predictor.feature_names = tuple(payload["feature_names"])
        predictor.base_model = cls._repair_sklearn_pickle_compatibility(
            payload["base_model"]
        )
        predictor.calibrator = payload["calibrator"]
        predictor.training_prevalence = float(payload["training_prevalence"])
        predictor.conformal_quantile = float(payload["conformal_quantile"])
        predictor.fit_group_sha256 = str(payload["fit_group_sha256"])
        return predictor


def _expected_calibration_error(
    labels: np.ndarray,
    probabilities: np.ndarray,
    bins: int,
) -> float:
    boundaries = np.linspace(0.0, 1.0, bins + 1)
    result = 0.0
    for index in range(bins):
        if index == bins - 1:
            mask = (probabilities >= boundaries[index]) & (
                probabilities <= boundaries[index + 1]
            )
        else:
            mask = (probabilities >= boundaries[index]) & (
                probabilities < boundaries[index + 1]
            )
        if np.any(mask):
            result += float(np.mean(mask)) * abs(
                float(np.mean(labels[mask])) - float(np.mean(probabilities[mask]))
            )
    return result


def evaluate_predictions(
    dataset: WarningDataset,
    probabilities: Sequence[float],
    prediction_sets: Sequence[Sequence[int]],
    *,
    probability_threshold: float,
    horizon_s: float,
    decision_period_s: float,
    calibration_bins: int,
    latency_s: Sequence[float] | None = None,
) -> dict[str, float | int | None]:
    """Compute sample, event, uncertainty, and latency warning metrics."""

    dataset.validate()
    labels = np.asarray(dataset.labels, dtype=int)
    probabilities_array = np.asarray(probabilities, dtype=float)
    if len(probabilities_array) != len(labels) or not np.all(
        np.isfinite(probabilities_array)
    ):
        raise EarlyWarningError("probabilities must be finite and match dataset rows")
    if np.any((probabilities_array < 0.0) | (probabilities_array > 1.0)):
        raise EarlyWarningError("probabilities must be within [0, 1]")
    if len(prediction_sets) != len(labels):
        raise EarlyWarningError("prediction sets must match dataset rows")
    try:
        from sklearn.metrics import (
            average_precision_score,
            brier_score_loss,
        )
    except ImportError as exc:
        raise EarlyWarningError("evaluation requires scikit-learn") from exc

    predicted = probabilities_array >= probability_threshold
    true_positive = int(np.sum((labels == 1) & predicted))
    true_negative = int(np.sum((labels == 0) & ~predicted))
    false_positive = int(np.sum((labels == 0) & predicted))
    false_negative = int(np.sum((labels == 1) & ~predicted))
    positive_count = true_positive + false_negative
    negative_count = true_negative + false_positive
    predicted_positive_count = true_positive + false_positive
    precision = (
        true_positive / predicted_positive_count
        if predicted_positive_count > 0
        else None
    )
    recall = true_positive / positive_count if positive_count > 0 else None
    specificity = true_negative / negative_count if negative_count > 0 else None
    coverage = float(
        np.mean(
            [int(label) in {int(value) for value in prediction_set} for label, prediction_set in zip(labels, prediction_sets, strict=True)]
        )
    )
    set_sizes = np.asarray([len(set(values)) for values in prediction_sets], dtype=float)

    false_alarm_episodes = 0
    event_count = 0
    detected_events = 0
    lead_times: list[float] = []
    for run_id in sorted(set(dataset.run_ids)):
        indices = np.asarray(
            [index for index, value in enumerate(dataset.run_ids) if value == run_id],
            dtype=int,
        )
        order = indices[np.argsort(dataset.decision_timestamps_s[indices])]
        run_predicted = predicted[order]
        run_times = dataset.decision_timestamps_s[order]
        alarm_times = [
            float(run_times[index])
            for index, value in enumerate(run_predicted)
            if bool(value) and (index == 0 or not bool(run_predicted[index - 1]))
        ]
        finite_onsets = dataset.first_excursion_timestamps_s[order]
        finite_onsets = finite_onsets[np.isfinite(finite_onsets)]
        event_time = float(np.min(finite_onsets)) if len(finite_onsets) else None
        linked: list[float] = []
        for alarm_time in alarm_times:
            if event_time is not None and 0.0 < event_time - alarm_time <= horizon_s + 1.0e-12:
                linked.append(alarm_time)
            else:
                false_alarm_episodes += 1
        if event_time is not None:
            event_count += 1
            if linked:
                detected_events += 1
                lead_times.append(event_time - min(linked))

    monitored_hours = len(labels) * decision_period_s / 3600.0
    latencies = np.asarray(latency_s if latency_s is not None else [], dtype=float)
    if len(latencies) and (len(latencies) != len(labels) or not np.all(np.isfinite(latencies))):
        raise EarlyWarningError("latency values must be finite and match dataset rows")
    pr_auc = (
        float(average_precision_score(labels, probabilities_array))
        if positive_count > 0 and negative_count > 0
        else None
    )
    return {
        "row_count": int(len(labels)),
        "positive_count": positive_count,
        "negative_count": negative_count,
        "true_positive_count": true_positive,
        "true_negative_count": true_negative,
        "false_positive_count": false_positive,
        "false_negative_count": false_negative,
        "predicted_positive_count": predicted_positive_count,
        "prevalence": float(np.mean(labels)),
        "precision": None if precision is None else float(precision),
        "recall": None if recall is None else float(recall),
        "specificity": None if specificity is None else float(specificity),
        # A precision-recall curve requires both target classes.  Negative-only
        # structural-null and robustness sets remain useful for specificity and
        # false-alarm diagnostics, but assigning them PR-AUC=0 would imply a
        # defined ranking experiment that did not occur.
        "pr_auc": pr_auc,
        "brier_score": float(brier_score_loss(labels, probabilities_array)),
        "expected_calibration_error": float(
            _expected_calibration_error(labels, probabilities_array, calibration_bins)
        ),
        "conformal_coverage": coverage,
        "mean_prediction_set_size": float(np.mean(set_sizes)),
        "empty_prediction_set_fraction": float(np.mean(set_sizes == 0)),
        "two_class_prediction_set_fraction": float(np.mean(set_sizes == 2)),
        "false_alarm_episodes": int(false_alarm_episodes),
        "false_alarms_per_simulated_hour": float(
            false_alarm_episodes / max(monitored_hours, 1.0e-12)
        ),
        "event_count": int(event_count),
        "detected_event_count": int(detected_events),
        "event_recall": float(detected_events / event_count) if event_count else None,
        "missed_event_rate": float(1.0 - detected_events / event_count) if event_count else None,
        "median_warning_lead_time_s": (
            float(np.median(lead_times)) if lead_times else None
        ),
        "mean_warning_lead_time_s": float(np.mean(lead_times)) if lead_times else None,
        "mean_prediction_latency_s": float(np.mean(latencies)) if len(latencies) else None,
        "p95_prediction_latency_s": (
            float(np.quantile(latencies, 0.95)) if len(latencies) else None
        ),
    }
