# Broker Reports Gate 2 Financial Semantic Choice V6

Status: `ACTIVE_V6_UNCHANGED_CONTEXT_V2_1_RESPONSE_PROFILE_NON_ACTIVE`

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
their human-readable semantic distinction. The implemented non-active Context
V2.0 completeness baseline obtains that wording from the single versioned
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

Historical Financial Semantic V6 GOAL 5 defined only this minimal response
contract. That completed program goal is distinct from current Minimal Model
Surface GOAL 5. Independent response validation and canonical materialization
remain downstream boundaries.

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

The separately versioned
[Local Choice V2.1](./BROKER_REPORTS_GATE2_FINANCIAL_SEMANTIC_LOCAL_CHOICE.v2.1.md)
response profile is also implemented inside this same factory and remains
non-active and transport-ineligible. It uses Context V2.1 `choice_N` keys and
restores them only through the private Context V2.1 mapping receipt. It does
not replace this active exact-ID schema or historical Local Choice v1.

The
[LLM Semantic Context v1](./BROKER_REPORTS_GATE2_LLM_SEMANTIC_CONTEXT.v1.md)
defines the complete model-visible boundary. The local candidate satisfies its
zero-opaque-ID Choice shape locally. The pre-transport Context Linter was
subsequently implemented for the non-active candidate profile, and the
historical Slim-program GOAL 4 diagnostic is terminal; neither changed the
active Choice.

The later Managed Semantic Decision Context
[alias necessity audit](../../reports/2026-07-28/BROKER_REPORTS_GATE2_MANAGED_SEMANTIC_CONTEXT_GOAL2_ALIAS_NECESSITY_AND_READABILITY_AUDIT.report.md)
required the separately versioned Context V2.0 completeness candidate to pair
each unique local choice key with the mapped type's exact Pack title as a
separate label;
evidence differences stay in structured relationships. Positional `A/B` may
not remain the sole presentation, but the label must not replace unique
response identity or turn semantic ambiguity into a technical failure.
Cross-type ambiguity can use `unclassified`; same-type indistinguishability
hits the count-one compatibility stop. Those V2.0 keys are implemented only in
the non-active packet sidecar and its private receipt. This active contract,
its exact-ID response and its runtime route remain unchanged.

The exact historical completeness shape is fixed by
[LLM Semantic Context V2.0](./BROKER_REPORTS_GATE2_LLM_SEMANTIC_CONTEXT.v2.md):
`choice_N` is a request-local response key, its adjacent label is presentation
only, and the strict unclassified branch uses only codes with complete
catalog-owned visible reason cards. Managed Semantic Decision Context GOAL 4
implements those keys/cards only in the packet-owned non-active Context V2.0
candidate and private mapping receipt.
The V2.0 response schema/parser is still `NOT_IMPLEMENTED`; the active exact-ID
Choice and historical Local Choice v1 are unchanged.

The
[Minimal Model Surface v1](./BROKER_REPORTS_GATE2_MINIMAL_MODEL_SURFACE.v1.md)
supersedes V2.0 as the target field set for the implemented non-active
[V2.1 candidate](./BROKER_REPORTS_GATE2_LLM_SEMANTIC_CONTEXT.v2.1.md).
GOAL 7 implements the exact GOAL 5-selected managed projection and GOAL 8
builds only that PacketFactory candidate plus private receipt. The later
governing program separately authorized GOAL 9 to add the V2.1 response
profile through this existing Choice authority.

GOAL 9 does not change active V6 Choice bytes or its two active reason codes.
Its inactive profile adds the exact Context V2.1 reason set, including
`single_registry_type_no_safe_record`, and normalizes it to the unchanged V6
minimal Choice field shape. Active Expansion/materialization of that third
reason is not claimed. Context Linter V2.1 and the sealed request belong to
GOAL 10 and are now implemented non-active through additive
`Gate2FinancialSemanticV6ContextLinterFactory.create_context_v2_1`. That
consumer uses this exact schema without changing or rebuilding it. Provider
projection and adapter proof remain stopped before GOAL 11.

The selection rules use existing managed strings: Pack
`examples[0]`, `counterexamples[0]`, the unique direct rule against the only
other current visible type, and the exact first sentence of catalog `meaning`.
GOAL 7 may not author replacement markers or reason wording.
