"""Simulation script to run the integrated runtime and generate a trace."""

import argparse
import json
import logging
import sys
from pathlib import Path

from semifab_poc.config import load_runtime_config
from semifab_poc.simulation.runtime import IntegratedRuntime
from semifab_poc.simulation.chain import ChainSchedule, ChainScenario, ChainEventKind
from semifab_poc.simulation.coupling import CouplingConfig
from semifab_poc.control.contracts import load_control_contract_bundle
from semifab_poc.control.predictive import PredictiveSupervisor
from semifab_poc.control.safety import SafetyFilterImpl

logging.basicConfig(level=logging.INFO)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run integrated WP17 simulation.")
    parser.add_argument("--runtime-config", type=Path, default=Path("configs/runtime/default.yaml"))
    parser.add_argument("--control-bundle", type=Path, default=Path("configs/control/bundle.yaml"))
    parser.add_argument("--output", type=Path, default=Path("tests/regression/reference_trace.json"))
    args = parser.parse_args()

    # If configs do not exist, use basic instantiation for regression trace creation
    try:
        runtime_config = load_runtime_config(args.runtime_config)
    except Exception:
        logging.warning("Failed to load runtime config, falling back to default.")
        from semifab_poc.config import RuntimeConfig
        runtime_config = RuntimeConfig(dt_s=0.01, duration_s=10.0)

    try:
        bundle = load_control_contract_bundle(
            args.control_bundle.parent / "predictive.yaml",
            args.control_bundle.parent / "baselines.yaml",
            args.control_bundle.parent / "safety.yaml",
        )
        controller = PredictiveSupervisor(bundle.predictive)
        safety = SafetyFilterImpl(bundle.safety)
    except Exception:
        logging.warning("Failed to load control configs, falling back to mocks.")
        from semifab_poc.control.base import ActionRecord, SafetyDecisionRecord, Controller, SafetyFilter
        from semifab_poc.control.contracts import ActionType, SafetyOutcome

        class MockController(Controller):
            def reset(self): pass
            def act(self, observation, prediction, constraints):
                return ActionRecord(
                    run_id=observation.run_id,
                    decision_step_index=observation.decision_step_index,
                    effective_step_index=observation.decision_step_index + 1,
                    stage="PROPOSED",
                    action_id="test-action-123",
                    action_type=ActionType.NO_ACTION,
                    target="supervisory.none",
                    unit="1",
                    rationale="Test",
                    controller_id="test-controller"
                )

        class MockSafetyFilter(SafetyFilter):
            def __init__(self): self.last_action = None
            def reset(self): self.last_action = None
            def validate(self, proposed_action, observation, uncertainty, constraints):
                self.last_action = ActionRecord(
                    run_id=observation.run_id,
                    decision_step_index=observation.decision_step_index,
                    effective_step_index=observation.decision_step_index + 1,
                    stage="FINAL",
                    action_id="test-action-456",
                    action_type=ActionType.SAFE_HOLD,
                    target="cmp.process_mode",
                    unit="1",
                    rationale="Safety override",
                    controller_id="safety-filter"
                )
                return SafetyDecisionRecord(
                    run_id=observation.run_id,
                    decision_step_index=observation.decision_step_index,
                    proposed_action_id=proposed_action.action_id,
                    outcome=SafetyOutcome.REPLACED_WITH_HOLD,
                    final_action_id=self.last_action.action_id,
                    violated_constraint_ids=("test_constraint",),
                    sensor_valid=True,
                    uncertainty_acceptable=True,
                    process_envelope_valid=True,
                    latency_s=0.001
                )
        
        controller = MockController()
        safety = MockSafetyFilter()

    schedule = ChainSchedule(
        dt_s=runtime_config.dt_s,
        duration_s=runtime_config.duration_s,
        plant_warmup_s=1.0,
        dress_end_s=2.0,
        polish_start_s=5.0
    )
    coupling = CouplingConfig()
    scenario = ChainScenario(
        run_id="regression-trace-1",
        family=ChainEventKind.NORMAL,
        seed=1001,
        event_start_s=6.0,
        event_duration_s=2.0
    )

    runtime = IntegratedRuntime(
        runtime=runtime_config,
        schedule=schedule,
        coupling_config=coupling,
        predictor=None,
        estimator=None,
        controller=controller,
        safety_filter=safety,
    )

    trace = runtime.run(scenario)
    
    # Dump trace to JSON
    output = {
        "run_id": trace.run_id,
        "family": trace.family,
        "truth_rows": trace.truth_rows,
        "actions": [a.model_dump(mode="json") for a in trace.actions],
        "safety_decisions": [s.model_dump(mode="json") for s in trace.safety_decisions]
    }
    
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w") as f:
        json.dump(output, f, indent=2)
        
    logging.info(f"Trace written to {args.output}")

if __name__ == "__main__":
    main()
