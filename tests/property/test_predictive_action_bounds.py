"""Property tests for WP15 predictive bounds."""

import pytest
from semifab_poc.control.predictive import PredictiveSupervisor
from semifab_poc.control.contracts import load_predictive_controller_contract, ActionType
from semifab_poc.models.early_warning import Prediction, WarningObservationWindow

def test_predictive_action_bounds():
    # Only the 4 configured primary actions are allowed to be proposed
    contract = load_predictive_controller_contract("configs/controllers/predictive.yaml")
    controller = PredictiveSupervisor(contract)
    
    allowed = {ActionType.NO_ACTION, ActionType.ADVISORY_WARNING, ActionType.SAFE_HOLD, ActionType.CONTROLLED_RESUME}
    
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
    pred = Prediction(0.6, True, (1,), True, 1, 0.1, 0.01)
    
    action = controller.act(obs, pred, None)
    assert action.action_type in allowed
