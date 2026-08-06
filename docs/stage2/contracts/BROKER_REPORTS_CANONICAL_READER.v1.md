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

`CANONICAL_GATE2_READ_ENABLED=false` remains mandatory globally. DOC27 enables
only three test-scoped consumer flags; the research flag is blocked without its
real active version. `gate2_handoff_v0` remains the sole background/primary
product read authority until separately authorized later waves.

The reader returns Gate 2 source representation only. DOC32 added a neutral,
research-only PDF proof projection. DOC33 minimally generalized that existing
helper as `render_neutral_canonical_projection` for PDF, HTML, CSV and XLSX. It
accepts only the reader-returned canonical artifact, has no financial semantics
or private evidence dependency, and is not a Gate 3 or product implementation.

DOC28 did not advance this authority. The approved source cohort is locally
available, but no accessible durable active versions exist. The research
consumer remains blocked, all six Wave 2 product consumers remain on legacy,
and no shadow execution or fallback was attempted.

## DOC29 reader update

DOC29 added six factory-routed, read-only Wave 2 shadow contracts. In the
isolated durable cohort each consumer completed three stable 16-document runs
with zero canonical/access regressions, provider requests, product writes or
fallbacks. These are compatibility shadows only: consumers migrated = 0.
Target execution is blocked by host recovery, so Wave 2 cutover is not ready.

## DOC32 reader update

The target now has eight corrected active PDF versions with non-empty ordered
nodes. Reader reconstruction verified 76 physical components with zero missing
chunks before and after service restart, container recreation and isolated
restore; cross-tenant reads remained denied. The research PDF adapter uses
`local_pdf_compact_research_output_v2` and returns a generic projection derived
only from the reader envelope. Six Wave 2 contracts passed shadow-only; none was
migrated and no global/product read valve changed.

## DOC33 unified reader update

DOC33 confirms `CanonicalReaderFactory.create` as the one public read authority
for all four supported formats. A read-only retained-cohort proof returned 16/16
validated artifacts and 16/16 non-empty neutral projections through that reader.
The six Wave 2 shadow outputs no longer expose source format as a consumer API
field; their projection kind, ordered structure, table, issue and provenance
requirements are format-independent. Format remains available only inside the
canonical source identity for audit and inside Gate 2 adapters/diagnostics.

The [Gate 2 Exit Contract v1](./BROKER_REPORTS_GATE2_EXIT_CONTRACT.v1.md) is the
normative boundary summary. Product cutover, the global canonical read valve,
legacy deletion and Gate 3 remain unchanged.
