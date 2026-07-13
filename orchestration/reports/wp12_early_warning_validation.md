# WP12 synthetic early-warning validation

Date: 2026-07-12<br>
Task: T-WP12<br>
Final experiment revision: `1.4-no-test-selection`<br>
Evidence plane: `SYNTHETIC_SIMULATOR`<br>
Disposition: VALIDATED within the narrow claim boundary below

## Executive determination

WP12 answers a limited version of the detection part of the research question:
under the configured synthetic dressing-water-support topology, arrived utility
and plant observations can warn of a future persistent active-polish MRR
trajectory excursion relative to a paired event-disabled simulator reference.
Both frozen learned models pass the preregistered primary synthetic-ensemble
gate. Logistic regression has the largest descriptive held-out PR-AUC, but no
TEST-derived model choice is used in any downstream calculation.

The primary logistic result is PR-AUC 0.9904 at prevalence 0.04348, row
precision 0.975, row recall 0.9286, event recall 3/3, median warning lead time
2.71 s, one false-alarm episode in 193.2 eligible simulated seconds, and
empirical split-conformal coverage 0.9296. The corresponding gradient-boosted
result is PR-AUC 0.9130, row precision 0.9130, row recall 1.0, event recall 3/3,
the same median lead time and false-alarm episode count, and coverage 0.8773.
The constant prevalence baseline detects 0/3 events.

These apparently strong primary results depend on only three independent
event-bearing TEST runs and deliberately severe full-DRESS synthetic service-
loss endpoints. Robustness is not broad. Under high synthetic sensor noise,
logistic precision falls to 0.1019, specificity to 0.0657, uncertainty coverage
to 0.0959, and false alarms rise to 821.9 per eligible simulated hour. Both
learned models false-alarm badly when severe upstream disturbances are replayed
under a no-CMP-connection topology even though no MRR event occurs. The result
therefore supports claim C-003 only for the named primary ensemble. It does not
support real-fab, defect, yield, equipment, controller-efficacy, safety, or
production claims.

## Evidence and implementation

Primary artifacts:

- [frozen configuration](../../configs/models/early_warning.yaml);
- [target and evaluation freeze](../decisions/wp12_early_warning_target.md);
- [independent conformal correction](../decisions/wp12_conformal_separation.md);
- [observation-robustness completion](../decisions/wp12_observation_robustness_completion.md);
- [secondary model-selection correction](../decisions/wp12_secondary_model_selection_correction.md);
- [implementation](../../src/semifab_poc/models/early_warning.py);
- [open-loop chain runner](../../src/semifab_poc/simulation/chain.py);
- [validation driver](../../scripts/validate_wp12_early_warning.py);
- [machine-readable validation report](../../reports/early_warning/wp12_validation.json);
- [dataset manifest](../../reports/early_warning/wp12_dataset_manifest.json);
- [eligible feature/label rows](../../reports/early_warning/wp12_dataset.csv);
- [held-out predictions](../../reports/early_warning/wp12_predictions.csv);
- [model comparison figure](../../reports/early_warning/figures/wp12_model_comparison.png); and
- [held-out warning timeline](../../reports/early_warning/figures/wp12_warning_timeline.png).

The chain runner advances the frozen electrical, UPS, drive, pump, UPW,
utility-to-CMP coupling, CMP, and sensor components in causal plant order. It is
an open-loop WP12 evidence runner, not the WP17 supervisory-control runtime.
No controller action is proposed or applied in this work package.

## Controlled revision history

### Revision 1.0: target feasibility failure

The first frozen experiment stopped before fitting because TRAIN contained no
positive target row. No calibration or TEST performance was inspected. A
read-only limiting-case audit found that the ±5% target became reachable only
near complete loss of DRESS service: the full-interruption and full-pump-trip
mean active-polish MRR ratios were approximately 0.94589 and 0.94578. The
authorized revision-1.1 amendment added a deterministic 0.00--5.99 s endpoint
to the maximum configured severity of interruption, pump-trip,
valve-restriction, and tool-demand families in each primary split. The target,
models, seeds, physics, and gate did not change.

### Revision 1.1: first complete run and audit findings

