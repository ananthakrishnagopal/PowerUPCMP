from pathlib import Path

from semifab_poc.simulation.scenario import load_scenarios


def test_fixed_scenario_replay_is_deterministic() -> None:
    scenario = load_scenarios(Path("configs/scenarios/library.yaml"))["compound_disturbance"]
    first = tuple(
        (event.event_id, value, event.initiating_cause.value)
        for event, value in scenario.values_at(1.10)
    )
    second = tuple(
        (event.event_id, value, event.initiating_cause.value)
        for event, value in scenario.values_at(1.10)
    )
    assert first == second == (
        ("compound-sag", -0.25, "GRID_VOLTAGE_SAG"),
        ("compound-demand", 0.0002, "TOOL_DEMAND_SPIKE"),
    )
