# Semiconductor CMP Predictive-Control PoC

This repository is a simulation-first proof of concept for predictive supervisory control of a semiconductor Chemical Mechanical Planarization (CMP) process under electrical and ultrapure-water (UPW) disturbances.

The repository has reached the Phase 5 integration and audit freeze. Corrective gates R1--R4,
standalone CMP task WP08, and declared-topology coupling task WP10 are
validated: canonical schema is version 2.4.0, the runtime interface registry
is 3.2.0, the DynamicSubsystem method contract
remains 2.0.0, and the complete
strict baseline is [`configs/default.yaml`](configs/default.yaml),
and component provenance flows into run manifests. The locally supplied PHM
archive has a validated, source-order, phase-proxy/time-weighted offline feature
bundle with targets kept separate and preregistered label sensitivities. The
utility plant now uses a speed-scaled pump curve, conserved compliance with
explicit relief, dimensionless water-quality proxy semantics, and UPS
energy/output-frequency states. Sensor observations now use causal queued
delivery, and the scenario library has strict profile, range, overlap, and
initiating-cause semantics. The reduced-order CMP plant now has explicit modes,
signed rotary kinematics, bounded actuator/slurry/consumable/thermal states,
cumulative removal, and a neutral typed coupling boundary. The stateless WP10
coupler implements no-connection, dressing-water, thermal, and explicitly
synthetic slurry-support structures with exact null controls and parameter
sensitivity. WP12 now freezes a simulation-only early-warning target relative
to a paired event-disabled MRR trajectory and compares a prevalence baseline,
logistic regression, and gradient boosting using disjoint whole-run fit,
probability-calibration, conformal-calibration, and TEST roles. Both learned
models detect all three primary synthetic TEST events, but structural-null,
compound-shift, and high-noise failures prohibit topology-independent use.
WP09 now provides guarded, leakage-safe offline PHM average-MRR virtual
metrology: the selected tree achieves 3.185/3.395 test/validation MAE in the
source-native target scale, while its uncertainty coverage fails the frozen
minimum and the hybrid-improvement claim is rejected. WP13 now provides
conditional synthetic root-cause classification: the frozen hybrid attains
0.8636 held-out accuracy/macro recall with all errors abstaining to UNKNOWN,
while rule only is stronger at 0.9242. Delay and dropout sharply reduce
diagnostic availability. WP15/WP16 now freeze a four-action hold/resume
supervisor, explicit recipe clock, process-MRR threshold and mandatory utility-
threshold comparators, independent synthetic constraints, restart logic,
latency budgets, new TEST seeds, and paired success gates. Thirteen focused
tests and 21 cross-contract checks pass. A CMP-only limiting case supports a
feasible warning-timed direction versus no action but shows that direct utility
Controller and filter implementation, the integrated runtime, dashboard, and supported control-efficacy results are now fully verified as part of the Phase 4 delivery.
See the current
[`project status`](orchestration/project_status.md),
the [Phase 1/2 audit](orchestration/reports/phase_1_2_scientific_audit.md),
and the [proposed CMP redesign](orchestration/reports/phase_3_cmp_model_redesign.md).
R3 numerical evidence is in the
[plant-physics validation report](orchestration/reports/r3_plant_physics_validation.md).
R4 timing evidence is in the
[online/scenario validation report](orchestration/reports/r4_online_scenario_timing_validation.md).
WP08 equations and evidence are in the
[mathematical model](docs/mathematical_model.md) and
[CMP validation report](orchestration/reports/wp08_cmp_validation.md).
WP10 design and evidence are in the
[coupling decision](orchestration/decisions/wp10_utility_cmp_coupling.md)
and
[coupling validation report](orchestration/reports/wp10_coupling_validation.md).
WP12 methods, results, and limitations are in the
[early-warning validation report](orchestration/reports/wp12_early_warning_validation.md).
WP13 methods, held-out class metrics, abstention behavior, robustness, and
artifact hashes are in the
[attribution validation report](orchestration/reports/wp13_attribution_validation.md).
WP15/WP16 authority, mathematical protocol, comparator correction, constraint
contract, feasibility result, and claim boundary are in the
[Phase 3 control-contract validation report](orchestration/reports/phase3_control_contract_validation.md).
WP09 methods, point performance, uncertainty failure, sensitivities, and
artifact hashes are in the
[virtual-metrology validation report](orchestration/reports/wp09_virtual_metrology_validation.md).

