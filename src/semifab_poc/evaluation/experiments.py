"""Experiment definitions and batch runners for WP18."""

import logging
from typing import Sequence, Iterator

from semifab_poc.config import RuntimeConfig
from semifab_poc.simulation.runtime import IntegratedRuntime, IntegratedTrace
from semifab_poc.simulation.chain import ChainSchedule, ChainScenario, ChainEventKind
from semifab_poc.simulation.coupling import CouplingConfig
from semifab_poc.evaluation.metrics import compute_paired_metrics, PairedRunMetrics
from semifab_poc.control.contracts import ControlContractBundle
from semifab_poc.control.baselines import NoActionController, ProcessMrrThresholdController, UtilityThresholdController
from semifab_poc.control.predictive import PredictiveSupervisor
from semifab_poc.control.safety import SafetyFilterImpl

logger = logging.getLogger(__name__)

SCENARIO_FAMILIES = [
    ChainEventKind.NORMAL,
    ChainEventKind.HEALTHY_SAG,
    ChainEventKind.GRID_INTERRUPTION,
    ChainEventKind.PUMP_TRIP,
    ChainEventKind.VALVE_RESTRICTION,
    ChainEventKind.TOOL_DEMAND_SPIKE,
]

def generate_scenarios(base_seed: int, count_per_family: int) -> Iterator[ChainScenario]:
    """Generates scenarios for primary TEST."""
    for idx, family in enumerate(SCENARIO_FAMILIES):
        for run_idx in range(count_per_family):
            seed = base_seed + idx * 1000 + run_idx
            yield ChainScenario(
                run_id=f"run-{family.value}-{seed}",
                family=family,
                seed=seed,
                event_start_s=5.0,
                event_duration_s=2.0 if family != ChainEventKind.PUMP_TRIP else 10.0,
            )

def run_paired_experiments(
    runtime_config: RuntimeConfig,
    schedule: ChainSchedule,
    coupling: CouplingConfig,
    bundle: ControlContractBundle,
    base_seed: int = 230000,
    count_per_family: int = 8,
) -> list[PairedRunMetrics]:
    
    results = []
    
    for scenario in generate_scenarios(base_seed, count_per_family):
        logger.info(f"Running scenario {scenario.run_id}")
        
        # We need independent safety filters per controller to prevent state leakage
        safeties = {
            "NO_ACTION": SafetyFilterImpl(bundle.safety),
            "PROCESS_THRESHOLD": SafetyFilterImpl(bundle.safety),
            "UTILITY_THRESHOLD": SafetyFilterImpl(bundle.safety),
            "PREDICTIVE": SafetyFilterImpl(bundle.safety),
        }
        
        controllers = {
            "NO_ACTION": NoActionController(bundle.baselines),
            "PROCESS_THRESHOLD": ProcessMrrThresholdController(bundle.baselines),
            "UTILITY_THRESHOLD": UtilityThresholdController(bundle.baselines),
            "PREDICTIVE": PredictiveSupervisor(bundle.predictive),
        }
        
        traces = {}
        for name, ctrl in controllers.items():
            rt = IntegratedRuntime(
                runtime=runtime_config,
                schedule=schedule,
                coupling_config=coupling,
                predictor=None,
                estimator=None,
                controller=ctrl,
                safety_filter=safeties[name],
            )
            traces[name] = rt.run(scenario)
            
        ref_trace = traces["NO_ACTION"]
        for name, trace in traces.items():
            metrics = compute_paired_metrics(trace, ref_trace, schedule.dt_s, name)
            results.append(metrics)
            
    return results
