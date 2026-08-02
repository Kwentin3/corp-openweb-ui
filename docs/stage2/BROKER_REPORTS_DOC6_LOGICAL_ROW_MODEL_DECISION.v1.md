# Broker Reports DOC6 Logical-Row Model Decision v1

Status: `APPROVED_INACTIVE_ARCHITECTURE`

Decision date: `2026-08-02`

Governing contract:
[Managed Document v2](./contracts/BROKER_REPORTS_MANAGED_DOCUMENT.v2.md)

## 1. Context and risk

The canceled DOC5.1 direction treated a table primarily as a rectangular
rows/cells grid with spans. That shape is adequate for regular tables, but it
cannot be the universal source of truth for the observed PDF corpus:

- table titles and group headers are rows without a full data-grid shape;
- nested labels, sparse data rows, notes, subtotals and totals have different
  entry counts;
- physical X positions do not always equal logical columns;
- a wide visual region does not imply several empty logical cells;
- page continuation and repeated headers are order/hierarchy facts, not grid
  completion.

Forcing those structures into a rectangle creates fake empties, loses row
roles and hierarchy, and makes geometry the semantic authority. The active risk
is silent structural distortion while all physical cells still appear
accounted.

## 2. Decision

The canonical TABLE v2 model is:

```text
ordered logical rows
-> explicit row roles
-> explicit row nesting and parent
-> ordered row entries
-> optional logical-column bindings
-> private geometry evidence
```

Rows may have different entry counts. `logical_columns[]` may be empty. A
rectangular grid may be derived only after regularity is proven and remains a
non-authoritative consumer projection.

`rows[][]`, canonical cells, required equal-width rows, span coordinates and
`COVERED_BY_SPAN` placeholders are rejected as the v2 core. Visual coverage
may be recorded as `covers_logical_column_ids` or private evidence, without
inventing entries.

## 3. Domain and ownership map

| Boundary | Sole owner | Owns | Does not own |
| --- | --- | --- | --- |
| Existing private source projection | `FullSourceArtifactFactory.create` | PDF text/layout observations, source order, words, refs and parser provenance | Logical rows, roles or v2 validation |
| Inactive PDF document assembly | `ManagedPdfDocumentV2Factory` | Raw-byte/private-artifact-identity intake, internal FullSource invocation, sole-complete-projection consumption, document block order, table-factory coordination and one v2 candidate | A second parser, caller-supplied parallel projection, provider route or v1 mutation |
| Logical table recovery | `LogicalRowTableFactory` | Boundaries, row bands/order/grouping, roles, hierarchy, entries, optional columns, continuation and word ownership | Contract acceptance, rendering or financial semantics |
| v2 acceptance | `ManagedDocumentContractV2Validator` | Schema, deterministic invariants, canonical JSON and integrity | Source reading, inference, repair or persistence |
| Derived model view | `ManagedDocumentLlmViewV2Factory` | Deterministic row-oriented projection of validated v2 | Source authority, recovery or summarization |
| Independent view audit | `ManagedDocumentLlmViewV2Auditor` | Independent field/row/entry accounting and omission checks | Construction, repair or shared renderer logic |

These are distinct operation authorities inside Global Gate 1, not new product
gates. No operation has two owners.

## 4. Boundary contracts

### 4.1 Input

`ManagedPdfDocumentV2Factory.create(schema)` returns a builder whose public API
is `build(content_bytes, source_artifact_ref=...)`. It requires non-empty raw
PDF bytes and a `PRIVATE_SOURCE` artifact identity, invokes the established
FullSource builder internally, and consumes only the sole complete
`pdf_text_layer_projection`. It does not accept a filename as semantic input,
accept a caller-built competing projection, invoke a parallel PDF parser, or
elevate a bounded preview into full source authority.

The raw source artifact remains private and checksum-bound. Recovery may use
words, bbox, ruled-region observations, physical-span observations, anchors and
continuation evidence already carried by the source boundary.

### 4.2 Output

