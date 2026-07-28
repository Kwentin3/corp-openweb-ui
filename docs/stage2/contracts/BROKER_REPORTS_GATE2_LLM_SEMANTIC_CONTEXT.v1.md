# Broker Reports Gate 2 LLM Semantic Context v1

Status: `NORMATIVE_TARGET_GOAL1_VIEW_IMPLEMENTED_NOT_ACTIVE`

Contract identity:
`broker_reports_gate2_llm_semantic_context_v1`

## Purpose

This contract defines the complete information boundary that a future Gate 2
financial semantic request may expose to an LLM.

The backend keeps the complete Evidence Bundle, Candidate Compilation, Typed
Options, exact refs, bindings, provenance and integrity evidence. The model
receives only the readable evidence and semantic distinctions needed to choose
one local option alias or the explicit unclassified outcome.

This GOAL defines the contract only. It does not change the current V6 packet,
Prompt, Choice, request builder, provider adapter, expansion, validator,
materializer or runtime route. Provider calls are zero.

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

Other authorities remain unchanged:

| Concern | Existing authority |
| --- | --- |
| source literals, structure, refs and provenance | Evidence Bundle |
| type and role meaning | Financial Semantic Pack |
| complete canonical options and bindings | Candidate Compiler and Typed Option |
| canonical current response | V6 Choice |
| provider request construction | `Gate2OpenWebUIRequestBuilder.build` |
| provider projection and parsing | provider adapters |
| canonical choice expansion | V6 Decision Expansion |
| acceptance and records | validator and materializer |

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
option ID. Replacing this current V6 behavior requires the separate versioned
Choice candidate in GOAL 2.

## Relationship to the staged program

| Stage | Contract relationship |
| --- | --- |
| GOAL 0 | defines this target; runtime remains unchanged |
| GOAL 1 | implemented an inactive Slim View and receipt inside the existing packet owner; the active payload/hash and current Choice remain unchanged, so full conformance is not yet claimed |
| GOAL 2 | separately versions local Choice aliases and proves canonical expansion parity; only then can the full local request reach zero opaque IDs |
| GOAL 3 | enforces this contract with a pre-transport linter and totality proof |
| GOAL 4+ | records actual provider tokens and semantic evidence only where calls are explicitly authorized |
| GOAL 8 | may activate exactly one qualified conforming context under a separate decision |

No earlier stage may claim the acceptance of a later one.

## GOAL 1 implementation status

`Gate2FinancialSemanticV6PacketFactory.create` now returns:

1. the unchanged active V6 packet;
2. `Gate2FinancialSemanticV6SlimViewCandidate` with `active=False`;
3. `Gate2FinancialSemanticV6SlimAliasReceipt`, available only as private
   code-owned evidence.

The candidate uses local value, structural and type aliases. Exact source and
type IDs, lineage, option bindings and deterministic-reference values remain
in the receipt and existing authorities. Exact `return_id` is still visible
because the active V6 Choice requires it; this is the one explicit transition
exception and keeps full Context v1 conformance blocked until GOAL 2.

Across the 10 frozen semantic cases:

```text
ACTIVE_PACKET_HASH_PARITY: 10_OF_10_EXACT
ACTIVE_PACKET_UTF8_BYTES: 73970
SLIM_VIEW_UTF8_BYTES: 18938
PROJECTED_VIEW_BYTE_REDUCTION: 74.4_PERCENT
CURRENT_REQUEST_ESTIMATOR_TOTAL: 22950
SLIM_WITH_CURRENT_CHOICE_ESTIMATOR_TOTAL: 8163
PROJECTED_ESTIMATOR_REDUCTION: 64.4_PERCENT
SLIM_ACTIVE: FALSE
PROVIDER_CALLS: ZERO
```

The estimator comparison is analysis-only: it keeps the exact current Prompt,
model and Choice response format and replaces only the user-message view. It
does not create a request route or authorize transport.

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
ACTIVE_PACKET_HASH_PARITY: EXACT
```
