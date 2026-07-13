"""Strict Phase 3 contracts for bounded supervisory control and safety.

This module validates configuration and scientific invariants only. It does
not implement a controller, mutate a plant, or approve an action. Concrete
WP14--WP16 runtime policies are intentionally deferred to Phase 4.
"""

from __future__ import annotations

import hashlib
import math
from enum import Enum
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from semifab_poc.data.schema import QualityFlag


class ControlContractError(ValueError):
    """Raised when a frozen controller/safety contract cannot be validated."""


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, validate_assignment=True)


class ActionType(str, Enum):
    NO_ACTION = "NO_ACTION"
    VFD_COMMAND_ADJUSTMENT = "VFD_COMMAND_ADJUSTMENT"
    VALVE_ADJUSTMENT = "VALVE_ADJUSTMENT"
    CMP_DOWNFORCE_REDUCTION = "CMP_DOWNFORCE_REDUCTION"
    HEAD_SPEED_REDUCTION = "HEAD_SPEED_REDUCTION"
    PLATEN_SPEED_REDUCTION = "PLATEN_SPEED_REDUCTION"
    ADVISORY_WARNING = "ADVISORY_WARNING"
    SAFE_HOLD = "SAFE_HOLD"
    CONTROLLED_RESUME = "CONTROLLED_RESUME"


class SafetyOutcome(str, Enum):
    APPROVED = "APPROVED"
    CLIPPED = "CLIPPED"
    REJECTED_OUT_OF_ENVELOPE = "REJECTED_OUT_OF_ENVELOPE"
    REJECTED_SENSOR_INVALID = "REJECTED_SENSOR_INVALID"
    REJECTED_HIGH_UNCERTAINTY = "REJECTED_HIGH_UNCERTAINTY"
    REPLACED_WITH_HOLD = "REPLACED_WITH_HOLD"


class ReferenceValue(_StrictModel):
    value: float = Field(gt=0.0)
    unit: str = Field(min_length=1)


class PredictorBinding(_StrictModel):
    target_id: str = Field(min_length=1)
    model_kind: str = Field(min_length=1)
    horizon_s: float = Field(gt=0.0)
    artifact_path: Path
    artifact_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    metadata_path: Path
    metadata_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    model_config_path: Path
    model_config_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    required_topology: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_frozen_identity(self) -> PredictorBinding:
        if self.target_id != "SIM_ACTIVE_POLISH_MRR_TRAJECTORY_V1":
            raise ValueError("predictive controller target must remain the frozen WP12 target")
        if self.model_kind != "LOGISTIC":
            raise ValueError("Phase 3 binds the first controller to the logistic artifact")
        if not math.isclose(self.horizon_s, 3.0, rel_tol=0.0, abs_tol=1.0e-12):
            raise ValueError("controller horizon must match the frozen 3.0 s warning horizon")
        if self.required_topology != "DRESSING_WATER_SUPPORT":
            raise ValueError("primary control applicability requires dressing-water support")
        return self


class RiskPolicy(_StrictModel):
    advisory_probability: float = Field(ge=0.0, le=1.0)
    hold_probability: float = Field(ge=0.0, le=1.0)
    resume_maximum_probability: float = Field(ge=0.0, le=1.0)
    require_positive_singleton_for_hold: bool
    require_negative_singleton_for_resume: bool
    maximum_prediction_age_s: float = Field(gt=0.0)

    @model_validator(mode="after")
    def validate_hysteresis(self) -> RiskPolicy:
        if not (
            self.resume_maximum_probability
            < self.advisory_probability
            < self.hold_probability
        ):
            raise ValueError("resume < advisory < hold probability is required")
        if not (
            self.require_positive_singleton_for_hold
            and self.require_negative_singleton_for_resume
        ):
            raise ValueError("hold and resume require the frozen singleton evidence")
        return self


