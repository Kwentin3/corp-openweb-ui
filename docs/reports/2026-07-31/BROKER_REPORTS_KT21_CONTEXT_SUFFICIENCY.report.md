# Broker Reports KT2.1 — Context Sufficiency Closure

Date: 2026-07-31

Status: `PASSED`

## 1. Problem and decision

The KT2 mechanical path could safely restore one opaque Pack-backed option,
but a unique option did not prove that the model-visible source context was
semantically sufficient. Values such as amount, date, and currency can describe
many different financial facts. KT2.1 therefore adds an inactive, deterministic
bounded-context projection and a fail-closed guard before typed materialization.

The simulated model decides only which of the prebound opaque Type Card options
is plausible for a source unit. It does not create values, canonical IDs, source
refs, or context. Deterministic code retains all canonical authority.

## 2. Current-context audit

Three real row-window packages from the same private source family were audited
through privacy-safe structural copies. All three had the same facet availability.
Exact customer values and raw refs stayed under ignored `local/` storage.

| Facet | Original document | Gate 2 package | Source unit | Old model request | Lost |
| --- | ---: | ---: | ---: | ---: | ---: |
| document type/role/title/issuer | present | absent | absent | absent | yes |
| reporting period/account type/language | present or possible | absent | absent | absent | yes/unknown |
| section path/table title/group label | present or possible | absent | absent | absent | yes/unknown |
| raw headers | present | `unknown` | `unknown` | technical substitute | yes |
| normalized column roles | not source-native | absent | absent | weak placeholder | yes |
| target row | present | present | present | partially visible | partial |
| parent/previous/next rows | present or possible | parent table only | absent | absent | yes |
| footnote/continuation | possible | absent or empty | absent or empty | absent | yes/unknown |
| extraction/reconstruction quality | n/a | present | present | absent | yes |
| missing/truncated state | n/a | partial | partial | absent | yes |
| unresolved issues | n/a | present | absent | absent | yes |

`CURRENT_CONTEXT_SUFFICIENCY = INSUFFICIENT`

The earlier public fixture also replaced the first semantic row label with a
numeric value. It could not remain a positive typed case.

## 3. Bounded semantic context

`Gate2BoundedSemanticContextFactory` is the single subordinate builder. It is
not a product owner and has no provider or product entrypoint. It selects only
by same document/table identity, row ordinal, and explicit parent, footnote, or
continuation links. It cannot inspect Type Cards, return a canonical type, form
a semantic shortlist, use regex/synonyms, embeddings, RAG, or model retrieval.

The versioned request layer is
`broker_reports_bounded_semantic_context_v1` and contains:

1. document context;
2. section context;
3. table context with raw headers and normalized roles together;
4. target unit;
5. local structural context;
6. quality, restrictions, missing facets, and truncation state.

Budgets are two previous and two next rows, two parents, four group labels, four
footnotes, section depth six, 2,000 text characters per bounded field, 24,000
request characters, and 32,000 UTF-8 request bytes. Truncation is explicit and
blocks typed output when a required facet is affected.

## 4. Model-visible requests

The exact privacy-safe full request, all Type Cards, simulated response, sealed
binding, guard decisions, and hashes are committed in
`tests/fixtures/kt21_bounded_semantic_context_trace.safe.json`.

The first full-context source unit exposes this safe semantic structure:

```json
{
  "source_unit_key": "u01",
  "bounded_semantic_context_hash": "61a906080e72465f9dca233c8e85554f411155de16d28290deda8c409fa9676c",
  "document_context": {
    "document_type": "broker_report",
    "document_role": "primary_statement",
    "document_title": "Synthetic quarterly statement",
    "issuer_role": "synthetic_issuer",
    "reporting_period": "2026-Q2",
    "account_type": "synthetic_account",
    "language": "en",
    "statement_scope": "synthetic_statement_scope"
  },
  "section_context": {
    "section_path": ["Statement", "Totals"],
    "table_title": "Synthetic statement metrics",
    "group_labels": ["Reported metrics"],
    "related_notes": ["Synthetic note"]
  },
  "table_context": {
    "raw_headers": ["Line item", "Amount", "As of date", "Currency"],
    "normalized_column_roles": ["source_label", "amount", "as_of_date", "currency"],
    "header_confidence": "high",
    "table_quality": "high"
  },
  "target_unit": {
    "raw_cells": [["Synthetic printed total", "203.00", "2026-06-30", "USD"]],
    "visible_labels": ["Synthetic printed total"],
    "row_role": "fact_candidate",
    "row_ordinal": 1
  },
  "quality_and_restrictions": {
    "context_truncated": false,
    "missing_facets": [],
    "unresolved_issues": [],
    "financial_interpretation_allowed": true
  }
}
```

The values-only request retains only the target amount/date/currency evidence;
it has hash
`f5b2e10073f3d653a5022878b851439d40e046a88e036a35ef13d6867e81997c`.
It lacks `printed_label_evidence_ref` and `statement_scope`, so its decision is
`INSUFFICIENT` and `typed_allowed = false`.

## 5. Pack-backed requirements and guard

Every Type Card now includes `required_context_facets` and
`context_disqualifiers`. They are projected from the existing Semantic Pack's
required/identity roles, date/currency requirements, and ambiguity guidance.
Pack bytes, Pack hash, canonical meanings, and type count did not change.

`Gate2ContextSufficiencyGuard` allows typed materialization only when:

