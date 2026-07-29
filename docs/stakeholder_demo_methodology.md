# Stakeholder Demo Methodology

## Executive Purpose

This demonstration is designed to answer one business and scientific question:

> Can a semiconductor CMP process be supervised using early warning of
> utility-driven process risk, so that a bounded hold/resume response can be
> evaluated before any production-tool integration?

The demo shows the concept in a synthetic, reduced-order environment. It is not
a production claim. Its value is that it makes the proposed control philosophy
visible, auditable, and technically discussable before asking for expensive
fab-data or tool-integration work.

## Business Rationale

CMP is sensitive to disturbances that do not originate inside the polishing
module alone. Electrical supply, drive behavior, pump flow, UPW pressure,
conditioning support, and thermal conditions can all affect process stability.

The business problem is not just whether a tool can detect a fault after the
process has already moved out of range. The more valuable question is whether
the process can be supervised early enough to avoid continuing through a risky
recipe segment.

The demo therefore focuses on a conservative supervisory action:

```text
detect rising process risk
-> pause recipe progress
-> wait for recovery
-> resume under bounded conditions
```

This is intentionally a **risk-reduction workflow**, not a claim of automatic
yield improvement. The intended stakeholder takeaway is:

> The POC provides a transparent way to evaluate whether utility-aware early
> warning can support safer CMP supervisory decisions.

## Scientific Rationale

The methodology is simulation-first because real CMP intervention studies are
expensive, operationally risky, and hard to interpret without a controlled
causal setup.

A synthetic simulator lets us control:

- the initiating disturbance;
- the disturbance timing;
- whether the utility path is connected or disconnected from CMP;
- what the controller is allowed to observe;
- when a warning is issued;
- when a hold/resume action occurs;
- the comparison between disturbed and recovered behavior.

This control is scientifically useful because it separates three questions:

1. **Propagation:** can a utility disturbance plausibly create process risk?
2. **Prediction:** can arrived observations warn before the risky polishing
   interval?
3. **Supervision:** can a bounded action be triggered without giving the model
   unsafe direct control authority?

The demo addresses these questions qualitatively for stakeholder review. Full
scientific validation remains in the formal validation reports.

## Demonstration Scenario Set

The current dashboard is organized around replayable scenarios rather than
ad-hoc live tuning. The preferred recording path is:

1. **Normal baseline** — utilities remain healthy, MRR reaches a stable polish
   plateau, warning probability stays low, and no hold occurs.
2. **Power-to-water cascade** — grid voltage drops first; the electrical
   disturbance propagates through drive/pump support; UPW pressure and flow
   degrade downstream; warning probability crosses the hold gate; CMP enters a
   bounded safe hold and later resumes.
3. **UPW pump trip after stable polish** — water-side support degrades while
   grid support remains nominal. This is a simpler water-dominant fault case.

The grid-interruption replay is retained as backup technical evidence. The
live sandbox is for parameter exploration, not the main recording path.

## Physical Modeling Basis

The physical story is built around a reduced-order CMP and utility model.

The utility side represents:

- electrical/UPS behavior;
- drive and motor response;
- pump flow;
- UPW pressure and tool flow;
- effective utility support reaching CMP.

The CMP side represents:

- process mode;
- contact and rotary exposure;
- dressing/conditioning state;
- slurry/utility support;
- pad condition;
- material removal rate.

The flagship causal pathway in the dashboard is the power-water cascade:

```text
stable POLISH MRR
-> grid voltage sag
-> drive/motor and pump support degradation
-> UPW pressure and flow degradation
-> elevated MRR-exposure risk
-> warning threshold crossing
-> predictive safe hold
-> controlled resume after utility recovery
```

This is a reduced-order causal hypothesis. It is useful for a POC because the
sequence is inspectable: the viewer can see the initiating power-side signal,
the downstream water-side response, the warning signal, the operating-mode
change, and the resulting MRR pause. It is not claimed to be a calibrated model
of a specific production CMP tool.

## Mathematical Framing

The CMP model follows a pressure-velocity removal structure inspired by
Preston-style CMP modeling:

```text
removal rate ~ pressure exposure × relative velocity exposure × process modifiers
```

In simplified terms:

```text
MRR = base removal
      × pressure-velocity exposure
      × slurry/process availability
      × pad-condition modifier
      × recipe modifier
```

The utility-to-CMP connection is represented as an availability bottleneck:

```text
availability = min(pressure support, flow support)
```

This is intentionally conservative. If either pressure or flow is insufficient,
the service available to the CMP support path is limited.

