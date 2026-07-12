from dataclasses import fields, replace

import numpy as np
import pytest

from semifab_poc.data.schema import LatentStateRecord, canonical_signal_definitions
from semifab_poc.simulation.cmp import (
    SPATIAL_PROXY_LABEL,
    CmpBoundaryConditions,
    CmpConfig,
    CmpHoldReason,
    CmpMode,
    CmpModelError,
    CmpSubsystem,
)


def test_cmp_config_rejects_invalid_geometry_exponents_and_bounds() -> None:
    with pytest.raises(CmpModelError, match="radial_quadrature_order"):
        CmpSubsystem(replace(CmpConfig(), radial_quadrature_order=3))
    with pytest.raises(CmpModelError, match="pressure_exponent"):
        CmpSubsystem(replace(CmpConfig(), pressure_exponent=0.0))
    with pytest.raises(CmpModelError, match="nominal contact pressure"):
        CmpSubsystem(
            replace(
                CmpConfig(),
                nominal_contact_pressure_pa=70_000.0,
                maximum_contact_pressure_pa=60_000.0,
            )
        )


def test_reset_is_idle_and_nominal_reference_is_exactly_normalized() -> None:
    model = CmpSubsystem()
    idle = model.reset()
    nominal = model.nominal_polish_state()

    assert idle.mode is CmpMode.IDLE
    assert idle.instantaneous_mrr_m_s == 0.0
    assert model.constant_field_quadrature == pytest.approx(1.0, abs=1.0e-14)
    assert nominal.pressure_velocity_exposure == pytest.approx(1.0, abs=1.0e-12)
    assert nominal.instantaneous_mrr_physics_m_s == pytest.approx(
        model.config.reference_mrr_m_s,
        rel=1.0e-12,
    )
    assert (
        model.classical_preston_coefficient_pa_inv
        * model.config.nominal_contact_pressure_pa
        * model.reference_velocity_scale_m_s
    ) == pytest.approx(model.config.reference_mrr_m_s, rel=1.0e-14)


def test_signed_dual_axis_kinematics_has_required_special_cases() -> None:
    model = CmpSubsystem()
    zero = model.relative_velocity_field(0.0, 0.0)
    equal_corotation = model.relative_velocity_field(8.0, 8.0)
    counter_rotation = model.relative_velocity_field(8.0, -6.0)

    assert np.all(zero == 0.0)
    assert np.allclose(
        equal_corotation,
        8.0 * model.config.center_offset_m,
        rtol=0.0,
        atol=1.0e-14,
    )
    assert np.ptp(counter_rotation) > 0.0


def test_area_quadrature_refinement_converges_for_relative_velocity() -> None:
    coarse = CmpSubsystem(replace(CmpConfig(), radial_quadrature_order=8, angular_quadrature_order=32))
    medium = CmpSubsystem()
    fine = CmpSubsystem(replace(CmpConfig(), radial_quadrature_order=32, angular_quadrature_order=128))

    values = [
        model.area_mean_relative_velocity(8.0, 6.0)
        for model in (coarse, medium, fine)
    ]
    assert abs(values[1] - values[2]) < 1.0e-10
    assert abs(values[0] - values[2]) < 1.0e-7


def test_modes_gate_removal_and_hold_preserves_cumulative_removal() -> None:
    model = CmpSubsystem()
    state = model.reset()
    prepared = model.step(state, {"mode_request": "PREPARE"}, None, 0.01)
    polishing = model.step(prepared, {"mode_request": "POLISH"}, None, 0.01)
    held = model.step(polishing, {"mode_request": "HOLD"}, None, 0.01)

    assert prepared.instantaneous_mrr_m_s == 0.0
    assert prepared.active_polish_time_s == 0.0
    assert polishing.instantaneous_mrr_m_s > 0.0
    assert polishing.active_polish_time_s == pytest.approx(0.01)
    assert polishing.cumulative_removal_m > 0.0
    assert held.mode is CmpMode.HOLD
    assert held.hold_reason is CmpHoldReason.REQUESTED
    assert held.instantaneous_mrr_m_s == 0.0
    assert held.cumulative_removal_m == polishing.cumulative_removal_m
    assert held.active_polish_time_s == polishing.active_polish_time_s


