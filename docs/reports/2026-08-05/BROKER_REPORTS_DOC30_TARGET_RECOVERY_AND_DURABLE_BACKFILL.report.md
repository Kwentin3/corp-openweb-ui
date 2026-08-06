# Broker Reports DOC30 Target Recovery and Durable Backfill

Date: 2026-08-05

Status: `PARTIALLY_COMPLETED`

## Outcome

The documented key-based SSH route recovered at `2026-08-05T16:29:50Z`.
Read-only incident accounting proved that the DOC29 monolithic Python process
was killed by the host OOM killer at `2026-08-05T16:04:48Z` after consuming
about 1.81 GB anonymous RSS. The old job had auto-removed and was not retried.

Both persistent SQLite stores passed a fresh bounded `integrity_check` with
zero foreign-key violations. STT retained its pre-incident 103 artifact
records. DOC29 wrote zero canonical versions and zero payload files, and the
Broker logical row set matched the pre-change snapshot. The recovery decision
was therefore `RETAIN`; no cleanup or restore was performed.

DOC30 introduced a closed-world, factory-routed, one-document entrypoint with
durable checkpoints and per-document receipts. Two canaries passed. The
frozen cohort then reached 8 active canonical versions before document 7, an
XLSX, was killed by its 1 GiB container memory cgroup (`exit 137`,
`OOMKilled=true`). The mandatory OOM stop condition ended the run without a
retry. Seven documents were never attempted. The failed document left zero
artifact records, canonical versions or payload files.

```text
DOC30_PROGRAM = PARTIALLY_COMPLETED
TARGET_HOST_RECOVERY = CONFIRMED
DOC29_INCIDENT_STATE = ACCOUNTED
BROKER_STORAGE_INTEGRITY = CONFIRMED
STT_STORAGE_INTEGRITY = CONFIRMED
RECOVERY_ACTION = RETAIN
RESOURCE_BOUNDED_BACKFILL = PARTIAL
TARGET_DURABILITY = NOT_CONFIRMED
TARGET_BACKUP_RESTORE = BLOCKED
RESEARCH_CONSUMER = NOT_STARTED
WAVE2_SHADOW = NOT_STARTED
WAVE2_CUTOVER = NOT_PERFORMED
PRIMARY_PRODUCT_CUTOVER = NOT_PERFORMED
LEGACY_HANDOFF = RETAINED
GATE3 = NOT_STARTED
```

## Required accounting

1. SSH route: the ignored local target note supplied the existing authority;
   credentials were not requested. Three bounded probes are accounted: two
   banner timeouts and one successful recovery.
2. Host state: Docker and SSH are active; OpenWebUI is healthy with restart
   count 0. The persistent filesystem had about 32.97 GB free, 35% used, and
   6% inode use. The host has about 4.11 GB RAM and no swap.
3. DOC29 job: the one monolithic attempt was OOM-killed and auto-removed. It
   produced no terminal receipt and was never retried.
4. Broker/STT integrity: both final bounded read-only checks returned `ok` and
   zero foreign-key violations. STT retained 103 artifact records.
5. DOC29 writes: zero canonical versions, active pointers, components and
   payload files. All incident accounting slots are classified.
6. Recovery decision: `RETAIN`; no Broker cleanup, Broker restore, STT change,
   volume deletion or unrelated OpenWebUI mutation occurred.
7. Cause: confirmed host OOM from the DOC29 monolithic Python process. The
   later DOC30 XLSX failure was isolated to its container memory cgroup and did
   not make OpenWebUI unhealthy.
8. Limits: concurrency 1, one document per container, CPU 0.5, RAM/swap
   1 GiB, pids 128, read I/O 20 MiB/s, write I/O 10 MiB/s, 600 seconds per
   document, 10,800 seconds overall, 10 MiB logs, 16 MiB input ceiling, 4 GiB
   free-space floor, 10% critical ratio and 4096 components. Cgroup values were
   verified from inside the container before writes.
9. Canaries: 2/2 passed. The small canary completed in 12.022077 seconds with
   52,473,856 bytes peak memory; the large PDF completed in 23.873388 seconds
   with 196,775,936 bytes peak memory. A repeated completed canary was skipped
   idempotently without another version.
10. Frozen cohort: 9 attempted, 8 completed, 1 failed, 7 never attempted and
    0 unaccounted. The completed subset has 8 active pointers, 8 matching roots,
    16 verified components, zero missing chunks and fail-closed cross-tenant
    access. The failed XLSX has zero partial persisted state.
11. Restart/recreation: not performed because complete backfill is a
    prerequisite. Durability is not confirmed.
12. Backup/restore: the pre-change Broker backup remains historical evidence.
    No new complete target backup or isolated restore was attempted after the
    OOM stop. Backup/restore is blocked, not failed.
13. Research consumer: not started; no consumer flag changed and no silent
    fallback was introduced.
14. Wave 2 shadow: not started; no consumer migrated and no product side
    effect or provider call ran.
15. Tests: 9 focused DOC30 implementation/evidence tests pass. The full suite
    was not started because the run stopped before durability and consumer
    prerequisites; this is not recorded as a test timeout.
16. A separate Wave 2 cutover GOAL is not authorized. It remains blocked
    behind an explicit policy decision for the XLSX memory failure, complete
    backfill, restart/recreation durability, backup/restore, research consumer
    and Wave 2 shadow evidence.

## Stop and handoff

Do not retry document 7, raise its memory limit, or continue documents 8-16
under DOC30. A new explicit resource-policy decision must choose how the XLSX
case is handled. Until then, retain the 8 completed active versions and the
legacy handoff, and keep all consumer and product cutovers off.

No historical DOC29 receipt or hash was rewritten.
