#!/usr/bin/env python3
"""Generate deterministic WP10 coupling and sensitivity evidence."""

from __future__ import annotations

import csv
import hashlib
import json
import math
from dataclasses import asdict, replace
from pathlib import Path
from typing import Callable

import numpy as np

from semifab_poc.config import load_runtime_config, runtime_config_sha256
from semifab_poc.simulation.cmp import CmpHoldReason, CmpMode, CmpSubsystem
from semifab_poc.simulation.coupling import (
    CouplingConfig,
    UtilityCmpTopology,
    UtilityToCmpCoupler,
)
from semifab_poc.simulation.drive import DriveSubsystem
from semifab_poc.simulation.electrical import ElectricalConfig, ElectricalSubsystem
from semifab_poc.simulation.pump import PumpSubsystem
from semifab_poc.simulation.upw import UpwState, UpwSubsystem


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "reports" / "sensitivity"
DT_S = 0.01
DRESS_END_S = 6.0
POLISH_START_S = 7.0
DURATION_S = 9.0
GLOBAL_SENSITIVITY_SEED = 20260711
GLOBAL_SENSITIVITY_SAMPLES = 4096
PLANT_WARMUP_S = 3.0


def topology_config(
    topology: UtilityCmpTopology,
    link_strength: float | None = None,
    **updates: float,
) -> CouplingConfig:
    if link_strength is None:
        link_strength = 0.0 if topology is UtilityCmpTopology.NO_CONNECTION else 1.0
    return replace(
        CouplingConfig(),
        topology=topology,
        link_strength=link_strength,
        **updates,
    )


def initial_cmp_state(model: CmpSubsystem):
    return replace(
        model.reset(),
        mode=CmpMode.DRESS,
        hold_reason=CmpHoldReason.NONE,
        pad_surface_activity=0.50,
        pad_remaining_life=0.90,
        dresser_effectiveness=0.90,
        dresser_command=1.0,
    )


def phase_action(time_s: float) -> dict[str, float | str]:
    if time_s < DRESS_END_S:
        return {"mode_request": "DRESS", "dresser_command": 1.0}
    if time_s < POLISH_START_S:
        return {"mode_request": "PREPARE"}
    return {"mode_request": "POLISH"}