class ActionPolicy(_StrictModel):
    enabled_actions: tuple[ActionType, ...] = Field(min_length=1)
    disabled_actions: dict[ActionType, str]
    states: tuple[str, ...] = Field(min_length=1)
    attribution_is_advisory_only: bool
    reinforcement_learning_allowed: bool

    @model_validator(mode="after")
    def validate_action_partition(self) -> ActionPolicy:
        expected_enabled = {
            ActionType.NO_ACTION,
            ActionType.ADVISORY_WARNING,
            ActionType.SAFE_HOLD,
            ActionType.CONTROLLED_RESUME,
        }
        enabled = set(self.enabled_actions)
        disabled = set(self.disabled_actions)
        if enabled != expected_enabled:
            raise ValueError("primary controller must use the frozen four-action vocabulary")
        if enabled & disabled or enabled | disabled != set(ActionType):
            raise ValueError("enabled and disabled actions must partition the canonical vocabulary")
        if any(not reason.strip() for reason in self.disabled_actions.values()):
            raise ValueError("every disabled action requires a rationale")
        if self.states != ("RUNNING", "HOLDING", "RECOVERING", "COMPLETE"):
            raise ValueError("controller states differ from the frozen state machine")
        if not self.attribution_is_advisory_only:
            raise ValueError("primary attribution must remain advisory-only")
        if self.reinforcement_learning_allowed:
            raise ValueError("reinforcement learning is excluded from the first PoC")
        return self


class PhaseClockPolicy(_StrictModel):
    freeze_states: tuple[str, ...]
    restore_interrupted_phase: bool
    equal_recipe_completion_required: bool
    maximum_extension_s: float = Field(gt=0.0)
    interrupted_dress_route: tuple[str, ...]

    @model_validator(mode="after")
    def validate_phase_clock(self) -> PhaseClockPolicy:
        if self.freeze_states != ("HOLDING", "RECOVERING"):
            raise ValueError("recipe clock must freeze in HOLDING and RECOVERING")
        if not self.restore_interrupted_phase or not self.equal_recipe_completion_required:
            raise ValueError("hold cannot skip phase restoration or equal recipe completion")
        if self.interrupted_dress_route != ("HOLD", "RECOVER", "PREPARE", "DRESS"):
            raise ValueError("interrupted DRESS must use the frozen valid transition route")
        return self


class ObjectiveConfig(_StrictModel):
    method: str = Field(min_length=1)
    expected_excursion_weight: float = Field(gt=0.0)
    phase_delay_weight: float = Field(ge=0.0)
    hold_duration_weight: float = Field(ge=0.0)
    action_transition_weight: float = Field(ge=0.0)
    primary_order: tuple[str, ...]
    evaluation_metrics: tuple[str, ...]

    @model_validator(mode="after")
    def validate_objective(self) -> ObjectiveConfig:
        expected_order = (
            "SAFETY_FEASIBILITY",
            "PREDICTED_EXCURSION_RISK",
            "RECIPE_COMPLETION_AND_CUMULATIVE_REMOVAL",
            "HOLD_RECOVERY_AND_CYCLE_DELAY",
            "ACTION_TRANSITIONS",
        )
        required_metrics = {
            "ACTIVE_POLISH_PEAK_MRR_DEVIATION",
            "ACTIVE_POLISH_INTEGRATED_ABSOLUTE_MRR_ERROR",
            "COMPLETED_RECIPE_CUMULATIVE_REMOVAL_ERROR",
            "HOLD_DURATION",
            "RECOVERY_DURATION",
            "CYCLE_TIME_EXTENSION",
            "ACTION_EFFORT",
        }
        if self.method != "LEXICOGRAPHIC_BOUNDED_ACTION_SEARCH":
            raise ValueError("only the frozen bounded action search is permitted")
        if self.primary_order != expected_order:
            raise ValueError("objective priorities differ from the frozen lexicographic order")
        if set(self.evaluation_metrics) != required_metrics:
            raise ValueError("objective omits a required MRR, removal, hold, or effort metric")
        return self


class LatencyBudget(_StrictModel):
    controller_p95_s: float = Field(gt=0.0)
    end_to_end_p95_s: float = Field(gt=0.0)
    missed_budget_fallback: ActionType

    @model_validator(mode="after")
    def validate_latency(self) -> LatencyBudget:
        if self.controller_p95_s > self.end_to_end_p95_s:
            raise ValueError("controller budget cannot exceed the end-to-end budget")
        if self.missed_budget_fallback is not ActionType.SAFE_HOLD:
            raise ValueError("a missed control latency budget must fail to hold")
        return self


