from dataclasses import replace

import pytest

from semifab_poc.simulation.cmp import CmpHoldReason, CmpMode, CmpSubsystem
from semifab_poc.simulation.coupling import (
    CouplingConfig,
    UtilityCmpTopology,
    UtilityToCmpCoupler,
)
from semifab_poc.simulation.upw import UpwState, UpwSubsystem


def state_at(supply_pressure_pa: float, tool_flow_m3_s: float, temperature_k: float = 293.15) -> UpwState:
    return UpwState(
        supply_pressure_pa=supply_pressure_pa,
        return_pressure_pa=min(100_000.0, supply_pressure_pa),
        tool_flow_m3_s=tool_flow_m3_s,
        valve_position=1.0,
        tool_demand_m3_s=1.0e-4,
        temperature_k=temperature_k,
        water_quality_deviation_proxy=0.0,
    )


def dressing_coupler(link_strength: float = 1.0) -> UtilityToCmpCoupler:
    return UtilityToCmpCoupler(
        replace(
            CouplingConfig(),
            topology=UtilityCmpTopology.DRESSING_WATER_SUPPORT,
            link_strength=link_strength,
        )
    )


def test_effective_availability_is_monotone_in_pressure_at_fixed_flow() -> None:
    coupler = dressing_coupler()
    values = [
        coupler.couple(state_at(pressure, 1.0e-4)).effective_availability
        for pressure in (100_000.0, 180_000.0, 240_000.0, 285_000.0, 300_000.0)
    ]
    assert values == sorted(values)
    assert values[0] == 0.0
    assert values[-1] == 1.0


def test_effective_availability_is_monotone_in_flow_at_fixed_pressure() -> None:
    coupler = dressing_coupler()
    values = [
        coupler.couple(state_at(300_000.0, flow)).effective_availability
        for flow in (0.0, 5.0e-5, 7.0e-5, 9.5e-5, 1.0e-4)
    ]
    assert values == sorted(values)
    assert values[0] == 0.0
    assert values[-1] == 1.0


def test_degraded_availability_is_nonincreasing_in_link_strength() -> None:
    state = state_at(240_000.0, 8.0e-5)
    values = [
        dressing_coupler(link).couple(state).effective_availability
        for link in (0.0, 0.25, 0.50, 0.75, 1.0)
    ]
    assert values == sorted(values, reverse=True)
    assert values[0] == 1.0


def test_coupling_is_deterministic_and_does_not_mutate_input() -> None:
    coupler = dressing_coupler()
    state = state_at(240_000.0, 8.0e-5)
    snapshot = state
    first = coupler.couple(state)
    second = coupler.couple(state)
    assert first == second
    assert state == snapshot


def test_all_support_states_remain_bounded_over_upw_envelope() -> None:
    coupler = dressing_coupler()
    for pressure in (100_000.0, 180_000.0, 240_000.0, 300_000.0, 600_000.0):
        for flow in (0.0, 5.0e-5, 1.0e-4, 5.0e-4):
            result = coupler.couple(state_at(pressure, flow))
            assert 0.0 <= result.pressure_support <= 1.0
            assert 0.0 <= result.flow_support <= 1.0
            assert 0.0 <= result.hydraulic_support <= 1.0
            assert 0.0 <= result.effective_availability <= 1.0


def test_default_temperature_to_mrr_path_is_a_structural_null() -> None:
    config = replace(
        CouplingConfig(),
        topology=UtilityCmpTopology.THERMAL_LOOP,
        link_strength=1.0,
    )
    coupler = UtilityToCmpCoupler(config)
    model = CmpSubsystem()
    cold = model.nominal_polish_state()
    warm = model.nominal_polish_state()
    cold_boundary = coupler.couple(state_at(300_000.0, 1.0e-4, 283.15)).boundary
    warm_boundary = coupler.couple(state_at(300_000.0, 1.0e-4, 303.15)).boundary
    for _ in range(100):
        cold = model.step(cold, None, cold_boundary.as_mapping(), 0.01)
        warm = model.step(warm, None, warm_boundary.as_mapping(), 0.01)
    assert cold.interface_temperature_k < warm.interface_temperature_k
    assert cold.instantaneous_mrr_m_s == warm.instantaneous_mrr_m_s


def test_dressing_disturbance_changes_later_mrr_only_through_pad_memory() -> None:
    model = CmpSubsystem()
    initial = replace(
        model.reset(),
        mode=CmpMode.DRESS,
        hold_reason=CmpHoldReason.NONE,
        pad_surface_activity=0.50,
        pad_remaining_life=0.90,
        dresser_effectiveness=0.90,
        dresser_command=1.0,
    )
    healthy_boundary = dressing_coupler().couple(UpwSubsystem().reset()).boundary
    failed_boundary = dressing_coupler().couple(state_at(150_000.0, 0.0)).boundary
    healthy = initial
    failed = initial
    for _ in range(200):
        action = {"mode_request": "DRESS", "dresser_command": 1.0}
        healthy = model.step(healthy, action, healthy_boundary.as_mapping(), 0.05)
        failed = model.step(failed, action, failed_boundary.as_mapping(), 0.05)

    assert healthy.instantaneous_mrr_m_s == failed.instantaneous_mrr_m_s == 0.0
    assert healthy.pad_surface_activity > failed.pad_surface_activity
    for requested in ("PREPARE", "POLISH"):
        healthy = model.step(healthy, {"mode_request": requested}, None, 0.01)
        failed = model.step(failed, {"mode_request": requested}, None, 0.01)
    assert healthy.instantaneous_mrr_m_s > failed.instantaneous_mrr_m_s


def test_no_connection_matches_neutral_cmp_boundary_for_arbitrary_upw_trace() -> None:
    coupler = UtilityToCmpCoupler()
    model = CmpSubsystem()
    coupled = model.nominal_polish_state()
    neutral = model.nominal_polish_state()
    for step in range(100):
        pressure = 100_000.0 + 5_000.0 * (step % 50)
        flow = 1.0e-4 * ((step % 20) / 20.0)
        boundary = coupler.couple(state_at(pressure, flow, 280.0 + step * 0.1)).boundary
        coupled = model.step(coupled, None, boundary.as_mapping(), 0.01)
        neutral = model.step(neutral, None, None, 0.01)
    assert coupled == neutral

