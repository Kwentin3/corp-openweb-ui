# Broker Reports Gate 2 Domain — GOAL 8 Risk-Based Benchmark

Date: 2026-07-26.

GOAL: `GOAL_8_RISK_BASED_BENCHMARK`.

Base revision:
`09e76058adfe6991f189e838f5524987da3afd8b`.

Branch:
`codex/broker-reports-gate2-domain-goal8-risk-benchmark`.

Authoring status:
`IMPLEMENTED_AND_VERIFIED_PENDING_AUTONOMOUS_REVIEW`.

## 1. Objective

GOAL 8 replaces exact-disposition-first benchmark acceptance with absolute
product-risk gates and separately visible quality metrics.

This change adds:

- a versioned risk benchmark contract;
- a frozen, hash-bound synthetic manifest;
- a generic deterministic scorer;
- one reproducible aggregate-only sealed result;
- positive and fail-closed tests for every hard blocker family;
- explicit generic structural pre-close cases;
- exact query-completeness tests.

It does not call or qualify a model, use an actual customer corpus, change
runtime routing, persist a domain, or mutate stage/production.

## 2. Absolute safety gates

The scorer fails the result when any count is nonzero:

```text
incorrect_typed_type
invented_value
invalid_ref
wrong_role
duplicate_or_cross_scope_binding
literal_or_provenance_loss
missing_terminal_owner
incomplete_query_response
```

No average, distribution, recall, precision, or unclassified-rate metric can
override a hard blocker. Tests introduce each risk independently and prove a
terminal `FAILED` result.

## 3. Safe under-typing

Typed reference → `unclassified_financial_input` is not an unsafe typed
misclassification when:

- every source value and exact literal is retained;
- required provenance remains present;
- no invalid, duplicate, or cross-scope binding exists;
- exactly one terminal owner exists.

The controlled sealed result intentionally contains one such case. It remains
safety-passing while recording:

```text
typed_reference_total=2
typed_correct_total=1
typed_recall=0.5
typed_to_unclassified_total=1
safe_under_typing_total=1
safe_under_typing_rate=0.5
```

This is a scorer-policy proof, not a measured model or production recall
claim.

## 4. Quality metrics and disposition observations

The synthetic controlled result records:

```text
classification_precision=1.0
unclassified_rate=0.666667
layout_noise_handling_rate=1.0
query_completeness_rate=1.0
```

Reference and candidate disposition distributions intentionally differ. The
safe result marks:

```text
primary_acceptance_gate=false
```

Therefore the safe under-typed case lowers recall and changes distribution
without being mislabeled as an unsafe typed error.

## 5. Generic structural pre-close

The deterministic helper consumes only:

```text
source_supported
structural_role
financial_value_candidates_total
```

It closes only:

- unsupported source projections as `unsupported`;
- closed layout roles with zero financial value candidates as
  `no_financial_input`.

All other combinations return no deterministic outcome. A manifest case
declared deterministic is rejected unless this closed evidence proves its
reference disposition.

The target Python contains no Financial Semantic Pack type ID, financial word,
header interpretation, synonym, type-specific regex, or type-specific
admission branch.

## 6. Binding, value, ownership, and provenance checks

The scorer is driven by fixture data and generically checks:

- Pack type identity for typed claims;
- source-value membership;
- role/ref equality;
- source-scope equality;
- duplicate roles, refs, and bindings;
- exact literal retention;
- required provenance retention and foreign provenance;
- exactly one referenced terminal owner.

The aggregate result contains no source refs or source literals. A dedicated
privacy test verifies that controlled literals and value refs do not enter the
safe result.

## 7. Query completeness

The controlled query case requires:

- `query_result_complete=true`;
- exact matching and cumulative counts;
- the exact complete ordered `{record_id, record_sha256}` set, binding
  literal-bearing record content without exposing literals;
- generic recomputation of every candidate record hash from its complete
  canonical record object before reference comparison;
- no duplicate record ID;
- all required and no foreign provenance refs.

Negative tests independently prove failure for false completeness, a partial
cumulative count, changed order, changed record content hash, foreign or
malformed refs, and provenance loss. Candidate lists are checked closed;
malformed entries cannot disappear during scoring.

