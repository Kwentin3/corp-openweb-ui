# Broker Reports Gate 2 LLM Semantic Context v1

Status: `GOAL3_PRETRANSPORT_LINTER_IMPLEMENTED_NOT_ACTIVE`

Contract identity:
`broker_reports_gate2_llm_semantic_context_v1`

## Purpose

This contract defines the complete information boundary that a future Gate 2
financial semantic request may expose to an LLM.

The backend keeps the complete Evidence Bundle, Candidate Compilation, Typed
Options, exact refs, bindings, provenance and integrity evidence. The model
receives only the readable evidence and semantic distinctions needed to choose
one local option alias or the explicit unclassified outcome.

GOAL 3 implements this boundary for one non-active Slim request profile. It
adds a fail-closed pre-transport Context Linter and sealed request receipt
without changing the current V6 packet, Prompt text, active Choice, provider
adapter, expansion, validator, materializer or runtime route. Provider calls
are zero.

## Conformance boundary

For this contract, the **complete model-visible request** includes:

1. all system and user message content supplied for the semantic decision;
2. all semantic context supplied through any request field;
3. the response schema, enums and descriptions that constrain the model.

Transport headers, provider metadata and the raw provider envelope are not
model-visible, but remain private code-owned evidence.

A request is conforming only when every model-visible surface satisfies this
contract. A short user message does not compensate for opaque IDs embedded in
the response schema.

## Architecture owner

`Gate2FinancialSemanticV6PacketFactory.create` remains the sole construction
owner for the current packet and any non-active context candidate derived from
the same validated inputs.

The owner may later construct, inside the existing V6 packet module:

- the unchanged active V6 packet;
- one non-active context candidate;
- one private alias receipt.

It must not create or delegate to a second packet builder, Candidate Compiler,
financial-semantic registry or provider-side semantic rewrite.

Current authorities and the one planned ownership slot remain fixed:

| Concern | Authority/placement | Current status |
| --- | --- | --- |
| source literals, structure, refs and provenance | Evidence Bundle | existing |
| type and role meaning | Financial Semantic Pack | existing |
| closed decision-reason codes and response shape | V6 Choice/decision contracts | existing |
| human-readable decision-reason meaning | [Financial Decision Reason Catalog v1](./BROKER_REPORTS_GATE2_FINANCIAL_DECISION_REASON_CATALOG.v1.md) in the existing managed OpenWebUI Financial Domain asset family | versioned repository draft present; inactive and not model-visible |
| complete canonical options and bindings | Candidate Compiler and Typed Option | existing |
| canonical current response | V6 Choice | existing |
| complete candidate request lint and seal | V6 Context Linter | existing |
| provider request construction | `Gate2OpenWebUIRequestBuilder.build` | existing |
| provider projection and parsing | provider adapters | existing |
| canonical choice expansion | V6 Decision Expansion | existing |
| acceptance and records | validator and materializer | existing |

The packet owner is a deterministic renderer, not a semantic-content author.
Context V2 must project type wording from the Pack and reason wording from the
single managed catalog. It may shorten or arrange those meanings under this
contract, but must not copy independent wording into the packet module, Prompt,
runner, provider adapter or report projector. The current code-owned V6 Prompt
and active packet remain unchanged until a separately qualified activation.
The catalog draft alone does not prove compatibility with frozen V6 expected
answers; that audit remains a prerequisite to a model-visible Context V2.

## Core invariants

### 1. Opaque machine IDs are never model-visible

The complete conforming request contains zero global refs, storage IDs,
content hashes, canonical option IDs or other machine identities whose text
does not convey financial meaning.

Closed semantic enums such as `no_registry_type`, readable role names such as
`amount`, and local aliases such as `v1` or `A` are not opaque global IDs.
They are allowed only for the bounded meanings defined below.

### 2. Every authoritative semantic literal appears exactly once

Every Evidence Bundle source value that carries model-relevant semantic
content has exactly one rendered occurrence linked by the private receipt to
its exact `source_value_ref`.

An exact literal must not be repeated in option bindings, summaries, type
cards or another context block. Two distinct source values may legitimately
contain equal text; they remain two structurally distinct authoritative
occurrences and are not collapsed.

