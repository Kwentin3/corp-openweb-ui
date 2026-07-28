# Broker Reports Gate 2 Financial Semantic Local Choice v1

Status: `GOAL3_LINTED_NOT_ACTIVE`

Contract identity:
`broker_reports_gate2_financial_semantic_local_choice_candidate_v1`

Policy identity:
`broker_reports_gate2_llm_semantic_context_local_choice_v1`

## Purpose

This contract removes canonical Typed Option IDs from the non-active Gate 2
model surface without changing the active V6 Choice, canonical expansion,
validation or materialization path.

The model may return only:

```json
{"choice": "A"}
```

or:

```json
{
  "choice": "unclassified",
  "reason": "no_registry_type"
}
```

`A`, `B`, and later aliases are request-local indexes. They are not financial
identities, are never persisted, and have meaning only together with the exact
request-bound private alias receipt.

## Authority

`Gate2FinancialSemanticV6ChoiceContractFactory.create` remains the only V6
Choice-contract construction entrypoint. It returns:

1. the unchanged active V6 Choice contract;
2. one `Gate2FinancialSemanticV6LocalChoiceCandidate` with `active=False`.

`Gate2FinancialSemanticV6DecisionExpansionFactory` remains the sole
minimal-choice-to-canonical-decision expansion authority. Its
`create_from_local_candidate` entrypoint first normalizes the local answer to
the exact current V6 Choice and then delegates to the same canonical expansion
logic used by `create`.

No second Choice factory, packet builder, Candidate Compiler, provider adapter
or materializer is introduced.

## Model-visible schema

When typed choices are available:

```json
{
  "title": "Semantic choice",
  "anyOf": [
    {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "choice": {
          "type": "string",
          "enum": ["A", "B"]
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
            "ambiguous_registry_type",
            "no_registry_type"
          ]
        }
      },
      "required": ["choice", "reason"]
    }
  ]
}
```

When no typed choice exists, the typed variant is omitted. The unclassified
variant and exact reason set remain unchanged.

The schema contains no canonical option ID, input type ID, source ref, hash or
storage identity.

## Exact normalization

For one exact packet:

| Local answer | Private receipt lookup | Current canonical Choice |
| --- | --- | --- |
| `{"choice":"A"}` | `A → exact typed_option_id` | `{"disposition":"typed_input","typed_option_id":"<exact>"}` |
| `{"choice":"unclassified","reason":"ambiguous_registry_type"}` | no option lookup | `{"disposition":"unclassified_financial_input","reason_code":"ambiguous_registry_type"}` |
| `{"choice":"unclassified","reason":"no_registry_type"}` | no option lookup | `{"disposition":"unclassified_financial_input","reason_code":"no_registry_type"}` |

The normalizer:

- accepts only the exact closed shapes above;
- rejects unknown aliases, reasons, extra fields and duplicate JSON keys;
- performs no fallback, repair, semantic rewrite or typed-to-unclassified
  conversion;
- verifies candidate, Slim View and alias-receipt integrity before lookup.

## Private binding

The non-active candidate is code-bound to:

- active packet hash;
- Slim View hash;
- Slim alias-receipt integrity hash;
- unchanged active Choice schema hash;
- ordered local choice aliases;
- exact unclassified reasons;
- local response-schema hash;
- its own integrity hash.

Exact `A/B → typed_option_id` mapping remains in
`Gate2FinancialSemanticV6SlimAliasReceipt`. It is never placed in messages or
the local response schema.

## Permutation

Choice order is a code-owned, request-local projection. The existing packet
factory accepts an optional exact permutation for the non-active Slim
candidate only:

```text
canonical order: option X, option Y
visible mapping: A → X, B → Y

reversed order: option Y, option X
visible mapping: A → Y, B → X
```

The active packet payload/hash and canonical compilation remain unchanged.
The visible choice records and private mapping move together. Duplicate,
missing or unknown option IDs fail closed.