class ControllerEvaluationConfig(_StrictModel):
    controller_development_seed_start: int = Field(ge=0)
    primary_test_seed_start: int = Field(ge=0)
    robustness_seed_start: int = Field(ge=0)
    minimum_runs_per_primary_family: int = Field(gt=0)
    primary_threshold_controller_id: str = Field(min_length=1)
    required_secondary_comparator: str = Field(min_length=1)
    negative_control_families: tuple[str, ...]
    hold_required_families: tuple[str, ...]
    minimum_threshold_relative_improvement: float = Field(ge=0.0, le=1.0)
    maximum_threshold_relative_worsening: float = Field(ge=0.0, le=1.0)
    minimum_hold_required_nonworse_fraction: float = Field(ge=0.0, le=1.0)
    maximum_negative_control_hold_rate: float = Field(ge=0.0, le=1.0)
    bootstrap_confidence: float = Field(gt=0.0, lt=1.0)
    require_nonnegative_no_action_bootstrap_lower_bound: bool
    maximum_cycle_extension_s: float = Field(gt=0.0)
    require_zero_final_constraint_violations: bool
    prohibit_wp12_wp13_seeds_in_primary_test: bool

    @model_validator(mode="after")
    def validate_evaluation_freeze(self) -> ControllerEvaluationConfig:
        starts = (
            self.controller_development_seed_start,
            self.primary_test_seed_start,
            self.robustness_seed_start,
        )
        if len(set(starts)) != 3 or min(starts) < 120_000:
            raise ValueError("controller seed ranges must be distinct from WP12/WP13 roles")
        if self.primary_threshold_controller_id != "PROCESS_MRR_THRESHOLD_HYSTERESIS_V1":
            raise ValueError("primary threshold comparator must act on observed process MRR")
        if self.required_secondary_comparator != "UTILITY_THRESHOLD_HYSTERESIS_V1":
            raise ValueError("the stronger upstream utility comparator is mandatory")
        if self.negative_control_families != ("NORMAL", "HEALTHY_SAG"):
            raise ValueError("negative-control families differ from the Phase 3 freeze")
        if set(self.hold_required_families) != {
            "GRID_INTERRUPTION",
            "PUMP_TRIP",
            "VALVE_RESTRICTION",
            "TOOL_DEMAND_SPIKE",
        }:
            raise ValueError("hold-required families differ from the Phase 3 freeze")
        if not (
            self.require_nonnegative_no_action_bootstrap_lower_bound
            and self.require_zero_final_constraint_violations
            and self.prohibit_wp12_wp13_seeds_in_primary_test
        ):
            raise ValueError("controller evaluation isolation and safety gates are mandatory")
        return self


class PredictiveControllerContract(_StrictModel):
    schema_version: str
    policy_id: str = Field(min_length=1)
    evidence_plane: str
    decision_period_s: float = Field(gt=0.0)
    predictor: PredictorBinding
    risk_policy: RiskPolicy
    action_policy: ActionPolicy
    phase_clock: PhaseClockPolicy
    objective: ObjectiveConfig
    latency_budget: LatencyBudget
    evaluation: ControllerEvaluationConfig

    @model_validator(mode="after")
    def validate_cross_contract(self) -> PredictiveControllerContract:
        if self.schema_version != "1.0.0" or self.evidence_plane != "SYNTHETIC_SIMULATOR":
            raise ValueError("unsupported predictive controller contract identity")
        if not math.isclose(self.decision_period_s, 0.10, rel_tol=0.0, abs_tol=1.0e-12):
            raise ValueError("controller decision period must remain 0.10 s")
        if self.latency_budget.end_to_end_p95_s >= self.decision_period_s:
            raise ValueError("end-to-end budget must be shorter than one decision period")
        if not math.isclose(
            self.phase_clock.maximum_extension_s,
            self.evaluation.maximum_cycle_extension_s,
            rel_tol=0.0,
            abs_tol=1.0e-12,
        ):
            raise ValueError("phase-clock and evaluation extension limits must match")
        return self


class NoActionConfig(_StrictModel):
    controller_id: str = Field(min_length=1)
    preserve_nominal_commands: bool
    request_mode_change: bool


