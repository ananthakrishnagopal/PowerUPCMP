"""Integrated WP17 Plant and Controller Runtime.

Executes the frozen 15-step simulator update order, integrating the causal 
plant components, sensors, early warning predictor, root-cause attribution,
predictive supervisory control, and independent safety filter.
"""

from __future__ import annotations

import math
import uuid
from dataclasses import dataclass, replace
from typing import Any, Mapping

from semifab_poc.config import RuntimeConfig
from semifab_poc.control.base import ActionRecord, Controller, SafetyDecisionRecord, SafetyFilter
from semifab_poc.control.contracts import ActionType, SafetyOutcome
from semifab_poc.data.schema import LatentStateRecord, ObservationRecord, RootCause
from semifab_poc.models.attribution import Attribution, AttributionObservationWindow, RootCauseEstimator
from semifab_poc.models.early_warning import (
    EarlyWarningPredictor,
    Prediction,
    WarningObservationWindow,
    normalization_for_warning_runtime,
)
from semifab_poc.simulation.chain import ChainEventKind, ChainScenario, ChainSchedule, ChainRunnerError
from semifab_poc.simulation.cmp import CmpHoldReason, CmpMode, CmpSubsystem
from semifab_poc.simulation.coupling import CouplingConfig, UtilityToCmpCoupler
from semifab_poc.simulation.drive import DriveSubsystem
from semifab_poc.simulation.electrical import ElectricalSubsystem
from semifab_poc.simulation.pump import PumpSubsystem
from semifab_poc.simulation.sensors import SensorModel
from semifab_poc.simulation.upw import UpwSubsystem


@dataclass(frozen=True)
class IntegratedTrace:
    run_id: str
    family: str
    truth_rows: tuple[dict[str, Any], ...]
    observations: tuple[ObservationRecord, ...]
    predictions: tuple[Prediction, ...]
    attributions: tuple[Attribution, ...]
    actions: tuple[ActionRecord, ...]
    safety_decisions: tuple[SafetyDecisionRecord, ...]


