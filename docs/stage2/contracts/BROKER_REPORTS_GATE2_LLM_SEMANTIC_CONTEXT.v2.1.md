# Broker Reports Gate 2 LLM Semantic Context V2.1

Status: `IMPLEMENTED_NON_ACTIVE_THREE_PROVIDER_LOCAL_PROOF`

Contract identity:
`broker_reports_gate2_llm_semantic_context_v2_1`

Contract version: `2.1.0`

Policy identity: `broker_reports_gate2_minimal_model_surface_v1`

Runtime activation: `false`

Transport eligible: `false`

Response profile:
`broker_reports_gate2_financial_semantic_context_v2_1_choice_response_profile_v1`

Sealed-request receipt:
`broker_reports_gate2_llm_semantic_context_v2_1_sealed_request_receipt_v1`

Provider-neutral request profile:
`broker_reports_gate2_financial_semantic_v6_request_v2_1_candidate`

Non-active provider schema projection policy:
`broker_reports_gate2_context_v2_1_local_schema_projection_v1`

## 1. Purpose and boundary

Context V2.1 is the sole current minimal model-facing successor candidate for
the Broker Reports Gate 2 financial semantic decision. It implements the
[Minimal Model Surface v1](./BROKER_REPORTS_GATE2_MINIMAL_MODEL_SURFACE.v1.md)
inside the existing
`Gate2FinancialSemanticV6PacketFactory.create` owner.

For every validated semantic operation, that owner constructs:

1. the active four-block V6 packet, byte-identical to its frozen baseline;
2. one non-active Context V2.1 candidate; and
3. one private exact mapping receipt.

The candidate is not part of `packet.payload`. The existing Choice authority
builds one separately versioned inactive response profile. The existing Context
Linter combines that exact candidate and schema with the unchanged Prompt,
validates the private mapping receipt, and seals one provider-neutral request.
The GOAL 11 zero-call coordinator then delegates provider projection/extraction,
canonical materialization, Financial Domain persistence/restore and replay to
their existing authorities. No live runtime route, provider transport or model
qualification runner consumes it.

The implemented
[Context V2.0](./BROKER_REPORTS_GATE2_LLM_SEMANTIC_CONTEXT.v2.md)
remains immutable, version-pinned historical completeness evidence. The
current packet path does not build V2.0 per request.

## 2. Sole authorities

| Concern | Sole authority | V2.1 rule |
| --- | --- | --- |
| source facts and real hierarchy | validated Evidence Bundle | exact readable projection; no invented structure |
| type and role meaning | Financial Semantic Pack | read through the existing projection owner |
| unclassified reason meaning | decision-reason catalog v2 in inactive family v3 | exact minimal managed projection |
| exact options and bindings | Candidate Compilation and Typed Option owners | private; only necessary same-title differences may be visible |
| candidate and receipt construction | `Gate2FinancialSemanticV6PacketFactory.create` | one current candidate and one receipt |
| response schema and parsing | existing V6 Choice owner | one inactive V2.1 profile restores only through the private receipt |
| complete-request lint and seal | additive `Gate2FinancialSemanticV6ContextLinterFactory.create_context_v2_1` method under the existing linter owner; historical `create` unchanged | one inactive V2.1 request profile and private sealed-request receipt |
| provider projection binding | adapter-owned `Gate2PreparedProviderRequest.validate_schema_binding`, `canonical_schema_is_bound` and additive `context_v2_1_contract_is_bound` | the adapter deterministically rebuilds the complete prepared request from the validated sealed request and repository profile, then compares the whole contract: messages, model, top-level shape, provider metadata, full projected schema, wrapper/name/strictness, transform count, hashes and `broker_reports_gate2_context_v2_1_local_schema_projection_v1` |
| exact local evidence/replay | additive `Gate2FinancialSemanticV6DecisionEvidenceFactory.create_context_v2_1_candidate` and Context V2.1 serialize/restore/replay functions under the existing evidence owner | the sealed request is replay-validated against Packet/Choice authorities; restored adapter output and the exact rebuilt prepared request are compared before replay; no coordinator rerun or provider call |

No V2.1 Packet factory, projection owner, Choice factory or semantic wording
authority is introduced.

## 3. Closed model-visible payload

The candidate payload has exactly these ordered root fields:

1. `task`;
2. `source`;
3. `type_cards`;
4. `choices`;
5. `unclassified_reasons`.

The exact task is:

```text
Select one choice only when the visible source, type cards, and any shown differentiators uniquely support it; otherwise select unclassified.
```

The root grammar is:

```json
{
  "task": "<exact task>",
  "source": {
    "children": []
  },
  "type_cards": [],
  "choices": [],
  "unclassified_reasons": []
}
```

`choices` may be empty. Every other required array is non-empty. Nulls, empty
optional containers and fields outside the Minimal Model Surface allowlist
are forbidden.

## 4. Source projection

`source.children` contains only real Evidence Bundle structures:

- `table`;
- `row`;
- `text segment`.

Every authoritative non-`source_reference` value appears exactly once as one
`meaning` plus byte-exact `literal` occurrence. Equal literals at distinct
source occurrences remain distinct. The hierarchy may reorder a flat
interleaved bundle sequence only by grouping values under their exact real
row/table/segment lineage; occurrence and source-reference parity remain
exact in the private receipt.

The candidate does not expose:

- `source.document`;
- invented `evidence group` nodes;
- `source_reference` literals;
- `value_type`;
- source, association, document, row, cell, segment or evidence refs;
- provenance, hashes or integrity identities;
- generic roles, labels or local keys without a decision consumer.

If a non-reference value cannot be represented in a real visible hierarchy,
construction fails closed.

## 5. Managed type and reason projection

`type_cards` and `unclassified_reasons` are exact deep copies of
`Gate2FinancialSemanticV5ProjectionFactory.create_minimal_managed_projection`.
Packet code owns no copied type or reason wording.

The current projection contains:

- two ordered type cards;
- three ordered unclassified reason cards;
- local `type_N` keys only;
- exact managed title, definition, primary positive signal, primary negative
  signal and reciprocal nearest-competitor distinction;
- exact reason code, title and `use_when`.

The private receipt pins the projection profile/version, projection hash,
authority-audit hash, managed source identities and Registry identity.

## 6. Choices and differentiators

Each compiled Typed Option restores through one request-local `choice_N`.
The visible choice contains:

- exact local `choice_key`;
- exact managed type title; and
- optional `differentiators` only when otherwise same-title choices require
  them.

Canonical option/type IDs and complete bindings remain private. A visible
differentiator is allowed only when the minimum set of differing exact
bindings uniquely separates every same-title option, its role is readable,
and its target is a real visible value or structure. A shared target,
unrepresentable binding shape, indistinguishable option set, cross-type title
collision or title collision in the visible glossary fails closed.

`value_N` and `structure_N` exist only when an emitted differentiator consumes
them. The current frozen two-type suite has title-distinct choices, therefore
it emits zero differentiators, zero `value_N` and zero `structure_N`.

## 7. Private exact mapping receipt

The receipt schema is
`broker_reports_gate2_llm_semantic_context_v2_1_mapping_receipt_v1`.
It is never model input and contains:

- active packet identity and hash;
- Context contract, policy and view identity;
- minimal projection and managed-source authority pins;
- exact Evidence Bundle and Candidate Compilation scope pins;
- every visible source occurrence pointer, exact source refs, lineage,
  evidence refs and meaning-authority pointer;
- exact `type_N` to canonical type mapping;
- exact `choice_N` to Typed Option and type mapping;
- every ordered option binding;
- the exact visible/backend-only binding partition; and
- presentation order plus integrity hash.

The public validator deterministically rebuilds both candidate and receipt.
Changing payload, order, mapping, binding, authority pin or receipt material
is rejected even when the supplied payload or receipt hash is recomputed.

Repository-safe rendering publishes only hashes, counts, byte sizes,
non-active status and zero-call accounting. It publishes no source literal,
source ref, option ID or private lineage.

## 8. Frozen deterministic proof

The current ten frozen semantic cases retain the earlier active, historical
V2.0 and Context-candidate measurements and add the exact provider-neutral
sealed request:

| Case | Active V6 bytes | Historical V2.0 bytes | Context V2.1 bytes | Sealed request bytes |
| --- | ---: | ---: | ---: | ---: |
| `syn_successor_v2_unique_cash` | 9,638 | 8,070 | 2,645 | 3,522 |
| `syn_successor_v2_unique_printed_total` | 9,905 | 8,068 | 2,643 | 3,520 |
| `syn_successor_v2_multiple_compatible` | 4,246 | 7,620 | 2,624 | 3,359 |
| `syn_successor_v2_no_registry_type` | 9,770 | 8,065 | 2,640 | 3,517 |
| `syn_successor_v2_missing_discriminator` | 9,145 | 7,921 | 2,584 | 3,453 |
| `syn_successor_v2_detail_vs_subtotal` | 3,822 | 7,560 | 2,584 | 3,311 |
| `syn_successor_v2_adjacent_equal` | 3,724 | 7,556 | 2,580 | 3,307 |
| `syn_successor_v2_adjacent_fx` | 4,066 | 7,624 | 2,624 | 3,359 |
| `syn_successor_v2_optional_missing` | 9,779 | 8,068 | 2,643 | 3,520 |
| `syn_successor_v2_forbidden_neighbour` | 9,875 | 8,069 | 2,644 | 3,521 |
| **Total** | **73,970** | **78,621** | **26,211** | **34,389** |

