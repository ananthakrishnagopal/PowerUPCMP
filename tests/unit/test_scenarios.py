from pathlib import Path

import pytest

from semifab_poc.data.schema import RootCause
from semifab_poc.simulation.scenario import (
    Scenario,
    ScenarioError,
    ScenarioEvent,
    ScenarioProfile,
    load_scenarios,
)


LIBRARY = Path("configs/scenarios/library.yaml")


def test_all_required_scenario_families_are_present() -> None:
    scenarios = load_scenarios(LIBRARY)
    required = {
        "normal_operation",
        "mild_voltage_sag",
        "severe_voltage_sag",
        "ups_transfer",
        "pump_trip",
        "valve_restriction",
        "tool_demand_spike",
        "temperature_excursion",
        "pressure_sensor_bias",
        "sensor_dropout",
        "recoverable_disturbance",
        "hold_required_disturbance",
        "compound_disturbance",
        "slow_drift",
    }
    assert set(scenarios) == required


def test_invalid_target_unit_time_and_magnitude_are_rejected() -> None:
    invalid = ScenarioEvent(
        scenario_id="invalid",
        event_id="bad",
        event_type="bad",
        start_s=-1.0,
        duration_s=1.0,
        priority=1,
        target="upw.tool_demand_m3_s",
        profile=ScenarioProfile.STEP,
        magnitude=1.0,
        unit="Pa",
        initiating_cause=RootCause.UNKNOWN,
        declaration_order=0,
    )
    with pytest.raises(ScenarioError):
        invalid.validate()


def test_equal_time_events_are_priority_then_declaration_order_stable() -> None:
    scenario = Scenario.from_mapping(
        {
            "scenario_id": "ordered",
            "description": "ordering test",
            "schema_version": "2.0.0",
            "compound_cause_policy": "MULTI_LABEL_ORDERED",
            "events": [
                {
                    "event_id": "second",
                    "event_type": "test",
                    "start_s": 1.0,
                    "duration_s": 1.0,
                    "priority": 20,
                    "target": "upw.tool_demand_m3_s",
                    "profile": "PULSE",
                    "magnitude": 1.0e-4,
                    "unit": "m^3/s",
                    "initiating_cause": "TOOL_DEMAND_SPIKE",
                },
                {
                    "event_id": "first",
                    "event_type": "test",
                    "start_s": 1.0,
                    "duration_s": 1.0,
                    "priority": 10,
                    "target": "electrical.grid_voltage_delta_pu",
                    "profile": "PULSE",
                    "magnitude": -0.1,
                    "unit": "pu",
                    "initiating_cause": "GRID_VOLTAGE_SAG",
                },
            ],
        }
    )
    assert [event.event_id for event in scenario.events_at(1.0)] == ["first", "second"]
    assert scenario.initiating_causes_at(1.0) == (
        RootCause.GRID_VOLTAGE_SAG,
        RootCause.TOOL_DEMAND_SPIKE,
    )


def test_profile_duration_contracts_are_executable_before_replay() -> None:
    common = dict(
        scenario_id="profiles",
        event_id="event",
        event_type="sensor_drift",
        start_s=1.0,
        priority=1,
        target="sensor.pressure.drift_per_s",
        magnitude=50.0,
        unit="Pa/s",
        initiating_cause=RootCause.PRESSURE_SENSOR_FAULT,
        declaration_order=0,
    )
    with pytest.raises(ScenarioError, match="positive duration"):
        ScenarioEvent(**common, duration_s=0.0, profile=ScenarioProfile.RAMP).validate()
    with pytest.raises(ScenarioError, match="duration_s == 0"):
        ScenarioEvent(**common, duration_s=1.0, profile=ScenarioProfile.STEP).validate()
    persistent = ScenarioEvent(**common, duration_s=0.0, profile=ScenarioProfile.STEP)
    persistent.validate()
    assert persistent.active_at(100.0)


def test_target_bounds_propagation_causes_and_voltage_sign_are_rejected() -> None:
    common = dict(
        scenario_id="invalid",
        event_id="bad",
        event_type="voltage_sag",
        start_s=1.0,
        duration_s=1.0,
        priority=1,
        target="electrical.grid_voltage_delta_pu",
        profile=ScenarioProfile.PULSE,
        unit="pu",
        declaration_order=0,
    )
    with pytest.raises(ScenarioError, match="within"):
        ScenarioEvent(
            **common,
            magnitude=-2.0,
            initiating_cause=RootCause.GRID_VOLTAGE_SAG,
        ).validate()
    with pytest.raises(ScenarioError, match="propagation state"):
        ScenarioEvent(
            **common,
            magnitude=-0.2,
            initiating_cause=RootCause.UPS_TRANSFER,
        ).validate()
    with pytest.raises(ScenarioError, match="sign"):
        ScenarioEvent(
            **common,
            magnitude=0.2,
            initiating_cause=RootCause.GRID_VOLTAGE_SAG,
        ).validate()


