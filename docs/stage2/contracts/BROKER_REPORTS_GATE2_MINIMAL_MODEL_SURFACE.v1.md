# Broker Reports Gate 2 Minimal Model Surface v1

Status: `ACCEPTED_NON_ACTIVE_SURFACE_WITH_V2_1_SEALED_REQUEST_PROFILE`

Contract identity:
`broker_reports_gate2_minimal_model_surface_v1`

Contract version: `1.0.0`

Target context revision: `2.1`

Implementation status (2026-07-29): GOAL 7 implements the exact managed
Pack/reason mappings from section 6 as the inactive profile documented by
[Financial Domain Asset Family v3](./BROKER_REPORTS_OPENWEBUI_FINANCIAL_DOMAIN_ASSET_FAMILY.v3.md).
GOAL 8 implements the sole current non-active
  [Context V2.1](./BROKER_REPORTS_GATE2_LLM_SEMANTIC_CONTEXT.v2.1.md)
  Packet candidate and its private exact mapping receipt in the existing Packet
  factory. GOAL 9 implements the separately versioned inactive
  [Local Choice V2.1 response profile](./BROKER_REPORTS_GATE2_FINANCIAL_SEMANTIC_LOCAL_CHOICE.v2.1.md)
  in the existing Choice factory. GOAL 10 implements the provider-neutral
  complete-request linter and sealed request receipt in the existing Context
  Linter factory. Provider request routing and activation remain unimplemented.

## 1. Purpose and scope

This contract defines the smallest Gate 2 semantic decision surface that a
model may see. For every visible field it applies one test:

> Can omission of this field change the correct semantic choice?

If the answer is no, the field is not model-visible.

This is a field-eligibility and necessity contract inside the existing
Semantic Matcher boundary. It does not create a packet, Pack, reason, Choice,
Prompt, linter, provider or materialization authority.

The implemented
[LLM Semantic Context V2.0](./BROKER_REPORTS_GATE2_LLM_SEMANTIC_CONTEXT.v2.md)
remains an exact, non-active historical completeness baseline. This contract
supersedes V2.0 as the target model surface for the current non-active V2.1
candidate. It does not rewrite V2.0 bytes, evidence or receipts.

GOAL 5 does not:

- change runtime or any active/non-active packet bytes;
- implement the managed minimal projection;
- implement Context V2.1, a response profile or a linter;
- change the Prompt, expected answers or outcome taxonomy;
- call a provider, run a benchmark or admit a model;
- publish or activate a managed asset.

## 2. Existing authorities remain sole

| Concern | Sole authority | Minimal-surface rule |
| --- | --- | --- |
| source facts and real document structure | validated [Evidence Bundle](./BROKER_REPORTS_GATE2_FINANCIAL_EVIDENCE_BUNDLE.v1.md) | exact readable projection only |
| financial type meaning | [Financial Semantic Pack](./BROKER_REPORTS_FINANCIAL_SEMANTIC_PACK.v1.md) | GOAL 7 must expose one versioned minimal managed projection |
| human reason meaning | [Financial Decision Reason Catalog](./BROKER_REPORTS_GATE2_FINANCIAL_DECISION_REASON_CATALOG.v1.md) | GOAL 7 must expose one versioned minimal managed projection after the GOAL 6 taxonomy decision |
| exact Typed Options and bindings | Candidate Compilation and Typed Option authorities | stay private; only choice differences may be rendered |
| context construction and private mapping | existing `Gate2FinancialSemanticV6PacketFactory.create` | GOAL 8 implements one non-active V2.1 candidate plus one private exact receipt in this owner only |
| response schema and normalization | existing V6 Choice authority | GOAL 9 implements one inactive versioned V2.1 profile without changing active V6 |
| complete-request lint | existing Context Linter authority | additive `create_context_v2_1` seals the inactive provider-neutral V2.1 request; historical `create` remains unchanged |
| provider projection and parsing | existing provider adapters | transport-only; unchanged by GOAL 5 |

The existing V5-named shared Pack projection owner remains the only projection
owner. GOAL 7 added one versioned profile there; it did not add another
loader, Pack, catalog, packet builder or adapter-owned semantic dictionary.

The governing GOAL 8 slice authorized only the Packet candidate and private
mapping receipt. The later Context V2.1 Qualification And Admission program
separately authorizes GOAL 9 to add the versioned inactive response profile in
the existing Choice authority and GOAL 10 to add the provider-neutral sealed
request through the same linter authority. Neither changes the active route.

## 3. Closed V2.1 semantic payload shape

The implemented non-active V2.1 user-content object has exactly these ordered
root fields:

1. `task`;
2. `source`;
3. `type_cards`;
4. `choices`;
5. `unclassified_reasons`.

The closed shape is:

