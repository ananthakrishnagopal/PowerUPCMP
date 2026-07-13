# Decision record: R2 PHM semantics and evaluation policy

Date: 2026-07-11  
Status: ACCEPTED FOR R2 IMPLEMENTATION  
Scope: T-PHASE12-REMEDIATION, subgate R2  
Depends on: validated R1 schema/interface/configuration

## Scientific boundary

The PHM process columns are proprietary scaled signals. The original challenge
does not declare the MRR target unit. R2 therefore produces native-unit public
features and labels only. It does not infer Pa, m³/s, rad/s, seconds of
consumable life, SI Preston parameters, or an electrical/UPW causal link.

R2 supports offline average-MRR virtual metrology preparation. It does not
create streaming early-warning features, simulator calibration, or a control
result.

## Source-order and continuity policy

The loader adds `SOURCE_ROW_INDEX` before concatenation so original row order
is auditable. Calculations group by `TRACE_ID`, `WAFER_ID`, and `STAGE` and
retain stable source order. For consecutive source timestamps,

\[
\Delta t_i=t_i-t_{i-1}.
\]

R2 records zero, negative, non-finite, and long increments separately. A
continuity segment starts at the first row, after a negative increment, or
after \(\Delta t_i>10\,s\). The 10 s threshold is a preregistered engineering
threshold: ordinary positive increments have 99th percentile approximately
3.333 s and 99.5th percentile approximately 5.333 s in training, while the
99.9th percentile is 17 s. Threshold sensitivity is reported later if model
results depend materially on it.

Zero increments are duplicate-time evidence and receive no interval duration;
they are not silently deleted. Negative increments are invalid ordering
evidence and start a new segment.

## Time-weighting convention

For a row inside one continuity segment, define valid adjacent increments as
strictly positive and no greater than 10 s. Its centered support weight is

\[
w_i=\frac{1}{2}\Delta t_{i-1}^{valid}
   +\frac{1}{2}\Delta t_{i+1}^{valid}.
\]

The time-weighted mean and population variance of signal \(x\) over a process
mode are

\[
\bar x_w=\frac{\sum_i w_i x_i}{\sum_i w_i},
\qquad
s_w^2=\max\left(0,
\frac{\sum_i w_i x_i^2}{\sum_i w_i}-\bar x_w^2
\right).
\]

Rows with zero support do not change the mean or extrema. A mode with no
positive support produces null features plus explicit row/duration/coverage
features; it is not imputed in R2.

Absolute `TIMESTAMP` is metadata for continuity and stress splitting, never a
default predictor feature.

## Input-only process-mode proxies

The challenge-specific literature describes preparation, main polishing,
ending, and post-CMP cleaning. The public signals do not supply authoritative
row-level phase labels, so R2 uses deterministic **proxy** labels and does not
claim they are measured physical modes.

A row is an `ACTIVE_POLISH_PROXY` candidate only when all are true:

1. at least one pressure signal is strictly nonzero;
2. at least one of slurry lines A/B/C is strictly nonzero;
3. wafer or stage rotation is strictly nonzero; and
4. head rotation is strictly nonzero.

The exact-zero boundary is used because the source contains explicit off
values; no MRR label or holdout statistic sets it. Within each continuity
segment:

- rows before the first active candidate are `PREPARE_PROXY`;
- active candidates are `ACTIVE_POLISH_PROXY`;
- inactive holes between active candidates are
  `TRANSITION_WITHIN_POLISH_PROXY`;
- rows after the last candidate are `ENDING_OR_CLEANING_PROXY`; and
- a segment with no active candidate is `UNRESOLVED_PROXY`.

`DRESSING_WATER_STATUS` remains an input signal and duty feature. It is not used
alone to declare dressing or cleaning because it is frequently nonzero during
active signal combinations. No row is silently removed based on its proxy.

## Phase-aware offline feature contract

Features are grouped by `WAFER_ID` and `STAGE`. They contain:

