"""Unit tests for WP14 baseline controllers."""

import pytest
from semifab_poc.control.baselines import ProcessMrrThresholdController, UtilityThresholdController
from semifab_poc.control.contracts import load_baseline_controller_contract, ActionType
from semifab_poc.models.early_warning import WarningObservationWindow
from semifab_poc.data.schema import ObservationRecord, QualityFlag, DataOrigin

@pytest.fixture
def baseline_contract():
    return load_baseline_controller_contract("configs/controllers/baselines.yaml")

def create_obs_window(mrr_val, timestamp_s):
    obs = ObservationRecord(
        run_id="test",
        sample_index=1,
        source_step_index=1,
        source_timestamp_s=timestamp_s,
        observed_timestamp_s=timestamp_s,
        arrival_timestamp_s=timestamp_s,
        sensor_id="mrr_sensor",
        signal_id="cmp.mrr",
        value=mrr_val,
        unit="m/s",
        quality_flags=(),
        data_origin=DataOrigin.SYNTHETIC_SIMULATOR
    )
    return WarningObservationWindow(
        run_id="test",
        decision_step_index=int(timestamp_s * 10),
        decision_timestamp_s=timestamp_s,
        observations=(obs,),
        process_mode="POLISH",
        polish_start_s=0.0,
        normalization_by_signal={},
        sensor_sample_period_s=0.1,
        battery_capacity_ratio=1.0,
        ups_load_ratio=0.5,
    )

def test_fixed_threshold_uses_observed_state_only(baseline_contract):
    controller = ProcessMrrThresholdController(baseline_contract)
    assert controller.config.use_arrived_observations_only

def test_hysteresis_prevents_threshold_chatter(baseline_contract):
    controller = ProcessMrrThresholdController(baseline_contract)
    
    ref = 2.0e-8
    # 0.95 ratio is lower_relative_fraction. We go below it to trigger hold.
    obs1 = create_obs_window(ref * 0.94, 0.1)
    act1 = controller.act(obs1, None, None)
    assert act1.action_type == ActionType.NO_ACTION # Needs persistence
    
    obs2 = create_obs_window(ref * 0.94, 0.4)
    act2 = controller.act(obs2, None, None)
    assert act2.action_type == ActionType.SAFE_HOLD # Persistence met
    assert controller.held
    
    # 0.96 ratio is below release_lower_relative_fraction (0.97) but above 0.95.
    # Should not chatter back to NO_ACTION/RESUME.
    obs3 = create_obs_window(ref * 0.96, 0.5)
    act3 = controller.act(obs3, None, None)
    assert act3.action_type == ActionType.SAFE_HOLD
    assert controller.held

def test_safe_hold_and_controlled_resume_are_stateful(baseline_contract):
    controller = UtilityThresholdController(baseline_contract)
    assert not controller.held
    
    # No valid signals provided -> immediate breach
    obs_empty = WarningObservationWindow(
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
    
    # Initial breach needs persistence
    controller.act(obs_empty, None, None)
    assert not controller.held
    
    # Next step meets persistence 0.10s
    obs_empty = WarningObservationWindow(
        run_id="test",
        decision_step_index=2,
        decision_timestamp_s=0.2,
        observations=(),
        process_mode="POLISH",
        polish_start_s=0.0,
        normalization_by_signal={},
        sensor_sample_period_s=0.1,
        battery_capacity_ratio=1.0,
        ups_load_ratio=0.5,
    )
    act2 = controller.act(obs_empty, None, None)
    assert act2.action_type == ActionType.SAFE_HOLD
    assert controller.held
