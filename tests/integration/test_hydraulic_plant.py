import pytest

from semifab_poc.simulation.pump import PumpSubsystem
from semifab_poc.simulation.upw import UpwSubsystem


def _run_speed_step(dt_s: float, duration_s: float = 0.5) -> float:
    pump = PumpSubsystem()
    upw = UpwSubsystem()
    pump_state = pump.reset()
    upw_state = upw.reset()
    speed = 0.70 * pump.config.reference_motor_speed_rad_s
    for _ in range(round(duration_s / dt_s)):
        pump_state = pump.step(
            pump_state,
            None,
            {
                "motor_speed_rad_s": speed,
                "system_differential_pressure_pa": (
                    upw_state.supply_pressure_pa - upw_state.return_pressure_pa
                ),
            },
            dt_s,
        )
        upw_state = upw.step(
            upw_state,
            None,
            {"pump_flow_m3_s": pump_state.volumetric_flow_m3_s},
            dt_s,
        )
    return upw_state.supply_pressure_pa


def test_nominal_pump_and_upw_operating_point_is_self_consistent() -> None:
    pump = PumpSubsystem()
    upw = UpwSubsystem()
    upw_state = upw.reset()
    pump_state = pump.operating_point(
        pump.config.reference_motor_speed_rad_s,
        upw_state.supply_pressure_pa - upw_state.return_pressure_pa,
    )
    assert pump_state.volumetric_flow_m3_s == pytest.approx(
        upw.config.reference_pump_flow_m3_s
    )
    updated = upw.step(
        upw_state,
        None,
        {"pump_flow_m3_s": pump_state.volumetric_flow_m3_s},
        0.01,
    )
    assert updated.supply_pressure_pa == pytest.approx(upw_state.supply_pressure_pa)
    assert abs(updated.mass_balance_residual_m3_s) <= upw.config.hydraulic_balance_tolerance_m3_s


def test_hydraulic_operator_split_converges_under_timestep_refinement() -> None:
    reference = _run_speed_step(0.001)
    error_20_ms = abs(_run_speed_step(0.02) - reference)
    error_10_ms = abs(_run_speed_step(0.01) - reference)
    error_5_ms = abs(_run_speed_step(0.005) - reference)
    assert error_10_ms < error_20_ms
    assert error_5_ms < error_10_ms
    assert error_5_ms / 300_000.0 < 5.0e-4


def test_closed_tool_valve_reaches_a_conserved_pump_system_operating_point() -> None:
    pump = PumpSubsystem()
    upw = UpwSubsystem()
    pump_state = pump.reset()
    upw_state = upw.reset()
    for _ in range(500):
        pump_state = pump.step(
            pump_state,
            None,
            {
                "motor_speed_rad_s": pump.config.reference_motor_speed_rad_s,
                "system_differential_pressure_pa": (
                    upw_state.supply_pressure_pa - upw_state.return_pressure_pa
                ),
            },
            0.01,
        )
        upw_state = upw.step(
            upw_state,
            {"valve_position": 0.0},
            {"pump_flow_m3_s": pump_state.volumetric_flow_m3_s},
            0.01,
        )
    assert upw_state.tool_flow_m3_s == 0.0
    assert upw_state.supply_pressure_pa > upw.config.nominal_supply_pressure_pa
    assert pump_state.volumetric_flow_m3_s == pytest.approx(
        upw_state.return_flow_m3_s + upw_state.relief_flow_m3_s,
        rel=1.0e-6,
    )
    assert abs(pump_state.operating_point_residual_pa) <= pump.config.operating_point_tolerance_pa
    assert abs(upw_state.mass_balance_residual_m3_s) <= upw.config.hydraulic_balance_tolerance_m3_s
