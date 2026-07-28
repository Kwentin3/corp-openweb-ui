# Broker Reports Gate 2 Financial Semantic Choice V6

Status: Goal 5 contract for Candidate Records By Construction.

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

The
[LLM Semantic Context v1](./BROKER_REPORTS_GATE2_LLM_SEMANTIC_CONTEXT.v1.md)
defines a future full-request target with zero opaque model-visible IDs.
Meeting that target requires a separate versioned, non-active Choice candidate
that accepts only request-local option aliases and deterministically expands
them to this canonical Choice.

The GOAL 1 Slim View is implemented but remains non-active and continues to
show exact `return_id` because this current Choice requires it. The local
Choice candidate is still not defined, implemented or activated. GOAL 2 must
prove exact alias mapping, permutation behavior, canonical
expansion/materialization parity and unchanged unclassified retention before
any provider qualification.
