# Broker Reports Managed Document v2

Status: `CONTRACTED_INACTIVE`

Schema version: `broker_reports_managed_document_v2`

Contract owner:
`services/broker-reports-gate1-proof/broker_reports_gate1/managed_document_contracts_v2.py`

Schema: `BROKER_REPORTS_MANAGED_DOCUMENT.v2.schema.json`

## 1. Decision

Managed Document v2 is an additive Global Gate 1 representation contract. It
keeps the v1 source-bound ordered document stream, but replaces the TABLE core
with an ordered collection of logical rows:

```text
TABLE
-> ordered logical rows
-> row roles and hierarchy
-> ordered entries inside each row
-> optional logical-column bindings
-> private geometry evidence
```

A table is not a rectangular grid by definition. Different rows may contain
different numbers and kinds of entries. Sparse rows, titles, group headers,
notes, subtotals and totals are valid rows and are not padded.

The following are not canonical v2 table state:

- `rows[][]`;
- cells or cell coordinates;
- a required equal-width grid;
- merged-cell or span topology;
- synthetic empty entries representing visually covered coordinates.

A later consumer may derive a rectangular view for a proven regular table, but
that view cannot write back into v2 or become source authority. A visual span
is only secondary evidence or an entry-to-column coverage relation.

Managed Document v1 and its schema, validator, builder and view remain
unchanged. There is no implicit v1-to-v2 upgrade.

## 2. Inactive boundary and sole owners

The DOC6 contour is offline and inactive:

| Operation | Sole owner | Responsibility |
| --- | --- | --- |
| Full-source PDF observations | `FullSourceArtifactFactory.create` | Existing private source text, order, words, layout and provenance projection. |
| PDF-to-v2 document orchestration | `ManagedPdfDocumentV2Factory` | Accepts raw PDF bytes plus a required private source-artifact identity, invokes the established FullSource owner internally, consumes its sole complete PDF projection, preserves document order, coordinates table recovery and submits one candidate for validation. |
| Logical table recovery | `LogicalRowTableFactory` | Table boundary, ordered row bands, row grouping, roles, hierarchy, entries, optional logical columns, continuation and source-word ownership. |
| v2 contract validation and sealing | `ManagedDocumentContractV2Validator` | Draft 2020-12 schema, cross-object invariants, duplicate-key rejection, canonical JSON and integrity. |
| LLM Document View v2 | `ManagedDocumentLlmViewV2Factory` | Deterministic derived row-oriented view of an already validated v2 document. |
| Independent view audit | `ManagedDocumentLlmViewV2Auditor` | Recomputes view coverage independently; it does not construct or repair the view. |

`ManagedPdfDocumentV2Factory.create(schema)` returns the inactive builder. Its
public `build(content_bytes, source_artifact_ref=...)` API accepts non-empty raw
PDF bytes and a required `PRIVATE_SOURCE` artifact identity. The builder calls
the exact `FullSourceArtifactFactory.create()` builder exactly once and
delegates to a private assembly seam. The additive
`build_with_source_bound_scopes(...)` accepts the same original bytes/private
artifact identity plus raw scope requests and also invokes FullSource exactly
once. No public method accepts `FullSourceBuildResult`, profile, units, summary,
ready receipt or ready reviewed evidence.
The factory and builder expose no FullSource/recovery/validator dependency
injection or mutable owner attributes; the private build call constructs both
established source owners and the exact v2 validator as local variables. Tests may
count the real owner call through a local monkeypatch, but no official builder
path accepts a fake owner or validator.

Only `build_with_source_bound_scopes(...)` accepts original
`source_bound_scope_requests`; the legacy `build(...)` signature and behavior
remain unchanged. The builder passes those requests to
`LogicalRowTableFactory.recover_with_source_bound_scopes`, where the existing
binder creates and consumes private receipts within the same owner call. No
ready receipt or caller-created scope is accepted. The closed v2 document
retains the resulting title/header rows, issues and exact word ownership; the
receipt transport fields remain recovery-only and are not added to v2
`source_parts`. An accepted `PRESENT` leading title/header/body partition keeps
a narrow inspectable `reviewed_source_bound_evidence` record with the same-call
scope receipt ref, proposal hash, raster-manifest hash and bound source-word
refs. A bound `ABSENT`, `EMPTY`, `EXPLAINER` or partial receipt is audit-only:
it may keep `source_bound_audit_evidence`, but it never relabels rows or entries
as `REVIEWED_SOURCE_BOUND` and contributes nothing to the private reviewed
plan.

