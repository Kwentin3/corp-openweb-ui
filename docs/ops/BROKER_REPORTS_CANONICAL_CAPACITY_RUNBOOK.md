# Broker Reports Canonical Capacity Runbook

Status: `CURRENT_TARGET_PARTIAL_STOPPED_ON_OOM`

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

The isolated DOC29 cohort produced 105,494,726 logical canonical bytes for 16
documents, p95/largest 47,494,041 bytes, 172 components, version amplification
1.0 and evidence amplification 18.528778. These are planning observations, not
a target SLO.

## Recovery and cleanup

If a job degrades application or control-plane health, stop only that exact job
through the host console. Do not delete volumes, run `compose down -v`, rotate
active versions or retry the workload. After health returns, collect SQLite
integrity, free capacity, job state and canonical pointer/component counts.

DOC30 recovery measured about 32.97 GB free on the persistent filesystem with
35% space and 6% inodes used. The per-document contour raised the job floor to
4 GiB free while retaining the 10% critical ratio, 128 MiB logical artifact
ceiling and 4096-component ceiling.

The frozen workload limits were CPU 0.5, RAM/swap 1 GiB, pids 128, read I/O
20 MiB/s, write I/O 10 MiB/s, 600 seconds per document, 10,800 seconds overall,
10 MiB logs and 16 MiB input. After 8 successful versions, one XLSX reached
the memory cgroup limit and was OOM-killed. That is an explicit stop condition;
no retry or continuation is authorized by DOC30. Any new policy must retain
the one-document rules in
[BROKER_REPORTS_RESOURCE_BOUNDED_BACKFILL_RUNBOOK.md](BROKER_REPORTS_RESOURCE_BOUNDED_BACKFILL_RUNBOOK.md).
