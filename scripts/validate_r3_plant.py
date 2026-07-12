#!/usr/bin/env python3
"""Generate deterministic R3 utility-plant validation evidence."""

from __future__ import annotations

import csv
import json
import math
from dataclasses import asdict
from pathlib import Path

from semifab_poc.config import load_runtime_config, runtime_config_sha256
from semifab_poc.simulation.drive import DriveSubsystem
from semifab_poc.simulation.electrical import ElectricalConfig, ElectricalSubsystem, UpsMode
from semifab_poc.simulation.pump import PumpSubsystem
from semifab_poc.simulation.upw import UpwSubsystem


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "reports" / "plant"


def coupled_speed_step(dt_s: float, duration_s: float = 0.5) -> float:
    pump = PumpSubsystem()
    upw = UpwSubsystem()
    pump_state = pump.reset()
    upw_state = upw.reset()
    motor_speed = 0.70 * pump.config.reference_motor_speed_rad_s
    for _ in range(round(duration_s / dt_s)):
        pump_state = pump.step(
            pump_state,
            None,
            {
                "motor_speed_rad_s": motor_speed,
                "system_differential_pressure_pa": (
                    upw_state.supply_pressure_pa - upw_state.return_pressure_pa
                ),
            },
            dt_s,
        )
        upw_state = upw.step(
            upw_state,
            None,
            {"pump_flow_m3_s": pump_state.volumetric_flow_m3_s},
            dt_s,
        )
    return upw_state.supply_pressure_pa


def pump_evidence() -> dict[str, object]:
    pump = PumpSubsystem()
    reference_power = pump.config.reference_power_w
    homologous = []
    for ratio in (0.25, 0.5, 0.75, 1.0, 1.2):
        state = pump.from_motor_speed(ratio * pump.config.reference_motor_speed_rad_s)
        homologous.append(
            {
                "speed_ratio": ratio,
                "flow_m3_s": state.volumetric_flow_m3_s,
                "head_pa": state.head_pa,
                "shaft_power_w": state.power_w,
                "flow_ratio_error": state.volumetric_flow_m3_s
                / pump.config.reference_flow_m3_s
                - ratio,
                "head_ratio_error": state.head_pa / pump.config.reference_head_pa
                - ratio**2,
                "power_ratio_error": state.power_w / reference_power - ratio**3,
                "operating_point_residual_pa": state.operating_point_residual_pa,
            }
        )

    pressure_sweep = []
    for differential_pressure in (0.0, 100_000.0, 200_000.0, 300_000.0, 400_001.0):
        state = pump.operating_point(
            pump.config.reference_motor_speed_rad_s,
            differential_pressure,
        )
        pressure_sweep.append(
            {
                "differential_pressure_pa": differential_pressure,
                "flow_m3_s": state.volumetric_flow_m3_s,
                "check_valve_closed": state.check_valve_closed,
                "curve_head_pa": state.head_pa,
                "operating_point_residual_pa": state.operating_point_residual_pa,
            }
        )
    return {
        "config": asdict(pump.config),
        "curve_coefficient_pa_s2_m6": pump.config.curve_coefficient_pa_s2_m6,
        "reference_power_w": reference_power,
        "homologous_points": homologous,
        "network_pressure_sweep": pressure_sweep,
    }


