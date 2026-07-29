# PowerUPCMP Customer Demo Speaker Notes

## Demo objective

Show how a controlled CMP utility disturbance moves through the simulator,
becomes a warning signal, and results in a bounded supervisory safe hold. Keep
the distinction between **demonstrated in simulation** and **validated in a
fab** explicit throughout the conversation.

Suggested duration: 15 minutes, followed by 10 minutes of technical questions.

## Before the meeting

1. Install the project in the documented Python environment.
2. Start the dashboard with `conda run -n devkki python src/semifab_poc/dashboard/server.py`.
3. Open `http://localhost:8080/story.html` and confirm the story dashboard is
   visible.
4. In **Selected scenario**, confirm the scenario list contains the baseline,
   `stakeholder-demo-stable-polish-fault`,
   `stakeholder-demo-grid-interruption`, and
   `stakeholder-demo-power-to-water-cascade`, with **Power-to-water cascade**
   selected for the main recording.
5. Use **Run** as the recording path. The **Live sandbox** is only
   for parameter exploration after the main replay has been shown.
6. Keep the repository documentation available for provenance questions. The primary references are `docs/stakeholder_demo_methodology.md`, `docs/assumptions_and_limitations.md`, `docs/architecture.md`, and the WP12/WP13/WP15/WP16 validation reports.

## 1. Frame the problem (1 minute)

**Say:** “This is a technical proof of concept for supervisory control of a CMP process when utility conditions degrade. The dashboard is a local, read-only view of a deterministic simulator. It is designed to make the causal chain and the control decision inspectable.”

Do not lead with disclaimers on the recording surface. Instead, frame the
screen as a replay of a controlled simulator artifact and reserve validation
boundaries for questions.

## 2. Establish the baseline (1 minute)

Use the `stakeholder-demo-normal-baseline` replay first, then switch to the
`stakeholder-demo-power-to-water-cascade` replay. Live scenarios are backup.

**Say:** “We start with a healthy reference. The point is to establish expected process modes and avoid interpreting every model signal as an event.”

Use the charts to identify the normal mode progression. The expected result is no safe hold and a low warning probability. This is a useful negative control: the supervisor should not intervene without a simulated disturbance.

## 3. Replay the power-water cascade trace (4 minutes)

Click **Run**. Keep the dashboard visible while the stream
progresses. The trace is a curated synthetic replay named
`stakeholder-demo-power-to-water-cascade.json`. It is the preferred recording
artifact because it shows the power-water nexus directly: grid support drops
first, UPW pressure and flow degrade downstream, and the supervisor holds after
the warning crosses the gate.

**Say:** “The important point is timing. CMP is already in stable polishing.
The grid disturbance appears first. Water-side support follows. The warning
probability then crosses the hold gate, and the supervisor pauses polishing
while the coupled utility system recovers.”

Walk through the screens in this order:

- **Scenario box:** explain the replay facts. Fault timing is in seconds.
  Grid voltage is in per-unit: `1.00 pu` is nominal voltage. UPW pressure is
  shown as percent of nominal pressure. The artifact seed is the reproducible
  simulator seed.
- **Event timeline:** establish the sequence first: stable polishing, utility
  disturbance, warning threshold crossing, supervisor proposal, safety
  approval, hold, controlled resume, and completion.
- **Facility layer:** show that grid voltage moves first and UPW pressure/flow
  follow. This is the hybrid power-water behavior.
- **Prediction layer:** show the warning probability and the hold gate. Keep
  this distinct from physical MRR.
- **Process outcome:** point out the stable MRR plateau before the disturbance.
  When MRR goes to zero during `HOLD`, explain that polishing is intentionally
  paused.
- **Supervisor action:** show the mode transition. A `HOLD` state is the
  visible bounded control response.

When the decision banner changes, say: “The value is the traceability: named
utility disturbance, visible facility response, warning signal, bounded hold,
and controlled resume.”

## 4. Compare against no action (2 minutes)

If time allows, open the **Live sandbox**, change **Protection mode** to
**Unprotected baseline**, and run a matching live scenario. Point out that the
seed, duration, and disturbance settings are held constant. Treat this as a
qualitative backup comparison, not as the formal evidence path for the
recording.

**Say:** “This is the paired comparator. A credible efficacy study needs the same disturbance and initial conditions, with only the controller policy changed.”

Compare the operating-mode chart and the process curve. Avoid claiming saved wafers or a measured yield improvement from this view. The current dashboard is a trace viewer; paired aggregate metrics belong in the evaluation reports.

