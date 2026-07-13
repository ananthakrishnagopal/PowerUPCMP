"""WP14 baseline controllers."""

from __future__ import annotations

import uuid
from typing import Any

from semifab_poc.control.base import ActionRecord, Controller
from semifab_poc.control.contracts import ActionType, BaselineControllerContract
from semifab_poc.data.schema import QualityFlag
from semifab_poc.models.early_warning import Prediction, WarningObservationWindow


class NoActionController(Controller):
    """Frozen WP14 no-action baseline."""

    def __init__(self, config: BaselineControllerContract) -> None:
        self.config = config.no_action
        self.controller_id = self.config.controller_id

    def reset(self) -> None:
        pass

    def act(
        self,
        observation: WarningObservationWindow,
        prediction: Prediction | None,
        constraints: Any,
    ) -> ActionRecord:
        return ActionRecord(
            run_id=observation.run_id,
            decision_step_index=observation.decision_step_index,
            effective_step_index=observation.decision_step_index + 1,
            stage="PROPOSED",
            action_id=str(uuid.uuid4()),
            action_type=ActionType.NO_ACTION,
            target="supervisory.none",
            value=None,
            unit="1",
            rationale="NO_ACTION baseline preserves nominal commands",
            controller_id=self.controller_id,
        )


class ProcessMrrThresholdController(Controller):
    """Frozen WP14 process-MRR hysteresis threshold comparator."""

    def __init__(self, config: BaselineControllerContract) -> None:
        self.config = config.process_threshold
        self.controller_id = self.config.controller_id
        self.held = False
        self.violation_start_s: float | None = None

    def reset(self) -> None:
        self.held = False
        self.violation_start_s = None

    def _get_mrr_reference(self, observation: WarningObservationWindow) -> float:
        # PAIRED_EVENT_DISABLED_PHASE_PROGRESS_TRAJECTORY
        # Simplified reference for baseline testing (normally provided by simulator reference trace)
        # Using a dummy nominal value for now; tests will mock or supply valid normalized inputs
        return 2.0e-8

    def act(
        self,
        observation: WarningObservationWindow,
        prediction: Prediction | None,
        constraints: Any,
    ) -> ActionRecord:
        
        # Default to no action unless threshold is breached
        action_type = ActionType.NO_ACTION
        target = "supervisory.none"
        rationale = "Process MRR within threshold"

        mrr_obs = None
        for obs in observation.observations:
            if obs.signal_id == self.config.target_signal_id:
                if mrr_obs is None or obs.arrival_timestamp_s > mrr_obs.arrival_timestamp_s:
                    mrr_obs = obs

        if observation.process_mode not in self.config.active_modes:
            self.violation_start_s = None
        elif mrr_obs is not None:
            age = observation.decision_timestamp_s - mrr_obs.observed_timestamp_s
            valid = True
            if age > self.config.maximum_observation_age_s:
                valid = False
            if QualityFlag.MISSING in mrr_obs.quality_flags or QualityFlag.INVALID in mrr_obs.quality_flags:
                valid = False

            if valid and mrr_obs.value is not None:
                mrr = float(mrr_obs.value)
                ref = self._get_mrr_reference(observation)
                
                ratio = mrr / ref if ref > 0 else 1.0

                if not self.held:
                    if ratio < self.config.lower_relative_fraction or ratio > self.config.upper_relative_fraction:
                        if self.violation_start_s is None:
                            self.violation_start_s = observation.decision_timestamp_s
                        elif (observation.decision_timestamp_s - self.violation_start_s) >= self.config.persistence_s:
                            self.held = True
                            action_type = ActionType.SAFE_HOLD
                            target = "cmp.process_mode"
                            rationale = f"MRR ratio {ratio:.3f} breached threshold limits"
                    else:
                        self.violation_start_s = None
                else:
                    if self.config.release_lower_relative_fraction <= ratio <= self.config.release_upper_relative_fraction:
                        # Resume logic
                        self.held = False
                        action_type = ActionType.CONTROLLED_RESUME
                        target = "cmp.process_mode"
                        rationale = f"MRR ratio {ratio:.3f} recovered inside release limits"
                        self.violation_start_s = None
                    else:
                        action_type = ActionType.SAFE_HOLD
                        target = "cmp.process_mode"
                        rationale = "Remaining held due to out of release bounds"

        if self.held and action_type == ActionType.NO_ACTION:
            action_type = ActionType.SAFE_HOLD
            target = "cmp.process_mode"
            rationale = "Maintained HOLD"

        return ActionRecord(
            run_id=observation.run_id,
            decision_step_index=observation.decision_step_index,
            effective_step_index=observation.decision_step_index + 1,
            stage="PROPOSED",
            action_id=str(uuid.uuid4()),
            action_type=action_type,
            target=target,
            value=None,
            unit="1",
            rationale=rationale,
            controller_id=self.controller_id,
        )


