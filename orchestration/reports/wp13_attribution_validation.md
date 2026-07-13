# WP13 synthetic root-cause attribution validation

Date: 2026-07-13
Task: T-WP13
Experiment revision: `1.0-preregistered`
Evidence plane: synthetic simulator only
Outcome: interpretation gate passed; bounded diagnostic-attribution claim supported

## Executive result

The frozen hybrid estimator classified the initiating cause correctly on
57/66 held-out whole runs, for accuracy and macro recall of 0.8636. It retained
all six normal runs as `UNKNOWN`, assigned no incorrect known cause, achieved
1.000 selective accuracy on the known-cause predictions it did issue, and
covered 85% of the 60 known-cause runs. All nine errors were conservative
abstentions to `UNKNOWN`, not substitutions of one known cause for another.

The simpler frozen rule-only comparator scored higher on the same TEST set:
0.9242 accuracy and macro recall. This finding is retained as evidence that the
learned component did not improve the synthetic rule model. The declared
hybrid remains the primary method because switching methods after TEST access
would violate the preregistered no-TEST-selection policy.

These results support only conditional diagnostic classification inside the
declared simulator, topology, severity grid, and sensor model. They are not
experimental causal proof, real-fab fault diagnosis, controller efficacy, or
equipment-safety evidence.

## Scientific question and scope

WP13 asks:

> Given a positive, valid early-warning decision and only observations that
> have arrived by the decision time, can the estimator distinguish the
> initiating simulated disturbance while abstaining under weak, invalid,
> conflicting, out-of-distribution, normal, or compound evidence?

The primary experiment intentionally supplies a neutral valid-positive
singleton warning token. This isolates cause separability from WP12 warning
recall. The result is therefore conditional diagnostic capability, not an
end-to-end warning-and-diagnosis rate. An absent, negative, invalid, or
non-singleton warning is required to produce `UNKNOWN` in runtime use.

## Frozen cause semantics

The ten primary initiating classes are grid-voltage sag, grid-voltage swell,
grid interruption, grid-frequency deviation, pump trip, valve restriction,
tool-demand spike, thermal excursion, pressure-sensor fault, and flow-sensor
fault. `UNKNOWN` is a required eleventh output.

UPS transfer and VFD derating are retained as propagation evidence only. They
are not initiating TEST labels and cannot replace the declared upstream cause.
Compound simulator truth is retained as an ordered tuple offline, but the
single-label online estimator must abstain when two initiating chains are
simultaneously strong.

## Causal online boundary

At decision time \(t_d\), the admissible observation set is

\[
\mathcal O(t_d)=\{o_i:t_{\mathrm{arrival},i}\le t_d\}.
\]

The online input contains the opaque run identifier, decision step and time,
the contemporaneous warning record, and arrived observation records. It does
not contain simulator initiating labels, scenario family or magnitude, latent
state, future samples, future MRR, paired-reference MRR, offline excursion
labels, `event_active`, pad state, coupling state, or CMP MRR.

Fourteen observed channels cover grid and UPS voltage/frequency, UPS battery
energy, VFD available output and trip state, motor speed, pump flow, UPW supply
pressure and tool flow, valve position, tool demand, and temperature. Sensor
faults are injected at the observation boundary; they do not alter the latent
hydraulic state. Simulator-generated fault-quality flags are not features.

## Feature and residual construction

For observed signal \(s\), fixed engineering reference \(\mu_s\), and positive
scale \(\sigma_s\), the engineering-normalized sample is

\[
z_s=(x_s-\mu_s)/\sigma_s.
\]

From a 0.75 s arrived-observation window the estimator computes latest value,
short-window mean, least-squares slope, and missing fraction. Learned-model
median imputation and standardization are fit on TRAIN only. No complete-trace
statistic is available online.

The pressure-consistency proxy is

\[
\widehat P=P_r+(P_0-P_r)(Q_p/Q_{p,0})^2,
\qquad
r_P=(P_{\mathrm{obs}}-\widehat P)/P_0,
\]

and the flow-consistency proxy is

