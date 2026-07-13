#!/usr/bin/env python3
"""Validate the frozen Phase 3 control/safety contracts without running control."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

from semifab_poc.config import load_runtime_config
from semifab_poc.control.contracts import (
    ActionType,
    file_sha256,
    load_control_contract_bundle,
    verify_canonical_vocabularies,
    verify_predictor_binding,
)


ROOT = Path(__file__).resolve().parents[1]
PREDICTIVE_PATH = ROOT / "configs/controllers/predictive.yaml"
BASELINES_PATH = ROOT / "configs/controllers/baselines.yaml"
SAFETY_PATH = ROOT / "configs/controllers/safety.yaml"


def build_validation_payload() -> dict[str, Any]:
    bundle = load_control_contract_bundle(
        PREDICTIVE_PATH,
        BASELINES_PATH,
        SAFETY_PATH,
    )
    verify_predictor_binding(bundle.predictive, ROOT)
    verify_canonical_vocabularies(
        bundle.safety,
        ROOT / "orchestration/canonical_schema.yaml",
    )
    runtime = load_runtime_config(ROOT / "configs/default.yaml")

    envelopes = bundle.safety.action_envelopes
    primary_actions = set(bundle.predictive.action_policy.enabled_actions)
    numeric_actions = set(envelopes)
    disabled_actions = set(bundle.predictive.action_policy.disabled_actions)

    reserve_j = (
        bundle.safety.release_envelope.battery_reserve_factor
        * runtime.electrical.nominal_ups_load_w
        / runtime.electrical.inverter_efficiency
        * (
            bundle.predictive.predictor.horizon_s
            + bundle.safety.state_machine.recovery_dwell_s
        )
    )

    objective = bundle.predictive.objective
    hold_threshold = bundle.predictive.risk_policy.hold_probability
    resume_threshold = bundle.predictive.risk_policy.resume_maximum_probability
    run_score_at_hold_threshold = objective.expected_excursion_weight * hold_threshold
    projected_hold_score = (
        objective.phase_delay_weight
        + objective.hold_duration_weight
        + objective.action_transition_weight
    )
    projected_continue_hold_score = (
        objective.phase_delay_weight + objective.hold_duration_weight
    )
    resume_score_at_release_threshold = (
        objective.expected_excursion_weight * resume_threshold
        + objective.action_transition_weight
    )

    plant_bound_checks = {
        "vfd_supervisory_max_not_above_command_max": (
            envelopes[ActionType.VFD_COMMAND_ADJUSTMENT].maximum <= 1.0
        ),
        "valve_supervisory_max_not_above_full_open": (
            envelopes[ActionType.VALVE_ADJUSTMENT].maximum <= 1.0
        ),
        "downforce_action_is_reduction_only": (
            envelopes[ActionType.CMP_DOWNFORCE_REDUCTION].maximum
            <= runtime.cmp.nominal_contact_pressure_pa
        ),
        "head_action_is_reduction_only": (
            envelopes[ActionType.HEAD_SPEED_REDUCTION].maximum
            <= abs(runtime.cmp.nominal_head_angular_speed_rad_s)
        ),
        "platen_action_is_reduction_only": (
            envelopes[ActionType.PLATEN_SPEED_REDUCTION].maximum
            <= abs(runtime.cmp.nominal_platen_angular_speed_rad_s)
        ),
        "preston_exponents_are_positive": (
            runtime.cmp.pressure_exponent > 0.0
            and runtime.cmp.velocity_exponent > 0.0
        ),
    }

    checks = {
        "strict_cross_contract_validation": True,
        "predictor_artifact_binding_verified": True,
        "canonical_action_and_safety_vocabularies_match": True,
        "primary_action_set_is_exactly_four": primary_actions
        == {
            ActionType.NO_ACTION,
            ActionType.ADVISORY_WARNING,
            ActionType.SAFE_HOLD,
            ActionType.CONTROLLED_RESUME,
        },
        "all_numeric_actions_disabled_in_primary": numeric_actions == disabled_actions
        and all(not item.primary_enabled for item in envelopes.values()),
        "all_numeric_envelopes_inside_plant_authority": all(plant_bound_checks.values()),
        "hold_score_below_run_score_at_frozen_hold_gate": (
            projected_hold_score < run_score_at_hold_threshold
        ),
        "resume_score_below_continued_hold_at_frozen_release_gate": (
            resume_score_at_release_threshold < projected_continue_hold_score
        ),
        "hold_and_recovery_freeze_recipe_clock": (
            bundle.predictive.phase_clock.freeze_states == ("HOLDING", "RECOVERING")
            and bundle.safety.state_machine.freeze_recipe_clock_in == ("HOLD", "RECOVER")
        ),
        "interrupted_phase_restoration_required": (
            bundle.predictive.phase_clock.restore_interrupted_phase
            and bundle.safety.state_machine.restore_interrupted_phase
        ),
        "equal_recipe_completion_required": (
            bundle.predictive.phase_clock.equal_recipe_completion_required
        ),
        "battery_reserve_positive_and_feasible": (
            0.0 < reserve_j < runtime.electrical.battery_capacity_j
        ),
        "controller_seed_ranges_are_new": (
            bundle.predictive.evaluation.controller_development_seed_start >= 120_000
            and bundle.predictive.evaluation.primary_test_seed_start >= 120_000
            and bundle.predictive.evaluation.robustness_seed_start >= 120_000
        ),
        "paired_comparison_tolerances_frozen": (
            math.isclose(
                bundle.predictive.evaluation.minimum_threshold_relative_improvement,
                0.05,
            )
            and math.isclose(
                bundle.predictive.evaluation.maximum_threshold_relative_worsening,
                0.05,
            )
        ),
        "primary_threshold_uses_observed_process_mrr": (
            bundle.baselines.process_threshold.target_signal_id == "cmp.mrr"
            and bundle.baselines.process_threshold.controller_id
            == bundle.predictive.evaluation.primary_threshold_controller_id
        ),
        "upstream_utility_threshold_is_mandatory_secondary_comparator": (
            bundle.baselines.utility_threshold_comparator.controller_id
            == bundle.predictive.evaluation.required_secondary_comparator
        ),
        "safety_utility_hold_does_not_preempt_dress_comparison": (
            bundle.safety.continuation_envelope.automatic_hold_modes
            == ("PREPARE", "POLISH")
        ),
        "zero_final_constraint_violations_required": (
            bundle.predictive.evaluation.require_zero_final_constraint_violations
            and bundle.safety.final_action_required
        ),
        "controller_independence_required": bundle.safety.controller_imports_forbidden,
        "reinforcement_learning_absent": (
            not bundle.predictive.action_policy.reinforcement_learning_allowed
        ),
        "controller_budget_inside_decision_period": (
            bundle.predictive.latency_budget.end_to_end_p95_s
            < bundle.predictive.decision_period_s
        ),
    }
    if not all(checks.values()):
        failed = sorted(name for name, passed in checks.items() if not passed)
        raise RuntimeError(f"Phase 3 control-contract checks failed: {failed}")

    return {
        "artifact_id": "PHASE3_CONTROL_SAFETY_CONTRACT_VALIDATION_V1",
        "evidence_plane": "SYNTHETIC_SIMULATOR",
        "scope": "Scientific configuration/contract validation only; no controller runtime or efficacy result.",
        "contract_files": {
            str(PREDICTIVE_PATH.relative_to(ROOT)): file_sha256(PREDICTIVE_PATH),
            str(BASELINES_PATH.relative_to(ROOT)): file_sha256(BASELINES_PATH),
            str(SAFETY_PATH.relative_to(ROOT)): file_sha256(SAFETY_PATH),
        },
        "bound_predictor": {
            "target_id": bundle.predictive.predictor.target_id,
            "model_kind": bundle.predictive.predictor.model_kind,
            "horizon_s": bundle.predictive.predictor.horizon_s,
            "artifact_sha256": bundle.predictive.predictor.artifact_sha256,
            "metadata_sha256": bundle.predictive.predictor.metadata_sha256,
            "model_config_sha256": bundle.predictive.predictor.model_config_sha256,
            "required_topology": bundle.predictive.predictor.required_topology,
        },
        "primary_enabled_actions": sorted(action.value for action in primary_actions),
        "primary_disabled_numeric_actions": sorted(action.value for action in numeric_actions),
        "comparators": {
            "required_primary": bundle.baselines.process_threshold.controller_id,
            "required_secondary": (
                bundle.baselines.utility_threshold_comparator.controller_id
            ),
        },
        "plant_bound_checks": plant_bound_checks,
        "derived_values": {
            "battery_release_reserve_j": reserve_j,
            "run_score_at_hold_threshold": run_score_at_hold_threshold,
            "projected_hold_score": projected_hold_score,
            "resume_score_at_release_threshold": resume_score_at_release_threshold,
            "projected_continue_hold_score": projected_continue_hold_score,
            "decision_period_s": bundle.predictive.decision_period_s,
            "controller_p95_budget_s": bundle.predictive.latency_budget.controller_p95_s,
            "end_to_end_p95_budget_s": bundle.predictive.latency_budget.end_to_end_p95_s,
        },
        "checks": checks,
        "claim_boundary": (
            "The frozen contracts are internally consistent and bounded by the current "
            "synthetic plant. This does not show controller benefit, closed-loop safety, "
            "equipment protection, or real production readiness."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "reports/control/phase3_control_contract_validation.json",
    )
    args = parser.parse_args()
    payload = build_validation_payload()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"output": str(args.output), "checks": len(payload["checks"])}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