def hydraulic_evidence(dt_s: float) -> dict[str, object]:
    upw = UpwSubsystem()
    nominal = upw.reset()
    nominal_next = upw.step(nominal, None, None, dt_s)

    trip_state = nominal
    trip_pressures = [trip_state.supply_pressure_pa]
    trip_max_residual = 0.0
    for _ in range(round(1.0 / dt_s)):
        trip_state = upw.step(trip_state, None, {"pump_flow_m3_s": 0.0}, dt_s)
        trip_pressures.append(trip_state.supply_pressure_pa)
        trip_max_residual = max(
            trip_max_residual,
            abs(trip_state.mass_balance_residual_m3_s),
        )

    relief_state = nominal
    relief_max_residual = 0.0
    for _ in range(round(2.0 / dt_s)):
        relief_state = upw.step(
            relief_state,
            {"valve_position": 0.0},
            {"pump_flow_m3_s": 3.0e-4, "tool_demand_m3_s": 0.0},
            dt_s,
        )
        relief_max_residual = max(
            relief_max_residual,
            abs(relief_state.mass_balance_residual_m3_s),
        )

    dts = (0.02, 0.01, 0.005, 0.0025, 0.001)
    reference_dt = 0.0005
    reference_pressure = coupled_speed_step(reference_dt)
    convergence = [
        {
            "dt_s": step,
            "final_supply_pressure_pa": (pressure := coupled_speed_step(step)),
            "absolute_error_vs_0_5_ms_pa": abs(pressure - reference_pressure),
            "relative_error_vs_nominal": abs(pressure - reference_pressure)
            / upw.config.nominal_supply_pressure_pa,
        }
        for step in dts
    ]
    return {
        "config": asdict(upw.config),
        "nominal": {
            "state": asdict(nominal),
            "next_state": asdict(nominal_next),
            "pressure_change_pa": (
                nominal_next.supply_pressure_pa - nominal.supply_pressure_pa
            ),
        },
        "pump_trip": {
            "duration_s": 1.0,
            "first_step_pressure_pa": trip_pressures[1],
            "final_pressure_pa": trip_pressures[-1],
            "monotone_nonincreasing": all(
                right <= left + 1.0e-9
                for left, right in zip(trip_pressures, trip_pressures[1:])
            ),
            "maximum_mass_balance_residual_m3_s": trip_max_residual,
        },
        "relief_case": {
            "duration_s": 2.0,
            "final_state": asdict(relief_state),
            "relief_active": relief_state.relief_flow_m3_s > 0.0,
            "maximum_mass_balance_residual_m3_s": relief_max_residual,
        },
        "timestep_convergence": {
            "disturbance": "instantaneous motor-speed boundary from 1.0 to 0.70 pu",
            "duration_s": 0.5,
            "reference_dt_s": reference_dt,
            "reference_final_supply_pressure_pa": reference_pressure,
            "results": convergence,
        },
    }


def electrical_evidence(dt_s: float) -> dict[str, object]:
    model = ElectricalSubsystem()
    state = model.reset()
    initial_energy = state.battery_energy_j
    for _ in range(round(0.4 / dt_s)):
        state = model.step(
            state,
            None,
            {"grid_voltage_pu": 0.75, "ups_load_power_w": 2_500.0},
            dt_s,
        )
    sag_end = state

    depleted_model = ElectricalSubsystem(
        ElectricalConfig(
            battery_capacity_j=100.0,
            initial_battery_energy_j=100.0,
            nominal_ups_load_w=2_500.0,
        )
    )
    depleted_state = depleted_model.reset()
    depletion_step = None
    for index in range(20):
        depleted_state = depleted_model.step(
            depleted_state,
            None,
            {"grid_voltage_pu": 0.75, "ups_load_power_w": 2_500.0},
            dt_s,
        )
        if depleted_state.ups_mode is UpsMode.BYPASS:
            depletion_step = index + 1
            break

    frequency_state = model.step(
        model.reset(),
        None,
        {"grid_frequency_hz": 49.0},
        dt_s,
    )
    return {
        "config": asdict(model.config),
        "healthy_sag_energy": {
            "duration_s": 0.4,
            "load_power_w": 2_500.0,
            "initial_energy_j": initial_energy,
            "final_energy_j": sag_end.battery_energy_j,
            "energy_used_j": initial_energy - sag_end.battery_energy_j,
            "final_mode": sag_end.ups_mode.value,
        },
        "depletion": {
            "initial_energy_j": 100.0,
            "depletion_step": depletion_step,
            "depletion_time_upper_bound_s": (
                None if depletion_step is None else depletion_step * dt_s
            ),
            "final_mode": depleted_state.ups_mode.value,
            "final_energy_j": depleted_state.battery_energy_j,
        },
        "frequency_step": {
            "grid_frequency_hz": frequency_state.grid_frequency_hz,
            "ups_output_frequency_hz": frequency_state.ups_output_frequency_hz,
        },
    }


