from semifab_poc.simulation.pump import PumpSubsystem


def test_pump_flow_head_and_power_are_monotonic_with_speed() -> None:
    pump = PumpSubsystem()
    states = [pump.from_motor_speed(ratio * pump.config.reference_motor_speed_rad_s) for ratio in (0.0, 0.25, 0.5, 0.75, 1.0, 1.2)]
    flows = [state.volumetric_flow_m3_s for state in states]
    heads = [state.head_pa for state in states]
    powers = [state.power_w for state in states]
    assert flows == sorted(flows)
    assert heads == sorted(heads)
    assert powers == sorted(powers)
    assert all(power >= 0.0 for power in powers)


def test_affinity_power_cubic_relation_at_reference_ratios() -> None:
    pump = PumpSubsystem()
    half = pump.from_motor_speed(0.5 * pump.config.reference_motor_speed_rad_s)
    assert half.volumetric_flow_m3_s == 0.5 * pump.config.reference_flow_m3_s
    assert half.head_pa == 0.25 * pump.config.reference_head_pa
    assert half.power_w == 0.125 * pump.config.reference_power_w


def test_open_operating_points_satisfy_quadratic_pump_curve() -> None:
    pump = PumpSubsystem()
    for ratio in (0.4, 0.7, 1.0, 1.2):
        shutoff = pump.config.shutoff_head_pa * ratio**2
        for pressure_fraction in (0.0, 0.25, 0.5, 0.75):
            state = pump.operating_point(
                ratio * pump.config.reference_motor_speed_rad_s,
                pressure_fraction * shutoff,
            )
            assert state.check_valve_closed is False
            assert abs(state.operating_point_residual_pa) <= pump.config.operating_point_tolerance_pa
