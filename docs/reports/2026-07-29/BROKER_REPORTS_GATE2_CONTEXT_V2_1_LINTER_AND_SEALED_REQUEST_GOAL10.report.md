# Broker Reports Gate 2 Context V2.1 Linter And Sealed Request — GOAL 10

Date: `2026-07-29`

Status: `LOCAL_IMPLEMENTATION_ACCEPTED_DELIVERY_GATES_PENDING`

Base: `origin/main@4078cd033b3df3616441bc40d7d588b5967eeebb`

Branch:
`agent/broker-reports-gate2-context-v2-1-linter-goal10`

Provider calls: `0`

Runtime activation: `false`

## Outcome

GOAL 10 adds one inactive provider-neutral request method under the existing
Context Linter authority:

```text
Gate2FinancialSemanticV6ContextLinterFactory.create_context_v2_1
```

Historical `Gate2FinancialSemanticV6ContextLinterFactory.create` remains the
unchanged Slim request path. No second linter, Packet factory, Choice
authority, Prompt owner or Semantic Pack was created.
The existing Choice public validator additionally binds the exact model-order
bytes of its V2.1 response schema; the emitted schema, schema hash and active
Choice behavior remain unchanged.

The new request profile is exactly:

```text
broker_reports_gate2_financial_semantic_v6_request_v2_1_candidate
```

The private sealed-request receipt identity is exactly:

```text
broker_reports_gate2_llm_semantic_context_v2_1_sealed_request_receipt_v1
```

The linter constants are
`CONTEXT_V2_1_SEALED_REQUEST_PROFILE` and
`CONTEXT_V2_1_SEALED_REQUEST_RECEIPT_SCHEMA_VERSION`; the receipt policy is
`broker_reports_gate2_minimal_model_surface_v1`.

Every result is:

- `active=false`;
- `transport_eligible=false`;
- `provider_calls_total=0`;
- bound to the exact Packet candidate, private mapping receipt, Prompt and
  Choice-owned response schema;
- rejected fail closed on request drift, receipt drift, invariant failure or
  a complete-request size above `4 500` UTF-8 bytes.

## Exact provider-neutral surface

The model-visible logical request has exactly two root fields:

```text
messages
response_format
```

`messages` contains the exact Prompt-owned system message followed by the
Context V2.1 candidate serialized as one minified JSON user string. The exact
response wrapper is:

```json
{
  "type": "json_schema",
  "json_schema": {
    "strict": true,
    "schema": {}
  }
}
```

The empty schema object above is a metavariable for the exact Choice-owned
schema. It is never emitted empty. `json_schema.name`, schema titles,
descriptions, examples and provider-specific prose are absent.

The linter pins separate SHA-256 identities for the response schema,
response-format wrapper and complete model-visible request. It does not
substitute Choice's sorted canonical integrity hash for the model-order request
hash.

The governed Choice schemas retain their two GOAL 9 baselines:

| Visible choices | Response schema UTF-8 bytes | Response schema SHA-256 |
| ---: | ---: | --- |
| 0 | 274 | `bd17c1792c0b42e24c7639d4dc5614e1c961942245fca76a32a40566f8b5bb90` |
| 2 | 416 | `0b726d1b40ceefee44abc53cdf9d343c09c06457201841ac30d84cb1bd05efc4` |

## Frozen request baselines

The governed synthetic cases have these exact model-visible request baselines:

| Case | UTF-8 bytes | Estimated input tokens |
| --- | ---: | ---: |
| `syn_successor_v2_unique_cash` | 3,522 | 945 |
| `syn_successor_v2_unique_printed_total` | 3,520 | 944 |
| `syn_successor_v2_multiple_compatible` | 3,359 | 904 |
| `syn_successor_v2_no_registry_type` | 3,517 | 944 |
| `syn_successor_v2_missing_discriminator` | 3,453 | 928 |
| `syn_successor_v2_detail_vs_subtotal` | 3,311 | 892 |
| `syn_successor_v2_adjacent_equal` | 3,307 | 891 |
| `syn_successor_v2_adjacent_fx` | 3,359 | 904 |
| `syn_successor_v2_optional_missing` | 3,520 | 944 |
| `syn_successor_v2_forbidden_neighbour` | 3,521 | 945 |
| **Total** | **34,389** | **9,241** |

The maximum is `3,522/4,500` bytes. The estimator identity is
`compact_request_utf8_bytes_div_4_plus_64_v1`; it is deterministic planning
evidence, not a provider tokenizer or admission source of truth.