class ProcessThresholdControllerConfig(_StrictModel):
    controller_id: str = Field(min_length=1)
    target_signal_id: str = Field(min_length=1)
    reference_policy: str = Field(min_length=1)
    lower_relative_fraction: float = Field(gt=0.0)
    upper_relative_fraction: float = Field(gt=0.0)
    persistence_s: float = Field(gt=0.0)
    release_lower_relative_fraction: float = Field(gt=0.0)
    release_upper_relative_fraction: float = Field(gt=0.0)
    maximum_observation_age_s: float = Field(gt=0.0)
    active_modes: tuple[str, ...]
    use_arrived_observations_only: bool
    warning_probability_visible: bool
    attribution_visible: bool

    @model_validator(mode="after")
    def validate_process_threshold(self) -> ProcessThresholdControllerConfig:
        if self.controller_id != "PROCESS_MRR_THRESHOLD_HYSTERESIS_V1":
            raise ValueError("unexpected primary process-threshold controller identity")
        if self.target_signal_id != "cmp.mrr":
            raise ValueError("primary threshold comparator must use observed synthetic MRR")
        if self.reference_policy != "PAIRED_EVENT_DISABLED_PHASE_PROGRESS_TRAJECTORY":
            raise ValueError("process threshold requires the frozen phase-progress reference")
        if not (
            self.lower_relative_fraction
            < self.release_lower_relative_fraction
            < 1.0
            < self.release_upper_relative_fraction
            < self.upper_relative_fraction
        ):
            raise ValueError("process-MRR release band must lie inside the hold band")
        if self.active_modes != ("POLISH",):
            raise ValueError("process-MRR threshold is meaningful only in active POLISH")
        if not self.use_arrived_observations_only:
            raise ValueError("process threshold must consume arrived observations only")
        if self.warning_probability_visible or self.attribution_visible:
            raise ValueError("process-threshold baseline cannot see model outputs")
        return self


class UtilityThresholdControllerConfig(_StrictModel):
    controller_id: str = Field(min_length=1)
    hold_persistence_s: float = Field(gt=0.0)
    release_dwell_s: float = Field(gt=0.0)
    low_hold_ratio: float = Field(gt=0.0)
    high_hold_ratio: float = Field(gt=0.0)
    release_lower_ratio: float = Field(gt=0.0)
    release_upper_ratio: float = Field(gt=0.0)
    hold_temperature_deviation_k: float = Field(gt=0.0)
    release_temperature_deviation_k: float = Field(gt=0.0)
    low_ratio_signal_ids: tuple[str, ...] = Field(min_length=1)
    high_ratio_signal_ids: tuple[str, ...] = Field(min_length=1)
    temperature_signal_id: str = Field(min_length=1)
    use_arrived_observations_only: bool
    warning_probability_visible: bool
    attribution_visible: bool

    @model_validator(mode="after")
    def validate_threshold_hysteresis(self) -> UtilityThresholdControllerConfig:
        if self.controller_id != "UTILITY_THRESHOLD_HYSTERESIS_V1":
            raise ValueError("unexpected utility-threshold comparator identity")
        if not self.low_hold_ratio < self.release_lower_ratio <= 1.0:
            raise ValueError("low-side release must be inside the hold threshold")
        if not 1.0 <= self.release_upper_ratio < self.high_hold_ratio:
            raise ValueError("high-side release must be inside the hold threshold")
        if self.release_temperature_deviation_k >= self.hold_temperature_deviation_k:
            raise ValueError("temperature release band must be narrower than hold band")
        if not self.use_arrived_observations_only:
            raise ValueError("threshold controller must consume arrived observations only")
        if self.warning_probability_visible or self.attribution_visible:
            raise ValueError("fixed-threshold baseline cannot see model outputs")
        return self


class BaselineControllerContract(_StrictModel):
    schema_version: str
    evidence_plane: str
    decision_period_s: float = Field(gt=0.0)
    no_action: NoActionConfig
    process_threshold: ProcessThresholdControllerConfig
    utility_threshold_comparator: UtilityThresholdControllerConfig
    references: dict[str, ReferenceValue]
    resume_uses_independent_safety_contract: bool

    @model_validator(mode="after")
    def validate_baseline(self) -> BaselineControllerContract:
        required_references = {
            "electrical.ups_output_voltage",
            "drive.motor_angular_speed",
            "pump.volumetric_flow",
            "upw.supply_pressure",
            "upw.tool_flow",
            "upw.temperature",
        }
        if self.schema_version != "1.0.0" or self.evidence_plane != "SYNTHETIC_SIMULATOR":
            raise ValueError("unsupported baseline controller contract identity")
        if set(self.references) != required_references:
            raise ValueError("baseline references must contain the frozen signal set")
        if not self.no_action.preserve_nominal_commands or self.no_action.request_mode_change:
            raise ValueError("no-action baseline must preserve commands and modes")
        if not self.resume_uses_independent_safety_contract:
            raise ValueError("baseline resume cannot bypass the safety filter")
        return self