The first complete run demonstrated warning separation but reused the same
CALIBRATION rows to fit the sigmoid map and estimate conformal scores. A
post-run audit also found undefined PR-AUC values represented as zero on
negative-only sets. The probability result was retained as an audit snapshot,
but its uncertainty result was superseded. Details are preserved in the
[revision-1.1 audit](wp12_revision_1_1_method_audit.md).

### Revision 1.2: independent conformal calibration

A new 18-run `CONFORMAL_CALIBRATION` split with seed start 62000 was frozen
before regeneration. TRAIN fits the base model; CALIBRATION fits the sigmoid
map; CONFORMAL_CALIBRATION supplies nonconformity scores; TEST remains held out.
The base/sigmoid probability payload reproduced exactly, proving that this
correction changed uncertainty sets rather than warning probabilities.

### Revision 1.3: robustness class support and reporting domains

The original noise/delay/dropout subsets selected only upper-median scenarios
and therefore contained no events. Revision 1.3 froze two positions per family:
the upper median and the maximum endpoint. This produces 12 scenarios and three
events per corruption case. Censor counts became split-specific, and bootstrap
resamples with one class began contributing to metrics that remain defined.

### Revision 1.4: no TEST-driven secondary model selection

Earlier scripts used the learned model with maximum TEST PR-AUC for sensitivity
and corruption analyses. Revision 1.4 removed that dependency: all three model
families receive every secondary analysis. The report's descriptive winner is
explicitly marked `used_for_downstream_selection: false`. Recall, precision,
and specificity now become `null` when their mathematical denominator is zero,
and explicit confusion counts are recorded.

## Target mathematics

Let $R_k$ be the disturbed true simulated instantaneous average MRR and let
$R_k^{ref}$ be the event-disabled paired reference at the same simulation
step. The point-violation indicator is

\[
v_k = \mathbf{1}\left[m_k=\mathrm{POLISH}\right]
      \mathbf{1}\left[R_k^{ref}>\epsilon_R\right]
      \mathbf{1}\left[
      R_k < 0.95R_k^{ref}\;\lor\;R_k>1.05R_k^{ref}
      \right],
\]

where $m_k$ is the simulated CMP mode and
$\epsilon_R=10^{-12}\,\mathrm{m/s}$. HOLD, DRESS, PREPARE, RECOVER, IDLE,
and COMPLETE cannot create an excursion merely because their MRR is zero.

For simulator step $\Delta t=0.01\,\mathrm{s}$ and persistence
$\tau_p=0.25\,\mathrm{s}$, the required discrete interval count is

\[
n_p=\left\lceil\frac{\tau_p}{\Delta t}\right\rceil=25.
\]

An episode is accepted only if 25 consecutive active-polish intervals violate
the band. After that persistence is established, the stored episode onset is
the first violating interval, not the later confirmation interval. This
retrospective-onset convention makes the warning task predict the beginning of
a subsequently persistent departure. A mode break or in-band interval resets
the persistence counter.

At eligible decision time $t_d$, with frozen horizon $H=3.0\,\mathrm{s}$,
the offline label is

\[
y(t_d)=\mathbf{1}\left[t_d<t_e\le t_d+H\right],
\]

where $t_e$ is the first accepted episode onset. The label is generated
from future simulator truth offline and is never an online feature.

Decision cadence is 0.10 s. A decision row is excluded rather than converted
to a negative when:

1. the complete future horizon is unavailable;
2. the future horizon lacks 25 contiguous active-polish intervals; or
3. an accepted event has already begun at or before the decision.

The machine-readable reasons are `INCOMPLETE_FUTURE_HORIZON`,
`NO_ACTIVE_POLISH_OPPORTUNITY`, and `POST_EXCURSION_ONSET`.

## Causal observation and feature boundary

Only records satisfying

\[
t_{arrival}\le t_d,\qquad k_{source}\le k_d
\]

may enter the feature vector. Source, reported, and arrival timestamps remain
separate. The 65 frozen features use eight observed signals:

- grid voltage;
- UPS output voltage;
- UPS battery energy;
- motor angular speed;
- pump volumetric flow;
- UPW supply pressure;
- UPW tool flow; and
- UPW temperature.