def simulate_chain(
    scenario: str,
    coupling_config: CouplingConfig,
) -> list[dict[str, object]]:
    runtime = load_runtime_config(ROOT / "configs" / "default.yaml")
    if scenario == "healthy_25pct_400ms_sag":
        electrical_config = runtime.electrical
        event_start_s = 1.0
        event_end_s = 1.4
    elif scenario == "degraded_ups_3s_interruption_during_dress":
        electrical_config = replace(
            runtime.electrical,
            battery_capacity_j=500.0,
            initial_battery_energy_j=500.0,
        )
        event_start_s = 1.0
        event_end_s = 4.0
    else:
        raise ValueError(f"unknown WP10 scenario: {scenario}")

    electrical = ElectricalSubsystem(electrical_config)
    drive = DriveSubsystem(runtime.drive)
    pump = PumpSubsystem(runtime.pump)
    upw = UpwSubsystem(runtime.upw)
    cmp = CmpSubsystem(runtime.cmp)
    coupler = UtilityToCmpCoupler(coupling_config, runtime.upw, runtime.cmp)

    electrical_state = electrical.reset()
    drive_state = drive.reset()
    pump_state = pump.reset()
    upw_state = upw.reset()
    cmp_state = initial_cmp_state(cmp)
    rows: list[dict[str, object]] = []

    # The drive and pump reset at rest by contract. Warm up only the upstream
    # plant before the declared CMP DRESS window so startup is not mistaken for
    # an electrical disturbance or coupling response.
    for _ in range(round(PLANT_WARMUP_S / DT_S)):
        electrical_state = electrical.step(
            electrical_state,
            None,
            {"grid_voltage_pu": 1.0, "ups_load_power_w": electrical.config.nominal_ups_load_w},
            DT_S,
        )
        drive_state = drive.step(
            drive_state,
            {"vfd_command_pu": 1.0, "restart_request": True},
            {"ups_output_voltage_pu": electrical_state.ups_output_voltage_pu},
            DT_S,
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
            DT_S,
        )
        upw_state = upw.step(
            upw_state,
            None,
            {"pump_flow_m3_s": pump_state.volumetric_flow_m3_s},
            DT_S,
        )

    for step in range(round(DURATION_S / DT_S)):
        source_time_s = step * DT_S
        event_active = event_start_s <= source_time_s < event_end_s
        electrical_disturbance: dict[str, float | bool] = {
            "ups_load_power_w": electrical.config.nominal_ups_load_w,
        }
        if scenario == "healthy_25pct_400ms_sag":
            electrical_disturbance["grid_voltage_pu"] = 0.75 if event_active else 1.0
        else:
            electrical_disturbance["force_interruption"] = event_active

        electrical_state = electrical.step(
            electrical_state,
            None,
            electrical_disturbance,
            DT_S,
        )
        drive_state = drive.step(
            drive_state,
            {"vfd_command_pu": 1.0, "restart_request": True},
            {"ups_output_voltage_pu": electrical_state.ups_output_voltage_pu},
            DT_S,
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
            DT_S,
        )
        upw_state = upw.step(
            upw_state,
            None,
            {"pump_flow_m3_s": pump_state.volumetric_flow_m3_s},
            DT_S,
        )
        coupling = coupler.couple(upw_state)
        cmp_state = cmp.step(
            cmp_state,
            phase_action(source_time_s),
            coupling.boundary.as_mapping(),
            DT_S,
        )

        rows.append(
            {
                "scenario": scenario,
                "topology": UtilityCmpTopology(coupling_config.topology).value,
                "step_index": step + 1,
                "source_time_s": source_time_s,
                "timestamp_s": (step + 1) * DT_S,
                "event_active": event_active,
                "grid_voltage_pu": electrical_state.grid_voltage_pu,
                "ups_output_voltage_pu": electrical_state.ups_output_voltage_pu,
                "ups_mode": electrical_state.ups_mode.value,
                "battery_energy_j": electrical_state.battery_energy_j,
                "vfd_available_output_pu": drive_state.vfd_available_output_pu,
                "vfd_tripped": drive_state.tripped,
                "motor_speed_rad_s": drive_state.motor_speed_rad_s,
                "pump_flow_m3_s": pump_state.volumetric_flow_m3_s,
                "pump_head_pa": pump_state.head_pa,
                "pump_operating_point_residual_pa": pump_state.operating_point_residual_pa,
                "upw_supply_pressure_pa": upw_state.supply_pressure_pa,
                "upw_tool_flow_m3_s": upw_state.tool_flow_m3_s,
                "upw_temperature_k": upw_state.temperature_k,
                "upw_mass_balance_residual_m3_s": upw_state.mass_balance_residual_m3_s,
                "pressure_support": coupling.pressure_support,
                "flow_support": coupling.flow_support,
                "hydraulic_support": coupling.hydraulic_support,
                "effective_availability": coupling.effective_availability,
                "dressing_availability": coupling.boundary.dressing_availability,
                "slurry_utility_availability": coupling.boundary.slurry_utility_availability,
                "coolant_temperature_k": coupling.boundary.coolant_temperature_k,
                "cooling_conductance_factor": coupling.boundary.cooling_conductance_factor,
                "cmp_mode": cmp_state.mode.value,
                "cmp_pad_surface_activity": cmp_state.pad_surface_activity,
                "cmp_interface_temperature_k": cmp_state.interface_temperature_k,
                "cmp_mrr_m_s": cmp_state.instantaneous_mrr_m_s,
                "cmp_cumulative_removal_m": cmp_state.cumulative_removal_m,
            }
        )
    return rows