Deterministic-reference values whose literal is itself an opaque machine
identity remain code-only. Their structural meaning is represented by a local
group or location alias and their exact value remains in the Evidence Bundle,
Typed Option and private receipt.

### 3. Null fields are omitted

No model-visible object contains a JSON `null`. A missing authoritative
optional value is represented by field omission, never by a placeholder,
empty label or invented hierarchy.

### 4. Structure is readable and evidence-derived

The view represents the available hierarchy as:

```text
document
  → section and/or table
    → row and/or text segment
      → authoritative values
```

Only hierarchy levels and labels proven by Evidence Bundle association or
lineage may be rendered. Missing levels are omitted. The renderer must not
invent a page, section, table, row, segment, label, role or relationship.

### 5. Aliases are local, total and disposable

Aliases:

- are deterministic within one exact request;
- are unique within their namespace;
- resolve bijectively to exact code-owned identities in the private receipt;
- do not become financial, persistence or provenance identifiers;
- are never reused across requests as stable identity;
- are never accepted without the exact request-bound mapping;
- are not stored in canonical materialized records.

Permitted namespaces are:

| Concept | Form |
| --- | --- |
| structural section | `s1`, `s2`, ... |
| table | `t1`, `t2`, ... |
| row | `r1`, `r2`, ... |
| text segment | `seg1`, `seg2`, ... |
| evidence group fallback | `g1`, `g2`, ... |
| source value | `v1`, `v2`, ... |
| visible type card | `T1`, `T2`, ... |
| selectable option | `A`, `B`, ... |

### 6. Semantic metadata is preserved

The model-visible view retains:

- the exact semantic selection instruction;
- every model-relevant exact source literal and its technical value type;
- every non-null visible label, column meaning, row role and section role;
- readable evidence-derived structure;
- Pack-owned short meaning for every represented type;
- Pack-owned distinctions needed to contrast represented types;
- Pack-owned ambiguity or mandatory-unclassified guidance;
- readable role-to-local-alias bindings for every selectable option;
- explicit allowed unclassified reasons.

The view may shorten identifiers and remove duplicated administration. It may
not weaken, broaden, infer or rewrite financial meaning.

### 7. Technical complexity remains code-owned

The model does not own or reconstruct:

- exact refs or provenance;
- role completeness;
- source-family compatibility;
- canonical option identity;
- canonical bindings;
- retention;
- record IDs;
- integrity;
- validation;
- materialization.

The model returns only a local semantic choice. Code resolves that choice
through the request-bound alias receipt and the existing canonical
authorities.

## Closed model-visible field allowlist

The final conforming view is closed by default. Any field not listed here is
forbidden until a later contract version explains its semantic or structural
value.

| Path or concept | Value |
| --- | --- |
| `task` | one concise semantic selection instruction |
| `source.document` | root readable document container, never a document ref |
| structural node `children[]` | evidence-derived nested section/table/row/segment nodes |
| structural node `alias` | one permitted request-local structural alias |
| structural node `kind` | readable `section`, `table`, `row`, `text segment`, or evidence-derived fallback `evidence group` |
| structural node `label` | exact non-null visible label |
| structural node `section_role` | exact non-null section role |
| structural node `row_role` | exact non-null row role |
| structural node `values[]` | authoritative value occurrences owned by that node |
| value `alias` | request-local `vN` alias |
| value `meaning` | exact non-null column meaning or visible label |
| value `value` | exact authoritative semantic literal |
| value `type` | compact technical value type |
| value `label` | exact non-null visible label when distinct from `meaning` |
| `type_cards[]` | cards only for types represented by visible choices |
| type card `alias` | request-local `TN` alias |
| type card `meaning` | exact Pack-owned short meaning |
| type card `distinctions[]` | Pack-owned contrast rules |
| distinction `against` | local visible type alias or readable external concept |
| distinction `rule` | exact Pack-owned rule |
| type card `unclassified_when` | exact Pack-owned ambiguity rule |
| `choices[]` | readable selectable candidates |
| choice `alias` | request-local `A`, `B`, ... |
| choice `type` | local visible type-card alias |
| choice `bindings[]` | readable `role=local-alias` bindings |
| `unclassified[]` | closed semantic reason-code set |
| response `choice` | local choice alias or `unclassified` |
| response `reason` | required allowed reason only for unclassified |