class UtilityThresholdController(Controller):
    """Frozen WP14 upstream utility threshold comparator."""

    def __init__(self, config: BaselineControllerContract) -> None:
        self.config = config.utility_threshold_comparator
        self.references = config.references
        self.controller_id = self.config.controller_id
        self.held = False
        self.violation_start_s: float | None = None
        self.recovery_start_s: float | None = None

    def reset(self) -> None:
        self.held = False
        self.violation_start_s = None
        self.recovery_start_s = None

    def _get_obs(self, observation: WarningObservationWindow, signal_id: str):
        best = None
        for obs in observation.observations:
            if obs.signal_id == signal_id:
                if best is None or obs.arrival_timestamp_s > best.arrival_timestamp_s:
                    best = obs
        return best

    def act(
        self,
        observation: WarningObservationWindow,
        prediction: Prediction | None,
        constraints: Any,
    ) -> ActionRecord:
        
        breach = False
        recover = True

        for sig in self.config.low_ratio_signal_ids + self.config.high_ratio_signal_ids + (self.config.temperature_signal_id,):
            obs = self._get_obs(observation, sig)
            if not obs or obs.value is None or QualityFlag.MISSING in obs.quality_flags:
                breach = True
                recover = False
                continue
            
            val = float(obs.value)
            ref = self.references[sig].value
            
            if sig == self.config.temperature_signal_id:
                dev = abs(val - ref)
                if dev > self.config.hold_temperature_deviation_k:
                    breach = True
                if dev > self.config.release_temperature_deviation_k:
                    recover = False
            else:
                ratio = val / ref if ref > 0 else 1.0
                if sig in self.config.low_ratio_signal_ids and ratio < self.config.low_hold_ratio:
                    breach = True
                if sig in self.config.high_ratio_signal_ids and ratio > self.config.high_hold_ratio:
                    breach = True
                
                if ratio < self.config.release_lower_ratio or ratio > self.config.release_upper_ratio:
                    recover = False

        action_type = ActionType.NO_ACTION
        target = "supervisory.none"
        rationale = "Utility parameters nominal"

        if not self.held:
            if breach:
                if self.violation_start_s is None:
                    self.violation_start_s = observation.decision_timestamp_s
                elif (observation.decision_timestamp_s - self.violation_start_s) >= self.config.hold_persistence_s:
                    self.held = True
                    action_type = ActionType.SAFE_HOLD
                    target = "cmp.process_mode"
                    rationale = "Utility threshold breached"
            else:
                self.violation_start_s = None
        else:
            if recover:
                if self.recovery_start_s is None:
                    self.recovery_start_s = observation.decision_timestamp_s
                elif (observation.decision_timestamp_s - self.recovery_start_s) >= self.config.release_dwell_s:
                    self.held = False
                    action_type = ActionType.CONTROLLED_RESUME
                    target = "cmp.process_mode"
                    rationale = "Utility threshold recovered"
                    self.recovery_start_s = None
                    self.violation_start_s = None
                else:
                    action_type = ActionType.SAFE_HOLD
                    target = "cmp.process_mode"
                    rationale = "Recovering, dwell not met"
            else:
                self.recovery_start_s = None
                action_type = ActionType.SAFE_HOLD
                target = "cmp.process_mode"
                rationale = "Remaining held due to utility breach"

        return ActionRecord(
            run_id=observation.run_id,
            decision_step_index=observation.decision_step_index,
            effective_step_index=observation.decision_step_index + 1,
            stage="PROPOSED",
            action_id=str(uuid.uuid4()),
            action_type=action_type,
            target=target,
            value=None,
            unit="1",
            rationale=rationale,
            controller_id=self.controller_id,
        )
