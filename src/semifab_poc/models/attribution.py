"""Conservative synthetic root-cause attribution with mandatory abstention.

Online estimation consumes arrived observation records and a contemporaneous
early-warning result. Simulator initiating labels are accepted only by the
offline dataset used to fit and evaluate the statistical comparator. Rule
chains and coefficient contributions are diagnostic evidence, never causal
proof.
"""

from __future__ import annotations

import hashlib
import json
import math
import pickle
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from semifab_poc.data.schema import ObservationRecord, RootCause
from semifab_poc.models.early_warning import Prediction


PRIMARY_INITIATING_CAUSES = (
    RootCause.GRID_VOLTAGE_SAG,
    RootCause.GRID_VOLTAGE_SWELL,
    RootCause.GRID_INTERRUPTION,
    RootCause.GRID_FREQUENCY_DEVIATION,
    RootCause.PUMP_TRIP,
    RootCause.VALVE_RESTRICTION,
    RootCause.TOOL_DEMAND_SPIKE,
    RootCause.THERMAL_EXCURSION,
    RootCause.PRESSURE_SENSOR_FAULT,
    RootCause.FLOW_SENSOR_FAULT,
)
PROPAGATION_EVIDENCE_CAUSES = (
    RootCause.UPS_TRANSFER,
    RootCause.VFD_DERATING,
)
MODEL_CAUSES = PRIMARY_INITIATING_CAUSES + (RootCause.UNKNOWN,)
ALL_CAUSES = tuple(RootCause)


class AttributionError(ValueError):
    """Raised when attribution configuration, data, or state is invalid."""


class AttributionMethod(str, Enum):
    ALWAYS_UNKNOWN = "ALWAYS_UNKNOWN"
    RULE_ONLY = "RULE_ONLY"
    LOGISTIC = "LOGISTIC"
    HYBRID = "HYBRID"


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, validate_assignment=True)


class EstimatorConfig(_StrictModel):
    estimator_id: str = Field(min_length=1)
    primary_method: AttributionMethod
    primary_initiating_causes: tuple[RootCause, ...]
    propagation_evidence_causes: tuple[RootCause, ...]
    unknown_cause: RootCause
    causal_proof: bool
    require_positive_warning: bool
    require_singleton_positive_conformal_set: bool

    @model_validator(mode="after")
    def validate_vocabulary(self) -> EstimatorConfig:
        if self.primary_initiating_causes != PRIMARY_INITIATING_CAUSES:
            raise ValueError("primary initiating causes must match the frozen ordered vocabulary")
        if self.propagation_evidence_causes != PROPAGATION_EVIDENCE_CAUSES:
            raise ValueError("propagation causes must be UPS_TRANSFER then VFD_DERATING")
        if self.unknown_cause is not RootCause.UNKNOWN:
            raise ValueError("unknown_cause must be UNKNOWN")
        if self.causal_proof:
            raise ValueError("attribution causal_proof must remain false")
        return self


class FeatureConfig(_StrictModel):
    window_s: float = Field(gt=0.0)
    maximum_observation_age_s: float = Field(gt=0.0)
    sensor_sample_period_s: float = Field(gt=0.0)
    statistics: tuple[str, ...]
    allowed_signal_ids: tuple[str, ...] = Field(min_length=1)
    critical_signal_ids: tuple[str, ...] = Field(min_length=1)
    forbidden_signal_ids: tuple[str, ...]
    normalization_by_signal: dict[str, tuple[float, float]]

    @model_validator(mode="after")
    def validate_features(self) -> FeatureConfig:
        if self.statistics != (
            "latest",
            "short_mean",
            "short_slope",
            "missing_fraction",
        ):
            raise ValueError("attribution statistics do not match the frozen order")
        allowed = set(self.allowed_signal_ids)
        if len(allowed) != len(self.allowed_signal_ids):
            raise ValueError("allowed attribution signal IDs must be unique")
        if not set(self.critical_signal_ids) <= allowed:
            raise ValueError("critical attribution signals must be allowed")
        if allowed & set(self.forbidden_signal_ids):
            raise ValueError("allowed and forbidden attribution signals must be disjoint")
        if set(self.normalization_by_signal) != allowed:
            raise ValueError("each allowed attribution signal requires one normalization")
        for signal_id, (offset, scale) in self.normalization_by_signal.items():
            if not math.isfinite(offset) or not math.isfinite(scale) or scale <= 0.0:
                raise ValueError(f"invalid attribution normalization for {signal_id}")
        return self


class SensorEnsembleConfig(_StrictModel):
    delay_s: float = Field(ge=0.0)
    packet_loss_probability: float = Field(ge=0.0, le=1.0)
    timestamp_jitter_std_s: float = Field(ge=0.0)
    noise_by_signal: dict[str, float]

    @model_validator(mode="after")
    def validate_noise(self) -> SensorEnsembleConfig:
        if any(
            not math.isfinite(value) or value < 0.0
            for value in self.noise_by_signal.values()
        ):
            raise ValueError("attribution sensor noise must be finite and non-negative")
        return self


class ResidualConfig(_StrictModel):
    nominal_return_pressure_pa: float = Field(ge=0.0)
    nominal_supply_pressure_pa: float = Field(gt=0.0)
    nominal_pump_flow_m3_s: float = Field(gt=0.0)
    nominal_tool_flow_m3_s: float = Field(gt=0.0)
    tool_resistance_pa_s_m3: float = Field(gt=0.0)

    @model_validator(mode="after")
    def validate_pressures(self) -> ResidualConfig:
        if self.nominal_return_pressure_pa >= self.nominal_supply_pressure_pa:
            raise ValueError("nominal return pressure must be below supply pressure")
        return self


