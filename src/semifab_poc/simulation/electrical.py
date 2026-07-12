"""Bounded electrical disturbance and UPS transfer model.

This is a lumped, simulation-only model. It represents voltage/frequency
disturbances and UPS mode timing; it does not model switching waveforms,
electromagnetic transients, hardware protection, or production response.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from enum import Enum
from typing import Any, Mapping

from .base import DynamicSubsystem


class ElectricalModelError(ValueError):
    """Raised when electrical configuration, state, or disturbance is invalid."""


class UpsMode(str, Enum):
    GRID = "GRID"
    TRANSFER = "TRANSFER"
    BATTERY = "BATTERY"
    BYPASS = "BYPASS"
    RECOVERY = "RECOVERY"


@dataclass(frozen=True)
class ElectricalConfig:
    provenance_id: str = "synthetic-electrical-energy-v2"
    nominal_voltage_pu: float = 1.0
    nominal_frequency_hz: float = 50.0
    voltage_min_pu: float = 0.0
    voltage_max_pu: float = 1.5
    frequency_min_hz: float = 0.0
    frequency_max_hz: float = 100.0
    transfer_threshold_pu: float = 0.85
    recovery_threshold_pu: float = 0.95
    transfer_delay_s: float = 0.05
    recovery_delay_s: float = 0.25
    output_time_constant_s: float = 0.05
    frequency_time_constant_s: float = 0.10
    transfer_output_pu: float = 0.80
    battery_output_pu: float = 1.00
    ups_rated_power_w: float = 3_000.0
    ups_overload_trip_ratio: float = 1.20
    nominal_ups_load_w: float = 2_500.0
    battery_capacity_j: float = 3_600_000.0
    initial_battery_energy_j: float = 3_600_000.0
    minimum_battery_energy_j: float = 0.0
    inverter_efficiency: float = 0.95
    maximum_charge_power_w: float = 500.0

    def validate(self) -> None:
        if not isinstance(self.provenance_id, str) or not self.provenance_id.strip():
            raise ElectricalModelError("provenance_id must be a non-empty string")
        positive = {
            "transfer_delay_s": self.transfer_delay_s,
            "recovery_delay_s": self.recovery_delay_s,
            "output_time_constant_s": self.output_time_constant_s,
            "frequency_time_constant_s": self.frequency_time_constant_s,
            "ups_rated_power_w": self.ups_rated_power_w,
            "ups_overload_trip_ratio": self.ups_overload_trip_ratio,
            "nominal_ups_load_w": self.nominal_ups_load_w,
            "battery_capacity_j": self.battery_capacity_j,
            "inverter_efficiency": self.inverter_efficiency,
            "maximum_charge_power_w": self.maximum_charge_power_w,
        }
        for name, value in positive.items():
            if not math.isfinite(value) or value <= 0.0:
                raise ElectricalModelError(f"{name} must be finite and positive")
        if not self.voltage_min_pu <= self.nominal_voltage_pu <= self.voltage_max_pu:
            raise ElectricalModelError("nominal voltage must be inside voltage bounds")
        if not self.frequency_min_hz <= self.nominal_frequency_hz <= self.frequency_max_hz:
            raise ElectricalModelError("nominal frequency must be inside frequency bounds")
        if not 0.0 < self.transfer_threshold_pu < self.recovery_threshold_pu <= self.voltage_max_pu:
            raise ElectricalModelError("voltage thresholds must satisfy 0 < transfer < recovery <= maximum")
        for name, value in {
            "transfer_output_pu": self.transfer_output_pu,
            "battery_output_pu": self.battery_output_pu,
        }.items():
            if not self.voltage_min_pu <= value <= self.voltage_max_pu:
                raise ElectricalModelError(f"{name} must be inside voltage bounds")
        if not math.isfinite(self.minimum_battery_energy_j) or self.minimum_battery_energy_j < 0.0:
            raise ElectricalModelError("minimum_battery_energy_j must be finite and non-negative")
        if not self.minimum_battery_energy_j < self.battery_capacity_j:
            raise ElectricalModelError("minimum battery energy must be below capacity")
        if not self.minimum_battery_energy_j <= self.initial_battery_energy_j <= self.battery_capacity_j:
            raise ElectricalModelError("initial battery energy must be inside configured bounds")
        if not 0.0 < self.inverter_efficiency <= 1.0:
            raise ElectricalModelError("inverter_efficiency must be within (0, 1]")
        if self.nominal_ups_load_w > self.ups_rated_power_w * self.ups_overload_trip_ratio:
            raise ElectricalModelError("nominal UPS load exceeds the overload limit")


@dataclass(frozen=True)
class ElectricalState:
    grid_voltage_pu: float
    grid_frequency_hz: float
    ups_output_voltage_pu: float
    ups_output_frequency_hz: float
    ups_mode: UpsMode
    battery_energy_j: float
    ups_load_power_w: float
    transfer_timer_s: float = 0.0
    recovery_timer_s: float = 0.0

    def validate(self, config: ElectricalConfig) -> None:
        values = {
            "grid_voltage_pu": self.grid_voltage_pu,
            "grid_frequency_hz": self.grid_frequency_hz,
            "ups_output_voltage_pu": self.ups_output_voltage_pu,
            "ups_output_frequency_hz": self.ups_output_frequency_hz,
            "battery_energy_j": self.battery_energy_j,
            "ups_load_power_w": self.ups_load_power_w,
            "transfer_timer_s": self.transfer_timer_s,
            "recovery_timer_s": self.recovery_timer_s,
        }
        if any(not math.isfinite(value) for value in values.values()):
            raise ElectricalModelError("electrical state must be finite")
        if not config.voltage_min_pu <= self.grid_voltage_pu <= config.voltage_max_pu:
            raise ElectricalModelError("grid voltage is outside configured bounds")
        if not config.frequency_min_hz <= self.grid_frequency_hz <= config.frequency_max_hz:
            raise ElectricalModelError("grid frequency is outside configured bounds")
        if not config.frequency_min_hz <= self.ups_output_frequency_hz <= config.frequency_max_hz:
            raise ElectricalModelError("UPS output frequency is outside configured bounds")
        if not config.voltage_min_pu <= self.ups_output_voltage_pu <= config.voltage_max_pu:
            raise ElectricalModelError("UPS output voltage is outside configured bounds")
        if self.transfer_timer_s < 0.0 or self.recovery_timer_s < 0.0:
            raise ElectricalModelError("UPS timers cannot be negative")
        if not config.minimum_battery_energy_j <= self.battery_energy_j <= config.battery_capacity_j:
            raise ElectricalModelError("battery energy is outside configured bounds")
        if self.ups_load_power_w < 0.0:
            raise ElectricalModelError("UPS load power cannot be negative")


class ElectricalSubsystem(DynamicSubsystem[ElectricalState, ElectricalConfig]):
    """Deterministic electrical/UPS dynamic subsystem."""

    def __init__(self, config: ElectricalConfig | None = None) -> None:
        self.config = config or ElectricalConfig()
        self.config.validate()

    def reset(self, initial_state: ElectricalState | None = None) -> ElectricalState:
        if initial_state is None:
            initial_state = ElectricalState(
                grid_voltage_pu=self.config.nominal_voltage_pu,
                grid_frequency_hz=self.config.nominal_frequency_hz,
                ups_output_voltage_pu=self.config.nominal_voltage_pu,
                ups_output_frequency_hz=self.config.nominal_frequency_hz,
                ups_mode=UpsMode.GRID,
                battery_energy_j=self.config.initial_battery_energy_j,
                ups_load_power_w=self.config.nominal_ups_load_w,
            )
        initial_state.validate(self.config)
        return initial_state

    def step(
        self,
        state: ElectricalState,
        action: Mapping[str, Any] | None,
        disturbance: Mapping[str, Any] | None,
        dt_s: float,
    ) -> ElectricalState:
        """Advance one step using bounded scenario inputs.

        Supported disturbance keys are `grid_voltage_pu`, `grid_voltage_delta_pu`,
        `grid_frequency_hz`, `grid_frequency_delta_hz`, `force_interruption`,
        `ups_load_power_w`, and `force_bypass`. Actions may request
        `force_ups_mode` for deterministic
        test scenarios; real controller actions are a later work package.
        """

        del action  # Electrical control actions are intentionally not implemented in T-WP04.
        if not math.isfinite(dt_s) or dt_s <= 0.0:
            raise ElectricalModelError("dt_s must be finite and positive")
        state.validate(self.config)
        if dt_s > self.config.output_time_constant_s or dt_s > self.config.frequency_time_constant_s:
            raise ElectricalModelError("dt_s exceeds explicit-Euler stability bound")
        event = disturbance or {}
        grid_voltage = float(event.get("grid_voltage_pu", self.config.nominal_voltage_pu))
        grid_voltage += float(event.get("grid_voltage_delta_pu", 0.0))
        if not math.isfinite(grid_voltage):
            raise ElectricalModelError("grid voltage disturbance must be finite")
        grid_voltage = min(self.config.voltage_max_pu, max(self.config.voltage_min_pu, grid_voltage))
        grid_frequency = float(event.get("grid_frequency_hz", self.config.nominal_frequency_hz))
        grid_frequency += float(event.get("grid_frequency_delta_hz", 0.0))
        if not math.isfinite(grid_frequency):
            raise ElectricalModelError("grid frequency disturbance must be finite")
        grid_frequency = min(self.config.frequency_max_hz, max(self.config.frequency_min_hz, grid_frequency))
        ups_load_power = float(event.get("ups_load_power_w", self.config.nominal_ups_load_w))
        if not math.isfinite(ups_load_power) or ups_load_power < 0.0:
            raise ElectricalModelError("ups_load_power_w must be finite and non-negative")
        interruption = bool(event.get("force_interruption", False))
        if interruption:
            grid_voltage = self.config.voltage_min_pu
        overload = ups_load_power > self.config.ups_rated_power_w * self.config.ups_overload_trip_ratio
        bypass = bool(event.get("force_bypass", False))
        forced_mode = event.get("force_ups_mode")
        if forced_mode is not None:
            try:
                mode = UpsMode(str(forced_mode))
            except ValueError as exc:
                raise ElectricalModelError(f"unknown forced UPS mode: {forced_mode}") from exc
            next_state = replace(state, ups_mode=mode, transfer_timer_s=0.0, recovery_timer_s=0.0)
        else:
            mode = state.ups_mode
            transfer_timer = state.transfer_timer_s
            recovery_timer = state.recovery_timer_s
            fault = interruption or grid_voltage < self.config.transfer_threshold_pu
            stable = not interruption and grid_voltage >= self.config.recovery_threshold_pu
            if bypass or overload:
                mode = UpsMode.BYPASS
                transfer_timer = 0.0
                recovery_timer = 0.0
            elif mode is UpsMode.GRID:
                if fault:
                    mode = UpsMode.TRANSFER
                    transfer_timer = self.config.transfer_delay_s
            elif mode is UpsMode.TRANSFER:
                transfer_timer = max(0.0, transfer_timer - dt_s)
                if transfer_timer == 0.0:
                    mode = UpsMode.BATTERY
            elif mode is UpsMode.BATTERY:
                if stable:
                    mode = UpsMode.RECOVERY
                    recovery_timer = self.config.recovery_delay_s
            elif mode is UpsMode.RECOVERY:
                if fault:
                    mode = UpsMode.TRANSFER
                    transfer_timer = self.config.transfer_delay_s
                    recovery_timer = 0.0
                else:
                    recovery_timer = max(0.0, recovery_timer - dt_s)
                    if recovery_timer == 0.0:
                        mode = UpsMode.GRID
            elif mode is UpsMode.BYPASS and stable:
                mode = UpsMode.RECOVERY
                recovery_timer = self.config.recovery_delay_s
            next_state = replace(
                state,
                ups_mode=mode,
                transfer_timer_s=transfer_timer,
                recovery_timer_s=recovery_timer,
            )

        if overload:
            next_state = replace(
                next_state,
                ups_mode=UpsMode.BYPASS,
                transfer_timer_s=0.0,
                recovery_timer_s=0.0,
            )

        battery_energy = next_state.battery_energy_j
        if next_state.ups_mode in {UpsMode.TRANSFER, UpsMode.BATTERY}:
            required_energy = ups_load_power * dt_s / self.config.inverter_efficiency
            available_energy = battery_energy - self.config.minimum_battery_energy_j
            if required_energy > available_energy + 1.0e-12:
                battery_energy = self.config.minimum_battery_energy_j
                next_state = replace(
                    next_state,
                    ups_mode=UpsMode.BYPASS,
                    transfer_timer_s=0.0,
                    recovery_timer_s=0.0,
                )
            else:
                # An exactly exhausted interval can round a few ulps below
                # the configured minimum. Preserve the accepted energy
                # decision while projecting only that numerical residue to
                # the physical state bound. The next unsupported interval
                # transitions deterministically to BYPASS above.
                battery_energy = max(
                    self.config.minimum_battery_energy_j,
                    battery_energy - required_energy,
                )
        elif next_state.ups_mode in {UpsMode.GRID, UpsMode.RECOVERY}:
            battery_energy = min(
                self.config.battery_capacity_j,
                battery_energy + self.config.maximum_charge_power_w * dt_s,
            )

        if next_state.ups_mode is UpsMode.GRID or next_state.ups_mode is UpsMode.RECOVERY:
            target_voltage = grid_voltage
        elif next_state.ups_mode is UpsMode.TRANSFER:
            target_voltage = self.config.transfer_output_pu
        elif next_state.ups_mode is UpsMode.BATTERY:
            target_voltage = self.config.battery_output_pu
        else:  # BYPASS
            target_voltage = grid_voltage
        if next_state.ups_mode in {UpsMode.TRANSFER, UpsMode.BATTERY}:
            target_frequency = self.config.nominal_frequency_hz
        else:
            target_frequency = grid_frequency
        voltage_alpha = dt_s / self.config.output_time_constant_s
        frequency_alpha = dt_s / self.config.frequency_time_constant_s
        updated = replace(
            next_state,
            grid_voltage_pu=grid_voltage,
            grid_frequency_hz=grid_frequency,
            ups_output_voltage_pu=next_state.ups_output_voltage_pu
            + voltage_alpha * (target_voltage - next_state.ups_output_voltage_pu),
            ups_output_frequency_hz=next_state.ups_output_frequency_hz
            + frequency_alpha * (target_frequency - next_state.ups_output_frequency_hz),
            battery_energy_j=battery_energy,
            ups_load_power_w=ups_load_power,
        )
        updated.validate(self.config)
        return updated
