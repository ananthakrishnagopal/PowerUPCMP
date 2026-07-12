#!/usr/bin/env python3
"""Generate deterministic WP08 CMP scientific-validation evidence."""

from __future__ import annotations

import csv
import hashlib
import json
import math
from dataclasses import asdict, replace
from pathlib import Path

from semifab_poc.config import load_runtime_config, runtime_config_sha256
from semifab_poc.simulation.cmp import (
    SPATIAL_PROXY_LABEL,
    CmpHoldReason,
    CmpMode,
    CmpSubsystem,
)


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "reports" / "cmp"
WP08_RUNTIME_CONFIG_SHA256 = (
    "99d7876eb76d561de97ed577d77da30e929c70276070bb6f84df0fb9c9e91670"
)


def reference_trace(model: CmpSubsystem, dt_s: float = 0.01) -> list[dict[str, object]]:
    state = model.reset()
    rows: list[dict[str, object]] = []
    duration_s = 7.0
    for step in range(round(duration_s / dt_s)):
        source_time_s = step * dt_s
        if source_time_s < 1.0:
            requested_mode = CmpMode.PREPARE
        elif source_time_s < 6.0:
            requested_mode = CmpMode.POLISH
        else:
            requested_mode = CmpMode.HOLD
        state = model.step(
            state,
            {"mode_request": requested_mode.value},
            None,
            dt_s,
        )
        rows.append(
            {
                "step_index": step + 1,
                "timestamp_s": (step + 1) * dt_s,
                "mode": state.mode.value,
                "contact_pressure_pa": state.contact_pressure_pa,
                "platen_angular_speed_rad_s": state.platen_angular_speed_rad_s,
                "head_angular_speed_rad_s": state.head_angular_speed_rad_s,
                "relative_velocity_m_s": state.relative_velocity_m_s,
                "slurry_availability": state.slurry_availability,
                "interface_temperature_k": state.interface_temperature_k,
                "pressure_velocity_exposure": state.pressure_velocity_exposure,
                "pad_surface_activity": state.pad_surface_activity,
                "pad_remaining_life": state.pad_remaining_life,
                "dresser_effectiveness": state.dresser_effectiveness,
                "instantaneous_mrr_m_s": state.instantaneous_mrr_m_s,
                "cumulative_removal_m": state.cumulative_removal_m,
                "active_polish_time_s": state.active_polish_time_s,
                "stage_average_mrr_m_s": state.stage_average_mrr_m_s,
                "thermal_energy_residual_w": state.thermal_energy_residual_w,
            }
        )
    return rows


