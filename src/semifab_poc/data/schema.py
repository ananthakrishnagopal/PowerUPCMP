"""Typed records for the frozen canonical data schema.

These records intentionally keep simulated latent state, observed sensor state,
and public measured output as different Python types. A sensor corruption model
can therefore not accidentally return a latent record to an online consumer.
"""

from __future__ import annotations

import math
import re
from datetime import date, datetime
from enum import Enum
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DataModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, validate_assignment=True)


class SemanticClass(str, Enum):
    MEASURED_PROCESS_OUTPUT = "MEASURED_PROCESS_OUTPUT"
    SIMULATED_PHYSICAL_STATE = "SIMULATED_PHYSICAL_STATE"
    OBSERVED_SENSOR_STATE = "OBSERVED_SENSOR_STATE"
    PROCESS_EXCURSION = "PROCESS_EXCURSION"
    QUALITY_RISK_PROXY = "QUALITY_RISK_PROXY"
    PHYSICAL_DEFECT = "PHYSICAL_DEFECT"
    YIELD_OUTCOME = "YIELD_OUTCOME"
    MODEL_OUTPUT = "MODEL_OUTPUT"
    CONTROL_ACTION = "CONTROL_ACTION"
    SAFETY_DECISION = "SAFETY_DECISION"


class DataOrigin(str, Enum):
    PUBLIC_MEASURED = "PUBLIC_MEASURED"
    SYNTHETIC_SIMULATOR = "SYNTHETIC_SIMULATOR"
    DERIVED_PUBLIC_DATA = "DERIVED_PUBLIC_DATA"
    DERIVED_SYNTHETIC = "DERIVED_SYNTHETIC"
    CONFIGURATION = "CONFIGURATION"


class QualityFlag(str, Enum):
    VALID = "VALID"
    MISSING = "MISSING"
    DELAYED = "DELAYED"
    DROPPED = "DROPPED"
    STUCK = "STUCK"
    BIASED = "BIASED"
    DRIFTING = "DRIFTING"
    QUANTISED = "QUANTISED"
    OUT_OF_RANGE = "OUT_OF_RANGE"
    TIMESTAMP_JITTERED = "TIMESTAMP_JITTERED"
    UNIT_UNRESOLVED = "UNIT_UNRESOLVED"
    INVALID = "INVALID"


class SourceUnitStatus(str, Enum):
    """Whether a public source declares the physical unit of a value."""

    DECLARED = "DECLARED"
    NATIVE_UNDECLARED = "NATIVE_UNDECLARED"
    UNKNOWN = "UNKNOWN"


class RootCause(str, Enum):
    GRID_VOLTAGE_SAG = "GRID_VOLTAGE_SAG"
    GRID_VOLTAGE_SWELL = "GRID_VOLTAGE_SWELL"
    GRID_INTERRUPTION = "GRID_INTERRUPTION"
    GRID_FREQUENCY_DEVIATION = "GRID_FREQUENCY_DEVIATION"
    UPS_TRANSFER = "UPS_TRANSFER"
    VFD_DERATING = "VFD_DERATING"
    PUMP_TRIP = "PUMP_TRIP"
    VALVE_RESTRICTION = "VALVE_RESTRICTION"
    TOOL_DEMAND_SPIKE = "TOOL_DEMAND_SPIKE"
    THERMAL_EXCURSION = "THERMAL_EXCURSION"
    PRESSURE_SENSOR_FAULT = "PRESSURE_SENSOR_FAULT"
    FLOW_SENSOR_FAULT = "FLOW_SENSOR_FAULT"
    UNKNOWN = "UNKNOWN"