The preserved candidate proof and additive GOAL 10 acceptance accounting are:

```text
ROOT_BLOCKS: 5_EXACT
SOURCE_LITERAL_OCCURRENCES: 45_EXACT
CHOICES: 12_EXACT
COMPILED_BINDINGS: 59_EXACT
VISIBLE_DIFFERENTIATOR_BINDINGS: 0
BACKEND_ONLY_BINDINGS: 59_EXACT
TYPE_CARDS_PER_CASE: 2_EXACT
REASON_CARDS_PER_CASE: 3_EXACT
ACTIVE_PACKET_HASH_PARITY: 10_OF_10_EXACT
ACTIVE_UNCLASSIFIED_RETENTION: EXACT_TOTALITY_PROOF
CONTEXT_V2_1_AGGREGATE_UTF8_BYTES: 26211
CONTEXT_V2_0_HISTORICAL_AGGREGATE_UTF8_BYTES: 78621
REDUCTION_VS_V2_0_UTF8_BYTES: 52410
REDUCTION_VS_V2_0_PERCENT: 66.66
PER_CASE_SMALLER_THAN_ACTIVE: 10_OF_10
CONTEXT_AGGREGATE_TARGET_BYTES: PASSED_LE_30000
CONTEXT_CANDIDATE_PER_CASE_TARGET_BYTES: 10_OF_10_LE_4500
SEALED_REQUESTS: 10_EXACT
SEALED_REQUEST_MAX_UTF8_BYTES: 3522
SEALED_REQUEST_LIMIT_UTF8_BYTES: 4500
SEALED_REQUESTS_WITHIN_LIMIT: 10_OF_10
SEALED_REQUEST_AGGREGATE_UTF8_BYTES: 34389
ESTIMATED_INPUT_TOKENS_AGGREGATE: 9241
SOURCE_OCCURRENCE_MAPPINGS: 45_OF_45
STRUCTURE_MAPPINGS: 20_OF_20
TYPE_MAPPINGS: 20_OF_20
CHOICE_RESTORATIONS: 12_OF_12
MAPPING_ROWS: 156_OF_156
INCLUDED_BINDING_ROWS: 59_OF_59
OPAQUE_GLOBAL_IDS: ZERO
BACKEND_HASHES_IN_MODEL_VIEW: ZERO
DUPLICATE_LITERALS: ZERO
NULL_FIELDS: ZERO
UNUSED_OR_ORPHAN_KEYS: ZERO
UNEXPLAINED_REASON_CODES: ZERO
SEMANTIC_LITERAL_COVERAGE: 100_PERCENT
MAPPING_COVERAGE: 100_PERCENT
PROVIDER_ADAPTER_CHANGES: ZERO
PROVIDER_CALLS: ZERO
FULL_BENCHMARK: NOT_RUN
RUNTIME_ACTIVATION: FALSE
```

The byte boundary covers the exact `messages` plus `response_format` logical
request. The token estimate is recorded under
`compact_request_utf8_bytes_div_4_plus_64_v1`; it is planning evidence, not a
provider tokenizer or admission source of truth.

## 9. Exact sealed provider-neutral request

The existing Context Linter authority's additive `create_context_v2_1` method
consumes:

1. `V6_SEMANTIC_SYSTEM_PROMPT` byte-exact;
2. `packet.context_v2_candidate.payload`;
3. `choice_contract.context_v2_1_response_profile.response_schema`; and
4. `packet.context_v2_mapping_receipt`.

It does not reconstruct any of them. The exact response format is:

```json
{
  "type": "json_schema",
  "json_schema": {
    "strict": true,
    "schema": {}
  }
}
```

The empty object above is a contract metavariable for the inserted exact
Choice-owned schema. It is not emitted literally. `json_schema.name`, schema
titles, descriptions and examples are forbidden from the canonical logical
request.

The exact request projection has only:

```text
messages:
  - role: system
    content: <exact Prompt string>
  - role: user
    content: <Context V2.1 serialized as one minified JSON string>
response_format: <exact wrapper above>
```

