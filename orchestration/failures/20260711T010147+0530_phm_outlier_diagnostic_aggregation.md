# Failure report

## Task

Read-only scientific audit of the four extreme PHM training removal-rate
labels and their associated process trajectories while rethinking T-WP08.

## Failed command

    conda run -n devkki python -c "... groupby(...).agg(['mean','min','max']) ..."

The complete command and traceback are preserved in the active-session tool
log.

## Error

Pandas raised:

    TypeError: dtype 'string' does not support operation 'mean'

The aggregation selected identifier columns such as MACHINE_ID, MACHINE_DATA,
and CHAMBER after the loader had correctly normalized them to string dtype.

## Files changed before failure

None during this scientific review. All repository inspection, PHM range
summaries, bundled-document reading, and literature checks were read-only.
This failure report is the only file added after the failure as required by
project policy.

## Read-only diagnosis

- The PHM loader intentionally stores grouping identifiers as strings.
- The diagnostic requested numeric mean, minimum, and maximum operations for a
  mixed identifier/process column selection.
- Pandas correctly rejected a mean for the string extension dtype.
- The PHM dataset and loader were not mutated.
- Earlier successful read-only evidence remains valid: four stage-A removal
  labels are approximately 4,129 to 4,326 while the next largest label is
  approximately 163; their interpretation has not yet been established.
- This failure does not change the already identified modelling concerns:
  hidden dataset scaling, unspecified target unit, stage-average labels,
  same-direction kinematics, missing electrical/UPW measurements, and absent
  dynamic CMP conditioning states.

## Likely causes

1. The diagnostic column list mixed categorical identifiers with numeric
   process variables.
2. The aggregation applied the same numeric functions to every selected
   column instead of using first/nunique for identifiers and numeric summaries
   for process variables.

## Recovery options

1. Rerun a corrected read-only diagnostic that summarizes identifier columns
   with first/nunique and numeric process columns with mean/min/max.
2. Skip detailed inspection of the four extreme labels and record them as an
   unresolved mixture/outlier risk before virtual-metrology modelling.
3. Coerce identifiers to numeric solely for the diagnostic. This is not
   recommended because numeric arithmetic on opaque IDs is meaningless.

## Recommended option

Option 1. It preserves identifier semantics and can determine whether the four
labels correspond to a distinct machine, chamber, stage recipe, trace length,
or apparent isolated label anomaly.

## User decision required

Authorize the corrected read-only outlier diagnostic and continuation of the
T-WP08 scientific redesign review. No CMP implementation should begin until
the redesign is reviewed.