```json
{
  "task": "<one short decision instruction>",
  "source": {
    "children": [
      "<real source nodes only>"
    ]
  },
  "type_cards": [
    {
      "type_key": "type_1",
      "title": "<short managed title>",
      "definition": "<one short managed definition>",
      "positive_signal": "<one primary managed positive signal>",
      "negative_signal": "<one primary managed negative signal>",
      "nearest_competitor": {
        "type_key": "type_2",
        "distinction": "<one managed direct distinction>"
      }
    }
  ],
  "choices": [
    {
      "choice_key": "choice_1",
      "title": "<readable managed title>",
      "differentiators": [
        {
          "role": "<readable managed role>",
          "value_key": "value_1"
        }
      ]
    }
  ],
  "unclassified_reasons": [
    {
      "code": "<allowed reason code>",
      "title": "<short managed title>",
      "use_when": "<one managed sentence>"
    }
  ]
}
```

The example is a grammar illustration, not an implemented payload. Optional
fields and arrays are omitted when their closed conditions below do not hold.
`choices` may be an empty array because zero selectable records is decision
information. No other empty array, empty string, null or placeholder is
allowed in a conforming payload.

The current V2.1 task is exactly one instruction:

```text
Select one choice only when the visible source, type cards, and any shown differentiators uniquely support it; otherwise select unclassified.
```

This wording asks the model to judge only information that remains visible. It
does not ask the model to verify complete backend bindings. If GOAL 6 changes
the outcome taxonomy in a way that makes the instruction inexact, it must
update this contract before GOAL 7. Packet code may not silently reword it.

The exact current system Prompt and strict response-schema protocol stay in
their existing owners. GOAL 5 added no model-visible Prompt/schema prose and
no response field. GOAL 9 now implements the closed request-bound response
schema in the Choice owner. GOAL 10 integrates the unchanged Prompt and that
exact schema with Context V2.1 through additive `create_context_v2_1`, without
provider projection or transport.

## 4. Complete field allowlist and necessity

The complete request allowlist has two parts:

- `P01`–`P18`: canonical provider-neutral protocol fields that deliver and
  constrain one restorable
  semantic answer;
- `M01`–`M32`: semantic user-content fields.

Every path below is allowed only with the stated authority and consumer.
“Yes” answers the governing omission question. A protocol-field omission can
prevent a correct semantic choice from being delivered or constrained. Any
path not listed is model-view forbidden.

### 4.1 Closed request and response protocol

The exact system message remains:

```text
Return exactly one JSON object that conforms to the supplied strict response schema. Use only the task and evidence in the user message.
```

There is no other system/developer message and no schema description prose.

| ID | JSON path or field | Cardinality and authority | Can omission change the correct choice? |
| --- | --- | --- | --- |
| `P01` | system-message exact content | one exact Prompt-owned string | **Yes.** Without the strict one-object/evidence-only instruction, an otherwise correct semantic decision may not be returned in the allowed form. |
| `P02` | request-root `messages` | one two-item array from the request builder | **Yes.** It carries the only instruction and semantic evidence. |
| `P03` | request-root `response_format` | one strict schema wrapper from Choice/provider projection | **Yes.** Without it an invalid key or reason is not fail-closed. |
| `P04` | message-item `role` | exactly `system`, then `user` | **Yes.** It distinguishes instruction from decision evidence. |
| `P05` | message-item `content` | exact Prompt string, then minified semantic payload string | **Yes.** Omission removes either the task boundary or the evidence. |
| `P06` | response-format `type` | exactly `json_schema` | **Yes.** Omission can prevent strict structured output. |
| `P07` | response-format `json_schema` | one closed object | **Yes.** It contains the request-bound response contract. |
| `P08` | `json_schema.strict` | exactly boolean `true` | **Yes.** Without it extra or malformed output can escape the closed choice contract. |
| `P09` | `json_schema.schema` | one request-bound schema object | **Yes.** It carries the allowed local choices and reasons. |
| `P10` | schema-root `anyOf` | typed then unclassified when choices exist; unclassified branch alone otherwise | **Yes.** It preserves safe unclassified output even when selectable records exist. |
| `P11` | branch `type` | exactly `object` | **Yes.** It rejects non-object output. |
| `P12` | branch `additionalProperties` | exactly boolean `false` | **Yes.** It rejects uncontracted semantic fields or repairs. |
| `P13` | branch `properties` | exactly the allowed branch fields | **Yes.** It defines `choice` and conditional `reason`. |
| `P14` | branch `required` | exact branch field set | **Yes.** It prevents a missing choice or missing unclassified reason. |
| `P15` | property `type` | exactly `string` | **Yes.** It closes the scalar response shape. |
| `P16` | property `enum` | exact request-local choice set or allowed reason-code set | **Yes.** It prevents invented identities or reasons. |
| `P17` | model-output `choice` | one allowed `choice_N` or `unclassified` | **Yes.** It is the semantic disposition and restoration key. |
| `P18` | model-output `reason` | one allowed reason code only for `unclassified` | **Yes.** It distinguishes the accepted unclassified outcome. |

