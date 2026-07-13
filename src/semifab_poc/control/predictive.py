"""WP15 predictive supervisory controller."""

from __future__ import annotations

import uuid
from typing import Any

from semifab_poc.control.base import ActionRecord, Controller
from semifab_poc.control.contracts import ActionType, PredictiveControllerContract
from semifab_poc.models.early_warning import Prediction, WarningObservationWindow


class PredictiveSupervisor(Controller):
    """Frozen WP15 predictive supervisory controller."""

    def __init__(self, config: PredictiveControllerContract) -> None:
        self.config = config
        self.state = "RUNNING"
        self.controller_id = self.config.policy_id
        
        # State tracking for phase clock simulation
        self.held_at_s: float | None = None
        self.interrupted_mode: str | None = None

    def reset(self) -> None:
        self.state = "RUNNING"
        self.held_at_s = None
        self.interrupted_mode = None

    def _is_applicable(self, prediction: Prediction | None, observation: WarningObservationWindow) -> bool:
        if prediction is None:
            return False
        if not prediction.uncertainty_valid:
            return False
        # Age check
        if (observation.decision_timestamp_s - prediction.feature_cutoff_timestamp_s) > self.config.risk_policy.maximum_prediction_age_s:
            return False
        # Schema/config/topology binding is asserted true if Prediction is generated (enforced by the predictor loading)
        return True

    def act(
        self,
        observation: WarningObservationWindow,
        prediction: Prediction | None,
        constraints: Any,
    ) -> ActionRecord:

        applicable = self._is_applicable(prediction, observation)
        p_k = prediction.probability if prediction else 0.0
        s_k = prediction.conformal_prediction_set if prediction else ()

        action_type = ActionType.NO_ACTION
        target = "supervisory.none"
        rationale = "Default no action"

        if observation.process_mode == "COMPLETE":
            self.state = "COMPLETE"

        # Update state based on observed mode (this is simplified; real state updates happen when actions are applied)
        # But we trust the last state if it's holding or recovering.
        if self.state == "RUNNING":
            positive_condition = (tuple(s_k) == (1,)) if self.config.risk_policy.require_positive_singleton_for_hold else True
            if applicable and p_k >= self.config.risk_policy.hold_probability and positive_condition:
                action_type = ActionType.SAFE_HOLD
                target = "cmp.process_mode"
                rationale = "Predictive excursion risk is high"
                self.state = "HOLDING"
                self.held_at_s = observation.decision_timestamp_s
                self.interrupted_mode = observation.process_mode
            elif applicable and p_k >= self.config.risk_policy.advisory_probability:
                action_type = ActionType.ADVISORY_WARNING
                target = "supervisory.advisory"
                rationale = "Elevated risk advisory"
        elif self.state == "HOLDING":
            negative_condition = (tuple(s_k) == (0,)) if self.config.risk_policy.require_negative_singleton_for_resume else True
            if applicable and p_k <= self.config.risk_policy.resume_maximum_probability and negative_condition:
                action_type = ActionType.CONTROLLED_RESUME
                target = "cmp.process_mode"
                rationale = "Risk cleared, proposing controlled resume"
                self.state = "RECOVERING"
            else:
                action_type = ActionType.SAFE_HOLD
                target = "cmp.process_mode"
                rationale = "Maintaining hold until risk clears"
        elif self.state == "RECOVERING":
            action_type = ActionType.NO_ACTION
            target = "supervisory.none"
            rationale = "No additional actuation during recovery"
        elif self.state == "COMPLETE":
            action_type = ActionType.NO_ACTION
            target = "supervisory.none"
            rationale = "Recipe complete"

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
