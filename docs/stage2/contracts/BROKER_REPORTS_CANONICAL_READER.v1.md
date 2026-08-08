# Broker Reports Canonical Reader v1

Status: `CURRENT`

Date: 2026-08-06

## Boundary

`CanonicalReaderFactory.create` is the sole Gate 2 canonical query/lifecycle
boundary. It receives the ArtifactStore-created adapter and trusted
`ArtifactAccessContext`; consumers never observe SQLite, payload paths or the
single/chunked physical choice.

## Operations

- `read(manifest_ref, context)` resolves one validated immutable version;
- `read_envelope(manifest_ref, context)` resolves that exact manifest and adds
  safe identity/status/root/layout/component/byte accounting;
- `read_active(document_id, context)` follows the authenticated atomic pointer;
- `read_active_envelope(document_id, context)` returns the same validated
  artifact plus safe version/layout/component/byte accounting for compatibility
  telemetry;
- `history(document_id, context)` returns cross-run version metadata;
- `read_container(...)` returns one container and its ordered nodes;
- `read_table(...)` returns one table node;
- `activate(...)` and `rollback(...)` delegate atomic lifecycle operations and
  return append-only safe receipts.

Every logical reconstruction rechecks persisted component checksums and the
canonical root hash, validates the common source/root/container/node contract,
and repeats the format-neutral completeness assessment. Partial reads have the
same API for small single-payload, component-chunked and XLSX row-chunked
documents. Missing components, stale versions, invalid references, empty
non-empty inputs, blocking issues and lifecycle-invalid records fail closed;
there is no silent legacy fallback.

## Consumer compatibility status

DOC27 consumer-specific adapters return exactly one internal status:

`CANONICAL_OK`, `CANONICAL_INCOMPLETE`, `CANONICAL_CONFLICT`,
`CANONICAL_ACCESS_DENIED`, `CANONICAL_VERSION_UNSUPPORTED` or
`CANONICAL_STORAGE_FAILURE`.

Each adapter has a versioned mapping and its own `CANONICAL_READ_<CONSUMER_ID>`
flag. The adapter may only call this reader, never ArtifactStore/SQLite/payload
paths or private research evidence. Missing active versions, unsupported schema,
unresolved provenance, missing chunks/root mismatch and blocking conflicts are
terminal. The adapter never performs legacy fallback; orchestration rolls back
by disabling that consumer's flag.

Safe telemetry contains only consumer/wave, attempts/success/blocked, latency,
payload byte count, component count, schema version, a hash of version ID,
compatibility status and rollback count. Source text, table values, paths and
tenant identity are forbidden.

## Product policy

Canonical reads remain disabled by default and there is no global read cutover.
G3.C5 explicitly enables the reader only inside stable Workspace
Model/workflow `broker-reports-ndfl`; other test-scoped consumer flags cannot
authorize a background or primary product read. `gate2_handoff_v0` remains
product compatibility authority for consumers not explicitly migrated.

The reader returns Gate 2 source representation only.
`render_neutral_canonical_projection` accepts only the reader-returned artifact
for PDF, HTML, CSV and XLSX. It has no financial semantics or private evidence
dependency and remains completeness proof tooling rather than a product
implementation. G3.2 `Gate3ProjectionFactory.create` is the sole task-specific
projection consumer: after the NDFL workflow resolves and compare-and-swap
activates one exact manifest through this reader, it calls
`read_active_envelope` and emits one non-persisted `Gate3ProjectionV1`. It has
no format input, provider call or fallback and is product-active only through
NDFL. The six Wave 2 diagnostic contracts likewise consume the one reader;
none was cut over.

The [Gate 2 Exit Contract v1](./BROKER_REPORTS_GATE2_EXIT_CONTRACT.v1.md) is the
normative boundary summary. Product cutover beyond NDFL, a global canonical
read valve and destructive legacy deletion remain separately authorized work.
G3.3 and later semantic behavior stays outside this reader contract.