def trace_sha256(rows: list[dict[str, object]]) -> str:
    payload = json.dumps(rows, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def convergence_evidence(model: CmpSubsystem) -> dict[str, object]:
    def simulate(dt_s: float):
        state = model.nominal_polish_state()
        for _ in range(round(1.0 / dt_s)):
            state = model.step(
                state,
                {
                    "contact_pressure_command_pa": (
                        0.70 * model.config.nominal_contact_pressure_pa
                    )
                },
                None,
                dt_s,
            )
        return state

    reference_dt_s = 0.001
    reference = simulate(reference_dt_s)
    cases = []
    for dt_s in (0.04, 0.02, 0.01, 0.005, 0.0025):
        state = simulate(dt_s)
        cases.append(
            {
                "dt_s": dt_s,
                "contact_pressure_pa": state.contact_pressure_pa,
                "interface_temperature_k": state.interface_temperature_k,
                "cumulative_removal_m": state.cumulative_removal_m,
                "pressure_error_vs_1_ms_pa": abs(
                    state.contact_pressure_pa - reference.contact_pressure_pa
                ),
                "temperature_error_vs_1_ms_k": abs(
                    state.interface_temperature_k - reference.interface_temperature_k
                ),
                "cumulative_error_vs_1_ms_m": abs(
                    state.cumulative_removal_m - reference.cumulative_removal_m
                ),
            }
        )
    return {
        "reference_dt_s": reference_dt_s,
        "reference_state": {
            "contact_pressure_pa": reference.contact_pressure_pa,
            "interface_temperature_k": reference.interface_temperature_k,
            "cumulative_removal_m": reference.cumulative_removal_m,
        },
        "cases": cases,
    }


def quadrature_evidence() -> dict[str, object]:
    cases = []
    for radial, angular in ((8, 32), (16, 64), (32, 128), (48, 192)):
        from semifab_poc.simulation.cmp import CmpConfig

        model = CmpSubsystem(
            replace(
                CmpConfig(),
                radial_quadrature_order=radial,
                angular_quadrature_order=angular,
            )
        )
        cases.append(
            {
                "radial_order": radial,
                "angular_order": angular,
                "constant_field_integral": model.constant_field_quadrature,
                "area_mean_relative_velocity_m_s": (
                    model.area_mean_relative_velocity(8.0, 6.0)
                ),
                "reference_velocity_scale_m_s": model.reference_velocity_scale_m_s,
            }
        )
    reference = cases[-1]["area_mean_relative_velocity_m_s"]
    for case in cases:
        case["absolute_velocity_error_vs_48x192_m_s"] = abs(
            float(case["area_mean_relative_velocity_m_s"]) - float(reference)
        )
    return {"cases": cases}


def consumable_evidence(model: CmpSubsystem) -> dict[str, object]:
    initial = replace(
        model.reset(),
        mode=CmpMode.DRESS,
        hold_reason=CmpHoldReason.NONE,
        pad_surface_activity=0.50,
        pad_remaining_life=0.80,
        dresser_effectiveness=0.90,
        dresser_command=1.0,
    )
    state = initial
    for _ in range(round(10.0 / 0.05)):
        state = model.step(
            state,
            {"mode_request": "DRESS", "dresser_command": 1.0},
            {"dressing_availability": 1.0},
            0.05,
        )
    return {
        "duration_s": 10.0,
        "initial": {
            "pad_surface_activity": initial.pad_surface_activity,
            "pad_remaining_life": initial.pad_remaining_life,
            "dresser_effectiveness": initial.dresser_effectiveness,
        },
        "final": {
            "pad_surface_activity": state.pad_surface_activity,
            "pad_remaining_life": state.pad_remaining_life,
            "dresser_effectiveness": state.dresser_effectiveness,
            "instantaneous_mrr_m_s": state.instantaneous_mrr_m_s,
        },
    }


def thermal_null_evidence(model: CmpSubsystem) -> dict[str, float]:
    cold = model.nominal_polish_state()
    warm = model.nominal_polish_state()
    for _ in range(100):
        cold = model.step(cold, None, {"coolant_temperature_k": 283.15}, 0.01)
        warm = model.step(warm, None, {"coolant_temperature_k": 303.15}, 0.01)
    return {
        "cold_interface_temperature_k": cold.interface_temperature_k,
        "warm_interface_temperature_k": warm.interface_temperature_k,
        "instantaneous_mrr_difference_m_s": (
            warm.instantaneous_mrr_m_s - cold.instantaneous_mrr_m_s
        ),
        "temperature_sensitivity_k_inv": model.config.temperature_sensitivity_k_inv,
    }


def write_csv_atomic(path: Path, rows: list[dict[str, object]]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def main() -> int:
    current_runtime = load_runtime_config(ROOT / "configs" / "default.yaml")
    runtime = current_runtime.model_copy(
        update={"schema_version": "2.3.0", "interface_version": "3.1.0"}
    )
    if runtime_config_sha256(runtime) != WP08_RUNTIME_CONFIG_SHA256:
        raise RuntimeError("frozen WP08 runtime configuration hash changed")
    model = CmpSubsystem(runtime.cmp)
    first_trace = reference_trace(model)
    second_trace = reference_trace(model)
    first_hash = trace_sha256(first_trace)
    if first_trace != second_trace:
        raise RuntimeError("WP08 fixed-input replay is not deterministic")

    nominal = model.nominal_polish_state()
    spatial = model.spatial_uniformity_proxy(nominal)
    quadrature = quadrature_evidence()
    convergence = convergence_evidence(model)
    consumables = consumable_evidence(model)
    thermal_null = thermal_null_evidence(model)
    maximum_thermal_residual = max(
        abs(float(row["thermal_energy_residual_w"])) for row in first_trace
    )
    polish_rows = [row for row in first_trace if row["mode"] == "POLISH"]
    hold_rows = [row for row in first_trace if row["mode"] == "HOLD"]

    checks = {
        "constant_field_quadrature_within_1e_12": (
            abs(model.constant_field_quadrature - 1.0) <= 1.0e-12
        ),
        "nominal_exposure_within_1e_12": (
            abs(nominal.pressure_velocity_exposure - 1.0) <= 1.0e-12
        ),
        "nominal_mrr_within_1e_12_relative": math.isclose(
            nominal.instantaneous_mrr_m_s,
            model.config.reference_mrr_m_s,
            rel_tol=1.0e-12,
            abs_tol=0.0,
        ),
        "zero_pressure_exposure": (
            model.pressure_velocity_exposure(
                0.0,
                model.config.nominal_platen_angular_speed_rad_s,
                model.config.nominal_head_angular_speed_rad_s,
            )
            == 0.0
        ),
        "zero_speed_exposure": (
            model.pressure_velocity_exposure(
                model.config.nominal_contact_pressure_pa,
                0.0,
                0.0,
            )
            == 0.0
        ),
        "hold_mrr_zero": all(float(row["instantaneous_mrr_m_s"]) == 0.0 for row in hold_rows),
        "polish_accumulates_removal": bool(polish_rows)
        and float(polish_rows[-1]["cumulative_removal_m"]) > 0.0,
        "thermal_residual_below_1e_7_w": maximum_thermal_residual < 1.0e-7,
        "dressing_restores_activity": (
            float(consumables["final"]["pad_surface_activity"])
            > float(consumables["initial"]["pad_surface_activity"])
        ),
        "dressing_does_not_restore_pad_life": (
            float(consumables["final"]["pad_remaining_life"])
            < float(consumables["initial"]["pad_remaining_life"])
        ),
        "dressing_consumes_dresser": (
            float(consumables["final"]["dresser_effectiveness"])
            < float(consumables["initial"]["dresser_effectiveness"])
        ),
        "thermal_null_has_zero_mrr_effect": (
            float(thermal_null["instantaneous_mrr_difference_m_s"]) == 0.0
        ),
        "spatial_proxy_label_exact": spatial.label == SPATIAL_PROXY_LABEL,
        "deterministic_replay": first_trace == second_trace,
        "ten_ms_error_below_forty_ms_error": (
            float(convergence["cases"][2]["cumulative_error_vs_1_ms_m"])
            < float(convergence["cases"][0]["cumulative_error_vs_1_ms_m"])
        ),
    }
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise RuntimeError(f"WP08 validation checks failed: {failed}")

    report = {
        "report_id": "WP08_CMP_SCIENTIFIC_VALIDATION_V1",
        "evidence_plane": "SYNTHETIC_SIMULATOR",
        "public_data_validation": False,
        "real_fab_validation": False,
        "physical_defect_or_yield_validation": False,
        "schema_version": runtime.schema_version,
        "interface_version": runtime.interface_version,
        "runtime_config_sha256": runtime_config_sha256(runtime),
        "cmp_config": asdict(model.config),
        "parameter_provenance_classes": model.parameter_provenance_classes(),
        "reference": {
            "reference_mrr_m_s": model.config.reference_mrr_m_s,
            "reference_mrr_nm_min": model.config.reference_mrr_m_s * 6.0e10,
            "reference_velocity_scale_m_s": model.reference_velocity_scale_m_s,
            "classical_preston_coefficient_pa_inv": (
                model.classical_preston_coefficient_pa_inv
            ),
            "nominal_exposure": nominal.pressure_velocity_exposure,
            "nominal_mrr_m_s": nominal.instantaneous_mrr_m_s,
        },
        "quadrature": quadrature,
        "convergence": convergence,
        "consumables": consumables,
        "thermal_structural_null": thermal_null,
        "spatial_uniformity_proxy": {
            "label": spatial.label,
            "coefficient_of_variation": spatial.coefficient_of_variation,
            "radial_point_count": len(spatial.radial_positions_m),
        },
        "reference_trace": {
            "row_count": len(first_trace),
            "sha256": first_hash,
            "maximum_absolute_thermal_energy_residual_w": maximum_thermal_residual,
            "final_cumulative_removal_m": first_trace[-1]["cumulative_removal_m"],
            "final_active_polish_time_s": first_trace[-1]["active_polish_time_s"],
            "final_stage_average_mrr_m_s": first_trace[-1]["stage_average_mrr_m_s"],
        },
        "checks": checks,
        "all_checks_passed": True,
        "claims_boundary": (
            "Synthetic reduced-order CMP state validation only; no experimental WIWNU, "
            "physical-defect, yield, equipment, production-control, or real-fab claim."
        ),
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = OUTPUT_DIR / "wp08_validation.json"
    temporary = report_path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(report_path)
    trace_path = OUTPUT_DIR / "wp08_reference_trace.csv"
    write_csv_atomic(trace_path, first_trace)
    print(
        json.dumps(
            {
                "report": str(report_path.relative_to(ROOT)),
                "trace": str(trace_path.relative_to(ROOT)),
                "trace_sha256": first_hash,
                "reference_velocity_scale_m_s": model.reference_velocity_scale_m_s,
                "reference_mrr_nm_min": model.config.reference_mrr_m_s * 6.0e10,
                "maximum_thermal_residual_w": maximum_thermal_residual,
                "all_checks_passed": True,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