`ManagedPdfDocumentV2Factory` submits one complete candidate to
`ManagedDocumentContractV2Validator`. The validator returns a copied,
integrity-bound `broker_reports_managed_document_v2` value or fails closed.
For this PDF route, `document_id` is a deterministic internal diagnostic hash
of the supplied private artifact identity. It is classified `PRIVATE_SOURCE`,
excluded from safe diagnostics and never enters LLM Document View v2 or its
parity surface.

TABLE content has:

```text
table_id
ordered_rows[]
logical_columns[]
source_parts[]
relations[]        # document relation-ID refs
issues[]           # document issue-ID refs
known_gap_ids[]
```

Geometry evidence and source-word ownership are top-level private registries.
They are referenced from TABLE structures but are not duplicated in TABLE.

### 4.3 View

LLM Document View v2 starts only from a validated v2 value. It preserves table,
row and entry order, roles, nesting, parents, optional column bindings,
continuation and safe source pointers. It excludes bbox, coordinates, private
refs, evidence checksums, confidence values and source-word traces.

The independent auditor does not import renderer internals or use rendered text
as the machine source of truth.

## 5. Recovery flow

```text
ManagedPdfDocumentV2Factory.create(schema)
-> build(raw PDF bytes, private source-artifact identity)
-> sole complete FullSource PDF projection
-> table boundary
-> ordered row bands
-> row grouping
-> observable row roles
-> ordered entries
-> optional logical columns
-> private geometry relations
-> exact-once source-word reconciliation
-> Managed Document v2 validation
-> inactive LLM Document View v2
```

`LogicalRowTableFactory` is the only table-recovery owner in this flow.
Research helpers may propose boundaries or evidence, but they cannot emit
canonical TABLE state or bypass validation.

## 6. Invariants

### 6.1 Rows and entries

- table row order and each row's entry order are contiguous and exact;
- row, entry and column IDs are document-unique;
- role is one of the closed neutral structural roles;
- unresolved role, nesting, parent or column binding is local and issue-bound;
- parent rows precede children and are proven `GROUP_HEADER` rows;
- no entry is invented to fill a coordinate;
- no source value is normalized, dropped, duplicated or moved to another row.

### 6.2 Optional columns

Columns exist only when headers plus repeated observable alignment prove them.
Physical positions such as description, currency marker and number may map to
fewer logical columns. Amount values and financial expectations are not
evidence.

An empty column model preserves the ordered entries. It does not flatten the
TABLE or make the row unknown.

### 6.3 Geometry

Geometry supports, but does not define, boundary, row membership/order,
indentation, entry grouping, column alignment, visual coverage and
continuation. Geometry remains `PRIVATE_SOURCE` and cannot enter the model
view except through bounded safe source pointers.

### 6.4 Source ownership

Every word inside a TABLE region is exactly one of `OWNED`,
`PROVEN_DUPLICATE` or `UNRESOLVED`. Each entry owns at least one canonical
word. Each ownership record carries a distinct word-level source anchor that
is also bound to its owner entry. For PDF, its `source_word_id` is
deterministically derived from that anchor's non-empty
`locator.source_block_ref`, and the anchor must carry a word bbox. An unresolved word blocks that table;
accepted DOC6 evidence requires zero unresolved words, zero multiple owners
and zero paragraph duplication.

## 7. Reuse decision for the stopped DOC5.1 work

The preserved DOC5.1 checkpoint is evidence, not an implementation base.

Neutral facts allowed for explicit reuse:

- PDF crops, high-DPI renders, OCR and visual transcripts;
- source hashes, words, bbox and ruled-region observations;
- physical span observations as secondary evidence;
- exact-once word ownership, anchors, overlap and continuation checks;
- safe-pointer, canonical-JSON, integrity, privacy and independent-auditor
  patterns.

Rejected as architecture:

- the canceled grid-first v2 schema as a whole;
- `rows[][]` or cells as TABLE authority;
- cell spans as the central recovery model;
- covered-coordinate placeholders;
- cell/span-count parity as semantic parity.

No stopped DOC5.1 file is copied into the DOC6 implementation PR merely
because it exists in the checkpoint.

## 8. Delivery slices

1. Freeze the row-first v2 schema and standalone validator.
2. Implement the sole `LogicalRowTableFactory` behind the inactive v2
   document factory.