For normalized arrived values $z_j$, each channel contributes latest value,
observation age, 0.5 s mean, minimum, least-squares slope, missing fraction, and
history minimum. UPS output, pressure, and tool flow also contribute a causal
history deficit

\[
D_j(t_d)=\int_{0}^{t_d}\max(0,0.95-z_j(t))\,dt,
\]

implemented by trapezoidal integration over arrived source samples. Known
DRESS/PREPARE/POLISH schedule indicators, normalized time to scheduled polish,
battery-capacity ratio, and UPS-load ratio are permitted static configuration.
They are not future measurements. `cmp.mrr`, latent pad activity, coupling
availability, event family/magnitude, simulator cause, and all future truth are
forbidden. Median imputation and scaling are fit on TRAIN only.

The online phase indicator is the known synthetic recipe schedule in this
open-loop experiment. Its use does not establish that a real tool's phase state
would be observed perfectly after a hold or altered schedule.

## Scenario and split accounting

All primary runs last 16 s after the existing 3 s plant warm-up: DRESS spans
0--6 s, PREPARE spans 6--7 s, and POLISH spans 7--16 s. Primary families are
normal, healthy sag, grid interruption, pump trip, valve restriction, and tool
demand spike. Whole run IDs never cross roles.

| Role | Whole runs | Eligible rows | Positive rows | Purpose |
|---|---:|---:|---:|---|
| TRAIN | 36 | 2,988 | 84 | Base-model fit |
| CALIBRATION | 18 | 1,404 | 84 | Sigmoid probability calibration |
| CONFORMAL_CALIBRATION | 18 | 1,404 | 84 | Independent conformal scores |
| TEST | 24 | 1,932 | 84 | Primary held-out evaluation |
| UNSEEN_COMPOUND | 6 | 528 | 0 | Separate compound-shift diagnostic |
| STRUCTURAL_NULL | 6 | 528 | 0 | No-CMP-connection diagnostic |

The 84 positive TEST rows arise from three event-bearing runs with 28 eligible
positive decisions each, not 84 independent events. TEST censor counts are 720
incomplete horizons, 1,008 no-active-polish opportunities, and 180 post-onset
decisions. Complete per-split and per-run accounting is in the dataset manifest.

The severe anchors repeat the same endpoint construction across split roles
with distinct run and sensor seeds. This gives independent corruptions but
limited physical diversity. It is a synthetic stress design, not a sampled fab
fault distribution.

## Frozen predictors and calibration

The prevalence baseline predicts the TRAIN prevalence

\[
\hat p(x)=\frac{1}{n_T}\sum_{i\in T}y_i=0.02811245.
\]

Logistic regression uses TRAIN-only median imputation, standardization,
balanced class weights, $C=1$, and the frozen seed. Histogram gradient
boosting uses 200 iterations, learning rate 0.05, at most 15 leaves, minimum 20
samples per leaf, L2 regularization 0.1, balanced training weights, and the same
seed. No TEST result tunes these settings.

For base probability $p_b$, the one-dimensional sigmoid calibrator fits

\[
\tilde p=\sigma\left(a\,\operatorname{logit}
  (\operatorname{clip}(p_b,10^{-6},1-10^{-6}))+b\right)
\]

on CALIBRATION only. The alarm threshold is $\tilde p\ge0.5$.

For independent conformal row $i$, the binary nonconformity score is

\[
s_i=\begin{cases}
1-\tilde p_i,&y_i=1,\\
\tilde p_i,&y_i=0.
\end{cases}
\]

With $n_q$ conformal rows and $\alpha=0.10$, the exact finite-sample
rank is

\[
k=\min\left(n_q,\left\lceil(n_q+1)(1-\alpha)\right\rceil\right),
\qquad \hat q=s_{(k)}.
\]

The prediction set is

\[
\Gamma(x)=\{0:\tilde p(x)\le\hat q\}
\cup\{1:1-\tilde p(x)\le\hat q\}.
\]

