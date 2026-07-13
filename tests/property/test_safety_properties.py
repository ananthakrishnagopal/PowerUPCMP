"""Property tests for WP16 safety properties."""

import pytest
import uuid
from semifab_poc.control.safety import SafetyFilterImpl
from semifab_poc.control.contracts import load_safety_filter_contract, ActionType
from semifab_poc.models.early_warning import Prediction, WarningObservationWindow
from semifab_poc.control.base import ActionRecord

def test_property_sweep_has_zero_final_constraint_violations():
    contract = load_safety_filter_contract("configs/controllers/safety.yaml")
    filter_impl = SafetyFilterImpl(contract)
    
    obs = WarningObservationWindow(
        run_id="test",
        decision_step_index=1,
        decision_timestamp_s=0.1,
        observations=(),
        process_mode="POLISH",
        polish_start_s=0.0,
        normalization_by_signal={},
        sensor_sample_period_s=0.1,
        battery_capacity_ratio=1.0,
        ups_load_ratio=0.5,
    )
    
    # Check that whatever junk we throw, the final action is inside constraints
    junk = ActionRecord(
        run_id="test", decision_step_index=1, effective_step_index=1, # invalid timing rejected by safety filter
        stage="PROPOSED", action_id=str(uuid.uuid4()), action_type=ActionType.VFD_COMMAND_ADJUSTMENT,
        target="drive.vfd_command", value=999.0, unit="pu", rationale="junk", controller_id="test"
    )
    
    dec = filter_impl.validate(junk, obs, None, None)
    assert dec.outcome != "APPROVED"
    assert filter_impl.last_action.action_type in (ActionType.SAFE_HOLD, ActionType.NO_ACTION)
    assert filter_impl.last_action.stage == "FINAL"
    # value for SAFE_HOLD is None
    assert filter_impl.last_action.value is None
