# Manuscript evidence map

Status: working traceability record for the journal-neutral manuscript<br>
Evidence freeze: public-data WP09, synthetic WP08/WP10, bounded synthetic WP12, and conditional synthetic WP13 complete; control and safety results pending

## Claim boundary

The manuscript may support C-001 only for offline average MRR on the
precedence-retained PHM whole-wafer roles in the source-native, undeclared
target scale. The tree's point-performance gate passes, while its frozen
uncertainty-coverage gate fails. It may support C-002 and C-011 at the
explicitly limited synthetic level and C-003 only for the frozen ±5%, 0.25 s
persistent, 3 s horizon target on the named primary WP12 ensemble, with three
independent TEST events and explicit structural/noise failures. C-008 and the
cross-model C-009 gate fail on public data. C-007 is supported only as
conditional synthetic simulator-label classification after a valid diagnostic
warning, with explicit abstention and communication-availability failures.
The manuscript must not represent attribution as experimental causal proof or
represent controller efficacy, safety filtering, physical defects, yield,
real equipment, or production control as completed.

Primary governance source: [`claims_matrix.md`](../orchestration/claims_matrix.md).

## Quantitative-result traceability

| Manuscript result | Evidence source | Status and limitation |
|---|---|---|
| PHM archive: 17,399,074 compressed bytes; 558 selected members; 58 header-only traces | [`data_sources.yaml`](../orchestration/data_sources.yaml), `data/raw/phm_2016_cmp/extraction_manifest.yaml` | Provenance/schema evidence only; no public-model performance claim |
| PHM processed source rows: 1,981/424/424 with 405 target-free predictors; precedence-retained evaluation rows: 1,981/311/275 from mutually disjoint wafers | [`r2_phm_semantics_validation.md`](../orchestration/reports/r2_phm_semantics_validation.md), [`r2_official_wafer_precedence.md`](../orchestration/decisions/r2_official_wafer_precedence.md) | Native target unit remains source-undeclared; full source holdouts are collision-contaminated diagnostics; no SI bridge |
| WP09 tree: test/validation MAE 3.185/3.395, RMSE 5.176/6.693, and R² 0.975/0.958 | [`wp09_virtual_metrology_validation.md`](../orchestration/reports/wp09_virtual_metrology_validation.md), [`wp09_validation.json`](../reports/virtual_metrology/wp09_validation.json) | Offline source-native average MRR only; selected before holdout opening; final-validation paired tree-minus-mean interval [-28.191, -24.363] |
| WP09 tree interval coverage: 0.839 test and 0.847 validation | [`wp09_virtual_metrology_validation.md`](../orchestration/reports/wp09_virtual_metrology_validation.md) | Fails the frozen 0.85 minimum despite nominal 90% intervals; no calibrated-uncertainty claim |
| WP09 hybrid-minus-tree validation MAE interval [1.502, 3.650]; consumable ablation changes sign across tree and ridge | [`wp09_virtual_metrology_validation.md`](../orchestration/reports/wp09_virtual_metrology_validation.md) | Rejects public-data C-008 and the model-family-independent C-009 gate; association is not causation |
| WP09 chronological tree stress: MAE 18.50, RMSE 239.84, median absolute error 3.19 | [`wp09_virtual_metrology_validation.md`](../orchestration/reports/wp09_virtual_metrology_validation.md), [`wp09_predictions.csv`](../reports/virtual_metrology/wp09_predictions.csv) | Dominated by one preregistered 4326.154 target; retained without post-hoc correction |
| CMP nominal power-mean speed, 100 nm/min reference, energy residual, mode gating, timestep refinement | [`wp08_cmp_validation.md`](../orchestration/reports/wp08_cmp_validation.md) | Synthetic WP08 structure and numerics only |
| Healthy 25%/400 ms sag retains full coupling support and identical CMP traces | [`wp10_coupling_validation.md`](../orchestration/reports/wp10_coupling_validation.md), `reports/sensitivity/wp10_negative_control_trace.csv` | Structural negative control, not a failed attempt to create an excursion |
| Degraded 500 J UPS interruption reduces end-DRESS pad activity by 5.3576% and later mean simulated MRR by 3.1926% | [`wp10_coupling_validation.md`](../orchestration/reports/wp10_coupling_validation.md), `reports/sensitivity/wp10_positive_chain_trace.csv` | Declared synthetic stress test; no safe envelope or controller claim |
| Saltelli analysis: 4,096 base samples and 36,864 evaluations | [`wp10_coupling_validation.json`](../reports/sensitivity/wp10_coupling_validation.json) | Conditional on selected topology, state, output, and synthetic parameter ranges |
| WP12 target: paired-reference ±5% active-POLISH band, 0.25 s persistence, 3 s horizon | [`wp12_early_warning_target.md`](../orchestration/decisions/wp12_early_warning_target.md), [`wp12_early_warning_validation.md`](../orchestration/reports/wp12_early_warning_validation.md) | Frozen simulator process-excursion target; not a defect, yield, or equipment event |
| TEST support: 1,932 eligible rows, 84 positive decisions, 24 runs, only 3 event-bearing runs | [`wp12_dataset_manifest.json`](../reports/early_warning/wp12_dataset_manifest.json) | Rows are not independent event replication; severe full-DRESS anchors limit diversity |
| Logistic: PR-AUC 0.9904, precision 0.9750, row recall 0.9286, event recall 3/3, median lead 2.71 s, coverage 0.9296 | [`wp12_early_warning_validation.md`](../orchestration/reports/wp12_early_warning_validation.md), [`wp12_validation.json`](../reports/early_warning/wp12_validation.json) | Named primary synthetic ensemble only; one false-alarm episode; no model selected for downstream use |
| Gradient boosted: PR-AUC 0.9130, row recall 1.0, event recall 3/3, median lead 2.71 s, coverage 0.8773 | [`wp12_early_warning_validation.md`](../orchestration/reports/wp12_early_warning_validation.md), [`wp12_validation.json`](../reports/early_warning/wp12_validation.json) | Named primary synthetic ensemble only; one false-alarm episode |
| Structural null: zero events but 30 logistic and 9 gradient-boosted false-alarm episodes | [`wp12_early_warning_validation.md`](../orchestration/reports/wp12_early_warning_validation.md) | Demonstrates missing topology-independent applicability; constrains WP15/WP16 |
| WP13 TEST support: 198 decision rows, 66 whole runs, six runs per ten known causes plus normal UNKNOWN | [`wp13_attribution_validation.md`](../orchestration/reports/wp13_attribution_validation.md), [`wp13_validation.json`](../reports/attribution/wp13_validation.json) | Primary final-window evaluation supplies a neutral valid-positive warning; conditional diagnostic classification only |
| WP13 hybrid: accuracy/macro recall 0.8636, UNKNOWN recall 1.0, known-cause coverage 0.85, selective accuracy 1.0 | [`wp13_attribution_validation.md`](../orchestration/reports/wp13_attribution_validation.md), [`wp13_validation.json`](../reports/attribution/wp13_validation.json) | All nine errors abstain to UNKNOWN; feature contributions and rule chains are not causal proof |
| WP13 rule-only comparator: accuracy/macro recall 0.9242 | [`wp13_attribution_validation.md`](../orchestration/reports/wp13_attribution_validation.md) | Outperforms the frozen primary hybrid; retained as comparator without post-TEST model switching |
| WP13 compound: 5/6 abstentions and 6/6 truth-set recall at two | [`wp13_attribution_validation.md`](../orchestration/reports/wp13_attribution_validation.md) | Ordered simulator truth is offline only and does not inflate single-cause accuracy |
| WP13 communication robustness: 0 known-cause coverage at 0.20 s delay and 0.15 at 10% dropout | [`wp13_attribution_validation.md`](../orchestration/reports/wp13_attribution_validation.md) | Demonstrates diagnostic unavailability rather than false known-cause substitution |
| Pre-WP13 holdout suite: 23/23 focused and 211/211 complete tests with warnings treated as errors | [`wp13_attribution_validation.md`](../orchestration/reports/wp13_attribution_validation.md) | Supports frozen software contracts and guarded opening; performance comes from separately hashed TEST artifacts |
| Pre-WP09 holdout suite: 192/192 with warnings treated as errors | [`wp09_virtual_metrology_validation.md`](../orchestration/reports/wp09_virtual_metrology_validation.md) | Supports frozen code/contracts and guarded target access; public-data performance comes from the separately hashed result artifact, not test count |

