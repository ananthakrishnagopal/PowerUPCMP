# Failure report

## Task

Correct a formatting explanation in the new Phase 3 CMP and utility-coupling
decision record before activating T-WP08.

## Failed command

An apply_patch request targeting
orchestration/decisions/20260711_phase_3_cmp_and_utility_model.md.

## Error

The patch tool rejected the request before making a change:

    apply_patch verification failed: Failed to find expected lines

The failed patch expected visible plus-sign characters that were diff markers
in the original patch transport and therefore were not written into the saved
file.

## Files changed before failure

- orchestration/decisions/20260711_phase_3_cmp_and_utility_model.md was added
  before the failed corrective patch.

No source code, test, configuration, data, or previously existing
orchestration file was changed after the failure.

## Read-only diagnosis

- The saved decision record already renders the intended multiplication
  relation without plus signs:
  MRR equals K times contact pressure times relative velocity times the
  modifiers.
- The record contains one now-stale explanatory sentence referring to rendered
  plus signs. It is documentation-only and does not alter the selected model,
  units, parameter values, or task state.
- The failure is a patch-context mismatch caused by diff-marker handling in
  the transport layer, not a scientific, numerical, interface, dependency, or
  repository-permission failure.

## Likely causes

1. Lines prefixed with plus signs in the first patch were interpreted as patch
   additions, so the plus signs were not persisted in the document.
2. The corrective patch searched for those non-persisted characters.

## Recovery options

1. Apply a narrowly targeted documentation-only patch that removes the stale
   sentence, then continue the planned Phase 3 work.
2. Leave the sentence for a later documentation cleanup and continue only
   after recording that it is non-semantic.
3. Recreate the decision record from scratch. This is unnecessary and risks
   overwriting a correct scientific decision record.

## Recommended option

Option 1. Make the one-line documentation correction, re-read the decision
record, then resume T-WP08. No model, parameter, interface, or claim changes
are involved.

## User decision required

Authorize the documentation-only corrective patch and resumption of the
bounded Phase 3 CMP physics task.
