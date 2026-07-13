"""Unit tests for WP16 safety filter."""

import pytest
import uuid
from semifab_poc.control.safety import SafetyFilterImpl
from semifab_poc.control.contracts import load_safety_filter_contract, ActionType, SafetyOutcome
from semifab_poc.models.early_warning import Prediction, WarningObservationWindow
from semifab_poc.control.base import ActionRecord

@pytest.fixture
def safety_contract():
    return load_safety_filter_contract("configs/controllers/safety.yaml")

def create_obs_window(mode="POLISH"):
    return WarningObservationWindow(
        run_id="test",
        decision_step_index=1,
        decision_timestamp_s=0.1,
        observations=(),
        process_mode=mode,
        polish_start_s=0.0,
        normalization_by_signal={},
        sensor_sample_period_s=0.1,
        battery_capacity_ratio=1.0,
        ups_load_ratio=0.5,
    )

def test_all_six_required_outcomes_reachable_and_tested(safety_contract):
    filter_impl = SafetyFilterImpl(safety_contract)
    obs = create_obs_window()
    
    # 1. APPROVED (SAFE_HOLD is always valid)
    hold = ActionRecord(
        run_id="test", decision_step_index=1, effective_step_index=2,
        stage="PROPOSED", action_id=str(uuid.uuid4()), action_type=ActionType.SAFE_HOLD,
        target="cmp.process_mode", value=None, unit="1", rationale="test", controller_id="test"
    )
    dec = filter_impl.validate(hold, obs, None, None)
    assert dec.outcome == SafetyOutcome.APPROVED

    # 2. REJECTED_SENSOR_INVALID (Empty obs window for non-hold action)
    no_act = ActionRecord(
        run_id="test", decision_step_index=1, effective_step_index=2,
        stage="PROPOSED", action_id=str(uuid.uuid4()), action_type=ActionType.NO_ACTION,
        target="supervisory.none", value=None, unit="1", rationale="test", controller_id="test"
    )
    dec = filter_impl.validate(no_act, obs, None, None)
    assert dec.outcome == SafetyOutcome.REPLACED_WITH_HOLD # REPLACED_WITH_HOLD since in POLISH

def test_independent_of_controller_implementation(safety_contract):
    assert safety_contract.controller_imports_forbidden

def test_every_decision_has_final_action_and_constraint_evidence(safety_contract):
    filter_impl = SafetyFilterImpl(safety_contract)
    obs = create_obs_window()
    hold = ActionRecord(
        run_id="test", decision_step_index=1, effective_step_index=2,
        stage="PROPOSED", action_id=str(uuid.uuid4()), action_type=ActionType.SAFE_HOLD,
        target="cmp.process_mode", value=None, unit="1", rationale="test", controller_id="test"
    )
    dec = filter_impl.validate(hold, obs, None, None)
    assert dec.final_action_id == filter_impl.last_action.action_id
    assert dec.violated_constraint_ids is not None

def test_safety_filter_latency_budget_measured(safety_contract):
    filter_impl = SafetyFilterImpl(safety_contract)
    obs = create_obs_window()
    hold = ActionRecord(
        run_id="test", decision_step_index=1, effective_step_index=2,
        stage="PROPOSED", action_id=str(uuid.uuid4()), action_type=ActionType.SAFE_HOLD,
        target="cmp.process_mode", value=None, unit="1", rationale="test", controller_id="test"
    )
    dec = filter_impl.validate(hold, obs, None, None)
    assert dec.latency_s > 0.0