class IntegratedRuntime:
    """15-step integrated simulator and controller runtime."""

    interface_version = "1.0.0"

    def __init__(
        self,
        runtime: RuntimeConfig,
        schedule: ChainSchedule,
        coupling_config: CouplingConfig,
        predictor: EarlyWarningPredictor,
        estimator: RootCauseEstimator,
        controller: Controller,
        safety_filter: SafetyFilter,
    ) -> None:
        schedule.validate(runtime)
        coupling_config.validate()
        if not runtime.sensors:
            raise ChainRunnerError("runtime requires at least one sensor")
        self.runtime = runtime
        self.schedule = schedule
        self.coupling_config = coupling_config
        self.predictor = predictor
        self.estimator = estimator
        self.controller = controller
        self.safety_filter = safety_filter

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
            ("electrical.grid_frequency", electrical_state.grid_frequency_hz, "Hz", "electrical"),
            ("electrical.ups_output_voltage", electrical_state.ups_output_voltage_pu, "pu", "electrical"),
            ("electrical.ups_output_frequency", electrical_state.ups_output_frequency_hz, "Hz", "electrical"),
            ("electrical.ups_battery_energy", electrical_state.battery_energy_j, "J", "electrical"),
            ("drive.vfd_available_output", drive_state.vfd_available_output_pu, "pu", "drive"),
            ("drive.vfd_trip_state", drive_state.tripped, "1", "drive"),
            ("drive.motor_angular_speed", drive_state.motor_speed_rad_s, "rad/s", "drive"),
            ("pump.volumetric_flow", pump_state.volumetric_flow_m3_s, "m^3/s", "pump"),
            ("upw.supply_pressure", upw_state.supply_pressure_pa, "Pa", "upw"),
            ("upw.tool_flow", upw_state.tool_flow_m3_s, "m^3/s", "upw"),
            ("upw.valve_position", upw_state.valve_position, "1", "upw"),
            ("upw.tool_demand", upw_state.tool_demand_m3_s, "m^3/s", "upw"),
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
                provenance_id="integrated-runtime-v1",
            )
            for signal_id, value, unit, subsystem in signals
        )

    def _apply_observation_faults(
        self,
        records: tuple[ObservationRecord, ...],
        scenario: ChainScenario,
    ) -> tuple[ObservationRecord, ...]:
        changed: list[ObservationRecord] = []
        for record in records:
            source_timestamp_s = record.source_timestamp_s
            if source_timestamp_s is None:
                changed.append(record)
                continue
            source_time_s = max(0.0, source_timestamp_s - self.schedule.dt_s)
            fault_active = (
                scenario.event_start_s
                <= source_time_s
                < scenario.event_start_s + scenario.event_duration_s
            )
            if not fault_active or not isinstance(record.value, (int, float)):
                changed.append(record)
                continue
            value = float(record.value)
            if (
                scenario.family is ChainEventKind.PRESSURE_SENSOR_FAULT
                and record.signal_id == "upw.supply_pressure"
            ):
                value = min(
                    self.runtime.upw.maximum_supply_pressure_pa,
                    max(0.0, value + scenario.pressure_sensor_bias_pa),
                )
            elif (
                scenario.family is ChainEventKind.FLOW_SENSOR_FAULT
                and record.signal_id == "upw.tool_flow"
            ):
                value = min(
                    self.runtime.upw.maximum_flow_m3_s,
                    max(0.0, value + scenario.flow_sensor_bias_m3_s),
                )
            else:
                changed.append(record)
                continue
            payload = record.model_dump()
            payload["value"] = value
            changed.append(ObservationRecord.model_validate(payload))
        return tuple(changed)

    def run(self, scenario: ChainScenario) -> IntegratedTrace:
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
        sensor = SensorModel(scenario.run_id, self.runtime.sensors)
        sensor.reset(scenario.seed)

        self.controller.reset()
        self.safety_filter.reset()

        electrical_state = electrical.reset()
        drive_state = drive.reset()
        pump_state = pump.reset()
        upw_state = upw.reset()
        cmp_state = self._initial_cmp_state(cmp)

        # Plant Warmup (Open Loop)
        for _ in range(round(self.schedule.plant_warmup_s / self.schedule.dt_s)):
            electrical_state = electrical.step(
                electrical_state, None, {"grid_voltage_pu": 1.0, "ups_load_power_w": scenario.ups_load_power_w}, self.schedule.dt_s
            )
            drive_state = drive.step(
                drive_state, {"vfd_command_pu": 1.0, "restart_request": True}, {"ups_output_voltage_pu": electrical_state.ups_output_voltage_pu}, self.schedule.dt_s
            )
            pump_state = pump.step(
                pump_state, None, {"motor_speed_rad_s": drive_state.motor_speed_rad_s, "system_differential_pressure_pa": upw_state.supply_pressure_pa - upw_state.return_pressure_pa}, self.schedule.dt_s
            )
            upw_state = upw.step(
                upw_state, {"valve_position": 1.0}, {"pump_flow_m3_s": pump_state.volumetric_flow_m3_s}, self.schedule.dt_s
            )

        truth_rows: list[dict[str, Any]] = []
        all_observations: list[ObservationRecord] = []
        predictions: list[Prediction] = []
        attributions: list[Attribution] = []
        actions: list[ActionRecord] = []
        safety_decisions: list[SafetyDecisionRecord] = []

        active_observations: list[ObservationRecord] = []
        final_action = None

        steps = round(self.schedule.duration_s / self.schedule.dt_s)
        for zero_index in range(steps):
            source_time_s = zero_index * self.schedule.dt_s
            timestamp_s = (zero_index + 1) * self.schedule.dt_s
            step_index = zero_index + 1
            
            # Step 1: Read deterministic scenario events for the current time
            event_active = (
                scenario.event_start_s
                <= source_time_s
                < scenario.event_start_s + scenario.event_duration_s
            )
            electrical_disturbance: dict[str, float | bool] = {
                "grid_voltage_pu": 1.0,
                "grid_frequency_hz": self.runtime.electrical.nominal_frequency_hz,
                "ups_load_power_w": scenario.ups_load_power_w,
            }
            drive_disturbance: dict[str, float | bool] = {}
            upw_disturbance: dict[str, float] = {}
            
            # Apply programmed scenario event
            if event_active:
                if scenario.family in {ChainEventKind.HEALTHY_SAG, ChainEventKind.GRID_VOLTAGE_SAG, ChainEventKind.GRID_VOLTAGE_SWELL}:
                    electrical_disturbance["grid_voltage_pu"] = scenario.grid_voltage_pu
                elif scenario.family in {ChainEventKind.GRID_INTERRUPTION, ChainEventKind.COMPOUND_INTERRUPTION_DEMAND}:
                    electrical_disturbance["force_interruption"] = True
                if scenario.family is ChainEventKind.GRID_FREQUENCY_DEVIATION:
                    electrical_disturbance["grid_frequency_hz"] = scenario.grid_frequency_hz
                if scenario.family is ChainEventKind.PUMP_TRIP:
                    drive_disturbance["force_trip"] = True
                if scenario.family in {ChainEventKind.TOOL_DEMAND_SPIKE, ChainEventKind.COMPOUND_INTERRUPTION_DEMAND}:
                    upw_disturbance["tool_demand_m3_s"] = scenario.tool_demand_m3_s
                if scenario.family is ChainEventKind.THERMAL_EXCURSION:
                    upw_disturbance["inlet_temperature_k"] = scenario.inlet_temperature_k

            # Action Application from Step 14
            upw_action: dict[str, float] = {"valve_position": 1.0}
            if event_active and scenario.family is ChainEventKind.VALVE_RESTRICTION:
                upw_action["valve_position"] = scenario.valve_position

            drive_action = {"vfd_command_pu": 1.0, "restart_request": True}
            cmp_action: dict[str, float | str] = {}
            
            # Open-loop base phase schedule
            if source_time_s < self.schedule.dress_end_s:
                cmp_action = {"mode_request": "DRESS", "dresser_command": 1.0}
            elif source_time_s < self.schedule.polish_start_s:
                cmp_action = {"mode_request": "PREPARE"}
            else:
                cmp_action = {"mode_request": "POLISH"}

            # Apply final action from previous step if any
            if final_action is not None and final_action.action_type != ActionType.NO_ACTION:
                if final_action.action_type == ActionType.SAFE_HOLD:
                    cmp_action["mode_request"] = "HOLD"
                elif final_action.action_type == ActionType.CONTROLLED_RESUME:
                    cmp_action["mode_request"] = "RECOVER"
                elif final_action.action_type == ActionType.VALVE_ADJUSTMENT and final_action.value is not None:
                    upw_action["valve_position"] = final_action.value
                elif final_action.action_type == ActionType.VFD_COMMAND_ADJUSTMENT and final_action.value is not None:
                    drive_action["vfd_command_pu"] = final_action.value
                elif final_action.action_type == ActionType.CMP_DOWNFORCE_REDUCTION and final_action.value is not None:
                    cmp_action["downforce_reduction"] = final_action.value
                elif final_action.action_type == ActionType.HEAD_SPEED_REDUCTION and final_action.value is not None:
                    cmp_action["head_speed_reduction"] = final_action.value
                elif final_action.action_type == ActionType.PLATEN_SPEED_REDUCTION and final_action.value is not None:
                    cmp_action["platen_speed_reduction"] = final_action.value

            if (
                cmp_state.mode is CmpMode.RECOVER
                and cmp_action.get("mode_request") == "DRESS"
            ):
                cmp_action["mode_request"] = "PREPARE"
            elif (
                cmp_state.mode is CmpMode.HOLD
                and cmp_action.get("mode_request") not in {"HOLD", "RECOVER", "COMPLETE"}
            ):
                cmp_action["mode_request"] = "HOLD"

            # Step 2: Update electrical and UPS latent state
            electrical_state = electrical.step(
                electrical_state, None, electrical_disturbance, self.schedule.dt_s
            )

            # Step 3: Update VFD and motor latent state
            drive_disturbance["ups_output_voltage_pu"] = electrical_state.ups_output_voltage_pu
            drive_state = drive.step(
                drive_state, drive_action, drive_disturbance, self.schedule.dt_s
            )

            # Step 4: Update pump latent state
            pump_state = pump.step(
                pump_state, None, {
                    "motor_speed_rad_s": drive_state.motor_speed_rad_s,
                    "system_differential_pressure_pa": upw_state.supply_pressure_pa - upw_state.return_pressure_pa
                }, self.schedule.dt_s
            )

            # Step 5: Update UPW hydraulic and thermal latent state
            upw_disturbance["pump_flow_m3_s"] = pump_state.volumetric_flow_m3_s
            upw_state = upw.step(
                upw_state, upw_action, upw_disturbance, self.schedule.dt_s
            )

            # Step 6: Compute typed utility-to-CMP boundary conditions
            coupling = coupler.couple(upw_state)

            # Step 7: Update true CMP state and true simulated MRR
            cmp_state = cmp.step(
                cmp_state, cmp_action, coupling.boundary.as_mapping(), self.schedule.dt_s
            )

            # Step 8: Generate observed signals from latent state
            latent_records = self._latent_records(
                scenario.run_id, step_index, timestamp_s, electrical_state, drive_state, pump_state, upw_state
            )
            raw_observations = sensor.sample(latent_records, step_index, timestamp_s)
            faulted_observations = self._apply_observation_faults(raw_observations, scenario)
            all_observations.extend(faulted_observations)
            active_observations.extend(faulted_observations)
            
            # Prune observations to keep only those that have arrived by decision_timestamp
            arrived_observations = tuple(
                obs for obs in active_observations
                if obs.arrival_timestamp_s <= timestamp_s + 1.0e-12
            )
            # Remove observations that are too old to save memory, keeping at least 3 seconds of history
            active_observations = [
                obs for obs in active_observations
                if (timestamp_s - obs.arrival_timestamp_s) <= 3.0
            ]

            # Prepare decision window
            warning_window = WarningObservationWindow(
                run_id=scenario.run_id,
                decision_step_index=step_index,
                decision_timestamp_s=timestamp_s,
                observations=arrived_observations,
                process_mode=cmp_state.mode.value,
                polish_start_s=self.schedule.polish_start_s,
                normalization_by_signal=(
                    normalization_for_warning_runtime(
                        scenario_battery_capacity_j=scenario.battery_capacity_j,
                        runtime=self.runtime,
                    )
                    if self.predictor is not None
                    else {}
                ),
                sensor_sample_period_s=self.runtime.sensors[0].sample_period_s,
                battery_capacity_ratio=electrical_state.battery_energy_j / electrical_config.battery_capacity_j,
                ups_load_ratio=scenario.ups_load_power_w / self.runtime.electrical.ups_rated_power_w,
            )

            # Step 9: Update streaming features & Step 10: Predict MRR
            prediction = None
            if self.predictor is not None:
                prediction = self.predictor.predict(warning_window)
                predictions.append(prediction)

            # Step 11: Estimate the initiating cause
            attribution = None
            if self.estimator is not None and prediction is not None:
                attribution_window = AttributionObservationWindow(
                    run_id=scenario.run_id,
                    decision_step_index=step_index,
                    decision_timestamp_s=timestamp_s,
                    observations=arrived_observations,
                )
                attribution = self.estimator.estimate(attribution_window, prediction)
                attributions.append(attribution)

            # Step 12: Ask the selected controller for a proposed action
            proposed_action = self.controller.act(
                observation=warning_window,
                prediction=prediction,
                constraints=None
            )
            actions.append(proposed_action)

            # Step 13: Validate the proposal with the independent safety filter
            safety_decision = self.safety_filter.validate(
                proposed_action=proposed_action,
                observation=warning_window,
                uncertainty=prediction,
                constraints=None
            )
            safety_decisions.append(safety_decision)

            # Step 14: Store the approved/replaced action for application at the next actuation boundary
            final_action = self.safety_filter.last_action

            # Step 15: Log events, true state, observed state
            truth_rows.append(
                {
                    "run_id": scenario.run_id,
                    "family": scenario.family.value,
                    "step_index": step_index,
                    "source_time_s": source_time_s,
                    "timestamp_s": timestamp_s,
                    "event_active": event_active,
                    "grid_voltage_pu": electrical_state.grid_voltage_pu,
                    "grid_frequency_hz": electrical_state.grid_frequency_hz,
                    "ups_output_voltage_pu": electrical_state.ups_output_voltage_pu,
                    "ups_output_frequency_hz": electrical_state.ups_output_frequency_hz,
                    "battery_energy_j": electrical_state.battery_energy_j,
                    "vfd_available_output_pu": drive_state.vfd_available_output_pu,
                    "vfd_tripped": drive_state.tripped,
                    "motor_speed_rad_s": drive_state.motor_speed_rad_s,
                    "pump_flow_m3_s": pump_state.volumetric_flow_m3_s,
                    "upw_supply_pressure_pa": upw_state.supply_pressure_pa,
                    "upw_tool_flow_m3_s": upw_state.tool_flow_m3_s,
                    "upw_valve_position": upw_state.valve_position,
                    "upw_tool_demand_m3_s": upw_state.tool_demand_m3_s,
                    "upw_temperature_k": upw_state.temperature_k,
                    "effective_availability": coupling.effective_availability,
                    "cmp_mode": cmp_state.mode.value,
                    "cmp_pad_surface_activity": cmp_state.pad_surface_activity,
                    "cmp_mrr_m_s": cmp_state.instantaneous_mrr_m_s,
                    "cmp_cumulative_removal_m": cmp_state.cumulative_removal_m,
                }
            )

        return IntegratedTrace(
            run_id=scenario.run_id,
            family=scenario.family.value,
            truth_rows=tuple(truth_rows),
            observations=tuple(all_observations),
            predictions=tuple(predictions),
            attributions=tuple(attributions),
            actions=tuple(actions),
            safety_decisions=tuple(safety_decisions),
        )