class RuleConfig(_StrictModel):
    grid_sag_start_fraction: float = Field(ge=0.0)
    grid_sag_full_fraction: float = Field(gt=0.0)
    grid_swell_start_fraction: float = Field(ge=0.0)
    grid_swell_full_fraction: float = Field(gt=0.0)
    interruption_start_voltage_pu: float = Field(ge=0.0, le=1.0)
    interruption_full_voltage_pu: float = Field(ge=0.0, le=1.0)
    frequency_start_hz: float = Field(ge=0.0)
    frequency_full_hz: float = Field(gt=0.0)
    motor_loss_start_fraction: float = Field(ge=0.0)
    motor_loss_full_fraction: float = Field(gt=0.0)
    valve_loss_start_fraction: float = Field(ge=0.0)
    valve_loss_full_fraction: float = Field(gt=0.0)
    demand_gain_start_fraction: float = Field(ge=0.0)
    demand_gain_full_fraction: float = Field(gt=0.0)
    temperature_start_k: float = Field(ge=0.0)
    temperature_full_k: float = Field(gt=0.0)
    pressure_residual_start_fraction: float = Field(ge=0.0)
    pressure_residual_full_fraction: float = Field(gt=0.0)
    flow_residual_start_fraction: float = Field(ge=0.0)
    flow_residual_full_fraction: float = Field(gt=0.0)
    physical_quiet_max_score: float = Field(ge=0.0, le=1.0)
    propagation_start_fraction: float = Field(ge=0.0)
    propagation_full_fraction: float = Field(gt=0.0)
    rule_softmax_temperature: float = Field(gt=0.0)

    @model_validator(mode="after")
    def validate_thresholds(self) -> RuleConfig:
        ordered = (
            (self.grid_sag_start_fraction, self.grid_sag_full_fraction),
            (self.grid_swell_start_fraction, self.grid_swell_full_fraction),
            (self.frequency_start_hz, self.frequency_full_hz),
            (self.motor_loss_start_fraction, self.motor_loss_full_fraction),
            (self.valve_loss_start_fraction, self.valve_loss_full_fraction),
            (self.demand_gain_start_fraction, self.demand_gain_full_fraction),
            (self.temperature_start_k, self.temperature_full_k),
            (
                self.pressure_residual_start_fraction,
                self.pressure_residual_full_fraction,
            ),
            (self.flow_residual_start_fraction, self.flow_residual_full_fraction),
            (self.propagation_start_fraction, self.propagation_full_fraction),
        )
        if any(start >= full for start, full in ordered):
            raise ValueError("each attribution rule start threshold must be below full")
        if self.interruption_full_voltage_pu >= self.interruption_start_voltage_pu:
            raise ValueError("interruption full voltage must be below its start voltage")
        return self


