import urllib.request
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
        assert "PowerUPCMP Results Dashboard" in html
        assert "SYNTHETIC VALUES:" in html
        assert "SPATIAL PROXY:" in html

def test_api_traces(dashboard_server):
    req = urllib.request.Request(f"{dashboard_server}/api/traces")
    with urllib.request.urlopen(req) as response:
        assert response.status == 200
        data = response.read().decode('utf-8')
        assert "traces" in data

def test_no_unique_model_or_control_logic_in_dashboard():
    # Structural test: just confirm the files are only display code
    from pathlib import Path
    dashboard_dir = Path(__file__).parent.parent.parent / "src" / "semifab_poc" / "dashboard"
    app_js = dashboard_dir / "app.js"
    assert app_js.exists()
    content = app_js.read_text()
    assert "updateDashboard" in content
    # No logic indicating model execution
    assert "class Controller" not in content
