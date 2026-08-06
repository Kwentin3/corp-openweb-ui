# Broker Reports DOC31 XLSX Streaming Runbook

Use the closed-world DOC31 image built from `Dockerfile.doc31`. Mount the frozen
cohort read-only and the canonical data volume read-write. Keep concurrency and
batch size at one.

## Order of operations

1. Confirm OpenWebUI health, Broker/STT SQLite integrity, free capacity, the
   frozen `8 completed / 8 pending` checkpoint and absence of a running job.
2. Run `small-canary` in the isolated DOC31 canary namespace.
3. Run the exact failed XLSX with the frozen limits. Stop on OOM, root mismatch,
   missing chunk, unexpected active pointer, service degradation or DB failure.
4. Re-run `verify` before processing another document.
5. Resume only pending indexes. XLSX uses the streaming route; PDF/HTML/CSV use
   the retained DOC30 route. Exact duplicate source instances receive a stable
   per-cohort document scope; source and canonical root hashes do not change.
6. Run `verify --require-complete`. Expected accounting is 16 active roots,
   zero missing chunks and cross-tenant denial.
7. Restart only the relevant OpenWebUI service, wait for healthy, and verify.
   Recreate a disposable verifier on the unchanged volume and verify again.
8. With mutations paused, run `backup`; then run `restore` into an empty,
   isolated namespace. The restore must validate all roots/components through
   reader factories.
9. Run the research consumer. Stop before Wave 2 if any consumer returns
   incomplete, unresolved, access-open or storage-failure status.

## Resume and cleanup

The private DOC30 checkpoint remains the cohort authority. XLSX staging lives
under the private DOC31 namespace and is reusable only when its sealed authority
and every chunk hash match. Never edit checkpoints manually.

A failed unfinalized streaming candidate is removed by
`abort_canonical_candidate`. A fully persisted but unactivated failed run is
cleaned only through the scoped retention API. Never delete payload files or
SQLite rows directly.

## Restore boundaries

Backup uses SQLite Online Backup and snapshots only immutable payloads
referenced by active canonical graphs. The private manifest and restored
payloads stay outside Git. Do not replace the live namespace during proof;
restore into a separate empty root and exercise normal readers plus the
cross-tenant denial check.

## Current stop

DOC31 reached 16/16 storage durability, but research migration stopped because
the eight retained PDF canonicals have zero logical nodes and correctly return
`CANONICAL_INCOMPLETE`. Wave 2 shadow and all cutovers remain prohibited until a
separate goal repairs and re-proves that PDF source-accounting gap without
rewriting historical evidence.
