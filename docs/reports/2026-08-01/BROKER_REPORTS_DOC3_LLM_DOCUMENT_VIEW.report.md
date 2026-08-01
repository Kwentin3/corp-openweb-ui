# Broker Reports DOC3 LLM Document View Closure Report

Status: `PASSED_INACTIVE`

Effective date: 2026-08-01

Base commit: `3282780c7fdf6548bbfabf6179c784971a3f4242`

Implementation commit: `6711587f0f5aa26843b8caff19d9b5f0317082ff`

Implementation merge commit: `ebe3d6a7e375ff97f0242c7ee5bfdd476d594500`

Implementation PR: `#251`

## 1. Result

DOC3 adds one inactive deterministic transformation:

```text
validated Managed Document v1
-> ManagedDocumentLlmViewFactory
-> broker_reports_llm_document_view_v1
```

The result is one UTF-8 tagged-text stream with a fixed trust header, compact
JSON-escaped values, exact block order and a strict end marker. It changes
representation only. It does not select, summarize, repair, classify, chunk,
retrieve, truncate or send document content to a model.

`ManagedDocumentLlmViewFactory` is the single renderer owner.
`ManagedDocumentLlmViewAuditor` is the single view-only auditor owner and uses
only the Python standard library. The auditor imports neither the renderer nor
the Managed Document validator.

## 2. Canonical format

The view begins and ends exactly as follows:

```text
BROKER_REPORTS_LLM_DOCUMENT_VIEW_V1
CONTENT_TRUST UNTRUSTED_SOURCE_DOCUMENT
DOCUMENT_BEGIN
...
DOCUMENT_END
END_BROKER_REPORTS_LLM_DOCUMENT_VIEW_V1
```

Every source-derived value is compact sorted JSON on one physical line. Quotes,
backslashes, tabs, newlines, Unicode, HTML, Markdown, JSON and renderer-like
markers remain data inside the JSON value and cannot create a delimiter.

The stream contains every status-bearing metadata field, the safe anchor
registry, every block in `blocks[].ordinal` order, relations, quality, issues
and the complete known-loss ledger. TABLE uses indexed JSON row arrays and
retains header hierarchy, row groups, markers, units, annotations, relation
IDs and gap IDs. UNKNOWN and unprocessed VISUAL blocks remain visible.

## 3. Receipt and field coverage

Each render creates a private
`broker_reports_llm_document_view_receipt_v1`. It binds input and output hashes,
size and token metrics, block/metadata/table coverage, and ordered per-item
relation/issue/loss coverage with view line ranges and projection hashes.

The sealed DOC1-to-DOC3 field-disposition authority allows only:

```text
RENDERED
RENDERED_AS_SAFE_POINTER
OMITTED_CONTROL_FIELD
OMITTED_PRIVATE_SOURCE_FIELD
OMITTED_REDUNDANT_WITH_EXACT_OWNER
```

The four real inputs exercised 737 concrete DOC1 paths. All 737 resolved to an
allowed disposition; `UNACCOUNTED_FIELD` and unaccounted render omissions are
zero.

## 4. Privacy boundary

The view structurally excludes source checksums, private artifact refs, local
paths, private locators, resolver/access context and provider payloads.
UNKNOWN/VISUAL records may expose only the boolean that a private source
artifact exists. Exact-value leakage guards, the repository privacy suite and
private human review passed.

Real views, receipts, checklists, comparisons and source values remain under
ignored private storage. Git contains only counts, sizes, hashes and statuses.

## 5. Real-corpus coverage

The same four private valid DOC2 Managed Documents were used. No DOC1 schema or
DOC2 builder byte changed.

| Metric | Input | Rendered | Omitted |
| --- | ---: | ---: | ---: |
| Managed Documents / views | 4 | 4 | 0 |
| Blocks | 131 | 131 | 0 |
| TABLE blocks | 6 | 6 | 0 |
| TABLE rows | 82 | 82 | 0 |
| TABLE cells | 467 | 467 | 0 |
| UNKNOWN blocks | 26 | 26 | 0 |
| VISUAL blocks | 9 | 9 | 0 |
| Relations | 0 | 0 | 0 |
| Issues | 35 | 35 | 0 |
| Known losses | 44 | 44 | 0 |

Primary block order was preserved. Invented content, filtering, truncation,
semantic selection and private-source rendering are all zero.

## 6. View sizes