Empty `choices` is allowed. Empty structural containers must be omitted.
Field order and alias assignment order are deterministic and version-pinned by
the eventual implementation.

## Forbidden model-visible fields and values

The following are forbidden anywhere in messages, response schema enums or
descriptions:

- `source_value_ref`, `association_ref`, `evidence_ref`, `provenance_ref`;
- package, bundle, normalization-run, document, scope or source-family refs;
- page, table, row, cell or text-segment global refs;
- `typed_option_id`, canonical `option_id` and option integrity identity;
- canonical `input_type_id` and Pack/Registry identity;
- schema, policy, prompt, packet, view, receipt or content hashes;
- storage IDs, artifact refs, provider response IDs and repository paths;
- provider metadata, expected answers, hidden reasoning and audit envelopes;
- complete required/optional role administration;
- compilation, materializability or validation receipts;
- null fields;
- summaries that restate a literal, binding or relationship already visible;
- any field whose semantic or structural value is not documented in the
  allowlist.

Field-name scans are necessary but not sufficient. A global ref placed under
an allowed key such as `label` is still forbidden.

## Private alias receipt

The request-bound receipt is never model-visible. It contains at least:

```text
context_contract_identity
active_packet_hash
candidate_view_hash
choice_candidate_schema_hash, when one exists
value alias → exact source_value_ref
structural alias → exact association and lineage refs
type alias → exact input_type_id
choice alias → exact typed_option_id
code-only deterministic-reference values
exact role bindings for every choice
integrity_sha256
```

Receipt validation fails closed on collision, missing mapping, extra mapping,
wrong source scope, wrong option, changed ordering, hash mismatch or tampered
content.

The receipt never replaces the Evidence Bundle, Candidate Compilation or Typed
Option. It is only a deterministic request-local index into those
authorities.

## Measurement contract

The packet-owner candidate records:

- exact minified model-visible UTF-8 bytes;
- exact counts for semantic literals, structural nodes and choices;
- duplicate authoritative occurrences;
- null fields;
- opaque IDs;
- mapped, unmapped and orphan aliases;
- candidate-view and receipt hashes.

The request/linter authority records the repository estimator name and result
only after the candidate view, Prompt and versioned Choice schema are assembled
into one complete non-active request. The packet factory must not duplicate or
call downstream Prompt, Choice or request-builder authorities merely to
estimate them.

When a GOAL explicitly permits provider calls, evidence additionally records:

- provider-reported actual input and output tokens;
- exact token-source fields normalized by the existing adapter;
- latency and cost under the existing budget/evidence authority.

GOAL 0 performs no provider call, so it cannot report actual provider tokens.
It defines the mandatory future measurement boundary instead.

## Contract examples

### Conforming target input

This synthetic example defines the target information boundary. It is not an
active request and does not define the separate Choice candidate schema:

```json
{
  "task": "Select a typed option only when the visible source uniquely supports its complete prebound record; otherwise select unclassified.",
  "source": {
    "document": {
      "children": [
        {
          "alias": "t1",
          "kind": "table",
          "children": [
            {
              "alias": "r1",
              "kind": "row",
              "role": "fact_candidate",
              "values": [
                {
                  "alias": "v1",
                  "meaning": "amount",
                  "value": "-120.5000",
                  "type": "decimal"
                },
                {
                  "alias": "v2",
                  "meaning": "currency",
                  "value": "RUB",
                  "type": "currency"
                },
                {
                  "alias": "v3",
                  "meaning": "reporting date",
                  "value": "2026-03-01",
                  "type": "date"
                },
                {
                  "alias": "v4",
                  "meaning": "description",
                  "value": "Cash balance",
                  "type": "text"
                }
              ]
            }
          ]
        }
      ]
    }
  },
  "type_cards": [
    {
      "alias": "T1",
      "meaning": "A source-stated cash-class balance for an explicit statement scope and reporting date. Restricted or segregated balances are excluded unless the source explicitly classifies them as ordinary cash.",
      "distinctions": [
        {
          "against": "T2",
          "rule": "Use this type only when ordinary cash-class state semantics are explicit; a printed total without that classification remains a printed metric or unclassified."
        },
        {
          "against": "cash movement",
          "rule": "A movement is an event over time; this type is a state at one reporting date."
        }
      ],
      "unclassified_when": "Choose unclassified when ordinary versus restricted or segregated status is unclear. Choose unclassified when reporting date, statement scope, or currency or unit cannot be bound to exact source refs. A cash-like label alone is insufficient without a source-stated amount and state context."
    },
    {
      "alias": "T2",
      "meaning": "A financial total or metric printed by the source for an explicit reporting scope and date or period. It remains distinct from every aggregate calculated by Gate 2.",
      "distinctions": [
        {
          "against": "T1",
          "rule": "A printed total is not a cash balance unless ordinary cash-class state semantics are explicit."
        },
        {
          "against": "Gate 2 calculated aggregate",
          "rule": "This type preserves a total printed by the source; a value calculated by Gate 2 is never this type."
        }
      ],
      "unclassified_when": "Choose unclassified when the printed label cannot be bound to exact evidence. Choose unclassified when neither a date nor period or the statement scope can be bound. Do not infer that a visually emphasized or last row is a printed total."
    }
  ],
  "choices": [
    {
      "alias": "A",
      "type": "T2",
      "bindings": [
        "amount=v1",
        "as_of_date=v3",
        "currency=v2",
        "printed_label_evidence_ref=r1",
        "source_label=v4",
        "statement_scope=r1"
      ]
    },
    {
      "alias": "B",
      "type": "T1",
      "bindings": [
        "amount=v1",
        "as_of_date=v3",
        "currency=v2",
        "statement_scope=r1"
      ]
    }
  ],
  "unclassified": [
    "ambiguous_registry_type",
    "no_registry_type"
  ]
}
```

The type meanings and rules above are copied from the current Pack projection.
The local aliases and readable external-concept labels illustrate only the
target presentation and do not change Pack identity or meaning.

### Non-conforming examples

```json
{"alias":"v1","value":"100","source_value_ref":"financial-source-value:..."}
```

Forbidden because a global ref is visible.

```json
{"alias":"v1","value":"100","label":null}
```

Forbidden because null fields must be omitted.

```json
{
  "values":[{"alias":"v1","value":"100"}],
  "choices":[{"alias":"A","bindings":["amount=100"]}]
}
```

Forbidden because the authoritative literal is repeated instead of referenced
through `v1`.

```json
{"choice":"financial-typed-option:744e3c95321e39b5f068c13cb76c72ae"}
```

Forbidden by the target contract because the model sees a canonical opaque
option ID. The GOAL 2 Local Choice candidate removes this ID from the
non-active request; the current active V6 route still uses its historical
exact-ID Choice.

## Relationship to the staged program

| Stage | Contract relationship |
| --- | --- |
| GOAL 0 | defines this target; runtime remains unchanged |
| GOAL 1 | implemented an inactive Slim View and receipt inside the existing packet owner; the active payload/hash and current Choice remain unchanged, so full conformance is not yet claimed |
| GOAL 2 | implemented the separate non-active Local Choice, removed `return_id` from Slim v2 and proved zero opaque IDs plus canonical expansion/materialization parity |
| GOAL 3 | implemented a pre-transport linter, sealed receipt, exact replay and totality proof for the non-active candidate request profile |
| GOAL 4 | consumed the exact six-submission Nano/Haiku diagnostic; technical pipeline passed, but Haiku missed the unclassified reason, so acceptance failed and the benchmark remains blocked |
| GOAL 5-7 | conditional research/experiments/benchmark remain unstarted and require their exact prerequisites plus separate authorization |
| GOAL 8 | may activate exactly one qualified conforming context under a separate decision |

No earlier stage may claim the acceptance of a later one.

## GOAL 1-3 implementation status

`Gate2FinancialSemanticV6PacketFactory.create` now returns:

1. the unchanged active V6 packet;
2. Slim View v2 with `active=False`;
3. `Gate2FinancialSemanticV6SlimAliasReceipt`, available only as private
   code-owned evidence.

`Gate2FinancialSemanticV6ChoiceContractFactory.create` also returns the
separate versioned
[Local Choice v1](./BROKER_REPORTS_GATE2_FINANCIAL_SEMANTIC_LOCAL_CHOICE.v1.md)
candidate with `active=False`.