def test_interval_overlap_requires_multilabel_and_same_target_is_always_rejected() -> None:
    def mapping(policy: str, second_target: str = "upw.tool_demand_m3_s"):
        second_cause = (
            "TOOL_DEMAND_SPIKE"
            if second_target == "upw.tool_demand_m3_s"
            else "GRID_VOLTAGE_SAG"
        )
        second_unit = "m^3/s" if second_target == "upw.tool_demand_m3_s" else "pu"
        second_magnitude = 2.0e-4 if second_target == "upw.tool_demand_m3_s" else -0.1
        return {
            "schema_version": "2.0.0",
            "scenario_id": "overlap",
            "description": "interval overlap",
            "compound_cause_policy": policy,
            "events": [
                {
                    "event_id": "one",
                    "event_type": "sag",
                    "start_s": 1.0,
                    "duration_s": 1.0,
                    "priority": 10,
                    "target": "electrical.grid_voltage_delta_pu",
                    "profile": "PULSE",
                    "magnitude": -0.2,
                    "unit": "pu",
                    "initiating_cause": "GRID_VOLTAGE_SAG",
                },
                {
                    "event_id": "two",
                    "event_type": "second",
                    "start_s": 1.5,
                    "duration_s": 1.0,
                    "priority": 20,
                    "target": second_target,
                    "profile": "PULSE",
                    "magnitude": second_magnitude,
                    "unit": second_unit,
                    "initiating_cause": second_cause,
                },
            ],
        }

    with pytest.raises(ScenarioError, match="MULTI_LABEL_ORDERED"):
        Scenario.from_mapping(mapping("SINGLE_EVENT"))
    accepted = Scenario.from_mapping(mapping("MULTI_LABEL_ORDERED"))
    assert len(accepted.events_at(1.75)) == 2
    with pytest.raises(ScenarioError, match="same target"):
        Scenario.from_mapping(
            mapping("MULTI_LABEL_ORDERED", "electrical.grid_voltage_delta_pu")
        )


def test_unknown_keys_and_malformed_piecewise_points_are_rejected() -> None:
    with pytest.raises(ScenarioError, match="unknown scenario keys"):
        Scenario.from_mapping(
            {
                "schema_version": "2.0.0",
                "scenario_id": "unknown",
                "description": "bad key",
                "typo": 1,
            }
        )
    with pytest.raises(ScenarioError, match="exactly time and value"):
        Scenario.from_mapping(
            {
                "schema_version": "2.0.0",
                "scenario_id": "points",
                "description": "bad points",
                "events": [
                    {
                        "event_id": "points",
                        "event_type": "drift",
                        "start_s": 0.0,
                        "duration_s": 1.0,
                        "target": "sensor.pressure.drift_per_s",
                        "profile": "PIECEWISE_LINEAR",
                        "magnitude": 10.0,
                        "unit": "Pa/s",
                        "initiating_cause": "PRESSURE_SENSOR_FAULT",
                        "piecewise_points": [[0.0, 0.0, 1.0], [1.0, 10.0]],
                    }
                ],
            }
        )


def test_library_uses_grid_interruption_as_initiating_cause() -> None:
    scenario = load_scenarios(LIBRARY)["ups_transfer"]
    assert scenario.events[0].initiating_cause is RootCause.GRID_INTERRUPTION


def test_piecewise_profile_requires_bounded_complete_endpoint_contract() -> None:
    valid = Scenario.from_mapping(
        {
            "schema_version": "2.0.0",
            "scenario_id": "piecewise",
            "description": "valid piecewise drift",
            "events": [
                {
                    "event_id": "drift",
                    "event_type": "sensor_drift",
                    "start_s": 1.0,
                    "duration_s": 2.0,
                    "target": "sensor.pressure.drift_per_s",
                    "profile": "PIECEWISE_LINEAR",
                    "magnitude": 20.0,
                    "unit": "Pa/s",
                    "initiating_cause": "PRESSURE_SENSOR_FAULT",
                    "piecewise_points": [[0.0, 0.0], [1.0, 5.0], [2.0, 20.0]],
                }
            ],
        }
    )
    assert valid.values_at(2.5)[0][1] == pytest.approx(12.5)
    assert valid.events_at(3.0) == ()

    bad = valid.events[0].__class__(
        **{
            **valid.events[0].__dict__,
            "piecewise_points": ((0.0, 0.0), (2.0, 200_000.0)),
            "magnitude": 200_000.0,
        }
    )
    with pytest.raises(ScenarioError, match="within"):
        bad.validate()
