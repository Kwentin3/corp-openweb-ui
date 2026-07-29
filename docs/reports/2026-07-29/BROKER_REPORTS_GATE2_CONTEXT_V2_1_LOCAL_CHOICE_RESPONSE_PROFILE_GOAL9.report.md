# Broker Reports Gate 2 Context V2.1 Local Choice Response Profile — GOAL 9

Date: `2026-07-29`

Status: `LOCAL_IMPLEMENTATION_ACCEPTED_DELIVERY_GATES_PENDING`

Base: `origin/main@359679faf4542c5c8b8659af84a0388fdcb378eb`

Branch:
`agent/broker-reports-gate2-context-v2-1-choice-goal9`

Provider calls: `0`

Runtime activation: `false`

## Outcome

GOAL 9 adds one versioned inactive response profile to the existing
`Gate2FinancialSemanticV6ChoiceContractFactory.create` authority:

```text
schema_version =
broker_reports_gate2_financial_semantic_context_v2_1_choice_response_profile_v1

policy_version =
broker_reports_gate2_llm_semantic_context_v2_1_local_choice_v1
```

The profile is:

- `active=false`;
- `transport_eligible=false`;
- `provider_calls_total=0`;
- `post_response_repair_allowed=false`;
- integrity-bound to the active Packet, Context V2.1 view, private mapping
  receipt and unchanged active V6 Choice schema.

No second Packet, Choice, Pack, response-parser module or provider route was
created.

## Authority path

Normative contracts:

- [Architecture Authorities](../../stage2/contracts/BROKER_REPORTS_ARCHITECTURE_AUTHORITIES.md)
- [Minimal Model Surface v1](../../stage2/contracts/BROKER_REPORTS_GATE2_MINIMAL_MODEL_SURFACE.v1.md)
- [Context V2.1](../../stage2/contracts/BROKER_REPORTS_GATE2_LLM_SEMANTIC_CONTEXT.v2.1.md)
- [Active Choice V6](../../stage2/contracts/BROKER_REPORTS_GATE2_FINANCIAL_SEMANTIC_CHOICE_V6.md)
- [Local Choice V2.1](../../stage2/contracts/BROKER_REPORTS_GATE2_FINANCIAL_SEMANTIC_LOCAL_CHOICE.v2.1.md)

Historical predecessor implementation evidence remains unchanged:

- GOAL 7 minimal managed projection report/receipt;
- GOAL 8 Context V2.1 candidate/private-receipt report/receipt;
- historical Local Choice v1 schema/parser behavior and hashes.

The new governing program separately cleared the historical post-GOAL-8 STOP.
It assigns the Choice profile to GOAL 9 and moves Context Linter V2.1 plus the
sealed request to GOAL 10.

## Closed response shapes

When visible choices exist, the profile accepts exactly:

```json
{"choice":"choice_1"}
```

or:

```json
{"choice":"unclassified","reason":"no_registry_type"}
```

The exact allowed reason set is:

```text
no_registry_type
single_registry_type_no_safe_record
ambiguous_registry_type
```

When `choices=[]`, the typed branch is absent. The schema contains only the
closed unclassified branch.

The two frozen current response-schema shapes are:

| Visible choices | Minified UTF-8 bytes | SHA-256 |
| ---: | ---: | --- |
| 0 | 274 | `bd17c1792c0b42e24c7639d4dc5614e1c961942245fca76a32a40566f8b5bb90` |
| 2 | 416 | `0b726d1b40ceefee44abc53cdf9d343c09c06457201841ac30d84cb1bd05efc4` |

Across the ten governed cases the response schemas total 3,592 UTF-8 bytes.
This is response-profile evidence only, not a complete sealed-request budget
claim.

## Deterministic restoration

Typed normalization follows one path:

```text
choice_N
→ exact equal choice_key row in
  packet.context_v2_mapping_receipt.choice_restoration
→ row.typed_option_id
→ unchanged minimal V6 typed Choice shape
```

The implementation does not parse `N`, index Compilation, use historical
`A/B`, match a title or trust a model-provided backend ID.

Unclassified normalization copies the exact allowed reason into
`reason_code`; no trim, alias, case conversion, fallback, retry or repair is
performed.

The third reason is admitted only by this inactive V2.1 profile. Active V6
Choice, historical Local Choice v1, Expansion and the canonical decision
contract remain at their existing two-reason boundary. GOAL 9 therefore does
not claim active expansion/materialization for the third reason.

## Frozen compatibility proof

```text
GOVERNED_CASES: 10
TYPED_CHOICE_RESTORATIONS: 12_EXACT
ZERO_CHOICE_SCHEMAS: 4_UNCLASSIFIED_ONLY
V2_1_REASON_CODES: 3_EXACT
ACTIVE_CHOICE_SCHEMA_HASH_PARITY: 10_OF_10_EXACT
HISTORICAL_LOCAL_CHOICE_V1_SCHEMA_HASHES: 2_OF_2_EXACT
ACTIVE_PACKET_BYTES_OR_HASHES_CHANGED: NO
CONTEXT_V2_1_PACKET_OR_RECEIPT_CHANGED: NO
PROVIDER_ADAPTER_FILES_CHANGED: ZERO
EXPANSION_FILES_CHANGED: ZERO
LINTER_OR_REQUEST_BUILDER_FILES_CHANGED: ZERO
MANAGED_ASSET_FILES_CHANGED: ZERO
BENCHMARK_FILES_CHANGED: ZERO
NEW_CHOICE_FACTORIES: ZERO
PROVIDER_CALLS: ZERO
RUNTIME_ACTIVATION: FALSE
```

Fail-closed tests cover unknown response choice, duplicate JSON key, orphan
receipt mapping, coordinated receipt/profile/Choice option-ID tampering,
extra/free-text fields, missing/unknown reason, zero-choice typed output,
profile/schema/hash tampering and full-contract rebuild mismatch.

## Local verification

Generated and static checks:

```text
build_openwebui_managed_financial_assets.py --check: PASSED
build_gate2_financial_semantic_model_assets.py --check: PASSED
build_gate2_financial_semantic_v5_execution.py --check: PASSED
build_openwebui_pipe_bundle.py --target all + tracked diff: PASSED
ruff E9,F63,F7,F82: PASSED
```

Test results from the exact documented CI command set:

```text
Context V2.1 anti-drift: 21 passed
Architecture/Packet -k context_v2_1: 9 passed, 38 deselected
Focused Broker Reports suite: 169 passed, 5 dependency warnings
```

The initial focused run correctly failed because a pre-GOAL-9 anti-drift test
forbade the new reason in every Python module except managed assets. That test
was narrowed to permit the reason only in the inactive Choice-owned V2.1
profile and still forbid it in Expansion, runtime, requests and adapters. The
complete focused suite then passed.

Safe aggregate evidence:
[GOAL 9 safe receipt](./BROKER_REPORTS_GATE2_CONTEXT_V2_1_LOCAL_CHOICE_RESPONSE_PROFILE_GOAL9.receipt.safe.json).

## Delivery and continuation

This report records local implementation evidence. It does not substitute for
the required GitHub delivery gates:

1. push the exact branch head;
2. open a separate PR against current `main`;
3. wait for the real `broker-reports-ci` GitHub Actions check;
4. perform fresh review of the immutable PR head;
5. submit a formal GitHub review, not an `APPROVED` comment;
6. merge only after review and green check.

GOAL 10 is not implemented here and is not authorized by this local report.
It may start only from the new merged `origin/main` after every delivery gate
above is satisfied.
