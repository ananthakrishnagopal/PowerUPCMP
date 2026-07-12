from dataclasses import fields, replace
from pathlib import Path

import pytest

from semifab_poc.config import load_runtime_config
from semifab_poc.data.schema import LatentStateRecord, canonical_signal_definitions
from semifab_poc.simulation.cmp import CmpBoundaryConditions, CmpConfig
from semifab_poc.simulation.coupling import (
    PROVENANCE_CLASSES,
    CouplingConfig,
    CouplingModelError,
    UtilityCmpTopology,
    UtilityToCmpCoupler,
)
from semifab_poc.simulation.upw import UpwConfig, UpwState, UpwSubsystem


def degraded_upw_state(*, temperature_k: float = 293.15, quality: float = 0.0) -> UpwState:
    return UpwState(
        supply_pressure_pa=150_000.0,
        return_pressure_pa=100_000.0,
        tool_flow_m3_s=0.0,
        valve_position=1.0,
        tool_demand_m3_s=1.0e-4,
        temperature_k=temperature_k,
        water_quality_deviation_proxy=quality,
    )


def connected_config(topology: UtilityCmpTopology, link_strength: float = 1.0) -> CouplingConfig:
    return replace(
        CouplingConfig(),
        topology=topology,
        link_strength=link_strength,
    )


def test_config_rejects_invalid_topology_thresholds_references_and_null_link() -> None:
    with pytest.raises(CouplingModelError, match="NO_CONNECTION"):
        UtilityToCmpCoupler(replace(CouplingConfig(), link_strength=0.1))
    with pytest.raises(CouplingModelError, match="pressure fractions"):
        UtilityToCmpCoupler(
            replace(CouplingConfig(), pressure_zero_fraction=0.95)
        )
    with pytest.raises(CouplingModelError, match="reference_tool_flow"):
        UtilityToCmpCoupler(replace(CouplingConfig(), reference_tool_flow_m3_s=0.0))
    with pytest.raises(CouplingModelError, match="reference UPW temperature"):
        UtilityToCmpCoupler(
            replace(CouplingConfig(), reference_upw_temperature_k=400.0)
        )


def test_nominal_upw_state_is_neutral_for_every_topology() -> None:
    upw = UpwSubsystem()
    nominal = upw.reset()
    neutral = CmpBoundaryConditions.from_mapping(None, CmpConfig())

    for topology in UtilityCmpTopology:
        link = 0.0 if topology is UtilityCmpTopology.NO_CONNECTION else 1.0
        result = UtilityToCmpCoupler(connected_config(topology, link)).couple(nominal)
        assert result.hydraulic_support == 1.0
        assert result.effective_availability == 1.0
        assert result.boundary == neutral


def test_no_connection_is_exactly_neutral_for_degraded_utility_state() -> None:
    coupler = UtilityToCmpCoupler()
    result = coupler.couple(degraded_upw_state(temperature_k=320.0, quality=1.0))

    assert result.hydraulic_support == 0.0
    assert result.effective_availability == 1.0
    assert result.boundary == CmpBoundaryConditions.from_mapping(None, CmpConfig())


def test_zero_link_is_exactly_neutral_for_every_connected_topology() -> None:
    neutral = CmpBoundaryConditions.from_mapping(None, CmpConfig())
    for topology in UtilityCmpTopology:
        if topology is UtilityCmpTopology.NO_CONNECTION:
            continue
        result = UtilityToCmpCoupler(connected_config(topology, 0.0)).couple(
            degraded_upw_state(temperature_k=320.0)
        )
        assert result.effective_availability == 1.0
        assert result.boundary == neutral


