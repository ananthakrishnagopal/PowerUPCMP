"""WP16 independent safety filter."""

from __future__ import annotations

from typing import Any
import uuid
import time

from semifab_poc.control.base import ActionRecord, SafetyDecisionRecord, SafetyFilter
from semifab_poc.control.contracts import ActionType, SafetyFilterContract, SafetyOutcome
from semifab_poc.models.early_warning import Prediction, WarningObservationWindow


class SafetyFilterImpl(SafetyFilter):
    """Frozen WP16 independent safety guard."""

    def __init__(self, config: SafetyFilterContract) -> None:
        self.config = config
        self.state = "RUNNING"
        self.last_action: ActionRecord | None = None
        self.hold_start_s: float | None = None
        self.recovery_start_s: float | None = None
        
    def reset(self) -> None:
        self.state = "RUNNING"
        self.last_action = None
        self.hold_start_s = None
        self.recovery_start_s = None

    def validate(
        self,
        proposed_action: ActionRecord,
        observation: WarningObservationWindow,
        uncertainty: Prediction | None,
        constraints: Any,
    ) -> SafetyDecisionRecord:
        
        violated_constraints = []
        sensor_valid = True
        uncertainty_acceptable = True
        process_envelope_valid = True
        outcome = SafetyOutcome.APPROVED

        # Track state updates based on observed mode
        mode = observation.process_mode
        if mode == "COMPLETE":
            self.state = "COMPLETE"

        # Check mandatory hold conditions
        is_hold_proposal = proposed_action.action_type == ActionType.SAFE_HOLD

        # Basic invalidity checks
        if proposed_action.stage != "PROPOSED":
            violated_constraints.append("stage_must_be_proposed")
            outcome = SafetyOutcome.REJECTED_OUT_OF_ENVELOPE

        if proposed_action.effective_step_index < observation.decision_step_index + 1:
            violated_constraints.append("timing_must_be_future")
            outcome = SafetyOutcome.REJECTED_OUT_OF_ENVELOPE

        # If it's a numeric action
        if proposed_action.action_type in self.config.action_envelopes:
            env = self.config.action_envelopes[proposed_action.action_type]
            if mode not in env.allowed_modes:
                violated_constraints.append("mode_not_allowed")
                process_envelope_valid = False
                outcome = SafetyOutcome.REJECTED_OUT_OF_ENVELOPE
            elif proposed_action.value is not None:
                if proposed_action.value < env.minimum or proposed_action.value > env.maximum:
                    outcome = SafetyOutcome.REJECTED_OUT_OF_ENVELOPE
                    violated_constraints.append("hard_magnitude_exceeded")
                # clip logic could go here

        if not is_hold_proposal:
            # Check sensor valid for non-hold actuation
            if not observation.observations and self.config.observation_validity.required_for_non_hold_actuation:
                sensor_valid = False
            
            if not sensor_valid:
                outcome = SafetyOutcome.REJECTED_SENSOR_INVALID
                
            # Check uncertainty for active risk/resume
            if proposed_action.action_type == ActionType.CONTROLLED_RESUME:
                if uncertainty is None or not uncertainty.uncertainty_valid:
                    uncertainty_acceptable = False
                    outcome = SafetyOutcome.REJECTED_HIGH_UNCERTAINTY
                elif uncertainty.probability > self.config.uncertainty_and_applicability.resume_maximum_probability:
                    uncertainty_acceptable = False
                    outcome = SafetyOutcome.REJECTED_HIGH_UNCERTAINTY

        if outcome != SafetyOutcome.APPROVED:
            # Apply fallbacks
            if not sensor_valid and mode in ("PREPARE", "POLISH"):
                outcome = SafetyOutcome.REPLACED_WITH_HOLD
                final_action_type = ActionType.SAFE_HOLD
            elif not uncertainty_acceptable:
                outcome = SafetyOutcome.REPLACED_WITH_HOLD
                final_action_type = ActionType.SAFE_HOLD
            else:
                final_action_type = ActionType.NO_ACTION if mode not in ("PREPARE", "POLISH") else ActionType.SAFE_HOLD
                
            final_target = "cmp.process_mode" if final_action_type == ActionType.SAFE_HOLD else "supervisory.none"
            final_value = None
            final_unit = "1"
        else:
            final_action_type = proposed_action.action_type
            final_target = proposed_action.target
            final_value = proposed_action.value
            final_unit = proposed_action.unit
            
            # If the original was hold, transition our state
            if is_hold_proposal and self.state != "HOLD":
                self.state = "HOLD"
                self.hold_start_s = observation.decision_timestamp_s
            elif final_action_type == ActionType.CONTROLLED_RESUME:
                self.state = "RECOVER"
                self.recovery_start_s = observation.decision_timestamp_s

        if final_action_type == ActionType.SAFE_HOLD:
            outcome = SafetyOutcome.REPLACED_WITH_HOLD if not is_hold_proposal else SafetyOutcome.APPROVED

        self.last_action = ActionRecord(
            run_id=observation.run_id,
            decision_step_index=observation.decision_step_index,
            effective_step_index=observation.decision_step_index + 1,
            stage="FINAL",
            action_id=str(uuid.uuid4()),
            action_type=final_action_type,
            target=final_target,
            value=final_value,
            unit=final_unit,
            rationale="Safety filter final disposition",
            controller_id=proposed_action.controller_id
        )

        return SafetyDecisionRecord(
            run_id=observation.run_id,
            decision_step_index=observation.decision_step_index,
            proposed_action_id=proposed_action.action_id,
            outcome=outcome,
            final_action_id=self.last_action.action_id,
            violated_constraint_ids=tuple(violated_constraints),
            sensor_valid=sensor_valid,
            uncertainty_acceptable=uncertainty_acceptable,
            process_envelope_valid=process_envelope_valid,
            latency_s=0.001
        )
