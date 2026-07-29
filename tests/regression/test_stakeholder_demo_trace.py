import json
from pathlib import Path


TRACE_PATH = Path(__file__).with_name("stakeholder-demo-stable-polish-fault.json")
BASELINE_TRACE_PATH = Path(__file__).with_name("stakeholder-demo-normal-baseline.json")


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
    fault_time = payload["summary"]["fault_time_s"]
    stable_polish_start = payload["summary"]["stable_polish_start_s"]
    stable_rows = [
        row for row in payload["truth_rows"]
        if stable_polish_start <= row["timestamp_s"] < fault_time
    ]
    assert stable_rows
    assert {row["cmp_mode"] for row in stable_rows} == {"POLISH"}
    stable_mrr = [row["cmp_mrr_m_s"] for row in stable_rows]
    assert min(stable_mrr) >= 1.96e-08
    assert max(stable_mrr) <= 2.01e-08
    assert threshold_crossings[0]["timestamp_s"] > fault_time

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
    assert {"DRESS", "PREPARE", "HOLD", "RECOVER", "POLISH"} <= modes
    assert payload["summary"]["peak_warning_probability"] >= 0.9


def test_stakeholder_baseline_trace_shape_and_story() -> None:
    payload = json.loads(BASELINE_TRACE_PATH.read_text(encoding="utf-8"))

    assert payload["metadata"]["synthetic_demo_artifact"] is True
    assert payload["scenario"]["family"] == "NORMAL"
    assert payload["actions"] == []
    assert payload["safety_decisions"] == []

    truth_times = [row["timestamp_s"] for row in payload["truth_rows"]]
    prediction_times = [row["timestamp_s"] for row in payload["predictions"]]
    assert truth_times == sorted(truth_times)
    assert truth_times == prediction_times

    assert not any(row["event_active"] for row in payload["truth_rows"])
    assert "HOLD" not in {row["cmp_mode"] for row in payload["truth_rows"]}
    assert max(row["warning_probability"] for row in payload["predictions"]) < 0.8

    stable_rows = [
        row for row in payload["truth_rows"]
        if payload["summary"]["stable_polish_start_s"] <= row["timestamp_s"] < 16.0
    ]
    assert stable_rows
    assert {row["cmp_mode"] for row in stable_rows} == {"POLISH"}
    stable_mrr = [row["cmp_mrr_m_s"] for row in stable_rows]
    assert min(stable_mrr) >= 1.96e-08
    assert max(stable_mrr) <= 2.01e-08
