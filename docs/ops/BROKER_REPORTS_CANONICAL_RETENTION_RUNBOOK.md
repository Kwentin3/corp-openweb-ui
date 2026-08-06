# Broker Reports Canonical Retention Runbook

Status: `CURRENT_POLICY_VALIDATED_RUNTIME_ROTATION_BLOCKED`

Date: 2026-08-05

This runbook covers durable Broker Reports canonical artifacts only. It does
not authorize deletion, enable a retention worker, or replace customer/case
policy.

## Classes

The durable store must classify every object as one of:

- `SOURCE`;
- `ACTIVE_CANONICAL`;
- `SUPERSEDED_CANONICAL`;
- `EVIDENCE`;
- `RAW_PROVIDER`;
- `TEMPORARY`;
- `PROJECTION_CACHE`;
- `RESEARCH`.

## Fail-closed rules

- Never delete an active version or its reachable chunks.
- Never delete the current rollback target before a replacement rollback
  target is validated and retained.
- Apply tenant/case policy before TTL defaults.
- Treat metadata and payload deletion as one receipted operation; a partial
  result is a failure requiring reconciliation.
- Record only safe identifiers, counts, classes, hashes, timestamps, and
  disposition codes in Git evidence.
- No cleanup may run while the durable backend, active pointer, backup, restore,
  or metadata/payload consistency is unproved.

## Rotation receipt

Each approved run must report attempted, deleted, retained, blocked, orphaned,
and reconciled counts per class; pre/post manifest hashes; tenant/access scope;
and the worker/runtime identity. Zero unaccounted objects is required.

## DOC29 status

All `8/8` classes are contract-tested. Frozen defaults are: no TTL for source
and active canonical authority; 30 days for superseded canonical and evidence;
14 days for raw-provider and research material; 1 day for temporary material;
7 days for projection cache. The hard capacity floor is 1 GiB free, with 20%
warning and 10% critical ratios; insufficient capacity rejects only the
canonical shadow write explicitly.

No target deletion or rotation was run. Active versions deleted = 0, rollback
targets deleted = 0, orphan chunks observed in the isolated proof = 0. Runtime
rotation remains blocked until target host recovery, post-job accounting and
target restore proof. The cleanup owner remains an ArtifactStore-routed
canonical retention worker; cron or direct filesystem deletion is forbidden.