Schema `name`, `title`, `description`, examples and provider-added explanatory
fields are absent from the canonical model-visible surface.

`P01`–`P18` describe the provider-neutral logical request, not an OpenAI- or
Anthropic-native transport envelope. GOAL 11 must prove that each exact
provider projection preserves this logical surface and adds no model-visible
semantic content. A provider-required transport name or structural wrapper is
allowed only when that proof establishes it is not model-visible. If the
provider exposes an additional field or prose to the model, the projection
remains non-conforming until a versioned contract amendment justifies it.
GOAL 5 and GOAL 10 claim no provider-profile compatibility.

### 4.2 Closed semantic user content

| ID | JSON path or field | Cardinality and authority | Can omission change the correct choice? |
| --- | --- | --- | --- |
| `M01` | `/task` | one exact instruction from section 3 | **Yes.** Without the operation and safe-unclassified rule, the model cannot know the requested decision. |
| `M02` | `/source` | one object | **Yes.** It separates source evidence from glossary and selectable records. |
| `M03` | `/source/children` | one non-empty Evidence-Bundle-ordered array | **Yes.** Losing the real hierarchy can change which literal belongs to which row or segment. |
| `M04` | source-node `kind` | one of `table`, `row`, `text segment` from real Evidence Bundle association/lineage | **Yes.** Table, row and text context can change semantic interpretation. |
| `M05` | table-node `children` | one non-empty ordered array | **Yes.** It preserves real parent/child grouping. |
| `M06` | row/text-node `values` | one non-empty ordered array | **Yes.** It preserves which facts occur together. |
| `M07` | node `section_role` | optional exact readable Evidence Bundle role, only with a recorded decision consumer | **Yes only when its removal makes two semantic readings remain possible.** Presence alone is insufficient. |
| `M08` | node `row_role` | optional exact readable Evidence Bundle role, only with a recorded decision consumer | **Yes only when its removal makes two semantic readings remain possible.** Generic roles such as `fact candidate` are omitted. |
| `M09` | node `structure_key` | optional request-local `structure_N`; only when a retained differentiator targets that node | **Yes only with that consumer.** Otherwise the key is unused identity and is omitted. |
| `M10` | value `meaning` | one non-empty, decision-sufficient readable Evidence Bundle meaning | **Yes.** A literal without sufficient source meaning can support the wrong financial type. |
| `M11` | value `literal` | one exact authoritative non-reference literal occurrence | **Yes.** It is the source fact being classified. |
| `M12` | value `label` | optional exact visible label, only when omission can change the choice and it differs from `meaning` and `literal` | **Yes only with that recorded consumer.** Distinctness alone is insufficient. |
| `M13` | value `value_key` | optional request-local `value_N`; only when a retained differentiator targets that value | **Yes only with that consumer.** Otherwise the key is unused identity and is omitted. |
| `M14` | `/type_cards` | one non-empty array in the existing authority-derived type order | **Yes.** The model must compare source meaning with available terms even when `choices` is empty. |
| `M15` | type `type_key` | one request-local `type_N` | **Yes.** It gives the nearest-competitor relation an unambiguous local target without exposing a canonical type ID. |
| `M16` | type `title` | one exact short managed title | **Yes.** It makes the type scannable and lets the readable choice title match its glossary term. |
| `M17` | type `definition` | one exact managed definition | **Yes.** The title alone does not close the semantic boundary. |
| `M18` | type `positive_signal` | exact managed `examples[0]` under the mapping in section 6 | **Yes.** It states one concrete primary support signal without exposing the examples array. |
| `M19` | type `negative_signal` | exact managed `counterexamples[0]` under the mapping in section 6 | **Yes.** It states one concrete primary exclusion without exposing the counterexamples array. |
| `M20` | type `nearest_competitor` | required for each of the current two visible types | **Yes.** Either term can otherwise remain plausible for a financial total. |
| `M21` | nearest competitor `type_key` | one existing local type key | **Yes.** It identifies exactly which visible term the distinction compares. |
| `M22` | nearest competitor `distinction` | one exact managed reciprocal direct rule | **Yes.** It supplies the decisive boundary between the two current terms. |
| `M23` | `/choices` | one Candidate-Compiler-ordered array; empty is allowed | **Yes.** It is the complete selectable local-key set, not a plausibility count. |
| `M24` | choice `choice_key` | one request-local `choice_N` | **Yes.** It is the only model-returned identity and restores privately to one exact Typed Option. |
| `M25` | choice `title` | one exact readable managed title | **Yes.** Without it a choice that has no differentiator is only an opaque local key and cannot be mapped to a semantic term. |
| `M26` | choice `differentiators` | optional non-empty array only among otherwise same-title selectable choices | **Yes only when removing it makes two selectable records indistinguishable.** Cross-type binding asymmetry is not a differentiator. |
| `M27` | differentiator `role` | one exact readable Pack role with the consumer proven by `M26` | **Yes.** A target without its semantic relation is ambiguous. |
| `M28` | differentiator target | exactly one of `value_key`, `structure_key` | **Yes.** It identifies the source occurrence that distinguishes otherwise same-title choices. |
| `M29` | `/unclassified_reasons` | one catalog-ordered array with one card per currently allowed semantic reason | **Yes.** The model must distinguish allowed unclassified outcomes. |
| `M30` | reason `code` | one exact Choice/decision-contract code | **Yes.** It is the model-returned reason identity. |
| `M31` | reason `title` | one exact short managed title | **Yes.** It makes the code understandable without schema prose. |
| `M32` | reason `use_when` | exactly one managed sentence under the mapping in section 6 | **Yes.** It states the positive selection boundary for that reason. |

