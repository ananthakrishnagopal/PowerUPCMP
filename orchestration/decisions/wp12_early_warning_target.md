# Decision: WP12 early-warning target, uncertainty, and evaluation freeze

Date: 2026-07-12
Status: FROZEN FOR CONTROLLED IMPLEMENTATION
Task: T-WP12
Evidence plane: synthetic simulator only

## Decision question

WP12 asks whether observations available by decision time can predict a future
persistent departure of simulated active-polish average MRR from a predefined
synthetic operating envelope. It does not predict a physical defect, yield
outcome, equipment event, or real production excursion.

## Scientific rationale

A fixed band around the fresh-pad 100 nm/min reference would incorrectly label
normal pad conditioning/decay in other recipe states. The primary envelope is
therefore defined relative to an event-disabled paired nominal trajectory with
the same initial state, process schedule, declared topology, and static plant
parameters. The reference is generated and frozen offline before disturbed-run
labels; it is not visible to the online predictor as future truth.

The WP10 degraded-UPS case produced a 3.1926% later MRR difference. The primary
WP12 tolerance is deliberately the round, separately declared ±5% engineering
band. WP12 will not tighten the band to force that existing mechanism example
to become a positive event. More severe parameterized disturbances must create
positive labels if the simulator supports them.

## Primary target

Target ID: `SIM_ACTIVE_POLISH_MRR_TRAJECTORY_V1`.

For event-disabled reference MRR `R_ref(t)` and disturbed true simulated MRR
`R_true(t)`, define a point violation only while the CMP mode is `POLISH`:

```text
R_true(t) < 0.95 R_ref(t)
or
R_true(t) > 1.05 R_ref(t)
```

The reference must be positive and finite at the evaluated active-polish
sample. A qualifying excursion begins only after the violation persists for
0.25 s continuously in active POLISH. HOLD, PREPARE, DRESS, RECOVER, IDLE, and
COMPLETE never count as zero-MRR violations. A mode break or in-envelope sample
resets persistence.

Primary prediction horizon: 3.0 s.

The horizon exceeds configured sensor/communication delays and the dominant
lumped hydraulic/drive dynamics, includes the 1 s PREPARE interval, and leaves
a supervisory decision window before a later POLISH departure. Horizon
sensitivities at 1.0 and 5.0 s are descriptive only and cannot replace the
primary result.

At decision time `t`, the binary label is one when the first qualifying
excursion onset lies in `(t, t + 3.0 s]`. Labels are generated offline. The
future true state and event label are not online features.

## Eligibility and censoring

Decision cadence is 0.10 s. A decision is eligible only when:

1. the complete 3.0 s future horizon is present in the trace;
2. the future horizon contains at least 0.25 s of contiguous active POLISH, so
   a persistent violation could be observed; and
3. no qualifying excursion has already begun at or before the decision time.

Censor reasons are counted separately as `INCOMPLETE_FUTURE_HORIZON`,
`NO_ACTIVE_POLISH_OPPORTUNITY`, and `POST_EXCURSION_ONSET`. Censored rows do not
become negative labels. Negative runs remain eligible through the last complete
horizon. The first excursion step/timestamp remains offline evaluation data.

Cumulative-removal error is retained as a secondary diagnostic and future
controller metric. It is not silently OR-combined into this first classifier's
primary label.

## Causal feature boundary

Only observations with `arrival_timestamp_s <= decision_timestamp_s` may enter
a feature window. Source timestamps, reported timestamps, and arrival times
remain distinct. The feature-cutoff step and timestamp are recorded.

Primary sensor channels are:

- grid voltage;
- UPS output voltage;
- UPS battery energy;
- motor angular speed;
- pump volumetric flow;
- UPW supply pressure;
- UPW tool flow; and
- UPW temperature.

The predictor may use known static configuration (nominal references, battery
capacity/load ratio, declared topology, and process schedule). It may not use:

- true or observed future MRR;
- latent pad activity, coupling availability, or plant truth;
- event-active flags, event family, magnitude, or initiating-cause labels;
- simulator root-cause labels;
- offline reference trajectory values after the feature cutoff; or
- complete-trace features.

For each channel, features include latest value/age, 0.50 s rolling mean,
minimum, slope, and missing fraction. Additional causal memory features are
DRESS-to-date minima and integrated deficits of UPS output, normalized UPW
pressure, and normalized tool flow. These state summaries are computed only
from arrived records and preserve the delayed conditioning pathway after
utilities recover. Known phase indicators and time to scheduled POLISH are
allowed because they are recipe configuration, not future measured state.

All normalization constants are fixed engineering references from configuration
or known per-run static capacity. Any statistical imputer/scaler is fit on the
training groups only.

## Scenario and split freeze

The primary ensemble uses the declared `DRESSING_WATER_SUPPORT` topology with a
16 s run: DRESS from 0--6 s, PREPARE from 6--7 s, and POLISH from 7--16 s. The
plant receives the existing 3 s upstream warm-up. Fixed-seed parameterized
families are:

- normal operation;
- healthy voltage sag;
- grid interruption with varied UPS energy/duration;
- pump trip;
- valve restriction; and
- tool-demand spike.

Whole run IDs are assigned before simulation to disjoint training, calibration,
and test groups. Rows from one run never cross splits. The main held-out test
contains new parameter draws from known families. Compound interruption/demand
runs are an unseen-family robustness set. Severe no-connection/zero-link runs
are a structural robustness set and are not folded into the primary metric.
Split membership and seeds are configuration, never selected from performance.

### Version 1.1 training-feasibility amendment

The first version-1 experiment stopped before model fitting because TRAIN had
no positive label. No calibration/test metric or class count was written or
inspected. A read-only limiting-case audit showed that the frozen ±5% target is
reachable when conditioning service is lost for essentially the complete DRESS
interval: full-DRESS interruption and pump-trip mean POLISH MRR ratios were
0.94589 and 0.94578 relative to nominal.

Revision `1.1-feasibility-amendment` retains the target, persistence, horizon,
physics, coupling, seeds, model hyperparameters, calibration, and interpretation
gate. It adds one deterministic 0.00--5.99 s service-loss endpoint at the
highest severity of each interruption, pump-trip, valve-restriction, and
tool-demand-spike family in TRAIN, CALIBRATION, and TEST. All other parameter
draws remain unchanged. This endpoint is an explicitly synthetic hold-required
stress case, not a real equipment specification. The complete experiment must
restart from scratch.

## Model families and frozen hyperparameters

Required comparisons:

1. constant training-prevalence baseline;
2. logistic regression with training-only median imputation, standardization,
   balanced class weighting, `C=1`, and fixed seed; and
3. histogram gradient-boosted trees with 200 iterations, learning rate 0.05,
   at most 15 leaf nodes, minimum 20 samples per leaf, L2 regularization 0.1,
   balanced training weights, and fixed seed.

No test-label hyperparameter selection is permitted. Reinforcement learning is
outside WP12.

## Calibration and uncertainty

Base models are fitted on training run groups only. A one-dimensional sigmoid
calibrator with `C=1` is fitted on disjoint calibration groups using clipped
base probabilities. The alarm threshold is frozen at calibrated probability
0.5.

Classification uncertainty uses split-conformal prediction sets at nominal
90% marginal coverage (`alpha=0.10`) on a separate conformal-calibration split
as amended below.
The finite-sample `higher` quantile is recorded. Test reports include marginal
coverage, mean prediction-set size, empty/two-class set fractions, Brier score,
and 10-bin expected calibration error. Coverage is a held-out simulator result,
not a real-world guarantee.

### Version 1.2 independent-conformal methodological amendment

