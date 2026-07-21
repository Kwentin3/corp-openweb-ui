# Broker Reports Goal 4 — Workload Authority

Date: 2026-07-21

Implementation commit: `4cc5e83b85df76bcd15936df8ddca4ddecc7e376`

Branch: `codex/broker-reports-goal4-workload-authority-v1`

## Verdict

Goal 4 is accepted for delivery. Broker Reports now has one maintained, persisted, cross-process workload authority for admission, progress, provider budgets, cancellation, review waiting, retry, cleanup, and crash recovery. Gate 1 heavy concurrency is fixed at one, Gate 2 local concurrency is capped at two, and excess work remains in a persisted FIFO queue.

No customer corpus was opened, copied, or changed. No live OpenWebUI deployment or production data was mutated during this goal.

## Archaeology decision

Historical commit `a460c811` contained a useful bounded-admission scaffold, but it was intentionally not cherry-picked. Its state lived in process-local locks, deques, and dictionaries and was explicitly marked as an implementation-pending single-instance scaffold. It did not satisfy persisted authentication, cross-process coordination, provider budgets, crash recovery, or production routing.

The useful ideas—typed transitions, FIFO admission, cooperative cancellation, and bounded concurrency tests—were selectively adapted into the maintained SQLite authority.

## Maintained authority

The implementation is rooted at `broker_reports_gate1/workload_authority.py` and can only be constructed through `WorkloadAuthorityFactory`. It uses SQLite WAL plus `BEGIN IMMEDIATE` transactions to coordinate all Function instances sharing the configured authority database.

Persisted authenticated status requires an exact match of user, case, chat, and workspace-model context. The public state vocabulary is exactly:

`queued`, `source_intake`, `normalizing`, `building_document_memory`, `validating`, `preparing_gate2`, `awaiting_provider`, `awaiting_review`, `completed`, `failed`, `cancelled`.

The maintained routing covers the Gate 1 normalizer, Gate 2 source-fact and domain preparation, table/structural/hybrid/VLM provider calls, passport and clarification provider calls, review waiting, and generated OpenWebUI bundles. Lightweight deterministic work and private source intake remain distinct resource classes.

## Safety properties

- Gate 1 heavy admission is exactly one; configuration drift fails closed.
- Gate 2 local admission accepts one or two and rejects values above two.
- Local and provider queues are persisted FIFO queues, not process-local queues.
- Provider calls acquire separate persisted per-provider budgets.
- Admission has no fixed wall-clock timeout; worker leases detect crashes without declaring success.
- Cancellation is cooperative for running work and immediate for queued/review-waiting work.
- Terminal cancellation and failure remove only the job-owned private `brjob_*` temporary directory; the persisted audit trail remains.
- A crashed worker becomes `failed` with `worker_lease_expired`; it cannot become `completed`.
- Retry creates a new linked job and private temporary directory from a failed/cancelled job.
- A Gate 1 result awaiting review does not consume a local worker slot. Only an authenticated accepted review receipt can complete it.
- Gate 2 rejects DCP input unless its owning Gate 1 workload is persisted as `completed`, preventing publication after a crash between artifact persistence and workload completion.
- No local OCR worker pool was introduced. The only background thread is a bounded lease heartbeat for the active job.

## Acceptance evidence

| Criterion | Result | Evidence |
| --- | --- | --- |
| `WORKLOAD_AUTHORITY SINGLE_AND_MAINTAINED` | PASS | Factory-only authority, contract-bound shared SQLite store, production pipe routing, anti-drift tests |
| `GATE1_CONCURRENCY ONE` | PASS | Configuration invariant plus simultaneous multi-instance admission test |
| `GATE2_CONCURRENCY MAXIMUM_TWO` | PASS | Two admitted, third queued; values over two rejected |
| `QUEUE_BEYOND_CAPACITY ENFORCED` | PASS | Transactional FIFO head and active-capacity checks across authority instances |
| `PROGRESS TYPED_PERSISTED_AND_VISIBLE` | PASS | Exact state enum, transition audit, authenticated snapshots and queue positions |
| `CANCELLATION TERMINAL_AND_CLEAN` | PASS | Queued, active, async/provider-wait cancellation tests; owned temp cleanup and retained audit |
| `FALSE_PARTIAL_COMPLETION ZERO` | PASS | Cancellation-before-completion barrier, lease-expiry failure, and Gate 2 completed-owner check |
| `LOCAL_OCR_WORKER_POOL ABSENT` | PASS | Contract constant, architecture policy, and anti-drift assertion |

## Verification

- Focused workload/architecture/bundle suite: `39 passed`.
- Complete service suite after final bundle generation: `1015 passed, 20 skipped`.
- The five warnings are existing SWIG deprecation warnings (`SwigPyPacked`, `SwigPyObject`, `swigvarlink`).
- Ruff on all changed source and focused tests: passed.
- Python compilation of all changed runtime entrypoints: passed.
- `git diff --check`: passed.
- All three generated bundles were built twice and produced identical SHA-256 values.

Bundle SHA-256:

- Gate 1: `D65CBED620357E4273E546DBFACFB59B6FF5055EE18E17290D0B89797A32E089`
- Gate 2 source-fact: `5F337AB5D1B14D8232AB2B39B4C7E03497391D5A359AA53053A6915587A5EBFD`
- Gate 2 domain: `FC5D290DB52CC2B4E616DF55214BF85738DF6617B5C174FADE01B6B198EA5C78`

## Residual risk

This goal proves the authority contract and production routing with deterministic and integration tests. It does not claim a live multi-host deployment exercise against production data. SQLite coordination assumes all participating OpenWebUI workers use the same configured database filesystem, which is now an explicit deployment contract and fails closed on capacity-contract drift.
