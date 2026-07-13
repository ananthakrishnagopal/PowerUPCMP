# Failure report

## Task

Commit the frozen WP09 scientific protocol before model implementation or
official holdout target access.

## Failed command

```text
git add configs/models/virtual_metrology.yaml orchestration/decisions/wp09_virtual_metrology.md orchestration/task_manifest.yaml orchestration/project_status.md && git diff --cached --check && git commit -m "docs: preregister WP09 virtual metrology"
```

## Error

```text
fatal: Unable to create '/home/akki/cmp_modelling/.git/index.lock': Read-only file system
```

## Files changed before failure

- `configs/models/virtual_metrology.yaml`
- `orchestration/decisions/wp09_virtual_metrology.md`
- `orchestration/task_manifest.yaml`
- `orchestration/project_status.md`

These files passed the untracked/tracked whitespace preflight and governance
validation before the Git operation. This failure report is the only file
created after the failed command. No model code was written and no official
test or validation MRR value was accessed.

## Read-only diagnosis

The failed `git add` stopped the chained command before the staged check or
commit. `.git/index.lock` is absent, so a stale lock is not responsible. Unix
metadata shows `.git` and `.git/index` owned and normally writable by user
`akki`, but the current managed filesystem profile exposes `.git` read-only to
the sandbox. The four preregistration changes remain unstaged and intact.

## Likely causes

The Git mutation was executed without the elevated filesystem permission
needed by this session's managed profile. Earlier Git checkpoints were made
under an approval path that allowed `.git` writes.

## Recovery options

1. Run `git add`, `git diff --cached --check`, and `git commit` as separate
   commands with the required escalated Git permission, then verify the
   worktree and commit.
2. Leave the preregistration uncommitted and do not implement WP09 because its
   one-shot holdout rule requires a committed decision/configuration.
3. Remove the one-shot commitment requirement, which would weaken the frozen
   scientific protocol and is not recommended.

## Recommended option

Option 1. It restores the intended auditable checkpoint without changing any
scientific content.

## User decision required

Authorize an escalated Git staging and commit retry before WP09 implementation.
