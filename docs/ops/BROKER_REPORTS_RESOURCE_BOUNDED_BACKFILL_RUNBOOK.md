# Broker Reports Resource-Bounded Backfill Runbook

Status: `CURRENT_LIMITS_FROZEN_PARTIAL_STOPPED_ON_OOM`

Date: 2026-08-05

## Processing contract

The only allowed order is:

```text
one document -> validate -> publish immutable version -> optional activate
-> per-document safe receipt -> durable checkpoint -> next document
```

Concurrency is 1 and batch size is 1. A 16-document indivisible job is
forbidden. Resume identifies completion by source and canonical root hashes,
verifies the existing version through `CanonicalReaderFactory`, and skips it.
It must not create a second active version, retry provider work, fall back to
legacy output or hide a repeated attempt.

## Frozen DOC30 limits

The target run used CPU 0.5, RAM/swap 1 GiB, pids 128, read I/O 20 MiB/s,
write I/O 10 MiB/s, 600 seconds per document, 10,800 seconds overall, 10 MiB
logs and 16 MiB maximum input. Limits were applied to each job container and
verified through its cgroup before any write. Concurrency and batch size were
both 1.

The target run raised the free-space floor to 4 GiB and retained the 10%
critical ratio, 128 MiB logical artifact ceiling and 4096-component ceiling.
Before every document, measure the persistent filesystem and stop before
reservation when a guard fails.

The two canaries passed. The cohort then completed 8 documents; document 7,
an XLSX, reached the 1 GiB memory cgroup and exited 137 with `OOMKilled=true`.
It produced no persisted partial state. Do not retry it, raise the limit or
continue the remaining seven documents without a new explicit policy.

## Canary and cohort gates

1. Run one small document and publish its terminal receipt.
2. Reconfirm SSH, OpenWebUI, Docker, swap/OOM, disk and partial-state health.
3. Run one large PDF and repeat the same checks.
4. Continue the frozen 16-document cohort only after both canaries pass.
5. Stop on missing receipt, partial state, health loss, OOM, critical capacity
   or an unapplied resource limit.

After each document, record only hashed identity, format, source/root hashes,
version, component count, layout type, elapsed time, bounded resource
observations, validation, activation and receipt. Keep source bytes, names,
paths, payloads and tenant values outside Git.

## Durability sequence

After 16/16 success, verify all active versions, restart only the relevant
service, verify again, recreate only its container against the same volume and
verify again. Then pause canonical mutations, take a SQLite Online Backup plus
the referenced immutable payload set and hash manifest, and restore to an
isolated namespace through `CanonicalReaderFactory`. Never use `down -v`.