The complete local projection uses only value, structural, type and choice
aliases. Exact source/type/option IDs, lineage, bindings and
deterministic-reference values remain in the receipt and existing authorities.
Across the frozen suite, opaque IDs in exact messages plus response schema are
zero. The candidate request now has a pre-transport invariant; active runtime
conformance remains blocked until a later qualified activation replaces the
historical exact-ID route.

`Gate2FinancialSemanticV6ContextLinterFactory.create` now assembles the exact
Prompt + Slim View + Local Choice projection, verifies the complete
model-visible surface, measures it, seals one request-bound receipt and then
delegates request construction to the existing
`Gate2OpenWebUIRequestBuilder.build`. The builder's versioned
`financial_semantic_v6_slim_linted_v1` profile rejects a missing, stale or
tampered receipt before provider projection or transport.

The linter is a downstream validation authority because the packet owner
cannot inspect the complete Prompt and Choice schema without violating their
separate authorities. It does not build another packet, compile options,
rewrite financial meaning or assemble provider `form_data`.

Across the 10 frozen semantic cases:

```text
ACTIVE_PACKET_HASH_PARITY: 10_OF_10_EXACT
ACTIVE_CHOICE_SCHEMA_HASH_PARITY: 10_OF_10_EXACT
ACTIVE_PACKET_UTF8_BYTES: 73970
SLIM_VIEW_UTF8_BYTES: 18098
CURRENT_COMPLETE_MODEL_VIEW_UTF8_BYTES: 89220
LOCAL_COMPLETE_MODEL_VIEW_UTF8_BYTES: 26404
PROJECTED_COMPLETE_VIEW_BYTE_REDUCTION: 70.4_PERCENT
CURRENT_REQUEST_ESTIMATOR_TOTAL: 22950
SLIM_WITH_LOCAL_CHOICE_ESTIMATOR_TOTAL: 7247
PROJECTED_ESTIMATOR_REDUCTION: 68.4_PERCENT
FULL_MODEL_VISIBLE_OPAQUE_IDS: ZERO
SEMANTIC_LITERAL_COVERAGE: 100_PERCENT
DUPLICATE_LITERALS: ZERO
NULL_FIELDS: ZERO
UNMAPPED_ALIASES: ZERO
ORPHAN_ALIASES: ZERO
ALIAS_COLLISIONS: ZERO
STRUCTURAL_HIERARCHY: VALID
EXACT_OPTION_COVERAGE: COMPLETE
ALIAS_RECEIPT_INTEGRITY: VALID
EXACT_REQUEST_REPLAY: 10_OF_10
LOCAL_OUTPUTS_MATERIALIZED: 32_OF_32
CANONICAL_EXPANSION_MATERIALIZATION_PARITY: EXACT
SLIM_ACTIVE: FALSE
LOCAL_CHOICE_ACTIVE: FALSE
LINTED_REQUEST_PROFILE_ACTIVE_IN_PRODUCT_RUNTIME: FALSE
PROVIDER_CALLS: ZERO
```

The measurement keeps the exact current Prompt text and replaces the user
view plus response schema together. GOAL 3 creates a sealed qualification-only
request profile, but does not call a provider, authorize a model, switch the
current qualification runner or activate a product runtime route.

The representative typed case produces:

```text
MODEL_VISIBLE_REQUEST_HASH: 02f69b3767139407a8ae0b7d45af24ebeec903e467f08ea838c21d69ded284d8
MODEL_VISIBLE_UTF8_BYTES: 3427
REPOSITORY_ESTIMATED_INPUT_TOKENS: 921
LINT_RECEIPT_INTEGRITY: 45c5d63f0fe6f5a72a4a7b62439b2099eb9b663a56a6c2fb5203d9cca69c9668
LOCAL_TOTALITY_INTEGRITY: 3e41ebc9dbc0a907e7d5ebda5a8de47632eae60ff3019fd39180de7b21c6b64f
```

The private alias receipt and its exact refs remain outside the model-visible
projection. The lint receipt contains only hashes, counts, booleans and
measurement identity; it is request metadata, not model context.

## GOAL 4 terminal model evidence

