# Broker Reports Gate 2 Financial Semantic Local Choice V2.1

Status: `IMPLEMENTED_NON_ACTIVE_RESPONSE_PROFILE`

Response-profile schema identity:
`broker_reports_gate2_financial_semantic_context_v2_1_choice_response_profile_v1`

Policy identity:
`broker_reports_gate2_llm_semantic_context_v2_1_local_choice_v1`

Runtime activation: `false`

Transport eligible: `false`

Provider calls in implementation proof: `0`

## 1. Purpose and authority

This contract is the strict response companion to
[LLM Semantic Context V2.1](./BROKER_REPORTS_GATE2_LLM_SEMANTIC_CONTEXT.v2.1.md).
It is an additive sidecar of the existing
`Gate2FinancialSemanticV6ChoiceContractFactory.create` authority. No second
Choice factory, Packet factory, response parser module or provider route is
introduced.

The profile is built only after the active V6 Packet, Context V2.1 candidate
and private mapping receipt have passed their existing validation. It pins:

- the active Packet hash;
- the Context V2.1 view hash;
- the private mapping-receipt integrity hash;
- the unchanged active V6 Choice schema hash;
- the exact ordered request-local `choice_N` keys;
- the exact three Context V2.1 reason codes;
- its response schema and integrity hashes.

The profile is not part of `packet.payload`, is not embedded in managed assets
and is not consumed by the active request or runtime paths.

## 2. Closed response schema

For a request with one or more visible choices, the schema has exactly two
closed branches:

```json
{
  "anyOf": [
    {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "choice": {
          "type": "string",
          "enum": ["choice_1", "choice_2"]
        }
      },
      "required": ["choice"]
    },
    {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "choice": {
          "type": "string",
          "enum": ["unclassified"]
        },
        "reason": {
          "type": "string",
          "enum": [
            "no_registry_type",
            "single_registry_type_no_safe_record",
            "ambiguous_registry_type"
          ]
        }
      },
      "required": ["choice", "reason"]
    }
  ]
}
```

The typed enum is request-bound; `choice_1` and `choice_2` above are an
illustrative current shape, not a global cardinality rule.
The version identity belongs to the profile and future strict response-format
wrapper, not to model-visible schema `title` or description prose.

When `choices=[]`, the typed branch is absent rather than present with an empty
enum. The only accepted branch is then:

```json
{
  "type": "object",
  "additionalProperties": false,
  "properties": {
    "choice": {
      "type": "string",
      "enum": ["unclassified"]
    },
    "reason": {
      "type": "string",
      "enum": [
        "no_registry_type",
        "single_registry_type_no_safe_record",
        "ambiguous_registry_type"
      ]
    }
  },
  "required": ["choice", "reason"]
}
```

Free text, nulls, missing fields, extra fields, technical dispositions,
canonical option IDs, type IDs, refs, bindings, literals, provenance and
records are forbidden.

## 3. Deterministic normalization

`normalize_financial_semantic_v6_context_v2_1_choice` is the Choice-owned
parser. It accepts one JSON object or its exact JSON serialization. It performs
no trim, case conversion, alias repair, fallback or semantic reinterpretation.

Typed normalization is:

```text
model choice_N
→ exact equal choice_key row in
  packet.context_v2_mapping_receipt.choice_restoration
→ that row's exact typed_option_id
→ {"disposition":"typed_input","typed_option_id":"<exact>"}
```

The implementation must not derive the option by parsing `N`, by indexing
Compilation directly, by using historical Slim `A/B` aliases, by matching a
title or by trusting model-provided backend identity.

Unclassified normalization is:

```text
{"choice":"unclassified","reason":"<allowed exact reason>"}
→
{"disposition":"unclassified_financial_input","reason_code":"<same exact reason>"}
```

The result preserves the existing minimal V6 Choice field shapes. The third
reason, `single_registry_type_no_safe_record`, is admitted only by this
non-active V2.1 profile. The active V6 Choice schema, historical Local Choice
v1, Expansion and canonical decision contract remain unchanged and still
accept their existing two reasons. Therefore this GOAL proves normalization,
not active expansion or materialization of the third reason.

## 4. Fail-closed rules

The parser or profile validator rejects:

- unknown or duplicate JSON keys;
- unknown, duplicate or orphan `choice_N` mappings;
- a typed response with `reason`;
- an unclassified response without `reason`;
- an unknown reason or free-text answer;
- a typed branch when the Context candidate has zero choices;
- duplicate receipt targets or a receipt target outside the active option set;
- choice, pointer, reason or presentation-order mismatch;
- Context view, receipt, active Choice, schema or profile hash mismatch;
- inactive/transport/provider-call/repair flags with any non-canonical value.

The public full Choice-contract validator rebuilds the profile through the same
existing factory and rejects resealed contract tampering against the original
Packet, Bundle, source package, Compilation and Registry authorities.

## 5. Compatibility and non-claims

Unchanged:

- active V6 Choice schema bytes and all ten frozen schema hashes;
- active Packet bytes and hashes;
- historical Local Choice v1 schema, parser and hashes;
- Context V2.1 payload and private mapping receipt;
- Prompt and active Expansion/materialization/totality paths;
- provider execution identity and live transport;
- managed assets, benchmark expectations and runtime admission.

Not owned by this Choice contract:

- provider-specific schema projection or response-envelope extraction;
- provider calls or qualification;
- persistence, replay, benchmark execution or runtime activation.

GOAL 10 consumes this profile only through additive
`Gate2FinancialSemanticV6ContextLinterFactory.create_context_v2_1` and emits an
inactive provider-neutral sealed request. It neither changes nor reconstructs
the Choice schema. Choice-owned public validation binds the schema's exact
model-order bytes, so reordered fields cannot retain acceptance merely because
the canonical integrity serializer sorts keys.

GOAL 11 consumes the sealed request through existing OpenAI, Anthropic and
Google adapters, then returns adapter-extracted output to this parser. The
existing Expansion/decision factories expose an additive candidate-only path
for all three reasons; active V6 remains unchanged. Exact synthetic evidence is
in the [GOAL 11 report](../../reports/2026-07-29/BROKER_REPORTS_GATE2_CONTEXT_V2_1_THREE_PROVIDER_LOCAL_PROOF_GOAL11.report.md).

GOAL 12 may carry the same exact inactive profile through the separately
versioned qualification-only
[budget-model smoke](./BROKER_REPORTS_GATE2_CONTEXT_V2_1_BUDGET_MODEL_SMOKE.v1.md).
That path does not make this Choice profile product-transport-eligible: the
immutable slot plan, one-attempt client seam and external evidence ledger are
qualification authorities, while parsing and restoration still delegate here
without semantic repair.
