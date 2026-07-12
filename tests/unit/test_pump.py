import pytest

from semifab_poc.simulation.pump import PumpModelError, PumpSubsystem


def test_affinity_reference_and_zero_speed_cases() -> None:
    pump = PumpSubsystem()
    reference = pump.from_motor_speed(pump.config.reference_motor_speed_rad_s)
    assert reference.speed_ratio == pytest.approx(1.0)
    assert reference.volumetric_flow_m3_s == pytest.approx(pump.config.reference_flow_m3_s)
    assert reference.head_pa == pytest.approx(pump.config.reference_head_pa)
    assert reference.power_w == pytest.approx(pump.config.reference_power_w)
    stopped = pump.from_motor_speed(0.0)
    assert stopped.volumetric_flow_m3_s == 0.0
    assert stopped.head_pa == 0.0
    assert stopped.power_w == 0.0


def test_pump_step_uses_motor_speed_disturbance() -> None:
    pump = PumpSubsystem()
    state = pump.step(
        pump.reset(),
        None,
        {
            "motor_speed_rad_s": 0.5 * pump.config.reference_motor_speed_rad_s,
            "system_differential_pressure_pa": 0.25 * pump.config.reference_head_pa,
        },
        0.01,
    )
    assert state.speed_ratio == pytest.approx(0.5)
    assert state.volumetric_flow_m3_s == pytest.approx(0.5 * pump.config.reference_flow_m3_s)
    assert state.head_pa == pytest.approx(0.25 * pump.config.reference_head_pa)
    assert state.power_w == pytest.approx(0.125 * pump.config.reference_power_w)
    assert state.operating_point_residual_pa == pytest.approx(0.0, abs=1.0e-9)
    assert state.check_valve_closed is False


def test_operating_flow_decreases_with_network_pressure_and_check_valve_blocks_reverse_flow() -> None:
    pump = PumpSubsystem()
    speed = pump.config.reference_motor_speed_rad_s
    pressures = (0.0, 1.0e5, 2.0e5, 3.0e5)
    flows = [pump.operating_point(speed, pressure).volumetric_flow_m3_s for pressure in pressures]
    assert flows == sorted(flows, reverse=True)
    blocked = pump.operating_point(speed, pump.config.shutoff_head_pa + 1.0)
    assert blocked.volumetric_flow_m3_s == 0.0
    assert blocked.check_valve_closed is True


def test_pump_rejects_invalid_timestep() -> None:
    pump = PumpSubsystem()
    with pytest.raises(PumpModelError, match="positive"):
        pump.step(pump.reset(), None, None, 0.0)