| Safe ID | Bytes | Characters | Lines | Whitespace tokens | Reference tokens |
| --- | ---: | ---: | ---: | ---: | ---: |
| `real_pdf_1` | 10,771 | 10,768 | 206 | 844 | 10,771 |
| `real_pdf_2` | 22,499 | 22,428 | 236 | 2,005 | 22,499 |
| `real_pdf_4` | 95,033 | 94,821 | 841 | 8,513 | 95,033 |
| `real_pdf_5` | 161,367 | 153,155 | 1,387 | 6,412 | 161,367 |
| Total | 289,670 | 281,172 | 2,670 | 17,774 | 289,670 |

The exact offline reference tokenizer is
`broker_reports_utf8_byte_bpe_v1` using pinned `tiktoken==0.12.0`. It has an
in-memory byte vocabulary and makes no network or external vocabulary read.
Its count is deliberately model-independent and does not establish a model
context window.

## 7. Size partition

| Category | Bytes | Share |
| --- | ---: | ---: |
| Metadata | 15,813 | 5.4590% |
| Textual blocks | 29,706 | 10.2551% |
| Tables | 84,830 | 29.2850% |
| UNKNOWN blocks | 80,258 | 27.7067% |
| VISUAL blocks | 4,174 | 1.4410% |
| Relations | 0 | 0.0000% |
| Issues | 16,134 | 5.5698% |
| Loss ledger | 26,097 | 9.0092% |
| Renderer labels/delimiters | 32,658 | 11.2742% |

The receipt also records size by page and by block type. Category bytes sum
exactly to the complete view bytes.

## 8. Three-pass parity

For every real Managed Document, three isolated process modes ran:

1. Pass A received only Managed Document and sealed its complete projection.
2. Pass B received only LLM View and used the independent auditor.
3. Pass C received only the two sealed checklists.

All 52 dimensions matched: document passport, metadata, anchors, block order,
block content, tables, unknowns, visuals, relations, issues, losses, scalar
value hashes and quality. Four of four documents reached full parity. Critical
mismatches and noncritical findings are zero.

## 9. Replay and persistence

Each real document was processed twice. Six private files per document were
compared across runs: Managed Document copy, view, render receipt, Pass A
checklist, Pass B checklist and Pass C comparison. All 24 hashes matched.

Each render persisted the private view and receipt through the scoped
ArtifactStore types and read both back through ArtifactResolver. Across both
runs this produced 16 exact readbacks. DOC3 artifact types were removed from
the global admitted set when each offline store operation ended.

## 10. Review and validation

The isolated implementation review found one material issue before commit:
relations, issues and losses were initially counted only in aggregate receipt
coverage. It was corrected to ordered per-item coverage with line ranges and
source/rendered projection hashes. The complete proof was regenerated after
the fix. A formal review COMMENT on PR #251 records the reviewed boundaries and
the correction; it does not claim approval by a separate human reviewer.

Local exact implementation validation:

```text
full service suite = 2379 passed, 5 pre-existing conditional skips
DOC1-DOC3 focus = 73 passed
architecture/privacy focus = 62 passed, 1 unrelated conditional skip
KT2/KT2.1/artifact/bundle regression focus = 75 passed
privacy and bundle closeout = 34 passed
changed-file Ruff = PASSED
compileall = PASSED
Draft 2020-12 schemas = PASSED
git diff --check = PASSED
generated tracked bundle diff = 0
```

GitHub Actions run `30697392070` completed `SUCCESS` on exact head
`6711587f0f5aa26843b8caff19d9b5f0317082ff`. Its generated assets, generated
Function bundles, Ruff, anti-drift and focused Broker Reports steps all passed.
PR #251 merged as `ebe3d6a7e375ff97f0242c7ee5bfdd476d594500`.
The merge tree is byte-identical to the implementation commit tree.

## 11. Scope stop

DOC3 is inactive. It changes no prompt, valve, provider/model path, admission,
runtime product route, generated bundle or live state. It does not establish
PDF-to-LLM semantic equivalence, select a model, qualify a real model or start
product activation.

```text
DOC3_LLM_DOCUMENT_VIEW = PASSED
MANAGED_DOCUMENT_TO_LLM_VIEW = PROVEN
PDF_TO_LLM_SEMANTIC_EQUIVALENCE = NOT_STARTED
REAL_MODEL_QUALIFICATION = NOT_STARTED
PRODUCT_ACTIVATION = NOT_STARTED
DOC4 = NOT_STARTED
```
