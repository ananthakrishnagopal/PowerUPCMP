# Phase 1 and Phase 2 scientific audit

Date: 2026-07-11  
Scope: repository governance, public-data pipeline, plant simulation,
observation layer, scenarios, tests, and readiness for CMP modelling  
Disposition: Phase 2 implementation evidence is useful, but the Phase 2 gate
must be treated as provisional and corrective work is required before T-WP08
or T-WP10 implementation.

## Executive conclusion

The repository has a strong provenance and claims-control foundation, a
carefully preserved PHM archive, deterministic component code, immutable state
records, explicit sensor corruption, and reproducible scenario definitions.
Those are valuable foundations.

The review nevertheless found several phase-gate defects that make immediate
CMP implementation scientifically unsafe:

1. The public PHM data cannot be represented honestly by the frozen SI-only
   public-measurement schema.
2. The implemented plant classes do not conform to the frozen
   DynamicSubsystem interface.
3. The PHM feature pipeline aggregates preparation, polishing, ending, and
   post-CMP cleaning rows together and does not satisfy the declared outlier
   and timestamp-processing acceptance criteria.
4. The pump and UPW models do not preserve a consistent pump-system operating
   point or hydraulic mass balance under important limiting cases.
5. The current reference voltage sag is almost completely masked by the UPS
   and produces no UPW tool-flow change.
6. Sensor timestamp jitter can make an observation arrive before its source
   state exists.
7. Scenario validation accepts physically invalid magnitudes, overlapping
   multi-cause events under a single-cause policy, and a zero-duration ramp
   that divides by zero.

The correct response is not to tune a larger UPW-to-MRR gain. The Phase 1
contracts and the affected Phase 2 components should receive bounded
remediation, followed by a replacement Phase 3 model decision.

## Audit method

The review was performed by:

- re-reading the Phase 1 charter, architecture, schema, interfaces,
  assumptions, risks, claims, dependency graph, manifest, and checkpoints;
- inspecting every Phase 2 source module and its tests;
- checking completed-task outputs and Python method signatures;
- reading the official PHM challenge description bundled with the supplied
  archive;
- recomputing PHM label, timing, grouping, and process-signal summaries;
- inspecting the non-authoritative derived experiment code while keeping it
  excluded from the raw-data pipeline;
- replaying the 25 percent, 400 ms voltage sag through the implemented
  electrical, drive, pump, and UPW components;
- evaluating hydraulic mass-balance and pump-trip limiting cases;
- testing sensor timestamp causality and scenario edge cases; and
- reviewing primary CMP research and official pump/water references.

No source implementation was changed during this review.

## Findings summary

