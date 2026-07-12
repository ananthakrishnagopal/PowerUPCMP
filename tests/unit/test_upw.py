import pytest

from semifab_poc.simulation.upw import UpwModelError, UpwSubsystem


def test_nominal_upw_state_is_an_equilibrium() -> None:
    upw = UpwSubsystem()
    state = upw.reset()
    updated = upw.step(state, None, None, 0.01)
    assert updated.supply_pressure_pa == pytest.approx(state.supply_pressure_pa)
    assert updated.tool_flow_m3_s == pytest.approx(1.0e-4)
    assert updated.return_flow_m3_s == pytest.approx(1.0e-4)
    assert updated.temperature_k == pytest.approx(state.temperature_k)


def test_valve_restriction_and_demand_are_reflected_in_tool_flow() -> None:
    upw = UpwSubsystem()
    state = upw.reset()
    restricted = upw.step(
        state,
        {"valve_position": 0.25},
        {"tool_demand_m3_s": 2.0e-4},
        0.01,
    )
    assert restricted.valve_position == pytest.approx(0.25)
    assert restricted.tool_demand_m3_s == pytest.approx(2.0e-4)
    assert 0.0 < restricted.tool_flow_m3_s < restricted.tool_demand_m3_s
    assert restricted.tool_flow_m3_s < state.tool_flow_m3_s
    assert abs(restricted.mass_balance_residual_m3_s) <= upw.config.hydraulic_balance_tolerance_m3_s


def test_thermal_and_dimensionless_water_quality_proxy_are_supported_and_bounded() -> None:
    upw = UpwSubsystem()
    state = upw.reset()
    updated = upw.step(
        state,
        None,
        {
            "inlet_temperature_k": 300.0,
            "thermal_load_w": 500.0,
            "water_quality_source_deviation_proxy": 0.10,
            "water_quality_ingress_proxy_per_s": 0.001,
        },
        0.01,
    )
    assert updated.temperature_k > state.temperature_k
    assert updated.water_quality_deviation_proxy > state.water_quality_deviation_proxy
    assert (
        0.0
        <= updated.water_quality_deviation_proxy
        <= upw.config.maximum_water_quality_deviation_proxy
    )


def test_pump_trip_pressure_decays_through_compliance_without_stale_flows() -> None:
    upw = UpwSubsystem()
    state = upw.reset()
    first = upw.step(state, None, {"pump_flow_m3_s": 0.0}, 0.01)
    assert state.return_pressure_pa < first.supply_pressure_pa < state.supply_pressure_pa
    expected_return = (
        first.supply_pressure_pa - first.return_pressure_pa
    ) / upw.config.return_resistance_pa_s_m3
    assert first.return_flow_m3_s == pytest.approx(expected_return)
    assert abs(first.mass_balance_residual_m3_s) <= upw.config.hydraulic_balance_tolerance_m3_s
    second = upw.step(first, None, {"pump_flow_m3_s": 0.0}, 0.01)
    assert second.supply_pressure_pa < first.supply_pressure_pa


def test_relief_flow_is_explicit_and_conserved() -> None:
    upw = UpwSubsystem()
    state = upw.reset()
    for _ in range(200):
        state = upw.step(
            state,
            {"valve_position": 0.0},
            {"pump_flow_m3_s": 3.0e-4, "tool_demand_m3_s": 0.0},
            0.01,
        )
    assert state.supply_pressure_pa > upw.config.relief_set_pressure_pa
    assert state.relief_flow_m3_s > 0.0
    assert abs(state.mass_balance_residual_m3_s) <= upw.config.hydraulic_balance_tolerance_m3_s


def test_supply_temperature_flushing_uses_pump_inflow_not_tool_flow() -> None:
    upw = UpwSubsystem()
    initial = upw.reset()
    no_inflow = upw.step(
        initial,
        {"valve_position": 1.0},
        {"pump_flow_m3_s": 0.0, "inlet_temperature_k": 300.0},
        0.01,
    )
    with_inflow = upw.step(
        initial,
        {"valve_position": 0.0},
        {"pump_flow_m3_s": 2.0e-4, "inlet_temperature_k": 300.0},
        0.01,
    )
    assert no_inflow.temperature_k == pytest.approx(initial.temperature_k)
    assert with_inflow.temperature_k > initial.temperature_k


def test_invalid_timestep_is_rejected() -> None:
    upw = UpwSubsystem()
    with pytest.raises(UpwModelError, match="positive"):
        upw.step(upw.reset(), None, None, 0.0)
    with pytest.raises(UpwModelError, match="operator-split"):
        upw.step(upw.reset(), None, None, 1.0)
