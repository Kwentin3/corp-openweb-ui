# Broker Reports Canonical Capacity Runbook

Status: `CURRENT`

Date: 2026-08-05

## Policy

`CanonicalArtifactStoreFactory` checks capacity before reserving a version.
The defaults are:

- hard minimum free space: 1 GiB;
- warning: free ratio at or below 20%;
- critical: free ratio at or below 10%;
- maximum logical canonical artifact: 128 MiB;
- maximum physical components per version: 4096.

At the hard floor the canonical shadow write fails explicitly with
`canonical_capacity_insufficient`. Legacy processing remains authoritative and
must not silently claim that canonical persistence succeeded.

## Operator check

Measure the filesystem that owns `openwebui_data`, not the container writable
layer. Report total/free bytes and ratio without host paths. For Canonical and
STT separately report metadata, payload, chunks, temporary bytes, average,
p95, largest document, version amplification and evidence amplification.

Historical cohort measurements are planning evidence, not a target SLO. Freeze
new CPU, memory, I/O, time, log, input and free-space limits before an
authorized run; do not derive them silently from an earlier proof.

## Recovery and cleanup

If a job degrades application or control-plane health, stop only that exact job
through the host console. Do not delete volumes, run `compose down -v`, rotate
active versions or retry the workload. After health returns, collect SQLite
integrity, free capacity, job state and canonical pointer/component counts.

OOM, missing terminal receipt, unapplied limits, capacity failure or degraded
application/control-plane health is an explicit stop. Do not retry, raise a
limit or continue the cohort without a new policy decision. Retain the
one-document rules in
[BROKER_REPORTS_RESOURCE_BOUNDED_BACKFILL_RUNBOOK.md](BROKER_REPORTS_RESOURCE_BOUNDED_BACKFILL_RUNBOOK.md).