3. Prove boundary, row, entry, column, continuation and ownership behavior with
   synthetic fixtures.
4. Seal visual gold independently from parser/recovery output.
5. Build deterministic LLM Document View v2 and its independent auditor.
6. Compare PDF visual gold -> Managed Document v2 -> LLM Document View v2.
7. Run regression, privacy, closed-world, bundle-parity and architecture
   checks before any merge.

Each slice is additive and verifiable. None changes v1 or activates a product
consumer.

## 9. Validation and acceptance

Contract validation proves expressibility and invariant enforcement. Recovery
acceptance additionally requires:

```text
EXPECTED_LOGICAL_TABLES_TOTAL = 28
REPRESENTED_LOGICAL_TABLES_TOTAL = 28
BASELINE_TABLES_REGRESSED_TOTAL = 0
MISSING_LOGICAL_ROWS_TOTAL = 0
EXTRA_LOGICAL_ROWS_TOTAL = 0
WRONG_ROW_ORDER_TOTAL = 0
CRITICAL_ROW_MISMATCHES_TOTAL = 0
CRITICAL_ENTRY_MISMATCHES_TOTAL = 0
INVENTED_SOURCE_VALUES_TOTAL = 0
DROPPED_SOURCE_VALUES_TOTAL = 0
DUPLICATED_SOURCE_VALUES_TOTAL = 0
UNRESOLVED_TABLE_WORDS_TOTAL = 0
MULTIPLE_ENTRY_WORD_OWNERS_TOTAL = 0
TABLE_WORDS_DUPLICATED_AS_PARAGRAPH_TOTAL = 0
```

Local noncritical UNKNOWN roles or column bindings remain allowed when the row
and values are preserved, the issue is explicit and visual gold also records
the uncertainty.

## 10. Risks and controls

| Risk | Control |
| --- | --- |
| A recovery helper becomes a second TABLE authority | Architecture tests require all canonical TABLE creation to route through `LogicalRowTableFactory`. |
| Physical X positions become semantic columns | Columns require repeated alignment and header/geometry evidence; unknown remains local. |
| Spans recreate a hidden grid | No core cell/span objects; coverage is an evidence-bound entry relation only. |
| Geometry leaks into the view | Private information partition plus independent view omission audit. |
| Source values are lost or duplicated | Exact-once word ownership and paragraph-overlap reconciliation. |
| v2 silently activates | No product consumer, provider route or generated-bundle change; inactive flags and architecture import checks remain required. |
| Recovery overfits the corpus | No file, broker, page, safe-ID or bbox constants; synthetic transformations and holdout checks. |

## 11. Non-goals and deferred work

DOC6 does not:

- mutate or deprecate Managed Document v1;
- define financial types or infer financial meaning;
- activate v2 in OpenWebUI or Gate 2;
- call a provider or begin model qualification;
- create Knowledge/RAG or vector artifacts;
- make a derived rectangular projection canonical;
- authorize OCR/VLM as runtime table authority;
- change generated bundles.

Product activation, a public persistence route and any regular-table
rectangular convenience projection require separate contracts and goals.

## 12. Decision receipt

```text
DOC6_CANONICAL_TABLE_MODEL = ORDERED_LOGICAL_ROWS
LOGICAL_COLUMNS = OPTIONAL_EVIDENCE_BOUND
GEOMETRY = PRIVATE_SECONDARY_EVIDENCE
SOURCE_WORD_OWNERSHIP = EXACT_ONCE_PRIVATE_REGISTRY
RECTANGULAR_GRID_FIRST_MODEL = REJECTED
CELL_SPAN_CORE = REJECTED
FULL_SOURCE_PROJECTION_OWNER = FullSourceArtifactFactory.create
TABLE_RECOVERY_OWNER = LogicalRowTableFactory
CONTRACT_VALIDATOR_OWNER = ManagedDocumentContractV2Validator
SCHEMA_IDENTITY = EXACT_ID_PLUS_CANONICAL_SHA256
V1_CHANGED = FALSE
PRODUCT_ROUTE_CHANGED = FALSE
PROVIDER_CALLS_AUTHORIZED = ZERO
PRODUCT_ACTIVATION = NOT_STARTED
```
