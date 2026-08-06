# Broker Reports Branch Lifecycle v1

Status: `CURRENT`

Date: 2026-08-06

The default workflow is:

```text
one authorized GOAL
-> one named working branch
-> terminal verification
-> reviewed merge
-> closure receipt
-> local and remote branch deletion
```

Before deleting a branch, record its purpose, head SHA, ahead/behind state,
unique commits, PR or immutable commit reference, integration status and one of
the DOC34 classifications. Unverified unique product work blocks deletion.

A long-lived branch is permitted only when its owner/GOAL, completion
criterion, expiry review date and merge-or-delete rule are written down. An
experiment ends by integrating the smallest proven product slice or by closing
and deleting the branch while retaining a PR/commit reference. A directory
named `archive` is not a substitute for Git history.

Force-push, shared-history rewrite and deletion of an ambiguously owned branch
require separate authorization. Temporary worktrees are removed after their
route completes; the canonical checkout returns to clean `main`.