The `source` object deliberately contains `children` directly. The V2.0
`source.document` wrapper contained no field other than `children`; removing
that information-free wrapper does not flatten or alter the real node
hierarchy.

`value_type` is not a separate model field. When scalar kind can change the
choice, the single `meaning` must convey it from existing Evidence Bundle
metadata; if one decision-sufficient exact readable meaning cannot be
projected, construction fails closed. Goal 8 may not solve that failure by
adding a second redundant field without a contract version.

The choice intentionally has no visible `type_key`. For the current two-type
ontology, its exact readable title already identifies the visible glossary
term, while the private mapping binds the choice to its exact type and Typed
Option. A second visible key would not change the correct choice. If future
managed titles cease to identify a term, that is a contract-version problem;
it must not be repaired with opaque identity.

## 5. Source and differentiator rules

### 5.1 Exact source facts

- Every validated Evidence Bundle `source_value` other than
  `source_reference` appears exactly once as one value object.
- The literal is byte-exact. It is never copied into a choice, glossary,
  summary, relationship or label.
- Equal text in two distinct source occurrences remains two occurrences.
- `meaning`, optional `label`, optional structural roles and real
  parent/child order come only from Evidence Bundle authority. Technical
  `value_type` remains backend-only and may only inform the single
  decision-sufficient `meaning`.
- No relevance filter may discard an authoritative non-reference literal.
- A `source_reference` literal is never model-visible.
- A section, group, label, row, table or segment may not be invented.
- The V2.0 fallback `evidence group` is not real document structure and is not
  allowed in V2.1. If a necessary differentiator cannot target a real visible
  value or node through a local key, construction must fail closed.

### 5.2 Consumer-bound local keys

`value_N` and `structure_N` are emitted only for targets of retained
differentiators. Numbering is contiguous in existing authority order and
does not encode a global reference. Exact mappings remain private.

`type_N` and `choice_N` are request-local. They never copy or reversibly encode
`input_type_id`, `typed_option_id`, hashes or source refs.

### 5.3 Only differences enter choices

Compiler blocks, blocked bindings and raw binding asymmetry do not prove type
plausibility or semantic relevance. The renderer first uses the exact managed
titles and type cards. A concrete binding may enter a choice only when all of
these conditions hold:

1. at least two selectable choices have the same visible title;
2. their exact backend records bind different source occurrences;
3. removal of the proposed fact makes those otherwise same-title records
   indistinguishable in the complete visible request;
4. the readable role comes from the Pack and the target comes from the
   Evidence Bundle;
5. the fact appears once and does not copy its source literal.

A binding identical across choices, a binding difference between already
distinct type titles, and a Compiler-only diagnostic remain backend-only.
Full bindings always remain in the private mapping.

With one choice, or with the current title-distinct two-type choice pairs,
`differentiators` is omitted. If a future choice set requires a repeated or
shared proper-subset fact, the current contract fails closed pending a
versioned representation; it does not reintroduce V2.0
`shared_relationships` or `applies_to`.

The renderer does not invent label qualifiers when two choices share a title.
The local keys and exact private mappings stay distinct; semantic uncertainty
remains an unclassified decision rather than a presentation repair.

## 6. Exact managed wording mappings

GOAL 5 selects existing managed strings; it does not author new financial or
reason wording. GOAL 7 must implement these exact rules as one versioned,
integrity-identified profile in the existing shared projection owner.

### 6.1 Type cards

For every currently visible Pack type:

| Minimal field | Exact managed source |
| --- | --- |
| `title` | the type's exact `title` |
| `definition` | the type's exact `definition` |
| `positive_signal` | exact `examples[0]` |
| `negative_signal` | exact `counterexamples[0]` |
| nearest competitor identity | the only other visible type in the current two-type set |
| `nearest_competitor.distinction` | the unique exact `semantic_distinctions[].rule` whose `against` is that other visible type |

Pack array order is normative. GOAL 5 explicitly designates index `0` as the
single primary positive/negative signal for this minimal profile; the arrays
themselves remain backend-only. This is a field-selection rule, not new
wording.