The final $\hat q$ values are 0.05982562 for prevalence, 0.000613325 for
logistic regression, and 0.000709242 for gradient boosting. Empty and
two-class sets are permitted and reported. Because time rows within a run are
dependent and the fixed severity grids are not iid draws, coverage is an
empirical row-level simulator result, not a formal run-wise or real-world
guarantee.

## Metrics and accounting

PR-AUC is undefined and therefore `null` when a set has only one target class.
Precision, recall, and specificity are similarly `null` when their respective
denominators are zero. Confusion counts accompany the rates.

An alarm episode begins only on a false-to-true threshold crossing. It is linked
to an event when the onset lies in $0<t_e-t_a\le H$; other threshold-crossing
episodes are false alarms. The reported hourly rate is

\[
r_{FA}=\frac{N_{FA}}
{N_{eligible}\,\Delta t_d/3600},
\qquad \Delta t_d=0.10\,\mathrm{s}.
\]

Thus one primary false-alarm episode over 1,932 eligible rows corresponds to
18.6335 per eligible simulated hour. It is not an empirical real-fab alarm
rate. Warning lead time uses the earliest linked alarm within the 3 s positive
window. Reported inference timing is amortized vectorized offline prediction,
not streaming controller latency or a production-response benchmark.

## Primary held-out results

| Metric | Prevalence | Logistic | Gradient boosted |
|---|---:|---:|---:|
| Rows / positive rows | 1,932 / 84 | 1,932 / 84 | 1,932 / 84 |
| PR-AUC | 0.04348 | **0.99040** | 0.91304 |
| Precision | undefined | **0.97500** | 0.91304 |
| Row recall | 0.00000 | 0.92857 | **1.00000** |
| Specificity | 1.00000 | **0.99892** | 0.99567 |
| Brier score | 0.04186 | **0.00321** | 0.00678 |
| Event recall | 0/3 | **3/3** | **3/3** |
| Missed-event rate | 1.000 | **0.000** | **0.000** |
| Median warning lead | undefined | **2.71 s** | **2.71 s** |
| False-alarm episodes | 0 | 1 | 1 |
| False alarms / eligible simulated hour | 0.00 | 18.63 | 18.63 |
| Conformal coverage | 0.95652 | **0.92961** | 0.87733 |
| Empty-set fraction | 0.00000 | 0.07039 | 0.12267 |

Both learned models pass all four preregistered gates:

1. PR-AUC exceeds TEST prevalence by at least 0.05;
2. event recall is at least 0.80;
3. median lead time is at least 0.50 s; and
4. empirical conformal coverage is at least 0.85.

Passing means “useful on this configured synthetic primary ensemble.” The gate
has no false-alarm acceptance threshold, and its event-recall component is based
on only three events.

## Grouped-bootstrap uncertainty

One thousand whole-run bootstrap repetitions were drawn with replacement.
Metrics use only repetitions in which they are defined; Brier score, coverage,
and false-alarm rate use all 1,000. Forty-three repetitions contain no positive
event run, so logistic PR-AUC, recall, event recall, and lead time have 957 valid
repetitions.

For logistic regression, the 2.5/50/97.5 percentiles are:

| Metric | 2.5% | Median | 97.5% | Valid repetitions |
|---|---:|---:|---:|---:|
| PR-AUC | 0.93270 | 0.99678 | 1.00000 | 957 |
| Row recall | 0.78571 | 0.92857 | 1.00000 | 957 |
| Brier score | 0.000023 | 0.002981 | 0.008868 | 1,000 |
| Conformal coverage | 0.86902 | 0.93034 | 0.97418 | 1,000 |
| Event recall | 1.000 | 1.000 | 1.000 | 957 |
| Median lead time | 2.11 s | 2.71 s | 2.71 s | 957 |
| False alarms / eligible hour | 0.00 | 18.07 | 59.60 | 1,000 |

These intervals reflect resampling of the 24 configured TEST runs. They do not
create additional event mechanisms and should not be interpreted as narrow
population confidence intervals for a fab.

## Observation-corruption robustness

Each corruption set contains 12 scenarios, 876 eligible rows, 84 positive rows,
and three events. Learned-model results are:

