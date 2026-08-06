# Broker Reports Resource-Bounded Backfill Runbook

Status: `CURRENT`

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

## Frozen run limits

Before execution, record CPU, memory/swap, pids, read/write I/O, per-document
and overall timeout, log size, input size, minimum free bytes, critical free
ratio, maximum artifact bytes and component count. Verify the effective cgroup
and persistent filesystem before any write. Limits apply to each one-document
job and cannot change during the run.

OOM, timeout, missing receipt, partial state, capacity failure or unapplied
limit is terminal. Do not retry, increase a limit or continue the cohort
without a new explicit policy decision.

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

After the authorized cohort succeeds, verify all active versions, restart only the relevant
service, verify again, recreate only its container against the same volume and
verify again. Then pause canonical mutations, take a SQLite Online Backup plus
the referenced immutable payload set and hash manifest, and restore to an
isolated namespace through `CanonicalReaderFactory`. Never use `down -v`.