The projection fails closed if either selected array entry is absent/empty,
if the direct reciprocal distinction is missing/non-unique, or if the
visible type set is not exactly the current two-type set. A future larger
ontology requires the later shortlist/ranking contract; GOAL 7 may not infer
a nearest type.

### 6.2 Reason cards

For every reason retained by the GOAL 6 taxonomy:

| Minimal field | Exact managed source |
| --- | --- |
| `code` | exact catalog `code` |
| `title` | exact catalog `human_title` |
| `use_when` | exact first sentence of catalog `meaning` |

“First sentence” means the exact prefix through the first U+002E FULL STOP
that is followed by one ASCII space or end of string. No trim, case change,
normalization, summary or synonym substitution is allowed.

For the current catalog, the exact projected sentences are:

| Code | Exact minimal `use_when` |
| --- | --- |
| `no_registry_type` | `Source-stated financial values are present, but none of the available financial type definitions matches their visible meaning.` |
| `single_registry_type_no_safe_record` | `Exactly one available financial type remains plausible, but the visible source does not uniquely support one complete prebound record for that type.` |
| `ambiguous_registry_type` | `Source-stated financial values are present and two or more distinct available financial type definitions remain plausible after all visible evidence is considered, so no single type can be selected safely.` |

These sentences already exist byte-for-byte in the managed catalog and align
with the visible definitions/source evidence. The current longer `use_when`
field remains backend administration; it is not copied or truncated by
Packet code.

GOAL 7 owns only the deterministic projection. It may store authority pointers
and transformation identity, but may not embed replacement wording. Any
agent-authored phrase, Packet/Prompt/adapter hardcode or different positional
selection is forbidden.

GOAL 6 resolved the former “one plausible type but no safe record” stop by
adding the inactive managed catalog-v2 reason above. It did not change the
historical active decision/Choice code set. GOAL 7 projects all three
catalog-v2 reasons only in its transport-ineligible managed profile. GOAL 9
adds the separately authorized inactive V2.1 Choice profile and preserves all
three exact codes; it does not change the active V6 reason set.

## 7. V2.0 field disposition

This table classifies every surface row in the V2.0 closed allowlist. “Backend
only” means the information remains available to existing deterministic code
or private receipts but is forbidden from model view.

| V2.0 surface | V2.1 disposition |
| --- | --- |
| system message | `RETAIN_UNCHANGED_PROTOCOL`; GOAL 5 adds no prose |
| provider-neutral request root | `RETAIN_UNCHANGED_PROTOCOL`; later integration only |
| message item | `RETAIN_UNCHANGED_PROTOCOL`; later integration only |
| context root | `MINIMIZE`; remove `shared_relationships` |
| source root `document` | `FORBID`; move its sole `children` field to `source` |
| document `children` | `RETAIN`; same real hierarchy under `source.children` |
| table node | `MINIMIZE`; real `kind`, `children`, consumer-bound key only |
| row node | `MINIMIZE`; real `kind`, roles when informative, `values`, consumer-bound key |
| text-segment node | `MINIMIZE`; real `kind`, roles when informative, `values`, consumer-bound key |
| evidence-group node | `FORBID`; not real document structure |
| value | `MINIMIZE`; keep meaning, literal and conditional label/key; `value_type` is backend-only |
| type card | `MINIMIZE`; keep only fields `M15`–`M22` |
| type evidence requirement | `BACKEND_ONLY` |
| type distinction | `MINIMIZE`; exact current reciprocal nearest competitor only |
| shared relationship | `BACKEND_ONLY`; common facts cannot distinguish a choice |
| choice relationship | `MINIMIZE_AND_RENAME`; only necessary same-title record differentiators |
| choice | `MINIMIZE_AND_RENAME`; key, title and differentiators only |
| reason card | `MINIMIZE`; code, title and exact mapped one-sentence use rule only |
| reason contrast | `BACKEND_ONLY` |
| response object | `RETAIN_PROTOCOL_FIELDS`; inactive V2.1 parser implemented in the Choice owner |
| response-format wrapper | `MINIMIZE_PROTOCOL`; GOAL 10 builds and lints exact `type` + `json_schema(strict,schema)`; schema `name` is absent |
| response-schema root | `MINIMIZE_PROTOCOL`; implemented with `anyOf` only and no `title` |
| response-schema branch | `RETAIN_PROTOCOL_FIELDS`; inactive V2.1 profile implemented |
| response-schema property | `RETAIN_PROTOCOL_FIELDS`; inactive V2.1 profile implemented |

## 8. Complete model-view forbidden list

The allowlist in section 4 is closed. In particular, model view forbids:

- every field or value not explicitly allowed by `P01`–`P18` and
  `M01`–`M32`;
