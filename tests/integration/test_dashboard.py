import urllib.request
import json
import threading
import time
import pytest
from src.semifab_poc.dashboard.server import run_server

@pytest.fixture(scope="module")
def dashboard_server():
    server_thread = threading.Thread(target=run_server, args=(8085,), daemon=True)
    server_thread.start()
    time.sleep(1) # wait for server to start
    yield "http://localhost:8085"

def test_local_smoke_test_succeeds(dashboard_server):
    # Test HTML serving
    req = urllib.request.Request(dashboard_server)
    with urllib.request.urlopen(req) as response:
        assert response.status == 200
        html = response.read().decode('utf-8')
        assert "PowerUPCMP" in html
        assert "SYNTHETIC VALUES:" in html
        assert "Replay validated demo" in html
        assert "Predictive classifier demo" in html
        assert 'value="8.0"' in html
        assert 'value="3.0"' in html
        assert 'value="16"' in html

def test_api_traces(dashboard_server):
    req = urllib.request.Request(f"{dashboard_server}/api/traces")
    with urllib.request.urlopen(req) as response:
        assert response.status == 200
        payload = json.loads(response.read().decode('utf-8'))
        assert payload["traces"] == [
            "stakeholder-demo-normal-baseline.json",
            "stakeholder-demo-stable-polish-fault.json",
            "stakeholder-demo-grid-interruption.json",
            "stakeholder-demo-power-water-disturbance.json",
        ]

def test_baseline_replay_stream_header(dashboard_server):
    req = urllib.request.Request(
        f"{dashboard_server}/api/stream/stakeholder-demo-normal-baseline.json"
    )
    with urllib.request.urlopen(req, timeout=10) as response:
        assert response.status == 200
        line = response.readline().decode("utf-8").strip()

    assert line.startswith("data:")
    payload = json.loads(line.removeprefix("data:").strip())
    assert payload["scenario"]["family"] == "NORMAL"
    assert payload["summary"]["peak_warning_probability"] == 0.05
    assert payload["actions"] == []
    assert payload["safety_decisions"] == []

def test_stakeholder_replay_stream_header(dashboard_server):
    req = urllib.request.Request(
        f"{dashboard_server}/api/stream/stakeholder-demo-stable-polish-fault.json"
    )
    with urllib.request.urlopen(req, timeout=10) as response:
        assert response.status == 200
        line = response.readline().decode("utf-8").strip()

    assert line.startswith("data:")
    payload = json.loads(line.removeprefix("data:").strip())
    assert payload["scenario"]["family"] == "PUMP_TRIP"
    assert payload["scenario"]["event_start_s"] == 8.0
    assert payload["summary"]["stable_polish_start_s"] == 4.0
    assert payload["summary"]["final_status"] == "Recovered after stable-polish synthetic safe hold"
    assert payload["actions"][0]["action_type"] == "SAFE_HOLD"
    assert payload["safety_decisions"][0]["outcome"] == "APPROVED"

@pytest.mark.parametrize(
    ("trace_name", "family", "peak_probability"),
    [
        ("stakeholder-demo-grid-interruption.json", "GRID_INTERRUPTION", 0.93),
        ("stakeholder-demo-power-water-disturbance.json", "POWER_WATER_DISTURBANCE", 0.96),
    ],
)
def test_additional_fault_replay_stream_headers(
    dashboard_server, trace_name, family, peak_probability
):
    req = urllib.request.Request(f"{dashboard_server}/api/stream/{trace_name}")
    with urllib.request.urlopen(req, timeout=10) as response:
        assert response.status == 200
        line = response.readline().decode("utf-8").strip()

    assert line.startswith("data:")
    payload = json.loads(line.removeprefix("data:").strip())
    assert payload["scenario"]["family"] == family
    assert payload["summary"]["peak_warning_probability"] == peak_probability
    assert payload["actions"][0]["action_type"] == "SAFE_HOLD"
    assert payload["safety_decisions"][0]["outcome"] == "APPROVED"

def test_live_simulation_streams_model_predictions(dashboard_server):
    req = urllib.request.Request(
        f"{dashboard_server}/api/simulate?"
        "family=PUMP_TRIP&controller=PREDICTIVE&duration=16&"
        "grid_volt=1.0&valve_pos=1.0&sensor_bias=0&"
        "ev_start=8.0&ev_dur=3.0&seed=123"
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        assert response.status == 200
        saw_prediction = False
        saw_pre_event_prediction = False
        saw_post_event_prediction = False
        saw_hold = False
        for _ in range(200):
            line = response.readline().decode("utf-8").strip()
            if not line.startswith("data:"):
                continue
            payload = json.loads(line.removeprefix("data:").strip())
            truth = payload.get("truth")
            if truth and truth.get("cmp_mode") == "HOLD":
                saw_hold = True
            prediction = payload.get("prediction")
            if prediction is None:
                if saw_pre_event_prediction and saw_post_event_prediction and saw_hold:
                    break
                continue
            assert "warning_probability" in prediction
            assert "conformal_prediction_set" in prediction
            assert "uncertainty_valid" in prediction
            assert isinstance(prediction["warning_probability"], float)
            saw_prediction = True
            if prediction["timestamp_s"] < 8.0:
                saw_pre_event_prediction = True
            else:
                saw_post_event_prediction = True
            if saw_pre_event_prediction and saw_post_event_prediction and saw_hold:
                break

        assert saw_prediction, "live simulation did not stream model predictions"
        assert saw_pre_event_prediction, "live simulation did not stream a pre-event warning baseline"
        assert saw_post_event_prediction, "live simulation did not stream a post-event model prediction"
        assert saw_hold, "live simulation did not enter HOLD under utility protection"

def test_no_unique_model_or_control_logic_in_dashboard():
    # Structural test: just confirm the files are only display code
    from pathlib import Path
    dashboard_dir = Path(__file__).parent.parent.parent / "src" / "semifab_poc" / "dashboard"
    app_js = dashboard_dir / "app.js"
    assert app_js.exists()
    content = app_js.read_text()
    assert "updateDashboard" in content
    assert "$('sim-controller').value = 'PREDICTIVE'" in content
    assert "$('sim-event-start').value = '8.0'" in content
    assert "$('sim-event-duration').value = '3.0'" in content
    assert "$('sim-duration').value = '16'" in content
    # No logic indicating model execution
    assert "class Controller" not in content