| Corruption | Model | PR-AUC | Precision | Specificity | Event recall | False alarms / eligible hour | Coverage |
|---|---|---:|---:|---:|---:|---:|---:|
| High delay | Logistic | 0.9933 | 0.6269 | 0.9369 | 3/3 | 369.9 | 0.7546 |
| High delay | Gradient boosted | 0.9087 | 0.9121 | 0.9899 | 3/3 | 82.2 | 0.7386 |
| High dropout | Logistic | 0.9906 | 0.6222 | 0.9356 | 3/3 | 452.1 | 0.8048 |
| High dropout | Gradient boosted | 0.9355 | 0.9032 | 0.9886 | 3/3 | 41.1 | 0.7763 |
| High noise | Logistic | 0.6002 | 0.1019 | 0.0657 | 3/3 | 821.9 | 0.0959 |
| High noise | Gradient boosted | 0.5283 | 0.5283 | 0.9053 | 3/3 | 41.1 | 0.7671 |

Event recall survives these named corruptions, but false alarms and uncertainty
coverage often do not. Logistic regression is especially brittle to the frozen
high-noise case. Gradient boosting has much better specificity and false-alarm
behavior there, yet its PR-AUC is only 0.5283 and coverage remains below the
nominal target. No robustness model is selected after observing these results.

## Structural and unseen-family diagnostics

The structural-null set applies severe upstream disturbances under an explicit
`NO_CONNECTION` topology. It has zero true MRR events. Logistic regression
raises 30 false-alarm episodes, predicts 350/528 rows positive, has specificity
0.3371, and covers only 0.0417 of labels with its conformal set. Gradient
boosting raises nine episodes, predicts 377/528 rows positive, has specificity
0.2860, and has zero coverage. The constant baseline does not alarm but also
cannot detect primary events.

The unseen compound set also contains no primary event. Logistic regression
raises ten episodes (681.8 per eligible simulated hour), specificity 0.8409,
and coverage 0.4811. Gradient boosting raises five episodes (340.9 per hour),
specificity 0.8447, and coverage 0.4564. PR-AUC and event recall are undefined
on both negative-only diagnostics.

These results show that the models often recognize severe upstream utility
patterns rather than proving the downstream MRR connection. The current
feature vector does not encode a general applicability certificate for unseen
topologies. WP15/WP16 must reject or hold when the model's declared topology,
sensor validity, or uncertainty conditions are not satisfied; the predictor
must not be applied as a topology-independent alarm.

## Target-definition sensitivity

The frozen models are not retrained for these descriptive target changes. The
same probabilities are rescored against alternate labels/eligibility rules.
Selected results are:

| Sensitivity | Positive rows | Logistic PR-AUC / recall / lead | GBT PR-AUC / recall / lead |
|---|---:|---|---|
| ±3% band | 112 | 0.9712 / 0.7143 / 2.41 s | 0.9574 / 0.8214 / 2.71 s |
| ±7.5% band | 0 | undefined / undefined / undefined | undefined / undefined / undefined |
| 1 s horizon | 24 | 1.0000 / 1.0000 / 0.71 s | 0.7742 / 1.0000 / 0.71 s |
| 5 s horizon | 144 | 0.9445 / 0.7361 / 3.61 s | 0.7137 / 0.6181 / 2.91 s |
| 0.10 s persistence | 90 | 0.9884 / 0.9111 / 2.91 s | 0.9043 / 0.9778 / 2.91 s |
| 0.50 s persistence | 75 | 0.9964 / 0.9600 / 2.41 s | 0.9036 / 1.0000 / 2.41 s |

The ±7.5% band has no held-out event and therefore cannot support an early-
warning ranking claim. Horizon and persistence changes materially alter row
support and warning interpretation even when event recall remains 3/3.

## Acceptance and reproducibility

The final validation driver completed in 428.1 s in conda environment `devkki`.
The complete repository suite then passed 170/170 tests in 48.01 s with warnings
treated as errors. After the WP12 status, running-paper, manuscript, and failure
records were finalized, governance found 15 YAML files, zero duplicate keys, 29
acyclic tasks, 25 valid assumptions, 99 Markdown files, 97 valid local links,
and zero missing local links.

Frozen or deterministic hashes:

