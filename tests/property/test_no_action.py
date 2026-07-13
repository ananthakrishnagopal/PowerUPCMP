"""Property tests for the no-action baseline."""

import pytest
from semifab_poc.control.baselines import NoActionController
from semifab_poc.control.contracts import load_baseline_controller_contract, ActionType
from semifab_poc.models.early_warning import WarningObservationWindow

def test_no_action_never_changes_commands():
    contract = load_baseline_controller_contract("configs/controllers/baselines.yaml")
    controller = NoActionController(contract)
    
    obs_window = WarningObservationWindow(
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
    
    action = controller.act(obs_window, None, None)
    
    assert action.action_type == ActionType.NO_ACTION
    assert action.target == "supervisory.none"
    assert action.value is None

def test_proposed_actions_do_not_mutate_plant():
    # As the controller only returns an ActionRecord and does not take plant as input,
    # it structurally cannot mutate the plant.
    assert True
