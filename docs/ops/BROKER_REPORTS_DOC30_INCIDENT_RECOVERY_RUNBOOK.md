# Broker Reports DOC30 Incident Recovery Runbook

Status: `INCIDENT_ACCOUNTED_BACKFILL_STOPPED_ON_OOM`

Date: 2026-08-05

## Scope and authority

The public infra document points to an ignored local target note containing
the existing key-based SSH route. Keep the endpoint, user, key location,
fingerprints, host paths and config values out of Git and safe evidence.

The exact DOC29 workload is `broker-reports-doc29-prepare`. Recovery authority
is limited to that job and the Broker namespace. Do not stop the Compose
project, OpenWebUI, STT, reverse proxy, databases or volumes without separate
evidence.

## Current incident state

Two bounded probes timed out during SSH banner exchange. SSH recovered at
`2026-08-05T16:29:50Z`. Kernel evidence proved the DOC29 monolithic Python
process was OOM-killed at `2026-08-05T16:04:48Z` and its container auto-removed.
OpenWebUI recovered healthy with zero restarts. Both Broker and STT SQLite
stores passed integrity and foreign-key checks; DOC29 wrote zero canonical
versions or payload files. The recovery action is `RETAIN`.

## Console recovery order

1. Open the VPS/provider console and record a UTC baseline.
2. Collect uptime/load, pressure, memory/swap, disk/inodes, OOM events, Docker
   responsiveness, container state and bounded resource usage.
3. If and only if the exact DOC29 job is still running and harms control-plane
   or product health, stop that container gracefully with a bounded timeout;
   force only that container if graceful stop cannot complete.
4. Confirm SSH banner, Docker and OpenWebUI responsiveness in a bounded quiet
   observation window.
5. From read-only connections or copied snapshots, run SQLite integrity and
   schema checks for Broker and STT. Stop on any non-`ok` result.
6. Account for every DOC29 version, active pointer, component, manifest,
   referenced payload and chunk; classify temporary/orphan state exactly.
7. Choose `RETAIN`, `CLEAN_PARTIAL` or `RESTORE_BROKER_NAMESPACE`. Before any
   restore, snapshot current Broker metadata, payload namespace and job logs.

Never run the old monolithic job, `compose down -v`, volume deletion, Docker
prune, global stack restart, whole-volume restore or STT mutation.

## Resume gate

SSH, product health, Docker, both SQLite stores, capacity and DOC29 accounting
were confirmed. Two resource-bounded canaries passed. The cohort reached 8
active versions before an XLSX container was OOM-killed at the frozen 1 GiB
limit. That terminal condition stopped DOC30 without retry or continuation;
the failed document left no partial persisted state. Resume requires a new
explicit resource-policy decision, not reuse of the old monolithic job.