| Artifact | SHA-256 |
|---|---|
| Runtime configuration | `b2b07edbaad458f6f66cf26ce88ffc5deef656a33701a7cccd8da94104d7383f` |
| WP12 configuration | `b53730011cb4f3c26173c727ba9fc562e9677a24a422f558a1c3330ab2df1e05` |
| Reference trace | `bf2dadd9d593fadb2d74d41f7c39840085d4bf4e247e5bfae729b583b39edbff` |
| Dataset CSV | `fabe232a503320c59e9a201b62731adc8bf4c6b1f5fd5ee57bb30091a30b43fa` |
| Dataset manifest | `5fce862c1992d05ab5c2043659034a95532a68fac89e0fd3878add74f751e76a` |
| Probability payload excluding timing/sets | `5a4fb7011fd6688718455c9692689937caa679ea29c884cdca099835a9830ede` |
| Prevalence model | `80a92460ad4213c67973929a32489b39adee689b7554dd13a608224833d9dfb1` |
| Logistic model | `c95b460397487760a33f64b04bca876b9e51c0108438730f85b0b298c26e7078` |
| Gradient-boosted model | `1ec579d00f70bba81feab0a024cce74f4ba5b41cfc43ae3bc735682ded199d0a` |
| Model-comparison figure | `76863b51a445311299307e95e5a2587aa91ccf7e07286034610e6f360b53b16f` |
| Timeline figure | `077177e0435e1e237e681c562ccde2e07f9057bfc21711b82056a4c7362dcfcb` |

The complete predictions CSV and JSON report include measured offline latency
and elapsed time, so their whole-file hashes are platform/run dependent. The
probability-payload hash deliberately excludes latency and conformal sets and
reproduced unchanged across methodological/reporting revisions.

Reproduction commands:

```text
conda run -n devkki python -m pytest -q -W error
env MPLCONFIGDIR=/tmp/semifab-poc-matplotlib \
  conda run -n devkki python scripts/validate_wp12_early_warning.py
conda run -n devkki python scripts/validate_governance.py
```

## Claim disposition

Claim C-003 may move to `SUPPORTED_SIMULATION` with this exact limitation:

> The frozen logistic and gradient-boosted models predict the preregistered
> ±5% paired-reference, 0.25 s persistent active-polish MRR trajectory event
> within a 3 s horizon on the named held-out synthetic dressing-support
> ensemble. Evidence comprises three event-bearing TEST runs and does not
> generalize to structural topology shift, severe observation corruption,
> public PHM data, a real fab, defects, yield, equipment safety, controller
> efficacy, or production control.

No WP12 evidence supports C-004, C-005, C-006, or C-007. WP12 predicts a
simulated process excursion; it neither attributes the cause nor intervenes.

## Open limitations and downstream requirements

1. Only three independent primary event runs are available; row counts must not
   be mistaken for event replication.
2. Positive events depend on extreme full-DRESS synthetic stress anchors near
   the target's feasibility boundary.
3. Split roles repeat a small severity grid and are not iid samples from a fab.
4. The paired reference and target depend on simulator structure and synthetic
   utility-to-CMP coupling assumptions.
5. Structural-null and unseen-compound false alarms are high; model
   applicability must be topology- and envelope-gated.
6. High synthetic noise severely degrades logistic discrimination, specificity,
   calibration, and uncertainty coverage.
7. Independent conformal calibration removes row reuse, but within-run temporal
   dependence prevents a formal run-level coverage guarantee.
8. Empty prediction sets occur on 7.04% of logistic and 12.27% of
   gradient-boosted primary rows; WP16 must treat them as invalid/high
   uncertainty rather than as approval.
9. Static schedule, battery capacity, and load are known simulator
   configuration. Real deployment would require audited availability and
   consistency of those fields.
10. Offline vectorized latency is not WP17 end-to-end controller latency.
11. The open-loop runner is not controller evidence. WP15/WP16 must freeze
    objective, action bounds, slew, applicability, uncertainty, and hold/resume
    behavior before any intervention comparison.
12. Public PHM virtual metrology remains a separate pending WP09 evidence plane.

WP12 is complete only within these restrictions.