## Closed invariants

The private receipt carries exactly these counters:

```text
opaque_global_ids
backend_hashes
duplicate_literals
null_fields
unused_or_orphan_keys
unexplained_reason_codes
semantic_literals_total
semantic_literals_covered_total
mapping_rows_total
mapping_rows_covered_total
```

The first six counters must be zero. Coverage is exact:

```text
SEMANTIC_LITERAL_COVERAGE: 45_OF_45
MAPPING_ROW_COVERAGE: 156_OF_156
SOURCE_OCCURRENCE_ROWS: 45
SOURCE_STRUCTURE_ROWS: 20
TYPE_MAPPING_ROWS: 20
CHOICE_RESTORATION_ROWS: 12
INCLUDED_BINDING_ROWS: 59
```

The aggregate mapping counter includes all five row classes; the private
receipt does not expose separate binding counters.

## Fail-closed boundary

Local negative fixtures are required to reject:

- changed Prompt or serialized Context;
- response wrapper/schema drift, including `json_schema.name` or reordered
  model-visible fields;
- mapping-receipt substitution or resealed mapping tampering;
- response-schema, format, request or receipt hash drift;
- opaque IDs, backend hashes, duplicate literals, nulls, orphan keys or
  unexplained reasons;
- missing semantic literals or mapping rows;
- non-finite JSON and request sizes above `4 500` bytes.

No repair, retry, fallback or provider call is allowed.

## Compatibility accounting

```text
ACTIVE_PACKET_BYTES_OR_HASHES_CHANGED: NO
CONTEXT_V2_1_PACKET_OR_MAPPING_RECEIPT_CHANGED: NO
ACTIVE_CHOICE_BYTES_OR_HASHES_CHANGED: NO
HISTORICAL_LOCAL_CHOICE_V1_CHANGED: NO
HISTORICAL_CONTEXT_LINTER_CREATE_CHANGED: NO
PROMPT_CHANGED: NO
PROVIDER_ADAPTER_FILES_CHANGED: ZERO
MANAGED_ASSET_FILES_CHANGED: ZERO
BENCHMARK_FILES_CHANGED: ZERO
PROVIDER_CALLS: ZERO
RUNTIME_ACTIVATION: FALSE
```

The stable GitHub Actions check remains `broker-reports-ci`. Its Context V2.1
anti-drift step and the matching README command now include both the historical
Context Linter test and the additive V2.1 sealed-request test. The documented
local command and Actions command do not intentionally diverge.

Provider-specific projection, adapter response extraction, persistence,
restore, replay, report materialization, qualification and production
admission are outside GOAL 10.

## Local verification

Maintained checks completed locally:

```text
managed financial assets --check: PASSED
semantic model assets --check: PASSED
V5 execution assets --check: PASSED
Function bundles target all + tracked diff: PASSED_CLEAN
ruff E9,F63,F7,F82: PASSED
current Context V2.1 anti-drift: 36 passed
architecture/Packet -k context_v2_1: 9 passed, 38 deselected
combined linter/context/architecture compatibility: 62 passed
focused Broker Reports suite: 169 passed, 5 existing SWIG DeprecationWarnings
repository privacy guard: 3 passed
safe receipt JSON and canonical integrity: PASSED
required doc paths and diff whitespace: PASSED
full service suite: NOT_RUN_NOT_CLAIMED
```

Safe aggregate evidence:
[GOAL 10 safe receipt](./BROKER_REPORTS_GATE2_CONTEXT_V2_1_LINTER_AND_SEALED_REQUEST_GOAL10.receipt.safe.json).
Canonical receipt integrity:
`541baaf60e078019aefaaeed562312118b1fe5f544f091613399f761ab1ee2f0`.

## Delivery and continuation

This report records locally accepted implementation evidence. It does not
substitute for GitHub delivery gates and does not claim a PR, formal approval,
green GitHub Actions check, full service suite or merge.

After local verification succeeds:

1. review the complete fresh diff;
2. commit and push the exact branch head;
3. open a separate PR against current `main`;
4. wait for the real `broker-reports-ci` GitHub Actions check;
5. fresh-review the immutable PR head;
6. submit a formal GitHub review when branch protection requires it;
7. merge only after review and green checks.

**STOP before GOAL 11:** provider-specific local end-to-end proof may begin
only from the new merged `origin/main` after every GOAL 10 delivery gate is
complete.