_SIGNAL_DEFINITIONS: dict[str, dict[str, Any]] = {
    "electrical.grid_voltage": {"unit": "pu", "minimum": 0.0, "maximum": 1.5},
    "electrical.grid_frequency": {"unit": "Hz", "minimum": 0.0, "maximum": 100.0},
    "electrical.ups_output_voltage": {"unit": "pu", "minimum": 0.0, "maximum": 1.5},
    "electrical.ups_output_frequency": {"unit": "Hz", "minimum": 0.0, "maximum": 100.0},
    "electrical.ups_battery_energy": {"unit": "J", "minimum": 0.0},
    "electrical.ups_load_power": {"unit": "W", "minimum": 0.0},
    "electrical.ups_mode": {
        "unit": "1",
        "values": {"GRID", "TRANSFER", "BATTERY", "BYPASS", "RECOVERY"},
    },
    "drive.vfd_command": {"unit": "pu", "minimum": 0.0, "maximum": 1.0},
    "drive.vfd_available_output": {"unit": "pu", "minimum": 0.0, "maximum": 1.0},
    "drive.vfd_derating": {"unit": "1", "minimum": 0.0, "maximum": 1.0},
    "drive.vfd_trip_state": {"unit": "1", "boolean": True},
    "drive.motor_angular_speed": {"unit": "rad/s", "minimum": 0.0},
    "pump.speed_ratio": {"unit": "1", "minimum": 0.0, "maximum": 1.2},
    "pump.volumetric_flow": {"unit": "m^3/s", "minimum": 0.0},
    "pump.head": {"unit": "Pa", "minimum": 0.0},
    "pump.power": {"unit": "W", "minimum": 0.0},
    "pump.operating_point_residual": {"unit": "Pa"},
    "upw.supply_pressure": {"unit": "Pa", "minimum": 0.0},
    "upw.return_pressure": {"unit": "Pa", "minimum": 0.0},
    "upw.tool_flow": {"unit": "m^3/s", "minimum": 0.0},
    "upw.valve_position": {"unit": "1", "minimum": 0.0, "maximum": 1.0},
    "upw.tool_demand": {"unit": "m^3/s", "minimum": 0.0},
    "upw.pump_inflow": {"unit": "m^3/s", "minimum": 0.0},
    "upw.return_flow": {"unit": "m^3/s", "minimum": 0.0},
    "upw.relief_flow": {"unit": "m^3/s", "minimum": 0.0},
    "upw.storage_flow": {"unit": "m^3/s"},
    "upw.mass_balance_residual": {"unit": "m^3/s"},
    "upw.temperature": {"unit": "K", "minimum": 273.15, "maximum": 373.15},
    "upw.conductivity_proxy": {"unit": "S/m", "minimum": 0.0},
    "upw.water_quality_deviation_proxy": {"unit": "1", "minimum": 0.0, "maximum": 1.0},
    "coupling.topology": {
        "unit": "1",
        "values": {
            "NO_CONNECTION",
            "DRESSING_WATER_SUPPORT",
            "THERMAL_LOOP",
            "SYNTHETIC_SLURRY_SUPPORT",
        },
    },
    "coupling.pressure_ratio": {"unit": "1", "minimum": 0.0},
    "coupling.flow_ratio": {"unit": "1", "minimum": 0.0},
    "coupling.pressure_support": {"unit": "1", "minimum": 0.0, "maximum": 1.0},
    "coupling.flow_support": {"unit": "1", "minimum": 0.0, "maximum": 1.0},
    "coupling.hydraulic_support": {"unit": "1", "minimum": 0.0, "maximum": 1.0},
    "coupling.effective_availability": {"unit": "1", "minimum": 0.0, "maximum": 1.0},
    "coupling.dressing_availability": {"unit": "1", "minimum": 0.0, "maximum": 1.0},
    "coupling.slurry_utility_availability": {"unit": "1", "minimum": 0.0, "maximum": 1.0},
    "coupling.coolant_temperature": {"unit": "K", "minimum": 273.15, "maximum": 353.15},
    "coupling.cooling_conductance_factor": {"unit": "1", "minimum": 0.0, "maximum": 2.0},
    "cmp.process_mode": {
        "unit": "1",
        "values": {"IDLE", "PREPARE", "POLISH", "DRESS", "HOLD", "RECOVER", "COMPLETE"},
    },
    "cmp.contact_pressure_command": {"unit": "Pa", "minimum": 0.0},
    "cmp.contact_pressure": {"unit": "Pa", "minimum": 0.0},
    "cmp.relative_velocity": {"unit": "m/s", "minimum": 0.0},
    "cmp.head_angular_speed": {"unit": "rad/s"},
    "cmp.platen_angular_speed": {"unit": "rad/s"},
    "cmp.slurry_flow": {"unit": "m^3/s", "minimum": 0.0},
    "cmp.slurry_availability": {"unit": "1", "minimum": 0.0, "maximum": 1.0},
    "cmp.pressure_velocity_exposure": {"unit": "1", "minimum": 0.0},
    "cmp.interface_temperature": {"unit": "K", "minimum": 273.15, "maximum": 353.15},
    "cmp.pad_surface_activity": {"unit": "1", "minimum": 0.0, "maximum": 1.0},
    "cmp.pad_remaining_life": {"unit": "1", "minimum": 0.0, "maximum": 1.0},
    "cmp.dresser_effectiveness": {"unit": "1", "minimum": 0.0, "maximum": 1.0},
    "cmp.dressing_activity": {"unit": "1", "minimum": 0.0, "maximum": 1.0},
    "cmp.pad_age": {"unit": "s", "minimum": 0.0},
    "cmp.dresser_age": {"unit": "s", "minimum": 0.0},
    "cmp.process_discrepancy": {"unit": "m/s"},
    "cmp.thermal_energy_residual": {"unit": "W"},
    "cmp.mrr": {"unit": "m/s", "minimum": 0.0},
    "cmp.mrr_physics": {"unit": "m/s", "minimum": 0.0},
    "cmp.mrr_deviation": {"unit": "m/s"},
    "cmp.cumulative_removal": {"unit": "m", "minimum": 0.0},
    "cmp.active_polish_time": {"unit": "s", "minimum": 0.0},
    "cmp.stage_average_mrr": {"unit": "m/s", "minimum": 0.0},
    "cmp.spatial_uniformity_proxy": {"unit": "1", "minimum": 0.0},
}

