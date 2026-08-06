# Broker Reports Canonical Storage and Lifecycle v1

Status: `CURRENT`

Date: 2026-08-05

## Ownership

`CanonicalArtifactStoreFactory.create` is the sole Gate 2 canonical lifecycle
facade. It delegates SQLite/blob mechanics to the existing
`ArtifactStoreFactory.create` adapter. Business code does not open SQLite or
payload paths. Every operation requires a trusted `ArtifactAccessContext`;
logical tenant identity comes only from that server context.

## Immutable version record

Each processing run reserves one immutable document-scoped version with:

- `document_id`, `source_artifact_ref`, `canonical_version_id` and monotonic
  `canonical_version_number`;
- schema, normalizer, source and canonical-root hashes;
- `previous_version_ref`, status, creation/activation times and retention class;
- the processing run ID and immutable manifest/component bindings.

Reprocessing never overwrites a version. The same source/content hash in a new
run is still a distinct version. A repeated publish in the same run is
idempotent only when all immutable material and component bytes match.

## Physical model

Small documents use one private file-backed manifest containing the complete
logical artifact. Larger documents use an immutable graph: manifest/envelope,
container inventory, ordered nodes per container, independently addressable
large tables, and provenance/issues.

All records use the existing ArtifactStore payload root. An atomic batch write
removes newly created payloads when its SQLite transaction fails. Finalization
checks every component ref and persisted checksum before changing `CANDIDATE`
to `VALIDATED`. A candidate with missing/changed chunks cannot activate.

## Activation and rollback

The operational state machine is
`CANDIDATE -> VALIDATED -> ACTIVE -> SUPERSEDED`.

There is at most one `ACTIVE` version per authenticated document scope. A
SQLite `BEGIN IMMEDIATE` compare-and-set transaction validates the complete
component graph, supersedes the old active version, changes retention classes,
switches the pointer and appends a safe activation receipt. A stale expected
pointer fails with `canonical_pointer_conflict` and preserves the old active.
Activating the already-active target is an idempotent `no_op` receipt.

Rollback is the same atomic pointer operation with operation `ROLLBACK`. It
targets an already validated/superseded immutable version, never deletes the
newer version, and records actor, reason, time and a context fingerprint.
Lifecycle APIs exist for shadow/storage proof; product canonical reads remain
disabled in DOC26.

## Retention classes

Configured classes are `SOURCE`, `ACTIVE_CANONICAL`,
`SUPERSEDED_CANONICAL`, `EVIDENCE`, `RAW_PROVIDER`, `TEMPORARY`,
`PROJECTION_CACHE` and `RESEARCH`. `RetentionPolicy` remains the execution
authority for TTL/cascade behavior. Activation assigns `ACTIVE_CANONICAL` and
rotation/rollback assigns `SUPERSEDED_CANONICAL` atomically.

Evidence cannot be purged before validation, ref/hash resolution, safe receipt,
pointer movement and the configured rollback window. Explicit run/source purge
deletes component payloads, removes component bindings and removes an active
pointer rather than leaving it aimed at purged data.

## Access

- source publish validation matches user, case-or-chat, workspace, document and
  current processing run;
- cross-run history/read matches authenticated user, case-or-chat, workspace
  and document while deliberately not trusting a caller tenant value;
- private read/activation/rollback requires `allow_private=true`;
- guessed IDs, stale pointers, deleted/expired/purge-pending records and hash
  mismatch fail closed.

Typed failures include `canonical_chunk_missing`,
`canonical_chunk_hash_mismatch`, `canonical_pointer_conflict`,
`canonical_version_not_active`, `canonical_source_scope_mismatch` and
`canonical_retention_class_invalid`, plus existing ArtifactStore failures.

## DOC28 durability status

The sole allowed deployment candidate reuses this ArtifactStore under the
existing `openwebui_data:/app/backend/data` mount. It has not been admitted as
operational: the target volume and container were not accessible from the
authorized environment, restart persistence was not observed, and the
repository backup/restore procedure has no completed integrity drill. A local
or temporary directory must not substitute for that missing proof. No DOC28
durable version or active pointer was created.

## DOC29 durability update

DOC29 identified the target and selected the existing Broker namespace inside
`openwebui_data`; STT storage is reused only as an operational pattern. The
16-document parser-only path passed in an isolated persistent store with 16
validated/active versions, 172 components, matching roots, partial reads and
an isolated application-consistent restore. Capacity checks now fail the
canonical write before version reservation at the configured hard floor.

Target admission remains incomplete. The bounded target job did not return a
receipt and the host stopped serving application health and SSH banners. Until
console recovery plus pointer/chunk accounting, restart and isolated target
restore are complete, the target store is `PARTIAL`, not operational.
