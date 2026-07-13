from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest
import yaml

from semifab_poc.config import load_runtime_config
from semifab_poc.control.contracts import (
    ActionType,
    ControlContractError,
    SafetyOutcome,
    load_control_contract_bundle,
    load_predictive_controller_contract,
    verify_canonical_vocabularies,
    verify_predictor_binding,
)
from semifab_poc.data.schema import canonical_signal_definitions
from semifab_poc.simulation.cmp import CmpMode, CmpSubsystem


ROOT = Path(__file__).parents[2]
PREDICTIVE = ROOT / "configs/controllers/predictive.yaml"
BASELINES = ROOT / "configs/controllers/baselines.yaml"
SAFETY = ROOT / "configs/controllers/safety.yaml"


def _bundle():
    return load_control_contract_bundle(PREDICTIVE, BASELINES, SAFETY)


def test_control_contract_bundle_loads_and_cross_validates() -> None:
    bundle = _bundle()

    assert bundle.predictive.schema_version == "1.0.0"
    assert bundle.baselines.schema_version == "1.0.0"
    assert bundle.safety.schema_version == "1.0.0"
    assert bundle.predictive.decision_period_s == bundle.safety.decision_period_s
    assert set(bundle.safety.outcomes) == set(SafetyOutcome)


def test_predictor_artifacts_and_canonical_vocabularies_are_exactly_bound() -> None:
    bundle = _bundle()

    verify_predictor_binding(bundle.predictive, ROOT)
    verify_canonical_vocabularies(
        bundle.safety,
        ROOT / "orchestration/canonical_schema.yaml",
    )


def test_primary_policy_enables_only_noncompensating_supervisory_actions() -> None:
    contract = _bundle().predictive

    assert set(contract.action_policy.enabled_actions) == {
        ActionType.NO_ACTION,
        ActionType.ADVISORY_WARNING,
        ActionType.SAFE_HOLD,
        ActionType.CONTROLLED_RESUME,
    }
    assert set(contract.action_policy.disabled_actions) == {
        ActionType.VFD_COMMAND_ADJUSTMENT,
        ActionType.VALVE_ADJUSTMENT,
        ActionType.CMP_DOWNFORCE_REDUCTION,
        ActionType.HEAD_SPEED_REDUCTION,
        ActionType.PLATEN_SPEED_REDUCTION,
    }
    assert contract.action_policy.attribution_is_advisory_only
    assert not contract.action_policy.reinforcement_learning_allowed


def test_numeric_supervisory_envelopes_are_reductions_inside_plant_bounds() -> None:
    bundle = _bundle()
    runtime = load_runtime_config(ROOT / "configs/default.yaml")
    envelopes = bundle.safety.action_envelopes

    vfd = envelopes[ActionType.VFD_COMMAND_ADJUSTMENT]
    valve = envelopes[ActionType.VALVE_ADJUSTMENT]
    pressure = envelopes[ActionType.CMP_DOWNFORCE_REDUCTION]
    head = envelopes[ActionType.HEAD_SPEED_REDUCTION]
    platen = envelopes[ActionType.PLATEN_SPEED_REDUCTION]

    assert vfd.maximum <= 1.0
    assert valve.maximum <= 1.0
    assert pressure.maximum <= runtime.cmp.nominal_contact_pressure_pa
    assert pressure.minimum >= 0.0
    assert head.maximum <= abs(runtime.cmp.nominal_head_angular_speed_rad_s)
    assert head.minimum >= 0.0
    assert platen.maximum <= abs(runtime.cmp.nominal_platen_angular_speed_rad_s)
    assert platen.minimum >= 0.0
    assert runtime.cmp.pressure_exponent > 0.0
    assert runtime.cmp.velocity_exponent > 0.0
    assert all(not envelope.primary_enabled for envelope in envelopes.values())


def test_action_targets_and_units_match_canonical_physical_signals() -> None:
    definitions = canonical_signal_definitions()
    for envelope in _bundle().safety.action_envelopes.values():
        definition = definitions[envelope.target]
        assert definition["unit"] == envelope.unit


def test_hold_and_release_thresholds_have_strict_hysteresis() -> None:
    bundle = _bundle()
    process_threshold = bundle.baselines.process_threshold
    utility_threshold = bundle.baselines.utility_threshold_comparator
    continuation = bundle.safety.continuation_envelope
    release = bundle.safety.release_envelope

    assert continuation.low_ratio < release.lower_ratio <= 1.0
    assert 1.0 <= release.upper_ratio < continuation.high_ratio
    assert (
        release.maximum_temperature_deviation_k
        < continuation.maximum_temperature_deviation_k
    )
    assert utility_threshold.release_dwell_s == release.continuous_valid_dwell_s
    assert (
        process_threshold.lower_relative_fraction
        < process_threshold.release_lower_relative_fraction
        < 1.0
        < process_threshold.release_upper_relative_fraction
        < process_threshold.upper_relative_fraction
    )
    assert continuation.automatic_hold_modes == ("PREPARE", "POLISH")
    assert (
        bundle.predictive.risk_policy.resume_maximum_probability
        < bundle.predictive.risk_policy.advisory_probability
        < bundle.predictive.risk_policy.hold_probability
    )