def test_each_connected_topology_changes_only_its_declared_boundary_fields() -> None:
    state = degraded_upw_state(temperature_k=303.15)
    dressing = UtilityToCmpCoupler(
        connected_config(UtilityCmpTopology.DRESSING_WATER_SUPPORT)
    ).couple(state)
    thermal = UtilityToCmpCoupler(
        connected_config(UtilityCmpTopology.THERMAL_LOOP)
    ).couple(state)
    slurry = UtilityToCmpCoupler(
        connected_config(UtilityCmpTopology.SYNTHETIC_SLURRY_SUPPORT)
    ).couple(state)

    assert dressing.boundary.dressing_availability == 0.0
    assert dressing.boundary.slurry_utility_availability == 1.0
    assert dressing.boundary.cooling_conductance_factor == 1.0
    assert thermal.boundary.dressing_availability == 1.0
    assert thermal.boundary.slurry_utility_availability == 1.0
    assert thermal.boundary.cooling_conductance_factor == 0.0
    assert thermal.boundary.coolant_temperature_k == pytest.approx(303.15)
    assert slurry.boundary.dressing_availability == 1.0
    assert slurry.boundary.slurry_utility_availability == 0.0
    assert slurry.boundary.cooling_conductance_factor == 1.0
    for result in (dressing, thermal, slurry):
        assert result.boundary.process_discrepancy_m_s == 0.0
        assert result.boundary.force_hold is False


def test_water_quality_proxy_has_no_coupling_effect() -> None:
    coupler = UtilityToCmpCoupler(
        connected_config(UtilityCmpTopology.DRESSING_WATER_SUPPORT)
    )
    clean = coupler.couple(degraded_upw_state(quality=0.0))
    degraded = coupler.couple(degraded_upw_state(quality=1.0))
    assert clean == degraded


def test_thermal_map_rejects_a_coolant_boundary_outside_cmp_envelope() -> None:
    coupler = UtilityToCmpCoupler(connected_config(UtilityCmpTopology.THERMAL_LOOP))
    with pytest.raises(CouplingModelError, match="invalid CMP boundary"):
        coupler.couple(degraded_upw_state(temperature_k=373.15))


def test_parameter_and_functional_provenance_are_complete() -> None:
    coupler = UtilityToCmpCoupler(
        connected_config(UtilityCmpTopology.DRESSING_WATER_SUPPORT)
    )
    expected = {field.name for field in fields(CouplingConfig)} - {
        "provenance_id",
        "topology",
    }
    classes = coupler.parameter_provenance_classes()
    metadata = coupler.parameter_metadata()

    assert set(classes) == expected
    assert set(classes.values()) == {"Synthetic assumption"}
    assert {record.name for record in metadata} == expected
    assert all(record.provenance_class in PROVENANCE_CLASSES for record in metadata)
    assert set(coupler.functional_form_provenance_classes().values()) <= PROVENANCE_CLASSES


def test_coupling_latent_values_validate_against_canonical_catalog() -> None:
    coupler = UtilityToCmpCoupler(
        connected_config(UtilityCmpTopology.DRESSING_WATER_SUPPORT)
    )
    result = coupler.couple(UpwSubsystem().reset())
    definitions = canonical_signal_definitions()
    for signal_id, value in coupler.latent_signal_values(result).items():
        record = LatentStateRecord(
            run_id="coupling-unit",
            step_index=0,
            timestamp_s=0.0,
            signal_id=signal_id,
            value=value,
            unit=definitions[signal_id]["unit"],
            subsystem="coupling",
            provenance_id=coupler.config.provenance_id,
        )
        assert record.value == value


def test_all_coupling_profiles_load_strictly() -> None:
    root = Path(__file__).parents[2]
    expected = {
        "no_connection.yaml": UtilityCmpTopology.NO_CONNECTION,
        "dressing_water_support.yaml": UtilityCmpTopology.DRESSING_WATER_SUPPORT,
        "thermal_loop.yaml": UtilityCmpTopology.THERMAL_LOOP,
        "synthetic_slurry_support.yaml": UtilityCmpTopology.SYNTHETIC_SLURRY_SUPPORT,
    }
    for filename, topology in expected.items():
        config = load_runtime_config(root / "configs" / "coupling" / filename)
        assert UtilityCmpTopology(config.coupling.topology) is topology

