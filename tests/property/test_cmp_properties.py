from dataclasses import replace

import pytest

from semifab_poc.simulation.cmp import (
    CmpConfig,
    CmpHoldReason,
    CmpMode,
    CmpModelError,
    CmpSubsystem,
)


def test_exposure_is_monotone_in_pressure_at_fixed_kinematics() -> None:
    model = CmpSubsystem()
    exposures = [
        model.pressure_velocity_exposure(pressure, 8.0, 6.0)
        for pressure in (0.0, 10_000.0, 30_000.0, 60_000.0)
    ]
    assert exposures == sorted(exposures)
    assert exposures[0] == 0.0
    assert exposures[-1] > exposures[-2]


def test_uniform_speed_scaling_obeys_velocity_exponent() -> None:
    model = CmpSubsystem()
    low = model.pressure_velocity_exposure(30_000.0, 4.0, 3.0)
    high = model.pressure_velocity_exposure(30_000.0, 8.0, 6.0)
    assert high / low == pytest.approx(2.0**model.config.velocity_exponent, rel=1.0e-12)


def test_all_nonpolish_modes_have_zero_material_removal() -> None:
    model = CmpSubsystem()
    for mode in (
        CmpMode.IDLE,
        CmpMode.PREPARE,
        CmpMode.DRESS,
        CmpMode.HOLD,
        CmpMode.RECOVER,
        CmpMode.COMPLETE,
    ):
        state = replace(
            model.reset(),
            mode=mode,
            hold_reason=(
                CmpHoldReason.REQUESTED if mode is CmpMode.HOLD else CmpHoldReason.NONE
            ),
        )
        next_state = model.step(state, None, None, 0.01)
        assert next_state.instantaneous_mrr_m_s == 0.0
        assert next_state.cumulative_removal_m == 0.0
        assert next_state.active_polish_time_s == 0.0


def test_fixed_action_boundary_history_replays_deterministically() -> None:
    model = CmpSubsystem()

    def replay():
        state = model.reset()
        trace = []
        for step in range(200):
            action = {
                "mode_request": "PREPARE" if step < 50 else "POLISH",
                "contact_pressure_command_pa": 27_000.0,
                "platen_speed_command_rad_s": 7.5,
                "head_speed_command_rad_s": 5.5,
            }
            state = model.step(state, action, None, 0.01)
            trace.append(state)
        return trace

    assert replay() == replay()


def test_timestep_refinement_reduces_dynamic_trace_error() -> None:
    model = CmpSubsystem()

    def simulate(dt_s: float):
        state = model.nominal_polish_state()
        for _ in range(round(1.0 / dt_s)):
            state = model.step(
                state,
                {"contact_pressure_command_pa": 0.70 * model.config.nominal_contact_pressure_pa},
                None,
                dt_s,
            )
        return state

    reference = simulate(0.0025)
    coarse = simulate(0.04)
    fine = simulate(0.01)

    def normalized_error(state) -> float:
        return (
            abs(state.contact_pressure_pa - reference.contact_pressure_pa)
            / model.config.nominal_contact_pressure_pa
            + abs(state.interface_temperature_k - reference.interface_temperature_k)
            + abs(state.cumulative_removal_m - reference.cumulative_removal_m)
            / max(reference.cumulative_removal_m, 1.0e-30)
        )

    assert normalized_error(fine) < normalized_error(coarse)


def test_consumable_states_remain_bounded_during_long_polish_and_dress() -> None:
    model = CmpSubsystem()
    state = model.nominal_polish_state()
    for _ in range(2_000):
        state = model.step(state, None, None, 0.05)
    state = model.step(state, {"mode_request": "DRESS", "dresser_command": 1.0}, None, 0.05)
    for _ in range(1_000):
        state = model.step(state, {"mode_request": "DRESS", "dresser_command": 1.0}, None, 0.05)

    assert 0.0 <= state.pad_surface_activity <= 1.0
    assert 0.0 <= state.pad_remaining_life <= 1.0
    assert 0.0 <= state.dresser_effectiveness <= 1.0
    assert state.instantaneous_mrr_m_s == 0.0


def test_zero_temperature_sensitivity_is_a_structural_null() -> None:
    model = CmpSubsystem(replace(CmpConfig(), temperature_sensitivity_k_inv=0.0))
    cold = model.nominal_polish_state()
    warm = model.nominal_polish_state()
    for _ in range(100):
        cold = model.step(cold, None, {"coolant_temperature_k": 283.15}, 0.01)
        warm = model.step(warm, None, {"coolant_temperature_k": 303.15}, 0.01)
    assert cold.interface_temperature_k < warm.interface_temperature_k
    assert cold.instantaneous_mrr_m_s == warm.instantaneous_mrr_m_s


def test_sensor_corruption_cannot_enter_cmp_physical_boundary() -> None:
    model = CmpSubsystem()
    with pytest.raises(CmpModelError, match="unknown CMP boundary"):
        model.step(
            model.reset(),
            None,
            {"pressure_sensor_bias_pa": 1_000.0},
            0.01,
        )


def test_step_does_not_mutate_immutable_input_state() -> None:
    model = CmpSubsystem()
    state = model.nominal_polish_state()
    snapshot = state
    next_state = model.step(state, None, None, 0.01)
    assert state == snapshot
    assert next_state is not state