def trace_sha256(rows: list[dict[str, object]]) -> str:
    payload = json.dumps(rows, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def upstream_projection(rows: list[dict[str, object]]) -> list[tuple[object, ...]]:
    keys = (
        "grid_voltage_pu",
        "ups_output_voltage_pu",
        "ups_mode",
        "battery_energy_j",
        "vfd_available_output_pu",
        "vfd_tripped",
        "motor_speed_rad_s",
        "pump_flow_m3_s",
        "pump_head_pa",
        "upw_supply_pressure_pa",
        "upw_tool_flow_m3_s",
        "upw_temperature_k",
    )
    return [tuple(row[key] for key in keys) for row in rows]


def chain_summary(rows: list[dict[str, object]]) -> dict[str, object]:
    dressing = [row for row in rows if float(row["source_time_s"]) < DRESS_END_S]
    polishing = [row for row in rows if float(row["source_time_s"]) >= POLISH_START_S]
    return {
        "scenario": rows[0]["scenario"],
        "topology": rows[0]["topology"],
        "trace_sha256": trace_sha256(rows),
        "minimum_ups_output_voltage_pu": min(float(row["ups_output_voltage_pu"]) for row in rows),
        "minimum_motor_speed_rad_s": min(float(row["motor_speed_rad_s"]) for row in rows),
        "minimum_pump_flow_m3_s": min(float(row["pump_flow_m3_s"]) for row in rows),
        "minimum_supply_pressure_pa": min(float(row["upw_supply_pressure_pa"]) for row in rows),
        "minimum_tool_flow_m3_s": min(float(row["upw_tool_flow_m3_s"]) for row in rows),
        "minimum_hydraulic_support": min(float(row["hydraulic_support"]) for row in rows),
        "minimum_effective_availability": min(float(row["effective_availability"]) for row in rows),
        "minimum_dressing_availability_during_dress": min(
            float(row["dressing_availability"]) for row in dressing
        ),
        "pad_surface_activity_at_dress_end": float(dressing[-1]["cmp_pad_surface_activity"]),
        "mean_polish_mrr_m_s": sum(float(row["cmp_mrr_m_s"]) for row in polishing) / len(polishing),
        "final_cumulative_removal_m": float(rows[-1]["cmp_cumulative_removal_m"]),
        "maximum_pump_curve_residual_pa": max(
            abs(float(row["pump_operating_point_residual_pa"])) for row in rows
        ),
        "maximum_hydraulic_mass_balance_residual_m3_s": max(
            abs(float(row["upw_mass_balance_residual_m3_s"])) for row in rows
        ),
    }


def first_time(rows: list[dict[str, object]], predicate: Callable[[dict[str, object]], bool]) -> float | None:
    for row in rows:
        if predicate(row):
            return float(row["source_time_s"])
    return None


def causal_onsets(rows: list[dict[str, object]]) -> dict[str, float | None]:
    nominal_motor = 188.5
    return {
        "grid_interruption_s": first_time(rows, lambda row: float(row["grid_voltage_pu"]) == 0.0),
        "ups_output_below_0_9_pu_s": first_time(
            rows, lambda row: float(row["ups_output_voltage_pu"]) < 0.9
        ),
        "motor_below_99pct_nominal_s": first_time(
            rows, lambda row: float(row["motor_speed_rad_s"]) < 0.99 * nominal_motor
        ),
        "pump_flow_below_99pct_reference_s": first_time(
            rows, lambda row: float(row["pump_flow_m3_s"]) < 0.99 * 2.0e-4
        ),
        "upw_pressure_below_full_support_s": first_time(
            rows, lambda row: float(row["pressure_support"]) < 1.0
        ),
        "coupling_availability_below_one_s": first_time(
            rows, lambda row: float(row["effective_availability"]) < 1.0
        ),
        "polish_start_s": first_time(rows, lambda row: row["cmp_mode"] == "POLISH"),
    }


def local_sensitivity() -> dict[str, object]:
    pressure_state = UpwState(
        supply_pressure_pa=240_000.0,
        return_pressure_pa=100_000.0,
        tool_flow_m3_s=1.0e-4,
        valve_position=1.0,
        tool_demand_m3_s=1.0e-4,
        temperature_k=303.15,
        water_quality_deviation_proxy=0.0,
    )
    flow_state = replace(pressure_state, supply_pressure_pa=300_000.0, tool_flow_m3_s=8.0e-5)
    base = topology_config(UtilityCmpTopology.DRESSING_WATER_SUPPORT, 0.5)
    cases: list[dict[str, object]] = []

    def derivative(
        name: str,
        step: float,
        state: UpwState,
        output: Callable[[object], float],
        config: CouplingConfig = base,
    ) -> None:
        low = replace(config, **{name: getattr(config, name) - step})
        high = replace(config, **{name: getattr(config, name) + step})
        low_value = output(UtilityToCmpCoupler(low).couple(state))
        high_value = output(UtilityToCmpCoupler(high).couple(state))
        cases.append(
            {
                "parameter": name,
                "step": step,
                "state_case": "pressure_limiting" if state is pressure_state else "flow_limiting",
                "output": "effective_availability",
                "centered_derivative": (high_value - low_value) / (2.0 * step),
            }
        )

    derivative("link_strength", 1.0e-4, pressure_state, lambda result: result.effective_availability)
    derivative("reference_supply_pressure_pa", 10.0, pressure_state, lambda result: result.effective_availability)
    derivative("pressure_zero_fraction", 1.0e-4, pressure_state, lambda result: result.effective_availability)
    derivative("pressure_full_fraction", 1.0e-4, pressure_state, lambda result: result.effective_availability)
    derivative("reference_tool_flow_m3_s", 1.0e-8, flow_state, lambda result: result.effective_availability)
    derivative("flow_zero_fraction", 1.0e-4, flow_state, lambda result: result.effective_availability)
    derivative("flow_full_fraction", 1.0e-4, flow_state, lambda result: result.effective_availability)

    thermal = topology_config(UtilityCmpTopology.THERMAL_LOOP, 0.5)
    step = 1.0e-3
    low = replace(thermal, reference_upw_temperature_k=thermal.reference_upw_temperature_k - step)
    high = replace(thermal, reference_upw_temperature_k=thermal.reference_upw_temperature_k + step)
    low_value = UtilityToCmpCoupler(low).couple(pressure_state).boundary.coolant_temperature_k
    high_value = UtilityToCmpCoupler(high).couple(pressure_state).boundary.coolant_temperature_k
    cases.append(
        {
            "parameter": "reference_upw_temperature_k",
            "step": step,
            "state_case": "thermal_deviation",
            "output": "coolant_temperature_k",
            "centered_derivative": (high_value - low_value) / (2.0 * step),
        }
    )
    return {"method": "centered finite difference at declared off-kink states", "cases": cases}


GLOBAL_PARAMETER_RANGES: tuple[tuple[str, float, float], ...] = (
    ("link_strength", 0.0, 1.0),
    ("reference_supply_pressure_pa", 250_000.0, 350_000.0),
    ("pressure_zero_fraction", 0.40, 0.75),
    ("pressure_full_fraction", 0.85, 1.00),
    ("reference_tool_flow_m3_s", 8.0e-5, 1.2e-4),
    ("flow_zero_fraction", 0.30, 0.70),
    ("flow_full_fraction", 0.85, 1.00),
)


def scale_samples(unit_samples: np.ndarray) -> np.ndarray:
    lower = np.array([item[1] for item in GLOBAL_PARAMETER_RANGES], dtype=float)
    upper = np.array([item[2] for item in GLOBAL_PARAMETER_RANGES], dtype=float)
    return lower + unit_samples * (upper - lower)


def evaluate_global_samples(samples: np.ndarray, state: UpwState) -> np.ndarray:
    values = np.empty(samples.shape[0], dtype=float)
    for index, row in enumerate(samples):
        updates = {name: float(row[column]) for column, (name, _, _) in enumerate(GLOBAL_PARAMETER_RANGES)}
        config = topology_config(UtilityCmpTopology.DRESSING_WATER_SUPPORT, **updates)
        values[index] = UtilityToCmpCoupler(config).couple(state).effective_availability
    return values


def global_sensitivity() -> dict[str, object]:
    state = UpwState(
        supply_pressure_pa=240_000.0,
        return_pressure_pa=100_000.0,
        tool_flow_m3_s=8.0e-5,
        valve_position=1.0,
        tool_demand_m3_s=1.0e-4,
        temperature_k=293.15,
        water_quality_deviation_proxy=0.0,
    )
    rng = np.random.default_rng(GLOBAL_SENSITIVITY_SEED)
    dimension = len(GLOBAL_PARAMETER_RANGES)
    matrix_a = scale_samples(rng.random((GLOBAL_SENSITIVITY_SAMPLES, dimension)))
    matrix_b = scale_samples(rng.random((GLOBAL_SENSITIVITY_SAMPLES, dimension)))
    output_a = evaluate_global_samples(matrix_a, state)
    output_b = evaluate_global_samples(matrix_b, state)
    variance = float(np.var(np.concatenate((output_a, output_b)), ddof=1))
    if variance <= 0.0 or not math.isfinite(variance):
        raise RuntimeError("WP10 global sensitivity output has no finite variance")

    indices = []
    for column, (name, lower, upper) in enumerate(GLOBAL_PARAMETER_RANGES):
        mixed = matrix_a.copy()
        mixed[:, column] = matrix_b[:, column]
        output_mixed = evaluate_global_samples(mixed, state)
        first_order = float(np.mean(output_b * (output_mixed - output_a)) / variance)
        total_order = float(0.5 * np.mean((output_a - output_mixed) ** 2) / variance)
        indices.append(
            {
                "parameter": name,
                "range": [lower, upper],
                "first_order_estimate_raw": first_order,
                "total_order_estimate": total_order,
            }
        )
    return {
        "method": "seeded Saltelli pick-freeze Monte Carlo estimators",
        "seed": GLOBAL_SENSITIVITY_SEED,
        "base_sample_count": GLOBAL_SENSITIVITY_SAMPLES,
        "evaluation_count": (2 + dimension) * GLOBAL_SENSITIVITY_SAMPLES,
        "representative_state": asdict(state),
        "output": "effective_availability",
        "output_variance": variance,
        "indices": indices,
        "note": "Raw finite-sample first-order estimates may be slightly negative; they are not clipped or renormalized.",
    }


def mismatch_sensitivity() -> list[dict[str, object]]:
    cases = {
        "zero_link": topology_config(UtilityCmpTopology.DRESSING_WATER_SUPPORT, 0.0),
        "weak_link": topology_config(UtilityCmpTopology.DRESSING_WATER_SUPPORT, 0.25),
        "nominal_link": topology_config(UtilityCmpTopology.DRESSING_WATER_SUPPORT, 1.0),
        "earlier_response": topology_config(
            UtilityCmpTopology.DRESSING_WATER_SUPPORT,
            1.0,
            pressure_zero_fraction=0.70,
            pressure_full_fraction=0.98,
            flow_zero_fraction=0.60,
            flow_full_fraction=0.98,
        ),
        "later_response": topology_config(
            UtilityCmpTopology.DRESSING_WATER_SUPPORT,
            1.0,
            pressure_zero_fraction=0.40,
            pressure_full_fraction=0.85,
            flow_zero_fraction=0.30,
            flow_full_fraction=0.85,
        ),
    }
    return [
        {"case": name, "config": asdict(config), "chain": chain_summary(simulate_chain("degraded_ups_3s_interruption_during_dress", config))}
        for name, config in cases.items()
    ]


def structural_boundary_comparison() -> list[dict[str, object]]:
    state = UpwState(
        supply_pressure_pa=150_000.0,
        return_pressure_pa=100_000.0,
        tool_flow_m3_s=0.0,
        valve_position=1.0,
        tool_demand_m3_s=1.0e-4,
        temperature_k=303.15,
        water_quality_deviation_proxy=0.0,
    )
    results = []
    for topology in UtilityCmpTopology:
        result = UtilityToCmpCoupler(topology_config(topology)).couple(state)
        results.append(
            {
                "topology": topology.value,
                "effective_availability": result.effective_availability,
                "boundary": result.boundary.as_mapping(),
            }
        )
    return results


def write_csv_atomic(path: Path, rows: list[dict[str, object]]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def main() -> int:
    runtime = load_runtime_config(ROOT / "configs" / "default.yaml")
    null = topology_config(UtilityCmpTopology.NO_CONNECTION)
    dressing = topology_config(UtilityCmpTopology.DRESSING_WATER_SUPPORT)

    negative_null = simulate_chain("healthy_25pct_400ms_sag", null)
    negative_dressing = simulate_chain("healthy_25pct_400ms_sag", dressing)
    positive_null = simulate_chain("degraded_ups_3s_interruption_during_dress", null)
    positive_dressing = simulate_chain("degraded_ups_3s_interruption_during_dress", dressing)
    positive_replay = simulate_chain("degraded_ups_3s_interruption_during_dress", dressing)

    negative_null_summary = chain_summary(negative_null)
    negative_dressing_summary = chain_summary(negative_dressing)
    positive_null_summary = chain_summary(positive_null)
    positive_dressing_summary = chain_summary(positive_dressing)

    checks = {
        "negative_upstream_traces_identical": upstream_projection(negative_null) == upstream_projection(negative_dressing),
        "positive_upstream_traces_identical": upstream_projection(positive_null) == upstream_projection(positive_dressing),
        "healthy_sag_remains_full_support": negative_dressing_summary["minimum_effective_availability"] == 1.0,
        "healthy_sag_cmp_trace_matches_null": all(
            left["cmp_pad_surface_activity"] == right["cmp_pad_surface_activity"]
            and left["cmp_mrr_m_s"] == right["cmp_mrr_m_s"]
            and left["cmp_cumulative_removal_m"] == right["cmp_cumulative_removal_m"]
            for left, right in zip(negative_null, negative_dressing, strict=True)
        ),
        "positive_event_reduces_dressing_availability": float(positive_dressing_summary["minimum_dressing_availability_during_dress"]) < 1.0,
        "positive_event_reduces_end_dress_pad_activity": float(positive_dressing_summary["pad_surface_activity_at_dress_end"]) < float(positive_null_summary["pad_surface_activity_at_dress_end"]),
        "positive_event_reduces_later_mean_mrr": float(positive_dressing_summary["mean_polish_mrr_m_s"]) < float(positive_null_summary["mean_polish_mrr_m_s"]),
        "positive_event_reduces_cumulative_removal": float(positive_dressing_summary["final_cumulative_removal_m"]) < float(positive_null_summary["final_cumulative_removal_m"]),
        "positive_replay_is_deterministic": positive_dressing == positive_replay,
        "pump_curve_residual_within_1e_6_pa": max(
            float(positive_null_summary["maximum_pump_curve_residual_pa"]),
            float(positive_dressing_summary["maximum_pump_curve_residual_pa"]),
        ) <= 1.0e-6,
        "hydraulic_mass_residual_within_1e_12_m3_s": max(
            float(positive_null_summary["maximum_hydraulic_mass_balance_residual_m3_s"]),
            float(positive_dressing_summary["maximum_hydraulic_mass_balance_residual_m3_s"]),
        ) <= 1.0e-12,
    }
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise RuntimeError(f"WP10 validation checks failed: {failed}")

    report = {
        "report_id": "WP10_UTILITY_CMP_COUPLING_VALIDATION_V1",
        "evidence_plane": "SYNTHETIC_SIMULATOR",
        "public_data_validation": False,
        "real_fab_validation": False,
        "controller_efficacy_validation": False,
        "physical_defect_or_yield_validation": False,
        "schema_version": runtime.schema_version,
        "interface_version": runtime.interface_version,
        "runtime_config_sha256": runtime_config_sha256(runtime),
        "default_topology": UtilityCmpTopology(runtime.coupling.topology).value,
        "coupling_parameter_provenance": UtilityToCmpCoupler.parameter_provenance_classes(),
        "functional_form_provenance": UtilityToCmpCoupler.functional_form_provenance_classes(),
        "parameter_registry": [asdict(item) for item in UtilityToCmpCoupler(dressing).parameter_metadata()],
        "structural_boundary_comparison": structural_boundary_comparison(),
        "negative_control": {
            "interpretation": "healthy-UPS 25 percent, 400 ms voltage sag; support remains full",
            "no_connection": negative_null_summary,
            "dressing_water_support": negative_dressing_summary,
        },
        "positive_causal_chain": {
            "interpretation": "synthetic degraded-UPS interruption during DRESS; not a real-tool calibration",
            "electrical_config_override": {"battery_capacity_j": 500.0, "initial_battery_energy_j": 500.0},
            "event": {"force_interruption": True, "start_s": 1.0, "end_s": 4.0},
            "phase_schedule": {"DRESS_end_s": DRESS_END_S, "POLISH_start_s": POLISH_START_S},
            "no_connection": positive_null_summary,
            "dressing_water_support": positive_dressing_summary,
            "causal_onsets": causal_onsets(positive_dressing),
        },
        "local_sensitivity": local_sensitivity(),
        "global_sensitivity": global_sensitivity(),
        "parameter_mismatch": mismatch_sensitivity(),
        "checks": checks,
        "all_checks_passed": True,
        "claims_boundary": (
            "Synthetic declared-topology propagation only; no actual tool plumbing, public-data coupling, "
            "physical-defect, yield, equipment, production-control, or controller-efficacy claim."
        ),
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = OUTPUT_DIR / "wp10_coupling_validation.json"
    temporary = report_path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(report_path)
    write_csv_atomic(OUTPUT_DIR / "wp10_negative_control_trace.csv", negative_null + negative_dressing)
    write_csv_atomic(OUTPUT_DIR / "wp10_positive_chain_trace.csv", positive_null + positive_dressing)
    print(
        json.dumps(
            {
                "report": str(report_path.relative_to(ROOT)),
                "negative_control": negative_dressing_summary,
                "positive_no_connection": positive_null_summary,
                "positive_dressing_connection": positive_dressing_summary,
                "all_checks_passed": True,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