Dashboard quantities use the following display conventions:

- **Grid voltage** is shown in per-unit (`pu`). `1.00 pu` means nominal
  voltage. `0.80 pu` means 80% of nominal voltage.
- **UPW pressure health** is shown as percent of nominal pressure in the
  scenario facts. For example, 45% means the minimum replayed pressure is 45%
  of the nominal reference used by the simulator.
- **MRR** is shown in nm/s after converting from the simulator's SI output.
- **Warning probability** is a model score on `[0, 1]`; the dashboard hold gate
  is displayed as a threshold line.

The warning model is framed as a probability of a future active-polish MRR
excursion:

```text
P(future MRR excursion within horizon | arrived observations)
```

The supervisory policy then applies simple, inspectable gates:

```text
hold when risk is high and uncertainty supports the positive warning
resume when risk clears and recovery conditions are satisfied
```

The important methodological point is that the model does not directly command
arbitrary tool actuation. It only proposes a bounded supervisory response, and
that response is checked before it becomes final.

## Model Methodology

The warning concept is based on causal streaming features:

- observations must have arrived by the decision time;
- future simulator truth is not used as an online feature;
- process risk is predicted ahead of the active polishing interval;
- uncertainty is represented through a decision set, not only a raw score.

This is the right modeling structure for a future shadow-mode deployment
because it mirrors the real operational constraint: a controller can only act
on information that has actually arrived.

The demo does not claim that the displayed warning model is ready for
production. It demonstrates the **form** of the decision loop that a future
validated model would occupy.

### Predictive Layer Used In The Dashboard

The dashboard predictive layer uses the local artifact:

```text
reports/early_warning/models/dashboard_warning.pkl
```

The artifact metadata records:

```text
model_kind: GRADIENT_BOOSTED
artifact_version: 1.0.0
```

In implementation terms, this is a scikit-learn
`HistGradientBoostingClassifier`. It is **not** XGBoost, LightGBM, or CatBoost.

The model was trained from simulator-generated traces, not fab telemetry. The
training script is:

```text
scripts/train_dashboard_warning.py
```

The training data source is the same deterministic CMP/utility simulator used
by the replay artifacts. The script generates synthetic scenario runs,
constructs online feature rows from observations that have arrived by each
decision time, and labels whether a near-future utility/MRR risk condition
appears within the prediction horizon.

The dashboard target can be summarized as:

```text
recent arrived utility/CMP observations
-> probability of near-future utility/MRR risk
```

The model input is a streaming feature vector built from utility and CMP
signals such as grid voltage, motor/pump response, UPW pressure/flow, process
mode context, and recent signal history. The feature extractor enforces the
online constraint: future simulator truth is used to create offline labels, but
not as an online feature.

The fitted predictor combines:

- a scikit-learn `HistGradientBoostingClassifier` for the base warning score;
- probability calibration for a more interpretable warning probability;
- a conformal-style prediction set used as an uncertainty signal;
- a supervisor threshold, currently displayed as the hold gate in the
  dashboard.

Current dashboard-warning artifact metrics are stored in:

```text
reports/early_warning/dashboard_warning_metrics.json
```

Key values from the current artifact:

| Metric | Current value | Interpretation |
| --- | ---: | --- |
| Training/evaluation rows | 16,968 total; 3,232 test rows | Synthetic feature rows generated from simulator traces |
| Positive fraction | 0.356 | About 36% of rows are labeled near-future risk |
| PR-AUC | 0.925 | Strong row-level separation relative to prevalence |
| Precision | 0.888 | When the model warns, most row-level warnings are true positives |
| Recall | 0.748 | The model catches about three quarters of positive risk rows |
| Specificity | 0.947 | Most negative rows remain quiet |
| Brier score | 0.084 | Probability-calibration error summary; lower is better |
| Expected calibration error | 0.029 | Average probability calibration gap |
| Conformal coverage | 0.908 | Prediction-set coverage on the held-out synthetic rows |
| Median warning lead time | 1.16 s | Typical warning lead before linked synthetic event onset |
| Event recall | 10/22 = 0.455 | Event-level detection is incomplete and should not be overclaimed |
| False alarms/hour | 456.7 simulated h^-1 | High at this operating point; useful for demo, not production tuning |

The stakeholder interpretation should be balanced:

```text
The artifact is strong enough to illustrate the predictive-supervision loop,
but it is not a production warning model. Row-level discrimination is good;
event-level recall and false-alarm behavior still require tuning and validation
against customer data.
```

Expected stakeholder questions:

- **Where did the training data come from?** From synthetic simulator traces
  generated inside this repository.