- row count, source-trace count, continuity-segment count;
- group start/end timestamps as split metadata only;
- duplicate, negative, and long-gap counts;
- per-proxy row fraction, positive-support duration, and duration fraction;
- time-weighted mean/standard deviation/minimum/maximum for each scaled process
  signal within each proxy; and
- stable machine/regime/chamber metadata and ambiguity flags.

The target is joined to completed group features, not replicated across raw
rows during feature calculation. This reduces accidental label access in
segmentation and aggregation. Complete-trace offline features are explicitly
for virtual metrology and may not enter the future streaming warning API.

## Training-label anomaly treatments

The four preregistered training keys are:

| Wafer | Stage | Original | Hypothetical / 60 |
|---|---|---:|---:|
| 2058207580 | A | 4326.15405 | 72.102568 |
| 1834206730 | A | 4202.11245 | 70.035207 |
| 1834206944 | A | 4182.41655 | 69.706942 |
| 1834206972 | A | 4129.49400 | 68.824900 |

R2 implements three named, immutable policies:

```text
ORIGINAL
EXCLUDE_FOUR_PREREGISTERED
HYPOTHETICAL_DIVIDE_FOUR_BY_60
```

`ORIGINAL` is the primary policy. The other two are sensitivity analyses. The
implementation verifies all four keys and original values before exclusion or
transformation, preserves the raw label column, and emits an audit. No policy
may be selected using test or validation results.

## Split hierarchy and leakage policy

1. Official training is the only fitting/tuning source.
2. Official test is an offline source role.
3. Official validation is the final public source role.
4. A feature-only R2.1 audit found that those source partitions reuse wafer
   IDs across opposite stages. The accepted precedence correction retains all
   training wafers, only test wafers absent from training, and only validation
   wafers absent from both original training and original test. The retained
   row counts are 1,981/311/275 and are mutually wafer-disjoint. Full 424-row
   test/validation partitions are collision-contaminated diagnostics only. See
   `orchestration/decisions/r2_official_wafer_precedence.md`.
5. Inner development splits group whole `WAFER_ID` values.
6. A chronological training stress split orders whole wafers by group start
   timestamp; absolute time is not a model feature.
7. A physical `MACHINE_ID` holdout is infeasible because the loaded dataset has
   only machine ID 2. This fact is reported, not hidden.
8. `MACHINE_DATA` is not a substitute grouping variable: 1,979 of 1,981
   training wafer/stage groups and every test/validation group contain multiple
   values. It may be summarized as an input signal but cannot define a
   leave-one-regime-out group split.
9. Stage A, stage B, combined-stage, and chronological/trace stress results are
   reported separately; no machine-generalization result is claimed.

Every fitted imputer, scaler, selector, phase threshold beyond the fixed R2
rules, physics coefficient, and model hyperparameter must record its fitting
wafer groups. A fit-scope audit must show those groups are a subset of training
and disjoint from calibration/test groups.

## Acceptance evidence

- Unit tests for source-order preservation, gap segmentation, centered time
  weights, proxy labels, unresolved groups, and absence of target use.
- Unit tests for each label policy and exact-key/value guards.
- Split tests for official source-role construction, cross-partition wafer
  collisions, precedence-retained isolation, wafer grouping, chronological
  grouping, fit-scope audit, and infeasible physical-machine holdout.
- Real-data semantic report with timing, modes, labels, regimes, and policies.
- Real-data feature generation with one row per official wafer/stage key and no
  absolute timestamp predictor.
- Existing loader integrity, empty-trace, and label-join evidence retained.
- Focused and complete `devkki` tests pass.

## Sources

- PHM Society 2016 CMP challenge:
  https://phmsociety.org/conference/annual-conference-of-the-phm-society/annual-conference-of-the-prognostics-and-health-management-society-2016/phm-data-challenge-4/
- Li et al., challenge-specific process phases and run types:
  https://doi.org/10.2991/iceea-18.2018.26
- Rahman et al., native PHM MRR modelling and physics-informed comparisons:
  https://doi.org/10.1109/ICPHM61352.2024.10627679