The one bounded diagnostic used the same Prompt, type meanings, two frozen
cases and expected answers for all cells. Only the exact model candidate
changes between Nano and Haiku; the separate Nano permutation changes only the
typed-choice order and deterministic alias mapping. Six submissions and six
responses completed through the canonical structured client with zero
fallback, repair or hidden retry.

```text
TECHNICAL_PIPELINE: PASSED
HAIKU_TYPED: PASSED
HAIKU_UNCLASSIFIED: FAILED_WITH_EXACT_EVIDENCE
NANO_SLIM_TYPED: FAILED_WITH_EXACT_EVIDENCE
NANO_SLIM_UNCLASSIFIED: FAILED_WITH_EXACT_EVIDENCE
NANO_REVERSED_TYPED: FAILED_WITH_EXACT_EVIDENCE
NANO_REVERSED_UNCLASSIFIED: PASSED
ACTUAL_INPUT_TOKENS_TOTAL: 4753
ACTUAL_OUTPUT_TOKENS_TOTAL: 130
ACTUAL_COST_USD: 0.002818900
LATENCY_TOTAL_MS: 28095
FULL_BENCHMARK: NOT_RUN
```

Haiku selected the correct typed alias `B` but returned
`ambiguous_registry_type` instead of `no_registry_type` for the unsupported
broker-fee case. Nano returned unclassified for the typed cash case in both
orders; it did not follow the first typed option. Nano's unclassified reason
was wrong in canonical order and correct after the order permutation, so its
result is mixed/order-sensitive rather than an order-independent type-card
failure.

The exact input shows the narrow contract gap: the response enum exposes both
unclassified reason labels, but the readable context does not define when
none of the visible registry types applies versus when multiple types are
plausible. This is evidence for `UNCLASSIFIED_RULE_UNCLEAR`, not permission to
change Prompt, Semantic Pack, type meaning or the provider adapter.

The immutable
[safe receipt](../../reports/2026-07-28/BROKER_REPORTS_GATE2_LLM_CONTEXT_GOAL4_SLIM_MODEL_DIAGNOSTIC.receipt.safe.json)
and
[detailed report](../../reports/2026-07-28/BROKER_REPORTS_GATE2_LLM_CONTEXT_GOAL4_SLIM_MODEL_DIAGNOSTIC.report.md)
preserve all six exact synthetic inputs, adapter-extracted outputs, normalized
answers, diffs and actual metrics. GOAL 5's published prerequisite is not met,
and GOAL 7 is blocked.

## Acceptance

```text
CONTRACT_IDENTITY: broker_reports_gate2_llm_semantic_context_v1
FIELD_ALLOWLIST: CLOSED_AND_EXPLICIT
FORBIDDEN_FIELDS: CLOSED_AND_EXPLICIT
OPAQUE_MACHINE_IDS_TARGET: ZERO
AUTHORITATIVE_SEMANTIC_LITERAL_OCCURRENCES: EXACTLY_ONCE
NULL_FIELDS_TARGET: ZERO
HIERARCHY: EVIDENCE_DERIVED_AND_READABLE
ALIASES: LOCAL_BIJECTIVE_AND_DISPOSABLE
SEMANTIC_METADATA: PRESERVED
CODE_ONLY_COMPLEXITY: EXPLICIT
SIZE_MEASUREMENT: REQUIRED
ACTUAL_PROVIDER_TOKENS: REQUIRED_WHEN_CALLS_ARE_AUTHORIZED
CURRENT_RUNTIME_CHANGED: NO
CURRENT_CHOICE_CHANGED: NO
SECOND_PACKET_BUILDER: ZERO
PROVIDER_CALLS: ZERO
GOAL1_SLIM_CANDIDATE: IMPLEMENTED_NOT_ACTIVE
GOAL2_LOCAL_CHOICE_CANDIDATE: IMPLEMENTED_NOT_ACTIVE
GOAL3_CONTEXT_LINTER: IMPLEMENTED_PRETRANSPORT
GOAL3_EXACT_REPLAY: PASSED
GOAL3_LOCAL_TOTALITY: 32_OF_32
LOCAL_FULL_REQUEST_OPAQUE_IDS: ZERO
ACTIVE_PACKET_HASH_PARITY: EXACT
ACTIVE_CHOICE_SCHEMA_HASH_PARITY: EXACT
ACTIVE_RUNTIME_ROUTE_CHANGED: NO
```
