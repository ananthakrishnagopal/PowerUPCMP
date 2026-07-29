"""Dashboard server with live physics simulation via IntegratedRuntime."""

import http.server
import socketserver
import json
import sys
import time
import urllib.parse
import traceback
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
import uuid

PORT = 8080
DASHBOARD_DIR = Path(__file__).parent
PROJECT_ROOT = DASHBOARD_DIR.parent.parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
LOG_DIR = PROJECT_ROOT / "reports" / "dashboard"
SIM_ERROR_LOG = LOG_DIR / "simulation_errors.log"
DEMO_TRACE_NAMES = (
    "stakeholder-demo-normal-baseline.json",
    "stakeholder-demo-stable-polish-fault.json",
    "stakeholder-demo-grid-interruption.json",
    "stakeholder-demo-power-to-water-cascade.json",
)


def _record_simulation_error(exc: BaseException) -> str:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    error_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    message = (
        f"\n[{error_id}] {type(exc).__name__}: {exc}\n"
        f"{traceback.format_exc()}\n"
    )
    SIM_ERROR_LOG.open("a", encoding="utf-8").write(message)
    return error_id


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
            and trace_name in DEMO_TRACE_NAMES
            and trace_path.parent == trace_dir
            and trace_path.is_file()
        )

        if path == '/api/traces':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            traces = [
                name for name in DEMO_TRACE_NAMES
                if (trace_dir / name).is_file()
            ]
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
                    header = {
                        key: data[key]
                        for key in ("metadata", "scenario", "summary", "actions", "safety_decisions")
                        if key in data
                    }
                    if header:
                        self.wfile.write(
                            f"data: {json.dumps(header)}\n\n".encode('utf-8')
                        )
                        self.wfile.flush()

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
        self.wfile.write(
            b'data: {"metadata": {"status": "initializing live simulation"}}\n\n'
        )
        self.wfile.flush()

        sys.path.insert(0, str(SRC_ROOT))

        from semifab_poc.config import load_runtime_config
        from semifab_poc.simulation.chain import (
            ChainSchedule, ChainScenario, ChainEventKind,
        )
        from semifab_poc.simulation.coupling import UtilityCmpTopology
        from semifab_poc.simulation.runtime import IntegratedRuntime
        from semifab_poc.simulation.sensors import SensorConfig
        from semifab_poc.models.early_warning import (
            EarlyWarningPredictor,
            load_early_warning_config,
        )
        from semifab_poc.control.baselines import NoActionController, UtilityThresholdController
        from semifab_poc.control.base import ActionRecord, Controller
        from semifab_poc.control.contracts import ActionType, load_control_contract_bundle
        from semifab_poc.control.predictive import PredictiveSupervisor
        from semifab_poc.control.safety import SafetyFilterImpl

        class LiveDemoControllerGate(Controller):
            def __init__(self, inner: Controller, decision_start_s: float) -> None:
                self.inner = inner
                self.decision_start_s = decision_start_s

            def reset(self) -> None:
                self.inner.reset()

            def act(self, observation, prediction, constraints):
                if observation.decision_timestamp_s < self.decision_start_s:
                    return ActionRecord(
                        run_id=observation.run_id,
                        decision_step_index=observation.decision_step_index,
                        effective_step_index=observation.decision_step_index + 1,
                        stage="PROPOSED",
                        action_id=str(uuid.uuid4()),
                        action_type=ActionType.NO_ACTION,
                        target="supervisory.none",
                        value=None,
                        unit="1",
                        rationale="Live demo warm-up; supervisor gate opens at event start",
                        controller_id="live-demo-controller-gate",
                    )
                return self.inner.act(observation, prediction, constraints)

        class LiveDemoPredictorThrottle:
            def __init__(self, inner, period_s: float) -> None:
                self.inner = inner
                self.period_s = period_s
                self.last_prediction = None

            def predict(self, observation_window):
                if (
                    self.last_prediction is not None
                    and observation_window.decision_timestamp_s
                    - self.last_prediction.feature_cutoff_timestamp_s
                    < self.period_s
                ):
                    return self.last_prediction
                self.last_prediction = self.inner.predict(observation_window)
                return self.last_prediction

        runtime_config = load_runtime_config(
            PROJECT_ROOT / "configs" / "default.yaml"
        ).model_copy(update={"duration_s": duration, "dt_s": 0.05})
        warning_config = load_early_warning_config(
            PROJECT_ROOT / "configs" / "models" / "early_warning.yaml"
        )
        units = {
            "electrical.grid_voltage": "pu",
            "electrical.ups_output_voltage": "pu",
            "electrical.ups_battery_energy": "J",
            "drive.motor_angular_speed": "rad/s",
            "pump.volumetric_flow": "m^3/s",
            "upw.supply_pressure": "Pa",
            "upw.tool_flow": "m^3/s",
            "upw.temperature": "K",
        }
        runtime_config = runtime_config.model_copy(
            update={
                "sensors": tuple(
                SensorConfig(
                    sensor_id=f"warning-live-{index}",
                    signal_id=signal_id,
                    unit=units[signal_id],
                    sample_period_s=warning_config.sensors.sample_period_s,
                    delay_s=warning_config.sensors.delay_s,
                    noise_std=warning_config.sensors.noise_by_signal[signal_id],
                    packet_loss_probability=warning_config.sensors.packet_loss_probability,
                    timestamp_jitter_std_s=warning_config.sensors.timestamp_jitter_std_s,
                    minimum_value=0.0,
                )
                for index, signal_id in enumerate(warning_config.features.allowed_signal_ids)
            ),
                "coupling": replace(
                    runtime_config.coupling,
                    topology=UtilityCmpTopology.SYNTHETIC_SLURRY_SUPPORT,
                    link_strength=1.0,
                ),
            }
        )
        schedule = ChainSchedule(
            dt_s=runtime_config.dt_s,
            duration_s=runtime_config.duration_s,
            plant_warmup_s=1.0,
            dress_end_s=warning_config.simulation.dress_end_s,
            polish_start_s=warning_config.simulation.polish_start_s,
        )
        coupling = runtime_config.coupling

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

        bundle = load_control_contract_bundle(
            PROJECT_ROOT / "configs" / "controllers" / "predictive.yaml",
            PROJECT_ROOT / "configs" / "controllers" / "baselines.yaml",
            PROJECT_ROOT / "configs" / "controllers" / "safety.yaml",
        )
        predictor_path = (
            PROJECT_ROOT / "reports" / "early_warning" / "models" / "dashboard_warning.pkl"
            if controller_type == "PREDICTIVE"
            else PROJECT_ROOT / "reports" / "early_warning" / "models" / "logistic.pkl"
        )
        predictor = EarlyWarningPredictor.load(predictor_path)
        if controller_type == "PREDICTIVE":
            predictor = LiveDemoPredictorThrottle(predictor, period_s=0.25)
        if controller_type == "PREDICTIVE":
            predictive_config = bundle.predictive.model_copy(
                update={
                    "risk_policy": bundle.predictive.risk_policy.model_copy(
                        update={
                            "hold_probability": 0.80,
                            "maximum_prediction_age_s": 0.30,
                        }
                    )
                }
            )
            base_ctrl = PredictiveSupervisor(predictive_config)
        elif controller_type == "UTILITY_THRESHOLD":
            base_ctrl = UtilityThresholdController(bundle.baselines)
        else:
            base_ctrl = NoActionController(bundle.baselines)
        ctrl = LiveDemoControllerGate(base_ctrl, ev_start)
        safety = SafetyFilterImpl(bundle.safety)

        # ----- Run simulation ------------------------------------------------
        try:
            rt = IntegratedRuntime(
                runtime=runtime_config,
                schedule=schedule,
                coupling_config=coupling,
                predictor=predictor,
                estimator=None,
                controller=ctrl,
                safety_filter=safety,
            )
            trace = rt.run(scenario)

            # Stream at 10 Hz (every 10th step of the 100 Hz sim)
            for i in range(0, len(trace.truth_rows), 10):
                t_row = dict(trace.truth_rows[i])  # make mutable copy
                ts = t_row["timestamp_s"]
                prediction = trace.predictions[i] if i < len(trace.predictions) else None
                action = trace.actions[i] if i < len(trace.actions) else None
                safety_decision = (
                    trace.safety_decisions[i]
                    if i < len(trace.safety_decisions)
                    else None
                )
                chunk = {"truth": t_row}
                if prediction is not None:
                    chunk["prediction"] = {
                        "timestamp_s": ts,
                        "predicted_mrr": t_row.get("cmp_mrr_m_s", 0.0),
                        "warning_probability": prediction.probability,
                        "predicted_excursion": prediction.predicted_excursion,
                        "conformal_prediction_set": prediction.conformal_prediction_set,
                        "uncertainty_valid": prediction.uncertainty_valid,
                        "latency_s": prediction.latency_s,
                    }
                if action is not None:
                    chunk["actions"] = [action.model_dump(mode="json")]
                if safety_decision is not None:
                    chunk["safety_decisions"] = [safety_decision.model_dump(mode="json")]
                self.wfile.write(
                    f"data: {json.dumps(chunk)}\n\n".encode('utf-8')
                )
                self.wfile.flush()
                time.sleep(0.1)

            self.wfile.write(b"event: end\ndata: {}\n\n")
            self.wfile.flush()

        except Exception as exc:
            error_id = _record_simulation_error(exc)
            try:
                msg = json.dumps({
                    "error": (
                        "Simulation failed. See "
                        f"reports/dashboard/simulation_errors.log ({error_id})."
                    )
                })
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