The builder consumes only the sole complete `pdf_text_layer_projection`. The
recovery owner does not reread a path, run a parallel PDF parser, call a
provider, or treat a preview slice as complete source authority. Raw PDF bytes
and the supplied artifact ref remain inside the existing Gate 1 source
boundary.

The normative inactive flow is:

```text
ManagedPdfDocumentV2Factory.create(schema)
-> ManagedPdfDocumentV2Builder.build(content_bytes, source_artifact_ref=...)
-> FullSourceArtifactFactory.create().build
-> shared validated ManagedPdfDocumentV2 assembly seam
-> LogicalRowTableFactory
-> ManagedDocumentContractV2Validator
-> broker_reports_managed_document_v2
-> ManagedDocumentLlmViewV2Factory
```

No owner in this contour is a product entrypoint. Provider calls, model-based
structure recovery, Knowledge/RAG, vectorization, product activation and
generated-bundle routing are forbidden.

## 3. Contract-owner boundary

The contract owner provides:

- closed enums and the copied, validated `ManagedDocumentV2` value;
- strict Draft 2020-12 schema validation after exact schema-identity checking;
- deterministic cross-object invariant validation;
- duplicate-key-rejecting JSON parsing;
- canonical JSON serialization and SHA-256 integrity;
- explicit sealing of an already constructed candidate.

The validator does not load the schema from disk, parse a source document,
recover a table, infer a row role, repair a candidate, render a view, write an
artifact or call a model. Construction belongs to the factories above;
acceptance belongs only to the validator.

Public `validate`, `parse_json` and `seal` reject any
`REVIEWED_SOURCE_BOUND` input. Only the Managed PDF builder's private sealing
seam may provide the exact reviewed plan created from the same-call recovery;
the validator compares receipt/proposal/raster/role refs and reviewed rows
exactly before sealing. This is a call-graph boundary, not a token or a second
public evidence contract.

The legacy no-scope path rejects any returned `source_bound_*` transport,
prebuilt reviewed record or reviewed row/entry origin before assembly. The
scoped path permits promotion only when its own public call received non-empty
raw requests and its local LogicalRow call produced the exact reviewed plan.
The reviewed plan is non-empty only for an actually accepted `PRESENT` leading
structure. Merely obtaining a `BOUND` receipt is not reviewed role authority.

Schema identity is both the exact `$id` and the SHA-256 of canonical schema
JSON (`ensure_ascii=false`, sorted keys, separators `(",", ":")`, finite
numbers only). The pinned v2 schema hash is
`02a60ac6d143bf6c2364c74a32a4eabc9d4852aaef5bd8b7bdc987ed81fb423a`.
A schema edit that preserves `$id` still fails closed. The validator receives
the schema object explicitly; no factory or builder may weaken or replace this
authority.

## 4. Information partition and top level

The information partition is fixed:

```json
{
  "CONTENT": ["/metadata", "/blocks/*/content"],
  "PROVENANCE": ["/source", "/anchors", "/relations"],
  "CONTROL": [
    "/information_partition",
    "/blocks/*/restoration",
    "/quality"
  ],
  "PRIVATE_SOURCE": [
    "/document_id",
    "/source/artifact",
    "/anchors/*/locator/private_locator",
    "/blocks/*/content/private_artifact",
    "/geometry_evidence",
    "/source_word_ownership"
  ]
}
```

Every v2 document has exactly these top-level fields:

| Field | Responsibility |
| --- | --- |
| `schema_version` | Exact v2 identity. |
| `document_id` | Stable internal diagnostic identity. The PDF builder derives it from the required private source-artifact identity. It is classified `PRIVATE_SOURCE`, excluded from safe diagnostics and never rendered into LLM Document View v2. |
| `information_partition` | Fixed content/provenance/control/private routing. |
| `source` | Private source binding, checksum, format, part count and producer identity. |
| `metadata` | Status-bearing document passport. |
| `anchors` | Typed source locators. |
| `geometry_evidence` | Private secondary evidence registry. |
| `source_word_ownership` | Private exact-once table-word accounting registry. |
| `blocks` | Sole contiguous zero-based document reading order. |
| `relations` | Explicit relations not expressible by order alone. |
| `quality` | Status, counters, issues and accounted losses. |
| `integrity_sha256` | SHA-256 over canonical JSON without this field. |

Unknown top-level properties fail. The v1 source, metadata, anchor, non-table
block, quality and canonical-JSON meanings remain stable unless the v2 schema
states a stricter invariant below.

## 5. Ordered document blocks