class ObservationValidityConfig(_StrictModel):
    blocking_quality_flags: tuple[QualityFlag, ...]
    conditionally_allowed_quality_flags: tuple[QualityFlag, ...]
    maximum_age_s_by_signal: dict[str, float]
    required_for_non_hold_actuation: tuple[str, ...]
    hold_allowed_when_observations_invalid: bool

    @model_validator(mode="after")
    def validate_observation_policy(self) -> ObservationValidityConfig:
        expected_blocking = {
            QualityFlag.MISSING,
            QualityFlag.DROPPED,
            QualityFlag.STUCK,
            QualityFlag.BIASED,
            QualityFlag.DRIFTING,
            QualityFlag.OUT_OF_RANGE,
            QualityFlag.UNIT_UNRESOLVED,
            QualityFlag.INVALID,
        }
        expected_conditional = {
            QualityFlag.DELAYED,
            QualityFlag.QUANTISED,
            QualityFlag.TIMESTAMP_JITTERED,
        }
        if set(self.blocking_quality_flags) != expected_blocking:
            raise ValueError("blocking sensor-quality flags differ from the safety freeze")
        if set(self.conditionally_allowed_quality_flags) != expected_conditional:
            raise ValueError("conditional sensor-quality flags differ from the safety freeze")
        if set(self.required_for_non_hold_actuation) != set(self.maximum_age_s_by_signal):
            raise ValueError("every required actuation signal needs an age limit")
        if any(value <= 0.0 or not math.isfinite(value) for value in self.maximum_age_s_by_signal.values()):
            raise ValueError("sensor maximum ages must be finite and positive")
        if not self.hold_allowed_when_observations_invalid:
            raise ValueError("safe hold must remain available under sensor invalidity")
        return self


class UncertaintyApplicabilityConfig(_StrictModel):
    predictor_target_id: str
    predictor_artifact_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    predictor_metadata_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    predictor_config_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    required_topology: str
    maximum_prediction_age_s: float = Field(gt=0.0)
    hold_probability: float = Field(ge=0.0, le=1.0)
    resume_maximum_probability: float = Field(ge=0.0, le=1.0)
    positive_hold_set: tuple[int, ...]
    negative_resume_set: tuple[int, ...]
    feature_cutoff_must_not_exceed_decision: bool
    topology_config_and_feature_schema_must_match: bool

    @model_validator(mode="after")
    def validate_uncertainty(self) -> UncertaintyApplicabilityConfig:
        if self.positive_hold_set != (1,) or self.negative_resume_set != (0,):
            raise ValueError("safety requires positive/negative singleton sets")
        if self.resume_maximum_probability >= self.hold_probability:
            raise ValueError("resume probability must remain below hold probability")
        if not (
            self.feature_cutoff_must_not_exceed_decision
            and self.topology_config_and_feature_schema_must_match
        ):
            raise ValueError("feature-cutoff and applicability binding are mandatory")
        return self


class ContinuationEnvelope(_StrictModel):
    hold_persistence_s: float = Field(gt=0.0)
    low_ratio: float = Field(gt=0.0)
    high_ratio: float = Field(gt=0.0)
    maximum_temperature_deviation_k: float = Field(gt=0.0)
    automatic_hold_modes: tuple[str, ...]

    @model_validator(mode="after")
    def validate_automatic_hold_modes(self) -> ContinuationEnvelope:
        if self.automatic_hold_modes != ("PREPARE", "POLISH"):
            raise ValueError("utility continuation hold must not preempt the DRESS comparison")
        return self


class ReleaseEnvelope(_StrictModel):
    continuous_valid_dwell_s: float = Field(gt=0.0)
    lower_ratio: float = Field(gt=0.0)
    upper_ratio: float = Field(gt=0.0)
    maximum_temperature_deviation_k: float = Field(gt=0.0)
    require_vfd_not_tripped: bool
    battery_reserve_factor: float = Field(gt=1.0)
    prediction_clear_dwell_s: float = Field(gt=0.0)