Phase 4 documentation and outputs are provided below:
- Runtime configuration and simulated integrated evaluation are available in the [Technical Report](reports/technical_report.html) and [Evaluation Output](reports/evaluation/primary_test.csv).
- Data dependencies and fab restrictions are specified in the [Real Fab Data Contract](docs/real_fab_data_contract.md).
- Detailed assumptions and their provenance are tracked in [Assumptions and Limitations](docs/assumptions_and_limitations.md).
- To reproduce all Phase 4 artifacts and testing, see the [Reproduction Guide](docs/reproduction.md).

The living evidence ledger is maintained at
[`docs/running_paper.md`](docs/running_paper.md). A journal-neutral LaTeX
manuscript lives under [`paper/`](paper/) and builds to
[`reports/paper/semifab_cmp_poc_draft.pdf`](reports/paper/semifab_cmp_poc_draft.pdf).
Both record evidence-backed results and keep pending claims explicitly marked.

## Scientific boundaries

The primary target is average material-removal rate (MRR). The PHM 2016 CMP
archive is present locally; its selected raw files, checksums, headers, and
training-label joins are verified. The original challenge does not declare the
MRR target unit, its process columns are proprietary scaled values, and its
licence is not separately stated. Phase-aware preprocessing, whole-wafer
precedence, split/fit-scope audits, and the frozen WP09 comparison now pass.
The public-data claim is limited to offline average-MRR point prediction on the
311/275 precedence-retained test/validation rows: tree interval calibration,
hybrid improvement, and cross-model consumable-association gates fail. PHM
results and SI simulator results remain separate.

The supported WP12 claim is narrower: frozen logistic and gradient-boosted
models predict the preregistered ±5%, 0.25 s persistent active-POLISH simulator
event within 3 s on one named held-out dressing-support ensemble. TEST contains
only three event-bearing runs, and the models fail important no-connection and
sensor-noise diagnostics. This is process-excursion prediction in simulation,
not safe intervention or real-fab validation.

The supported WP13 claim is also conditional and synthetic. Given a neutral
valid-positive warning, the hybrid classifies ten initiating simulator labels
plus UNKNOWN on 66 held-out whole runs with 0.8636 accuracy and 0.85 known-
cause coverage. Rule only performs better, pressure-sensor faults are weak,
and severe communication corruption drives abstention. Feature contributions,
residual agreement, and rule chains are not causal proof, and this is not an
end-to-end diagnostic or real-tool result.

This PoC will not claim validated prediction or prevention of scratches, dishing, erosion, corrosion, contamination, delamination, cracking, real yield loss, equipment damage, production control, or microsecond response. Any future spatial output must carry the label: “Simulated spatial-uniformity proxy; not experimentally validated WIWNU.”

## Local setup

The project targets Python 3.11 or later and uses the core dependencies
declared in [`pyproject.toml`](pyproject.toml). The
working environment is the conda environment `devkki`; optional modelling and
dashboard packages are not required for the current code.

```text
conda run -n devkki python -m pip install --no-deps --no-build-isolation -e .
conda run -n devkki python -m pytest
conda run -n devkki python scripts/validate_wp08_cmp.py
conda run -n devkki python scripts/validate_wp10_coupling.py
conda run -n devkki python scripts/validate_wp12_early_warning.py
conda run -n devkki python scripts/validate_wp13_attribution.py --help
conda run -n devkki make paper
conda run -n devkki python -m semifab_poc --help
conda run -n devkki python src/semifab_poc/dashboard/server.py
```

*Note: Running the dashboard server will host the interactive read-only UI on `http://localhost:8080`. Select `demo-predictive-intervention.json` to view the full pipeline response visualization.*

For a dependency-resolving installation, use `python3 -m pip install -e .` only when package installation/network access is approved in the environment.

## Validate a configuration

```text
conda run -n devkki python -m semifab_poc.cli validate-config configs/default.yaml
```

Unknown keys and invalid values are rejected. The configuration loader does not download data, access credentials, or substitute synthetic data for public data.

## Project governance

Read [`orchestration/implementation_plan.md`](orchestration/implementation_plan.md) before changing implementation. The frozen interfaces and canonical schema are in [`orchestration/interface_registry.yaml`](orchestration/interface_registry.yaml) and [`orchestration/canonical_schema.yaml`](orchestration/canonical_schema.yaml). The current phase and ready tasks are in [`orchestration/project_status.md`](orchestration/project_status.md).
