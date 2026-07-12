"""Speed-scaled centrifugal-pump curve for the synthetic utility plant.

The model identifies a quasi-steady operating flow from pump speed and the
network differential pressure. It is a bounded engineering approximation, not
a manufacturer performance curve or equipment-selection model.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Mapping

from .base import DynamicSubsystem


class PumpModelError(ValueError):
    """Raised when pump parameters or boundary conditions are invalid."""


@dataclass(frozen=True)
class PumpConfig:
    provenance_id: str = "synthetic-pump-curve-v2"
    reference_motor_speed_rad_s: float = 188.5
    reference_flow_m3_s: float = 2.0e-4
    reference_head_pa: float = 2.0e5
    shutoff_head_pa: float = 4.0e5
    hydraulic_efficiency: float = 0.70
    maximum_flow_m3_s: float = 5.0e-4
    max_speed_ratio: float = 1.20
    operating_point_tolerance_pa: float = 1.0e-6

    def validate(self) -> None:
        if not isinstance(self.provenance_id, str) or not self.provenance_id.strip():
            raise PumpModelError("provenance_id must be a non-empty string")
        for name, value in {
            "reference_motor_speed_rad_s": self.reference_motor_speed_rad_s,
            "reference_flow_m3_s": self.reference_flow_m3_s,
            "reference_head_pa": self.reference_head_pa,
            "shutoff_head_pa": self.shutoff_head_pa,
            "hydraulic_efficiency": self.hydraulic_efficiency,
            "maximum_flow_m3_s": self.maximum_flow_m3_s,
            "max_speed_ratio": self.max_speed_ratio,
            "operating_point_tolerance_pa": self.operating_point_tolerance_pa,
        }.items():
            if not math.isfinite(value) or value <= 0.0:
                raise PumpModelError(f"{name} must be finite and positive")
        if self.shutoff_head_pa <= self.reference_head_pa:
            raise PumpModelError("shutoff head must exceed reference head")
        if self.reference_flow_m3_s > self.maximum_flow_m3_s:
            raise PumpModelError("reference flow must not exceed maximum flow")
        if self.hydraulic_efficiency > 1.0:
            raise PumpModelError("hydraulic_efficiency must not exceed one")
        if self.maximum_possible_flow_m3_s > self.maximum_flow_m3_s:
            raise PumpModelError("maximum_flow_m3_s does not contain the configured pump curve")

    @property
    def curve_coefficient_pa_s2_m6(self) -> float:
        """Quadratic head-loss coefficient in ``Pa / (m³/s)²``."""

        return (self.shutoff_head_pa - self.reference_head_pa) / self.reference_flow_m3_s**2

    @property
    def maximum_possible_flow_m3_s(self) -> float:
        return self.max_speed_ratio * math.sqrt(
            self.shutoff_head_pa / self.curve_coefficient_pa_s2_m6
        )

    @property
    def reference_power_w(self) -> float:
        return self.reference_flow_m3_s * self.reference_head_pa / self.hydraulic_efficiency


@dataclass(frozen=True)
class PumpState:
    speed_ratio: float
    volumetric_flow_m3_s: float
    head_pa: float
    power_w: float
    system_differential_pressure_pa: float = 0.0
    operating_point_residual_pa: float = 0.0
    check_valve_closed: bool = False
    head_degradation_factor: float = 1.0

    def validate(self, config: PumpConfig) -> None:
        values = {
            "speed_ratio": self.speed_ratio,
            "volumetric_flow_m3_s": self.volumetric_flow_m3_s,
            "head_pa": self.head_pa,
            "power_w": self.power_w,
            "system_differential_pressure_pa": self.system_differential_pressure_pa,
            "operating_point_residual_pa": self.operating_point_residual_pa,
            "head_degradation_factor": self.head_degradation_factor,
        }
        if any(not math.isfinite(value) for value in values.values()):
            raise PumpModelError("pump state must be finite")
        if not 0.0 <= self.speed_ratio <= config.max_speed_ratio:
            raise PumpModelError("pump speed ratio is outside configured bounds")
        if not 0.0 <= self.volumetric_flow_m3_s <= config.maximum_flow_m3_s:
            raise PumpModelError("pump flow is outside configured bounds")
        if self.head_pa < 0.0 or self.power_w < 0.0 or self.system_differential_pressure_pa < 0.0:
            raise PumpModelError("pump head, power, and system pressure must be non-negative")
        if not 0.0 <= self.head_degradation_factor <= 1.0:
            raise PumpModelError("head degradation factor must be within [0, 1]")
        if not self.check_valve_closed and abs(self.operating_point_residual_pa) > config.operating_point_tolerance_pa:
            raise PumpModelError("open-check-valve pump operating point does not satisfy the curve")


class PumpSubsystem(DynamicSubsystem[PumpState, PumpConfig]):
    """Quasi-steady pump curve evaluated against network backpressure."""

    def __init__(self, config: PumpConfig | None = None) -> None:
        self.config = config or PumpConfig()
        self.config.validate()

    def reset(self, initial_state: PumpState | None = None) -> PumpState:
        if initial_state is None:
            initial_state = PumpState(0.0, 0.0, 0.0, 0.0, check_valve_closed=True)
        initial_state.validate(self.config)
        return initial_state

    def curve_head_pa(
        self,
        flow_m3_s: float,
        speed_ratio: float,
        head_degradation_factor: float = 1.0,
    ) -> float:
        """Return non-negative pump-curve head at one flow and speed."""

        if any(
            not math.isfinite(value)
            for value in (flow_m3_s, speed_ratio, head_degradation_factor)
        ):
            raise PumpModelError("pump-curve arguments must be finite")
        if flow_m3_s < 0.0:
            raise PumpModelError("pump-curve flow cannot be negative")
        if not 0.0 <= speed_ratio <= self.config.max_speed_ratio:
            raise PumpModelError("speed ratio is outside configured bounds")
        if not 0.0 <= head_degradation_factor <= 1.0:
            raise PumpModelError("head degradation factor must be within [0, 1]")
        head = (
            head_degradation_factor * self.config.shutoff_head_pa * speed_ratio**2
            - self.config.curve_coefficient_pa_s2_m6 * flow_m3_s**2
        )
        return max(0.0, head)

    def operating_point(
        self,
        motor_speed_rad_s: float,
        system_differential_pressure_pa: float,
        head_degradation_factor: float = 1.0,
    ) -> PumpState:
        """Solve pump flow at a supplied network differential pressure.

        A closed check valve is represented when network pressure exceeds the
        speed-scaled shutoff head. Reverse flow is intentionally excluded.
        """

        if not math.isfinite(motor_speed_rad_s) or motor_speed_rad_s < 0.0:
            raise PumpModelError("motor speed must be finite and non-negative")
        if not math.isfinite(system_differential_pressure_pa) or system_differential_pressure_pa < 0.0:
            raise PumpModelError("system differential pressure must be finite and non-negative")
        if not math.isfinite(head_degradation_factor) or not 0.0 <= head_degradation_factor <= 1.0:
            raise PumpModelError("head degradation factor must be within [0, 1]")

        ratio = min(
            self.config.max_speed_ratio,
            motor_speed_rad_s / self.config.reference_motor_speed_rad_s,
        )
        available_shutoff_head = (
            head_degradation_factor * self.config.shutoff_head_pa * ratio**2
        )
        if ratio == 0.0 or available_shutoff_head <= system_differential_pressure_pa:
            state = PumpState(
                speed_ratio=ratio,
                volumetric_flow_m3_s=0.0,
                head_pa=available_shutoff_head,
                power_w=0.0,
                system_differential_pressure_pa=system_differential_pressure_pa,
                operating_point_residual_pa=0.0,
                check_valve_closed=True,
                head_degradation_factor=head_degradation_factor,
            )
        else:
            flow = math.sqrt(
                (available_shutoff_head - system_differential_pressure_pa)
                / self.config.curve_coefficient_pa_s2_m6
            )
            if flow > self.config.maximum_flow_m3_s:
                raise PumpModelError("pump operating flow exceeds the configured envelope")
            curve_head = self.curve_head_pa(flow, ratio, head_degradation_factor)
            residual = curve_head - system_differential_pressure_pa
            power = flow * system_differential_pressure_pa / self.config.hydraulic_efficiency
            state = PumpState(
                speed_ratio=ratio,
                volumetric_flow_m3_s=flow,
                head_pa=curve_head,
                power_w=power,
                system_differential_pressure_pa=system_differential_pressure_pa,
                operating_point_residual_pa=residual,
                check_valve_closed=False,
                head_degradation_factor=head_degradation_factor,
            )
        state.validate(self.config)
        return state

    def from_motor_speed(self, motor_speed_rad_s: float) -> PumpState:
        """Return the homologous reference point for affinity-law checks."""

        if not math.isfinite(motor_speed_rad_s) or motor_speed_rad_s < 0.0:
            raise PumpModelError("motor speed must be finite and non-negative")
        ratio = min(
            self.config.max_speed_ratio,
            motor_speed_rad_s / self.config.reference_motor_speed_rad_s,
        )
        return self.operating_point(
            motor_speed_rad_s,
            self.config.reference_head_pa * ratio**2,
        )

    def step(
        self,
        state: PumpState,
        action: Mapping[str, Any] | None,
        disturbance: Mapping[str, Any] | None,
        dt_s: float,
    ) -> PumpState:
        del action
        if not math.isfinite(dt_s) or dt_s <= 0.0:
            raise PumpModelError("dt_s must be finite and positive")
        state.validate(self.config)
        event = disturbance or {}
        return self.operating_point(
            float(event.get("motor_speed_rad_s", 0.0)),
            float(event.get("system_differential_pressure_pa", 0.0)),
            float(event.get("head_degradation_factor", 1.0)),
        )