class SafetyStateMachine(_StrictModel):
    states: tuple[str, ...]
    minimum_hold_s: float = Field(gt=0.0)
    recovery_dwell_s: float = Field(gt=0.0)
    freeze_recipe_clock_in: tuple[str, ...]
    restore_interrupted_phase: bool
    invalid_recovery_returns_to_hold: bool
    terminal_complete: bool

    @model_validator(mode="after")
    def validate_state_machine(self) -> SafetyStateMachine:
        if self.states != ("RUNNING", "HOLD", "RECOVER", "COMPLETE"):
            raise ValueError("safety-filter states differ from the frozen state machine")
        if self.freeze_recipe_clock_in != ("HOLD", "RECOVER"):
            raise ValueError("recipe clock must freeze during hold and recovery")
        if not (
            self.restore_interrupted_phase
            and self.invalid_recovery_returns_to_hold
            and self.terminal_complete
        ):
            raise ValueError("state-machine fallback and terminal rules are mandatory")
        return self


class NumericActionEnvelope(_StrictModel):
    target: str = Field(min_length=1)
    unit: str = Field(min_length=1)
    minimum: float
    maximum: float
    maximum_step_change: float = Field(gt=0.0)
    maximum_slew_per_s: float = Field(gt=0.0)
    allowed_modes: tuple[str, ...] = Field(min_length=1)
    primary_enabled: bool

    @model_validator(mode="after")
    def validate_numeric_envelope(self) -> NumericActionEnvelope:
        if not all(math.isfinite(value) for value in (self.minimum, self.maximum)):
            raise ValueError("numeric action bounds must be finite")
        if self.minimum >= self.maximum:
            raise ValueError("numeric action minimum must be below maximum")
        if set(self.allowed_modes) - {"PREPARE", "POLISH"}:
            raise ValueError("numeric reduction action is outside PREPARE/POLISH")
        return self


class NonNumericActionEnvelope(_StrictModel):
    target: str = Field(min_length=1)
    unit: str = Field(min_length=1)
    allowed_modes: tuple[str, ...] = Field(min_length=1)


class FallbackConfig(_StrictModel):
    active_recipe_sensor_invalid: ActionType
    active_recipe_high_uncertainty: ActionType
    inactive_or_complete_invalid: ActionType
    latency_budget_missed: ActionType

    @model_validator(mode="after")
    def validate_fallbacks(self) -> FallbackConfig:
        if {
            self.active_recipe_sensor_invalid,
            self.active_recipe_high_uncertainty,
            self.latency_budget_missed,
        } != {ActionType.SAFE_HOLD}:
            raise ValueError("active invalidity and latency fallbacks must be SAFE_HOLD")
        if self.inactive_or_complete_invalid is not ActionType.NO_ACTION:
            raise ValueError("inactive invalidity fallback must be NO_ACTION")
        return self


