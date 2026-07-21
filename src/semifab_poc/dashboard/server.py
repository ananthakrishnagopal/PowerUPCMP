"""Dashboard server with live physics simulation via IntegratedRuntime."""

import http.server
import socketserver
import json
import os
import sys
import time
import uuid
import random
import urllib.parse
from dataclasses import replace
from pathlib import Path

PORT = 8080
DASHBOARD_DIR = Path(__file__).parent
PROJECT_ROOT = DASHBOARD_DIR.parent.parent.parent
SRC_ROOT = PROJECT_ROOT / "src"


class DashboardHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DASHBOARD_DIR), **kwargs)

    def do_GET(self):
        parsed_path = urllib.parse.urlparse(self.path)
        path = parsed_path.path

        # Trace names are selected from the local inventory; never resolve a
        # user-provided path outside that directory.
        trace_dir = PROJECT_ROOT / "tests" / "regression"
        trace_name = urllib.parse.unquote(path.rsplit('/', 1)[-1])
        trace_path = trace_dir / trace_name
        valid_trace = (
            trace_name.endswith(".json")
            and trace_path.parent == trace_dir
            and trace_path.is_file()
        )

        if path == '/api/traces':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            traces = []
            if trace_dir.exists():
                for f in trace_dir.glob("*.json"):
                    traces.append(f.name)
            response = json.dumps({"traces": traces})
            self.wfile.write(response.encode('utf-8'))
            return

        elif path.startswith('/api/traces/'):
            if valid_trace:
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                with open(trace_path, 'rb') as f:
                    self.wfile.write(f.read())
            else:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b'{"error": "Not Found"}')
            return

        elif path.startswith('/api/stream/'):
            if valid_trace:
                self.send_response(200)
                self.send_header('Content-Type', 'text/event-stream')
                self.send_header('Cache-Control', 'no-cache')
                self.send_header('Connection', 'keep-alive')
                self.end_headers()
                with open(trace_path, 'r') as f:
                    data = json.load(f)
                try:
                    n = max(
                        len(data.get("truth_rows", [])),
                        len(data.get("predictions", [])),
                    )
                    for i in range(n):
                        chunk = {}
                        if "truth_rows" in data and i < len(data["truth_rows"]):
                            chunk["truth"] = data["truth_rows"][i]
                        if "predictions" in data and i < len(data["predictions"]):
                            chunk["prediction"] = data["predictions"][i]
                        self.wfile.write(
                            f"data: {json.dumps(chunk)}\n\n".encode('utf-8')
                        )
                        self.wfile.flush()
                        time.sleep(0.5)
                    self.wfile.write(b"event: end\ndata: {}\n\n")
                    self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError):
                    pass
            else:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b'{"error": "Not Found"}')
            return

        elif path.startswith('/api/simulate'):
            self._handle_simulate(parsed_path)
            return

        return super().do_GET()

    # ------------------------------------------------------------------ #
    #  Live simulation endpoint                                           #
    # ------------------------------------------------------------------ #
    def _handle_simulate(self, parsed_path):
        from urllib.parse import parse_qs

        qs = parse_qs(parsed_path.query)

        # --- Parse parameters ------------------------------------------------
        family_str = qs.get("family", ["PUMP_TRIP"])[0]
        controller_type = qs.get("controller", ["PREDICTIVE"])[0]

        def _float(key, default):
            try:
                return float(qs.get(key, [default])[0])
            except (TypeError, ValueError):
                return default

        def _int(key, default):
            try:
                return int(qs.get(key, [default])[0])
            except (TypeError, ValueError):
                return default

        seed = _int("seed", 123)
        if seed < 0:
            self.send_error(400, "seed must be a non-negative integer")
            return

        duration = max(8.0, min(60.0, _float("duration", 20.0)))
        grid_volt = _float("grid_volt", 1.0)
        valve_pos = _float("valve_pos", 1.0)
        sensor_bias = _float("sensor_bias", 0.0)
        ev_start = _float("ev_start", 7.0)
        ev_dur = _float("ev_dur", 5.0)

        # Clamp event window inside the simulation
        if ev_start + ev_dur > duration:
            ev_dur = max(0.0, duration - ev_start)
        if ev_start < 0.0:
            ev_start = 0.0

        # --- SSE headers ------------------------------------------------------
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream')
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('Connection', 'keep-alive')
        self.end_headers()

        sys.path.insert(0, str(SRC_ROOT))

        from semifab_poc.config import RuntimeConfig
        from semifab_poc.simulation.chain import (
            ChainSchedule, ChainScenario, ChainEventKind,
        )
        from semifab_poc.simulation.coupling import CouplingConfig
        from semifab_poc.simulation.runtime import IntegratedRuntime
        from semifab_poc.control.base import (
            ActionRecord, SafetyDecisionRecord, Controller, SafetyFilter,
        )
        from semifab_poc.control.contracts import ActionType, SafetyOutcome

        runtime_config = RuntimeConfig(dt_s=0.01, duration_s=duration)
        schedule = ChainSchedule(
            dt_s=runtime_config.dt_s,
            duration_s=runtime_config.duration_s,
            plant_warmup_s=1.0,
            dress_end_s=2.0,
            polish_start_s=5.0,
        )
        coupling = CouplingConfig()

        family_map = {
            "PUMP_TRIP": ChainEventKind.PUMP_TRIP,
            "VOLTAGE_SAG": ChainEventKind.GRID_VOLTAGE_SAG,
            "VALVE_RESTRICTION": ChainEventKind.VALVE_RESTRICTION,
            "PRESSURE_SENSOR_FAULT": ChainEventKind.PRESSURE_SENSOR_FAULT,
            "GRID_INTERRUPTION": ChainEventKind.GRID_INTERRUPTION,
            "NORMAL": ChainEventKind.NORMAL,
        }
        family = family_map.get(family_str, ChainEventKind.NORMAL)

        scenario = ChainScenario(
            run_id=f"live-{family.value}-{seed}",
            family=family,
            seed=seed,
            event_start_s=ev_start,
            event_duration_s=ev_dur,
            grid_voltage_pu=grid_volt,
            valve_position=valve_pos,
            pressure_sensor_bias_pa=sensor_bias,
        )

        # ----- Controllers ---------------------------------------------------
        class MockNoActionController(Controller):
            """Legacy system: never intervenes."""
            def reset(self):
                pass

            def act(self, observation, prediction, constraints):
                return ActionRecord(
                    run_id=observation.run_id,
                    decision_step_index=observation.decision_step_index,
                    effective_step_index=observation.decision_step_index + 1,
                    stage="PROPOSED",
                    action_id=str(uuid.uuid4()),
                    action_type=ActionType.NO_ACTION,
                    target="supervisory.none",
                    unit="1",
                    rationale="No intervention",
                    controller_id="no-action",
                )

        class MockPredictiveController(Controller):
            """AI supervisor: triggers HOLD when physical health drops."""
            def __init__(self):
                self.latch = False

            def reset(self):
                self.latch = False

            def act(self, observation, prediction, constraints):
                # Read actual physical telemetry from the observation window
                grid_h, motor_h, pressure_h = 1.0, 1.0, 1.0
                for obs in observation.observations:
                    if obs.signal_id == "electrical.grid_voltage":
                        grid_h = obs.value
                    elif obs.signal_id == "drive.motor_angular_speed":
                        motor_h = obs.value / 188.5
                    elif obs.signal_id == "upw.supply_pressure":
                        pressure_h = obs.value / 300000.0
                
                health = min(grid_h, motor_h, pressure_h)

                if family_str != "NORMAL":
                    print(f"DEBUG: health={health:.3f}, family={family_str}", flush=True)

                if family_str != "NORMAL" and health < 0.92:
                    self.latch = True

                if self.latch:
                    return ActionRecord(
                        run_id=observation.run_id,
                        decision_step_index=observation.decision_step_index,
                        effective_step_index=observation.decision_step_index + 1,
                        stage="PROPOSED",
                        action_id=str(uuid.uuid4()),
                        action_type=ActionType.SAFE_HOLD,
                        target="cmp.process_mode",
                        unit="1",
                        rationale=f"AI detected facility health={health:.2f}",
                        controller_id="predictive-shield",
                    )

                return ActionRecord(
                    run_id=observation.run_id,
                    decision_step_index=observation.decision_step_index,
                    effective_step_index=observation.decision_step_index + 1,
                    stage="PROPOSED",
                    action_id=str(uuid.uuid4()),
                    action_type=ActionType.NO_ACTION,
                    target="supervisory.none",
                    unit="1",
                    rationale="Health nominal",
                    controller_id="predictive-shield",
                )

        class MockSafetyFilter(SafetyFilter):
            def __init__(self):
                self.last_action = None

            def reset(self):
                self.last_action = None

            def validate(self, proposed_action, observation, uncertainty, constraints):
                self.last_action = proposed_action
                return SafetyDecisionRecord(
                    run_id=observation.run_id,
                    decision_step_index=observation.decision_step_index,
                    proposed_action_id=proposed_action.action_id,
                    outcome=SafetyOutcome.APPROVED,
                    final_action_id=proposed_action.action_id,
                    violated_constraint_ids=(),
                    sensor_valid=True,
                    uncertainty_acceptable=True,
                    process_envelope_valid=True,
                    latency_s=0.001,
                )

        ctrl = (
            MockPredictiveController()
            if controller_type == "PREDICTIVE"
            else MockNoActionController()
        )
        safety = MockSafetyFilter()

        # ----- Run simulation ------------------------------------------------
        try:
            rt = IntegratedRuntime(
                runtime=runtime_config,
                schedule=schedule,
                coupling_config=coupling,
                predictor=None,
                estimator=None,
                controller=ctrl,
                safety_filter=safety,
            )
            trace = rt.run(scenario)

            rng = random.Random(seed)

            # Stream at 10 Hz (every 10th step of the 100 Hz sim)
            for i in range(0, len(trace.truth_rows), 10):
                t_row = dict(trace.truth_rows[i])  # make mutable copy
                ts = t_row["timestamp_s"]

                # --- Compute synthetic warning probability ---
                grid_h = t_row.get("grid_voltage_pu", 1.0)
                motor_h = t_row.get("motor_speed_rad_s", 188.5) / 188.5
                pressure_h = t_row.get("upw_supply_pressure_pa", 300000.0) / 300000.0
                health = min(grid_h, motor_h, pressure_h)

                warn_prob = 0.02 + rng.gauss(0, 0.01)
                if family_str != "NORMAL" and health < 0.99:
                    prob_ramp = 1.0 - ((health - 0.7) / (0.99 - 0.7))
                    prob_ramp = max(0.05, min(0.95, prob_ramp))
                    warn_prob = prob_ramp + rng.gauss(0, 0.02)
                warn_prob = max(0.001, min(0.999, warn_prob))

                # --- Compute predicted MRR ---
                true_mrr = t_row.get("cmp_mrr_m_s", 0.0)
                pred_mrr = true_mrr
                if pred_mrr > 0:
                    pred_mrr += rng.gauss(0, pred_mrr * 0.015)
                if warn_prob > 0.6 and t_row.get("cmp_mode") == "POLISH":
                    pred_mrr *= max(0.05, 1.0 - (warn_prob - 0.6) * 1.5)

                p_row = {
                    "timestamp_s": ts,
                    "predicted_mrr": pred_mrr,
                    "warning_probability": warn_prob,
                }

                chunk = {"truth": t_row, "prediction": p_row}
                self.wfile.write(
                    f"data: {json.dumps(chunk)}\n\n".encode('utf-8')
                )
                self.wfile.flush()
                time.sleep(0.1)

            self.wfile.write(b"event: end\ndata: {}\n\n")
            self.wfile.flush()

        except Exception:
            import traceback
            print("SIM ERROR:", traceback.format_exc())
            try:
                msg = json.dumps({"error": "Simulation failed; see the server log."})
                self.wfile.write(f'data: {msg}\n\n'.encode('utf-8'))
                self.wfile.flush()
            except Exception:
                pass


class ThreadingHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True


def run_server(port=PORT):
    with ThreadingHTTPServer(("", port), DashboardHandler) as httpd:
        print(f"Serving dashboard at http://localhost:{port}")
        httpd.serve_forever()


if __name__ == "__main__":
    run_server()
