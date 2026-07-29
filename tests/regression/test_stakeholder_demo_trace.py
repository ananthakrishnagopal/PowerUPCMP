import json
from pathlib import Path


TRACE_PATH = Path(__file__).with_name("stakeholder-demo-predictive-hold.json")


def test_stakeholder_demo_trace_shape_and_story() -> None:
    payload = json.loads(TRACE_PATH.read_text(encoding="utf-8"))

    assert payload["metadata"]["synthetic_demo_artifact"] is True
    assert payload["metadata"]["evidence_plane"] == "SYNTHETIC_SIMULATOR_DEMO"
    for key in ("metadata", "scenario", "truth_rows", "predictions", "actions", "safety_decisions", "summary"):
        assert key in payload

    truth_times = [row["timestamp_s"] for row in payload["truth_rows"]]
    prediction_times = [row["timestamp_s"] for row in payload["predictions"]]
    assert truth_times == sorted(truth_times)
    assert prediction_times == sorted(prediction_times)
    assert truth_times[0] == prediction_times[0]
    assert truth_times[-1] == prediction_times[-1]

    threshold_crossings = [
        row for row in payload["predictions"]
        if row["warning_probability"] >= row["hold_threshold"]
    ]
    assert threshold_crossings

    hold_actions = [
        action for action in payload["actions"]
        if action["action_type"] == "SAFE_HOLD"
    ]
    assert hold_actions
    assert threshold_crossings[0]["timestamp_s"] <= hold_actions[0]["timestamp_s"]

    final_hold_decisions = [
        decision for decision in payload["safety_decisions"]
        if decision["final_action_type"] == "SAFE_HOLD"
    ]
    assert final_hold_decisions
    assert final_hold_decisions[0]["outcome"] == "APPROVED"

    modes = {row["cmp_mode"] for row in payload["truth_rows"]}
    assert {"DRESS", "HOLD", "RECOVER", "POLISH"} <= modes
    assert payload["summary"]["peak_warning_probability"] >= 0.9
