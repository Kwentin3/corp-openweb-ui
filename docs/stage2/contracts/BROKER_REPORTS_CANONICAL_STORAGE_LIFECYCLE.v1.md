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

## Deployment requirement

The only allowed deployment reuses this ArtifactStore below the existing
`openwebui_data:/app/backend/data` mount. STT storage is an operational pattern,
not a shared canonical engine. A local or temporary directory cannot substitute
for target durability proof.

Admission requires terminal pointer/component accounting, successful reader
reconstruction across controlled restart/container recreation, an isolated
application-consistent restore, cross-scope denial and capacity preflight
before reservation. Historical isolated/target proofs are audit evidence, not
permission for a new product cutover; revalidate the current target at the
start of any authorized migration.
