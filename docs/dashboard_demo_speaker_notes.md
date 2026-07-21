# PowerUPCMP Customer Demo Speaker Notes

## Demo objective

Show how a controlled CMP disturbance moves through the simulator, becomes a warning signal, and can result in a supervisory safe hold. Keep the distinction between **demonstrated in simulation** and **validated in a fab** explicit throughout the conversation.

Suggested duration: 15 minutes, followed by 10 minutes of technical questions.

## Before the meeting

1. Install the project in the documented Python environment.
2. Start the dashboard with `conda run -n devkki python src/semifab_poc/dashboard/server.py`.
3. Open `http://localhost:8080` and confirm the page says `Ready for demo`.
4. Keep the repository documentation available for provenance questions. The primary references are `docs/assumptions_and_limitations.md`, `docs/architecture.md`, and the WP12/WP13/WP15/WP16 validation reports.
5. Use the default seed and parameters for the first run so the result is repeatable.

## 1. Frame the problem (1 minute)

**Say:** “This is a technical proof of concept for supervisory control of a CMP process when utility conditions degrade. The dashboard is a local, read-only view of a deterministic simulator. It is designed to make the causal chain and the control decision inspectable.”

Point to the yellow banner. Explain that the values are synthetic and that the spatial output is only a modeled proxy. Do not describe the result as yield protection or production control.

## 2. Establish the baseline (1 minute)

Select **Normal operation** and keep **Predictive shield** selected. Run the scenario.

**Say:** “We start with a healthy reference. The point is to establish expected process modes and avoid interpreting every model signal as an event.”

Use the charts to identify the normal mode progression. The expected result is no safe hold and a low warning probability. This is a useful negative control: the supervisor should not intervene without a simulated disturbance.

## 3. Inject a pump disturbance (3 minutes)

Select **Pump trip during polish** and run with the default seed. Keep the dashboard visible while the stream progresses. Other useful branches are **Grid voltage sag**, **UPW valve restriction**, **Pressure sensor bias**, and **Short grid interruption**; use them when the audience wants to see electrical, hydraulic, sensor-quality, or recovery behavior.

**Say:** “The event is introduced into the utility side. We are watching three separate things: the physical process response, the warning probability, and the supervisory operating mode. Keeping those separate is important because a high warning is not itself an action.”

Walk through the screens in this order:

- **Process health and warning:** MRR is the simulator outcome; the red curve is the model warning signal on the right axis.
- **Physical process response:** this is simulator ground truth, not a sensor measurement from a real tool.
- **Operating mode:** the mode transition is the visible control effect. A `HOLD` state is the action outcome in this demonstration.
- **Event timeline:** the timeline makes the sequence clear: initialization, warning, hold if observed, and completion.

When the decision banner changes, say: “The demonstrated value is the traceability from event to a synthetic warning proxy to a bounded supervisory response. It is not a claim that this response is ready to command a production tool.”

## 4. Compare against no action (2 minutes)

Change **Controller mode** to **No-action comparator** and rerun the same scenario with the same seed. Point out that the seed, duration, and disturbance are held constant.

**Say:** “This is the paired comparator. A credible efficacy study needs the same disturbance and initial conditions, with only the controller policy changed.”

Compare the operating-mode chart and the process curve. Avoid claiming saved wafers or a measured yield improvement from this view. The current dashboard is a trace viewer; paired aggregate metrics belong in the evaluation reports.

## 5. Replay evidence (2 minutes)

Open **Load an artifact**, select `demo-predictive-intervention`, and use **Replay artifact**.

**Say:** “The replay path shows that the dashboard is not dependent on a live calculation for presentation. It can replay a versioned local artifact, which is useful for review, audit, and a repeatable customer conversation.”

Point to **Evidence and limits**. Explain that the selected compact demo artifact contains truth rows and predictions, but does not contain attribution or safety-decision arrays. The UI says that explicitly rather than filling the gap with inferred values.

## 6. Technical deep dive (4 minutes)

Use these prompts if the audience wants more detail:

- **Architecture:** configuration and scenario create the disturbance; the utility and CMP subsystems produce the simulated trace; online features and predictions feed supervisory control; the safety contract bounds the action path.
- **Timing:** the dashboard samples the simulation for readability. It is not a latency benchmark or a promise of real-time execution.
- **Model boundary:** the warning is an early-warning signal for the frozen simulator target. Root-cause attribution and uncertainty must be discussed with their dedicated validation artifacts and limitations.
- **Data boundary:** public PHM data and simulator results are separate evidence planes. A public-data offline metric should not be presented as proof of online control.
- **Safety:** a demo `HOLD` is an observed simulator mode. It is not an independent production safety certification.

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

- If the live run is too slow, use the replay artifact.
- If a stream is interrupted, click **Run scenario** again; the server is stateless.
- If no artifact appears, confirm the server was started from the repository environment and that `tests/regression/*.json` exists.
- If a customer asks for root-cause detail during the compact replay, switch to the dedicated attribution validation report rather than inferring it from the scenario name.