_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _validate_signal(signal_id: str, value: Any, unit: str) -> None:
    definition = _SIGNAL_DEFINITIONS.get(signal_id)
    if definition is None:
        raise ValueError(f"unknown canonical signal_id: {signal_id}")
    if unit != definition["unit"]:
        raise ValueError(f"{signal_id} requires unit {definition['unit']!r}, got {unit!r}")
    if value is None:
        return
    if definition.get("boolean"):
        if not isinstance(value, bool):
            raise ValueError(f"{signal_id} requires a boolean value")
        return
    if "values" in definition:
        if value not in definition["values"]:
            raise ValueError(f"{signal_id} value {value!r} is not a canonical enum value")
        return
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{signal_id} requires a finite numeric value")
    numeric = float(value)
    if not math.isfinite(numeric):
        raise ValueError(f"{signal_id} value must be finite")
    if "minimum" in definition and numeric < definition["minimum"]:
        raise ValueError(f"{signal_id} value is below {definition['minimum']}")
    if "maximum" in definition and numeric > definition["maximum"]:
        raise ValueError(f"{signal_id} value is above {definition['maximum']}")


def _validate_public_source_value(signal_id: str, value: Any) -> None:
    """Validate raw public numeric content without assigning canonical units."""

    if signal_id not in _SIGNAL_DEFINITIONS:
        raise ValueError(f"unknown canonical signal_id: {signal_id}")
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{signal_id} public source value must be finite numeric data")
    if not math.isfinite(float(value)):
        raise ValueError(f"{signal_id} public source value must be finite")


class RunManifest(DataModel):
    run_id: str = Field(min_length=1)
    scenario_id: str = Field(min_length=1)
    controller_id: str = Field(min_length=1)
    config_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    code_revision: str = Field(min_length=1)
    run_seed: int = Field(ge=0)
    child_seed_map: dict[str, int]
    dt_s: float = Field(gt=0.0)
    duration_s: float = Field(gt=0.0)
    started_at_utc: datetime
    software_versions: dict[str, str]
    dataset_manifest_ids: tuple[str, ...]
    parameter_provenance_ids: dict[str, str] = Field(min_length=1)
    synthetic_only: bool

    @model_validator(mode="after")
    def validate_parameter_provenance(self) -> RunManifest:
        if any(
            not isinstance(key, str)
            or not key.strip()
            or not isinstance(value, str)
            or not value.strip()
            for key, value in self.parameter_provenance_ids.items()
        ):
            raise ValueError("parameter provenance names and IDs must be non-empty strings")
        return self


class LatentStateRecord(DataModel):
    """True simulator state; never an online observation."""

    semantic_class: ClassVar[SemanticClass] = SemanticClass.SIMULATED_PHYSICAL_STATE
    data_origin: ClassVar[DataOrigin] = DataOrigin.SYNTHETIC_SIMULATOR

    run_id: str = Field(min_length=1)
    step_index: int = Field(ge=0)
    timestamp_s: float = Field(ge=0.0)
    signal_id: str = Field(min_length=1)
    value: Any
    unit: str = Field(min_length=1)
    subsystem: str = Field(min_length=1)
    provenance_id: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_signal(self) -> LatentStateRecord:
        _validate_signal(self.signal_id, self.value, self.unit)
        return self


