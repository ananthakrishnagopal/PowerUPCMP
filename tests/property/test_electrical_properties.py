from semifab_poc.simulation.electrical import ElectricalSubsystem


def test_voltage_outputs_remain_bounded_across_configured_disturbances() -> None:
    model = ElectricalSubsystem()
    for voltage in (-1.0, 0.0, 0.50, 0.84, 0.85, 1.0, 1.2, 2.0):
        state = model.reset()
        for _ in range(40):
            state = model.step(state, None, {"grid_voltage_pu": voltage}, 0.01)
            assert model.config.voltage_min_pu <= state.grid_voltage_pu <= model.config.voltage_max_pu
            assert model.config.voltage_min_pu <= state.ups_output_voltage_pu <= model.config.voltage_max_pu
            assert model.config.frequency_min_hz <= state.grid_frequency_hz <= model.config.frequency_max_hz
            assert model.config.frequency_min_hz <= state.ups_output_frequency_hz <= model.config.frequency_max_hz
            assert model.config.minimum_battery_energy_j <= state.battery_energy_j <= model.config.battery_capacity_j


def test_electrical_replay_is_deterministic() -> None:
    disturbances = [
        {"grid_voltage_pu": 1.0},
        {"grid_voltage_pu": 0.70},
        {"grid_voltage_pu": 0.70, "grid_frequency_delta_hz": -0.5},
        {"grid_voltage_pu": 1.0},
    ]
    model = ElectricalSubsystem()

    def replay():
        state = model.reset()
        trace = []
        for disturbance in disturbances:
            for _ in range(10):
                state = model.step(state, None, disturbance, 0.01)
                trace.append(state)
        return trace

    assert replay() == replay()