def reference_chain(dt_s: float) -> tuple[dict[str, object], list[dict[str, object]]]:
    electrical = ElectricalSubsystem()
    drive = DriveSubsystem()
    pump = PumpSubsystem()
    upw = UpwSubsystem()
    electrical_state = electrical.reset()
    drive_state = drive.reset()
    pump_state = pump.reset()
    upw_state = upw.reset()

    warmup_s = 3.0
    sag_duration_s = 0.4
    recovery_observation_s = 1.0
    total_s = warmup_s + sag_duration_s + recovery_observation_s
    rows: list[dict[str, object]] = []
    for step in range(round(total_s / dt_s)):
        time_s = step * dt_s
        sag_active = warmup_s <= time_s < warmup_s + sag_duration_s
        electrical_state = electrical.step(
            electrical_state,
            None,
            {
                "grid_voltage_pu": 0.75 if sag_active else 1.0,
                "ups_load_power_w": electrical.config.nominal_ups_load_w,
            },
            dt_s,
        )
        drive_state = drive.step(
            drive_state,
            {"vfd_command_pu": 1.0},
            {"ups_output_voltage_pu": electrical_state.ups_output_voltage_pu},
            dt_s,
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
            dt_s,
        )
        upw_state = upw.step(
            upw_state,
            None,
            {"pump_flow_m3_s": pump_state.volumetric_flow_m3_s},
            dt_s,
        )
        rows.append(
            {
                "step_index": step,
                "time_s": time_s,
                "sag_active": sag_active,
                "grid_voltage_pu": electrical_state.grid_voltage_pu,
                "ups_output_voltage_pu": electrical_state.ups_output_voltage_pu,
                "ups_mode": electrical_state.ups_mode.value,
                "battery_energy_j": electrical_state.battery_energy_j,
                "motor_speed_rad_s": drive_state.motor_speed_rad_s,
                "pump_flow_m3_s": pump_state.volumetric_flow_m3_s,
                "pump_head_pa": pump_state.head_pa,
                "pump_operating_point_residual_pa": pump_state.operating_point_residual_pa,
                "upw_supply_pressure_pa": upw_state.supply_pressure_pa,
                "upw_tool_flow_m3_s": upw_state.tool_flow_m3_s,
                "upw_relief_flow_m3_s": upw_state.relief_flow_m3_s,
                "upw_mass_balance_residual_m3_s": upw_state.mass_balance_residual_m3_s,
            }
        )

    baseline_rows = [
        row for row in rows if warmup_s - 0.1 <= float(row["time_s"]) < warmup_s
    ]
    response_rows = [row for row in rows if float(row["time_s"]) >= warmup_s]

    def mean(key: str, selected: list[dict[str, object]]) -> float:
        return sum(float(row[key]) for row in selected) / len(selected)

    baseline_pressure = mean("upw_supply_pressure_pa", baseline_rows)
    baseline_flow = mean("upw_tool_flow_m3_s", baseline_rows)
    summary = {
        "scenario": "healthy UPS; 25 percent voltage sag for 400 ms",
        "interpretation": "synthetic negative control; no CMP connection applied",
        "dt_s": dt_s,
        "warmup_s": warmup_s,
        "baseline_supply_pressure_pa": baseline_pressure,
        "minimum_supply_pressure_pa_after_sag_start": min(
            float(row["upw_supply_pressure_pa"]) for row in response_rows
        ),
        "maximum_absolute_pressure_deviation_pa": max(
            abs(float(row["upw_supply_pressure_pa"]) - baseline_pressure)
            for row in response_rows
        ),
        "baseline_tool_flow_m3_s": baseline_flow,
        "minimum_tool_flow_m3_s_after_sag_start": min(
            float(row["upw_tool_flow_m3_s"]) for row in response_rows
        ),
        "minimum_ups_output_voltage_pu": min(
            float(row["ups_output_voltage_pu"]) for row in response_rows
        ),
        "minimum_motor_speed_rad_s": min(
            float(row["motor_speed_rad_s"]) for row in response_rows
        ),
        "maximum_pump_curve_residual_pa": max(
            abs(float(row["pump_operating_point_residual_pa"]))
            for row in response_rows
        ),
        "maximum_hydraulic_mass_balance_residual_m3_s": max(
            abs(float(row["upw_mass_balance_residual_m3_s"]))
            for row in response_rows
        ),
        "modes_observed": sorted({str(row["ups_mode"]) for row in response_rows}),
        "cmp_or_mrr_effect_applied": False,
    }
    return summary, rows


def write_csv_atomic(path: Path, rows: list[dict[str, object]]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def main() -> int:
    config = load_runtime_config(ROOT / "configs" / "checkpoints" / "r3_default.yaml")
    dt_s = config.dt_s
    chain_summary, chain_rows = reference_chain(dt_s)
    report = {
        "report_id": "R3_PLANT_VALIDATION_V1",
        "evidence_plane": "SYNTHETIC_SIMULATOR",
        "real_fab_validation": False,
        "cmp_or_controller_claim": False,
        "schema_version": config.schema_version,
        "interface_version": config.interface_version,
        "default_config_sha256": runtime_config_sha256(config),
        "parameter_provenance": config.parameter_provenance_ids,
        "pump": pump_evidence(),
        "hydraulics": hydraulic_evidence(dt_s),
        "electrical_ups": electrical_evidence(dt_s),
        "healthy_ups_reference_chain": chain_summary,
    }
    for value in report.values():
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("non-finite value in R3 validation report")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = OUTPUT_DIR / "r3_validation.json"
    temporary = report_path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(report_path)
    write_csv_atomic(OUTPUT_DIR / "r3_healthy_ups_reference_chain.csv", chain_rows)
    print(json.dumps({"report": str(report_path.relative_to(ROOT)), **chain_summary}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
