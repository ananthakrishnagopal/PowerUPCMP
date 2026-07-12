import pytest

from semifab_poc.simulation.electrical import (
    ElectricalConfig,
    ElectricalModelError,
    ElectricalSubsystem,
    UpsMode,
)


def test_normal_operation_converges_to_nominal() -> None:
    model = ElectricalSubsystem()
    state = model.reset()
    for _ in range(20):
        state = model.step(state, None, None, 0.01)
    assert state.ups_mode is UpsMode.GRID
    assert state.grid_voltage_pu == pytest.approx(1.0)
    assert state.ups_output_voltage_pu == pytest.approx(1.0)
    assert state.grid_frequency_hz == pytest.approx(50.0)
    assert state.ups_output_frequency_hz == pytest.approx(50.0)
    assert state.battery_energy_j == pytest.approx(model.config.battery_capacity_j)


def test_voltage_sag_transfers_then_reaches_battery() -> None:
    model = ElectricalSubsystem()
    state = model.reset()
    state = model.step(state, None, {"grid_voltage_pu": 0.70}, 0.01)
    assert state.ups_mode is UpsMode.TRANSFER
    for _ in range(6):
        state = model.step(state, None, {"grid_voltage_pu": 0.70}, 0.01)
    assert state.ups_mode is UpsMode.BATTERY
    assert model.config.transfer_output_pu <= state.ups_output_voltage_pu <= model.config.battery_output_pu
    for _ in range(20):
        state = model.step(state, None, {"grid_voltage_pu": 0.70}, 0.01)
    assert state.ups_output_voltage_pu == pytest.approx(model.config.battery_output_pu, abs=0.02)


def test_recovery_requires_stable_grid_and_dwell() -> None:
    model = ElectricalSubsystem()
    state = model.reset()
    for _ in range(8):
        state = model.step(state, None, {"grid_voltage_pu": 0.70}, 0.01)
    assert state.ups_mode is UpsMode.BATTERY
    state = model.step(state, None, {"grid_voltage_pu": 1.0}, 0.01)
    assert state.ups_mode is UpsMode.RECOVERY
    for _ in range(30):
        state = model.step(state, None, {"grid_voltage_pu": 1.0}, 0.01)
    assert state.ups_mode is UpsMode.GRID


def test_frequency_deviation_is_bounded() -> None:
    model = ElectricalSubsystem()
    state = model.reset()
    state = model.step(state, None, {"grid_frequency_delta_hz": 1000.0}, 0.01)
    assert state.grid_frequency_hz == 100.0
    assert state.ups_output_frequency_hz == pytest.approx(55.0)


def test_battery_energy_decreases_with_load_and_depletion_forces_bypass() -> None:
    model = ElectricalSubsystem()
    state = model.reset()
    updated = model.step(
        state,
        None,
        {"grid_voltage_pu": 0.70, "ups_load_power_w": 1_900.0},
        0.01,
    )
    assert updated.ups_mode is UpsMode.TRANSFER
    assert updated.battery_energy_j == pytest.approx(
        state.battery_energy_j - 1_900.0 * 0.01 / model.config.inverter_efficiency
    )

    depleted_model = ElectricalSubsystem(
        ElectricalConfig(initial_battery_energy_j=1.0, nominal_ups_load_w=100.0)
    )
    depleted = depleted_model.step(
        depleted_model.reset(),
        None,
        {"grid_voltage_pu": 0.70, "ups_load_power_w": 100.0},
        0.01,
    )
    assert depleted.ups_mode is UpsMode.BYPASS
    assert depleted.battery_energy_j == depleted_model.config.minimum_battery_energy_j


def test_exact_step_boundary_depletion_projects_to_minimum_then_bypasses() -> None:
    model = ElectricalSubsystem(
        ElectricalConfig(
            battery_capacity_j=500.0,
            initial_battery_energy_j=500.0,
            nominal_ups_load_w=2_500.0,
        )
    )
    state = model.reset()
    for _ in range(19):
        state = model.step(
            state,
            None,
            {"force_interruption": True, "ups_load_power_w": 2_500.0},
            0.01,
        )
    assert state.ups_mode in {UpsMode.TRANSFER, UpsMode.BATTERY}
    assert state.battery_energy_j == model.config.minimum_battery_energy_j

    state = model.step(
        state,
        None,
        {"force_interruption": True, "ups_load_power_w": 2_500.0},
        0.01,
    )
    assert state.ups_mode is UpsMode.BYPASS
    assert state.battery_energy_j == model.config.minimum_battery_energy_j


def test_overload_cannot_remain_on_battery() -> None:
    model = ElectricalSubsystem()
    state = model.step(
        model.reset(),
        None,
        {
            "grid_voltage_pu": 0.70,
            "ups_load_power_w": model.config.ups_rated_power_w
            * model.config.ups_overload_trip_ratio
            + 1.0,
        },
        0.01,
    )
    assert state.ups_mode is UpsMode.BYPASS


def test_forced_interruption_sets_grid_voltage_to_configured_minimum() -> None:
    model = ElectricalSubsystem()
    state = model.step(
        model.reset(),
        None,
        {"force_interruption": True},
        0.01,
    )
    assert state.grid_voltage_pu == model.config.voltage_min_pu
    assert state.ups_mode is UpsMode.TRANSFER


def test_invalid_timestep_and_forced_mode_are_rejected() -> None:
    model = ElectricalSubsystem()
    state = model.reset()
    with pytest.raises(ElectricalModelError, match="positive"):
        model.step(state, None, None, 0.0)
    with pytest.raises(ElectricalModelError, match="unknown forced"):
        model.step(state, None, {"force_ups_mode": "UNKNOWN"}, 0.01)


def test_configuration_rejects_invalid_thresholds() -> None:
    with pytest.raises(ElectricalModelError, match="thresholds"):
        ElectricalSubsystem(ElectricalConfig(transfer_threshold_pu=0.99, recovery_threshold_pu=0.90))