\[
\widehat Q_t=\min\!\left[D,
v\,\max(P_{\mathrm{obs}}-P_r,0)/R_t\right],
\qquad
r_Q=(Q_{\mathrm{obs}}-\widehat Q_t)/Q_{t,0}.
\]

These are engineering diagnostic residuals motivated by the existing pump
affinity and UPW valve equations. They do not replace the dynamic hydraulic
model and do not prove a physical sensor fault.

## Rule, learned, and hybrid estimators

Every initiating cause receives a bounded rule severity. The common ramp is

\[
\rho(d;a,b)=\operatorname{clip}\!\left(\frac{d-a}{b-a},0,1\right),
\qquad 0\le a<b.
\]

Direct signatures include voltage deficit or excess, near-zero voltage,
frequency deviation, drive/motor loss, valve closure, demand increase,
temperature deviation, and the two consistency residuals. A temperature-scaled
softmax maps these scores to the initiating classes plus `UNKNOWN`. UPS-transfer
and VFD-derating probabilities are displayed separately with at most 0.10 total
mass and do not enter initiating-class gates.

The statistical comparator is balanced multinomial logistic regression with
TRAIN-only median imputation and standardization, \(C=1\), `lbfgs`, at most
2,000 iterations, and seed 20260713. A scalar probability temperature is chosen
only on disjoint CALIBRATION runs by minimum multiclass log loss over the frozen
grid \(\{0.50,0.75,1.00,1.25,1.50,2.00\}\).

For class \(c\), transformed feature \(\widetilde x_j\), and coefficient
\(\beta_{cj}\), the reported local classifier contribution is

\[
a_{cj}=\beta_{cj}\widetilde x_j.
\]

This explains a fitted logit only; it is not a causal effect.

The frozen primary hybrid geometrically pools learned and rule probabilities:

\[
s_c=0.5\log(p_{\mathrm{ML},c}+10^{-9})
+0.5\log(p_{\mathrm{rule},c}+10^{-9}),
\qquad
p_{\mathrm{hybrid}}=\operatorname{softmax}(s).
\]

The mandatory comparators are always-`UNKNOWN`, rule only, and logistic.

## Mandatory abstention policy

The final prediction is `UNKNOWN` when any frozen condition holds:

1. the warning is not positive;
2. warning uncertainty is invalid or its conformal set is not exactly `{1}`;
3. a critical observation is stale or aggregate missingness exceeds 0.35;
4. a standardized learned feature magnitude exceeds 8.0;
5. the largest initiating probability is below 0.55;
6. the top-two initiating margin is below 0.10;
7. confident learned and rule distributions have Jensen--Shannon divergence
   above 0.35; or
8. at least two distinct initiating rule scores are at least 0.70.

When a gate fires, `UNKNOWN` probability is raised to at least 0.80 before
renormalization. Every attribution record stores `causal_proof=false`.

## Dataset, splits, and evaluation unit

TRAIN contains 264 decision rows and CALIBRATION 132, generated without TEST,
compound, or robustness access. TEST contains 198 rows from 66 disjoint whole
runs: six runs for each of ten known causes and six normal `UNKNOWN` runs, with
three decision windows per run. The primary evaluation unit is the final
window of each whole run. Multiple windows never cross split roles.

The TEST dataset SHA-256 is
`395464f24f9e5b50230bdfe9a19d18333492f1489a470bdc83636f643fb24329`.
Grouped bootstrap accuracy resamples whole run IDs for 1,000 repetitions.

## Guarded holdout opening

The scientific policy, code, configuration, serialized models, calibration
report, tests, and target-blind manifest were committed before TEST access.
The first guarded invocation stopped before TEST because raw Python equality
treated JSON-loaded arrays as lists while deterministic replay returned the
same values as tuples. Their canonical JSON hashes already matched, and no
opening marker was written. After explicit user authorization, the guard was
changed only to compare canonical payload hashes; a regression test proves a
changed seed is still rejected. Scientific configuration and model artifacts
were not changed.

After the guard correction, 23 focused tests and all 211 repository tests
passed with warnings treated as errors. The one-shot runner then wrote the
persistent opening marker at Git commit
`ec7bc8b41afc9261f56673c92bf2744b15a9540c`, regenerated the TEST payload once,
and refused future silent reruns.