class ObservationRecord(DataModel):
    """Sensor/communication output available to online consumers."""

    semantic_class: ClassVar[SemanticClass] = SemanticClass.OBSERVED_SENSOR_STATE

    run_id: str = Field(min_length=1)
    sample_index: int = Field(ge=0)
    source_step_index: int | None = Field(default=None, ge=0)
    source_timestamp_s: float | None = Field(default=None, ge=0.0)
    observed_timestamp_s: float = Field(ge=0.0)
    arrival_timestamp_s: float = Field(ge=0.0)
    sensor_id: str = Field(min_length=1)
    signal_id: str = Field(min_length=1)
    value: Any = None
    unit: str = Field(min_length=1)
    quality_flags: tuple[QualityFlag, ...] = ()
    uncertainty_std: float | None = Field(default=None, ge=0.0)
    data_origin: DataOrigin

    @model_validator(mode="after")
    def validate_observation(self) -> ObservationRecord:
        _validate_signal(self.signal_id, self.value, self.unit)
        if (self.source_step_index is None) != (self.source_timestamp_s is None):
            raise ValueError("source step and source timestamp must be both present or both absent")
        if (
            self.source_timestamp_s is not None
            and self.arrival_timestamp_s + 1.0e-12 < self.source_timestamp_s
        ):
            raise ValueError("arrival timestamp cannot precede source generation")
        if self.value is None and QualityFlag.MISSING not in self.quality_flags:
            raise ValueError("missing observation values require the MISSING quality flag")
        return self


class PublicMeasurementRecord(DataModel):
    """Verified public measurement; never a simulator latent state."""

    semantic_class: ClassVar[SemanticClass] = SemanticClass.MEASURED_PROCESS_OUTPUT
    data_origin: ClassVar[DataOrigin] = DataOrigin.PUBLIC_MEASURED

    dataset_id: str = Field(min_length=1)
    source_file_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_row_id: str = Field(min_length=1)
    wafer_id: str | None = None
    machine_id: str | None = None
    trace_id: str | None = None
    source_timestamp: datetime | date | float | int | None = None
    signal_id: str = Field(min_length=1)
    value: Any = None
    source_unit: str = Field(min_length=1)
    source_unit_status: SourceUnitStatus
    canonical_value: float | None = None
    canonical_unit: str | None = Field(default=None, min_length=1)
    conversion_id: str | None = Field(default=None, min_length=1)
    quality_flags: tuple[QualityFlag, ...] = ()

    @model_validator(mode="after")
    def validate_measurement(self) -> PublicMeasurementRecord:
        _validate_public_source_value(self.signal_id, self.value)
        definition = _SIGNAL_DEFINITIONS[self.signal_id]
        if self.value is None and QualityFlag.MISSING not in self.quality_flags:
            raise ValueError("null public source value requires the MISSING quality flag")
        if self.value is not None and QualityFlag.MISSING in self.quality_flags:
            raise ValueError("non-null public source value cannot carry the MISSING quality flag")

        if self.canonical_value is None:
            if self.canonical_unit is not None or self.conversion_id is not None:
                raise ValueError(
                    "null canonical_value requires null canonical_unit and conversion_id"
                )
            if self.value is not None and QualityFlag.UNIT_UNRESOLVED not in self.quality_flags:
                raise ValueError(
                    "an unconverted public source value requires UNIT_UNRESOLVED"
                )
            return self

        if self.value is None:
            raise ValueError("canonical_value cannot be present when source value is missing")
        if self.source_unit_status is not SourceUnitStatus.DECLARED:
            raise ValueError("canonical conversion requires a declared source unit")
        if self.canonical_unit != definition["unit"]:
            raise ValueError(
                f"{self.signal_id} requires canonical_unit {definition['unit']!r}, "
                f"got {self.canonical_unit!r}"
            )
        if self.conversion_id is None:
            raise ValueError("canonical conversion requires conversion_id")
        if QualityFlag.UNIT_UNRESOLVED in self.quality_flags:
            raise ValueError("converted values cannot carry UNIT_UNRESOLVED")
        _validate_signal(self.signal_id, self.canonical_value, self.canonical_unit)
        return self


def canonical_signal_definitions() -> dict[str, dict[str, Any]]:
    """Return a copy of the supported signal catalog for validators and reports."""

    return {signal_id: definition.copy() for signal_id, definition in _SIGNAL_DEFINITIONS.items()}
