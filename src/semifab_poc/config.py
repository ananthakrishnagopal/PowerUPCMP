"""Strict, serializable configuration primitives for local PoC runs."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .data.schema import canonical_signal_definitions
from .simulation.cmp import CmpConfig
from .simulation.coupling import CouplingConfig, UtilityToCmpCoupler
from .simulation.drive import DriveConfig
from .simulation.electrical import ElectricalConfig
from .simulation.pump import PumpConfig
from .simulation.sensors import SensorConfig
from .simulation.upw import UpwConfig


class ConfigError(ValueError):
    """Raised when a configuration file cannot be loaded or validated."""


class StrictModel(BaseModel):
    """Base model shared by configuration records.

    Unknown keys are rejected so a typo cannot silently change a simulation run.
    Frozen models also make configuration safe to pass across component boundaries.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, validate_assignment=True)


def _default_sensor_configs() -> tuple[SensorConfig, ...]:
    return (
        SensorConfig(
            sensor_id="upw-supply-pressure",
            signal_id="upw.supply_pressure",
            unit="Pa",
            sample_period_s=0.01,
            provenance_id="synthetic-pressure-sensor-v1",
            minimum_value=0.0,
            maximum_value=600_000.0,
        ),
        SensorConfig(
            sensor_id="upw-tool-flow",
            signal_id="upw.tool_flow",
            unit="m^3/s",
            sample_period_s=0.01,
            provenance_id="synthetic-flow-sensor-v1",
            minimum_value=0.0,
            maximum_value=5.0e-4,
        ),
        SensorConfig(
            sensor_id="upw-temperature",
            signal_id="upw.temperature",
            unit="K",
            sample_period_s=0.10,
            provenance_id="synthetic-temperature-sensor-v1",
            minimum_value=273.15,
            maximum_value=373.15,
        ),
    )


class RuntimeConfig(StrictModel):
    """Complete, typed, simulation-only runtime configuration."""

    project_name: str = Field(default="semifab_cmp_poc", min_length=1)
    schema_version: str = Field(default="2.4.0", min_length=1)
    interface_version: str = Field(default="3.2.0", min_length=1)
    seed: int = Field(default=0, ge=0)
    dt_s: float = Field(default=0.01, gt=0.0)
    duration_s: float = Field(default=10.0, gt=0.0)
    log_level: str = Field(default="INFO", min_length=1)
    artifact_dir: Path = Field(default=Path("artifacts"))
    synthetic_only: bool = True
    scenario_library: Path = Field(default=Path("configs/scenarios/library.yaml"))
    phm_data_config: Path = Field(default=Path("configs/data/phm_2016_cmp.yaml"))
    electrical: ElectricalConfig = Field(default_factory=ElectricalConfig)
    drive: DriveConfig = Field(default_factory=DriveConfig)
    pump: PumpConfig = Field(default_factory=PumpConfig)
    upw: UpwConfig = Field(default_factory=UpwConfig)
    cmp: CmpConfig = Field(default_factory=CmpConfig)
    coupling: CouplingConfig = Field(default_factory=CouplingConfig)
    sensors: tuple[SensorConfig, ...] = Field(default_factory=_default_sensor_configs, min_length=1)

    @field_validator("log_level")
    @classmethod
    def normalize_log_level(cls, value: str) -> str:
        normalized = value.upper()
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if normalized not in allowed:
            raise ValueError(f"log_level must be one of {sorted(allowed)}")
        return normalized

    @model_validator(mode="after")
    def validate_components_and_timestep(self) -> RuntimeConfig:
        supported_contract_pairs = {
            ("2.1.0", "2.0.0"),  # frozen R3 reproduction checkpoint
            ("2.2.0", "3.0.0"),  # current R4 runtime contract
            ("2.3.0", "3.1.0"),  # frozen WP08 CMP runtime contract
            ("2.4.0", "3.2.0"),  # current WP10 coupling runtime contract
        }
        if (self.schema_version, self.interface_version) not in supported_contract_pairs:
            raise ValueError(
                "unsupported schema/interface version pair; expected a frozen checkpoint pair"
            )
        if self.duration_s < self.dt_s:
            raise ValueError("duration_s must be at least one dt_s")

        self.electrical.validate()
        self.drive.validate()
        self.pump.validate()
        self.upw.validate()
        self.cmp.validate()
        self.coupling.validate()
        UtilityToCmpCoupler(self.coupling, self.upw, self.cmp)
        if self.dt_s > min(
            self.electrical.output_time_constant_s,
            self.electrical.frequency_time_constant_s,
            self.drive.motor_time_constant_s,
            self.upw.maximum_hydraulic_timestep_s,
            self.upw.minimum_thermal_time_constant_s,
            self.upw.water_quality_proxy_time_constant_s,
            self.cmp.maximum_timestep_s,
        ):
            raise ValueError("dt_s exceeds at least one configured explicit-Euler bound")

        definitions = canonical_signal_definitions()
        sensor_ids: set[str] = set()
        for sensor in self.sensors:
            sensor.validate()
            if sensor.sensor_id in sensor_ids:
                raise ValueError("sensor IDs must be unique")
            sensor_ids.add(sensor.sensor_id)
            definition = definitions.get(sensor.signal_id)
            if definition is None:
                raise ValueError(f"unknown sensor signal_id: {sensor.signal_id}")
            if sensor.unit != definition["unit"]:
                raise ValueError(
                    f"{sensor.signal_id} sensor requires unit {definition['unit']!r}"
                )
        return self

    @property
    def parameter_provenance_ids(self) -> dict[str, str]:
        """Return the component provenance map required by ``RunManifest``."""

        provenance = {
            "electrical": self.electrical.provenance_id,
            "drive": self.drive.provenance_id,
            "pump": self.pump.provenance_id,
            "upw": self.upw.provenance_id,
        }
        contract_pair = (self.schema_version, self.interface_version)
        if contract_pair in {
            ("2.3.0", "3.1.0"),
            ("2.4.0", "3.2.0"),
        }:
            provenance["cmp"] = self.cmp.provenance_id
        if contract_pair == ("2.4.0", "3.2.0"):
            provenance["coupling"] = self.coupling.provenance_id
        provenance.update(
            {f"sensor:{sensor.sensor_id}": sensor.provenance_id for sensor in self.sensors}
        )
        return provenance


