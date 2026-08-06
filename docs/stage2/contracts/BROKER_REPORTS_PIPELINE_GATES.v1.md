# Broker Reports Pipeline Gates v1

Status: `CURRENT`

Date: 2026-08-06

This contract is the sole current authority for global Broker Reports gate
numbers. It supersedes the gate-number assignment in
`BROKER_REPORTS_GATE_ARCHITECTURE.md`; local capability names and historical
artifact/module names remain compatibility identifiers only.

## Current gates

| Gate | Input | Owned work | Authoritative output | Evidence and projections |
| --- | --- | --- | --- | --- |
| Gate 1 | authenticated upload/request | custody, access checks, format detection, original-byte storage and route selection | resolver-backed original source artifact and intake/routing receipt | file/profile diagnostics are evidence, not a normalized document |
| Gate 2 | Gate 1 source ref plus trusted `ArtifactAccessContext` | format-specific extraction, deterministic normalization, provenance/issues, immutable version storage | validated `CanonicalArtifactV1`; exactly `OUTPUT OF GATE 2` | FullSource/parser units, table proposals, crops and raw provider responses remain evidence; `gate2_handoff_v0` is a temporary authoritative compatibility read |
| Gate 3 | active validated canonical version | product/task-specific LLM-friendly projection and financial semantic analysis | future semantic result and its checked evidence | no current implementation or activation; a reader-only neutral completeness renderer is proof tooling, not a stage output |

There is no current Gate 4 in this contract. Any older four-gate description is
`SUPERSEDED` for numbering and remains readable only as migration history.

## Authority and non-authority

- `CanonicalNormalizerFactory.create` is the sole Gate 2 logical builder.
- `CanonicalArtifactStoreFactory.create` is the sole Gate 2 lifecycle facade;
  storage mechanics stay in the `ArtifactStoreFactory` adapter.
- `CanonicalReaderFactory.create` is the sole canonical read boundary.
- Original source bytes and full private evidence remain resolver-backed and
  are never replaced by a canonical version.
- A provider response is a proposal/evidence item, never canonical authority.
- A product/task-specific LLM-friendly projection is a Gate 3 derivative, never
  canonical source. The format-neutral reader-only DOC33 renderer is bounded
  proof tooling and does not persist or activate a stage output.
- Financial facts, roles, ontology, tax meaning and cross-document
  reconciliation are absent from `CanonicalArtifactV1`.

## Current compatibility boundary

`gate2_handoff_v0` remains the only product read authority. Canonical writes
and comparisons are controlled shadow operations; the global product canonical
read valve remains disabled. DOC27 permits only consumer-specific canonical
read flags. Three isolated test consumers use that boundary; the local research
consumer is fail-closed because its real active canonical version is absent.
No background or primary product consumer was switched. Historical Python
filenames beginning with `gate1_` or `gate2_`, the
package name `broker-reports-gate1-proof`, and persisted schema IDs do not
reassign current gate ownership.

The existing financial-semantic modules named `gate2_*` are legacy-named
contours. They are not evidence that DOC26 created or activated current Gate 3.
They remain compatibility/historical surfaces until a separately authorized
consumer migration and Gate 3 contract.

## Status index

| Document family | Status | Rule |
| --- | --- | --- |
| this contract and Canonical Artifact/Storage/Reader v1 | `CURRENT` | owns current pipeline and canonical meaning |
| architecture authority map | `CURRENT` | owns factories and duplicate-prevention boundaries |
| global gate architecture dated 2026-07-22 | `SUPERSEDED` | old numbering only; link here before use |
| `gate2_handoff_v0` contracts/readers | `DEPRECATED` | compatibility authority until consumer-specific cutover and Wave 4 |
| DOC7-DOC26 reports, receipts and safe evidence | `HISTORICAL_EVIDENCE` | immutable; never rewritten to current terminology |
| research-only Managed Document/DOC23/DOC24 candidates | `HISTORICAL_EVIDENCE` | regression inputs, not product authority |
| a current Gate 3 contract/implementation | `UNRESOLVED` | not created by DOC26 |

## Invariants

1. `CanonicalArtifactV1 = OUTPUT OF GATE 2`.
2. Gate 1 does not mint canonical normalized document meaning.
3. Gate 2 does not add financial semantics.
4. Gate 3 is not started by a shadow write, lifecycle proof or active-pointer
   unit test.
5. A consumer-specific test flag is not a global or primary product cutover.
6. Product cutover requires a separate authorization after consumer migration.

## DOC28 deployment gate

The configured Broker Reports SQLite and payload defaults are below
`/app/backend/data`, and the repository compose contract mounts the named
`openwebui_data` volume there. This is a deployment candidate, not current
operational proof. DOC28 found no accessible target container/volume, no
authorized VPS route and no completed backup/restore drill. Durable canonical
writes, active-version creation, research cutover and Wave 2 shadow therefore
remain blocked. Global/background/primary canonical reads remain disabled.

## DOC29 deployment update

The target deployment, Compose project, containers, volumes and Broker paths
are now identified. An isolated 16-document durable contour passed, including
research rollback and 6x3 Wave 2 shadows. The bounded target backfill produced
no terminal receipt and the host control plane became unresponsive, so Gate 2
durability is only partial. Gate 3 is still not started, legacy handoff is
retained, and neither Wave 2 nor primary cutover is authorized.

## DOC32 PDF round-trip update

DOC32 repaired the Gate 2 PDF adapter/completeness boundary and the closed-world
parser runtime used by the bounded backfill. Full Evidence remains private and
separate; `CanonicalArtifactV1` remains the Gate 2 machine-readable document;
the neutral research projection is derived only from `CanonicalReader` and is
not Gate 3. Eight corrected PDF versions are active and durable, while their
old incomplete versions remain superseded evidence. Research migration passed
and Wave 2 passed shadow-only. `gate2_handoff_v0` remains product authority;
Wave 2 cutover, primary cutover and Gate 3 were not performed.

## DOC33 unified machine-projection update

DOC33 confirms the existing `canonical_artifact_v1` schema and
`CanonicalReaderFactory.create` as the one Gate 2 public logical contract and
reader for PDF, HTML, CSV and XLSX. The shared validator now enforces common
root/node/container/reference and meaningful-content completeness rules for all
four formats; PDF retains stricter source-atom accounting. Six Wave 2 shadow
contracts consume the same reader without a source-format field or branch.

The reader-only `render_neutral_canonical_projection` helper demonstrates
ordered text/table/issue delivery from all four formats without source bytes,
private evidence, provider or financial-semantic access. It is not persisted,
not a product consumer, and not Gate 3. The normative summary is
[Gate 2 Exit Contract v1](./BROKER_REPORTS_GATE2_EXIT_CONTRACT.v1.md).

No Wave 2 cutover, primary product cutover, global read activation, legacy
removal or Gate 3 start was performed by DOC33.