## 5. Replay evidence and limitations (2 minutes)

Point to **Selected scenario** and the replayable baseline/fault traces.

**Say:** “The replay path shows that the dashboard is not dependent on a live calculation for presentation. It can replay a versioned local artifact, which is useful for review, audit, and a repeatable customer conversation.”

Explain that the selected compact replay artifact contains truth rows,
predictions, proposed actions, safety decisions, and summary KPIs. It is marked
as a synthetic communication artifact rather than a new validation result.

## 6. Technical deep dive (4 minutes)

Use these prompts if the audience wants more detail:

- **Architecture:** configuration and scenario create the disturbance; the utility and CMP subsystems produce the simulated trace; online features and predictions feed supervisory control; the safety contract bounds the action path.
- **Predictive layer:** the dashboard warning artifact is
  `reports/early_warning/models/dashboard_warning.pkl`. It is a calibrated
  scikit-learn `HistGradientBoostingClassifier` trained on synthetic simulator
  traces generated by `scripts/train_dashboard_warning.py`. It is not XGBoost.
- **Training target:** recent arrived utility/CMP observations -> probability
  of near-future utility/MRR risk. Future simulator truth is used only to build
  offline labels, not online features.
- **Inputs:** streaming features from signals such as grid voltage,
  motor/pump response, UPW pressure/flow, process mode context, and recent
  signal history.
- **Current dashboard model metrics:** PR-AUC 0.925, precision 0.888, recall
  0.748, specificity 0.947, Brier score 0.084, ECE 0.029, conformal coverage
  0.908, median warning lead time about 1.16 s. Event recall is lower
  (10/22 = 0.455) and false alarms are high at this operating point, so the
  model should be described as a demonstration warning artifact, not a
  production model.
- **Timing:** the dashboard samples the simulation for readability. It is not a latency benchmark or a promise of real-time execution.
- **Model boundary:** the warning is an early-warning signal for the frozen simulator target. Root-cause attribution and uncertainty must be discussed with their dedicated validation artifacts and limitations.
- **Data boundary:** public PHM data and simulator results are separate evidence planes. A public-data offline metric should not be presented as proof of online control.
- **Safety:** a demo `HOLD` is an observed simulator mode approved by the local safety-filter path for this synthetic replay. It is not an independent production safety certification.

## Questions to handle carefully

**“How many wafers were saved?”**

“This dashboard does not support that claim. Wafer yield and physical defect outcomes are outside the validated scope of this PoC.”

**“Is the model causal?”**

“No. The simulator has an explicit causal topology for controlled experiments, but feature contribution or attribution is not causal proof.”

**“What model is driving the warning probability?”**

“A calibrated scikit-learn `HistGradientBoostingClassifier` trained on
synthetic simulator traces. It is not XGBoost. It predicts near-future
utility/MRR risk from observations available at decision time. It does not
directly command the tool; it only feeds the supervisory hold/resume decision
path.”

**“How good is the model?”**

“For the current dashboard artifact, row-level discrimination is strong:
PR-AUC is about 0.925 with precision around 0.888 and recall around 0.748.
Event-level detection is not yet production-grade: event recall is 10 out of 22
on the held-out synthetic event set, and false alarms are still high. So we use
it as a demonstration of the decision loop, not a final production warning
model.”

**“Where did the training data come from?”**

“From simulator-generated traces in this repository. No real fab telemetry was
used for this dashboard warning artifact.”

**“Can this connect to a tool?”**

“Not as demonstrated here. The next engineering step would be a real-fab data contract, offline shadow mode, independent safety review, and staged integration.”

**“Why is the dashboard local?”**

“The local server keeps this proof of concept read-only and reproducible. A production deployment would need authentication, audit logging, data governance, and an operational monitoring design.”

## Close (1 minute)

**Say:** “The takeaway is a transparent experiment loop: named disturbance, observable process response, warning signal, and bounded supervisory decision. The next investment decision is whether to validate the warning and control contracts against customer data in shadow mode. This POC intentionally stops before making a real-fab or yield claim.”

## Recovery notes

- Use the replay artifact for the recording. Use live runs only as backup.
- If a stream is interrupted, click **Run scenario** again; the server is stateless.
- If no artifact appears, confirm the server was started from the repository environment and that `tests/regression/*.json` exists.
- If a customer asks for root-cause detail during the compact replay, switch to the dedicated attribution validation report rather than inferring it from the scenario name.