def _read_yaml_mapping(path: Path) -> dict[str, Any]:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ConfigError(f"cannot read configuration {path}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise ConfigError(f"invalid YAML in {path}: {exc}") from exc
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ConfigError(f"configuration root must be a mapping: {path}")
    return raw


def load_runtime_config(path: str | Path) -> RuntimeConfig:
    """Load and strictly validate a runtime YAML configuration."""

    config_path = Path(path)
    try:
        return RuntimeConfig.model_validate(_read_yaml_mapping(config_path))
    except ConfigError:
        raise
    except Exception as exc:  # Pydantic's public exception type varies by major version.
        raise ConfigError(f"invalid runtime configuration {config_path}: {exc}") from exc


def dump_runtime_config(config: RuntimeConfig, path: str | Path) -> None:
    """Write a validated runtime configuration as YAML, without partial files."""

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(
        yaml.safe_dump(config.model_dump(mode="json"), sort_keys=False), encoding="utf-8"
    )
    temporary.replace(destination)


def runtime_config_sha256(config: RuntimeConfig) -> str:
    """Hash the canonical JSON form of a validated configuration."""

    canonical = config.model_dump(mode="json")
    if (config.schema_version, config.interface_version) in {
        ("2.1.0", "2.0.0"),
        ("2.2.0", "3.0.0"),
    }:
        # CMP configuration was introduced in schema/interface 2.3/3.1.
        # Excluding it preserves the exact canonical hashes of frozen R3/R4
        # checkpoints when they are loaded by the additive current model.
        canonical.pop("cmp", None)
        canonical.pop("coupling", None)
    elif (config.schema_version, config.interface_version) == ("2.3.0", "3.1.0"):
        # Coupling was introduced in schema/interface 2.4/3.2. Excluding it
        # preserves the exact WP08 canonical runtime hash.
        canonical.pop("coupling", None)
    payload = json.dumps(
        canonical,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