class SafetyFilterContract(_StrictModel):
    schema_version: str
    constraint_set_id: str = Field(min_length=1)
    evidence_plane: str
    decision_period_s: float = Field(gt=0.0)
    outcomes: tuple[SafetyOutcome, ...]
    observation_validity: ObservationValidityConfig
    uncertainty_and_applicability: UncertaintyApplicabilityConfig
    references: dict[str, ReferenceValue]
    continuation_envelope: ContinuationEnvelope
    release_envelope: ReleaseEnvelope
    state_machine: SafetyStateMachine
    action_envelopes: dict[ActionType, NumericActionEnvelope]
    non_numeric_actions: dict[ActionType, NonNumericActionEnvelope]
    fallbacks: FallbackConfig
    final_action_required: bool
    controller_imports_forbidden: bool

    @model_validator(mode="after")
    def validate_safety_contract(self) -> SafetyFilterContract:
        numeric_actions = {
            ActionType.VFD_COMMAND_ADJUSTMENT,
            ActionType.VALVE_ADJUSTMENT,
            ActionType.CMP_DOWNFORCE_REDUCTION,
            ActionType.HEAD_SPEED_REDUCTION,
            ActionType.PLATEN_SPEED_REDUCTION,
        }
        non_numeric_actions = {
            ActionType.NO_ACTION,
            ActionType.ADVISORY_WARNING,
            ActionType.SAFE_HOLD,
            ActionType.CONTROLLED_RESUME,
        }
        if self.schema_version != "1.0.0" or self.evidence_plane != "SYNTHETIC_SIMULATOR":
            raise ValueError("unsupported safety-filter contract identity")
        if set(self.outcomes) != set(SafetyOutcome) or len(self.outcomes) != len(SafetyOutcome):
            raise ValueError("safety contract must contain every canonical outcome once")
        if set(self.action_envelopes) != numeric_actions:
            raise ValueError("numeric safety envelopes do not match canonical actions")
        if set(self.non_numeric_actions) != non_numeric_actions:
            raise ValueError("non-numeric safety envelopes do not match canonical actions")
        for envelope in self.action_envelopes.values():
            if envelope.primary_enabled:
                raise ValueError("numeric actions must remain disabled in the primary WP15 policy")
            expected_step = envelope.maximum_slew_per_s * self.decision_period_s
            if not math.isclose(
                envelope.maximum_step_change,
                expected_step,
                rel_tol=0.0,
                abs_tol=1.0e-12,
            ):
                raise ValueError("per-step action limit must equal slew times decision period")
        continuation = self.continuation_envelope
        release = self.release_envelope
        if not continuation.low_ratio < release.lower_ratio <= 1.0:
            raise ValueError("release lower ratio must lie inside continuation envelope")
        if not 1.0 <= release.upper_ratio < continuation.high_ratio:
            raise ValueError("release upper ratio must lie inside continuation envelope")
        if release.maximum_temperature_deviation_k >= (
            continuation.maximum_temperature_deviation_k
        ):
            raise ValueError("release temperature band must be narrower")
        if not self.final_action_required or not self.controller_imports_forbidden:
            raise ValueError("final action and controller independence are mandatory")
        return self


class ControlContractBundle(_StrictModel):
    predictive: PredictiveControllerContract
    baselines: BaselineControllerContract
    safety: SafetyFilterContract

    @model_validator(mode="after")
    def validate_bundle_consistency(self) -> ControlContractBundle:
        periods = {
            self.predictive.decision_period_s,
            self.baselines.decision_period_s,
            self.safety.decision_period_s,
        }
        if len(periods) != 1:
            raise ValueError("all controller and safety decision periods must match")
        predictor = self.predictive.predictor
        uncertainty = self.safety.uncertainty_and_applicability
        binding_pairs = (
            (predictor.target_id, uncertainty.predictor_target_id),
            (predictor.artifact_sha256, uncertainty.predictor_artifact_sha256),
            (predictor.metadata_sha256, uncertainty.predictor_metadata_sha256),
            (predictor.model_config_sha256, uncertainty.predictor_config_sha256),
            (predictor.required_topology, uncertainty.required_topology),
        )
        if any(left != right for left, right in binding_pairs):
            raise ValueError("predictive and safety artifact/applicability bindings differ")
        risk = self.predictive.risk_policy
        if not math.isclose(
            risk.hold_probability,
            uncertainty.hold_probability,
            rel_tol=0.0,
            abs_tol=1.0e-12,
        ) or not math.isclose(
            risk.resume_maximum_probability,
            uncertainty.resume_maximum_probability,
            rel_tol=0.0,
            abs_tol=1.0e-12,
        ):
            raise ValueError("controller and safety probability thresholds differ")
        if not math.isclose(
            risk.maximum_prediction_age_s,
            uncertainty.maximum_prediction_age_s,
            rel_tol=0.0,
            abs_tol=1.0e-12,
        ):
            raise ValueError("controller and safety prediction-age limits differ")
        if self.baselines.references != self.safety.references:
            raise ValueError("baseline and safety physical references differ")
        process_threshold = self.baselines.process_threshold
        utility_threshold = self.baselines.utility_threshold_comparator
        continuation = self.safety.continuation_envelope
        release = self.safety.release_envelope
        if (
            process_threshold.controller_id
            != self.predictive.evaluation.primary_threshold_controller_id
        ):
            raise ValueError("primary process-threshold comparator identity differs")
        if (
            utility_threshold.controller_id
            != self.predictive.evaluation.required_secondary_comparator
        ):
            raise ValueError("required utility-threshold comparator identity differs")
        threshold_pairs = (
            (utility_threshold.hold_persistence_s, continuation.hold_persistence_s),
            (utility_threshold.low_hold_ratio, continuation.low_ratio),
            (utility_threshold.high_hold_ratio, continuation.high_ratio),
            (
                utility_threshold.hold_temperature_deviation_k,
                continuation.maximum_temperature_deviation_k,
            ),
            (utility_threshold.release_dwell_s, release.continuous_valid_dwell_s),
            (utility_threshold.release_lower_ratio, release.lower_ratio),
            (utility_threshold.release_upper_ratio, release.upper_ratio),
            (
                utility_threshold.release_temperature_deviation_k,
                release.maximum_temperature_deviation_k,
            ),
        )
        if any(
            not math.isclose(left, right, rel_tol=0.0, abs_tol=1.0e-12)
            for left, right in threshold_pairs
        ):
            raise ValueError("baseline threshold and independent safety envelopes differ")
        if set(self.predictive.action_policy.disabled_actions) != set(
            self.safety.action_envelopes
        ):
            raise ValueError("disabled primary actions and numeric safety envelopes differ")
        return self