Model serialization keeps insertion order, original Unicode, no optional
whitespace and finite JSON values. Choice continues to own the canonical
`response_schema_hash` and validates the schema's exact model-order bytes. The
linter pins that exact hash and separately computes the response-format and
complete-request hashes over their exact model-order bytes; it neither changes
nor redefines Choice integrity.

## 10. Private sealed-request receipt

The linter-owned receipt schema is exactly
`broker_reports_gate2_llm_semantic_context_v2_1_sealed_request_receipt_v1`.
Its request profile is exactly
`broker_reports_gate2_financial_semantic_v6_request_v2_1_candidate`.
The closed top-level field order is:

```text
schema_version
policy_version
request_profile
mapping_receipt_integrity_hash
context_view_hash
system_prompt_version
system_prompt_hash
local_response_profile_identity
response_schema_hash
response_format_hash
model_visible_request_hash
model_visible_utf8_bytes
token_estimator_id
estimated_input_tokens
invariant_counters
status
provider_calls_total
integrity_hash
```

`invariant_counters` is closed:

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

Every zero-target counter must be zero. Each covered total must equal its
denominator. `model_visible_utf8_bytes` must be at most `4 500`, both private
receipt integrity hashes must validate, and `status` must be `passed`.
Construction fails closed instead of issuing a transport-eligible request on
any mismatch or budget overflow. The receipt references the private mapping
receipt by integrity hash and never duplicates its private rows.

## 11. GOAL 11 local provider proof

GOAL 11 keeps this contract inactive and composes existing owners for OpenAI,
Anthropic and Google:

```text
Context V2.1 -> linter -> request builder -> provider adapter projection
-> simulated response -> adapter extraction -> V2.1 Choice restoration
-> candidate-only Expansion -> canonical validation/materialization
-> exact private evidence serialize/restore -> offline evidence replay
-> Financial Domain persistence/restore and replay reconstruction
-> transparent report projection
```

All three adapters pass the four governed semantic fixtures. Provider-visible
`choice` and `reason` enums are preserved, including Gemini projection. The
additive projection behavior is bound to
`broker_reports_gate2_context_v2_1_local_schema_projection_v1` in every
prepared request, private-evidence authority set, replay and report. Canonical
adapter versions are not relabelled because this policy is non-active,
request-shape-specific proof identity; any future transport activation must
carry and qualify it explicitly. The
third reason is admitted only by the explicit V2.1 candidate path; active V6
Choice schema/hash stays unchanged during the proof. Provider calls, repair,
fallback, retry and runtime activation are zero.

The candidate-only adapter entrypoint accepts exactly one terminal provider
envelope: `finish_reason=stop` for OpenAI/Google or `stop_reason=end_turn` for
Anthropic. It then rebuilds the complete expected provider request through the
canonical request builder and repository adapter and requires exact equality.
Legacy active `extract_content` behavior is unchanged.

Replay does not rerun the coordinator from its original Python inputs. It
restores the serialized exact private evidence, parses the preserved adapter
output again, and checks its profile, adapter, projection-policy, exact final
request and provider-visible schema against the freshly reconstructed trusted
projection before expansion, materialization and snapshot reconstruction.
Resealing drifted private fields and their hashes therefore fails closed.

Public
`Gate2FinancialSemanticV6TransparentSmokeReportFactory.create_context_v2_1_provider_case`
returns only a raw closed projection and has no evidence-minting authority.
`Gate2FinancialSemanticV6ContextV21ProviderProofFactory.create_case` incorporates
that projection into an unissued full proof, independently recomputes the same
unissued proof from the governed inputs and requires exact equality. Only then
may its private authority issue one opaque immutable case-evidence token.
Independent canonical full-proof validation follows. The repository-safe
aggregate accepts only the issued token, never a raw or resealed proof
dictionary. When projected, the token revalidates its closed field sets,
integrity hash, four frozen GOAL 10 `model_visible_request_sha256` baselines,
governed expected answers, repository provider tuple and field comparison
before producing the 12-case aggregate.

Exact synthetic requests, schemas, extracted outputs and field-level diffs are
published in the [GOAL 11 transparent report](../../reports/2026-07-29/BROKER_REPORTS_GATE2_CONTEXT_V2_1_THREE_PROVIDER_LOCAL_PROOF_GOAL11.transparent.json);
the [safe receipt](../../reports/2026-07-29/BROKER_REPORTS_GATE2_CONTEXT_V2_1_THREE_PROVIDER_LOCAL_PROOF_GOAL11.receipt.safe.json)
contains only hashes and aggregate accounting.

**STOP before GOAL 12:** no live provider smoke is authorized until the GOAL 11
PR is fresh-reviewed on its immutable head, the real `broker-reports-ci` check
is green and the PR is merged.
