# Broker Reports Gate 2 Financial Semantic Choice V6

Status: `ACTIVE_V6_UNCHANGED_LOCAL_CANDIDATE_NON_ACTIVE`

## Boundary

`Gate2FinancialSemanticV6ChoiceContractFactory.create` derives the only
provider-facing semantic-choice schema from the exact validated V6 packet.
The model chooses among code-owned Typed Option IDs; it never creates a typed
record.

The provider-neutral schema identity is
`broker_reports_gate2_financial_semantic_choice_v6`.

## Allowed responses

Typed:

```json
{
  "disposition": "typed_input",
  "typed_option_id": "<opaque code-owned option ID>"
}
```

Unclassified:

```json
{
  "disposition": "unclassified_financial_input",
  "reason_code": "ambiguous_registry_type | no_registry_type"
}
```

Each variant is a closed object. The typed option enum is copied exactly from
the validated packet. If no Typed Option exists, the typed variant is absent
for that packet; this does not create another provider disposition.

This contract owns the closed reason codes and JSON shape only. It does not own
their human-readable semantic distinction. Context V2 must obtain that wording
from the single versioned
[Financial Decision Reason Catalog v1](./BROKER_REPORTS_GATE2_FINANCIAL_DECISION_REASON_CATALOG.v1.md)
in the existing managed Financial Domain asset family. That catalog is
currently an inactive repository draft and is not exposed by this active
Choice route. Choice parsing and normalization continue to validate codes;
they must not reinterpret or repair a model decision.

## Prohibitions

The model response contains no separate type ID, source ref, role binding,
literal, provenance, dimension, or record field. It contains no free-form
reason.

`no_financial_input` and `unsupported` remain code-owned technical-preclose
outcomes and are never exposed in the provider semantic-choice schema.

## Disposition accounting

- provider semantic dispositions: exactly two globally;
- per-packet available provider dispositions: one or two, depending on whether
  at least one Typed Option exists;
- canonical Gate 2 dispositions: the existing four, unchanged.

Goal 5 defines only the minimal response contract. Independent response
validation and canonical materialization remain downstream boundaries.

## Relationship to local Choice aliases

The current V6 Choice remains the sole active provider-neutral response
contract and continues to require the exact opaque `typed_option_id`.

The separate versioned
[Local Choice v1](./BROKER_REPORTS_GATE2_FINANCIAL_SEMANTIC_LOCAL_CHOICE.v1.md)
candidate is now implemented but non-active. It accepts only request-local
aliases and deterministically normalizes them to this exact current Choice
before the existing expansion authority runs.

The GOAL 2 proof pins all 10 current Choice schema hashes, exact permutation
mapping, canonical expansion/materialization parity and unchanged
unclassified retention. Neither the current provider schema nor its request
route changed. Provider calls remain zero.

The
[LLM Semantic Context v1](./BROKER_REPORTS_GATE2_LLM_SEMANTIC_CONTEXT.v1.md)
defines the complete model-visible boundary. The local candidate satisfies its
zero-opaque-ID Choice shape locally; GOAL 3 must add the pre-transport Context
Linter before any provider diagnostic.
