# Claims matrix

Status values: `PLANNED`, `BLOCKED`, `SUPPORTED_SIMULATION`, `SUPPORTED_PUBLIC_DATA`, `REJECTED`. No claim is supported at Phase 1.

| ID | Permitted claim | Semantic class | Required evidence | Current status | Required wording or limitation |
|---|---|---|---|---|---|
| C-001 | A model predicts average CMP MRR on held-out PHM 2016 groups. | Measured process output | Verified PHM provenance/raw schema; native-unit contract; phase-aware time weighting; preregistered anomaly policy; official plus wafer/time/machine splits; baseline comparison; MAE, RMSE, relative error, R², uncertainty coverage | BLOCKED | Public-data result only; name native unit status, phase policy, grouping unit, and split policy. |
| C-002 | The simulator propagates configured electrical disturbances through UPS/VFD, motor/pump, UPW, a declared utility topology, and CMP states. | Simulated physical state | Equation tests, unit/conservation checks, limiting and null-topology cases, deterministic trace, timestep convergence, structural and parameter sensitivity | SUPPORTED_SIMULATION | Applies only to tested synthetic configurations. The healthy sag is a negative control; the positive result uses a declared degraded-UPS/DRESS topology. Mechanistic plausibility is not real-fab validation or controller efficacy. |
| C-003 | An early-warning model predicts whether simulated MRR will leave the configured safe envelope within horizon H. | Process excursion | Frozen target definition; leakage-safe temporal features; held-out scenarios; precision, recall, PR-AUC, false alarms/hour, missed events, lead time, uncertainty | PLANNED | The envelope and H must be preregistered before final evaluation. |
| C-004 | Predictive supervisory control reduces simulated MRR excursion versus no action. | Process excursion | Paired identical scenarios/seeds; active-polish peak/integrated MRR deviation; cumulative-removal error; hold/recovery/throughput costs; uncertainty and robustness summaries | PLANNED | Applies only to evaluated simulator configurations and declared utility topology. |
| C-005 | Predictive supervisory control improves simulated excursion outcomes versus threshold control. | Process excursion | Paired identical runs; preregistered non-inferiority tolerance; cumulative-removal, action, hold, recovery, and throughput trade-offs | PLANNED | Do not generalize beyond tested scenarios, topology, and assumptions. |
| C-006 | The independent safety filter keeps final simulated actions inside configured constraints. | Simulated control property | Unit/property tests, rejection-path tests, action audit, zero configured-constraint violations | PLANNED | This is software/simulation safety, not equipment certification. |
| C-007 | The attribution module identifies the initiating simulated cause. | Simulator-label classification | Held-out scenario labels; confusion matrix; unknown class; residual/rule evidence; feature attribution | PLANNED | Feature attribution is not causal proof. |
| C-008 | A physics-plus-residual model improves average-MRR prediction over specified baselines. | Measured process output or simulated output, reported separately | Same split/features for all models; native-unit PHM physics term or separate SI simulator physics; uncertainty; statistical paired comparison | BLOCKED for public data; PLANNED for simulation | State data origin and unit plane explicitly; never add SI simulator MRR to scaled PHM residuals. |
| C-009 | Consumable age and tool state are associated with MRR prediction error or performance. | Measured association | Verified columns, grouped analysis, uncertainty, confounding limitations | BLOCKED | Association only; do not claim causal consumable degradation without intervention evidence. |
| C-010 | A derived radial MRR or non-uniformity indicator changes under simulated disturbances. | Quality-risk proxy | Declared proxy equation, sensitivity analysis, synthetic reference traces | PLANNED | Label exactly: “Simulated spatial-uniformity proxy; not experimentally validated WIWNU.” |
| C-011 | The reduced-order synthetic CMP subsystem satisfies its declared process-mode, kinematic, generalized-Preston, consumable, slurry, thermal-energy, cumulative-removal, and numerical invariants. | Simulated physical state | Frozen decision; unit/property tests; dimensional and limiting cases; deterministic trace; energy residual; timestep refinement; complete parameter provenance | SUPPORTED_SIMULATION | Applies only to the frozen synthetic WP08 configuration and tested bounds; it is not real-tool calibration, measured WIWNU, a physical-defect model, yield evidence, or control efficacy. |

## Explicitly unsupported claims

The following claims are rejected for this PoC and must not appear as achievements:

| ID | Prohibited claim | Reason | Permitted treatment |
|---|---|---|---|
| X-001 | Prediction or prevention of scratches, dishing, erosion, corrosion, particle contamination, delamination, or cracking | No measured defect labels or validated defect mechanisms | Future work or real-fab data requirement only |
| X-002 | Prevention of real wafer-yield loss | No production yield labels or fab intervention study | Future work only |
| X-003 | Prevention of real equipment damage | No equipment safety certification or hardware trial | Future work only |
| X-004 | Readiness for real production control | Simulation-only supervisory layer | State explicitly that no real actuator interface exists |
| X-005 | Microsecond production response | The PoC is not designed or benchmarked as a real-time embedded controller | Report measured software latency at its actual platform and timestep |
| X-006 | Feature importance proves physical root cause | Predictive association is not causal identification | Combine simulator labels, mechanistic rules, residual checks, and cautious language |
| X-007 | Synthetic spatial proxy is measured WIWNU | No measured spatial metrology | Use the mandatory proxy label |

## Reporting gate

Before a claim moves from `PLANNED` or `BLOCKED`, the task manifest must identify its evidence artifacts and acceptance tests. A report-generation test must scan for prohibited or ambiguous wording, including any unqualified use of “validated,” “caused,” “prevented,” “defect,” “yield,” or “production control.”