| ID | Severity | Area | Finding | Consequence |
|---|---|---|---|---|
| GOV-01 | Critical | Interface | Electrical, drive, pump, and UPW classes omit the frozen reset config argument and observe method; simulation/base.py is absent. | The Phase 1 interface freeze is not implemented or contract-tested. |
| GOV-02 | High | Configuration | configs/default.yaml, required by the architecture as the complete safe baseline, is absent. | Component defaults are scattered in Python and cannot be hashed as one run configuration. |
| GOV-03 | Critical | Schema | PublicMeasurementRecord validates source values using the canonical signal unit, so a non-SI or unknown source unit cannot be stored before conversion. | PHM MRR cannot be represented without pretending its unit is m/s. |
| GOV-04 | High | Governance | T-WP03 is COMPLETE although tests/unit/test_phm_cmp.py is missing; assumptions, data-source status, README, and implementation-plan status are stale. | The manifest and checkpoint overstate completion. |
| DATA-01 | Critical | PHM semantics | Official documentation says all Table 1 process columns are scaled with hidden values. The original challenge does not state the MRR unit. | PHM process magnitudes cannot calibrate SI pressure, flow, speed, or Preston parameters. |
| DATA-02 | Critical | PHM labels | Four training labels are 4,129 to 4,326; all other training labels are at most about 163, and test/validation maxima are below 164. Dividing the four by 60 yields 68.8 to 72.1. | A likely unit/conversion anomaly can dominate MSE and model fitting, but cannot be silently changed. |
| DATA-03 | Critical | PHM features | Current aggregation mixes all rows for a wafer/stage. Challenge-specific research identifies preparation, main polish, ending, and post-CMP cleaning phases, with cleaning data that may copy a prior wafer. | Current features mix non-removal and potentially copied signals into the MRR model. |
| DATA-04 | High | PHM timing | There are 2,221 zero timestamp increments, 2,005 increments above 10 s, and a maximum within-wafer/stage gap above 15,000 s. Absolute TIMESTAMP is aggregated as a feature. | Row-weighted statistics and absolute-time features can encode sampling/gap/run-order artifacts. |
| DATA-05 | High | Splits | The primary split is a random wafer-group split only. No chronological, machine-held-out, stage/regime, or official test/validation policy is implemented. | Leakage by wafer is prevented, but generalization claims remain weak. |
| DATA-06 | High | Acceptance evidence | The missingness report does not report label outliers, timestamp duplicates/gaps, or process-phase coverage, despite T-WP03 acceptance language requiring outlier and timestamp processing. | T-WP03 is incomplete scientifically even though raw loading and joins work. |
| ELEC-01 | Medium | Electrical | frequency_time_constant_s and frequency_alpha are unused in the state update. | The configuration implies frequency dynamics that do not exist. |
| ELEC-02 | High | UPS | A-006 mentions an energy limit, but no battery energy, load, or capacity state exists. | UPS ride-through duration and load feasibility cannot be studied. |
| CHAIN-01 | Critical | Reference chain | The implemented 25 percent, 400 ms sag gives minimum UPS voltage 0.865536 pu, motor speed 187.1657 versus 188.5 rad/s, pressure 299.235 versus 300 kPa, and unchanged 1.0e-4 m3/s tool flow. | The current reference scenario does not create the intended UPW-flow or meaningful CMP disturbance. |
| PUMP-01 | Critical | Pump physics | Pump flow and head are independently imposed from affinity laws without solving their intersection with a system curve. | The pump duty point is over-specified and can be inconsistent with the hydraulic network. |
| UPW-01 | Critical | Conservation | At a closed valve and pressure ceiling, 5.0e-5 m3/s disappears from the balance. | Hydraulic conservation is violated. |
| UPW-02 | Critical | Transient | A pump trip collapses supply pressure from 300 kPa to 100 kPa in one 10 ms step because the head ceiling overrides compliance; the same returned state still reports the old tool flow. | The declared hydraulic compliance does not govern a key transient, and state variables are time-inconsistent. |
| UPW-03 | High | Water-quality semantics | conductivity_proxy is assigned physical unit S/m and nominal value 0.055 S/m. Type-I/ultrapure water near 25 C is about 0.055 microS/cm, or 5.5e-6 S/m. | A quantity described as a proxy is numerically and dimensionally confusable with a physical conductivity measurement. |
| SENSOR-01 | Critical | Online timing | With deterministic negative timestamp jitter, arrival time can be earlier than the source timestamp; one reviewed case had source 10 s and arrival 4.1058 s. | An online predictor could receive a future latent state before it exists. |
| SENSOR-02 | Medium | Validation | Sensor bounds do not reject non-finite configured minimum/maximum values, and input record run/step/time consistency is not checked. | Invalid observation configurations or mismatched records can pass too far downstream. |
| SCEN-01 | High | Scenario math | A zero-duration RAMP validates and then raises ZeroDivisionError at its start time. | Declarative validation does not guarantee executable replay. |
| SCEN-02 | High | Scenario bounds | A valve position magnitude of -5 validates. Similar target-specific pressure, flow, temperature, and voltage bounds are incomplete. | Invalid physical events can enter the runtime. |
| SCEN-03 | High | Cause policy | Overlapping events with different start times are not detected as concurrent; only equal start times are checked. | Compound causes can be silently labelled SINGLE_EVENT. |
| SCEN-04 | Medium | Semantics | STEP and PULSE have identical finite-duration behavior, while root-cause labels mix initiating disturbances with intermediate states such as UPS transfer. | Replay and attribution semantics are ambiguous. |
| TEST-01 | High | Scientific checks | Tests cover bounds and deterministic behavior but not frozen interface conformance, hydraulic balance, pump-system duty point, pump-trip decay, timestamp causality, timestep convergence, zero-duration ramps, overlap policy, or target bounds. | Passing tests do not cover the highest scientific risks. |
| DOC-01 | Medium | Documentation | README still says no dataset and no simulator are present. data_sources.yaml says loader pending. implementation_plan.md says Phase 1 is in progress. | Repository status is misleading to a new reviewer. |