`blocks[]` remains the only primary document reading order. Block ordinals
are exactly `0..n-1`. The closed block taxonomy remains:

```text
HEADING PARAGRAPH LIST TABLE NOTE VISUAL BOUNDARY UNKNOWN
```

Every block has a unique ID, ordinal, typed content, one or more source-anchor
IDs, restoration state and issue IDs. A TABLE owns its words; those words must
not also be emitted as paragraph content. Relations never replace reading
order.

## 6. TABLE content

Every TABLE content object contains exactly:

| Field | Meaning |
| --- | --- |
| `information_class` | Exactly `CONTENT`. |
| `table_id` | Document-unique logical-table ID. |
| `completeness_status` | `COMPLETE`, `PARTIAL`, `BLOCKED` or `UNKNOWN`. |
| `ordered_rows` | Non-empty canonical logical-row sequence. |
| `logical_columns` | Optional logical-column model; an empty array means no columns were proven. |
| `source_parts` | Non-empty ordered physical-source partition of the row sequence. |
| `relations` | Relation-ID references into the document relation ledger. |
| `issues` | Issue-ID references into `quality.issue_ledger`. |
| `known_gap_ids` | Loss-ID references into `quality.loss_ledger`. |

`relations` and `issues` are references, not duplicate ledgers.
`ordered_rows`, not a cell matrix, is the TABLE authority.

## 7. Logical Row

A logical row contains:

```json
{
  "row_id": "row_example",
  "ordinal": 0,
  "role": "GROUP_HEADER",
  "role_origin": "DETERMINISTIC_DERIVED",
  "nesting_level": 0,
  "parent_row_id": null,
  "entries": [
    {
      "entry_id": "entry_example",
      "ordinal": 0,
      "kind": "LABEL",
      "text": "Assets",
      "origin": "SOURCE_EXPLICIT",
      "column_binding_status": "NOT_APPLICABLE",
      "logical_column_id": null,
      "covers_logical_column_ids": [],
      "source_anchor_ids": ["anchor_example"],
      "geometry_evidence_ids": [],
      "issue_ids": []
    }
  ],
  "source_anchor_ids": ["anchor_example"],
  "geometry_evidence_ids": [],
  "issue_ids": []
}
```

Row IDs are unique across the document, and each row belongs to exactly one
TABLE. Row ordinals inside a table are exactly `0..n-1`.

Allowed roles:

```text
TABLE_TITLE
COLUMN_HEADER
GROUP_HEADER
DATA
SUBTOTAL
TOTAL
NOTE
CONTINUATION_HEADER
UNKNOWN
```

Roles describe observable document structure, not financial type or expected
business meaning. `MODEL_PROPOSED` is forbidden for `role_origin`.
`UNKNOWN` is valid only with an explicit issue.

`REVIEWED_SOURCE_BOUND` is the honest origin for `TABLE_TITLE`,
`COLUMN_HEADER` and `DATA` rows accepted through a same-call visual scope
receipt. Their entries carry the same origin. The validator requires their
anchor word refs in matching source-part evidence; relabeling them
`DETERMINISTIC_DERIVED` fails closed.

`nesting_level=null` requires an issue. A non-null parent:

- resolves to an earlier row in the same TABLE;
- identifies a `GROUP_HEADER`;
- has a known nesting level exactly one less than its child.

A row with no proven parent keeps `parent_row_id=null`. If its nonzero
nesting implies an unresolved parent, the row must carry an issue. The producer
must not guess the parent from financial meaning.

## 8. Row Entry

Each row contains one or more entries in exact `0..n-1` order. Entry counts
may differ between rows. An entry contains:

- document-unique `entry_id`;
- `ordinal`;
- `kind`: `LABEL`, `VALUE`, `UNIT`, `MARKER`, `NOTE` or `UNKNOWN`;
- source-preserving `text`;
- provenance `origin`;
- `column_binding_status`;
- required nullable `logical_column_id`; null means there is no direct logical
  column binding;
- required ordered `covers_logical_column_ids` array; use an empty array when
  the entry does not visually cover logical columns;
- source-anchor, geometry-evidence and issue refs.

`MODEL_PROPOSED` entry origin is forbidden. Null text is allowed only for an
explicit `UNKNOWN` entry with an issue; it is not a padding mechanism.
Whitespace, values, currency markers and dates must not be silently repaired
or normalized into invented source content.

## 9. Optional logical columns

`logical_columns` is required as an array so serialization is deterministic,
but the model itself is optional. Use an empty array when repeated observable
alignment and header evidence do not prove columns.

When columns exist:

- IDs are unique across the document and ordinals are `0..n-1`;
- every column has private geometry evidence;
- `header_path` contains only entries from `COLUMN_HEADER` or
  `CONTINUATION_HEADER` rows;
- every `header_path` entry has `column_binding_status=BOUND` and either binds
  directly to the target column or explicitly covers it; header entries follow
  document row order;
- an empty unresolved `header_path` carries an issue;
- column names or bindings must not be inferred from amounts or domain
  expectations.

One covering header entry may therefore appear in the paths of multiple
columns. A `GROUP_HEADER` entry may cover columns, but its row role does not
make it a valid `header_path` entry.

Entry binding is explicit:

| Status | `logical_column_id` | `covers_logical_column_ids` |
| --- | --- | --- |
| `BOUND` | May be null. A non-null ID resolves in the same TABLE. | May be empty. At least one of direct binding or coverage must be present. |
| `NOT_APPLICABLE` | Must be null. | Must be empty. |
| `UNKNOWN` | Must be null. | Must be empty, and the entry must reference a resolving issue. |

`covers_logical_column_ids` records visual coverage only. A non-empty array
contains at least two distinct existing columns in `logical_columns[].ordinal`
order. When both fields are present, `logical_column_id` equals the first,
leftmost covered logical column (`covers_logical_column_ids[0]`). An entry in a
`SUBTOTAL` or `TOTAL` row with coverage must always carry that direct leftmost
binding. Header and group spanners may instead use `BOUND`, a null direct
binding and non-empty coverage.

Non-empty coverage requires object-local geometry support: at least one
referenced `ENTRY_REGION`, `VISUAL_COVERAGE` or `COLUMN_ALIGNMENT` evidence
record overlaps the entry's source-anchor scope. Coverage never creates
synthetic empty entries for the columns it crosses.

## 10. Source parts and continuation

`source_parts[]` partitions all table rows exactly once, contiguously and in
order. Part IDs are document-unique; ordinals are `0..n-1`; page numbers are
strictly increasing; each region anchor resolves and matches its PDF page.
Every part has private table-region geometry evidence.

An affected part may additionally contain
`reviewed_source_bound_evidence`: `origin=REVIEWED_SOURCE_BOUND`, receipt ref,
proposal/raster-manifest SHA-256 values and separate title/header/body
source-word refs. Ordinary anchors still preserve the direct source words;
this reviewed record neither replaces nor invents their text.

One part uses exactly:

```text
SINGLE
```

and has no continuation evidence. Multiple parts use exactly:

```text
START, CONTINUATION..., END
```

and every part carries continuation evidence. Repeated headers remain logical
rows with role `CONTINUATION_HEADER`; they are neither dropped nor silently
used to create a second table. Cross-block continuation may additionally use a
validated `CONTINUATION_OF` relation.

## 11. Private geometry evidence

Geometry is a secondary evidence layer, never canonical table meaning. The
top-level registry is `PRIVATE_SOURCE`; every item has a unique ID, kind,
origin, source anchors, present private artifact, checksum and issue refs.

Allowed evidence kinds are:

```text
TABLE_REGION ROW_BAND ENTRY_REGION BASELINE INDENTATION COLUMN_ALIGNMENT
HORIZONTAL_RULE VERTICAL_RULE VISUAL_COVERAGE CONTINUATION UNKNOWN
```

Evidence may support boundary, row membership/order, indentation, entry
grouping, logical-column alignment, continuation and visual coverage.
`MODEL_PROPOSED` evidence is forbidden. Every evidence item must be referenced
by a row, entry, logical column or source part; orphan evidence fails.

Geometry references are object-local and kind-compatible. A row or entry may
reference evidence only when at least one evidence anchor is also carried by
that row or entry. Column references use column-alignment evidence. Every
source part references `TABLE_REGION` evidence anchored to its region anchor;
continuation references use `CONTINUATION` evidence anchored to that same
region. PDF row and entry anchors must remain on the page assigned to their
source part.

Rows and entries may have no geometry refs when their structure is proven
through other anchored observations. Source-part regions and any created
logical columns require geometry. Coordinates, bbox, parser traces, private
refs, confidence scores and evidence checksums must not enter LLM Document
View v2.

## 12. Exact-once source-word ownership

`source_word_ownership[]` is a private registry for every word inside a
recovered TABLE region. Each unique word ID has exactly one status:

- `OWNED`: one entry in the same TABLE owns the word;
- `PROVEN_DUPLICATE`: the word points to a canonical `OWNED` word with the
  same owner entry in the same TABLE;
