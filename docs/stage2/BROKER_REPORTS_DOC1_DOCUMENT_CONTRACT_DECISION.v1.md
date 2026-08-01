# Broker Reports DOC1 Document Contract Decision v1

Date: 2026-08-01

Status: `ACCEPTED_INACTIVE`

Base commit: `7cbb62f39915fd1499aeb009aac6a41bab0accb0`

## 1. Current problem and risk

DOC0 proved that no current artifact keeps headings, paragraphs, tables, notes
and page boundaries in one source order. The first irreversible downstream
loss occurs at:

```text
FullSourceArtifactBuilder._build_pdf_document
-> PdfLayoutUnitBuilder._build_page_units
```

The next contract therefore needs to preserve one document without making a
normalizer, model or graph database part of the contract authority. The active
risk is silent loss: an unsupported or unreadable element must not disappear
behind a successful status.

DOC0 is accepted as input. This decision does not repeat its pipeline audit.

## 2. Domain and ownership map

| Responsibility | DOC1 owner | Boundary |
| --- | --- | --- |
| Document DTO, enums, validation, canonical bytes and integrity | `managed_document_contracts.py` | Global Gate 1 inactive representation contract |
| Machine schema | `BROKER_REPORTS_MANAGED_DOCUMENT.v1.schema.json` | Draft 2020-12, strict closed properties |
| Source parsing and block construction | Future DOC2 adapter | Not started |
| Future model-visible projection | Future DOC3 renderer | Not started |
| Persistence | Existing ArtifactStore boundary, only after a later goal authorizes an adapter | No DOC1 writes |
| Financial meaning | Existing Global Gate 2 authorities | Forbidden in DOC1 |
| Product route, provider transport and activation | Existing product/provider owners | Unchanged and unreachable |

The new contract owner is necessary because no existing owner represents a
universal whole document. It does not duplicate `FullSourceArtifactFactory`,
document memory, table materialization, Semantic Pack, Packet, Choice,
ArtifactStore or provider responsibilities.

## 3. Decision

Use:

```text
Document
-> one ordered blocks[] stream
-> optional explicit relations[]
-> typed source anchors
-> issue and loss ledgers
```

`blocks[]` is the canonical reading order. Relations are secondary and express
only information that a linear sequence cannot safely carry: section
membership, captions, notes, footnotes and continuation/same-object links.

The choice is intentionally smaller than an ordered graph. It directly closes
the proven table/text interleaving gap, stays inspectable as JSON, and leaves
unknown elements in place without requiring graph traversal.

## 4. Boundary contracts

### 4.1 Content boundary

Document metadata and typed block contents are `CONTENT`. Raw source text is
retained; summaries and financial interpretation are forbidden.

### 4.2 Provenance boundary

`source`, `anchors` and `relations` are `PROVENANCE`. Source-specific PDF,
HTML, CSV and spreadsheet locators remain typed but do not define shared
document meaning.

### 4.3 Control boundary

Restoration state, issues, losses, counts and terminal quality are `CONTROL`.
No context loss may remain outside the ledger.

### 4.4 Private-source boundary

Original files, images and private locators use opaque `PRIVATE_SOURCE` refs
and checksums. Safe fixtures contain no filename, filesystem path, customer
value or real artifact ref.

### 4.5 Table boundary

The existing `description + rows` model remains the exact inner table content.
DOC1 wraps it in one ordered TABLE block and adds optional logical annotations,
source anchors, relations and loss refs. It does not promote physical geometry
to truth.

## 5. Unknown and loss policy

Unknown content is data, not a validation failure:

- `UNKNOWN` block preserves raw text and/or private artifact;
- unknown heading level, list nesting, metadata, relation, table header/group,
  unit or cell state uses an explicit status;
- `MODEL_PROPOSED` remains distinct from `SOURCE_EXPLICIT`;
- missing source content enters the loss ledger;
- a blocking loss makes the document `BLOCKED`;
- no artifact may set `unaccounted_context_loss_total` above zero.

No generic extension field can hide an unrepresented DOC0 facet.

## 6. Alternatives rejected

### Flat text

Rejected because it cannot keep tables, unknown elements, source anchors,
notes, footnotes, boundaries and explicit loss accounting as addressable
objects.

### Graph-first document

Rejected for v1 because source reading order would require traversal and the
MVP does not need graph storage, queries or graph algorithms. Explicit
relations cover the small set of non-linear relationships.

### Existing source units as the document

Rejected because DOC0 proved their table-first partition loses original
interleaving and their scope does not express headings, notes, continuation or
unknown elements as one document.

### Existing logical table as the document

Rejected because it is a bounded table transcription, not surrounding document
context. Its `description + rows` core is reused only inside TABLE.

## 7. Implementation slices