- the exact bounded context and source-package binding validate;
- the restored option is exact and unique;
- every selected Type Card facet is present and source-bound;
- context is not materially truncated or stale;
- no blocking unresolved issue or interpretation restriction exists;
- the existing validator accepts the decision.

Any failure produces the code-owned reason
`INSUFFICIENT_SEMANTIC_CONTEXT` and disposition
`unclassified_financial_input` before the existing sole materializer can create
a typed fact.

## 6. Ablation proof

| Variant | Context hash | Guard status | Typed |
| --- | --- | --- | ---: |
| values only | `f5b2e10073f3d653a5022878b851439d40e046a88e036a35ef13d6867e81997c` | insufficient | 0 |
| normalized roles only | `8cea7df44c7dff3df3a82b1676318e8782f58a3d0c052216cecbe2c1c5dccd7d` | insufficient | 0 |
| raw headers added | `1184aa32b8f1630bc4a175d9b2a82d6a3936a157268925429836a87d0684a3fa` | insufficient | 0 |
| section and table added | `6e5b5024b7818b8c4f76b06a8d642f33bd7c1180660f47d1905dafa17b7b4251` | insufficient | 0 |
| local structural context added | `9f089301e6573b19bc9cf2b2ae3b3854191e104979d8f4ed9f8fafc3bcf7174d` | insufficient | 0 |
| full bounded context | `61a906080e72465f9dca233c8e85554f411155de16d28290deda8c409fa9676c` | sufficient | 3 |

Removing context never changed unclassified/multiple/insufficient into a typed
or sufficient result. Truncated, cross-document, stale, source-mismatched, and
hash-tampered contexts are rejected.

## 7. Old case, typed and unclassified traces

All three old real-source units now terminate as:

```text
simulated singleton
→ INSUFFICIENT_SEMANTIC_CONTEXT
→ unclassified_financial_input
→ typed fact forbidden
```

The sufficient path is proven separately by three fixtures explicitly marked
`SEMANTICALLY_EQUIVALENT_SYNTHETIC_REDACTION`; all three reach the existing
validator and sole materializer as typed. The trace also declares
`REAL_PRIVATE_SOURCE`, `PRIVACY_SAFE_STRUCTURAL_COPY`, and
`DETERMINISTIC_CONTEXT_ABLATION` evidence classes without publishing private
bytes.

## 8. Replay and accounting

- exact replay status: `exact`;
- replay hash match: `true`;
- execution integrity hash:
  `86bd6c5cf6a680a204fd605e02b1bb3b2c146bc4adaca74b951793eb4029c0d0`;
- provider calls during replay: `0`;
- real packages/source units: `3 / 3`;
- context facets: `54` (`24` document, `12` section, `12` table, `6` local);
- ablation cases: `6`;
- old insufficient units unclassified: `3`;
- sufficient synthetic units typed: `3`;
- cross-document/hash-mismatch acceptances: `0 / 0`;
- semantic shortlists: `0`.

## 9. Tests, builders, CI, and post-merge verification

Before merge:

- KT2.1 focused: `15 passed`;
- KT2 + KT2.1: `33 passed`;
- architecture/current-state: `53 passed`;
- broader Gate 2/package/privacy/evidence: `107 passed`;
- builder matrix: `57 passed, 3 existing skipped`;
- full suite: `2306 passed, 5 skipped`;
- full suite with `--cache-clear`: `2306 passed, 5 skipped`;
- changed-file Ruff, compileall, managed builders, privacy/integrity, and
  `git diff --check`: passed;
- repository-wide Ruff exposed the already registered baseline of 264 old
  violations; changed Python files have zero Ruff violations;
- three Function bundle rebuilds: zero diff.

Hosted `Broker Reports CI` run `30650450798` passed all steps in 5m48s.

On exact implementation merge `a4ed4670d80d562fc866ae052d5a6e8d944e46d6`:

- KT2 + KT2.1 focused: `33 passed`;
- KT2.1 builder/replay/ablation check: passed;
- full suite: `2306 passed, 5 skipped, 0 failed, 0 errors`;
- three Function bundle rebuilds: zero diff;
- fresh read-only live verifier: passed;
- live/repository Function hashes: exact for all three;
- managed prompts: `12 / 12` exact;
- KT2.1 proof symbols in every live bundle: `0`;
- deploy required: `false`;
- provider calls/live changes: `0 / 0`.

## 10. Delivery and change accounting

- base commit: `f676370f1168555b57678c8874c2e0eb7917edd9`;
- implementation commit: `fbdb3247f6a7dbfbbaec2109e5e261dab093895e`;
- implementation PR: [#244](https://github.com/Kwentin3/corp-openweb-ui/pull/244);
- implementation merge: `a4ed4670d80d562fc866ae052d5a6e8d944e46d6`;
- implementation diff: 22 files, 6,072 insertions, 458 deletions;
- evidence merge: reported in the terminal response because a commit cannot
  contain its own future merge SHA;
- product routes, validators, materializers, replay owners, and canonical type
  count deltas: `0`;
- product reachability, model qualification, activation, provider calls, and
  live mutations: none.

## 11. Terminal status

```text
KT2_MECHANICAL_VERTICAL = PASSED
BOUNDED_SEMANTIC_CONTEXT = PASSED
CONTEXT_SUFFICIENCY_GUARD = PASSED
VALUES_ONLY_TYPED = 0
MISSING_REQUIRED_CONTEXT_TYPED = 0
CONTEXT_ABLATION_SAFETY = PASSED
REAL_MODEL_QUALIFICATION = NOT_STARTED
PRODUCT_ACTIVATION = NOT_STARTED
```
