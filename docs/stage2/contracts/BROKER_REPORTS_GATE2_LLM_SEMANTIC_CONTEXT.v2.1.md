# Broker Reports Gate 2 LLM Semantic Context V2.1

Status: `IMPLEMENTED_NON_ACTIVE_CONTEXT_AND_CHOICE_RESPONSE_PROFILE`

Contract identity:
`broker_reports_gate2_llm_semantic_context_v2_1`

Contract version: `2.1.0`

Policy identity: `broker_reports_gate2_minimal_model_surface_v1`

Runtime activation: `false`

Transport eligible: `false`

Response profile:
`broker_reports_gate2_financial_semantic_context_v2_1_choice_response_profile_v1`

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

The candidate is not part of `packet.payload`. The existing Choice authority is
its only consumer and builds one separately versioned inactive response
profile. No request builder, Prompt, provider adapter, runtime route,
persistence path, replay path or qualification runner consumes it.

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
| complete-request lint | existing Context Linter owner | no V2.1 lint profile exists |

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

The current ten frozen semantic cases prove:

| Case | Active V6 bytes | Historical V2.0 bytes | Context V2.1 bytes |
| --- | ---: | ---: | ---: |
| `syn_successor_v2_unique_cash` | 9,638 | 8,070 | 2,645 |
| `syn_successor_v2_unique_printed_total` | 9,905 | 8,068 | 2,643 |
| `syn_successor_v2_multiple_compatible` | 4,246 | 7,620 | 2,624 |
| `syn_successor_v2_no_registry_type` | 9,770 | 8,065 | 2,640 |
| `syn_successor_v2_missing_discriminator` | 9,145 | 7,921 | 2,584 |
| `syn_successor_v2_detail_vs_subtotal` | 3,822 | 7,560 | 2,584 |
| `syn_successor_v2_adjacent_equal` | 3,724 | 7,556 | 2,580 |
| `syn_successor_v2_adjacent_fx` | 4,066 | 7,624 | 2,624 |
| `syn_successor_v2_optional_missing` | 9,779 | 8,068 | 2,643 |
| `syn_successor_v2_forbidden_neighbour` | 9,875 | 8,069 | 2,644 |
| **Total** | **73,970** | **78,621** | **26,211** |

Acceptance facts:

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
AGGREGATE_TARGET_BYTES: PASSED_LE_30000
CONTEXT_CANDIDATE_PER_CASE_TARGET_BYTES: 10_OF_10_LE_4500
LOGICAL_REQUEST_FEASIBILITY_TARGET_BYTES: FEASIBILITY_ONLY_LE_4500
SEALED_REQUEST_TARGET_BYTES: NOT_PROVEN_GOAL10_NOT_IMPLEMENTED
PROVIDER_CALLS: ZERO
FULL_BENCHMARK: NOT_RUN
RUNTIME_ACTIVATION: FALSE
```

The earlier contract-derived maximum complete logical request envelope was
3,522 UTF-8 bytes for the current cases, within the 4,500-byte target. That
remains a historical local feasibility calculation only. GOAL 9 now provides
the required inactive Choice-owned V2.1 response profile, but no executable
sealed V2.1 request or linter profile exists and nothing was sent to a
provider. No sealed-request budget pass is claimed.

The two size comparisons are acceptance oracles for the governed current
two-type suite, not constructor rejection policy for unrelated historical or
future inputs. GOAL 10 owns the complete-request linter and budget guard after
the reviewed, green GOAL 9 PR is merged.

## 9. Current stop

GOAL 8 implemented only the candidate and private receipt. The later
separately authorized GOAL 9 adds the inactive
[Local Choice V2.1](./BROKER_REPORTS_GATE2_FINANCIAL_SEMANTIC_LOCAL_CHOICE.v2.1.md)
response profile and parser through the existing Choice owner. GOAL 9 does not
implement:

- a V2.1 Context Linter profile;
- a sealed request-builder profile;
- provider projection or transport;
- persistence, replay, qualification or activation;
- a full benchmark run.

**STOP before GOAL 10:** do not start the linter/sealed-request goal until the
GOAL 9 PR has a fresh review on its immutable head, a real green GitHub Actions
check and is merged.
