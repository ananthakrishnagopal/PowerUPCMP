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
3. Open `http://localhost:8080` and confirm the page says `Validated demo artifact ready`.
4. In **Load an artifact**, confirm `stakeholder-demo-stable-polish-fault` is selected.
5. Use **Replay validated demo** as the recording path. Live scenarios are backup.
6. Keep the repository documentation available for provenance questions. The primary references are `docs/stakeholder_demo_methodology.md`, `docs/assumptions_and_limitations.md`, `docs/architecture.md`, and the WP12/WP13/WP15/WP16 validation reports.

## 1. Frame the problem (1 minute)

**Say:** “This is a technical proof of concept for supervisory control of a CMP process when utility conditions degrade. The dashboard is a local, read-only view of a deterministic simulator. It is designed to make the causal chain and the control decision inspectable.”

Point to the yellow banner. Explain that the values are synthetic and that the spatial output is only a modeled proxy. Do not describe the result as yield protection or production control.

## 2. Establish the baseline (1 minute)

Use the canonical replay first. If time allows, select **Normal operation** and
keep **Predictive shield** selected, then run the scenario as a no-false-hold
baseline.

**Say:** “We start with a healthy reference. The point is to establish expected process modes and avoid interpreting every model signal as an event.”

Use the charts to identify the normal mode progression. The expected result is no safe hold and a low warning probability. This is a useful negative control: the supervisor should not intervene without a simulated disturbance.

## 3. Replay the stakeholder pump-trip trace (3 minutes)

Click **Replay validated demo**. Keep the dashboard visible while the stream
progresses. The trace is a curated synthetic replay named
`stakeholder-demo-stable-polish-fault.json`. It is the preferred recording
artifact because the pump-trip fault is injected after MRR has stabilized in
POLISH mode, and it contains the scenario, warning, action, safety, and summary
fields needed for a clean walkthrough.

**Say:** “The event is introduced into the utility side. We are watching three separate things: the physical process response, the warning probability, and the supervisory operating mode. Keeping those separate is important because a high warning is not itself an action.”

Walk through the screens in this order:

- **Process health and warning:** MRR is the simulator outcome; start by pointing out the stable MRR plateau before the amber event band. The red curve is the model warning signal on the right axis.
- **Physical process response:** this is simulator ground truth, not a sensor measurement from a real tool.
- **Operating mode:** the mode transition is the visible control effect. A `HOLD` state is the action outcome in this demonstration.
- **Event timeline:** the timeline makes the sequence clear: utility fault, warning threshold crossing, supervisor proposal, safety approval, hold, controlled resume, and completion.

When the decision banner changes, say: “The demonstrated value is the traceability from event to a synthetic warning proxy to a bounded supervisory response. It is not a claim that this response is ready to command a production tool.”

## 4. Compare against no action (2 minutes)

If time allows, change **Protection mode** to **Legacy System (Unprotected)**
and run the same pump-trip scenario. Point out that the seed, duration, and
disturbance are held constant. Treat this as a qualitative backup comparison,
not as the formal evidence path for the recording.

**Say:** “This is the paired comparator. A credible efficacy study needs the same disturbance and initial conditions, with only the controller policy changed.”

Compare the operating-mode chart and the process curve. Avoid claiming saved wafers or a measured yield improvement from this view. The current dashboard is a trace viewer; paired aggregate metrics belong in the evaluation reports.

## 5. Replay evidence and limitations (2 minutes)

Point to **Load an artifact**, the selected
`stakeholder-demo-stable-polish-fault` trace, and **Evidence & limits**.

**Say:** “The replay path shows that the dashboard is not dependent on a live calculation for presentation. It can replay a versioned local artifact, which is useful for review, audit, and a repeatable customer conversation.”

Explain that the selected compact demo artifact contains truth rows,
predictions, proposed actions, safety decisions, and summary KPIs. It is marked
as a synthetic communication artifact rather than a new validation result.

## 6. Technical deep dive (4 minutes)

Use these prompts if the audience wants more detail:

- **Architecture:** configuration and scenario create the disturbance; the utility and CMP subsystems produce the simulated trace; online features and predictions feed supervisory control; the safety contract bounds the action path.
- **Timing:** the dashboard samples the simulation for readability. It is not a latency benchmark or a promise of real-time execution.
- **Model boundary:** the warning is an early-warning signal for the frozen simulator target. Root-cause attribution and uncertainty must be discussed with their dedicated validation artifacts and limitations.
- **Data boundary:** public PHM data and simulator results are separate evidence planes. A public-data offline metric should not be presented as proof of online control.
- **Safety:** a demo `HOLD` is an observed simulator mode approved by the local safety-filter path for this synthetic replay. It is not an independent production safety certification.

## Questions to handle carefully

**“How many wafers were saved?”**

“This dashboard does not support that claim. Wafer yield and physical defect outcomes are outside the validated scope of this PoC.”

**“Is the model causal?”**

“No. The simulator has an explicit causal topology for controlled experiments, but feature contribution or attribution is not causal proof.”

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