## Local proof

Across all 10 frozen V6 cases:

```text
ACTIVE_CHOICE_SCHEMA_HASH_PARITY: 10_OF_10_EXACT
ACTIVE_PACKET_HASH_PARITY: 10_OF_10_EXACT
FULL_MODEL_VISIBLE_OPAQUE_IDS: ZERO
LOCAL_ALIAS_MAPPING: EXACT
PERMUTATION_MAPPING: EXACT
CANONICAL_EXPANSION_PARITY: EXACT
CANONICAL_MATERIALIZATION_PARITY: EXACT
UNCLASSIFIED_RETENTION: UNCHANGED
LOCAL_CHOICE_ACTIVE: FALSE
PROVIDER_CALLS: ZERO
FALLBACK_REPAIR_RETRY: ZERO
```

The complete model-visible projection measured here is the exact system/user
messages plus strict response format. Provider metadata, code-owned hashes and
private receipts are not model-visible.

| Measure, 10-case total | Current V6 | Slim v2 + Local Choice |
| --- | ---: | ---: |
| packet/view UTF-8 bytes | 73,970 | 18,098 |
| complete model-visible UTF-8 bytes | 89,220 | 26,404 |
| repository request estimator | 22,950 | 7,247 |

The complete-view byte reduction is 70.4%; the repository-estimator reduction
is 68.4%. These are deterministic local measurements, not provider-reported
tokens.

Representative frozen typed-case identities:

```text
SLIM_VIEW_HASH: ac9c598bcb5ed94b7af566c7b16e2f07ae22edf6025137fe6c2b7bf1e7541ce8
SLIM_ALIAS_RECEIPT_INTEGRITY: 997b90920c63c5d79272269f6d24cc5232f2d611855a951d6592b78fd03a9989
LOCAL_CHOICE_SCHEMA_HASH: adf7dbf67b563db7d82292fbacae541e204fbe1cb34cf1fca77d2fee8279eff4
LOCAL_CHOICE_CANDIDATE_INTEGRITY: 3df5c7c5c7901f29e1324d7bb2ad15f4d6f14d21c90c9b120cd0b9950e8318db
```

## Pre-transport lint boundary

The Local Choice is accepted by the non-active
`financial_semantic_v6_slim_linted_v1` request profile only after
`Gate2FinancialSemanticV6ContextLinterFactory.create` verifies and seals the
complete Prompt + Slim View + response-schema projection. The existing request
builder rejects missing or tampered lint receipts before transport.

Across the frozen suite, exact replay passes 10/10 and every local typed or
unclassified output materializes: 32/32, with zero
`validated_but_unmaterializable` results. This route is not called by the
current qualification runner, evidence runtime or product runtime. No provider
call is authorized by GOAL 3. GOAL 4 is the separate bounded model diagnostic;
activation remains a later decision after the qualified full benchmark.

## GOAL 4 model diagnostic result

GOAL 4 exercised this exact Local Choice candidate through the sealed Slim
request profile. The typed alias mapping worked mechanically in canonical and
reversed order: every schema-valid answer normalized, expanded and
materialized without repair. Six planned submissions produced six responses.

Semantic acceptance nevertheless failed. Haiku passed the typed cash case but
selected the wrong unclassified reason. Nano failed both canonical-order
cases, failed the reversed typed case and passed only the reversed
unclassified case. The exact
[evidence report](../../reports/2026-07-28/BROKER_REPORTS_GATE2_LLM_CONTEXT_GOAL4_SLIM_MODEL_DIAGNOSTIC.report.md)
shows that the model sees the allowed reason codes only as bare enum labels.
The post-execution audit therefore identifies a narrow readable
unclassified-reason boundary gap; the adapter and canonical parser behaved
correctly and must not rewrite that semantic answer.

The candidate remains non-active. The exact GOAL 4 authorization is consumed,
the full benchmark was not run, and no production admission follows.