1. Define the strict universal JSON schema and one inactive Python owner.
2. Add canonical serialization, integrity and semantic cross-reference checks.
3. Map all 53 DOC0 facets to contract fields, unknown policy and loss policy.
4. Add synthetic safe fixtures for ordinary PDF shape, unknown structure,
   continuation/footnote, CSV, XLSX and HTML.
5. Add focused behavioral and architecture tests.
6. Update current-state and evidence documents only after implementation merge.

Each slice is independently inspectable and introduces no product entrypoint.

## 8. Validation and acceptance surface

Focused tests assert schema/Python parity, all safe fixtures, unknown retention,
metadata state rules, block order, relation endpoints, duplicate IDs, table
core retention, cell annotations, empty/unreadable distinction, continuation,
footnotes, typed anchors, ledger/status consistency, canonical hash tampering,
all 53 DOC0 facets, financial-type absence, provider/product isolation,
generated-bundle byte parity and fixture privacy.

Repository validation additionally requires existing KT2, KT2.1 and DOC0
state checks, full service suite, changed-file Ruff, compileall,
`git diff --check` and zero generated-bundle diff.

## 9. Risks and controls

| Risk | Control |
| --- | --- |
| New module becomes a parser or second Gate 1 route | No source read API, no product import, no entrypoint and architecture tests. |
| Model proposal is presented as source fact | Closed origin enum plus mandatory source evidence for `SOURCE_EXPLICIT`. |
| Generic metadata hides missing facets | No free-form extension object; named additional metadata remains status-bearing. |
| Optional table annotations become physical truth | Only logical indexes/ranges are allowed; physical geometry claims are forbidden. |
| Unknown structure is dropped | UNKNOWN block requires retained text or private artifact. |
| Partial result looks complete | Ledger counters and terminal status are validator-bound. |
| Cross-platform hash drift | Canonical UTF-8 JSON is independent of repository line endings. |
| Synthetic proof is mistaken for parser proof | Fixture policy and `REAL_CORPUS_GAP=TRUE` are explicit. |

## 10. DOC0 coverage decision

The machine matrix
`BROKER_REPORTS_DOC0_TO_DOC1_CONTEXT_COVERAGE.v1.json` maps the exact 53 DOC0
IDs in source order.

```text
REPRESENTED = 51
REPRESENTED_AS_UNKNOWN = 2
REPRESENTED_IN_LOSS_LEDGER = 0
DEFERRED_WITH_EXPLICIT_BLOCKER = 0
DOC0_CONTEXT_FACETS_UNACCOUNTED_TOTAL = 0
```

Every row still includes a loss policy. A zero count for
`REPRESENTED_IN_LOSS_LEDGER` means the contract has a direct representation;
it does not mean a normalizer may omit the ledger when actual source content is
lost.

## 11. Architecture checks

1. One owner: `managed_document_contracts.py`.
2. The owner imports no parser.
3. No parser or product route imports the owner.
4. Generated Function bundles exclude the owner and rebuild byte-exact.
5. No product or CLI entrypoint exists.
6. No provider entrypoint/import exists.
7. Canonical financial type IDs are absent.
8. Semantic Pack is not imported or depended on.
9. Legacy pipeline code is unchanged.
10. Existing fallbacks are unchanged.
11. DOC2, DOC3 and DOC6 are not started.
12. `description + rows` exists only inside TABLE content.
13. Physical table geometry is not canonical truth.
14. All 53 DOC0 facets are accounted.

## 12. Non-goals and deferred work

DOC1 does not create or change:

- PDF, HTML, CSV, XLSX or XLS normalization runtime;
- `PdfLayoutUnitBuilder` or legacy splitting;
- fallback behavior;
- LLM-friendly rendering;
- model/provider calls or qualification;
- ArtifactStore product writes;
- Gate 1/Gate 2 product routes;
- Semantic Pack, Type-First or financial materialization;
- Gate 3/Gate 4 behavior;
- MCP, SQL, RAG, retrieval or importance ranking;
- generated bundles or live state.

DOC2 must choose and prove a real PDF construction policy against this accepted
contract. DOC3 must separately define the model-visible projection from the
explicit information partition. Neither begins here.

## 13. Decision status

```text
PRIMARY_DOCUMENT_MODEL = ORDERED_BLOCK_STREAM
EXPLICIT_RELATIONS = PRESENT
UNKNOWN_BLOCK = SUPPORTED
UNKNOWN_METADATA = SUPPORTED
SOURCE_PROVENANCE = PRESENT
LOSS_LEDGER = PRESENT
UNACCOUNTED_CONTEXT_LOSS_ALLOWED = 0
CURRENT_TABLE_CORE_REUSED = TRUE
PHYSICAL_TABLE_RECONSTRUCTION = NOT_REQUIRED
PDF_NORMALIZER = NOT_STARTED
LLM_FRIENDLY_RENDERER = NOT_STARTED
REAL_MODEL_QUALIFICATION = NOT_STARTED
PRODUCT_ACTIVATION = NOT_STARTED
```
