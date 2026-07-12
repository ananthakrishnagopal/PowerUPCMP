"""Reduced-order, fully synthetic CMP process physics.

The subsystem separates process mode, actuator state, rotary kinematics,
consumable health, interface temperature, and cumulative removal.  Its values
are simulated physical states; annular exposure is only a labelled spatial
uniformity proxy and is not experimentally validated WIWNU.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, fields
from enum import Enum
from numbers import Real
from typing import Any, Mapping

import numpy as np

from .base import DynamicSubsystem


SPATIAL_PROXY_LABEL = (
    "Simulated spatial-uniformity proxy; not experimentally validated WIWNU."
)


class CmpModelError(ValueError):
    """Raised when CMP configuration, state, action, or boundary is invalid."""


class CmpMode(str, Enum):
    IDLE = "IDLE"
    PREPARE = "PREPARE"
    POLISH = "POLISH"
    DRESS = "DRESS"
    HOLD = "HOLD"
    RECOVER = "RECOVER"
    COMPLETE = "COMPLETE"


class CmpHoldReason(str, Enum):
    NONE = "NONE"
    REQUESTED = "REQUESTED"
    FORCED_BOUNDARY = "FORCED_BOUNDARY"


@dataclass(frozen=True)
class CmpConfig:
    """Frozen synthetic parameters in canonical SI units."""

    provenance_id: str = "synthetic-cmp-reduced-order-v1"
    kinematics_model: str = "ROTARY_OFFSET_AREA_QUADRATURE"
    wafer_radius_m: float = 0.15
    center_offset_m: float = 0.20
    radial_quadrature_order: int = 16
    angular_quadrature_order: int = 64
    nominal_contact_pressure_pa: float = 30_000.0
    maximum_contact_pressure_pa: float = 60_000.0
    pressure_time_constant_s: float = 0.20
    pressure_ramp_up_pa_s: float = 100_000.0
    pressure_ramp_down_pa_s: float = 200_000.0
    nominal_platen_angular_speed_rad_s: float = 8.0
    nominal_head_angular_speed_rad_s: float = 6.0
    maximum_abs_platen_angular_speed_rad_s: float = 15.0
    maximum_abs_head_angular_speed_rad_s: float = 15.0
    spindle_time_constant_s: float = 0.15
    spindle_slew_rate_rad_s2: float = 40.0
    reference_slurry_flow_m3_s: float = 1.0e-5
    slurry_time_constant_s: float = 0.40
    reference_mrr_m_s: float = 1.6666666666667e-9
    maximum_mrr_m_s: float = 5.0e-9
    pressure_exponent: float = 1.0
    velocity_exponent: float = 1.0
    nominal_recipe_modifier: float = 1.0
    minimum_recipe_modifier: float = 0.5
    maximum_recipe_modifier: float = 1.5
    minimum_pad_modifier: float = 0.25
    pad_life_exponent: float = 1.0
    pad_glazing_rate_s_inv: float = 2.0e-4
    pad_conditioning_rate_s_inv: float = 2.0e-2
    pad_wear_polish_rate_s_inv: float = 1.0e-5
    pad_wear_dress_rate_s_inv: float = 5.0e-5
    dresser_wear_rate_s_inv: float = 2.0e-5
    interface_reference_temperature_k: float = 293.15
    minimum_interface_temperature_k: float = 273.15
    maximum_interface_temperature_k: float = 353.15
    interface_thermal_capacity_j_k: float = 5_000.0
    friction_heat_fraction: float = 0.80
    friction_coefficient: float = 0.05
    nominal_cooling_conductance_w_k: float = 200.0
    maximum_cooling_conductance_factor: float = 2.0
    slurry_density_kg_m3: float = 1_000.0
    slurry_specific_heat_j_kg_k: float = 4_000.0
    slurry_supply_temperature_k: float = 293.15
    temperature_sensitivity_k_inv: float = 0.0
    minimum_temperature_modifier: float = 0.5
    maximum_temperature_modifier: float = 1.5
    maximum_abs_process_discrepancy_m_s: float = 1.0e-9
    minimum_recovery_dwell_s: float = 0.5

    def validate(self) -> None:
        if not isinstance(self.provenance_id, str) or not self.provenance_id.strip():
            raise CmpModelError("provenance_id must be a non-empty string")
        if self.kinematics_model != "ROTARY_OFFSET_AREA_QUADRATURE":
            raise CmpModelError("unsupported CMP kinematics_model")
        if (
            not isinstance(self.radial_quadrature_order, int)
            or isinstance(self.radial_quadrature_order, bool)
            or self.radial_quadrature_order < 4
        ):
            raise CmpModelError("radial_quadrature_order must be an integer at least 4")
        if (
            not isinstance(self.angular_quadrature_order, int)
            or isinstance(self.angular_quadrature_order, bool)
            or self.angular_quadrature_order < 8
        ):
            raise CmpModelError("angular_quadrature_order must be an integer at least 8")

        positive = {
            "wafer_radius_m": self.wafer_radius_m,
            "center_offset_m": self.center_offset_m,
            "nominal_contact_pressure_pa": self.nominal_contact_pressure_pa,
            "maximum_contact_pressure_pa": self.maximum_contact_pressure_pa,
            "pressure_time_constant_s": self.pressure_time_constant_s,
            "pressure_ramp_up_pa_s": self.pressure_ramp_up_pa_s,
            "pressure_ramp_down_pa_s": self.pressure_ramp_down_pa_s,
            "maximum_abs_platen_angular_speed_rad_s": (
                self.maximum_abs_platen_angular_speed_rad_s
            ),
            "maximum_abs_head_angular_speed_rad_s": (
                self.maximum_abs_head_angular_speed_rad_s
            ),
            "spindle_time_constant_s": self.spindle_time_constant_s,
            "spindle_slew_rate_rad_s2": self.spindle_slew_rate_rad_s2,
            "reference_slurry_flow_m3_s": self.reference_slurry_flow_m3_s,
            "slurry_time_constant_s": self.slurry_time_constant_s,
            "reference_mrr_m_s": self.reference_mrr_m_s,
            "maximum_mrr_m_s": self.maximum_mrr_m_s,
            "pressure_exponent": self.pressure_exponent,
            "velocity_exponent": self.velocity_exponent,
            "nominal_recipe_modifier": self.nominal_recipe_modifier,
            "minimum_recipe_modifier": self.minimum_recipe_modifier,
            "maximum_recipe_modifier": self.maximum_recipe_modifier,
            "pad_life_exponent": self.pad_life_exponent,
            "interface_thermal_capacity_j_k": self.interface_thermal_capacity_j_k,
            "nominal_cooling_conductance_w_k": self.nominal_cooling_conductance_w_k,
            "maximum_cooling_conductance_factor": (
                self.maximum_cooling_conductance_factor
            ),
            "slurry_density_kg_m3": self.slurry_density_kg_m3,
            "slurry_specific_heat_j_kg_k": self.slurry_specific_heat_j_kg_k,
            "minimum_temperature_modifier": self.minimum_temperature_modifier,
            "maximum_temperature_modifier": self.maximum_temperature_modifier,
            "minimum_recovery_dwell_s": self.minimum_recovery_dwell_s,
        }
        for name, value in positive.items():
            if not math.isfinite(value) or value <= 0.0:
                raise CmpModelError(f"{name} must be finite and positive")

        finite = {
            "nominal_platen_angular_speed_rad_s": (
                self.nominal_platen_angular_speed_rad_s
            ),
            "nominal_head_angular_speed_rad_s": self.nominal_head_angular_speed_rad_s,
            "minimum_pad_modifier": self.minimum_pad_modifier,
            "pad_glazing_rate_s_inv": self.pad_glazing_rate_s_inv,
            "pad_conditioning_rate_s_inv": self.pad_conditioning_rate_s_inv,
            "pad_wear_polish_rate_s_inv": self.pad_wear_polish_rate_s_inv,
            "pad_wear_dress_rate_s_inv": self.pad_wear_dress_rate_s_inv,
            "dresser_wear_rate_s_inv": self.dresser_wear_rate_s_inv,
            "interface_reference_temperature_k": (
                self.interface_reference_temperature_k
            ),
            "minimum_interface_temperature_k": self.minimum_interface_temperature_k,
            "maximum_interface_temperature_k": self.maximum_interface_temperature_k,
            "friction_heat_fraction": self.friction_heat_fraction,
            "friction_coefficient": self.friction_coefficient,
            "slurry_supply_temperature_k": self.slurry_supply_temperature_k,
            "temperature_sensitivity_k_inv": self.temperature_sensitivity_k_inv,
            "maximum_abs_process_discrepancy_m_s": (
                self.maximum_abs_process_discrepancy_m_s
            ),
        }
        for name, value in finite.items():
            if not math.isfinite(value):
                raise CmpModelError(f"{name} must be finite")

        nonnegative = {
            "pad_glazing_rate_s_inv": self.pad_glazing_rate_s_inv,
            "pad_conditioning_rate_s_inv": self.pad_conditioning_rate_s_inv,
            "pad_wear_polish_rate_s_inv": self.pad_wear_polish_rate_s_inv,
            "pad_wear_dress_rate_s_inv": self.pad_wear_dress_rate_s_inv,
            "dresser_wear_rate_s_inv": self.dresser_wear_rate_s_inv,
            "friction_coefficient": self.friction_coefficient,
            "maximum_abs_process_discrepancy_m_s": (
                self.maximum_abs_process_discrepancy_m_s
            ),
        }
        if any(value < 0.0 for value in nonnegative.values()):
            raise CmpModelError("CMP wear, friction, and discrepancy bounds must be nonnegative")
        if self.nominal_contact_pressure_pa > self.maximum_contact_pressure_pa:
            raise CmpModelError("nominal contact pressure exceeds maximum")
        if abs(self.nominal_platen_angular_speed_rad_s) > (
            self.maximum_abs_platen_angular_speed_rad_s
        ):
            raise CmpModelError("nominal platen speed exceeds its magnitude bound")
        if abs(self.nominal_head_angular_speed_rad_s) > (
            self.maximum_abs_head_angular_speed_rad_s
        ):
            raise CmpModelError("nominal head speed exceeds its magnitude bound")
        if self.maximum_mrr_m_s < self.reference_mrr_m_s:
            raise CmpModelError("maximum MRR must not be below reference MRR")
        if not 0.0 < self.pressure_exponent <= 3.0:
            raise CmpModelError("pressure_exponent must be in (0, 3]")
        if not 0.0 < self.velocity_exponent <= 3.0:
            raise CmpModelError("velocity_exponent must be in (0, 3]")
        if not (
            self.minimum_recipe_modifier
            <= self.nominal_recipe_modifier
            <= self.maximum_recipe_modifier
        ):
            raise CmpModelError("nominal recipe modifier is outside its bounds")
        if not 0.0 <= self.minimum_pad_modifier <= 1.0:
            raise CmpModelError("minimum_pad_modifier must be within [0, 1]")
        if not (
            0.0
            < self.minimum_interface_temperature_k
            <= self.interface_reference_temperature_k
            <= self.maximum_interface_temperature_k
        ):
            raise CmpModelError("interface reference temperature is outside its bounds")
        if not (
            self.minimum_interface_temperature_k
            <= self.slurry_supply_temperature_k
            <= self.maximum_interface_temperature_k
        ):
            raise CmpModelError("slurry supply temperature is outside interface bounds")
        if not 0.0 <= self.friction_heat_fraction <= 1.0:
            raise CmpModelError("friction_heat_fraction must be within [0, 1]")
        if abs(self.temperature_sensitivity_k_inv) > 0.1:
            raise CmpModelError("temperature sensitivity magnitude exceeds 0.1 1/K")
        if not (
            self.minimum_temperature_modifier
            <= 1.0
            <= self.maximum_temperature_modifier
        ):
            raise CmpModelError("temperature modifier bounds must contain one")
        if self.maximum_cooling_conductance_factor < 1.0:
            raise CmpModelError("maximum cooling factor must be at least one")

    @property
    def contact_area_m2(self) -> float:
        return math.pi * self.wafer_radius_m**2

    @property
    def minimum_thermal_time_constant_s(self) -> float:
        maximum_conductance = (
            self.nominal_cooling_conductance_w_k
            * self.maximum_cooling_conductance_factor
            + self.slurry_density_kg_m3
            * self.slurry_specific_heat_j_kg_k
            * self.reference_slurry_flow_m3_s
        )
        return self.interface_thermal_capacity_j_k / maximum_conductance

    @property
    def maximum_timestep_s(self) -> float:
        return min(
            self.pressure_time_constant_s,
            self.spindle_time_constant_s,
            self.slurry_time_constant_s,
            self.minimum_thermal_time_constant_s,
        )


@dataclass(frozen=True)
class CmpBoundaryConditions:
    """Typed neutral-by-default boundary owned by the future WP10 coupler."""

    dressing_availability: float = 1.0
    slurry_utility_availability: float = 1.0
    coolant_temperature_k: float = 293.15
    cooling_conductance_factor: float = 1.0
    process_discrepancy_m_s: float = 0.0
    utilities_valid: bool = True
    sensors_valid: bool = True
    force_hold: bool = False

    @classmethod
    def from_mapping(
        cls,
        values: Mapping[str, Any] | None,
        config: CmpConfig,
    ) -> CmpBoundaryConditions:
        raw = dict(values or {})
        raw.setdefault(
            "coolant_temperature_k",
            config.interface_reference_temperature_k,
        )
        allowed = {field.name for field in fields(cls)}
        unknown = set(raw) - allowed
        if unknown:
            raise CmpModelError(f"unknown CMP boundary keys: {sorted(unknown)}")
        for name in ("utilities_valid", "sensors_valid", "force_hold"):
            if name in raw and type(raw[name]) is not bool:
                raise CmpModelError(f"{name} must be boolean")
        for name in allowed - {"utilities_valid", "sensors_valid", "force_hold"}:
            if name not in raw:
                continue
            value = raw[name]
            if isinstance(value, bool) or not isinstance(value, Real):
                raise CmpModelError(f"{name} must be a real number")
            raw[name] = float(value)
        boundary = cls(**raw)
        boundary.validate(config)
        return boundary

    def validate(self, config: CmpConfig) -> None:
        numeric = (
            self.dressing_availability,
            self.slurry_utility_availability,
            self.coolant_temperature_k,
            self.cooling_conductance_factor,
            self.process_discrepancy_m_s,
        )
        if any(not math.isfinite(value) for value in numeric):
            raise CmpModelError("CMP boundary values must be finite")
        if not 0.0 <= self.dressing_availability <= 1.0:
            raise CmpModelError("dressing availability must be within [0, 1]")
        if not 0.0 <= self.slurry_utility_availability <= 1.0:
            raise CmpModelError("slurry utility availability must be within [0, 1]")
        if not (
            config.minimum_interface_temperature_k
            <= self.coolant_temperature_k
            <= config.maximum_interface_temperature_k
        ):
            raise CmpModelError("coolant temperature is outside the CMP envelope")
        if not (
            0.0
            <= self.cooling_conductance_factor
            <= config.maximum_cooling_conductance_factor
        ):
            raise CmpModelError("cooling conductance factor is outside its bounds")
        if abs(self.process_discrepancy_m_s) > (
            config.maximum_abs_process_discrepancy_m_s
        ):
            raise CmpModelError("process discrepancy is outside its magnitude bound")
        if any(
            type(value) is not bool
            for value in (self.utilities_valid, self.sensors_valid, self.force_hold)
        ):
            raise CmpModelError("CMP validity and force-hold flags must be boolean")

    def as_mapping(self) -> dict[str, float | bool]:
        return {
            "dressing_availability": self.dressing_availability,
            "slurry_utility_availability": self.slurry_utility_availability,
            "coolant_temperature_k": self.coolant_temperature_k,
            "cooling_conductance_factor": self.cooling_conductance_factor,
            "process_discrepancy_m_s": self.process_discrepancy_m_s,
            "utilities_valid": self.utilities_valid,
            "sensors_valid": self.sensors_valid,
            "force_hold": self.force_hold,
        }


@dataclass(frozen=True)
class CmpState:
    mode: CmpMode
    mode_elapsed_s: float
    hold_reason: CmpHoldReason
    recovery_valid_dwell_s: float
    transition_count: int
    contact_pressure_command_pa: float
    contact_pressure_pa: float
    platen_speed_command_rad_s: float
    platen_angular_speed_rad_s: float
    head_speed_command_rad_s: float
    head_angular_speed_rad_s: float
    slurry_flow_command_m3_s: float
    slurry_availability: float
    slurry_flow_m3_s: float
    dresser_command: float
    realized_dressing_activity: float
    recipe_modifier: float
    relative_velocity_m_s: float
    pressure_velocity_exposure: float
    interface_temperature_k: float
    pad_surface_activity: float
    pad_remaining_life: float
    dresser_effectiveness: float
    friction_heat_w: float
    cooling_heat_w: float
    slurry_heat_w: float
    thermal_energy_residual_w: float
    instantaneous_mrr_physics_m_s: float
    process_discrepancy_m_s: float
    instantaneous_mrr_m_s: float
    cumulative_removal_m: float
    active_polish_time_s: float
    stage_average_mrr_m_s: float

    def validate(self, config: CmpConfig) -> None:
        if not isinstance(self.mode, CmpMode):
            raise CmpModelError("CMP mode must be a CmpMode")
        if not isinstance(self.hold_reason, CmpHoldReason):
            raise CmpModelError("CMP hold reason must be a CmpHoldReason")
        if self.mode is CmpMode.HOLD and self.hold_reason is CmpHoldReason.NONE:
            raise CmpModelError("HOLD mode requires an explicit hold reason")
        if self.mode is not CmpMode.HOLD and self.hold_reason is not CmpHoldReason.NONE:
            raise CmpModelError("hold reason must be NONE outside HOLD mode")
        if (
            not isinstance(self.transition_count, int)
            or isinstance(self.transition_count, bool)
            or self.transition_count < 0
        ):
            raise CmpModelError("transition_count must be a nonnegative integer")

        numeric_values = {
            field.name: getattr(self, field.name)
            for field in fields(self)
            if field.name not in {"mode", "hold_reason", "transition_count"}
        }
        if any(
            isinstance(value, bool)
            or not isinstance(value, Real)
            or not math.isfinite(float(value))
            for value in numeric_values.values()
        ):
            raise CmpModelError("all numeric CMP state values must be finite real numbers")
        for name in (
            "mode_elapsed_s",
            "recovery_valid_dwell_s",
            "relative_velocity_m_s",
            "pressure_velocity_exposure",
            "friction_heat_w",
            "instantaneous_mrr_physics_m_s",
            "instantaneous_mrr_m_s",
            "cumulative_removal_m",
            "active_polish_time_s",
            "stage_average_mrr_m_s",
        ):
            if numeric_values[name] < 0.0:
                raise CmpModelError(f"{name} must be nonnegative")
        if not (
            0.0
            <= self.contact_pressure_command_pa
            <= config.maximum_contact_pressure_pa
        ):
            raise CmpModelError("contact pressure command is outside its bounds")
        if not 0.0 <= self.contact_pressure_pa <= config.maximum_contact_pressure_pa:
            raise CmpModelError("contact pressure is outside its bounds")
        if abs(self.platen_speed_command_rad_s) > (
            config.maximum_abs_platen_angular_speed_rad_s
        ) or abs(self.platen_angular_speed_rad_s) > (
            config.maximum_abs_platen_angular_speed_rad_s
        ):
            raise CmpModelError("platen speed or command exceeds its magnitude bound")
        if abs(self.head_speed_command_rad_s) > (
            config.maximum_abs_head_angular_speed_rad_s
        ) or abs(self.head_angular_speed_rad_s) > (
            config.maximum_abs_head_angular_speed_rad_s
        ):
            raise CmpModelError("head speed or command exceeds its magnitude bound")
        if not 0.0 <= self.slurry_flow_command_m3_s <= config.reference_slurry_flow_m3_s:
            raise CmpModelError("slurry flow command is outside its bounds")
        if not 0.0 <= self.slurry_flow_m3_s <= config.reference_slurry_flow_m3_s:
            raise CmpModelError("realized slurry flow is outside its bounds")
        for name in (
            "slurry_availability",
            "dresser_command",
            "realized_dressing_activity",
            "pad_surface_activity",
            "pad_remaining_life",
            "dresser_effectiveness",
        ):
            if not 0.0 <= numeric_values[name] <= 1.0:
                raise CmpModelError(f"{name} must be within [0, 1]")
        if not (
            config.minimum_recipe_modifier
            <= self.recipe_modifier
            <= config.maximum_recipe_modifier
        ):
            raise CmpModelError("recipe modifier is outside its bounds")
        if not (
            config.minimum_interface_temperature_k
            <= self.interface_temperature_k
            <= config.maximum_interface_temperature_k
        ):
            raise CmpModelError("interface temperature is outside its bounds")
        if abs(self.process_discrepancy_m_s) > config.maximum_abs_process_discrepancy_m_s:
            raise CmpModelError("process discrepancy is outside its magnitude bound")
        if self.instantaneous_mrr_m_s > config.maximum_mrr_m_s:
            raise CmpModelError("instantaneous MRR exceeds its configured bound")
        if self.stage_average_mrr_m_s > config.maximum_mrr_m_s + 1.0e-18:
            raise CmpModelError("stage-average MRR exceeds its configured bound")
        if self.mode is not CmpMode.POLISH and (
            self.instantaneous_mrr_m_s > 1.0e-18
            or self.instantaneous_mrr_physics_m_s > 1.0e-18
        ):
            raise CmpModelError("material removal must be zero outside POLISH mode")
        if self.active_polish_time_s == 0.0 and self.cumulative_removal_m > 1.0e-18:
            raise CmpModelError("cumulative removal requires positive active polish time")


@dataclass(frozen=True)
class SpatialUniformityProxy:
    radial_positions_m: tuple[float, ...]
    normalized_exposure: tuple[float, ...]
    coefficient_of_variation: float
    label: str = SPATIAL_PROXY_LABEL


class CmpSubsystem(DynamicSubsystem[CmpState, CmpConfig]):
    """Deterministic reduced-order CMP process model."""

    _ALLOWED_ACTION_KEYS = frozenset(
        {
            "mode_request",
            "contact_pressure_command_pa",
            "platen_speed_command_rad_s",
            "head_speed_command_rad_s",
            "slurry_flow_command_m3_s",
            "dresser_command",
            "recipe_modifier",
        }
    )
    _ALLOWED_TRANSITIONS = {
        CmpMode.IDLE: frozenset({CmpMode.IDLE, CmpMode.PREPARE, CmpMode.HOLD}),
        CmpMode.PREPARE: frozenset(
            {CmpMode.PREPARE, CmpMode.POLISH, CmpMode.DRESS, CmpMode.HOLD, CmpMode.COMPLETE}
        ),
        CmpMode.POLISH: frozenset(
            {CmpMode.POLISH, CmpMode.DRESS, CmpMode.HOLD, CmpMode.COMPLETE}
        ),
        CmpMode.DRESS: frozenset(
            {CmpMode.DRESS, CmpMode.PREPARE, CmpMode.HOLD, CmpMode.COMPLETE}
        ),
        CmpMode.HOLD: frozenset({CmpMode.HOLD, CmpMode.RECOVER, CmpMode.COMPLETE}),
        CmpMode.RECOVER: frozenset(
            {CmpMode.RECOVER, CmpMode.PREPARE, CmpMode.POLISH, CmpMode.HOLD, CmpMode.COMPLETE}
        ),
        CmpMode.COMPLETE: frozenset({CmpMode.COMPLETE}),
    }

    def __init__(self, config: CmpConfig | None = None) -> None:
        self.config = config or CmpConfig()
        self.config.validate()
        nodes, weights = np.polynomial.legendre.leggauss(
            self.config.radial_quadrature_order
        )
        radius = self.config.wafer_radius_m
        self._radial_positions_m = 0.5 * radius * (nodes + 1.0)
        self._radial_weights_m = 0.5 * radius * weights
        self._angles_rad = (
            2.0
            * math.pi
            * (np.arange(self.config.angular_quadrature_order, dtype=float) + 0.5)
            / self.config.angular_quadrature_order
        )
        angular_weight = 2.0 * math.pi / self.config.angular_quadrature_order
        self._area_weights = (
            self._radial_weights_m[:, None]
            * self._radial_positions_m[:, None]
            * angular_weight
            / self.config.contact_area_m2
        )
        self._radial_area_weights = (
            2.0
            * self._radial_weights_m
            * self._radial_positions_m
            / self.config.wafer_radius_m**2
        )
        nominal_velocity = self.relative_velocity_field(
            self.config.nominal_platen_angular_speed_rad_s,
            self.config.nominal_head_angular_speed_rad_s,
        )
        power_mean = self._area_average(
            nominal_velocity**self.config.velocity_exponent
        )
        if not math.isfinite(power_mean) or power_mean <= 0.0:
            raise CmpModelError("nominal kinematics must yield positive relative velocity")
        self._reference_velocity_scale_m_s = (
            power_mean ** (1.0 / self.config.velocity_exponent)
        )
        if abs(self.constant_field_quadrature - 1.0) > 1.0e-12:
            raise CmpModelError("CMP area quadrature does not integrate a constant")

    @property
    def constant_field_quadrature(self) -> float:
        ones = np.ones(
            (
                self.config.radial_quadrature_order,
                self.config.angular_quadrature_order,
            )
        )
        return self._area_average(ones)

    @property
    def reference_velocity_scale_m_s(self) -> float:
        return self._reference_velocity_scale_m_s

    @property
    def classical_preston_coefficient_pa_inv(self) -> float:
        if not (
            math.isclose(self.config.pressure_exponent, 1.0)
            and math.isclose(self.config.velocity_exponent, 1.0)
        ):
            raise CmpModelError("a Pa^-1 Preston coefficient is defined only for alpha=beta=1")
        return self.config.reference_mrr_m_s / (
            self.config.nominal_contact_pressure_pa
            * self.reference_velocity_scale_m_s
        )

    def _area_average(self, values: np.ndarray) -> float:
        return float(np.sum(self._area_weights * values))

    def relative_velocity_field(
        self,
        platen_angular_speed_rad_s: float,
        head_angular_speed_rad_s: float,
    ) -> np.ndarray:
        for name, value in {
            "platen_angular_speed_rad_s": platen_angular_speed_rad_s,
            "head_angular_speed_rad_s": head_angular_speed_rad_s,
        }.items():
            if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value):
                raise CmpModelError(f"{name} must be a finite real number")
        if abs(platen_angular_speed_rad_s) > (
            self.config.maximum_abs_platen_angular_speed_rad_s
        ):
            raise CmpModelError("platen angular speed exceeds its magnitude bound")
        if abs(head_angular_speed_rad_s) > self.config.maximum_abs_head_angular_speed_rad_s:
            raise CmpModelError("head angular speed exceeds its magnitude bound")
        radius = self._radial_positions_m[:, None]
        cosine = np.cos(self._angles_rad[None, :])
        delta = platen_angular_speed_rad_s - head_angular_speed_rad_s
        offset = self.config.center_offset_m
        radicand = (
            platen_angular_speed_rad_s**2 * offset**2
            + delta**2 * radius**2
            + 2.0
            * platen_angular_speed_rad_s
            * delta
            * offset
            * radius
            * cosine
        )
        return np.sqrt(np.maximum(radicand, 0.0))

    def area_mean_relative_velocity(
        self,
        platen_angular_speed_rad_s: float,
        head_angular_speed_rad_s: float,
    ) -> float:
        return self._area_average(
            self.relative_velocity_field(
                platen_angular_speed_rad_s,
                head_angular_speed_rad_s,
            )
        )

    def pressure_velocity_exposure(
        self,
        contact_pressure_pa: float,
        platen_angular_speed_rad_s: float,
        head_angular_speed_rad_s: float,
    ) -> float:
        if (
            isinstance(contact_pressure_pa, bool)
            or not isinstance(contact_pressure_pa, Real)
            or not math.isfinite(contact_pressure_pa)
            or not 0.0 <= contact_pressure_pa <= self.config.maximum_contact_pressure_pa
        ):
            raise CmpModelError("contact pressure is outside its finite bounds")
        velocity = self.relative_velocity_field(
            platen_angular_speed_rad_s,
            head_angular_speed_rad_s,
        )
        pressure_factor = (
            contact_pressure_pa / self.config.nominal_contact_pressure_pa
        ) ** self.config.pressure_exponent
        velocity_factor = self._area_average(
            (velocity / self.reference_velocity_scale_m_s)
            ** self.config.velocity_exponent
        )
        return pressure_factor * velocity_factor

    def spatial_uniformity_proxy(self, state: CmpState) -> SpatialUniformityProxy:
        state.validate(self.config)
        velocity = self.relative_velocity_field(
            state.platen_angular_speed_rad_s,
            state.head_angular_speed_rad_s,
        )
        pressure_factor = (
            state.contact_pressure_pa / self.config.nominal_contact_pressure_pa
        ) ** self.config.pressure_exponent
        local_exposure = pressure_factor * (
            velocity / self.reference_velocity_scale_m_s
        ) ** self.config.velocity_exponent
        annular = np.mean(local_exposure, axis=1)
        mean_exposure = float(np.sum(self._radial_area_weights * annular))
        if mean_exposure > 0.0:
            normalized = annular / mean_exposure
            coefficient = math.sqrt(
                float(
                    np.sum(
                        self._radial_area_weights
                        * (normalized - 1.0) ** 2
                    )
                )
            )
        else:
            normalized = np.zeros_like(annular)
            coefficient = 0.0
        return SpatialUniformityProxy(
            radial_positions_m=tuple(float(value) for value in self._radial_positions_m),
            normalized_exposure=tuple(float(value) for value in normalized),
            coefficient_of_variation=coefficient,
        )

    def reset(self, initial_state: CmpState | None = None) -> CmpState:
        if initial_state is not None:
            if not isinstance(initial_state, CmpState):
                raise CmpModelError("initial_state must be a CmpState or None")
            initial_state.validate(self.config)
            return initial_state
        state = CmpState(
            mode=CmpMode.IDLE,
            mode_elapsed_s=0.0,
            hold_reason=CmpHoldReason.NONE,
            recovery_valid_dwell_s=0.0,
            transition_count=0,
            contact_pressure_command_pa=self.config.nominal_contact_pressure_pa,
            contact_pressure_pa=0.0,
            platen_speed_command_rad_s=(
                self.config.nominal_platen_angular_speed_rad_s
            ),
            platen_angular_speed_rad_s=0.0,
            head_speed_command_rad_s=self.config.nominal_head_angular_speed_rad_s,
            head_angular_speed_rad_s=0.0,
            slurry_flow_command_m3_s=self.config.reference_slurry_flow_m3_s,
            slurry_availability=0.0,
            slurry_flow_m3_s=0.0,
            dresser_command=0.0,
            realized_dressing_activity=0.0,
            recipe_modifier=self.config.nominal_recipe_modifier,
            relative_velocity_m_s=0.0,
            pressure_velocity_exposure=0.0,
            interface_temperature_k=self.config.interface_reference_temperature_k,
            pad_surface_activity=1.0,
            pad_remaining_life=1.0,
            dresser_effectiveness=1.0,
            friction_heat_w=0.0,
            cooling_heat_w=0.0,
            slurry_heat_w=0.0,
            thermal_energy_residual_w=0.0,
            instantaneous_mrr_physics_m_s=0.0,
            process_discrepancy_m_s=0.0,
            instantaneous_mrr_m_s=0.0,
            cumulative_removal_m=0.0,
            active_polish_time_s=0.0,
            stage_average_mrr_m_s=0.0,
        )
        state.validate(self.config)
        return state

    def nominal_polish_state(self) -> CmpState:
        velocity = self.area_mean_relative_velocity(
            self.config.nominal_platen_angular_speed_rad_s,
            self.config.nominal_head_angular_speed_rad_s,
        )
        exposure = self.pressure_velocity_exposure(
            self.config.nominal_contact_pressure_pa,
            self.config.nominal_platen_angular_speed_rad_s,
            self.config.nominal_head_angular_speed_rad_s,
        )
        friction_heat = (
            self.config.friction_heat_fraction
            * self.config.friction_coefficient
            * self.config.contact_area_m2
            * self.config.nominal_contact_pressure_pa
            * velocity
        )
        physics_mrr = self.config.reference_mrr_m_s * exposure
        state = CmpState(
            mode=CmpMode.POLISH,
            mode_elapsed_s=0.0,
            hold_reason=CmpHoldReason.NONE,
            recovery_valid_dwell_s=0.0,
            transition_count=0,
            contact_pressure_command_pa=self.config.nominal_contact_pressure_pa,
            contact_pressure_pa=self.config.nominal_contact_pressure_pa,
            platen_speed_command_rad_s=(
                self.config.nominal_platen_angular_speed_rad_s
            ),
            platen_angular_speed_rad_s=(
                self.config.nominal_platen_angular_speed_rad_s
            ),
            head_speed_command_rad_s=self.config.nominal_head_angular_speed_rad_s,
            head_angular_speed_rad_s=self.config.nominal_head_angular_speed_rad_s,
            slurry_flow_command_m3_s=self.config.reference_slurry_flow_m3_s,
            slurry_availability=1.0,
            slurry_flow_m3_s=self.config.reference_slurry_flow_m3_s,
            dresser_command=0.0,
            realized_dressing_activity=0.0,
            recipe_modifier=self.config.nominal_recipe_modifier,
            relative_velocity_m_s=velocity,
            pressure_velocity_exposure=exposure,
            interface_temperature_k=self.config.interface_reference_temperature_k,
            pad_surface_activity=1.0,
            pad_remaining_life=1.0,
            dresser_effectiveness=1.0,
            friction_heat_w=friction_heat,
            cooling_heat_w=0.0,
            slurry_heat_w=0.0,
            thermal_energy_residual_w=0.0,
            instantaneous_mrr_physics_m_s=physics_mrr,
            process_discrepancy_m_s=0.0,
            instantaneous_mrr_m_s=min(physics_mrr, self.config.maximum_mrr_m_s),
            cumulative_removal_m=0.0,
            active_polish_time_s=0.0,
            stage_average_mrr_m_s=0.0,
        )
        state.validate(self.config)
        return state

    @staticmethod
    def _finite_action_value(action: Mapping[str, Any], name: str, default: float) -> float:
        value = action.get(name, default)
        if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value):
            raise CmpModelError(f"{name} must be a finite real number")
        return float(value)

    @staticmethod
    def _first_order_slew(
        current: float,
        target: float,
        time_constant_s: float,
        negative_rate_limit: float,
        positive_rate_limit: float,
        dt_s: float,
    ) -> float:
        raw_rate = (target - current) / time_constant_s
        rate = min(positive_rate_limit, max(-negative_rate_limit, raw_rate))
        candidate = current + dt_s * rate
        if (target - current) * (target - candidate) < 0.0:
            return target
        return candidate

    def _parse_action(
        self,
        state: CmpState,
        action: Mapping[str, Any] | None,
    ) -> dict[str, float | CmpMode]:
        raw = dict(action or {})
        unknown = set(raw) - self._ALLOWED_ACTION_KEYS
        if unknown:
            raise CmpModelError(f"unknown CMP action keys: {sorted(unknown)}")
        try:
            mode = CmpMode(raw.get("mode_request", state.mode))
        except (TypeError, ValueError) as exc:
            raise CmpModelError("mode_request is not a canonical CMP mode") from exc
        parsed: dict[str, float | CmpMode] = {
            "mode_request": mode,
            "contact_pressure_command_pa": self._finite_action_value(
                raw,
                "contact_pressure_command_pa",
                state.contact_pressure_command_pa,
            ),
            "platen_speed_command_rad_s": self._finite_action_value(
                raw,
                "platen_speed_command_rad_s",
                state.platen_speed_command_rad_s,
            ),
            "head_speed_command_rad_s": self._finite_action_value(
                raw,
                "head_speed_command_rad_s",
                state.head_speed_command_rad_s,
            ),
            "slurry_flow_command_m3_s": self._finite_action_value(
                raw,
                "slurry_flow_command_m3_s",
                state.slurry_flow_command_m3_s,
            ),
            "dresser_command": self._finite_action_value(
                raw,
                "dresser_command",
                state.dresser_command,
            ),
            "recipe_modifier": self._finite_action_value(
                raw,
                "recipe_modifier",
                state.recipe_modifier,
            ),
        }
        if not (
            0.0
            <= float(parsed["contact_pressure_command_pa"])
            <= self.config.maximum_contact_pressure_pa
        ):
            raise CmpModelError("contact pressure command is outside its bounds")
        if abs(float(parsed["platen_speed_command_rad_s"])) > (
            self.config.maximum_abs_platen_angular_speed_rad_s
        ):
            raise CmpModelError("platen speed command exceeds its magnitude bound")
        if abs(float(parsed["head_speed_command_rad_s"])) > (
            self.config.maximum_abs_head_angular_speed_rad_s
        ):
            raise CmpModelError("head speed command exceeds its magnitude bound")
        if not (
            0.0
            <= float(parsed["slurry_flow_command_m3_s"])
            <= self.config.reference_slurry_flow_m3_s
        ):
            raise CmpModelError("slurry flow command is outside its bounds")
        if not 0.0 <= float(parsed["dresser_command"]) <= 1.0:
            raise CmpModelError("dresser command must be within [0, 1]")
        if not (
            self.config.minimum_recipe_modifier
            <= float(parsed["recipe_modifier"])
            <= self.config.maximum_recipe_modifier
        ):
            raise CmpModelError("recipe modifier is outside its bounds")
        return parsed

    def _resolve_mode(
        self,
        state: CmpState,
        requested: CmpMode,
        boundary: CmpBoundaryConditions,
        dt_s: float,
    ) -> tuple[CmpMode, float, CmpHoldReason]:
        valid = boundary.utilities_valid and boundary.sensors_valid
        if state.mode is CmpMode.RECOVER and valid:
            candidate_dwell = state.recovery_valid_dwell_s + dt_s
        elif state.mode is CmpMode.HOLD and requested is CmpMode.RECOVER and valid:
            candidate_dwell = dt_s
        else:
            candidate_dwell = 0.0

        if boundary.force_hold and state.mode is not CmpMode.COMPLETE:
            next_mode = CmpMode.HOLD
            hold_reason = CmpHoldReason.FORCED_BOUNDARY
        else:
            if requested not in self._ALLOWED_TRANSITIONS[state.mode]:
                raise CmpModelError(
                    f"invalid CMP mode transition {state.mode.value} -> {requested.value}"
                )
            next_mode = requested
            if requested is CmpMode.POLISH and not valid:
                if state.mode is CmpMode.RECOVER:
                    next_mode = CmpMode.RECOVER
                else:
                    raise CmpModelError("POLISH entry requires valid utilities and sensors")
            if (
                state.mode is CmpMode.RECOVER
                and requested in {CmpMode.PREPARE, CmpMode.POLISH}
                and candidate_dwell + 1.0e-12 < self.config.minimum_recovery_dwell_s
            ):
                next_mode = CmpMode.RECOVER
            if next_mode is CmpMode.HOLD and state.mode is CmpMode.HOLD:
                hold_reason = state.hold_reason
            elif next_mode is CmpMode.HOLD:
                hold_reason = CmpHoldReason.REQUESTED
            else:
                hold_reason = CmpHoldReason.NONE
        recovery_dwell = candidate_dwell if next_mode is CmpMode.RECOVER else 0.0
        return next_mode, recovery_dwell, hold_reason

    def step(
        self,
        state: CmpState,
        action: Mapping[str, Any] | None,
        disturbance: Mapping[str, Any] | None,
        dt_s: float,
    ) -> CmpState:
        if (
            isinstance(dt_s, bool)
            or not isinstance(dt_s, Real)
            or not math.isfinite(dt_s)
            or dt_s <= 0.0
        ):
            raise CmpModelError("dt_s must be finite and positive")
        dt_s = float(dt_s)
        if dt_s > self.config.maximum_timestep_s + 1.0e-12:
            raise CmpModelError("dt_s exceeds the CMP explicit-update stability bound")
        state.validate(self.config)
        parsed = self._parse_action(state, action)
        boundary = CmpBoundaryConditions.from_mapping(disturbance, self.config)
        requested = parsed["mode_request"]
        assert isinstance(requested, CmpMode)
        next_mode, recovery_dwell, hold_reason = self._resolve_mode(
            state,
            requested,
            boundary,
            dt_s,
        )

        contact_command = float(parsed["contact_pressure_command_pa"])
        platen_command = float(parsed["platen_speed_command_rad_s"])
        head_command = float(parsed["head_speed_command_rad_s"])
        slurry_command = float(parsed["slurry_flow_command_m3_s"])
        dresser_command = float(parsed["dresser_command"])
        recipe_modifier = float(parsed["recipe_modifier"])

        if next_mode in {CmpMode.PREPARE, CmpMode.POLISH}:
            pressure_target = contact_command
            platen_target = platen_command
            head_target = head_command
            slurry_target = (
                slurry_command
                / self.config.reference_slurry_flow_m3_s
                * boundary.slurry_utility_availability
            )
        elif next_mode is CmpMode.DRESS:
            pressure_target = 0.0
            platen_target = platen_command
            head_target = 0.0
            slurry_target = 0.0
        else:
            pressure_target = 0.0
            platen_target = 0.0
            head_target = 0.0
            slurry_target = 0.0

        contact_pressure = self._first_order_slew(
            state.contact_pressure_pa,
            pressure_target,
            self.config.pressure_time_constant_s,
            self.config.pressure_ramp_down_pa_s,
            self.config.pressure_ramp_up_pa_s,
            dt_s,
        )
        contact_pressure = min(
            self.config.maximum_contact_pressure_pa,
            max(0.0, contact_pressure),
        )
        platen_speed = self._first_order_slew(
            state.platen_angular_speed_rad_s,
            platen_target,
            self.config.spindle_time_constant_s,
            self.config.spindle_slew_rate_rad_s2,
            self.config.spindle_slew_rate_rad_s2,
            dt_s,
        )
        head_speed = self._first_order_slew(
            state.head_angular_speed_rad_s,
            head_target,
            self.config.spindle_time_constant_s,
            self.config.spindle_slew_rate_rad_s2,
            self.config.spindle_slew_rate_rad_s2,
            dt_s,
        )
        slurry_availability = state.slurry_availability + dt_s * (
            slurry_target - state.slurry_availability
        ) / self.config.slurry_time_constant_s
        slurry_availability = min(1.0, max(0.0, slurry_availability))
        slurry_flow = self.config.reference_slurry_flow_m3_s * slurry_availability

        relative_velocity = self.area_mean_relative_velocity(platen_speed, head_speed)
        exposure = self.pressure_velocity_exposure(
            contact_pressure,
            platen_speed,
            head_speed,
        )
        polish_indicator = 1.0 if next_mode is CmpMode.POLISH else 0.0
        dress_indicator = 1.0 if next_mode is CmpMode.DRESS else 0.0
        dressing_activity = (
            dress_indicator * dresser_command * boundary.dressing_availability
        )

        friction_heat = (
            polish_indicator
            * self.config.friction_heat_fraction
            * self.config.friction_coefficient
            * self.config.contact_area_m2
            * contact_pressure
            * relative_velocity
        )
        cooling_heat = (
            self.config.nominal_cooling_conductance_w_k
            * boundary.cooling_conductance_factor
            * (state.interface_temperature_k - boundary.coolant_temperature_k)
        )
        slurry_heat = (
            self.config.slurry_density_kg_m3
            * self.config.slurry_specific_heat_j_kg_k
            * slurry_flow
            * (
                state.interface_temperature_k
                - self.config.slurry_supply_temperature_k
            )
        )
        net_heat = friction_heat - cooling_heat - slurry_heat
        interface_temperature = state.interface_temperature_k + (
            dt_s * net_heat / self.config.interface_thermal_capacity_j_k
        )
        if not (
            self.config.minimum_interface_temperature_k
            <= interface_temperature
            <= self.config.maximum_interface_temperature_k
        ):
            raise CmpModelError("interface temperature left the configured envelope")
        thermal_residual = (
            self.config.interface_thermal_capacity_j_k
            * (interface_temperature - state.interface_temperature_k)
            / dt_s
            - net_heat
        )

        pad_activity = state.pad_surface_activity + dt_s * (
            -polish_indicator
            * self.config.pad_glazing_rate_s_inv
            * exposure
            * state.pad_surface_activity
            + dressing_activity
            * self.config.pad_conditioning_rate_s_inv
            * state.dresser_effectiveness
            * (1.0 - state.pad_surface_activity)
        )
        pad_remaining = state.pad_remaining_life - dt_s * (
            polish_indicator * self.config.pad_wear_polish_rate_s_inv * exposure
            + dressing_activity * self.config.pad_wear_dress_rate_s_inv
        )
        dresser_effectiveness = state.dresser_effectiveness - dt_s * (
            dressing_activity
            * self.config.dresser_wear_rate_s_inv
            * state.dresser_effectiveness
        )
        pad_activity = min(1.0, max(0.0, pad_activity))
        pad_remaining = min(1.0, max(0.0, pad_remaining))
        dresser_effectiveness = min(1.0, max(0.0, dresser_effectiveness))

        pad_modifier = self.config.minimum_pad_modifier + (
            1.0 - self.config.minimum_pad_modifier
        ) * pad_activity * pad_remaining**self.config.pad_life_exponent
        temperature_modifier = min(
            self.config.maximum_temperature_modifier,
            max(
                self.config.minimum_temperature_modifier,
                math.exp(
                    self.config.temperature_sensitivity_k_inv
                    * (
                        interface_temperature
                        - self.config.interface_reference_temperature_k
                    )
                ),
            ),
        )
        slurry_modifier = slurry_availability
        physics_mrr = (
            polish_indicator
            * self.config.reference_mrr_m_s
            * exposure
            * slurry_modifier
            * temperature_modifier
            * pad_modifier
            * recipe_modifier
        )
        if not math.isfinite(physics_mrr) or physics_mrr < 0.0:
            raise CmpModelError("equivalent physics MRR is nonfinite or negative")
        if polish_indicator:
            true_mrr = min(
                self.config.maximum_mrr_m_s,
                max(0.0, physics_mrr + boundary.process_discrepancy_m_s),
            )
        else:
            true_mrr = 0.0
        cumulative_removal = state.cumulative_removal_m + dt_s * true_mrr
        active_polish_time = state.active_polish_time_s + dt_s * polish_indicator
        stage_average = (
            cumulative_removal / active_polish_time
            if active_polish_time > 0.0
            else 0.0
        )
        mode_elapsed = state.mode_elapsed_s + dt_s if next_mode is state.mode else dt_s

        next_state = CmpState(
            mode=next_mode,
            mode_elapsed_s=mode_elapsed,
            hold_reason=hold_reason,
            recovery_valid_dwell_s=recovery_dwell,
            transition_count=state.transition_count + int(next_mode is not state.mode),
            contact_pressure_command_pa=contact_command,
            contact_pressure_pa=contact_pressure,
            platen_speed_command_rad_s=platen_command,
            platen_angular_speed_rad_s=platen_speed,
            head_speed_command_rad_s=head_command,
            head_angular_speed_rad_s=head_speed,
            slurry_flow_command_m3_s=slurry_command,
            slurry_availability=slurry_availability,
            slurry_flow_m3_s=slurry_flow,
            dresser_command=dresser_command,
            realized_dressing_activity=dressing_activity,
            recipe_modifier=recipe_modifier,
            relative_velocity_m_s=relative_velocity,
            pressure_velocity_exposure=exposure,
            interface_temperature_k=interface_temperature,
            pad_surface_activity=pad_activity,
            pad_remaining_life=pad_remaining,
            dresser_effectiveness=dresser_effectiveness,
            friction_heat_w=friction_heat,
            cooling_heat_w=cooling_heat,
            slurry_heat_w=slurry_heat,
            thermal_energy_residual_w=thermal_residual,
            instantaneous_mrr_physics_m_s=physics_mrr,
            process_discrepancy_m_s=boundary.process_discrepancy_m_s,
            instantaneous_mrr_m_s=true_mrr,
            cumulative_removal_m=cumulative_removal,
            active_polish_time_s=active_polish_time,
            stage_average_mrr_m_s=stage_average,
        )
        next_state.validate(self.config)
        return next_state

    @staticmethod
    def parameter_provenance_classes() -> dict[str, str]:
        """Classify every frozen configuration parameter except its registry ID."""

        literature = {"kinematics_model", "pressure_exponent", "velocity_exponent"}
        engineering = {
            "radial_quadrature_order",
            "angular_quadrature_order",
            "slurry_density_kg_m3",
            "slurry_specific_heat_j_kg_k",
        }
        names = {field.name for field in fields(CmpConfig)} - {"provenance_id"}
        return {
            name: (
                "Literature-supported"
                if name in literature
                else "Engineering approximation"
                if name in engineering
                else "Synthetic assumption"
            )
            for name in sorted(names)
        }

    @staticmethod
    def latent_signal_values(state: CmpState, config: CmpConfig) -> dict[str, Any]:
        """Return canonical latent values without creating online observations."""

        state.validate(config)
        return {
            "cmp.process_mode": state.mode.value,
            "cmp.contact_pressure_command": state.contact_pressure_command_pa,
            "cmp.contact_pressure": state.contact_pressure_pa,
            "cmp.relative_velocity": state.relative_velocity_m_s,
            "cmp.head_angular_speed": state.head_angular_speed_rad_s,
            "cmp.platen_angular_speed": state.platen_angular_speed_rad_s,
            "cmp.slurry_flow": state.slurry_flow_m3_s,
            "cmp.slurry_availability": state.slurry_availability,
            "cmp.pressure_velocity_exposure": state.pressure_velocity_exposure,
            "cmp.interface_temperature": state.interface_temperature_k,
            "cmp.pad_surface_activity": state.pad_surface_activity,
            "cmp.pad_remaining_life": state.pad_remaining_life,
            "cmp.dresser_effectiveness": state.dresser_effectiveness,
            "cmp.dressing_activity": state.realized_dressing_activity,
            "cmp.process_discrepancy": state.process_discrepancy_m_s,
            "cmp.thermal_energy_residual": state.thermal_energy_residual_w,
            "cmp.mrr": state.instantaneous_mrr_m_s,
            "cmp.mrr_physics": state.instantaneous_mrr_physics_m_s,
            "cmp.mrr_deviation": (
                state.instantaneous_mrr_m_s - config.reference_mrr_m_s
            ),
            "cmp.cumulative_removal": state.cumulative_removal_m,
            "cmp.active_polish_time": state.active_polish_time_s,
            "cmp.stage_average_mrr": state.stage_average_mrr_m_s,
        }
