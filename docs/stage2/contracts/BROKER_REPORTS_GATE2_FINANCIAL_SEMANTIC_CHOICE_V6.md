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
