from copy import deepcopy
from dataclasses import FrozenInstanceError
from inspect import signature
from pathlib import Path

import pytest
import yaml

from semifab_poc.simulation import (
    CmpSubsystem,
    DriveSubsystem,
    DynamicSubsystem,
    ElectricalSubsystem,
    PumpSubsystem,
    SensorModel,
    UpwSubsystem,
)


def _plant_subsystems() -> tuple[DynamicSubsystem, ...]:
    return (
        ElectricalSubsystem(),
        DriveSubsystem(),
        PumpSubsystem(),
        UpwSubsystem(),
        CmpSubsystem(),
    )


def test_all_plant_components_implement_dynamic_subsystem_v2() -> None:
    for subsystem in _plant_subsystems():
        assert isinstance(subsystem, DynamicSubsystem)
        assert subsystem.interface_version == "2.0.0"
        assert list(signature(type(subsystem).reset).parameters) == ["self", "initial_state"]
        assert list(signature(type(subsystem).step).parameters) == [
            "self",
            "state",
            "action",
            "disturbance",
            "dt_s",
        ]


def test_dynamic_subsystem_config_has_parameter_provenance_and_is_frozen() -> None:
    for subsystem in _plant_subsystems():
        assert subsystem.config.provenance_id.strip()
        with pytest.raises(FrozenInstanceError):
            subsystem.config.provenance_id = "changed"


def test_dynamic_subsystem_step_does_not_mutate_input() -> None:
    for subsystem in _plant_subsystems():
        state = subsystem.reset()
        snapshot = deepcopy(state)
        next_state = subsystem.step(state, None, None, 0.01)
        assert state == snapshot
        assert next_state is not state


def test_dynamic_subsystem_excludes_observation_boundary() -> None:
    assert not hasattr(DynamicSubsystem, "observe")
    assert all(not hasattr(subsystem, "observe") for subsystem in _plant_subsystems())
    assert hasattr(SensorModel, "sample")


def test_interface_and_schema_registry_major_versions_match() -> None:
    root = Path(__file__).parents[2] / "orchestration"
    interfaces = yaml.safe_load((root / "interface_registry.yaml").read_text(encoding="utf-8"))
    schema = yaml.safe_load((root / "canonical_schema.yaml").read_text(encoding="utf-8"))
    assert interfaces["registry_version"] == "3.2.0"
    assert interfaces["canonical_schema_version"] == "2.4.0"
    assert interfaces["interfaces"]["DynamicSubsystem"]["version"] == "2.0.0"
    assert schema["schema_version"] == "2.4.0"
    signals = {entry["id"]: entry for entry in schema["signal_catalog"]}
    assert signals["upw.water_quality_deviation_proxy"]["unit"] == "1"
    assert signals["upw.water_quality_deviation_proxy"]["physical_measurement"] is False
    assert signals["upw.conductivity_proxy"]["deprecated"] is True
    assert signals["upw.conductivity_proxy"]["emitted_by_r3_plant"] is False
    assert signals["cmp.head_angular_speed"]["valid_range"] == [None, None]
    assert signals["cmp.spatial_uniformity_proxy"]["mandatory_label"].startswith(
        "Simulated spatial-uniformity proxy"
    )
    assert signals["cmp.pad_age"]["deprecated"] is True
    assert signals["coupling.effective_availability"]["valid_range"] == [0.0, 1.0]
    assert interfaces["interfaces"]["UtilityToCmpCoupler"]["version"] == "1.0.0"
    assert interfaces["interfaces"]["SensorModel"]["version"] == "2.0.0"
    assert interfaces["interfaces"]["Scenario"]["version"] == "2.0.0"
    assert interfaces["runtime_contract"]["interface_version"] == "3.2.0"
    assert interfaces["runtime_contract"]["direct_generic_upw_to_mrr_multiplier_allowed"] is False
    assert "CmpBoundaryConditions" in interfaces["common_types"]
    assert "observe" not in interfaces["interfaces"]["DynamicSubsystem"]["methods"]