## Figure provenance

The six WP08/WP10 figures are generated by
[`generate_communication_figures.py`](../scripts/generate_communication_figures.py),
with hashes in
[`communication_figure_manifest.json`](../reports/figures/communication_figure_manifest.json).
The WP12 model-comparison and held-out timeline figures are generated by
[`validate_wp12_early_warning.py`](../scripts/validate_wp12_early_warning.py);
their SHA-256 values are recorded in
[`wp12_early_warning_validation.md`](../orchestration/reports/wp12_early_warning_validation.md).

The WP13 held-out confusion and per-class recall figures are generated by
[`validate_wp13_attribution.py`](../scripts/validate_wp13_attribution.py) during
the guarded one-shot execution. Their SHA-256 values are recorded in
[`wp13_attribution_validation.md`](../orchestration/reports/wp13_attribution_validation.md).

The WP09 model comparison, retained-validation scatter, and preregistered
sensitivity figures are generated by
[`generate_wp09_figures.py`](../scripts/generate_wp09_figures.py). Their frozen
input and output hashes are recorded in
[`wp09_figure_manifest.json`](../reports/virtual_metrology/figures/wp09_figure_manifest.json).

The communication manifest remains explicitly WP08/WP10-only. The two WP12
figures and two WP13 figures are synthetic and open loop. The three WP09
figures are public-data, offline virtual-metrology evidence in the undeclared
source-native target scale. None supports a real-fab, defect, yield,
controller-efficacy, causal-proof, or equipment claim.

## Reviewed manuscript artifact

`reports/paper/semifab_cmp_poc_draft.pdf` is a 17-page A4 PDF with SHA-256
`9437f7912372aed4579e0ad650cb73ae9edbbe06d741e102d5a48c4e6b1d420b`.
It was rebuilt from the repository root with
`conda run -n devkki make paper`. Title/evidence boundary, WP09 equations,
primary model table, three WP09 figures, WP12 results, WP13 equations,
comparator table, confusion/recall figures, evidence-status table, discussion,
limitations, and references passed representative visual review. The final
LaTeX log contains no overfull box, undefined-reference, undefined-citation,
or rerun warning.

## Literature-use boundary

The ten locally reviewed CMP papers and exact PDF hashes are listed in
[`wp10_literature_review.md`](../orchestration/reports/wp10_literature_review.md).
They support qualitative pressure--velocity, kinematic, pad-memory,
conditioning-water, slurry/rinse, and thermal pathways. They do not calibrate
facility-header pressure/flow thresholds, identify the PHM tool plumbing, or
support transfer of material-specific numerical effects.

## Pending manuscript results

The following remain protocols rather than results:

- WP14 no-action and fixed-threshold baselines;
- WP15 bounded predictive supervisory controller;
- WP16 independent safety filter;
- WP17--WP18 paired integrated controller evaluation.

When any pending item is completed, update the running paper, this evidence
map, the LaTeX manuscript, the claims matrix, the task manifest, and the project
status in the same reviewed change.
