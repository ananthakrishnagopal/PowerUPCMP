"""Declared, bounded utility-to-CMP connection topologies.

The coupler is a stateless physical boundary map.  It accepts validated latent
UPW state and emits the frozen CMP boundary type; it never consumes observed
sensor values, computes MRR, or makes a control/safety decision.  All values
are synthetic simulator quantities unless a future calibration record says
otherwise.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, fields
from enum import Enum
from numbers import Real

from .cmp import CmpBoundaryConditions, CmpConfig, CmpModelError
from .upw import UpwConfig, UpwState


PROVENANCE_CLASSES = frozenset(
    {
        "Literature-supported",
        "Data-calibrated",
        "Engineering approximation",
        "Synthetic assumption",
    }
)


class CouplingModelError(ValueError):
    """Raised when a coupling configuration, input, or result is invalid."""


class UtilityCmpTopology(str, Enum):
    """Mutually exclusive structural utility connections into CMP."""

    NO_CONNECTION = "NO_CONNECTION"
    DRESSING_WATER_SUPPORT = "DRESSING_WATER_SUPPORT"
    THERMAL_LOOP = "THERMAL_LOOP"
    SYNTHETIC_SLURRY_SUPPORT = "SYNTHETIC_SLURRY_SUPPORT"


@dataclass(frozen=True)
class CouplingConfig:
    """Frozen synthetic parameters in canonical SI units."""

    provenance_id: str = "synthetic-utility-cmp-coupling-v1"
    topology: UtilityCmpTopology = UtilityCmpTopology.NO_CONNECTION
    link_strength: float = 0.0
    reference_supply_pressure_pa: float = 300_000.0
    pressure_zero_fraction: float = 0.60
    pressure_full_fraction: float = 0.95
    reference_tool_flow_m3_s: float = 1.0e-4
    flow_zero_fraction: float = 0.50
    flow_full_fraction: float = 0.95
    reference_upw_temperature_k: float = 293.15

    def validate(self) -> None:
        if not isinstance(self.provenance_id, str) or not self.provenance_id.strip():
            raise CouplingModelError("provenance_id must be a non-empty string")
        try:
            topology = UtilityCmpTopology(self.topology)
        except (TypeError, ValueError) as exc:
            raise CouplingModelError("unsupported utility-to-CMP topology") from exc

        numeric = {
            field.name: getattr(self, field.name)
            for field in fields(self)
            if field.name not in {"provenance_id", "topology"}
        }
        for name, value in numeric.items():
            if isinstance(value, bool) or not isinstance(value, Real):
                raise CouplingModelError(f"{name} must be a real number")
            if not math.isfinite(float(value)):
                raise CouplingModelError(f"{name} must be finite")

        if not 0.0 <= self.link_strength <= 1.0:
            raise CouplingModelError("link_strength must be within [0, 1]")
        if topology is UtilityCmpTopology.NO_CONNECTION and self.link_strength != 0.0:
            raise CouplingModelError("NO_CONNECTION requires exactly zero link_strength")
        if self.reference_supply_pressure_pa <= 0.0:
            raise CouplingModelError("reference_supply_pressure_pa must be positive")
        if self.reference_tool_flow_m3_s <= 0.0:
            raise CouplingModelError("reference_tool_flow_m3_s must be positive")
        if not (
            0.0
            <= self.pressure_zero_fraction
            < self.pressure_full_fraction
            <= 1.0
        ):
            raise CouplingModelError(
                "pressure fractions must satisfy 0 <= zero < full <= 1"
            )
        if not (
            0.0 <= self.flow_zero_fraction < self.flow_full_fraction <= 1.0
        ):
            raise CouplingModelError(
                "flow fractions must satisfy 0 <= zero < full <= 1"
            )
        if self.reference_upw_temperature_k <= 0.0:
            raise CouplingModelError("reference_upw_temperature_k must be positive")


@dataclass(frozen=True)
class CouplingParameterMetadata:
    """Auditable value, bound, uncertainty, sign, and provenance record."""

    name: str
    nominal_value: float
    unit: str
    hard_lower_bound: float
    hard_upper_bound: float
    sensitivity_lower_bound: float
    sensitivity_upper_bound: float
    provenance_class: str
    expected_effect: str

    def validate(self) -> None:
        numeric = (
            self.nominal_value,
            self.hard_lower_bound,
            self.hard_upper_bound,
            self.sensitivity_lower_bound,
            self.sensitivity_upper_bound,
        )
        if any(not math.isfinite(value) for value in numeric):
            raise CouplingModelError(f"metadata for {self.name} must be finite")
        if not self.hard_lower_bound <= self.nominal_value <= self.hard_upper_bound:
            raise CouplingModelError(f"metadata nominal for {self.name} is outside hard bounds")
        if not (
            self.hard_lower_bound
            <= self.sensitivity_lower_bound
            <= self.nominal_value
            <= self.sensitivity_upper_bound
            <= self.hard_upper_bound
        ):
            raise CouplingModelError(
                f"metadata sensitivity range for {self.name} is invalid"
            )
        if self.provenance_class not in PROVENANCE_CLASSES:
            raise CouplingModelError(f"metadata provenance for {self.name} is invalid")
        if not self.unit or not self.expected_effect:
            raise CouplingModelError(f"metadata text for {self.name} must be non-empty")


@dataclass(frozen=True)
class CouplingResult:
    """One typed boundary plus finite diagnostic support states."""

    topology: UtilityCmpTopology
    pressure_ratio: float
    flow_ratio: float
    pressure_support: float
    flow_support: float
    hydraulic_support: float
    effective_availability: float
    boundary: CmpBoundaryConditions

    def validate(self, cmp_config: CmpConfig) -> None:
        try:
            UtilityCmpTopology(self.topology)
        except (TypeError, ValueError) as exc:
            raise CouplingModelError("coupling result has an invalid topology") from exc
        numeric = (
            self.pressure_ratio,
            self.flow_ratio,
            self.pressure_support,
            self.flow_support,
            self.hydraulic_support,
            self.effective_availability,
        )
        if any(not math.isfinite(value) for value in numeric):
            raise CouplingModelError("coupling diagnostics must be finite")
        if self.pressure_ratio < 0.0 or self.flow_ratio < 0.0:
            raise CouplingModelError("coupling pressure and flow ratios must be nonnegative")
        for value in numeric[2:]:
            if not 0.0 <= value <= 1.0:
                raise CouplingModelError("coupling support states must be within [0, 1]")
        self.boundary.validate(cmp_config)


class UtilityToCmpCoupler:
    """Pure utility-to-CMP boundary map for one declared topology."""

    def __init__(
        self,
        config: CouplingConfig | None = None,
        upw_config: UpwConfig | None = None,
        cmp_config: CmpConfig | None = None,
    ) -> None:
        self.config = config or CouplingConfig()
        self.upw_config = upw_config or UpwConfig()
        self.cmp_config = cmp_config or CmpConfig()
        self.config.validate()
        self.upw_config.validate()
        self.cmp_config.validate()
        if self.config.reference_supply_pressure_pa > self.upw_config.maximum_supply_pressure_pa:
            raise CouplingModelError(
                "reference supply pressure exceeds the UPW configured maximum"
            )
        if self.config.reference_tool_flow_m3_s > self.upw_config.maximum_flow_m3_s:
            raise CouplingModelError("reference tool flow exceeds the UPW configured maximum")
        if not (
            self.upw_config.minimum_temperature_k
            <= self.config.reference_upw_temperature_k
            <= self.upw_config.maximum_temperature_k
        ):
            raise CouplingModelError(
                "reference UPW temperature is outside the UPW configured envelope"
            )

    @staticmethod
    def normalized_ramp(value: float, zero: float, full: float) -> float:
        """Return the bounded linear support ramp R(value; zero, full)."""

        if any(
            isinstance(item, bool)
            or not isinstance(item, Real)
            or not math.isfinite(float(item))
            for item in (value, zero, full)
        ):
            raise CouplingModelError("ramp inputs must be finite real numbers")
        if not zero < full:
            raise CouplingModelError("ramp zero must be below ramp full")
        return min(1.0, max(0.0, (float(value) - float(zero)) / (float(full) - float(zero))))

    @classmethod
    def parameter_provenance_classes(cls) -> dict[str, str]:
        """Classify every numerical coupling coefficient."""

        return {
            field.name: "Synthetic assumption"
            for field in fields(CouplingConfig)
            if field.name not in {"provenance_id", "topology"}
        }

    @staticmethod
    def functional_form_provenance_classes() -> dict[str, str]:
        """Classify non-parameter structural choices separately."""

        return {
            "bounded_linear_support_ramp": "Engineering approximation",
            "pressure_flow_bottleneck_minimum": "Engineering approximation",
            "zero_link_affine_blend": "Engineering approximation",
            "temperature_deviation_map": "Engineering approximation",
            "conditioning_and_thermal_pathway_existence": "Literature-supported",
            "synthetic_slurry_support_pathway": "Synthetic assumption",
        }

    def parameter_metadata(self) -> tuple[CouplingParameterMetadata, ...]:
        """Return the complete current value/bounds/uncertainty registry."""

        c = self.config
        eps = 1.0e-12
        pressure_zero_upper = min(c.pressure_full_fraction - eps, c.pressure_zero_fraction + 0.15)
        pressure_full_lower = max(c.pressure_zero_fraction + eps, c.pressure_full_fraction - 0.10)
        flow_zero_upper = min(c.flow_full_fraction - eps, c.flow_zero_fraction + 0.20)
        flow_full_lower = max(c.flow_zero_fraction + eps, c.flow_full_fraction - 0.10)
        records = (
            CouplingParameterMetadata(
                "link_strength", c.link_strength, "1", 0.0, 1.0, 0.0, max(c.link_strength, 1.0),
                "Synthetic assumption",
                "larger values increase connected-topology response when hydraulic support is below one",
            ),
            CouplingParameterMetadata(
                "reference_supply_pressure_pa",
                c.reference_supply_pressure_pa,
                "Pa",
                eps,
                self.upw_config.maximum_supply_pressure_pa,
                max(eps, min(c.reference_supply_pressure_pa, 250_000.0)),
                min(self.upw_config.maximum_supply_pressure_pa, max(c.reference_supply_pressure_pa, 350_000.0)),
                "Synthetic assumption",
                "larger reference pressure generally lowers normalized pressure support at fixed supply pressure",
            ),
            CouplingParameterMetadata(
                "pressure_zero_fraction",
                c.pressure_zero_fraction,
                "1",
                0.0,
                c.pressure_full_fraction - eps,
                max(0.0, min(c.pressure_zero_fraction, 0.40)),
                pressure_zero_upper,
                "Synthetic assumption",
                "larger values generally reduce pressure support inside the transition interval",
            ),
            CouplingParameterMetadata(
                "pressure_full_fraction",
                c.pressure_full_fraction,
                "1",
                c.pressure_zero_fraction + eps,
                1.0,
                pressure_full_lower,
                min(1.0, max(c.pressure_full_fraction, 1.0)),
                "Synthetic assumption",
                "larger values generally reduce pressure support inside the transition interval",
            ),
            CouplingParameterMetadata(
                "reference_tool_flow_m3_s",
                c.reference_tool_flow_m3_s,
                "m^3/s",
                eps,
                self.upw_config.maximum_flow_m3_s,
                max(eps, min(c.reference_tool_flow_m3_s, 8.0e-5)),
                min(self.upw_config.maximum_flow_m3_s, max(c.reference_tool_flow_m3_s, 1.2e-4)),
                "Synthetic assumption",
                "larger reference flow generally lowers normalized flow support at fixed tool flow",
            ),
            CouplingParameterMetadata(
                "flow_zero_fraction",
                c.flow_zero_fraction,
                "1",
                0.0,
                c.flow_full_fraction - eps,
                max(0.0, min(c.flow_zero_fraction, 0.30)),
                flow_zero_upper,
                "Synthetic assumption",
                "larger values generally reduce flow support inside the transition interval",
            ),
            CouplingParameterMetadata(
                "flow_full_fraction",
                c.flow_full_fraction,
                "1",
                c.flow_zero_fraction + eps,
                1.0,
                flow_full_lower,
                min(1.0, max(c.flow_full_fraction, 1.0)),
                "Synthetic assumption",
                "larger values generally reduce flow support inside the transition interval",
            ),
            CouplingParameterMetadata(
                "reference_upw_temperature_k",
                c.reference_upw_temperature_k,
                "K",
                self.upw_config.minimum_temperature_k,
                self.upw_config.maximum_temperature_k,
                max(self.upw_config.minimum_temperature_k, c.reference_upw_temperature_k - 5.0),
                min(self.upw_config.maximum_temperature_k, c.reference_upw_temperature_k + 5.0),
                "Synthetic assumption",
                "sets the zero of the mapped UPW temperature deviation without changing the CMP neutral reference",
            ),
        )
        for record in records:
            record.validate()
        return records

    def couple(self, upw_state: UpwState) -> CouplingResult:
        """Map one validated latent UPW state to a typed CMP boundary."""

        upw_state.validate(self.upw_config)
        pressure_ratio = (
            upw_state.supply_pressure_pa / self.config.reference_supply_pressure_pa
        )
        flow_ratio = upw_state.tool_flow_m3_s / self.config.reference_tool_flow_m3_s
        pressure_support = self.normalized_ramp(
            pressure_ratio,
            self.config.pressure_zero_fraction,
            self.config.pressure_full_fraction,
        )
        flow_support = self.normalized_ramp(
            flow_ratio,
            self.config.flow_zero_fraction,
            self.config.flow_full_fraction,
        )
        hydraulic_support = min(pressure_support, flow_support)
        effective_availability = 1.0 - self.config.link_strength * (
            1.0 - hydraulic_support
        )
        topology = UtilityCmpTopology(self.config.topology)

        boundary_values: dict[str, float | bool] = {}
        if topology is UtilityCmpTopology.DRESSING_WATER_SUPPORT:
            boundary_values["dressing_availability"] = effective_availability
        elif topology is UtilityCmpTopology.THERMAL_LOOP:
            boundary_values["coolant_temperature_k"] = (
                self.cmp_config.interface_reference_temperature_k
                + self.config.link_strength
                * (upw_state.temperature_k - self.config.reference_upw_temperature_k)
            )
            boundary_values["cooling_conductance_factor"] = effective_availability
        elif topology is UtilityCmpTopology.SYNTHETIC_SLURRY_SUPPORT:
            boundary_values["slurry_utility_availability"] = effective_availability

        try:
            boundary = CmpBoundaryConditions.from_mapping(boundary_values, self.cmp_config)
        except CmpModelError as exc:
            raise CouplingModelError(f"coupling produced an invalid CMP boundary: {exc}") from exc
        result = CouplingResult(
            topology=topology,
            pressure_ratio=pressure_ratio,
            flow_ratio=flow_ratio,
            pressure_support=pressure_support,
            flow_support=flow_support,
            hydraulic_support=hydraulic_support,
            effective_availability=effective_availability,
            boundary=boundary,
        )
        result.validate(self.cmp_config)
        return result

    @staticmethod
    def latent_signal_values(result: CouplingResult) -> dict[str, float | str]:
        """Return canonical latent coupling diagnostics."""

        return {
            "coupling.topology": result.topology.value,
            "coupling.pressure_ratio": result.pressure_ratio,
            "coupling.flow_ratio": result.flow_ratio,
            "coupling.pressure_support": result.pressure_support,
            "coupling.flow_support": result.flow_support,
            "coupling.hydraulic_support": result.hydraulic_support,
            "coupling.effective_availability": result.effective_availability,
            "coupling.dressing_availability": result.boundary.dressing_availability,
            "coupling.slurry_utility_availability": result.boundary.slurry_utility_availability,
            "coupling.coolant_temperature": result.boundary.coolant_temperature_k,
            "coupling.cooling_conductance_factor": result.boundary.cooling_conductance_factor,
        }