The first successful revision-1.1 run completed before a post-run methods audit
identified that its sigmoid calibrator and conformal quantile reused the same
dedicated calibration rows. Because the fitted sigmoid map was therefore a
function of the rows later scored for nonconformity, the construction did not
satisfy the intended independence condition for split conformal prediction.
This is a methodological defect even though the report labelled held-out
coverage as empirical rather than guaranteed.

Revision `1.2-independent-conformal-amendment` adds a new
`CONFORMAL_CALIBRATION` split with seed start 62000, three runs per declared
family, and the already frozen scenario generator. TRAIN continues to fit the
base model, CALIBRATION continues to fit the sigmoid map, and the new split is
used only for the conformal quantile. All four fit/evaluation roles use disjoint
whole-run IDs. The target, physics, features, existing scenario seeds, sigmoid
and base-model hyperparameters, TEST groups, alarm threshold, metrics, and
interpretation gates do not change.

The amendment was frozen because of the theoretical independence requirement,
not because of test performance. Revision-1.1 TEST probabilities are preserved
by the pre-amendment probability-payload hash
`5a4fb7011fd6688718455c9692689937caa679ea29c884cdca099835a9830ede`;
the revised run must reproduce it exactly. Only the conformal quantile,
prediction sets, coverage/set-size metrics, timing fields, and artifact hashes
are permitted to change. No revision-1.2 results were generated before this
amendment was recorded.

Eligible decision rows remain temporally dependent within runs, and the fixed
severity grid is not an iid sample of real operating conditions. Consequently,
the nominal 90% quantity is interpreted as descriptive row-level split-
conformal coverage on this synthetic ensemble, not a formal run-wise or
real-world guarantee.

## Metrics and event accounting

Required sample-level metrics are precision, recall, PR-AUC, prevalence,
specificity, Brier score, and calibration error. Warning alarms are threshold
crossing episodes, not every positive sample. Per-run event accounting reports:

- false alarm episodes per simulated monitored hour;
- qualifying excursion-event recall and missed-event rate;
- warning lead time from first alarm in the positive pre-onset window to true
  excursion onset; and
- prediction latency and throughput.

Results report aggregate values plus grouped bootstrap 95% intervals where
defined. Unseen compound and structural-null robustness remain separate from
the primary held-out result.

## Preregistered interpretation gate

An early-warning model may be described as useful on the tested synthetic
ensemble only if, on the primary held-out set, at least one learned model:

1. improves PR-AUC by at least 0.05 absolute over held-out prevalence;
2. detects at least 80% of qualifying excursion episodes;
3. has median warning lead time of at least 0.50 s; and
4. achieves split-conformal marginal coverage of at least 85% at the nominal
   90% target.

Failure of any gate is reported without changing the target, split, or test
set. False alarms per hour have no post-hoc acceptance threshold in WP12; they
must be reported and considered when freezing WP15's objective.

## Sensitivity and robustness

Target-definition sensitivities use ±3%, ±7.5%, 1 s/5 s horizons, and
0.10 s/0.50 s persistence without replacing the primary result. Observation
robustness varies noise, delay, and dropout using named seeds. Parameter and
topology robustness remains separate from prediction residual uncertainty.

## Interface and schema impact analysis

No frozen physical subsystem, `DynamicSubsystem`, `SensorModel`, `Scenario`,
`CmpBoundaryConditions`, or utility-coupling interface changes. Predictor 1.0
is implemented without changing its frozen fit/predict/save/load contract.

Canonical schema 2.4.0 already defines prediction and eligible offline
excursion-label records. Only eligible decisions are serialized as label
records; censor counts/reasons belong to the dataset/report manifest. Therefore
no canonical record change is required for WP12. The plant runtime remains at
schema/interface 2.4.0/3.2.0 and its frozen hash must reproduce exactly.

## Claim boundary

Passing WP12 can support only the claim that a named model predicts this
configured synthetic process-excursion target on held-out simulated run groups.
It does not establish a real-fab causal relationship, defect prediction, yield
benefit, equipment protection, controller efficacy, safety certification, or
production readiness.