def test_recovery_requires_valid_dwell_before_polish() -> None:
    model = CmpSubsystem()
    state = model.nominal_polish_state()
    state = model.step(state, None, {"force_hold": True}, 0.01)
    assert state.mode is CmpMode.HOLD
    assert state.hold_reason is CmpHoldReason.FORCED_BOUNDARY

    state = model.step(state, {"mode_request": "RECOVER"}, None, 0.01)
    for _ in range(48):
        state = model.step(state, None, None, 0.01)
    assert state.mode is CmpMode.RECOVER
    state = model.step(state, {"mode_request": "POLISH"}, None, 0.01)
    assert state.mode is CmpMode.POLISH


def test_invalid_transition_unknown_action_and_unknown_boundary_are_rejected() -> None:
    model = CmpSubsystem()
    with pytest.raises(CmpModelError, match="invalid CMP mode transition"):
        model.step(model.reset(), {"mode_request": "POLISH"}, None, 0.01)
    with pytest.raises(CmpModelError, match="unknown CMP action"):
        model.step(model.reset(), {"pressure_pa": 1.0}, None, 0.01)
    with pytest.raises(CmpModelError, match="unknown CMP boundary"):
        model.step(model.reset(), None, {"upw_pressure_pa": 300_000.0}, 0.01)


def test_dressing_restores_activity_but_consumes_pad_and_dresser() -> None:
    model = CmpSubsystem()
    degraded = replace(
        model.reset(),
        mode=CmpMode.DRESS,
        pad_surface_activity=0.50,
        pad_remaining_life=0.80,
        dresser_effectiveness=0.90,
        dresser_command=1.0,
    )
    dressed = model.step(
        degraded,
        {"mode_request": "DRESS", "dresser_command": 1.0},
        {"dressing_availability": 1.0},
        0.05,
    )

    assert dressed.pad_surface_activity > degraded.pad_surface_activity
    assert dressed.pad_remaining_life < degraded.pad_remaining_life
    assert dressed.dresser_effectiveness < degraded.dresser_effectiveness
    assert dressed.instantaneous_mrr_m_s == 0.0


def test_interface_energy_balance_residual_is_numerically_closed() -> None:
    model = CmpSubsystem()
    next_state = model.step(model.nominal_polish_state(), None, None, 0.01)
    assert abs(next_state.thermal_energy_residual_w) < 1.0e-7
    assert next_state.interface_temperature_k > model.config.interface_reference_temperature_k


def test_boundary_defaults_are_neutral_for_custom_reference_temperature() -> None:
    config = replace(
        CmpConfig(),
        interface_reference_temperature_k=300.0,
        slurry_supply_temperature_k=300.0,
    )
    boundary = CmpBoundaryConditions.from_mapping(None, config)
    assert boundary.coolant_temperature_k == 300.0
    assert boundary.dressing_availability == 1.0
    assert boundary.slurry_utility_availability == 1.0
    assert boundary.force_hold is False


def test_spatial_output_carries_mandatory_proxy_label() -> None:
    model = CmpSubsystem()
    proxy = model.spatial_uniformity_proxy(model.nominal_polish_state())
    assert proxy.label == SPATIAL_PROXY_LABEL
    assert len(proxy.radial_positions_m) == model.config.radial_quadrature_order
    assert len(proxy.normalized_exposure) == model.config.radial_quadrature_order
    assert proxy.coefficient_of_variation >= 0.0


def test_parameter_provenance_classification_is_complete() -> None:
    expected = {field.name for field in fields(CmpConfig)} - {"provenance_id"}
    actual = CmpSubsystem.parameter_provenance_classes()
    assert set(actual) == expected
    assert set(actual.values()) <= {
        "Literature-supported",
        "Data-calibrated",
        "Engineering approximation",
        "Synthetic assumption",
    }


def test_cmp_latent_values_all_validate_against_canonical_signal_catalog() -> None:
    model = CmpSubsystem()
    state = model.nominal_polish_state()
    values = model.latent_signal_values(state, model.config)
    definitions = canonical_signal_definitions()
    for signal_id, value in values.items():
        definition = definitions[signal_id]
        record = LatentStateRecord(
            run_id="cmp-unit",
            step_index=0,
            timestamp_s=0.0,
            signal_id=signal_id,
            value=value,
            unit=definition["unit"],
            subsystem="cmp",
            provenance_id=model.config.provenance_id,
        )
        assert record.value == value
