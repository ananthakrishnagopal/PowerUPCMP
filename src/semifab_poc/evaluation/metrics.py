"""Metrics for WP18 paired evaluation and robustness."""

import numpy as np
from dataclasses import dataclass
from typing import Mapping, Sequence

from semifab_poc.simulation.runtime import IntegratedTrace


@dataclass(frozen=True)
class PairedRunMetrics:
    run_id: str
    scenario_family: str
    controller_name: str
    # Progress-matched MRR errors
    e_iae: float
    e_peak: float
    e_rem: float
    # Operational metrics
    hold_duration_s: float
    cycle_extension_s: float
    phase_completed: bool
    # Safety and latency
    safety_violations: int
    median_latency_s: float
    p95_latency_s: float
    worst_case_latency_s: float


def compute_paired_metrics(
    eval_trace: IntegratedTrace,
    ref_trace: IntegratedTrace,
    dt_s: float,
    controller_name: str,
) -> PairedRunMetrics:
    """Computes event-disabled progress-matched metrics."""
    
    def extract_mrr_and_modes(trace: IntegratedTrace) -> tuple[np.ndarray, np.ndarray]:
        mrrs = np.array([r["cmp_mrr_m_s"] for r in trace.truth_rows])
        modes = np.array([r["cmp_mode"] for r in trace.truth_rows])
        return mrrs, modes

    eval_mrrs, eval_modes = extract_mrr_and_modes(eval_trace)
    ref_mrrs, ref_modes = extract_mrr_and_modes(ref_trace)
    
    # Compute active polish progress \tau (time spent in POLISH mode)
    eval_is_polish = eval_modes == "POLISH"
    ref_is_polish = ref_modes == "POLISH"
    
    eval_progress = np.cumsum(eval_is_polish) * dt_s
    ref_progress = np.cumsum(ref_is_polish) * dt_s
    
    # Progress-matched interpolation
    max_progress = min(eval_progress[-1], ref_progress[-1])
    if max_progress <= 0:
        # No polishing happened in one or both
        e_iae = 0.0
        e_peak = 0.0
        e_rem = 0.0
    else:
        # Common progress grid
        progress_grid = np.arange(dt_s, max_progress + dt_s * 0.5, dt_s)
        
        # Interpolate MRRs onto the progress grid
        eval_mrr_interp = np.interp(progress_grid, eval_progress, eval_mrrs)
        ref_mrr_interp = np.interp(progress_grid, ref_progress, ref_mrrs)
        
        abs_diff = np.abs(eval_mrr_interp - ref_mrr_interp)
        e_iae = float(np.sum(abs_diff) * dt_s)
        e_peak = float(np.max(abs_diff))
        
        # Cumulative removal
        eval_cum = np.sum(eval_mrr_interp) * dt_s
        ref_cum = np.sum(ref_mrr_interp) * dt_s
        e_rem = float(np.abs(eval_cum - ref_cum))
        
    hold_duration_s = float(np.sum(eval_modes == "HOLD") * dt_s)
    cycle_extension_s = max(0.0, float(len(eval_modes) - len(ref_modes)) * dt_s)
    phase_completed = eval_progress[-1] >= ref_progress[-1] - 1e-6
    
    # Safeties
    safety_violations = sum(1 for sd in eval_trace.safety_decisions if sd.violated_constraint_ids)
    
    # Latencies
    latencies = [sd.latency_s for sd in eval_trace.safety_decisions]
    if latencies:
        median_latency_s = float(np.median(latencies))
        p95_latency_s = float(np.percentile(latencies, 95))
        worst_case_latency_s = float(np.max(latencies))
    else:
        median_latency_s = p95_latency_s = worst_case_latency_s = 0.0

    return PairedRunMetrics(
        run_id=eval_trace.run_id,
        scenario_family=eval_trace.family,
        controller_name=controller_name,
        e_iae=e_iae,
        e_peak=e_peak,
        e_rem=e_rem,
        hold_duration_s=hold_duration_s,
        cycle_extension_s=cycle_extension_s,
        phase_completed=phase_completed,
        safety_violations=safety_violations,
        median_latency_s=median_latency_s,
        p95_latency_s=p95_latency_s,
        worst_case_latency_s=worst_case_latency_s,
    )