- `UNRESOLVED`: no owner was proven, both owner fields are null and an issue
  is required.

Every entry must own at least one canonical source word. Every ownership row
uses its own unique word-level `source_anchor_id`, and that anchor must also be
bound to the owner entry. Reusing one source anchor for two ownership rows,
cross-table ownership, multiple registry rows for one word, duplicate chains
and self-duplicates fail.

For TABLE entries, the set of bound word-level anchors is exactly the set of
non-`UNRESOLVED` ownership anchors after excluding the table-part region
anchors. One word anchor cannot be bound to two entries, and removing an
ownership row while leaving its word anchor on an entry fails validation.

For the DOC6 PDF contour, every ownership anchor is a PDF word locator with a
non-empty `source_block_ref` and a four-coordinate bbox. `source_word_id` is
exactly `source_word_` plus the first 24 hex characters of SHA-256 over
canonical JSON array `[locator.source_block_ref]`. This independently binds the
registry identity to the claimed source word instead of trusting a free-form
ID.

A table with any unresolved word must be `BLOCKED`. DOC6 acceptance is
stricter than schema expressibility and requires:

```text
UNRESOLVED_TABLE_WORDS_TOTAL = 0
MULTIPLE_ENTRY_WORD_OWNERS_TOTAL = 0
TABLE_WORDS_DUPLICATED_AS_PARAGRAPH_TOTAL = 0
```

## 13. Relations and local uncertainty

Relation endpoints always identify an existing block and may additionally
identify a row and then an entry. An entry endpoint without its row is invalid.
Row and entry targets must belong to the identified TABLE block. TABLE
`relations` refs must name a relation incident to that block.

Local uncertainty is preferable to a flattened UNKNOWN block when boundary,
row order and values are proven. Unknown role, nesting, parent, header path or
column binding must remain local and issue-bound. A `COMPLETE` TABLE rejects
local unknown structure and known gaps.

## 14. Quality, canonical JSON and integrity

Document quality remains `COMPLETE`, `PARTIAL` or `BLOCKED`.
`unaccounted_context_loss_total` is exactly zero. Counters agree with the
block inventory and ledgers. A complete document rejects incomplete table
state; partial rejects blocking loss; blocked requires a blocking loss.

Canonical bytes are UTF-8 JSON with `ensure_ascii=false`, sorted keys and
separators `(",", ":")`. `integrity_sha256` is computed after removing only
that top-level field. Duplicate JSON keys are rejected before validation.
All numeric values are finite; JSON `NaN`, positive infinity and negative
infinity are rejected by parse, validation and sealing. `validate()` never
repairs or reseals; `seal()` is explicit.

## 15. Validation boundary

The sole validator checks schema plus at least:

- format, source-part and anchor consistency;
- unique block, table, row, entry, column, source-part, evidence, word,
  relation, issue and loss IDs;
- contiguous block, row, entry, column and source-part ordinals;
- row-parent order, role and nesting;
- entry/column binding, ordered header-path binding and visual-coverage
  evidence;
- exact source-part row partition, page-local anchors and continuation
  sequence;
- object-local, kind-compatible geometry evidence;
- exact-once word ownership, unique word anchors, deterministic anchor-to-word
  identity and entry coverage;
- relation endpoint ownership and table-local refs;
- issue, loss, anchor and geometry refs;
- absence of orphan geometry evidence;
- quality/status consistency and zero unaccounted context loss;
- exact canonical integrity.

Validation returns a deep-copied value and fails closed. Real-corpus recovery,
visual-gold parity and view parity are separate acceptance proofs; schema
validation alone does not establish them.

## 16. Scope

This contract authorizes only the inactive DOC6 path. It does not authorize:

- a product route or current packet change;
- provider calls or model qualification;
- LLM/VLM structure inference;
- changes to Managed Document v1;
- changes to generated bundles;
- financial classification or semantic repair;
- source-specific hardcoding by file, broker, page, safe ID or bbox.

```text
CANONICAL_TABLE_MODEL = ORDERED_LOGICAL_ROWS
RECTANGULAR_GRID_AUTHORITY = NONE
GEOMETRY_VISIBILITY = PRIVATE_SOURCE
FULL_SOURCE_INPUT_OWNER = FullSourceArtifactFactory.create
TABLE_RECOVERY_OWNER = LogicalRowTableFactory
CONTRACT_VALIDATOR_OWNER = ManagedDocumentContractV2Validator
PRODUCT_ACTIVATION = NOT_STARTED
PROVIDER_CALLS = ZERO
```