## Primary held-out results

| Method | Accuracy | Macro recall | Macro F1 | UNKNOWN recall | Known coverage | Selective accuracy | Top-2 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Always UNKNOWN | 0.0909 | 0.0909 | 0.0152 | 1.0000 | 0.0000 | undefined | 0.1818 |
| Rule only | 0.9242 | 0.9242 | 0.9303 | 1.0000 | 0.9167 | 1.0000 | 1.0000 |
| Logistic | 0.7121 | 0.7121 | 0.7138 | 0.8333 | 0.7167 | 0.9545 | 0.8182 |
| Hybrid, frozen primary | 0.8636 | 0.8636 | 0.8710 | 1.0000 | 0.8500 | 1.0000 | 1.0000 |

Hybrid grouped-bootstrap accuracy has mean 0.8620, 5th percentile 0.7879,
and 95th percentile 0.9242. Its normal false-attribution rate is zero. The
hybrid multiclass Brier score is 0.2243, log loss is 0.4257, and ten-bin
expected calibration error is 0.1589. These finite-grid synthetic calibration
statistics are descriptive; they do not establish deployment calibration.

## Hybrid class-conditional result

Every class has six held-out runs.

| Offline simulator initiating label | Recall | Precision when predicted | Misses to UNKNOWN |
|---|---:|---:|---:|
| Grid-voltage sag | 1.0000 | 1.0000 | 0 |
| Grid-voltage swell | 0.6667 | 1.0000 | 2 |
| Grid interruption | 1.0000 | 1.0000 | 0 |
| Grid-frequency deviation | 0.8333 | 1.0000 | 1 |
| Pump trip | 1.0000 | 1.0000 | 0 |
| Valve restriction | 1.0000 | 1.0000 | 0 |
| Tool-demand spike | 1.0000 | 1.0000 | 0 |
| Thermal excursion | 1.0000 | 1.0000 | 0 |
| Pressure-sensor fault | 0.3333 | 1.0000 | 4 |
| Flow-sensor fault | 0.6667 | 1.0000 | 2 |
| UNKNOWN/normal | 1.0000 | 0.4000 | 0 |

The low `UNKNOWN` precision is the expected cost of conservative abstention:
15 runs were labelled `UNKNOWN`, comprising six true normal runs and nine
known-cause abstentions. No error was a false known-cause substitution. Sensor
faults, especially pressure bias, are the weakest signatures because the
reduced-order consistency proxies provide limited independent redundancy.

The rule-only method correctly classifies 61/66 runs and exceeds the hybrid by
four runs. This is a valid held-out comparator result, not a basis for post-hoc
primary-model replacement. It motivates a future preregistered study of when
learned fusion adds value rather than an adjustment to WP13.

## Compound-event behavior

Six unseen runs combine grid interruption and tool-demand spike. The hybrid
abstains on 5/6, giving 0.8333 compound abstention against the frozen minimum
of 0.75. The pre-abstention top-two distribution contains both offline truth
labels on all six runs, for truth-set recall at two of 1.0000. Compound results
are reported separately and do not inflate single-cause accuracy.

## Robustness and availability

| Diagnostic set | Accuracy | UNKNOWN recall | Known coverage | Selective accuracy | Interpretation |
|---|---:|---:|---:|---:|---|
| Doubled noise | 0.8636 | 1.0000 | 0.8500 | 1.0000 | Primary aggregate accuracy retained |
| Parameter mismatch | 0.8636 | 1.0000 | 0.8500 | 1.0000 | Aggregate accuracy retained; class errors move |
| 0.20 s communication delay | 0.0909 | 1.0000 | 0.0000 | undefined | All runs abstain |
| 10% packet loss | 0.2273 | 1.0000 | 0.1500 | 1.0000 | Most known causes abstain |
| Pre-event/normal audit | 1.0000 | 1.0000 | not applicable | undefined | Zero false known causes |

Delay and dropout expose an availability failure, not unsafe over-attribution:
the stale/missing-data policy collapses toward `UNKNOWN`. WP16 must treat this
as an explicit invalid-sensor/applicability condition, and WP17/WP18 must report
diagnostic availability separately from correctness among issued diagnoses.

