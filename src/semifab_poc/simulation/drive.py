"""Bounded VFD and motor-speed dynamics driven by simulated UPS output."""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Any, Mapping

from .base import DynamicSubsystem


class DriveModelError(ValueError):
    """Raised when a VFD/motor state, command, or configuration is invalid."""


@dataclass(frozen=True)
class DriveConfig:
    provenance_id: str = "synthetic-drive-v1"
    nominal_motor_speed_rad_s: float = 188.5
    motor_time_constant_s: float = 0.20
    ramp_up_rate_rad_s2: float = 500.0
    ramp_down_rate_rad_s2: float = 1000.0
    undervoltage_trip_threshold_pu: float = 0.50
    derating_start_voltage_pu: float = 0.90
    derating_exponent: float = 1.0
    restart_delay_s: float = 0.25
    max_speed_ratio: float = 1.20

    def validate(self) -> None:
        if not isinstance(self.provenance_id, str) or not self.provenance_id.strip():
            raise DriveModelError("provenance_id must be a non-empty string")
        positive = {
            "nominal_motor_speed_rad_s": self.nominal_motor_speed_rad_s,
            "motor_time_constant_s": self.motor_time_constant_s,
            "ramp_up_rate_rad_s2": self.ramp_up_rate_rad_s2,
            "ramp_down_rate_rad_s2": self.ramp_down_rate_rad_s2,
            "derating_exponent": self.derating_exponent,
            "restart_delay_s": self.restart_delay_s,
            "max_speed_ratio": self.max_speed_ratio,
        }
        for name, value in positive.items():
            if not math.isfinite(value) or value <= 0.0:
                raise DriveModelError(f"{name} must be finite and positive")
        if not 0.0 < self.undervoltage_trip_threshold_pu < self.derating_start_voltage_pu <= 1.5:
            raise DriveModelError("trip and derating thresholds must satisfy 0 < trip < derating <= 1.5")


@dataclass(frozen=True)
class DriveState:
    vfd_command_pu: float
    vfd_available_output_pu: float
    motor_speed_rad_s: float
    tripped: bool = False
    restart_timer_s: float = 0.0

    def validate(self, config: DriveConfig) -> None:
        values = {
            "vfd_command_pu": self.vfd_command_pu,
            "vfd_available_output_pu": self.vfd_available_output_pu,
            "motor_speed_rad_s": self.motor_speed_rad_s,
            "restart_timer_s": self.restart_timer_s,
        }
        if any(not math.isfinite(value) for value in values.values()):
            raise DriveModelError("drive state must be finite")
        if not 0.0 <= self.vfd_command_pu <= 1.0:
            raise DriveModelError("VFD command must be within [0, 1]")
        if not 0.0 <= self.vfd_available_output_pu <= 1.0:
            raise DriveModelError("VFD available output must be within [0, 1]")
        if not 0.0 <= self.motor_speed_rad_s <= config.nominal_motor_speed_rad_s * config.max_speed_ratio:
            raise DriveModelError("motor speed is outside configured bounds")
        if self.restart_timer_s < 0.0:
            raise DriveModelError("restart timer cannot be negative")


class DriveSubsystem(DynamicSubsystem[DriveState, DriveConfig]):
    """Simulation-only VFD derating, motor lag, ramp, trip, and restart state."""

    def __init__(self, config: DriveConfig | None = None) -> None:
        self.config = config or DriveConfig()
        self.config.validate()

    def reset(self, initial_state: DriveState | None = None) -> DriveState:
        if initial_state is None:
            initial_state = DriveState(0.0, 0.0, 0.0)
        initial_state.validate(self.config)
        return initial_state

    def available_output(self, command_pu: float, ups_output_voltage_pu: float) -> float:
        """Return the bounded command after voltage-dependent derating."""

        if not math.isfinite(command_pu) or not math.isfinite(ups_output_voltage_pu):
            raise DriveModelError("command and UPS voltage must be finite")
        command = min(1.0, max(0.0, command_pu))
        if ups_output_voltage_pu <= self.config.undervoltage_trip_threshold_pu:
            return 0.0
        normalized = (ups_output_voltage_pu - self.config.undervoltage_trip_threshold_pu) / (
            self.config.derating_start_voltage_pu - self.config.undervoltage_trip_threshold_pu
        )
        derating = min(1.0, max(0.0, normalized)) ** self.config.derating_exponent
        return command * derating

    def step(
        self,
        state: DriveState,
        action: Mapping[str, Any] | None,
        disturbance: Mapping[str, Any] | None,
        dt_s: float,
    ) -> DriveState:
        if not math.isfinite(dt_s) or dt_s <= 0.0:
            raise DriveModelError("dt_s must be finite and positive")
        if dt_s > self.config.motor_time_constant_s:
            raise DriveModelError("dt_s exceeds explicit-Euler motor stability bound")
        state.validate(self.config)
        action = action or {}
        disturbance = disturbance or {}
        command = float(action.get("vfd_command_pu", state.vfd_command_pu))
        command = min(1.0, max(0.0, command))
        voltage = float(disturbance.get("ups_output_voltage_pu", 1.0))
        force_trip = bool(disturbance.get("force_trip", False))
        restart_request = bool(action.get("restart_request", False))
        tripped = state.tripped or force_trip or voltage <= self.config.undervoltage_trip_threshold_pu
        restart_timer = state.restart_timer_s
        if tripped:
            available = 0.0
            if restart_request and not force_trip and voltage > self.config.undervoltage_trip_threshold_pu:
                restart_timer = max(0.0, restart_timer - dt_s)
                if restart_timer == 0.0:
                    tripped = False
            else:
                restart_timer = self.config.restart_delay_s
        if not tripped:
            available = self.available_output(command, voltage)
            restart_timer = 0.0
        target_speed = self.config.nominal_motor_speed_rad_s * available
        unconstrained_rate = (target_speed - state.motor_speed_rad_s) / self.config.motor_time_constant_s
        bounded_rate = min(
            self.config.ramp_up_rate_rad_s2,
            max(-self.config.ramp_down_rate_rad_s2, unconstrained_rate),
        )
        motor_speed = state.motor_speed_rad_s + dt_s * bounded_rate
        motor_speed = min(
            self.config.nominal_motor_speed_rad_s * self.config.max_speed_ratio,
            max(0.0, motor_speed),
        )
        updated = DriveState(command, available, motor_speed, tripped, restart_timer)
        updated.validate(self.config)
        return updated