- V2.0 `source.document` and `evidence group`;
- V2.0 `shared_relationships`, `applies_to`, common bindings and any repeated
  binding;
- source `value_type` as a separate field, and structural roles/labels that
  lack a recorded per-occurrence decision consumer;
- choice `type_key`, canonical type/option identity and the old
  `label`/`relationships` field names;
- full required, optional, conditional and forbidden role schemas;
- role administration such as cardinality, exact role IDs,
  `source_ref_required`, identity roles and source-sign policy;
- lifecycle, compatible-source administration and tenant-overlay policy;
- semantic class when the minimal definition/signals already own the current
  distinction;
- synonym arrays and every raw example/counterexample array;
- complete ambiguity guidance, complete model guidance and external-concept
  distinction lists;
- reason `meaning`, `do_not_use_when`, contrasts, examples, numeric selection
  boundaries and display administration;
- validation, materialization, retention, persistence, replay or report
  guidance;
- blocked-binding, candidate-compiler or materializability diagnostics,
  including raw binding asymmetry presented as semantic plausibility;
- global source, association, evidence, provenance, document, package, scope,
  row, cell, segment, storage, record, type, option or asset IDs;
- schema, policy, prompt, packet, candidate, receipt, content, projection or
  integrity identities, versions and hashes;
- repository/filesystem paths, provider metadata, response IDs, raw
  envelopes, usage, cost or hidden reasoning;
- expected answers, benchmark labels, audit verdicts or qualification data;
- exact `source_reference` literals;
- copied authoritative literals, generated summaries and invented semantic
  wording;
- unused local keys, nulls, empty optional containers, empty labels and
  placeholders;
- additional system/developer messages, response-schema title/descriptions,
  examples or provider-visible wrapper prose introduced to compensate for
  removed fields.

Free-form `location` prose is not an allowed differentiator target. Allowed
field names also do not launder forbidden values; a global source ref under a
local-key field remains forbidden.

All exact refs, authority pins, complete bindings, restoration mappings and
integrity data stay in the implemented packet-owned private V2.1 receipt.
Private completeness is not permission to render those fields.

### 8.1 GOAL 8 implementation

The existing `Gate2FinancialSemanticV6PacketFactory.create` now constructs one
current non-active V2.1 candidate and one integrity-bound private receipt
alongside the unchanged active V6 packet. It calls the exact GOAL 7 minimal
projection and no longer builds historical V2.0 on the current per-request
path. V2.0 remains explicit version-pinned test evidence.

Executable proof across the ten frozen semantic cases records:

```text
ACTIVE_PACKET_HASH_PARITY: 10_OF_10_EXACT
MODEL_VISIBLE_ROOT_BLOCKS: 5_EXACT
SOURCE_LITERAL_OCCURRENCES: 45_EXACT
CHOICES: 12_EXACT
COMPILED_BINDINGS: 59_EXACT
VISIBLE_DIFFERENTIATOR_BINDINGS: ZERO
BACKEND_ONLY_BINDINGS: 59_EXACT
CONTEXT_V2_1_UTF8_BYTES_TOTAL: 26211
HISTORICAL_CONTEXT_V2_0_UTF8_BYTES_TOTAL: 78621
REDUCTION_VS_V2_0: 52410_BYTES_66_66_PERCENT
AGGREGATE_TARGET_LE_30000: PASSED
PER_CASE_SMALLER_THAN_ACTIVE: 10_OF_10
CONTEXT_CANDIDATE_PER_CASE_LE_4500: 10_OF_10
LOGICAL_REQUEST_FEASIBILITY_LE_4500: FEASIBILITY_ONLY
SEALED_REQUEST_LE_4500: NOT_PROVEN_CHOICE_PROFILE_NOT_AUTHORIZED
PROVIDER_CALLS: ZERO
FULL_BENCHMARK: NOT_RUN
RUNTIME_ACTIVATION: FALSE
```

At the GOAL 8 boundary, the maximum contract-derived logical Prompt + candidate
+ response-schema envelope was 3,522 bytes. That number remains historical
feasibility evidence, not a sealed-request result: the separately owned V2.1
Choice response profile was then unimplemented and no transport path ran. The
later GOAL 9 profile does not retroactively turn that estimate into a sealed
request pass.

### 8.2 GOAL 9 implementation

The existing `Gate2FinancialSemanticV6ChoiceContractFactory.create` now adds
one inactive Context V2.1 response profile to each validated current Choice
contract. It reads local keys and reason codes from the validated Context
candidate, pins the private receipt, and restores typed output only through
the receipt's exact `choice_restoration` row.

Executable proof across the same ten cases records:

```text
CHOICE_V2_1_RESPONSE_PROFILES: 10
TYPED_CHOICE_RESTORATIONS: 12_EXACT
ZERO_CHOICE_UNCLASSIFIED_ONLY_SCHEMAS: 4_EXACT
V2_1_REASON_CODES: 3_EXACT
ACTIVE_CHOICE_SCHEMA_HASH_PARITY: 10_OF_10_EXACT
HISTORICAL_LOCAL_CHOICE_V1_HASH_PARITY: EXACT
UNKNOWN_DUPLICATE_ORPHAN_CHOICE_REJECTION: PASSED
POST_RESPONSE_REPAIR: FORBIDDEN
CONTEXT_LINTER_V2_1: NOT_IMPLEMENTED
SEALED_REQUEST_LE_4500: NOT_PROVEN
PROVIDER_CALLS: ZERO
RUNTIME_ACTIVATION: FALSE
```

The third V2.1 reason is normalized without alteration but remains outside the
unchanged active V6 Choice/Expansion reason set. GOAL 9 therefore does not
claim active materialization for that reason.

### 8.3 GOAL 10 implementation

The same `Gate2FinancialSemanticV6ContextLinterFactory` authority now exposes
additive `create_context_v2_1`; historical `create` remains unchanged. The new
method consumes the exact Prompt, minified Context V2.1, Choice-owned schema
and packet-owned private mapping receipt, then emits one inactive,
transport-ineligible provider-neutral request and one private sealed-request
receipt.

The exact wrapper contains only `type: json_schema` and nested
`json_schema.strict` plus `json_schema.schema`; it contains no `name`, title,
description, examples or provider prose. Choice-owned public validation also
pins exact model-order schema bytes before the Linter consumes them.
Executable frozen baselines are:

```text
SEALED_REQUESTS: 10_EXACT
SEALED_REQUEST_MAX_UTF8_BYTES: 3522
SEALED_REQUEST_LIMIT_UTF8_BYTES: 4500
SEALED_REQUESTS_WITHIN_LIMIT: 10_OF_10
SEALED_REQUEST_UTF8_BYTES_TOTAL: 34389
ESTIMATED_INPUT_TOKENS_TOTAL: 9241
ZERO_TARGET_INVARIANTS: 6_OF_6_ZERO
SEMANTIC_LITERAL_COVERAGE: 45_OF_45
MAPPING_ROW_COVERAGE: 156_OF_156
INCLUDED_BINDING_ROWS: 59_OF_59
PROVIDER_ADAPTER_CHANGES: ZERO
PROVIDER_CALLS: ZERO
RUNTIME_ACTIVATION: FALSE
```

The private receipt identity is
`broker_reports_gate2_llm_semantic_context_v2_1_sealed_request_receipt_v1`;
the request profile is
`broker_reports_gate2_financial_semantic_v6_request_v2_1_candidate`.
`compact_request_utf8_bytes_div_4_plus_64_v1` is a deterministic planning
estimate, not provider-tokenizer evidence.

## 9. Representative human-readable examples

The literals below are allowlisted frozen synthetic values, not customer
data.

### 9.1 Minimal source and choices

```json
{
  "source": {
    "children": [
      {
        "kind": "table",
        "children": [
          {
            "kind": "row",
            "values": [
              {
                "meaning": "amount",
                "literal": "-120.5000"
              },
              {
                "meaning": "currency",
                "literal": "RUB"
              },
              {
                "meaning": "as of date",
                "literal": "2026-03-01"
              },
              {
                "meaning": "description",
                "literal": "Cash balance"
              }
            ]
          }
        ]
      }
    ]
  },
  "choices": [
    {
      "choice_key": "choice_1",
      "title": "Printed financial metric"
    },
    {
      "choice_key": "choice_2",
      "title": "Cash balance snapshot"
    }
  ]
}
```

The generic `fact candidate` row role, scalar types and local value keys are
absent because this occurrence has no decision consumer for them. The choices
already have distinct managed titles, so raw cross-type binding asymmetry is
also absent. Every exact binding remains private.

### 9.2 Type-card readability illustration

This example applies the exact managed-source mappings accepted in section 6.
GOAL 7 must project these strings from the Pack; it may not copy them into
Packet code.

```json
{
  "type_key": "type_1",
  "title": "Cash balance snapshot",
  "definition": "A source-stated cash-class balance for an explicit statement scope and reporting date. Restricted or segregated balances are excluded unless the source explicitly classifies them as ordinary cash.",
  "positive_signal": "A synthetic statement row explicitly states an ordinary cash balance for a reporting date and statement scope.",
  "negative_signal": "A synthetic row states a segregated regulatory asset without an ordinary cash classification.",
  "nearest_competitor": {
    "type_key": "type_2",
    "distinction": "Use this type only when ordinary cash-class state semantics are explicit; a printed total without that classification remains a printed metric or unclassified."
  }
}
```

### 9.3 Reason-card readability illustration

Both sentences below are exact first sentences of their managed catalog
`meaning` fields:

```json
[
  {
    "code": "no_registry_type",
    "title": "No available type matches",
    "use_when": "Source-stated financial values are present, but none of the available financial type definitions matches their visible meaning."
  },
  {
    "code": "ambiguous_registry_type",
    "title": "Multiple available types remain plausible",
    "use_when": "Source-stated financial values are present and two or more distinct available financial type definitions remain plausible after all visible evidence is considered, so no single type can be selected safely."
  }
]
```

## 10. Verification and acceptance

The historical GOAL 5 contract acceptance remains:

```text
COMPLETE_PROTOCOL_ALLOWLIST: P01-P18
COMPLETE_SEMANTIC_ALLOWLIST: M01-M32
FIELDS_WITHOUT_NECESSITY_ANSWER: ZERO
DEFAULT_FORBIDDEN_LIST: CLOSED
EXACT_MANAGED_WORDING_MAPPINGS: DEFINED
REPRESENTATIVE_HUMAN_READABLE_EXAMPLES: PRESENT
CURRENT_V2_0_BYTES_CHANGED: NO
ACTIVE_PACKET_BYTES_CHANGED: NO
RUNTIME_CODE_CHANGES: ZERO
MANAGED_ASSET_CHANGES: ZERO
MINIMAL_MANAGED_PROJECTION: NOT_IMPLEMENTED
CONTEXT_V2_1: NOT_IMPLEMENTED
CONTEXT_LINTER_V2_1: NOT_IMPLEMENTED
OUTCOME_TAXONOMY_CHANGED: NO
EXPECTED_ANSWERS_CHANGED: NO
PROVIDER_CALLS: ZERO
BENCHMARK_RUNS: ZERO
RUNTIME_ACTIVATION: FALSE
```

Historical GOAL 8 acceptance recorded:

```text
MINIMAL_MANAGED_PROJECTION: IMPLEMENTED_NON_ACTIVE
CONTEXT_V2_1_PACKET_CANDIDATE: IMPLEMENTED_NON_ACTIVE
PRIVATE_EXACT_MAPPING_RECEIPT: IMPLEMENTED
ACTIVE_PACKET_BYTES_CHANGED: NO
CURRENT_V2_0_BYTES_CHANGED: NO
CHOICE_V2_1_RESPONSE_PROFILE: NOT_IMPLEMENTED
CONTEXT_LINTER_V2_1: NOT_IMPLEMENTED
SEALED_V2_1_REQUEST: NOT_RUN
PROVIDER_CALLS: ZERO
FULL_BENCHMARK_RUNS: ZERO
RUNTIME_ACTIVATION: FALSE
```

Historical GOAL 9 acceptance recorded:

```text
CHOICE_V2_1_RESPONSE_PROFILE: IMPLEMENTED_NON_ACTIVE
CHOICE_V2_1_PARSER: IMPLEMENTED_NON_ACTIVE
ACTIVE_CHOICE_BYTES_CHANGED: NO
HISTORICAL_LOCAL_CHOICE_V1_CHANGED: NO
CONTEXT_V2_1_PACKET_BYTES_CHANGED: NO
CONTEXT_LINTER_V2_1: NOT_IMPLEMENTED
SEALED_V2_1_REQUEST: NOT_RUN
PROVIDER_ADAPTER_CHANGES: ZERO
PROVIDER_CALLS: ZERO
FULL_BENCHMARK_RUNS: ZERO
RUNTIME_ACTIVATION: FALSE
```

Current GOAL 10 acceptance adds:

```text
CONTEXT_LINTER_V2_1: IMPLEMENTED_NON_ACTIVE
SEALED_V2_1_REQUEST: IMPLEMENTED_NON_ACTIVE
HISTORICAL_CONTEXT_LINTER_CREATE_CHANGED: NO
RESPONSE_FORMAT_NAME_PRESENT: NO
SEALED_REQUESTS_WITHIN_4500_BYTES: 10_OF_10
SEALED_REQUEST_UTF8_BYTES_TOTAL: 34389
ESTIMATED_INPUT_TOKENS_TOTAL: 9241
SEMANTIC_LITERAL_COVERAGE: 45_OF_45
MAPPING_ROW_COVERAGE: 156_OF_156
PROVIDER_ADAPTER_CHANGES: ZERO
PROVIDER_CALLS: ZERO
FULL_BENCHMARK_RUNS: ZERO
RUNTIME_ACTIVATION: FALSE
```

The program state is:

1. GOAL 6 outcome taxonomy audit is complete;
2. GOAL 7 exact minimal managed projection is complete;
3. GOAL 8 non-active Context V2.1 candidate/private receipt is complete;
4. GOAL 9 inactive V2.1 Choice response profile/parser is complete and remains
   non-active;
5. GOAL 10 inactive provider-neutral linter/sealed request is implemented
   through the existing linter authority;
6. **STOP before GOAL 11:** provider-specific local proof may start only after
   GOAL 10 is fresh-reviewed on its immutable PR head, the real GitHub Actions
   check is green and the PR is merged.
