# Broker Reports DOC3 LLM Document View Brief

Status: `PASSED_INACTIVE`

Effective date: 2026-08-01

## Decision

DOC3 now provides one deterministic, full-context, model-visible text
representation for a validated Managed Document v1:

```text
Managed Document v1 -> broker_reports_llm_document_view_v1
```

`ManagedDocumentLlmViewFactory` is the only renderer owner. The view is UTF-8
tagged text with compact JSON values, a fixed untrusted-source header, exact
block order and a strict end marker. It does not summarize, filter, chunk,
truncate, classify or call a provider.

## Proof

The same four valid real DOC2 Managed Documents produced four views:

```text
blocks = 131/131
tables = 6/6
table rows = 82/82
table cells = 467/467
UNKNOWN = 26/26
VISUAL = 9/9
issues = 35/35
known losses = 44/44
content omissions = 0
private source fields rendered = 0
```

Pass A used only Managed Document; Pass B used only LLM View through the
standard-library independent auditor; Pass C used only the two sealed
checklists. All 52 dimensions matched across four documents. Critical and
noncritical findings are zero.

Two complete runs compared 24 private files with zero hash mismatches. The
views total 289,670 UTF-8 bytes and exact reference tokens; the largest view is
161,367 reference tokens. The reference tokenizer is the offline
`broker_reports_utf8_byte_bpe_v1` implementation on `tiktoken==0.12.0`; it is
not a model context-window claim.

## Delivery

- Implementation: PR #251, commit
  `6711587f0f5aa26843b8caff19d9b5f0317082ff`.
- Implementation merge:
  `ebe3d6a7e375ff97f0242c7ee5bfdd476d594500`.
- GitHub Actions exact-head result: `SUCCESS`.
- Local full service suite: 2,379 passed, 5 pre-existing conditional skips.
- Generated bundle diff, provider calls, product-route changes and live changes:
  zero.

## Scope stop

DOC1 schema and DOC2 builder are unchanged. PDF-to-LLM semantic equivalence,
real model qualification, product activation and DOC4 remain `NOT_STARTED`.
