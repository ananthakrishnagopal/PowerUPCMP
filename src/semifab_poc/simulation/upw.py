"""Conserved lumped UPW hydraulic, thermal, and proxy dynamics.

The model is simulation-only. Its dimensionless water-quality deviation is a
synthetic state, not measured conductivity, contamination, a physical defect,
or a yield outcome.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Mapping

from .base import DynamicSubsystem


class UpwModelError(ValueError):
    """Raised when a UPW configuration, state, action, or boundary is invalid."""


@dataclass(frozen=True)
class UpwConfig:
    provenance_id: str = "synthetic-upw-conserved-v2"
    nominal_supply_pressure_pa: float = 300_000.0
    nominal_return_pressure_pa: float = 100_000.0
    maximum_supply_pressure_pa: float = 600_000.0
    hydraulic_compliance_m3_pa: float = 2.0e-10
    return_resistance_pa_s_m3: float = 2.0e9
    tool_resistance_pa_s_m3: float = 1.0e9
    reference_pump_flow_m3_s: float = 2.0e-4
    maximum_flow_m3_s: float = 5.0e-4
    nominal_tool_demand_m3_s: float = 1.0e-4
    relief_set_pressure_pa: float = 500_000.0
    relief_resistance_pa_s_m3: float = 5.0e8
    hydraulic_balance_tolerance_m3_s: float = 1.0e-12
    maximum_hydraulic_timestep_s: float = 0.05
    hydraulic_solver_max_iterations: int = 100
    nominal_temperature_k: float = 293.15
    thermal_capacity_j_k: float = 5_000.0
    water_density_kg_m3: float = 997.0
    water_specific_heat_j_kg_k: float = 4_180.0
    ambient_thermal_conductance_w_k: float = 50.0
    minimum_temperature_k: float = 273.15
    maximum_temperature_k: float = 373.15
    nominal_water_quality_deviation_proxy: float = 0.0
    water_quality_proxy_time_constant_s: float = 60.0
    maximum_water_quality_deviation_proxy: float = 1.0

    def validate(self) -> None:
        if not isinstance(self.provenance_id, str) or not self.provenance_id.strip():
            raise UpwModelError("provenance_id must be a non-empty string")
        finite_positive = {
            "nominal_supply_pressure_pa": self.nominal_supply_pressure_pa,
            "nominal_return_pressure_pa": self.nominal_return_pressure_pa,
            "maximum_supply_pressure_pa": self.maximum_supply_pressure_pa,
            "hydraulic_compliance_m3_pa": self.hydraulic_compliance_m3_pa,
            "return_resistance_pa_s_m3": self.return_resistance_pa_s_m3,
            "tool_resistance_pa_s_m3": self.tool_resistance_pa_s_m3,
            "reference_pump_flow_m3_s": self.reference_pump_flow_m3_s,
            "maximum_flow_m3_s": self.maximum_flow_m3_s,
            "nominal_tool_demand_m3_s": self.nominal_tool_demand_m3_s,
            "relief_set_pressure_pa": self.relief_set_pressure_pa,
            "relief_resistance_pa_s_m3": self.relief_resistance_pa_s_m3,
            "hydraulic_balance_tolerance_m3_s": self.hydraulic_balance_tolerance_m3_s,
            "maximum_hydraulic_timestep_s": self.maximum_hydraulic_timestep_s,
            "thermal_capacity_j_k": self.thermal_capacity_j_k,
            "water_density_kg_m3": self.water_density_kg_m3,
            "water_specific_heat_j_kg_k": self.water_specific_heat_j_kg_k,
            "ambient_thermal_conductance_w_k": self.ambient_thermal_conductance_w_k,
            "water_quality_proxy_time_constant_s": self.water_quality_proxy_time_constant_s,
            "maximum_water_quality_deviation_proxy": self.maximum_water_quality_deviation_proxy,
        }
        for name, value in finite_positive.items():
            if not math.isfinite(value) or value <= 0.0:
                raise UpwModelError(f"{name} must be finite and positive")
        if not isinstance(self.hydraulic_solver_max_iterations, int) or self.hydraulic_solver_max_iterations <= 0:
            raise UpwModelError("hydraulic_solver_max_iterations must be a positive integer")
        if not 0.0 <= self.nominal_return_pressure_pa < self.nominal_supply_pressure_pa:
            raise UpwModelError("nominal return pressure must be non-negative and below nominal supply pressure")
        if self.maximum_supply_pressure_pa < self.nominal_supply_pressure_pa:
            raise UpwModelError("maximum supply pressure must not be below nominal supply pressure")
        if not self.nominal_supply_pressure_pa < self.relief_set_pressure_pa < self.maximum_supply_pressure_pa:
            raise UpwModelError("relief set pressure must be between nominal and maximum supply pressure")
        if self.reference_pump_flow_m3_s > self.maximum_flow_m3_s:
            raise UpwModelError("reference pump flow must not exceed maximum flow")
        if self.nominal_tool_demand_m3_s > self.maximum_flow_m3_s:
            raise UpwModelError("nominal tool demand must not exceed maximum flow")
        if not self.minimum_temperature_k <= self.nominal_temperature_k <= self.maximum_temperature_k:
            raise UpwModelError("nominal temperature must be inside temperature bounds")
        if not (
            0.0
            <= self.nominal_water_quality_deviation_proxy
            <= self.maximum_water_quality_deviation_proxy
        ):
            raise UpwModelError("nominal water-quality proxy must be inside bounds")

    @property
    def maximum_thermal_rate_w_k(self) -> float:
        return (
            self.water_density_kg_m3
            * self.water_specific_heat_j_kg_k
            * self.maximum_flow_m3_s
            + self.ambient_thermal_conductance_w_k
        )

    @property
    def minimum_thermal_time_constant_s(self) -> float:
        return self.thermal_capacity_j_k / self.maximum_thermal_rate_w_k


@dataclass(frozen=True)
class UpwState:
    supply_pressure_pa: float
    return_pressure_pa: float
    tool_flow_m3_s: float
    valve_position: float
    tool_demand_m3_s: float
    temperature_k: float
    water_quality_deviation_proxy: float
    return_flow_m3_s: float = 0.0
    relief_flow_m3_s: float = 0.0
    pump_inflow_m3_s: float = 0.0
    storage_flow_m3_s: float = 0.0
    mass_balance_residual_m3_s: float = 0.0

    def validate(self, config: UpwConfig) -> None:
        values = {
            "supply_pressure_pa": self.supply_pressure_pa,
            "return_pressure_pa": self.return_pressure_pa,
            "tool_flow_m3_s": self.tool_flow_m3_s,
            "valve_position": self.valve_position,
            "tool_demand_m3_s": self.tool_demand_m3_s,
            "temperature_k": self.temperature_k,
            "water_quality_deviation_proxy": self.water_quality_deviation_proxy,
            "return_flow_m3_s": self.return_flow_m3_s,
            "relief_flow_m3_s": self.relief_flow_m3_s,
            "pump_inflow_m3_s": self.pump_inflow_m3_s,
            "storage_flow_m3_s": self.storage_flow_m3_s,
            "mass_balance_residual_m3_s": self.mass_balance_residual_m3_s,
        }
        if any(not math.isfinite(value) for value in values.values()):
            raise UpwModelError("UPW state must be finite")
        if not 0.0 <= self.return_pressure_pa <= self.supply_pressure_pa <= config.maximum_supply_pressure_pa:
            raise UpwModelError("UPW pressures are outside configured bounds")
        if not 0.0 <= self.valve_position <= 1.0:
            raise UpwModelError("valve position must be within [0, 1]")
        for name in (
            "tool_flow_m3_s",
            "tool_demand_m3_s",
            "return_flow_m3_s",
            "relief_flow_m3_s",
            "pump_inflow_m3_s",
        ):
            if not 0.0 <= values[name] <= config.maximum_flow_m3_s:
                raise UpwModelError(f"{name} is outside configured bounds")
        if not config.minimum_temperature_k <= self.temperature_k <= config.maximum_temperature_k:
            raise UpwModelError("temperature is outside configured bounds")
        if not (
            0.0
            <= self.water_quality_deviation_proxy
            <= config.maximum_water_quality_deviation_proxy
        ):
            raise UpwModelError("water-quality deviation proxy is outside configured bounds")
        if abs(self.mass_balance_residual_m3_s) > config.hydraulic_balance_tolerance_m3_s:
            raise UpwModelError("hydraulic mass-balance residual exceeds tolerance")


class UpwSubsystem(DynamicSubsystem[UpwState, UpwConfig]):
    """Deterministic UPW model with an implicit conserved pressure update."""

    def __init__(self, config: UpwConfig | None = None) -> None:
        self.config = config or UpwConfig()
        self.config.validate()

    def _outflows(
        self,
        supply_pressure_pa: float,
        return_pressure_pa: float,
        valve_position: float,
        tool_demand_m3_s: float,
    ) -> tuple[float, float, float]:
        pressure_drop = max(0.0, supply_pressure_pa - return_pressure_pa)
        return_flow = pressure_drop / self.config.return_resistance_pa_s_m3
        valve_capacity = (
            valve_position * pressure_drop / self.config.tool_resistance_pa_s_m3
        )
        tool_flow = min(tool_demand_m3_s, max(0.0, valve_capacity))
        relief_flow = max(
            0.0,
            (supply_pressure_pa - self.config.relief_set_pressure_pa)
            / self.config.relief_resistance_pa_s_m3,
        )
        return tool_flow, return_flow, relief_flow

    def reset(self, initial_state: UpwState | None = None) -> UpwState:
        if initial_state is None:
            tool_flow, return_flow, relief_flow = self._outflows(
                self.config.nominal_supply_pressure_pa,
                self.config.nominal_return_pressure_pa,
                1.0,
                self.config.nominal_tool_demand_m3_s,
            )
            residual = (
                self.config.reference_pump_flow_m3_s
                - tool_flow
                - return_flow
                - relief_flow
            )
            if abs(residual) > self.config.hydraulic_balance_tolerance_m3_s:
                raise UpwModelError("configured nominal UPW point is not a hydraulic equilibrium")
            initial_state = UpwState(
                supply_pressure_pa=self.config.nominal_supply_pressure_pa,
                return_pressure_pa=self.config.nominal_return_pressure_pa,
                tool_flow_m3_s=tool_flow,
                valve_position=1.0,
                tool_demand_m3_s=self.config.nominal_tool_demand_m3_s,
                temperature_k=self.config.nominal_temperature_k,
                water_quality_deviation_proxy=self.config.nominal_water_quality_deviation_proxy,
                return_flow_m3_s=return_flow,
                relief_flow_m3_s=relief_flow,
                pump_inflow_m3_s=self.config.reference_pump_flow_m3_s,
                storage_flow_m3_s=0.0,
                mass_balance_residual_m3_s=residual,
            )
        initial_state.validate(self.config)
        return initial_state

    def _solve_supply_pressure(
        self,
        old_supply_pressure_pa: float,
        return_pressure_pa: float,
        pump_inflow_m3_s: float,
        valve_position: float,
        tool_demand_m3_s: float,
        dt_s: float,
    ) -> tuple[float, float, float, float, float, float]:
        storage_coefficient = self.config.hydraulic_compliance_m3_pa / dt_s

        def balance(pressure_pa: float) -> float:
            tool, returned, relief = self._outflows(
                pressure_pa,
                return_pressure_pa,
                valve_position,
                tool_demand_m3_s,
            )
            return (
                storage_coefficient * (pressure_pa - old_supply_pressure_pa)
                + tool
                + returned
                + relief
                - pump_inflow_m3_s
            )

        lower = return_pressure_pa
        upper = self.config.maximum_supply_pressure_pa
        lower_balance = balance(lower)
        upper_balance = balance(upper)
        tolerance = self.config.hydraulic_balance_tolerance_m3_s
        if lower_balance > tolerance:
            raise UpwModelError("return-pressure boundary is incompatible with hydraulic storage")
        if upper_balance < -tolerance:
            raise UpwModelError("configured relief capacity cannot bound the requested pump inflow")

        if abs(lower_balance) <= tolerance:
            pressure = lower
        elif abs(upper_balance) <= tolerance:
            pressure = upper
        else:
            pressure = 0.5 * (lower + upper)
            for _ in range(self.config.hydraulic_solver_max_iterations):
                residual = balance(pressure)
                if abs(residual) <= tolerance:
                    break
                if residual > 0.0:
                    upper = pressure
                else:
                    lower = pressure
                pressure = 0.5 * (lower + upper)
            else:
                raise UpwModelError("hydraulic balance solver did not converge")

        tool_flow, return_flow, relief_flow = self._outflows(
            pressure,
            return_pressure_pa,
            valve_position,
            tool_demand_m3_s,
        )
        storage_flow = storage_coefficient * (pressure - old_supply_pressure_pa)
        mass_residual = (
            pump_inflow_m3_s
            - tool_flow
            - return_flow
            - relief_flow
            - storage_flow
        )
        if abs(mass_residual) > tolerance:
            raise UpwModelError("hydraulic mass-balance residual exceeds tolerance")
        return pressure, tool_flow, return_flow, relief_flow, storage_flow, mass_residual

    def step(
        self,
        state: UpwState,
        action: Mapping[str, Any] | None,
        disturbance: Mapping[str, Any] | None,
        dt_s: float,
    ) -> UpwState:
        """Advance conserved hydraulics, thermal state, and synthetic proxy."""

        if not math.isfinite(dt_s) or dt_s <= 0.0:
            raise UpwModelError("dt_s must be finite and positive")
        if dt_s > self.config.maximum_hydraulic_timestep_s:
            raise UpwModelError("dt_s exceeds configured hydraulic operator-split bound")
        if dt_s > self.config.minimum_thermal_time_constant_s:
            raise UpwModelError("dt_s exceeds explicit-Euler thermal stability bound")
        if dt_s > self.config.water_quality_proxy_time_constant_s:
            raise UpwModelError("dt_s exceeds water-quality proxy stability bound")
        state.validate(self.config)
        action = action or {}
        event = disturbance or {}

        valve_position = float(action.get("valve_position", state.valve_position))
        valve_position += float(action.get("valve_delta", 0.0))
        if not math.isfinite(valve_position):
            raise UpwModelError("valve action must be finite")
        valve_position = min(1.0, max(0.0, valve_position))

        return_pressure = float(event.get("return_pressure_pa", self.config.nominal_return_pressure_pa))
        pump_inflow = float(event.get("pump_flow_m3_s", self.config.reference_pump_flow_m3_s))
        demand = float(event.get("tool_demand_m3_s", self.config.nominal_tool_demand_m3_s))
        if any(not math.isfinite(value) for value in (return_pressure, pump_inflow, demand)):
            raise UpwModelError("hydraulic boundary values must be finite")
        if not 0.0 <= return_pressure <= state.supply_pressure_pa:
            raise UpwModelError("return pressure must be within [0, current supply pressure]")
        if not 0.0 <= pump_inflow <= self.config.maximum_flow_m3_s:
            raise UpwModelError("pump inflow is outside the configured envelope")
        if not 0.0 <= demand <= self.config.maximum_flow_m3_s:
            raise UpwModelError("tool demand is outside the configured envelope")

        (
            supply_pressure,
            tool_flow,
            return_flow,
            relief_flow,
            storage_flow,
            mass_residual,
        ) = self._solve_supply_pressure(
            state.supply_pressure_pa,
            return_pressure,
            pump_inflow,
            valve_position,
            demand,
            dt_s,
        )

        inlet_temperature = float(event.get("inlet_temperature_k", self.config.nominal_temperature_k))
        ambient_temperature = float(event.get("ambient_temperature_k", self.config.nominal_temperature_k))
        thermal_load_w = float(event.get("thermal_load_w", 0.0))
        if any(
            not math.isfinite(value)
            for value in (inlet_temperature, ambient_temperature, thermal_load_w)
        ):
            raise UpwModelError("thermal boundary values must be finite")
        if not self.config.minimum_temperature_k <= inlet_temperature <= self.config.maximum_temperature_k:
            raise UpwModelError("inlet temperature is outside the configured envelope")
        if not self.config.minimum_temperature_k <= ambient_temperature <= self.config.maximum_temperature_k:
            raise UpwModelError("ambient temperature is outside the configured envelope")
        convective_conductance = (
            self.config.water_density_kg_m3
            * self.config.water_specific_heat_j_kg_k
            * pump_inflow
        )
        temperature_rate = (
            convective_conductance * (inlet_temperature - state.temperature_k)
            + self.config.ambient_thermal_conductance_w_k
            * (ambient_temperature - state.temperature_k)
            + thermal_load_w
        ) / self.config.thermal_capacity_j_k
        temperature = state.temperature_k + dt_s * temperature_rate
        if not self.config.minimum_temperature_k <= temperature <= self.config.maximum_temperature_k:
            raise UpwModelError("thermal update left the configured temperature envelope")

        proxy_source = float(
            event.get(
                "water_quality_source_deviation_proxy",
                self.config.nominal_water_quality_deviation_proxy,
            )
        )
        proxy_ingress = float(event.get("water_quality_ingress_proxy_per_s", 0.0))
        if not math.isfinite(proxy_source) or not math.isfinite(proxy_ingress):
            raise UpwModelError("water-quality proxy boundary values must be finite")
        if not 0.0 <= proxy_source <= self.config.maximum_water_quality_deviation_proxy:
            raise UpwModelError("water-quality source proxy is outside the configured envelope")
        proxy_rate = (
            (proxy_source - state.water_quality_deviation_proxy)
            / self.config.water_quality_proxy_time_constant_s
            + proxy_ingress
        )
        water_quality_proxy = state.water_quality_deviation_proxy + dt_s * proxy_rate
        if not 0.0 <= water_quality_proxy <= self.config.maximum_water_quality_deviation_proxy:
            raise UpwModelError("water-quality proxy update left the configured envelope")

        updated = UpwState(
            supply_pressure_pa=supply_pressure,
            return_pressure_pa=return_pressure,
            tool_flow_m3_s=tool_flow,
            valve_position=valve_position,
            tool_demand_m3_s=demand,
            temperature_k=temperature,
            water_quality_deviation_proxy=water_quality_proxy,
            return_flow_m3_s=return_flow,
            relief_flow_m3_s=relief_flow,
            pump_inflow_m3_s=pump_inflow,
            storage_flow_m3_s=storage_flow,
            mass_balance_residual_m3_s=mass_residual,
        )
        updated.validate(self.config)
        return updated
