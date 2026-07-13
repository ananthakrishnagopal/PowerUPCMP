"""Bounded open-loop utility-to-CMP chain runner for synthetic model datasets.

This is not the final WP17 controller runtime. It advances the already frozen
plant/CMP components in the canonical order, applies no supervisory action,
and exposes true rows separately from arrived sensor observations.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from enum import Enum
from typing import TYPE_CHECKING, Any

from semifab_poc.data.schema import LatentStateRecord, ObservationRecord
from semifab_poc.simulation.cmp import CmpHoldReason, CmpMode, CmpSubsystem
from semifab_poc.simulation.coupling import CouplingConfig, UtilityToCmpCoupler
from semifab_poc.simulation.drive import DriveSubsystem
from semifab_poc.simulation.electrical import ElectricalSubsystem
from semifab_poc.simulation.pump import PumpSubsystem
from semifab_poc.simulation.sensors import SensorConfig, SensorModel
from semifab_poc.simulation.upw import UpwSubsystem

if TYPE_CHECKING:
    from semifab_poc.config import RuntimeConfig


class ChainRunnerError(ValueError):
    """Raised when an open-loop chain scenario or schedule is invalid."""


class ChainEventKind(str, Enum):
    NORMAL = "NORMAL"
    HEALTHY_SAG = "HEALTHY_SAG"
    GRID_INTERRUPTION = "GRID_INTERRUPTION"
    PUMP_TRIP = "PUMP_TRIP"
    VALVE_RESTRICTION = "VALVE_RESTRICTION"
    TOOL_DEMAND_SPIKE = "TOOL_DEMAND_SPIKE"
    COMPOUND_INTERRUPTION_DEMAND = "COMPOUND_INTERRUPTION_DEMAND"


@dataclass(frozen=True)
class ChainScenario:
    run_id: str
    family: ChainEventKind
    seed: int
    event_start_s: float
    event_duration_s: float
    grid_voltage_pu: float = 1.0
    battery_capacity_j: float = 3_600_000.0
    ups_load_power_w: float = 2_500.0
    valve_position: float = 1.0
    tool_demand_m3_s: float = 1.0e-4

    def validate(self, runtime: RuntimeConfig, duration_s: float) -> None:
        if not self.run_id or self.seed < 0:
            raise ChainRunnerError("scenario run_id and seed must be valid")
        numeric = (
            self.event_start_s,
            self.event_duration_s,
            self.grid_voltage_pu,
            self.battery_capacity_j,
            self.ups_load_power_w,
            self.valve_position,
            self.tool_demand_m3_s,
        )
        if any(not math.isfinite(value) for value in numeric):
            raise ChainRunnerError("scenario numerical values must be finite")
        if self.event_start_s < 0.0 or self.event_duration_s < 0.0:
            raise ChainRunnerError("scenario event time and duration must be non-negative")
        if self.event_start_s + self.event_duration_s > duration_s + 1.0e-12:
            raise ChainRunnerError("scenario event exceeds run duration")
        if not runtime.electrical.voltage_min_pu <= self.grid_voltage_pu <= 1.0:
            raise ChainRunnerError("scenario grid voltage is outside the configured range")
        if self.battery_capacity_j <= 0.0 or self.ups_load_power_w < 0.0:
            raise ChainRunnerError("scenario battery/load values are invalid")
        if not 0.0 <= self.valve_position <= 1.0:
            raise ChainRunnerError("scenario valve position must be within [0, 1]")
        if not 0.0 <= self.tool_demand_m3_s <= runtime.upw.maximum_flow_m3_s:
            raise ChainRunnerError("scenario tool demand is outside the UPW envelope")


@dataclass(frozen=True)
class ChainSchedule:
    dt_s: float
    duration_s: float
    plant_warmup_s: float
    dress_end_s: float
    polish_start_s: float

    def validate(self, runtime: RuntimeConfig) -> None:
        values = (
            self.dt_s,
            self.duration_s,
            self.plant_warmup_s,
            self.dress_end_s,
            self.polish_start_s,
        )
        if any(not math.isfinite(value) for value in values):
            raise ChainRunnerError("schedule values must be finite")
        if self.dt_s <= 0.0 or self.duration_s <= 0.0 or self.plant_warmup_s < 0.0:
            raise ChainRunnerError("schedule timestep/durations are invalid")
        if not 0.0 < self.dress_end_s < self.polish_start_s < self.duration_s:
            raise ChainRunnerError("schedule must order DRESS, PREPARE, POLISH")
        if not math.isclose(self.dt_s, runtime.dt_s, rel_tol=0.0, abs_tol=1.0e-12):
            raise ChainRunnerError("chain schedule dt must match the frozen runtime dt")


@dataclass(frozen=True)
class ChainTrace:
    run_id: str
    family: str
    truth_rows: tuple[dict[str, Any], ...]
    observations: tuple[ObservationRecord, ...]


class SyntheticChainRunner:
    """Advance an uncontrolled declared-topology chain with causal sensing."""

    interface_version = "1.0.0"

    def __init__(
        self,
        runtime: RuntimeConfig,
        schedule: ChainSchedule,
        coupling_config: CouplingConfig,
        sensor_configs: tuple[SensorConfig, ...],
    ) -> None:
        schedule.validate(runtime)
        coupling_config.validate()
        if not sensor_configs:
            raise ChainRunnerError("chain runner requires at least one sensor")
        self.runtime = runtime
        self.schedule = schedule
        self.coupling_config = coupling_config
        self.sensor_configs = sensor_configs

    def _phase_action(self, source_time_s: float) -> dict[str, float | str]:
        if source_time_s < self.schedule.dress_end_s:
            return {"mode_request": "DRESS", "dresser_command": 1.0}
        if source_time_s < self.schedule.polish_start_s:
            return {"mode_request": "PREPARE"}
        return {"mode_request": "POLISH"}

    @staticmethod
    def _initial_cmp_state(model: CmpSubsystem):
        return replace(
            model.reset(),
            mode=CmpMode.DRESS,
            hold_reason=CmpHoldReason.NONE,
            pad_surface_activity=0.50,
            pad_remaining_life=0.90,
            dresser_effectiveness=0.90,
            dresser_command=1.0,
        )

    @staticmethod
    def _latent_records(
        run_id: str,
        step_index: int,
        timestamp_s: float,
        electrical_state: Any,
        drive_state: Any,
        pump_state: Any,
        upw_state: Any,
    ) -> tuple[LatentStateRecord, ...]:
        signals = (
            ("electrical.grid_voltage", electrical_state.grid_voltage_pu, "pu", "electrical"),
            (
                "electrical.ups_output_voltage",
                electrical_state.ups_output_voltage_pu,
                "pu",
                "electrical",
            ),
            (
                "electrical.ups_battery_energy",
                electrical_state.battery_energy_j,
                "J",
                "electrical",
            ),
            ("drive.motor_angular_speed", drive_state.motor_speed_rad_s, "rad/s", "drive"),
            ("pump.volumetric_flow", pump_state.volumetric_flow_m3_s, "m^3/s", "pump"),
            ("upw.supply_pressure", upw_state.supply_pressure_pa, "Pa", "upw"),
            ("upw.tool_flow", upw_state.tool_flow_m3_s, "m^3/s", "upw"),
            ("upw.temperature", upw_state.temperature_k, "K", "upw"),
        )
        return tuple(
            LatentStateRecord(
                run_id=run_id,
                step_index=step_index,
                timestamp_s=timestamp_s,
                signal_id=signal_id,
                value=value,
                unit=unit,
                subsystem=subsystem,
                provenance_id="synthetic-chain-warning-v1",
            )
            for signal_id, value, unit, subsystem in signals
        )

    def run(self, scenario: ChainScenario) -> ChainTrace:
        scenario.validate(self.runtime, self.schedule.duration_s)
        electrical_config = replace(
            self.runtime.electrical,
            battery_capacity_j=scenario.battery_capacity_j,
            initial_battery_energy_j=scenario.battery_capacity_j,
        )
        electrical = ElectricalSubsystem(electrical_config)
        drive = DriveSubsystem(self.runtime.drive)
        pump = PumpSubsystem(self.runtime.pump)
        upw = UpwSubsystem(self.runtime.upw)
        cmp = CmpSubsystem(self.runtime.cmp)
        coupler = UtilityToCmpCoupler(
            self.coupling_config,
            self.runtime.upw,
            self.runtime.cmp,
        )
        sensor = SensorModel(scenario.run_id, self.sensor_configs)
        sensor.reset(scenario.seed)

        electrical_state = electrical.reset()
        drive_state = drive.reset()
        pump_state = pump.reset()
        upw_state = upw.reset()
        cmp_state = self._initial_cmp_state(cmp)

        for _ in range(round(self.schedule.plant_warmup_s / self.schedule.dt_s)):
            electrical_state = electrical.step(
                electrical_state,
                None,
                {"grid_voltage_pu": 1.0, "ups_load_power_w": scenario.ups_load_power_w},
                self.schedule.dt_s,
            )
            drive_state = drive.step(
                drive_state,
                {"vfd_command_pu": 1.0, "restart_request": True},
                {"ups_output_voltage_pu": electrical_state.ups_output_voltage_pu},
                self.schedule.dt_s,
            )
            pump_state = pump.step(
                pump_state,
                None,
                {
                    "motor_speed_rad_s": drive_state.motor_speed_rad_s,
                    "system_differential_pressure_pa": (
                        upw_state.supply_pressure_pa - upw_state.return_pressure_pa
                    ),
                },
                self.schedule.dt_s,
            )
            upw_state = upw.step(
                upw_state,
                {"valve_position": 1.0},
                {"pump_flow_m3_s": pump_state.volumetric_flow_m3_s},
                self.schedule.dt_s,
            )

        truth_rows: list[dict[str, Any]] = []
        observations: list[ObservationRecord] = []
        steps = round(self.schedule.duration_s / self.schedule.dt_s)
        for zero_index in range(steps):
            source_time_s = zero_index * self.schedule.dt_s
            timestamp_s = (zero_index + 1) * self.schedule.dt_s
            step_index = zero_index + 1
            event_active = (
                scenario.event_start_s
                <= source_time_s
                < scenario.event_start_s + scenario.event_duration_s
            )
            electrical_disturbance: dict[str, float | bool] = {
                "grid_voltage_pu": 1.0,
                "ups_load_power_w": scenario.ups_load_power_w,
            }
            drive_disturbance: dict[str, float | bool] = {}
            upw_action: dict[str, float] = {"valve_position": 1.0}
            upw_disturbance: dict[str, float] = {}
            if event_active:
                if scenario.family is ChainEventKind.HEALTHY_SAG:
                    electrical_disturbance["grid_voltage_pu"] = scenario.grid_voltage_pu
                elif scenario.family in {
                    ChainEventKind.GRID_INTERRUPTION,
                    ChainEventKind.COMPOUND_INTERRUPTION_DEMAND,
                }:
                    electrical_disturbance["force_interruption"] = True
                if scenario.family is ChainEventKind.PUMP_TRIP:
                    drive_disturbance["force_trip"] = True
                if scenario.family is ChainEventKind.VALVE_RESTRICTION:
                    upw_action["valve_position"] = scenario.valve_position
                if scenario.family in {
                    ChainEventKind.TOOL_DEMAND_SPIKE,
                    ChainEventKind.COMPOUND_INTERRUPTION_DEMAND,
                }:
                    upw_disturbance["tool_demand_m3_s"] = scenario.tool_demand_m3_s

            electrical_state = electrical.step(
                electrical_state,
                None,
                electrical_disturbance,
                self.schedule.dt_s,
            )
            drive_disturbance["ups_output_voltage_pu"] = electrical_state.ups_output_voltage_pu
            drive_state = drive.step(
                drive_state,
                {"vfd_command_pu": 1.0, "restart_request": True},
                drive_disturbance,
                self.schedule.dt_s,
            )
            pump_state = pump.step(
                pump_state,
                None,
                {
                    "motor_speed_rad_s": drive_state.motor_speed_rad_s,
                    "system_differential_pressure_pa": (
                        upw_state.supply_pressure_pa - upw_state.return_pressure_pa
                    ),
                },
                self.schedule.dt_s,
            )
            upw_disturbance["pump_flow_m3_s"] = pump_state.volumetric_flow_m3_s
            upw_state = upw.step(
                upw_state,
                upw_action,
                upw_disturbance,
                self.schedule.dt_s,
            )
            coupling = coupler.couple(upw_state)
            cmp_state = cmp.step(
                cmp_state,
                self._phase_action(source_time_s),
                coupling.boundary.as_mapping(),
                self.schedule.dt_s,
            )
            observations.extend(
                sensor.sample(
                    self._latent_records(
                        scenario.run_id,
                        step_index,
                        timestamp_s,
                        electrical_state,
                        drive_state,
                        pump_state,
                        upw_state,
                    ),
                    step_index,
                    timestamp_s,
                )
            )
            truth_rows.append(
                {
                    "run_id": scenario.run_id,
                    "family": scenario.family.value,
                    "step_index": step_index,
                    "source_time_s": source_time_s,
                    "timestamp_s": timestamp_s,
                    "event_active": event_active,
                    "grid_voltage_pu": electrical_state.grid_voltage_pu,
                    "ups_output_voltage_pu": electrical_state.ups_output_voltage_pu,
                    "battery_energy_j": electrical_state.battery_energy_j,
                    "motor_speed_rad_s": drive_state.motor_speed_rad_s,
                    "pump_flow_m3_s": pump_state.volumetric_flow_m3_s,
                    "upw_supply_pressure_pa": upw_state.supply_pressure_pa,
                    "upw_tool_flow_m3_s": upw_state.tool_flow_m3_s,
                    "upw_temperature_k": upw_state.temperature_k,
                    "effective_availability": coupling.effective_availability,
                    "cmp_mode": cmp_state.mode.value,
                    "cmp_pad_surface_activity": cmp_state.pad_surface_activity,
                    "cmp_mrr_m_s": cmp_state.instantaneous_mrr_m_s,
                    "cmp_cumulative_removal_m": cmp_state.cumulative_removal_m,
                }
            )
        return ChainTrace(
            run_id=scenario.run_id,
            family=scenario.family.value,
            truth_rows=tuple(truth_rows),
            observations=tuple(observations),
        )