def _read_yaml_mapping(path: Path) -> dict[str, Any]:
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ControlContractError(f"cannot load control contract {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ControlContractError(f"control contract root must be a mapping: {path}")
    return payload


def _load(model_type: type[_StrictModel], path: str | Path) -> _StrictModel:
    contract_path = Path(path)
    try:
        return model_type.model_validate(_read_yaml_mapping(contract_path))
    except ControlContractError:
        raise
    except Exception as exc:
        raise ControlContractError(f"invalid control contract {contract_path}: {exc}") from exc


def load_predictive_controller_contract(path: str | Path) -> PredictiveControllerContract:
    return PredictiveControllerContract.model_validate(
        _load(PredictiveControllerContract, path).model_dump()
    )


def load_baseline_controller_contract(path: str | Path) -> BaselineControllerContract:
    return BaselineControllerContract.model_validate(
        _load(BaselineControllerContract, path).model_dump()
    )


def load_safety_filter_contract(path: str | Path) -> SafetyFilterContract:
    return SafetyFilterContract.model_validate(_load(SafetyFilterContract, path).model_dump())


def load_control_contract_bundle(
    predictive_path: str | Path,
    baselines_path: str | Path,
    safety_path: str | Path,
) -> ControlContractBundle:
    return ControlContractBundle(
        predictive=load_predictive_controller_contract(predictive_path),
        baselines=load_baseline_controller_contract(baselines_path),
        safety=load_safety_filter_contract(safety_path),
    )


def file_sha256(path: str | Path) -> str:
    """Return the exact SHA-256 of a local contract-bound artifact."""

    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_predictor_binding(
    contract: PredictiveControllerContract,
    repository_root: str | Path,
) -> None:
    """Verify exact bytes for every model artifact bound by Phase 3."""

    root = Path(repository_root)
    binding = contract.predictor
    checks = (
        (binding.artifact_path, binding.artifact_sha256),
        (binding.metadata_path, binding.metadata_sha256),
        (binding.model_config_path, binding.model_config_sha256),
    )
    for relative_path, expected in checks:
        path = root / relative_path
        if not path.is_file():
            raise ControlContractError(f"bound predictor artifact is missing: {relative_path}")
        actual = file_sha256(path)
        if actual != expected:
            raise ControlContractError(
                f"bound predictor artifact checksum differs: {relative_path}"
            )


def verify_canonical_vocabularies(
    contract: SafetyFilterContract,
    canonical_schema_path: str | Path,
) -> None:
    """Check that code/config enums equal the frozen canonical YAML vocabulary."""

    schema = _read_yaml_mapping(Path(canonical_schema_path))
    try:
        enumerations = schema["enumerations"]
        schema_actions = set(enumerations["action_type"])
        schema_outcomes = set(enumerations["safety_outcome"])
    except (KeyError, TypeError) as exc:
        raise ControlContractError("canonical schema lacks control vocabularies") from exc
    if schema_actions != {item.value for item in ActionType}:
        raise ControlContractError("code action vocabulary differs from canonical schema")
    if schema_outcomes != {item.value for item in SafetyOutcome}:
        raise ControlContractError("code safety vocabulary differs from canonical schema")
    if {item.value for item in contract.outcomes} != schema_outcomes:
        raise ControlContractError("safety configuration outcomes differ from canonical schema")