- **Is any real fab data used?** No.
- **What model is used?** A scikit-learn `HistGradientBoostingClassifier` with
  calibration and a conformal-style uncertainty set. It is not XGBoost.
- **What is the model predicting?** Whether near-future utility/MRR risk is
  likely from arrived observations.
- **Does the model directly command the tool?** No. It produces a warning
  probability; the supervisor proposes a bounded hold/resume action; the safety
  filter checks the final action.
- **Is this production-ready?** No. It is a simulator-backed methodology and
  communication artifact for deciding whether shadow-mode validation is worth
  pursuing.

## Control Methodology

The demo uses hold/resume because it is the most defensible supervisory action
at this stage.

More aggressive control, such as changing speeds, valve positions, or
downforce, would require stronger physical calibration and equipment authority.
The current POC does not have that evidence. A safe hold is more conservative:
it stops recipe progress during a risky interval and allows the process to
resume only after recovery.

This matters to stakeholders because the POC is not asking for trust in an
unbounded AI controller. It is demonstrating a bounded supervisory envelope:

```text
warning model -> proposed hold/resume -> safety check -> final bounded action
```

## Business Outcome Framing

The demo should be described as evidence for a decision process, not as proof
of wafer savings.

Supported wording:

```text
The POC demonstrates a traceable synthetic path from utility disturbance to
future CMP process-risk warning and bounded supervisory response.
```

Unsupported wording:

```text
The POC proves wafer savings, yield improvement, defect prevention, or
production-safe autonomous control.
```

The business value is that the POC identifies a practical next step:

> evaluate utility-aware CMP warning and supervisory hold logic in a
> customer-data shadow-mode study before considering production integration.

## Why This Is Useful Even Without Real-Fab Validation

A real-fab validation program should not begin with direct closed-loop control.
It should begin with a clear, testable hypothesis and a bounded evaluation
method.

This demo provides that method:

- define disturbances and candidate risk signatures;
- quantify warning lead time and false alarms;
- compare hold/resume policy against no-action and threshold baselines;
- measure cycle-time cost separately from process-risk reduction;
- keep safety authority independent from the predictive model;
- preserve the boundary between public data, simulator evidence, and future
  customer telemetry.

That is the scientific and business justification for the POC.

## Dashboard Story Layout

The story dashboard is designed to be read as a left-to-right causal chain:

```text
Facility layer -> Prediction layer -> Process outcome -> Supervisor action
```

- **Facility layer:** grid voltage, UPW pressure health, and pump-flow health.
  In the cascade replay, grid voltage falls first and water-side support
  follows.
- **Prediction layer:** warning probability and the hold gate. This separates
  model inference from physical process measurements.
- **Process outcome:** MRR. When MRR goes to zero during `HOLD`, that is the
  intended consequence of pausing polishing, not evidence that the physical
  process collapsed.
- **Supervisor action:** operating mode. A transition to `HOLD` is the visible
  bounded control response.

The scenario box summarizes the selected replay with self-contained units:
fault timing in seconds, grid voltage in per-unit, UPW pressure as percent of
nominal, and the artifact seed for reproducibility.

## What The Demo Demonstrates

The demo demonstrates:

- a plausible utility-to-CMP risk pathway;
- an early-warning supervisory concept;
- conservative hold/resume action authority;
- separation between prediction and final action;
- repeatable stakeholder communication;
- a framework for future shadow-mode evaluation.

## What The Demo Does Not Demonstrate

The demo does not demonstrate:

- real-fab telemetry performance;
- production tool safety;
- causal root-cause proof;
- yield improvement;
- defect prevention;
- equipment protection certification;
- final controller readiness.

These claims require future experimental data, customer-tool context, and
independent safety review.

## Recommended Technical Narrative

For a technical audience, present the method as:

1. **Controlled causal setup:** a synthetic utility disturbance is introduced.
2. **Physical propagation hypothesis:** utility degradation affects CMP support
   state and future MRR risk.
3. **Online prediction constraint:** the warning uses only arrived
   observations.
4. **Bounded supervisory response:** the model proposes hold/resume, not
   arbitrary tool control.
5. **Safety separation:** final action authority is independent from the
   predictive score.
6. **Business next step:** validate in shadow mode with customer data before
   considering production integration.

## Review Checklist

Before using the demo externally, confirm that the presentation states:

- synthetic simulator only;
- not real-fab telemetry;
- not production control;
- not yield or defect validation;
- hold/resume is conservative supervisory control;
- future work is shadow-mode customer-data validation.
