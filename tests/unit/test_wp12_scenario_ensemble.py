from pathlib import Path

from scripts.validate_wp12_early_warning import (
    observation_robustness_scenarios,
    scenarios_for_split,
    structural_null_scenarios,
    unseen_compound_scenarios,
)
from semifab_poc.simulation.chain import ChainEventKind
from semifab_poc.config import load_runtime_config
from semifab_poc.models.early_warning import load_early_warning_config


ROOT = Path(__file__).resolve().parents[2]


def test_every_frozen_wp12_scenario_constructs_and_validates() -> None:
    warning = load_early_warning_config(ROOT / "configs" / "models" / "early_warning.yaml")
    runtime = load_runtime_config(ROOT / "configs" / "default.yaml")
    expected_families = set(warning.splits.primary_families)
    for split in ("TRAIN", "CALIBRATION", "CONFORMAL_CALIBRATION", "TEST"):
        scenarios = scenarios_for_split(warning, split)
        assert {scenario.family.value for scenario in scenarios} == expected_families
        for scenario in scenarios:
            scenario.validate(runtime, warning.simulation.duration_s)
        for family in (
            ChainEventKind.GRID_INTERRUPTION,
            ChainEventKind.PUMP_TRIP,
            ChainEventKind.VALVE_RESTRICTION,
            ChainEventKind.TOOL_DEMAND_SPIKE,
        ):
            family_scenarios = [scenario for scenario in scenarios if scenario.family is family]
            anchor = family_scenarios[-1]
            assert anchor.event_start_s == warning.simulation.full_dress_anchor_start_s
            assert (
                anchor.event_start_s + anchor.event_duration_s
                == warning.simulation.full_dress_anchor_end_s
            )
    compound = unseen_compound_scenarios(warning)
    structural = structural_null_scenarios(warning)
    assert len(compound) == warning.splits.runs_per_family.unseen_compound
    assert len(structural) == warning.splits.runs_per_family.structural_null
    for scenario in compound + structural:
        scenario.validate(runtime, warning.simulation.duration_s)


def test_observation_robustness_selects_median_and_maximum_per_family() -> None:
    warning = load_early_warning_config(ROOT / "configs" / "models" / "early_warning.yaml")
    test_scenarios = scenarios_for_split(warning, "TEST")
    selected = observation_robustness_scenarios(warning, test_scenarios)

    assert len(selected) == 2 * len(warning.splits.primary_families)
    for family_name in warning.splits.primary_families:
        family_test = [
            scenario for scenario in test_scenarios if scenario.family.value == family_name
        ]
        family_selected = [
            scenario for scenario in selected if scenario.family.value == family_name
        ]
        assert family_selected == [family_test[len(family_test) // 2], family_test[-1]]