def test_primary_and_secondary_threshold_comparators_are_both_frozen() -> None:
    bundle = _bundle()

    assert (
        bundle.baselines.process_threshold.controller_id
        == bundle.predictive.evaluation.primary_threshold_controller_id
    )
    assert bundle.baselines.process_threshold.target_signal_id == "cmp.mrr"
    assert (
        bundle.baselines.utility_threshold_comparator.controller_id
        == bundle.predictive.evaluation.required_secondary_comparator
    )
    assert not bundle.baselines.process_threshold.warning_probability_visible
    assert not bundle.baselines.utility_threshold_comparator.warning_probability_visible


def test_interrupted_dress_has_a_valid_existing_cmp_transition_route() -> None:
    route = _bundle().predictive.phase_clock.interrupted_dress_route
    expected = (CmpMode.HOLD, CmpMode.RECOVER, CmpMode.PREPARE, CmpMode.DRESS)

    assert tuple(CmpMode(value) for value in route) == expected
    allowed = CmpSubsystem._ALLOWED_TRANSITIONS
    assert CmpMode.RECOVER in allowed[CmpMode.HOLD]
    assert CmpMode.PREPARE in allowed[CmpMode.RECOVER]
    assert CmpMode.DRESS in allowed[CmpMode.PREPARE]


def test_phase_clock_and_metrics_prevent_hold_only_score_gaming() -> None:
    contract = _bundle().predictive
    required = {
        "ACTIVE_POLISH_PEAK_MRR_DEVIATION",
        "ACTIVE_POLISH_INTEGRATED_ABSOLUTE_MRR_ERROR",
        "COMPLETED_RECIPE_CUMULATIVE_REMOVAL_ERROR",
        "HOLD_DURATION",
        "RECOVERY_DURATION",
        "CYCLE_TIME_EXTENSION",
        "ACTION_EFFORT",
    }

    assert contract.phase_clock.freeze_states == ("HOLDING", "RECOVERING")
    assert contract.phase_clock.restore_interrupted_phase
    assert contract.phase_clock.equal_recipe_completion_required
    assert set(contract.objective.evaluation_metrics) == required
    assert contract.evaluation.maximum_cycle_extension_s == 10.0


def test_controller_test_seeds_are_separate_from_wp12_and_wp13() -> None:
    bundle = _bundle()
    warning = yaml.safe_load(
        (ROOT / "configs/models/early_warning.yaml").read_text(encoding="utf-8")
    )
    attribution = yaml.safe_load(
        (ROOT / "configs/models/attribution.yaml").read_text(encoding="utf-8")
    )
    prior_starts = {
        int(value)
        for name, value in warning["splits"].items()
        if name.endswith("_seed_start")
    }
    prior_starts.update(
        int(value)
        for name, value in attribution["splits"].items()
        if name.endswith("_seed_start")
    )
    controller_starts = {
        bundle.predictive.evaluation.controller_development_seed_start,
        bundle.predictive.evaluation.primary_test_seed_start,
        bundle.predictive.evaluation.robustness_seed_start,
    }

    assert prior_starts.isdisjoint(controller_starts)
    assert min(controller_starts) > max(prior_starts)
    assert bundle.predictive.evaluation.prohibit_wp12_wp13_seeds_in_primary_test


def test_synthetic_battery_reserve_is_feasible_but_nonzero() -> None:
    bundle = _bundle()
    runtime = load_runtime_config(ROOT / "configs/default.yaml")
    reserve = (
        bundle.safety.release_envelope.battery_reserve_factor
        * runtime.electrical.nominal_ups_load_w
        / runtime.electrical.inverter_efficiency
        * (
            bundle.predictive.predictor.horizon_s
            + bundle.safety.state_machine.recovery_dwell_s
        )
    )

    assert reserve > 0.0
    assert reserve < runtime.electrical.battery_capacity_j


def test_unknown_predictive_key_is_rejected(tmp_path: Path) -> None:
    payload = yaml.safe_load(PREDICTIVE.read_text(encoding="utf-8"))
    payload["unreviewed_override"] = True
    path = tmp_path / "invalid.yaml"
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    with pytest.raises(ControlContractError, match="unreviewed_override"):
        load_predictive_controller_contract(path)


def test_probability_hysteresis_cannot_be_reversed(tmp_path: Path) -> None:
    payload = deepcopy(yaml.safe_load(PREDICTIVE.read_text(encoding="utf-8")))
    payload["risk_policy"]["resume_maximum_probability"] = 0.60
    path = tmp_path / "invalid.yaml"
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    with pytest.raises(ControlContractError, match="resume < advisory < hold"):
        load_predictive_controller_contract(path)