Fresh review of remote implementation head
`63976821d181fea06cf20cb496c306414c10233e` returned
`CHANGES_REQUIRED`. The first query fixture pinned record IDs but not record
content integrity, so changed literal-bearing record content under unchanged
IDs could pass. Candidate ref parsing also discarded malformed non-string
entries. The corrected contract freezes ordered `{record_id, record_sha256}`
pairs, treats a missing/changed hash as incomplete query plus literal loss,
marks foreign/malformed refs invalid, and never filters malformed list
members. Dedicated negatives prove each corrected boundary.

Fresh review of correction head
`2a1073e4940a267149ad5fa91e1adf7301424332` found one remaining
integrity gap: the scorer compared the candidate's claimed hash without
recomputing it from returned content. The scorer now receives the complete
candidate record, removes its claimed hash, hashes canonical content, and only
then compares the verified hash with the frozen reference. Negative tests
cover both altered content with a copied old hash and altered content with a
newly recomputed hash. Safe output still omits all record payloads and
literals.

## 8. Frozen artifacts and deterministic result

```text
manifest_integrity_sha256=
86160b09382bc2d08da8c097da49a8d4ca3800156a359defe0bde4b007d9e658

sealed_result_integrity_sha256=
bc7347a094a83aa90990ad8e07cfcbbfb5ab62d3aad706c930620b6011cb39f3

sealed_result_file_sha256=
727fb01a3bcfffd1e77af06022bf918cf1fb82d833b8f36237389a12651d6109
```

Two scorer executions were exact and equal to the committed safe result.
The file hash above is the current working-file SHA-256; the safe receipt pins
the final staged Git-blob SHA-256 boundary.

## 9. Verification

Explicit test cwd:
`services/broker-reports-gate1-proof`.

Test environment: none.

- focused risk benchmark: `22 passed in 0.77s`;
- benchmark/domain relevant set: `65 passed in 2.60s`;
- full Broker Reports suite:
  `1606 passed, 20 skipped, 5 unchanged warnings in 145.47s`;
- targeted Ruff: passed;
- targeted Python compile: passed;
- deterministic scorer rebuild: exact;
- `git diff --check`: passed;
- repository privacy guard: `3 passed in 0.77s`.

Execution accounting:

```text
provider_calls=0
customer_calls=0
model_calls=0
tokens=0
cost_usd=0
fallback=0
repair=0
stage_mutations=0
production_changes=0
```

## 10. Explicitly unchanged

GOAL 8 does not change:

- the Financial Semantic Pack or its meanings;
- managed Skill, Prompt, Function, or asset manifest;
- universal scope, model input, validator, or materializer;
- four-disposition decision contract;
- financial domain catalog/query API;
- Artifact Store or persistence;
- workload/provider policy;
- live stage or production assets;
- model admissions or allowlists;
- Gate 3 methodology.

It makes no economy-model, actual-corpus, full-scope, live-query, or production
readiness claim.

## 11. Acceptance

```text
SAFETY_GATES=ABSOLUTE
SAFE_UNDERTYPING=MEASURED
EXACT_DISPOSITION_DISTRIBUTION=NOT_PRIMARY
QUERY_COMPLETENESS=TESTED
```

Acceptance remains pending the required fresh autonomous review of the exact
remote PR diff.

Next permitted goal:
`GOAL_9_AFTER_GOAL_8_REVIEW_ACCEPTANCE_MERGE_AND_CLEANUP`.

## 12. Safe receipt

Repository-safe receipt:
[`BROKER_REPORTS_GATE2_DOMAIN_GOAL8_RISK_BASED_BENCHMARK.receipt.safe.json`](./BROKER_REPORTS_GATE2_DOMAIN_GOAL8_RISK_BASED_BENCHMARK.receipt.safe.json).

The final receipt records exact staged Git-blob hashes and contains no
customer/private values, raw candidate/provider output, secret, private path,
or live-stage claim.

Exact staged receipt Git-blob SHA-256:

`ae4434cb4b4c267344892035764147b9cda945067495ef5ad66cc6297d421055`.