## Timing

On the local validation platform, hybrid inference time over held-out final
windows has mean 3.436 ms, median 3.423 ms, 95th percentile 3.746 ms, and
maximum 3.849 ms. The median earliest correct attribution delay among the 56
correctly diagnosed known-cause runs is 1.0 simulated second. These are local
software and synthetic-timeline measurements, not production latency or a
microsecond-response claim.

## Frozen interpretation gates

All preregistered gates pass:

- accuracy 0.8636 is at least 0.70;
- macro recall 0.8636 is at least 0.65;
- improvement over always-`UNKNOWN` is 0.7727, at least 0.40;
- `UNKNOWN` recall 1.0000 is at least 0.80;
- normal false attribution 0.0000 is at most 0.20;
- selective accuracy 1.0000 is at least 0.75;
- known-cause coverage 0.8500 is at least 0.60;
- compound abstention 0.8333 is at least 0.75; and
- the feature audit finds zero forbidden or future features.

Passing these gates supports the bounded simulator-label classification claim
in C-007. It does not turn residual agreement, rule chains, or coefficient
contributions into causal proof.

## Downstream requirements

WP15 and WP16 must not treat a predicted cause as action authorization.
Downstream supervisory logic must independently check warning validity,
topology and configuration identity, sensor freshness, missingness, prediction
uncertainty, action constraints, and restart criteria. An `UNKNOWN` result,
high delay, high dropout, rule/model conflict, OOD feature, or compound signal
must reach the safety filter as an applicability limitation. The final runtime
must keep simulator truth in post-decision evaluation joins only.

## Provenance and reproduction

Run from the repository root in conda environment `devkki`:

```text
MPLCONFIGDIR=/tmp/semifab-poc-matplotlib conda run -n devkki python scripts/validate_wp13_attribution.py --run-one-shot --authorize-holdout-open
```

The one-shot command is historical and is not expected to run again after the
persistent opening marker exists. Audit and model-loading paths remain
reproducible without reopening TEST.

| Artifact | SHA-256 |
|---|---|
| Target-blind preparation payload | `e8b47b67a37972addedd5dc230005979bcb3d20f3bea76aa1ec07a5d186d3ab9` |
| Holdout opening marker | `53139b8b65c1acc2307fa6bb7b7488e7921e14b191b5f3206e299de39b502a3d` |
| TEST dataset payload | `395464f24f9e5b50230bdfe9a19d18333492f1489a470bdc83636f643fb24329` |
| Validation JSON | `f075e513bb2c836ea2ca1b20c281f21929ab3ad7fa01f8eea4bf79d5a613fefc` |
| Deterministic validation payload | `b1f7080dc0d091caa003793ec7eed98a92dd3b9a509c33a7f77e86a5dae74f99` |
| Prediction CSV | `8108f514930f6f2bfaf77bab5597e35432d6dded3c7290bfa34a294820f494eb` |
| Hybrid confusion figure | `07db0b4d0feec7d33fafc8d8a60f4e2bd8abb6c57616e3f216649059572b57ad` |
| Hybrid recall figure | `add6b0cfc5df9e9b2e079295872ade18b6ff7f67adab649f2b97410f0ea11615` |

Machine-readable results are in `reports/attribution/wp13_validation.json` and
`reports/attribution/wp13_predictions.csv`. The frozen method is in
`orchestration/decisions/wp13_root_cause_attribution.md`; the pre-holdout audit
is in `orchestration/reports/wp13_preholdout_checkpoint.md`; and the guard
failure and authorized recovery are preserved in
`orchestration/failures/20260713T150031+0530_wp13_preholdout_replay_type.md`.

## Acceptance disposition

- All required initiating causes and `UNKNOWN` are supported: pass.
- Residual rules and coefficient-based feature contributions are recorded:
  pass.
- Simulator initiating labels are hidden from the online estimator: pass.
- Held-out confusion matrix, accuracy, class metrics, uncertainty, timing,
  compound behavior, and robustness are reported: pass.
- Feature attribution and rule evidence are not described as causal proof:
  pass.

T-WP13 is scientifically complete within the stated synthetic boundary.
