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
        assert "Replay stakeholder demo" in html
        assert "Live utility threshold protection" in html
        assert 'value="7.2"' in html
        assert 'value="4.0"' in html
        assert 'value="16"' in html

def test_api_traces(dashboard_server):
    req = urllib.request.Request(f"{dashboard_server}/api/traces")
    with urllib.request.urlopen(req) as response:
        assert response.status == 200
        data = response.read().decode('utf-8')
        assert "traces" in data
        assert "stakeholder-demo-predictive-hold.json" in data

def test_live_simulation_streams_model_predictions(dashboard_server):
    req = urllib.request.Request(
        f"{dashboard_server}/api/simulate?"
        "family=PUMP_TRIP&controller=UTILITY_THRESHOLD&duration=16&"
        "grid_volt=1.0&valve_pos=1.0&sensor_bias=0&"
        "ev_start=7.2&ev_dur=4.0&seed=123"
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        assert response.status == 200
        saw_prediction = False
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
                if saw_prediction and saw_hold:
                    break
                continue
            assert prediction["timestamp_s"] >= 7.2
            assert "warning_probability" in prediction
            assert "conformal_prediction_set" in prediction
            assert "uncertainty_valid" in prediction
            assert isinstance(prediction["warning_probability"], float)
            saw_prediction = True
            if saw_hold:
                break

        assert saw_prediction, "live simulation did not stream a post-event model prediction"
        assert saw_hold, "live simulation did not enter HOLD under utility protection"

def test_no_unique_model_or_control_logic_in_dashboard():
    # Structural test: just confirm the files are only display code
    from pathlib import Path
    dashboard_dir = Path(__file__).parent.parent.parent / "src" / "semifab_poc" / "dashboard"
    app_js = dashboard_dir / "app.js"
    assert app_js.exists()
    content = app_js.read_text()
    assert "updateDashboard" in content
    assert "$('sim-controller').value = 'UTILITY_THRESHOLD'" in content
    assert "$('sim-event-duration').value = '4.0'" in content
    assert "$('sim-duration').value = '16'" in content
    # No logic indicating model execution
    assert "class Controller" not in content
