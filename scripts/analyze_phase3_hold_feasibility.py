#!/usr/bin/env python3
"""CMP-only limiting-case analysis for the frozen Phase 3 hold mechanism."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import numpy as np

from semifab_poc.simulation.cmp import (
    CmpBoundaryConditions,
    CmpHoldReason,
    CmpMode,
    CmpSubsystem,
)


ROOT = Path(__file__).resolve().parents[1]
DT_S = 0.01
DRESS_DURATION_S = 6.0
PREPARE_DURATION_S = 1.0
POLISH_DURATION_S = 9.0
DISTURBANCE_END_S = 5.99
PREDICTIVE_HOLD_START_S = 4.29
THRESHOLD_HOLD_START_S = 0.10


@dataclass(frozen=True)
class FeasibilityTrace:
    label: str
    wall_completion_s: float
    dress_progress_s: float
    prepare_progress_s: float
    polish_progress_s: float
    hold_duration_s: float
    recovery_duration_s: float
    end_dress_pad_activity: float
    end_dress_pad_remaining_life: float
    polish_mrr_m_s: tuple[float, ...]
    cumulative_removal_m: float


def _mode_action(model: CmpSubsystem, mode: CmpMode) -> dict[str, float | str]:
    action: dict[str, float | str] = {
        "mode_request": mode.value,
        "contact_pressure_command_pa": model.config.nominal_contact_pressure_pa,
        "platen_speed_command_rad_s": model.config.nominal_platen_angular_speed_rad_s,
        "head_speed_command_rad_s": model.config.nominal_head_angular_speed_rad_s,
        "slurry_flow_command_m3_s": model.config.reference_slurry_flow_m3_s,
        "dresser_command": 1.0,
        "recipe_modifier": model.config.nominal_recipe_modifier,
    }
    return action


def _run_case(
    label: str,
    *,
    disturbed: bool,
    hold_start_s: float | None,
) -> FeasibilityTrace:
    model = CmpSubsystem()
    state = replace(
        model.reset(),
        mode=CmpMode.DRESS,
        hold_reason=CmpHoldReason.NONE,
        pad_surface_activity=0.50,
        pad_remaining_life=0.90,
        dresser_effectiveness=0.90,
        dresser_command=1.0,
    )
    state.validate(model.config)

    wall_time_s = 0.0
    dress_progress_s = 0.0
    prepare_progress_s = 0.0
    polish_progress_s = 0.0
    hold_duration_s = 0.0
    recovery_duration_s = 0.0
    hold_triggered = False
    restoring_interrupted_dress = False
    end_dress_pad_activity: float | None = None
    end_dress_pad_remaining_life: float | None = None
    polish_mrr: list[float] = []

    maximum_steps = round(40.0 / DT_S)
    for _ in range(maximum_steps):
        event_active = disturbed and wall_time_s < DISTURBANCE_END_S - 1.0e-12
        if (
            hold_start_s is not None
            and not hold_triggered
            and dress_progress_s < DRESS_DURATION_S - 1.0e-12
            and event_active
            and wall_time_s >= hold_start_s - 1.0e-12
        ):
            hold_triggered = True
            restoring_interrupted_dress = True

        routing_prepare = False
        if restoring_interrupted_dress:
            if state.mode is CmpMode.DRESS:
                requested_mode = CmpMode.HOLD
            elif state.mode is CmpMode.HOLD:
                requested_mode = CmpMode.HOLD if event_active else CmpMode.RECOVER
            elif state.mode is CmpMode.RECOVER:
                requested_mode = CmpMode.PREPARE
            elif state.mode is CmpMode.PREPARE:
                requested_mode = CmpMode.DRESS
                routing_prepare = True
            else:
                raise RuntimeError(f"unexpected restoration mode: {state.mode.value}")
        elif dress_progress_s < DRESS_DURATION_S - 1.0e-12:
            requested_mode = CmpMode.DRESS
        elif prepare_progress_s < PREPARE_DURATION_S - 1.0e-12:
            requested_mode = CmpMode.PREPARE
        else:
            requested_mode = CmpMode.POLISH

        boundary = CmpBoundaryConditions(
            dressing_availability=0.0 if event_active else 1.0,
            slurry_utility_availability=1.0,
            coolant_temperature_k=model.config.interface_reference_temperature_k,
            cooling_conductance_factor=1.0,
            process_discrepancy_m_s=0.0,
            utilities_valid=not event_active,
            sensors_valid=True,
            force_hold=False,
        )
        previous_mode = state.mode
        state = model.step(
            state,
            _mode_action(model, requested_mode),
            boundary.as_mapping(),
            DT_S,
        )
        wall_time_s += DT_S

        if state.mode is CmpMode.HOLD:
            hold_duration_s += DT_S
        elif state.mode is CmpMode.RECOVER:
            recovery_duration_s += DT_S
        elif state.mode is CmpMode.DRESS:
            dress_progress_s += DT_S
            if restoring_interrupted_dress and previous_mode is CmpMode.PREPARE:
                restoring_interrupted_dress = False
        elif state.mode is CmpMode.PREPARE and not routing_prepare:
            if not restoring_interrupted_dress:
                prepare_progress_s += DT_S
        elif state.mode is CmpMode.POLISH:
            polish_progress_s += DT_S
            polish_mrr.append(state.instantaneous_mrr_m_s)

        if (
            end_dress_pad_activity is None
            and dress_progress_s >= DRESS_DURATION_S - 1.0e-12
            and state.mode is not CmpMode.DRESS
        ):
            end_dress_pad_activity = state.pad_surface_activity
            end_dress_pad_remaining_life = state.pad_remaining_life

        if polish_progress_s >= POLISH_DURATION_S - 1.0e-12:
            break
    else:
        raise RuntimeError(f"{label} did not complete within the analysis bound")

    if end_dress_pad_activity is None or end_dress_pad_remaining_life is None:
        raise RuntimeError(f"{label} did not record end-DRESS consumable state")
    expected_polish_steps = round(POLISH_DURATION_S / DT_S)
    if len(polish_mrr) != expected_polish_steps:
        raise RuntimeError(
            f"{label} produced {len(polish_mrr)} rather than {expected_polish_steps} polish steps"
        )
    return FeasibilityTrace(
        label=label,
        wall_completion_s=wall_time_s,
        dress_progress_s=dress_progress_s,
        prepare_progress_s=prepare_progress_s,
        polish_progress_s=polish_progress_s,
        hold_duration_s=hold_duration_s,
        recovery_duration_s=recovery_duration_s,
        end_dress_pad_activity=end_dress_pad_activity,
        end_dress_pad_remaining_life=end_dress_pad_remaining_life,
        polish_mrr_m_s=tuple(polish_mrr),
        cumulative_removal_m=state.cumulative_removal_m,
    )


def _metrics(trace: FeasibilityTrace, reference: FeasibilityTrace) -> dict[str, float]:
    values = np.asarray(trace.polish_mrr_m_s, dtype=float)
    reference_values = np.asarray(reference.polish_mrr_m_s, dtype=float)
    difference = values - reference_values
    reference_scale = np.maximum(reference_values, 1.0e-18)
    return {
        "wall_completion_s": trace.wall_completion_s,
        "cycle_extension_vs_reference_s": (
            trace.wall_completion_s - reference.wall_completion_s
        ),
        "hold_duration_s": trace.hold_duration_s,
        "recovery_duration_s": trace.recovery_duration_s,
        "end_dress_pad_activity": trace.end_dress_pad_activity,
        "end_dress_pad_activity_relative_to_reference": (
            trace.end_dress_pad_activity / reference.end_dress_pad_activity
        ),
        "end_dress_pad_remaining_life": trace.end_dress_pad_remaining_life,
        "peak_relative_mrr_deviation": float(
            np.max(np.abs(difference) / reference_scale)
        ),
        "integrated_absolute_mrr_error_m": float(np.sum(np.abs(difference)) * DT_S),
        "cumulative_removal_error_m": abs(
            trace.cumulative_removal_m - reference.cumulative_removal_m
        ),
        "mean_mrr_ratio": float(np.mean(values) / np.mean(reference_values)),
    }


def build_payload() -> dict[str, Any]:
    reference = _run_case("EVENT_DISABLED_REFERENCE", disturbed=False, hold_start_s=None)
    no_action = _run_case("DISTURBED_NO_ACTION", disturbed=True, hold_start_s=None)
    threshold = _run_case(
        "DISTURBED_THRESHOLD_HOLD",
        disturbed=True,
        hold_start_s=THRESHOLD_HOLD_START_S,
    )
    predictive = _run_case(
        "DISTURBED_WARNING_TIMED_HOLD",
        disturbed=True,
        hold_start_s=PREDICTIVE_HOLD_START_S,
    )
    metrics = {
        trace.label: _metrics(trace, reference)
        for trace in (reference, no_action, threshold, predictive)
    }
    no_action_metrics = metrics[no_action.label]
    threshold_metrics = metrics[threshold.label]
    predictive_metrics = metrics[predictive.label]
    checks = {
        "all_cases_complete_equal_dress_progress": all(
            abs(trace.dress_progress_s - DRESS_DURATION_S) <= DT_S + 1.0e-12
            for trace in (reference, no_action, threshold, predictive)
        ),
        "all_cases_complete_equal_active_polish_progress": all(
            abs(trace.polish_progress_s - POLISH_DURATION_S) <= DT_S + 1.0e-12
            for trace in (reference, no_action, threshold, predictive)
        ),
        "disturbed_no_action_crosses_five_percent_peak": (
            no_action_metrics["peak_relative_mrr_deviation"] > 0.05
        ),
        "warning_timed_hold_improves_peak_vs_no_action": (
            predictive_metrics["peak_relative_mrr_deviation"]
            < no_action_metrics["peak_relative_mrr_deviation"]
        ),
        "warning_timed_hold_improves_integrated_error_vs_no_action": (
            predictive_metrics["integrated_absolute_mrr_error_m"]
            < no_action_metrics["integrated_absolute_mrr_error_m"]
        ),
        "warning_timed_hold_improves_cumulative_removal_vs_no_action": (
            predictive_metrics["cumulative_removal_error_m"]
            < no_action_metrics["cumulative_removal_error_m"]
        ),
        "threshold_hold_uses_more_hold_time_than_warning_timed_hold": (
            threshold_metrics["hold_duration_s"] > predictive_metrics["hold_duration_s"]
        ),
        "warning_timed_hold_completes_within_extension_bound": (
            predictive_metrics["cycle_extension_vs_reference_s"] <= 10.0
        ),
    }
    if not all(checks.values()):
        failed = sorted(name for name, value in checks.items() if not value)
        raise RuntimeError(f"hold-feasibility checks failed: {failed}")
    return {
        "artifact_id": "PHASE3_CMP_HOLD_FEASIBILITY_V1",
        "evidence_plane": "SYNTHETIC_SIMULATOR",
        "scope": (
            "CMP-only limiting case using the frozen WP08 equations and an imposed "
            "conditioning-availability boundary; not WP17 closed-loop efficacy."
        ),
        "configuration": {
            "dt_s": DT_S,
            "dress_duration_s": DRESS_DURATION_S,
            "prepare_duration_s": PREPARE_DURATION_S,
            "polish_duration_s": POLISH_DURATION_S,
            "disturbance_start_s": 0.0,
            "disturbance_end_s": DISTURBANCE_END_S,
            "threshold_hold_start_s": THRESHOLD_HOLD_START_S,
            "warning_timed_hold_start_s": PREDICTIVE_HOLD_START_S,
            "warning_time_basis": "7.00 s excursion onset minus WP12 median 2.71 s lead",
            "equal_recipe_completion": True,
        },
        "metrics": metrics,
        "checks": checks,
        "claim_boundary": (
            "The frozen hold/phase-restoration mechanism has a feasible direction in this "
            "single deterministic CMP limiting case. It does not establish integrated "
            "controller benefit, robustness, safety-filter behavior, or real-fab validity."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "reports/control/phase3_hold_feasibility.json",
    )
    args = parser.parse_args()
    payload = build_payload()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"output": str(args.output), "checks": len(payload["checks"])}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
