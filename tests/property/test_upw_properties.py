from semifab_poc.simulation.upw import UpwSubsystem


def test_upw_state_remains_finite_and_bounded_under_bounded_events() -> None:
    upw = UpwSubsystem()
    state = upw.reset()
    for index in range(400):
        state = upw.step(
            state,
            {"valve_position": (index % 11) / 10.0},
            {
                "pump_flow_m3_s": (index % 6) * 5.0e-5,
                "return_pressure_pa": 0.8e5,
                "tool_demand_m3_s": (index % 5) * 5.0e-5,
                "inlet_temperature_k": 285.0 + (index % 8),
                "thermal_load_w": float((index % 9) * 100),
                "water_quality_source_deviation_proxy": 0.02 + (index % 6) * 0.01,
            },
            0.01,
        )
        state.validate(upw.config)
        assert abs(state.mass_balance_residual_m3_s) <= upw.config.hydraulic_balance_tolerance_m3_s


def test_tool_flow_is_monotonic_with_valve_position_at_fixed_pressure_and_demand() -> None:
    upw = UpwSubsystem()
    initial = upw.reset()
    flows = [
        upw.step(initial, {"valve_position": valve}, {"tool_demand_m3_s": 2.0e-4}, 0.01).tool_flow_m3_s
        for valve in (0.0, 0.25, 0.5, 0.75, 1.0)
    ]
    assert flows == sorted(flows)
