import sys
import urllib.parse
from dataclasses import dataclass
sys.path.insert(0, "/home/akki/cmp_modelling/src")

from semifab_poc.dashboard.server import DashboardHandler

class MockRequest:
    def makefile(self, *args, **kwargs):
        from io import BytesIO
        return BytesIO(b"")

class MockServer:
    pass

class TestHandler(DashboardHandler):
    def __init__(self, path):
        self.wfile = sys.stdout.buffer
        self.path = path
        self.request = MockRequest()
        self.client_address = ("127.0.0.1", 12345)
        self.server = MockServer()
    def setup(self): pass
    def finish(self): pass
    def send_response(self, *args, **kwargs): pass
    def send_header(self, *args, **kwargs): pass
    def end_headers(self, *args, **kwargs): pass

def run_test(family, controller):
    path = f"/api/simulate?family={family}&controller={controller}&seed=123&duration=15&ev_start=5.0&ev_dur=5.0"
    handler = TestHandler(path)
    
    # Capture output
    import io
    old_stdout = sys.stdout
    sys.stdout = io.StringIO()
    
    try:
        handler._handle_simulate(urllib.parse.urlparse(handler.path))
        output = sys.stdout.getvalue()
        sys.stdout = old_stdout
        
        # Check for errors in output
        if "error" in output.lower():
            print(f"[{family} | {controller}] ERROR found in output stream")
            return
            
        # Parse the last truth row to see if HOLD was reached or not
        lines = [line for line in output.split("\n") if line.strip()]
        last_line = lines[-1]
        
        if "HOLD" in output and controller == "PREDICTIVE" and family != "NORMAL":
            print(f"[{family} | {controller}] SUCCESS: SAFE_HOLD activated and simulation completed.")
        elif "HOLD" not in output and controller == "NO_ACTION" and family != "NORMAL":
            print(f"[{family} | {controller}] SUCCESS: No HOLD activated (Wafer damaged as expected).")
        elif family == "NORMAL":
            if "HOLD" in output:
                print(f"[{family} | {controller}] ERROR: False positive HOLD triggered in NORMAL mode!")
            else:
                print(f"[{family} | {controller}] SUCCESS: Normal operation finished safely.")
        else:
            print(f"[{family} | {controller}] UNEXPECTED OUTCOME! Last line: {last_line[:100]}")
    except Exception as e:
        sys.stdout = old_stdout
        print(f"[{family} | {controller}] EXCEPTION THROWN: {e}")

scenarios = ["NORMAL", "GRID_SAG", "PUMP_TRIP"]
controllers = ["NO_ACTION", "PREDICTIVE"]

for s in scenarios:
    for c in controllers:
        run_test(s, c)
