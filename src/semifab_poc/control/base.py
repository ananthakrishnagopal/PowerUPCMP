"""Base interfaces and typed records for control and safety."""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import Field

from semifab_poc.control.contracts import ActionType, SafetyOutcome
from semifab_poc.data.schema import DataModel, SemanticClass
from semifab_poc.models.early_warning import Prediction, WarningObservationWindow


class ActionRecord(DataModel):
    """Proposed or final supervisory action; no direct hardware command."""

    semantic_class: type[SemanticClass] = SemanticClass.CONTROL_ACTION

    run_id: str = Field(min_length=1)
    decision_step_index: int = Field(ge=0)
    effective_step_index: int = Field(ge=1)
    stage: str = Field(pattern="^(PROPOSED|FINAL)$")
    action_id: str = Field(min_length=1)
    action_type: ActionType
    target: str = Field(min_length=1)
    value: float | None = None
    unit: str = Field(min_length=1)
    rationale: str = Field(min_length=1)
    controller_id: str = Field(min_length=1)


class SafetyDecisionRecord(DataModel):
    """Independent disposition of a proposed action."""

    semantic_class: type[SemanticClass] = SemanticClass.SAFETY_DECISION

    run_id: str = Field(min_length=1)
    decision_step_index: int = Field(ge=0)
    proposed_action_id: str = Field(min_length=1)
    outcome: SafetyOutcome
    final_action_id: str = Field(min_length=1)
    violated_constraint_ids: tuple[str, ...]
    sensor_valid: bool
    uncertainty_acceptable: bool
    process_envelope_valid: bool
    latency_s: float = Field(ge=0.0)


class Controller:
    """Interface for supervisory control policies."""

    interface_version = "1.0.0"

    def reset(self) -> None:
        """Clear controller history; preserve configured policy."""
        pass

    def act(
        self,
        observation: WarningObservationWindow,
        prediction: Prediction | None,
        constraints: Any,
    ) -> ActionRecord:
        """Return a proposed action without mutating the plant."""
        raise NotImplementedError


class SafetyFilter:
    """Interface for the independent safety guard."""

    interface_version = "1.0.0"

    def validate(
        self,
        proposed_action: ActionRecord,
        observation: WarningObservationWindow,
        uncertainty: Prediction | None,
        constraints: Any,
    ) -> SafetyDecisionRecord:
        """Return an auditable disposition without mutating the plant."""
        raise NotImplementedError