## What remains sound

The following evidence survives the audit and should be retained:

- The user-supplied archive SHA-256 and ZIP CRC checks.
- Selective extraction of 558 original time-series/removal-rate members.
- Explicit preservation of 58 header-only traces without imputation.
- Exclusion of answer directories and derived experiments from raw inputs.
- Exact column validation and many-to-one training-label join audit.
- Frozen dataclass state values and component-level finiteness/range checks.
- Pump affinity scaling at homologous reference points.
- Deterministic electrical, drive, pump, sensor, UPW, and scenario replay for
  the cases actually tested.
- Separation of latent state and observation record types.
- Explicit missing/dropped sensor observations.
- Claims controls that reject defect, yield, equipment-damage, production,
  and real-time guarantees.
- The one-step controller-action timing intention.

These are implementation or provenance properties. They do not validate
real-fab physical parameters.

## PHM data findings in detail

### Native data semantics

The official challenge describes the target as average removal rate computed
from material thickness before and after polishing. It states that the Table 1
process columns are scaled using hidden values. Later NIST-affiliated work
reports MRR results in nm/min, but the original source file does not provide a
target unit declaration. The project should therefore preserve:

- the original numeric target;
- native dataset-unit status;
- a literature-reported nm/min interpretation as separate provenance; and
- no conversion to m/s unless a source-supported conversion decision is
  recorded.

### Label anomaly

The four extreme training values are:

| Wafer | Stage | Original target | Original divided by 60 |
|---|---|---:|---:|
| 2058207580 | A | 4326.15405 | 72.102568 |
| 1834206730 | A | 4202.11245 | 70.035207 |
| 1834206944 | A | 4182.41655 | 69.706942 |
| 1834206972 | A | 4129.49400 | 68.824900 |

Three occur in CMP-training-088 and one in CMP-training-152; all use machine
ID 2. Several associated groups contain zero pressure and slurry values over
the entire group. The excluded, non-authoritative experiment code in the
supplied repository discards target values above 1000 as anomalies. That is
supporting context, not authority to modify raw labels.

Required policy:

1. Primary public-data results retain all original labels.
2. A preregistered sensitivity analysis excludes the four labelled rows.
3. A second, explicitly hypothetical sensitivity divides only those four by
   60.
4. No policy is selected based on test or validation performance.
5. All three results are reported, and the four source IDs remain auditable.

### Process phases

Challenge-specific research reports at least four phases: preparation, main
polishing, ending, and post-CMP cleaning. It also reports two run types and
serious missingness in one type. The current mean/std/min/max aggregation
cannot distinguish those phases.

Required preprocessing:

- sort within wafer, stage, trace, and chamber;
- preserve duplicates and gaps as quality evidence;
- segment discontinuities before feature calculation;
- detect process modes using chamber plus pressure/slurry/rotation patterns;
- compute time-weighted, phase-specific statistics;
- never use the target to assign a process regime;
- fit any thresholds or change-point transformations on training groups only;
- keep complete-trace virtual-metrology features separate from streaming
  early-warning features.

## Plant-model findings in detail

### Pump and hydraulic network

Affinity laws scale homologous pump operating points; they do not independently
fix both flow and head for an arbitrary network. The revised model must include
a speed-scaled pump curve and solve the operating point against the hydraulic
system. A minimal conserved form is:

\[
C_h\frac{dP_s}{dt}
=Q_p(P_s-P_r,n)-Q_{\mathrm{tool}}(P_s,P_r,v)
-Q_{\mathrm{return}}(P_s,P_r)-Q_{\mathrm{relief}}(P_s).
\]

The relief/bypass term must make pressure limiting explicit and preserve the
mass balance. A pump trip must reduce pressure according to compliance and
outflows, not by an instantaneous head clip.

### Reference electrical sag

The current UPS does what its parameters request: it largely masks the grid
sag. Therefore, a large downstream MRR excursion cannot be obtained honestly
from the existing reference configuration. The project should distinguish:

- a healthy-UPS ride-through scenario expected to cause little/no excursion;
- a degraded/overloaded/bypass transfer scenario;
- a direct pump-trip scenario;
- a hydraulic demand/valve scenario; and
- a compound scenario.

The healthy-UPS case is scientifically valuable as a negative control. It
should not be retuned to force a positive result.

### UPW conductivity

If the quantity remains a non-physical water-quality proxy, its canonical unit
should be dimensionless. If it is intended to model conductivity, its value,
temperature compensation, unit conversion, and physical range must be
corrected and documented. It must not enter CMP MRR in the first PoC.

## Required remediation gates

### Gate R1: contract and configuration

- Add or formally revise DynamicSubsystem and contract tests.
- Add a complete, strictly validated configs/default.yaml.
- Add parameter provenance IDs to component configurations and run manifests.
- Revise the public-measurement schema to preserve unknown/native units.
- Reconcile README, assumptions, data sources, implementation plan, manifest,
  and project status.

### Gate R2: PHM semantics

- Add the missing unit test file.
- Add official-description provenance.
- Add label anomaly, duplicate, gap, duration, and phase reports.
- Implement phase-aware and time-weighted features.
- Implement official holdouts plus wafer, temporal, and machine stress splits.
- Add preprocessing fit-scope audits.

### Gate R3: plant physics

- Replace the over-specified pump output with pump-curve/system interaction.
- Preserve hydraulic mass balance with an explicit relief path.
- Make compliance govern pressure transients.
- remove or implement frequency dynamics and UPS energy/capacity.
- perform timestep-convergence and limiting-case checks.

### Gate R4: online and scenario timing

- Guarantee arrival_timestamp_s is not earlier than source generation time.
- Make decision visibility depend on arrival time.
- Reject invalid scenario target ranges and zero-duration dynamic profiles.
- Detect interval overlap for compound cause policy.
- Separate initiating disturbance labels from propagation-state labels.

T-WP08 and T-WP10 should remain blocked until R1 through R4 pass.

## Sources reviewed

- Official PHM 2016 challenge:
  https://phmsociety.org/conference/annual-conference-of-the-phm-society/annual-conference-of-the-prognostics-and-health-management-society-2016/phm-data-challenge-4/
- Li et al., Assessment of Physics-Based and Data-Driven Models for MRR
  Prediction in CMP:
  https://doi.org/10.2991/iceea-18.2018.26
- Rahman et al., Physics-Informed Multi-Task Learning for MRR Prediction:
  https://tsapps.nist.gov/publication/get_pdf.cfm?pub_id=957637
- DOE, Variable Speed Pumping and Pumping System Performance:
  https://www1.eere.energy.gov/manufacturing/tech_assistance/pdfs/variable_speed_pumping.pdf
- NIST Type-I water reference:
  https://www.nist.gov/system/files/documents/2017/05/09/NISTIR_7383_2013-04-24_2015-07-13Rev.pdf

## Audit decision

Phase 1 remains a useful architectural baseline but needs controlled schema and
interface amendments. Phase 2 should not be discarded; it should be reopened
for the four bounded remediation gates above. The existing Phase 3 CMP/utility
decision is not suitable for implementation and should be withdrawn in favor
of the redesign report.
