# Broker Reports DOC3 LLM Document View Decision v1

Effective date: 2026-08-01

Status: accepted inactive implementation decision

Base commit: `3282780c7fdf6548bbfabf6179c784971a3f4242`

## Decision

`ManagedDocumentLlmViewFactory` is the single renderer owner for a validated
Managed Document v1. It produces one canonical
`broker_reports_llm_document_view_v1` UTF-8 tagged-text stream and one private
coverage receipt. The renderer changes form only: it performs no selection,
summarization, classification, repair, extraction or model call.

`ManagedDocumentLlmViewAuditor` is the single independent view-only owner. It
uses only the Python standard library and the public tagged-text contract. It
imports neither renderer nor Managed Document validator.

## Boundary and format

Every source-derived value is compact canonical JSON on one physical line.
Therefore arbitrary quotes, backslashes, newlines, Unicode, HTML, Markdown,
JSON and renderer-like markers cannot create delimiters. The fixed header and
end marker establish a strict trust and framing boundary.

Metadata is status-bearing; anchors are reduced to safe pointers; blocks remain
in exact ordinal order; TABLE rows use JSON arrays; UNKNOWN and VISUAL remain
visible; relations, issues and losses retain their original order. Private
artifact refs, source checksums, paths and access context never enter the view.

## Field coverage

`BROKER_REPORTS_DOC1_TO_DOC3_VIEW_COVERAGE.v1.json` is the machine authority.
Each concrete DOC1 input path resolves to one allowed disposition and exact
owner. The four real documents exercised 737 concrete paths with zero
unaccounted fields.

## Tokenizer and size policy

The reference tokenizer is `broker_reports_utf8_byte_bpe_v1` on pinned
`tiktoken==0.12.0`. Its 256-byte vocabulary is constructed in memory, requires
no network or external vocabulary and yields exact deterministic UTF-8 counts.
It is deliberately model-independent. No model context-window claim is made;
model-specific counting remains DOC4 work.

The renderer always produces the full view. There is no truncation, chunking,
retrieval, RAG, sampling, row limiting or semantic filtering.

## Real-corpus result

The same four private valid DOC2 Managed Documents produced four views:

```text
blocks input/rendered = 131/131
tables input/rendered = 6/6
table rows input/rendered = 82/82
table cells input/rendered = 467/467
unknown blocks input/rendered = 26/26
visual blocks input/rendered = 9/9
issues input/rendered = 35/35
known losses input/rendered = 44/44
```

The views total 289,670 UTF-8 bytes and reference tokens. The largest view is
161,367 reference tokens. All 24 replay files matched across two independent
runs.

## Parity result

For each real document:

1. Pass A read only Managed Document;
2. Pass B read only LLM View through the independent auditor;
3. Pass C read only two sealed checklists.

All 52 comparison dimensions match. Four documents have full parity; critical
and noncritical findings are zero.

## Architecture and non-goals

The renderer is not imported by product actions, Gate 2 or generated bundles.
The CLI is invoked as a standard module from the service root and uses no
workspace path shim. Its scoped private artifact types are admitted only during
offline ArtifactStore writes and are removed afterward.

DOC1 schema and DOC2 builder are byte-identical to the base. DOC3 makes no
provider call, prompt, valve, admission, bundle, product-route, fallback, live,
Gate 2, Semantic Pack or Type-First change.

```text
MANAGED_DOCUMENT_TO_LLM_VIEW_PARITY = PASSED
PDF_TO_LLM_SEMANTIC_EQUIVALENCE = NOT_STARTED
REAL_MODEL_QUALIFICATION = NOT_STARTED
PRODUCT_ACTIVATION = NOT_STARTED
```

DOC4 is not started.