class ModelConfig(_StrictModel):
    random_seed: int = Field(ge=0)
    logistic_c: float = Field(gt=0.0)
    max_iter: int = Field(gt=0)
    class_weight: str
    calibration_temperature_grid: tuple[float, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_model(self) -> ModelConfig:
        if self.class_weight != "balanced":
            raise ValueError("frozen attribution class_weight must be balanced")
        if any(
            not math.isfinite(value) or value <= 0.0
            for value in self.calibration_temperature_grid
        ):
            raise ValueError("calibration temperatures must be finite and positive")
        if (
            tuple(sorted(set(self.calibration_temperature_grid)))
            != self.calibration_temperature_grid
        ):
            raise ValueError("calibration temperature grid must be unique and increasing")
        return self


class FusionConfig(_StrictModel):
    logistic_weight: float = Field(ge=0.0, le=1.0)
    probability_clip: float = Field(gt=0.0, lt=0.5)
    maximum_propagation_probability_mass: float = Field(ge=0.0, lt=1.0)


class UnknownPolicyConfig(_StrictModel):
    minimum_top_probability: float = Field(ge=0.0, le=1.0)
    minimum_top_two_margin: float = Field(ge=0.0, le=1.0)
    maximum_aggregate_missing_fraction: float = Field(ge=0.0, le=1.0)
    maximum_standardized_feature_abs: float = Field(gt=0.0)
    maximum_rule_model_js_divergence: float = Field(ge=0.0, le=1.0)
    disagreement_minimum_confidence: float = Field(ge=0.0, le=1.0)
    compound_minimum_rule_score: float = Field(ge=0.0, le=1.0)
    forced_unknown_probability: float = Field(gt=0.5, le=1.0)


class ScenarioRangesConfig(_StrictModel):
    grid_voltage_sag_pu: tuple[float, float]
    grid_voltage_swell_pu: tuple[float, float]
    grid_frequency_deviation_abs_hz: tuple[float, float]
    valve_position: tuple[float, float]
    tool_demand_m3_s: tuple[float, float]
    inlet_temperature_k: tuple[float, float]
    pressure_sensor_bias_pa: tuple[float, float]
    flow_sensor_bias_m3_s: tuple[float, float]

    @model_validator(mode="after")
    def validate_ranges(self) -> ScenarioRangesConfig:
        for name, bounds in self:
            if len(bounds) != 2 or not all(math.isfinite(value) for value in bounds):
                raise ValueError(f"scenario range {name} must contain two finite values")
            if bounds[0] >= bounds[1]:
                raise ValueError(f"scenario range {name} must be strictly increasing")
        return self


class SimulationConfig(_StrictModel):
    dt_s: float = Field(gt=0.0)
    duration_s: float = Field(gt=0.0)
    plant_warmup_s: float = Field(ge=0.0)
    dress_end_s: float = Field(gt=0.0)
    polish_start_s: float = Field(gt=0.0)
    topology: str = Field(min_length=1)
    event_start_s: float = Field(ge=0.0)
    event_duration_s: float = Field(gt=0.0)
    decision_offsets_s: tuple[float, ...] = Field(min_length=1)
    scenario_ranges: ScenarioRangesConfig

    @model_validator(mode="after")
    def validate_schedule(self) -> SimulationConfig:
        if not self.dress_end_s < self.polish_start_s < self.duration_s:
            raise ValueError("attribution schedule must order DRESS, POLISH, duration")
        if self.event_start_s + self.event_duration_s > self.duration_s + 1.0e-12:
            raise ValueError("attribution event exceeds the run duration")
        if any(
            offset <= 0.0 or offset >= self.event_duration_s
            for offset in self.decision_offsets_s
        ):
            raise ValueError("attribution decision offsets must lie inside the event")
        if tuple(sorted(set(self.decision_offsets_s))) != self.decision_offsets_s:
            raise ValueError("attribution decision offsets must be unique and increasing")
        return self


class RunsPerCauseConfig(_StrictModel):
    training: int = Field(gt=0)
    calibration: int = Field(gt=0)
    test: int = Field(gt=0)
    compound: int = Field(gt=0)
    robustness: int = Field(gt=0)


class SplitConfig(_StrictModel):
    train_seed_start: int = Field(ge=0)
    calibration_seed_start: int = Field(ge=0)
    test_seed_start: int = Field(ge=0)
    compound_seed_start: int = Field(ge=0)
    robustness_seed_start: int = Field(ge=0)
    runs_per_cause: RunsPerCauseConfig

    @model_validator(mode="after")
    def validate_seed_blocks(self) -> SplitConfig:
        starts = (
            self.train_seed_start,
            self.calibration_seed_start,
            self.test_seed_start,
            self.compound_seed_start,
            self.robustness_seed_start,
        )
        if len(set(starts)) != len(starts):
            raise ValueError("attribution split seed starts must be distinct")
        return self


class EvaluationConfig(_StrictModel):
    calibration_bins: int = Field(gt=1)
    grouped_bootstrap_repetitions: int = Field(gt=0)
    grouped_bootstrap_seed: int = Field(ge=0)
    minimum_accuracy: float = Field(ge=0.0, le=1.0)
    minimum_macro_recall: float = Field(ge=0.0, le=1.0)
    minimum_accuracy_improvement_over_unknown: float = Field(ge=0.0, le=1.0)
    minimum_unknown_recall: float = Field(ge=0.0, le=1.0)
    maximum_normal_false_attribution_rate: float = Field(ge=0.0, le=1.0)
    minimum_selective_accuracy: float = Field(ge=0.0, le=1.0)
    minimum_known_cause_coverage: float = Field(ge=0.0, le=1.0)
    minimum_compound_abstention_rate: float = Field(ge=0.0, le=1.0)


class RobustnessConfig(_StrictModel):
    noise_scale: float = Field(ge=1.0)
    delay_s: float = Field(ge=0.0)
    packet_loss_probability: float = Field(ge=0.0, le=1.0)


class AttributionConfig(_StrictModel):
    schema_version: str = Field(min_length=1)
    experiment_revision: str = Field(min_length=1)
    estimator: EstimatorConfig
    features: FeatureConfig
    sensors: SensorEnsembleConfig
    residuals: ResidualConfig
    rules: RuleConfig
    model: ModelConfig
    fusion: FusionConfig
    unknown_policy: UnknownPolicyConfig
    simulation: SimulationConfig
    splits: SplitConfig
    evaluation: EvaluationConfig
    robustness: RobustnessConfig

    @model_validator(mode="after")
    def validate_version(self) -> AttributionConfig:
        if self.schema_version != "1.0.0":
            raise ValueError("only attribution schema 1.0.0 is supported")
        if set(self.sensors.noise_by_signal) != set(self.features.allowed_signal_ids):
            raise ValueError("each attribution signal requires one sensor noise entry")
        return self


def load_attribution_config(path: str | Path) -> AttributionConfig:
    """Load the strict preregistered WP13 configuration."""

    config_path = Path(path)
    try:
        payload = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise AttributionError(f"cannot load attribution configuration: {exc}") from exc
    if not isinstance(payload, dict):
        raise AttributionError("attribution configuration root must be a mapping")
    try:
        return AttributionConfig.model_validate(payload)
    except Exception as exc:
        raise AttributionError(f"invalid attribution configuration: {exc}") from exc


@dataclass(frozen=True)
class AttributionObservationWindow:
    run_id: str
    decision_step_index: int
    decision_timestamp_s: float
    observations: tuple[ObservationRecord, ...]


@dataclass(frozen=True)
class AttributionFeatureVector:
    names: tuple[str, ...]
    values: np.ndarray
    latest_by_signal: Mapping[str, float]
    age_by_signal_s: Mapping[str, float]
    residual_evidence: Mapping[str, float]
    aggregate_missing_fraction: float
    critical_signal_stale: bool
    feature_cutoff_step_index: int
    feature_cutoff_timestamp_s: float


@dataclass(frozen=True)
class Attribution:
    run_id: str
    decision_step_index: int
    estimator_id: str
    predicted_cause: RootCause
    probability_by_cause: Mapping[RootCause, float]
    rule_chain_ids: tuple[str, ...]
    residual_evidence: Mapping[str, float]
    attribution_method: str
    causal_proof: bool = False

    def __post_init__(self) -> None:
        if not self.run_id or self.decision_step_index < 0 or not self.estimator_id:
            raise AttributionError("attribution record identity must be valid")
        if self.predicted_cause not in ALL_CAUSES:
            raise AttributionError("predicted attribution cause is not canonical")
        if set(self.probability_by_cause) != set(ALL_CAUSES):
            raise AttributionError("attribution probabilities must cover all canonical causes")
        probabilities = np.asarray(list(self.probability_by_cause.values()), dtype=float)
        if not np.all(np.isfinite(probabilities)) or np.any(probabilities < 0.0):
            raise AttributionError("attribution probabilities must be finite and non-negative")
        if not math.isclose(float(np.sum(probabilities)), 1.0, abs_tol=1.0e-9):
            raise AttributionError("attribution probabilities must sum to one")
        if self.causal_proof:
            raise AttributionError("an attribution record can never assert causal proof")
        if any(not item for item in self.rule_chain_ids):
            raise AttributionError("rule-chain IDs must be non-empty")
        if any(not math.isfinite(float(value)) for value in self.residual_evidence.values()):
            raise AttributionError("residual evidence values must be finite")


@dataclass(frozen=True)
class AttributionDataset:
    feature_names: tuple[str, ...]
    features: np.ndarray
    labels: tuple[RootCause, ...]
    run_ids: tuple[str, ...]
    split_ids: tuple[str, ...]
    decision_step_indices: np.ndarray
    decision_timestamps_s: np.ndarray

    def validate(self) -> None:
        rows = len(self.labels)
        if self.features.ndim != 2 or self.features.shape != (rows, len(self.feature_names)):
            raise AttributionError("attribution feature matrix does not match metadata")
        if not (
            len(self.run_ids)
            == len(self.split_ids)
            == len(self.decision_step_indices)
            == len(self.decision_timestamps_s)
            == rows
        ):
            raise AttributionError("attribution dataset columns must have equal length")
        if rows == 0 or len(set(self.feature_names)) != len(self.feature_names):
            raise AttributionError("attribution dataset must be non-empty with unique features")
        if not set(self.labels) <= set(MODEL_CAUSES):
            raise AttributionError("attribution dataset contains a non-initiating label")
        if not np.all(np.isfinite(self.decision_timestamps_s)):
            raise AttributionError("attribution decision timestamps must be finite")
        split_by_run: dict[str, str] = {}
        for run_id, split_id in zip(self.run_ids, self.split_ids, strict=True):
            prior = split_by_run.setdefault(run_id, split_id)
            if prior != split_id:
                raise AttributionError("one attribution run cannot cross dataset splits")

    def subset(self, split_id: str) -> AttributionDataset:
        self.validate()
        mask = np.asarray([value == split_id for value in self.split_ids], dtype=bool)
        if not np.any(mask):
            raise AttributionError(f"attribution dataset contains no {split_id!r} rows")
        indices = np.flatnonzero(mask)
        return AttributionDataset(
            feature_names=self.feature_names,
            features=self.features[mask].copy(),
            labels=tuple(self.labels[index] for index in indices),
            run_ids=tuple(self.run_ids[index] for index in indices),
            split_ids=tuple(self.split_ids[index] for index in indices),
            decision_step_indices=self.decision_step_indices[mask].copy(),
            decision_timestamps_s=self.decision_timestamps_s[mask].copy(),
        )


class AttributionFeatureExtractor:
    """Create arrived-only diagnostic features and redundancy residuals."""

    interface_version = "1.0.0"

    def __init__(self, config: FeatureConfig, residuals: ResidualConfig) -> None:
        self.config = config
        self.residuals = residuals

    def transform(self, window: AttributionObservationWindow) -> AttributionFeatureVector:
        if not window.run_id or window.decision_step_index < 0:
            raise AttributionError("attribution window identity must be valid")
        if not math.isfinite(window.decision_timestamp_s) or window.decision_timestamp_s < 0.0:
            raise AttributionError("attribution decision timestamp must be finite and non-negative")
        allowed = set(self.config.allowed_signal_ids)
        forbidden = set(self.config.forbidden_signal_ids)
        by_signal: dict[str, list[ObservationRecord]] = {
            signal_id: [] for signal_id in self.config.allowed_signal_ids
        }
        for record in window.observations:
            if record.run_id != window.run_id:
                raise AttributionError("observation run_id does not match attribution window")
            if record.arrival_timestamp_s > window.decision_timestamp_s + 1.0e-12:
                raise AttributionError("future-arrival observation crossed attribution cutoff")
            if record.signal_id in forbidden:
                raise AttributionError(f"forbidden attribution signal supplied: {record.signal_id}")
            if record.signal_id not in allowed:
                raise AttributionError(
                    f"unregistered attribution signal supplied: {record.signal_id}"
                )
            if record.source_step_index is None or record.source_timestamp_s is None:
                raise AttributionError("attribution observations require source identity")
            if record.source_step_index > window.decision_step_index:
                raise AttributionError("future source step crossed attribution cutoff")
            by_signal[record.signal_id].append(record)

        names: list[str] = []
        values: list[float] = []
        latest_by_signal: dict[str, float] = {}
        age_by_signal: dict[str, float] = {}
        missing_by_signal: dict[str, float] = {}
        window_start = window.decision_timestamp_s - self.config.window_s
        expected = max(
            1,
            math.floor(self.config.window_s / self.config.sensor_sample_period_s + 1.0e-12)
            + 1,
        )
        for signal_id in self.config.allowed_signal_ids:
            records = sorted(
                (
                    record
                    for record in by_signal[signal_id]
                    if record.source_timestamp_s is not None
                    and window_start - 1.0e-12
                    <= record.source_timestamp_s
                    <= window.decision_timestamp_s + 1.0e-12
                ),
                key=lambda record: (float(record.source_timestamp_s), record.sample_index),
            )
            valid = [
                record
                for record in records
                if isinstance(record.value, (int, float)) and record.value is not None
            ]
            offset, scale = self.config.normalization_by_signal[signal_id]
            normalized = np.asarray(
                [(float(record.value) - offset) / scale for record in valid], dtype=float
            )
            times = np.asarray(
                [float(record.source_timestamp_s) for record in valid], dtype=float
            )
            if valid:
                latest_by_signal[signal_id] = float(valid[-1].value)
                age_by_signal[signal_id] = (
                    window.decision_timestamp_s - float(valid[-1].source_timestamp_s)
                )
                latest = float(normalized[-1])
                mean = float(np.mean(normalized))
            else:
                latest_by_signal[signal_id] = math.nan
                age_by_signal[signal_id] = math.inf
                latest = math.nan
                mean = math.nan
            if len(normalized) >= 2 and float(np.ptp(times)) > 1.0e-12:
                centered_time = times - float(np.mean(times))
                slope = float(
                    np.dot(centered_time, normalized - float(np.mean(normalized)))
                    / np.dot(centered_time, centered_time)
                )
            else:
                slope = math.nan
            missing = min(1.0, max(0.0, 1.0 - len(valid) / expected))
            missing_by_signal[signal_id] = missing
            statistics = {
                "latest": latest,
                "short_mean": mean,
                "short_slope": slope,
                "missing_fraction": missing,
            }
            for statistic in self.config.statistics:
                names.append(f"{signal_id}:{statistic}")
                values.append(float(statistics[statistic]))

        pressure = latest_by_signal["upw.supply_pressure"]
        pump_flow = latest_by_signal["pump.volumetric_flow"]
        tool_flow = latest_by_signal["upw.tool_flow"]
        valve = latest_by_signal["upw.valve_position"]
        demand = latest_by_signal["upw.tool_demand"]
        if math.isfinite(pressure) and math.isfinite(pump_flow):
            pump_ratio = max(0.0, pump_flow / self.residuals.nominal_pump_flow_m3_s)
            expected_pressure = self.residuals.nominal_return_pressure_pa + (
                self.residuals.nominal_supply_pressure_pa
                - self.residuals.nominal_return_pressure_pa
            ) * pump_ratio**2
            pressure_residual = (
                pressure - expected_pressure
            ) / self.residuals.nominal_supply_pressure_pa
        else:
            pressure_residual = math.nan
        if all(math.isfinite(value) for value in (pressure, tool_flow, valve, demand)):
            capacity = valve * max(
                0.0,
                pressure - self.residuals.nominal_return_pressure_pa,
            ) / self.residuals.tool_resistance_pa_s_m3
            expected_flow = min(demand, capacity)
            flow_residual = (
                tool_flow - expected_flow
            ) / self.residuals.nominal_tool_flow_m3_s
        else:
            flow_residual = math.nan
        for name, value in (
            ("residual:pressure_fraction", pressure_residual),
            ("residual:flow_fraction", flow_residual),
        ):
            names.append(name)
            values.append(value)
        aggregate_missing = float(np.mean(tuple(missing_by_signal.values())))
        critical_stale = any(
            not math.isfinite(age_by_signal[signal_id])
            or age_by_signal[signal_id] > self.config.maximum_observation_age_s + 1.0e-12
            for signal_id in self.config.critical_signal_ids
        )
        return AttributionFeatureVector(
            names=tuple(names),
            values=np.asarray(values, dtype=float),
            latest_by_signal=latest_by_signal,
            age_by_signal_s=age_by_signal,
            residual_evidence={
                "pressure_fraction": pressure_residual,
                "flow_fraction": flow_residual,
            },
            aggregate_missing_fraction=aggregate_missing,
            critical_signal_stale=critical_stale,
            feature_cutoff_step_index=window.decision_step_index,
            feature_cutoff_timestamp_s=window.decision_timestamp_s,
        )


@dataclass(frozen=True)
class RuleEvidence:
    initiating_scores: Mapping[RootCause, float]
    propagation_scores: Mapping[RootCause, float]
    probability_by_model_cause: Mapping[RootCause, float]
    chain_ids: tuple[str, ...]
    residuals: Mapping[str, float]


def _ramp(severity: float, start: float, full: float) -> float:
    if not math.isfinite(severity):
        return 0.0
    return min(1.0, max(0.0, (severity - start) / (full - start)))


def _softmax(values: np.ndarray) -> np.ndarray:
    shifted = np.asarray(values, dtype=float) - float(np.max(values))
    weights = np.exp(shifted)
    return weights / float(np.sum(weights))


def _js_divergence(first: np.ndarray, second: np.ndarray, clip: float) -> float:
    left = np.clip(np.asarray(first, dtype=float), clip, 1.0)
    right = np.clip(np.asarray(second, dtype=float), clip, 1.0)
    left /= float(np.sum(left))
    right /= float(np.sum(right))
    midpoint = 0.5 * (left + right)
    return float(
        0.5 * np.sum(left * np.log(left / midpoint))
        + 0.5 * np.sum(right * np.log(right / midpoint))
    )


class ResidualRuleEngine:
    """Bounded simulator-consistent signatures with explicit chain evidence."""

    def __init__(self, config: AttributionConfig) -> None:
        self.config = config

    @staticmethod
    def _value(vector: AttributionFeatureVector, signal_id: str) -> float:
        return float(vector.latest_by_signal.get(signal_id, math.nan))

    @staticmethod
    def _feature(vector: AttributionFeatureVector, name: str) -> float:
        try:
            return float(vector.values[vector.names.index(name)])
        except ValueError:
            return math.nan

    def evaluate(self, vector: AttributionFeatureVector) -> RuleEvidence:
        rule = self.config.rules
        residual = self.config.residuals
        grid_voltage = self._value(vector, "electrical.grid_voltage")
        grid_frequency = self._value(vector, "electrical.grid_frequency")
        ups_voltage = self._value(vector, "electrical.ups_output_voltage")
        vfd_output = self._value(vector, "drive.vfd_available_output")
        trip_value = self._value(vector, "drive.vfd_trip_state")
        motor_speed = self._value(vector, "drive.motor_angular_speed")
        valve = self._value(vector, "upw.valve_position")
        demand = self._value(vector, "upw.tool_demand")
        temperature = self._value(vector, "upw.temperature")
        pressure_residual = float(vector.residual_evidence["pressure_fraction"])
        flow_residual = float(vector.residual_evidence["flow_fraction"])

        voltage_deficit = 1.0 - grid_voltage
        interruption = _ramp(
            voltage_deficit,
            1.0 - rule.interruption_start_voltage_pu,
            1.0 - rule.interruption_full_voltage_pu,
        )
        sag = _ramp(
            voltage_deficit,
            rule.grid_sag_start_fraction,
            rule.grid_sag_full_fraction,
        ) * (1.0 - interruption)
        swell = _ramp(
            grid_voltage - 1.0,
            rule.grid_swell_start_fraction,
            rule.grid_swell_full_fraction,
        )
        frequency = _ramp(
            abs(grid_frequency - 50.0),
            rule.frequency_start_hz,
            rule.frequency_full_hz,
        )
        upstream_electrical = max(sag, swell, interruption, frequency)
        nominal_motor = self.config.features.normalization_by_signal[
            "drive.motor_angular_speed"
        ][0]
        motor_loss = _ramp(
            1.0 - motor_speed / nominal_motor,
            rule.motor_loss_start_fraction,
            rule.motor_loss_full_fraction,
        )
        trip = 1.0 if math.isfinite(trip_value) and trip_value >= 0.5 else 0.0
        pump_trip = max(trip, motor_loss) * (1.0 - upstream_electrical)
        valve_loss = _ramp(
            1.0 - valve,
            rule.valve_loss_start_fraction,
            rule.valve_loss_full_fraction,
        )
        demand_gain = _ramp(
            demand / residual.nominal_tool_flow_m3_s - 1.0,
            rule.demand_gain_start_fraction,
            rule.demand_gain_full_fraction,
        )
        thermal = _ramp(
            abs(temperature - self.config.features.normalization_by_signal["upw.temperature"][0]),
            rule.temperature_start_k,
            rule.temperature_full_k,
        )
        physical_scores = (
            sag,
            swell,
            interruption,
            frequency,
            pump_trip,
            valve_loss,
            demand_gain,
            thermal,
        )
        quiet_gate = float(max(physical_scores) <= rule.physical_quiet_max_score)
        pressure_fault = _ramp(
            abs(pressure_residual),
            rule.pressure_residual_start_fraction,
            rule.pressure_residual_full_fraction,
        ) * quiet_gate
        flow_fault = _ramp(
            abs(flow_residual),
            rule.flow_residual_start_fraction,
            rule.flow_residual_full_fraction,
        ) * quiet_gate
        initiating_scores = {
            RootCause.GRID_VOLTAGE_SAG: sag,
            RootCause.GRID_VOLTAGE_SWELL: swell,
            RootCause.GRID_INTERRUPTION: interruption,
            RootCause.GRID_FREQUENCY_DEVIATION: frequency,
            RootCause.PUMP_TRIP: pump_trip,
            RootCause.VALVE_RESTRICTION: valve_loss,
            RootCause.TOOL_DEMAND_SPIKE: demand_gain,
            RootCause.THERMAL_EXCURSION: thermal,
            RootCause.PRESSURE_SENSOR_FAULT: pressure_fault,
            RootCause.FLOW_SENSOR_FAULT: flow_fault,
        }

        battery_slope = self._feature(
            vector,
            "electrical.ups_battery_energy:short_slope",
        )
        ups_separation = abs(ups_voltage - grid_voltage)
        ups_transfer = max(sag, interruption) * max(
            _ramp(ups_separation, 0.05, 0.20),
            _ramp(-battery_slope, 0.001, 0.010),
        )
        vfd_derating = _ramp(
            1.0 - vfd_output,
            rule.propagation_start_fraction,
            rule.propagation_full_fraction,
        )
        propagation_scores = {
            RootCause.UPS_TRANSFER: ups_transfer,
            RootCause.VFD_DERATING: vfd_derating,
        }
        maximum = max(initiating_scores.values())
        unknown_score = max(0.0, 1.0 - maximum)
        logits = np.asarray(
            [initiating_scores[cause] for cause in PRIMARY_INITIATING_CAUSES]
            + [unknown_score],
            dtype=float,
        ) / rule.rule_softmax_temperature
        probabilities = _softmax(logits)
        probability_by_cause = {
            cause: float(probability)
            for cause, probability in zip(MODEL_CAUSES, probabilities, strict=True)
        }
        chain_map = {
            RootCause.GRID_VOLTAGE_SAG: "GRID_SAG_TO_UPS_RESPONSE",
            RootCause.GRID_VOLTAGE_SWELL: "GRID_SWELL_OBSERVED",
            RootCause.GRID_INTERRUPTION: "GRID_LOSS_TO_UPS_RESPONSE",
            RootCause.GRID_FREQUENCY_DEVIATION: "GRID_FREQUENCY_DEVIATION_OBSERVED",
            RootCause.PUMP_TRIP: "VFD_TO_MOTOR_TO_PUMP_LOSS",
            RootCause.VALVE_RESTRICTION: "VALVE_TO_TOOL_FLOW_RESTRICTION",
            RootCause.TOOL_DEMAND_SPIKE: "TOOL_DEMAND_TO_HYDRAULIC_RESPONSE",
            RootCause.THERMAL_EXCURSION: "UPW_THERMAL_DEVIATION_OBSERVED",
            RootCause.PRESSURE_SENSOR_FAULT: "PRESSURE_REDUNDANCY_RESIDUAL",
            RootCause.FLOW_SENSOR_FAULT: "FLOW_REDUNDANCY_RESIDUAL",
        }
        chain_ids = [
            chain_map[cause]
            for cause in PRIMARY_INITIATING_CAUSES
            if initiating_scores[cause] >= 0.50
        ]
        if ups_transfer >= 0.50:
            chain_ids.append("UPS_TRANSFER_PROPAGATION_EVIDENCE")
        if vfd_derating >= 0.50:
            chain_ids.append("VFD_DERATING_PROPAGATION_EVIDENCE")
        return RuleEvidence(
            initiating_scores=initiating_scores,
            propagation_scores=propagation_scores,
            probability_by_model_cause=probability_by_cause,
            chain_ids=tuple(chain_ids),
            residuals={
                "pressure_fraction": (
                    pressure_residual if math.isfinite(pressure_residual) else 0.0
                ),
                "pressure_residual_available": float(math.isfinite(pressure_residual)),
                "flow_fraction": flow_residual if math.isfinite(flow_residual) else 0.0,
                "flow_residual_available": float(math.isfinite(flow_residual)),
            },
        )


class RootCauseEstimator:
    """Frozen RootCauseEstimator 1.0 implementation with conservative gates."""

    interface_version = "1.0.0"
    artifact_version = "1.0.0"

    def __init__(
        self,
        config: AttributionConfig,
        method: AttributionMethod | None = None,
    ) -> None:
        self.config = config
        self.method = method or config.estimator.primary_method
        self.extractor = AttributionFeatureExtractor(config.features, config.residuals)
        self.rules = ResidualRuleEngine(config)
        self.feature_names: tuple[str, ...] | None = None
        self.imputer: Any = None
        self.scaler: Any = None
        self.model: Any = None
        self.calibration_temperature: float = 1.0
        self.fit_group_sha256: str | None = None
        self._last_decision_by_run: dict[str, int] = {}

    @staticmethod
    def _sklearn() -> dict[str, Any]:
        try:
            from sklearn.impute import SimpleImputer
            from sklearn.linear_model import LogisticRegression
            from sklearn.preprocessing import StandardScaler
        except ImportError as exc:
            raise AttributionError("WP13 learned attribution requires scikit-learn") from exc
        return {
            "SimpleImputer": SimpleImputer,
            "LogisticRegression": LogisticRegression,
            "StandardScaler": StandardScaler,
        }

    def reset(self) -> None:
        """Clear online ordering state without discarding fitted parameters."""

        self._last_decision_by_run = {}

    def fit(self, dataset: AttributionDataset) -> RootCauseEstimator:
        """Fit on TRAIN and choose temperature on disjoint CALIBRATION groups."""

        if self.method not in {AttributionMethod.LOGISTIC, AttributionMethod.HYBRID}:
            raise AttributionError("only LOGISTIC and HYBRID attribution methods are fitted")
        dataset.validate()
        train = dataset.subset("TRAIN")
        calibration = dataset.subset("CALIBRATION")
        required = set(MODEL_CAUSES)
        if set(train.labels) != required or set(calibration.labels) != required:
            raise AttributionError("TRAIN and CALIBRATION must each contain every model cause")
        sklearn = self._sklearn()
        self.imputer = sklearn["SimpleImputer"](strategy="median")
        self.scaler = sklearn["StandardScaler"]()
        transformed_train = self.imputer.fit_transform(train.features)
        transformed_train = self.scaler.fit_transform(transformed_train)
        self.model = sklearn["LogisticRegression"](
            C=self.config.model.logistic_c,
            max_iter=self.config.model.max_iter,
            class_weight=self.config.model.class_weight,
            solver="lbfgs",
            random_state=self.config.model.random_seed,
        )
        self.model.fit(transformed_train, np.asarray([label.value for label in train.labels]))
        if set(self.model.classes_) != {cause.value for cause in MODEL_CAUSES}:
            raise AttributionError("fitted attribution classes do not match the frozen vocabulary")
        transformed_calibration = self.scaler.transform(
            self.imputer.transform(calibration.features)
        )
        logits = np.asarray(self.model.decision_function(transformed_calibration), dtype=float)
        label_positions = {
            str(label): index for index, label in enumerate(self.model.classes_)
        }
        truth_indices = np.asarray(
            [label_positions[label.value] for label in calibration.labels], dtype=int
        )
        losses: list[tuple[float, float]] = []
        clip = self.config.fusion.probability_clip
        for temperature in self.config.model.calibration_temperature_grid:
            probabilities = np.vstack([_softmax(row / temperature) for row in logits])
            loss = -float(
                np.mean(
                    np.log(
                        np.clip(
                            probabilities[np.arange(len(probabilities)), truth_indices],
                            clip,
                            1.0,
                        )
                    )
                )
            )
            losses.append((loss, temperature))
        self.calibration_temperature = min(losses)[1]
        self.feature_names = dataset.feature_names
        group_payload = {
            "train": sorted(set(train.run_ids)),
            "calibration": sorted(set(calibration.run_ids)),
        }
        self.fit_group_sha256 = hashlib.sha256(
            json.dumps(group_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        self.reset()
        return self

    def _learned_distribution(
        self,
        vector: AttributionFeatureVector,
    ) -> tuple[dict[RootCause, float], np.ndarray, float]:
        if any(item is None for item in (self.imputer, self.scaler, self.model)):
            raise AttributionError("learned attribution estimator is not fitted")
        if self.feature_names != vector.names:
            raise AttributionError("attribution feature schema differs from the fitted artifact")
        transformed = self.scaler.transform(
            self.imputer.transform(vector.values.reshape(1, -1))
        )
        logits = np.asarray(self.model.decision_function(transformed)[0], dtype=float)
        probabilities = _softmax(logits / self.calibration_temperature)
        by_value = {
            str(label): float(probability)
            for label, probability in zip(self.model.classes_, probabilities, strict=True)
        }
        return (
            {cause: by_value[cause.value] for cause in MODEL_CAUSES},
            transformed[0],
            float(np.max(np.abs(transformed[0]))),
        )

    def _feature_contributions(
        self,
        standardized: np.ndarray,
        cause: RootCause,
    ) -> dict[str, float]:
        if self.model is None or self.feature_names is None:
            return {}
        class_index = list(self.model.classes_).index(cause.value)
        contributions = np.asarray(self.model.coef_[class_index], dtype=float) * standardized
        order = np.argsort(-np.abs(contributions))[:8]
        return {
            f"feature_contribution:{self.feature_names[index]}": float(contributions[index])
            for index in order
        }

    def _pool(
        self,
        learned: Mapping[RootCause, float],
        rule: Mapping[RootCause, float],
    ) -> dict[RootCause, float]:
        clip = self.config.fusion.probability_clip
        weight = self.config.fusion.logistic_weight
        logits = np.asarray(
            [
                weight * math.log(max(clip, learned[cause]))
                + (1.0 - weight) * math.log(max(clip, rule[cause]))
                for cause in MODEL_CAUSES
            ],
            dtype=float,
        )
        probabilities = _softmax(logits)
        return {
            cause: float(probability)
            for cause, probability in zip(MODEL_CAUSES, probabilities, strict=True)
        }

    @staticmethod
    def _force_unknown(
        probabilities: Mapping[RootCause, float],
        minimum_unknown: float,
    ) -> dict[RootCause, float]:
        current_unknown = float(probabilities[RootCause.UNKNOWN])
        target = max(current_unknown, minimum_unknown)
        other_total = sum(
            float(probability)
            for cause, probability in probabilities.items()
            if cause is not RootCause.UNKNOWN
        )
        if other_total <= 1.0e-15:
            return {
                cause: (1.0 if cause is RootCause.UNKNOWN else 0.0)
                for cause in probabilities
            }
        scale = (1.0 - target) / other_total
        return {
            cause: (target if cause is RootCause.UNKNOWN else float(probabilities[cause]) * scale)
            for cause in probabilities
        }

    def _allocate_propagation(
        self,
        base: Mapping[RootCause, float],
        propagation_scores: Mapping[RootCause, float],
    ) -> dict[RootCause, float]:
        maximum_score = max(propagation_scores.values(), default=0.0)
        mass = self.config.fusion.maximum_propagation_probability_mass * maximum_score
        score_sum = sum(propagation_scores.values())
        result = {cause: 0.0 for cause in ALL_CAUSES}
        for cause in MODEL_CAUSES:
            result[cause] = (1.0 - mass) * float(base[cause])
        if score_sum > 0.0:
            for cause in PROPAGATION_EVIDENCE_CAUSES:
                result[cause] = mass * propagation_scores[cause] / score_sum
        return result

    def estimate(
        self,
        observation_window: AttributionObservationWindow,
        prediction: Prediction,
    ) -> Attribution:
        """Emit one canonical attribution without online simulator labels."""

        prior = self._last_decision_by_run.get(observation_window.run_id)
        if prior is not None and observation_window.decision_step_index <= prior:
            raise AttributionError("attribution decisions must advance monotonically within a run")
        vector = self.extractor.transform(observation_window)
        if prediction.feature_cutoff_step_index > observation_window.decision_step_index:
            raise AttributionError("warning feature cutoff is later than attribution cutoff")
        if (
            prediction.feature_cutoff_timestamp_s
            > observation_window.decision_timestamp_s + 1.0e-12
        ):
            raise AttributionError("warning timestamp cutoff is later than attribution cutoff")
        evidence = self.rules.evaluate(vector)
        rule_distribution = dict(evidence.probability_by_model_cause)
        standardized = np.asarray([], dtype=float)
        maximum_standardized = 0.0
        js_divergence = 0.0
        if self.method is AttributionMethod.ALWAYS_UNKNOWN:
            base = {cause: 0.0 for cause in MODEL_CAUSES}
            base[RootCause.UNKNOWN] = 1.0
            learned_distribution: dict[RootCause, float] | None = None
        elif self.method is AttributionMethod.RULE_ONLY:
            base = rule_distribution
            learned_distribution = None
        else:
            learned_distribution, standardized, maximum_standardized = (
                self._learned_distribution(vector)
            )
            if self.method is AttributionMethod.LOGISTIC:
                base = learned_distribution
            else:
                base = self._pool(learned_distribution, rule_distribution)
            js_divergence = _js_divergence(
                np.asarray([learned_distribution[cause] for cause in MODEL_CAUSES]),
                np.asarray([rule_distribution[cause] for cause in MODEL_CAUSES]),
                self.config.fusion.probability_clip,
            )

        ordered_initiators = sorted(
            PRIMARY_INITIATING_CAUSES,
            key=lambda cause: (-base[cause], cause.value),
        )
        top_cause = ordered_initiators[0]
        top_probability = float(base[top_cause])
        second_probability = float(base[ordered_initiators[1]])
        reasons: list[str] = []
        policy = self.config.unknown_policy
        if self.config.estimator.require_positive_warning and not prediction.predicted_excursion:
            reasons.append("ABSTAIN_NO_POSITIVE_WARNING")
        if not prediction.uncertainty_valid:
            reasons.append("ABSTAIN_WARNING_UNCERTAINTY_INVALID")
        if (
            self.config.estimator.require_singleton_positive_conformal_set
            and prediction.conformal_prediction_set != (1,)
        ):
            reasons.append("ABSTAIN_WARNING_SET_NOT_SINGLETON_POSITIVE")
        if vector.critical_signal_stale:
            reasons.append("ABSTAIN_CRITICAL_SENSOR_STALE")
        if (
            vector.aggregate_missing_fraction
            > policy.maximum_aggregate_missing_fraction + 1.0e-12
        ):
            reasons.append("ABSTAIN_EXCESS_MISSINGNESS")
        if maximum_standardized > policy.maximum_standardized_feature_abs:
            reasons.append("ABSTAIN_OUT_OF_DISTRIBUTION")
        if top_probability < policy.minimum_top_probability:
            reasons.append("ABSTAIN_LOW_CONFIDENCE")
        if top_probability - second_probability < policy.minimum_top_two_margin:
            reasons.append("ABSTAIN_LOW_MARGIN")
        if learned_distribution is not None:
            learned_confidence = max(learned_distribution.values())
            rule_confidence = max(rule_distribution.values())
            if (
                learned_confidence >= policy.disagreement_minimum_confidence
                and rule_confidence >= policy.disagreement_minimum_confidence
                and js_divergence > policy.maximum_rule_model_js_divergence
            ):
                reasons.append("ABSTAIN_RULE_MODEL_CONFLICT")
        strong_rules = [
            cause
            for cause, score in evidence.initiating_scores.items()
            if score >= policy.compound_minimum_rule_score
        ]
        if len(strong_rules) >= 2:
            reasons.append("ABSTAIN_COMPOUND_EVIDENCE")

        pre_gate_cause = max(MODEL_CAUSES, key=lambda cause: (base[cause], cause.value))
        if pre_gate_cause is RootCause.UNKNOWN or reasons:
            predicted_cause = RootCause.UNKNOWN
        else:
            predicted_cause = pre_gate_cause
        if reasons:
            base = self._force_unknown(base, policy.forced_unknown_probability)
        probabilities = self._allocate_propagation(base, evidence.propagation_scores)
        if reasons:
            probabilities = self._force_unknown(probabilities, policy.forced_unknown_probability)
        probabilities = {cause: probabilities.get(cause, 0.0) for cause in ALL_CAUSES}

        residuals: dict[str, float] = {
            **evidence.residuals,
            "aggregate_missing_fraction": vector.aggregate_missing_fraction,
            "maximum_standardized_feature_abs": maximum_standardized,
            "rule_model_js_divergence": js_divergence,
        }
        residuals.update(
            {
                f"rule_score:{cause.value}": float(score)
                for cause, score in evidence.initiating_scores.items()
            }
        )
        residuals.update(
            {
                f"propagation_score:{cause.value}": float(score)
                for cause, score in evidence.propagation_scores.items()
            }
        )
        if standardized.size and pre_gate_cause in MODEL_CAUSES:
            residuals.update(self._feature_contributions(standardized, pre_gate_cause))
        chain_ids = tuple(dict.fromkeys((*evidence.chain_ids, *reasons)))
        self._last_decision_by_run[observation_window.run_id] = (
            observation_window.decision_step_index
        )
        return Attribution(
            run_id=observation_window.run_id,
            decision_step_index=observation_window.decision_step_index,
            estimator_id=self.config.estimator.estimator_id,
            predicted_cause=predicted_cause,
            probability_by_cause=probabilities,
            rule_chain_ids=chain_ids,
            residual_evidence=residuals,
            attribution_method=self.method.value,
            causal_proof=False,
        )

    def save(self, path: str | Path) -> None:
        """Serialize a fitted estimator with a mandatory SHA-256 sidecar."""

        if (
            self.method in {AttributionMethod.LOGISTIC, AttributionMethod.HYBRID}
            and self.model is None
        ):
            raise AttributionError("cannot save an unfitted learned attribution estimator")
        destination = Path(path)
        payload = {
            "artifact_version": self.artifact_version,
            "config": self.config.model_dump(mode="json"),
            "method": self.method.value,
            "feature_names": self.feature_names,
            "imputer": self.imputer,
            "scaler": self.scaler,
            "model": self.model,
            "calibration_temperature": self.calibration_temperature,
            "fit_group_sha256": self.fit_group_sha256,
        }
        serialized = pickle.dumps(payload, protocol=pickle.HIGHEST_PROTOCOL)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(serialized)
        destination.with_suffix(destination.suffix + ".sha256").write_text(
            hashlib.sha256(serialized).hexdigest() + "\n",
            encoding="utf-8",
        )

    @classmethod
    def load(cls, path: str | Path) -> RootCauseEstimator:
        """Load a local estimator only after exact checksum verification."""

        source = Path(path)
        sidecar = source.with_suffix(source.suffix + ".sha256")
        try:
            serialized = source.read_bytes()
            expected = sidecar.read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise AttributionError(f"cannot load attribution artifact: {exc}") from exc
        actual = hashlib.sha256(serialized).hexdigest()
        if expected != actual:
            raise AttributionError("attribution artifact checksum does not match its sidecar")
        try:
            payload = pickle.loads(serialized)
        except Exception as exc:
            raise AttributionError(f"invalid attribution artifact payload: {exc}") from exc
        if payload.get("artifact_version") != cls.artifact_version:
            raise AttributionError("unsupported attribution artifact version")
        config = AttributionConfig.model_validate(payload["config"])
        estimator = cls(config, AttributionMethod(payload["method"]))
        estimator.feature_names = payload["feature_names"]
        estimator.imputer = payload["imputer"]
        estimator.scaler = payload["scaler"]
        estimator.model = payload["model"]
        estimator.calibration_temperature = float(payload["calibration_temperature"])
        estimator.fit_group_sha256 = payload["fit_group_sha256"]
        estimator.reset()
        return estimator
