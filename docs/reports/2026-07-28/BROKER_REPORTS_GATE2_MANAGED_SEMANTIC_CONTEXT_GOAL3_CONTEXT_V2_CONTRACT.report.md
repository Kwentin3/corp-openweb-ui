# Broker Reports Gate 2 — Managed Semantic Decision Context GOAL 3 Context V2 Contract

Date: 2026-07-28

Status:
`PASSED_AS_DOCUMENTATION_ONLY_VERSIONED_CONTRACT_WITH_COMPATIBILITY_STOP`

Base revision: `48f4f75398024c23a651780863818486aa071a5e`

Branch:
`codex/broker-reports-gate2-managed-context-goal3-context-v2-contract`

## 1. Outcome

GOAL 3 defines one closed, versioned
[LLM Semantic Context V2](../../stage2/contracts/BROKER_REPORTS_GATE2_LLM_SEMANTIC_CONTEXT.v2.md)
candidate. It is a product contract for the complete future model-visible
decision boundary, not an implementation and not a runtime activation.

The contract gives the model:

- the unchanged short task;
- Evidence-Bundle-owned readable source structure;
- every authoritative semantic literal exactly once per source occurrence;
- only locally necessary cross-reference keys;
- a complete card for every active source-family-compatible financial type;
- factored, explicitly scoped readable relationships;
- a readable label and disposable local key for every selectable Typed
  Option;
- complete catalog-owned meaning for both allowed unclassified reasons;
- one strict local response schema that restores the unchanged canonical V6
  Choice.

It denies the model:

- global refs and canonical type/option identities;
- hashes, storage/package identities and provider metadata;
- repeated projections of authoritative source literals;
- null fields and empty optional containers;
- blocked-binding or materialization diagnostics;
- unexplained reason codes;
- technical bindings without a semantic decision consumer.

The result is intentionally non-active:

```text
CONTEXT_V2_IMPLEMENTATION: NOT_IMPLEMENTED
CONTEXT_V2_MODEL_VISIBLE: NO
CONTEXT_V2_LINTER: NOT_IMPLEMENTED
CONTEXT_V2_RESTORE_REPLAY: NOT_IMPLEMENTED
PROVIDER_CALLS: 0
RUNTIME_ACTIVATION: FALSE
FULL_BENCHMARK: NOT_RUN
```

The current exact four-block V6 packet, exact-ID Choice, historical Slim v2,
Local Choice v1, Prompt, Pack, reason catalog bytes, provider adapters and
runtime route are unchanged.

## 2. Preconditions and Context Bootstrap

The prerequisite GOALs are merged:

| Prerequisite | Accepted result | Merge revision |
| --- | --- | --- |
| GOAL 1 — Managed Decision Reason Catalog | one inactive versioned catalog with mutually distinguishable reason meaning | `d470b8a0418fad3fc607e5be186fd24dcac0c795` |
| GOAL 2 — Alias Necessity and Readability Audit | closed reference-visibility policy and exact frozen alias/binding census | `48f4f75398024c23a651780863818486aa071a5e` |

Context Bootstrap followed the repository and service `AGENTS.md` instructions.
The normative inputs were:

- architecture authority map;
- LLM Semantic Context v1;
- Financial Semantic Packet V6 and Choice V6;
- Local Choice v1;
- Financial Semantic Pack and its existing projection;
- managed Financial Decision Reason Catalog v1;
- Evidence Bundle, Candidate Compilation and Typed Option contracts;
- Context Linter, provider request, Expansion, validation, materialization and
  evidence/replay boundaries;
- GOAL 1 and GOAL 2 reports and repository-safe receipts.

The affected authority is only the documented future model-visible
presentation contract inside existing owners. No new runtime owner is added.

## 3. Sole ownership and anti-drift boundary

| Concern | Sole existing owner | GOAL 3 decision |
| --- | --- | --- |
| packet and context rendering | `Gate2FinancialSemanticV6PacketFactory.create` | future Context V2 and its private authority mapping must be one non-active versioned output of this factory |
| type meaning | Financial Semantic Pack | exact selected meaning only through a versioned extension of the existing Pack projection |
| available type set | exact validated Registry snapshot with exact Pack `source_baseline` parity | active types whose Pack contracts are compatible with the Evidence Bundle source family; Compiler results are parity only |
| reason meaning | managed Financial Decision Reason Catalog v1 | exact selected catalog fields; no Python/Prompt/adapter copy |
| strict response schema | existing V6 Choice factory | future non-active local V2 profile |
| exact source facts and structure | Evidence Bundle | readable projection only; exact refs remain private |
| complete option records and bindings | Candidate Compilation and Typed Options | model selects a local key; backend restores the original exact option |
| pre-transport lint | existing Context Linter factory | future versioned V2 extension consumes the packet mapping plus Prompt/Choice outputs and emits a separate sealed-request receipt |
| provider projection/parsing | existing provider adapters | transport-only; no reason or financial-semantic repair |
| normalization and expansion | existing Choice/Expansion authorities | exact local-key restoration followed by unchanged canonical path |
| validation/materialization/replay | existing factories | unchanged and not executed as V2 in this GOAL |

The packet factory remains a renderer. It does not become a second financial
registry, reason catalog, binding resolver or expected-answer policy.

The candidate pins the inactive managed family at semantic version `1.1.0`
and manifest SHA-256
`4e5328554056741ecb783d130a5fd43034a6876484a25c98dfdd5e68bf76499d`.
Its available-type authority is the exact Registry snapshot
`broker_reports_gate2_financial_evidence_registry_v1` with SHA-256
`0bac59aad259b9e11a5037bb73b09642c2a87fd2baca36b8e4db7c5d5e852ac8`.
The mapping receipt must also prove the Pack `source_baseline` version/hash is
identical to that Registry snapshot.
The non-active projection profiles are
`broker_reports_gate2_financial_semantic_projection_v2_candidate@2.0.0` and
`broker_reports_gate2_financial_decision_reason_projection_v1_candidate@1.0.0`;
both extend existing owners and are not implementations.

## 4. Complete model-visible boundary

Conformance covers all future model-visible bytes:

1. the exact system message;
2. the complete minified user-message Context V2 JSON;
3. the complete strict response schema, including title, branches, property
   order and enum order;
4. any wrapper text or schema metadata exposed by a provider.

The exact unchanged system message is:

```text
Return exactly one JSON object that conforms to the supplied strict response schema. Use only the task and evidence in the user message.
```

Its unchanged authority version/hash are
`financial_semantic_v6_candidate_choice_v1` and
`59143216c08d6e5069bee757346508906cbaf5575b76bebee440d94dede8642b`.

The exact unchanged task, rendered once in the Context V2 object, is:

```text
Select a typed option only when the visible source uniquely supports its complete prebound record; otherwise select unclassified.
```

There are no other system/developer instructions or response-schema
descriptions. A provider wrapper that injects additional model-visible prose
does not conform to V2.

The provider-neutral envelope is also closed: `messages` then
`response_format`; exactly two message objects, each `role` then `content`,
with roles `system` then `user`. User content is the Context object serialized
as one minified JSON string, not an embedded object. Model-view serialization
preserves the field order fixed by the contract. Receipt integrity uses a
separate sorted-key canonicalizer, so hash canonicalization cannot reorder the
model view.

The ordered user-message root is closed:

```text
task
source
type_cards
choices
shared_relationships  # omitted when empty
unclassified_reasons
```

Every allowed nested field, authority, decision consumer, cardinality,
omission rule and private provenance is listed in the canonical contract.
Fields outside that matrix are forbidden.

## 5. Readable source projection

The current Evidence Bundle can prove only these visible node shapes:

```text
document
  -> table -> row -> values
  -> row -> values when table lineage is absent
  -> text segment -> values
  -> reference-only evidence group
```

The per-kind grammar is closed: tables have children only; rows and text
segments have optional readable roles plus non-empty values; fallback evidence
groups have neither roles, children nor values. Each may carry a structural
key only when an inbound relationship requires it.

It owns table/row/text-segment association and lineage plus per-value
`visible_label`, `section_role` and `row_role`. It does not own section-node
objects or structural-node labels. Context V2 therefore forbids emitting
either until a later Evidence Bundle and Context contract version adds an
authority.

Every validated non-reference Evidence Bundle source occurrence is rendered
once; there is no discretionary “model relevance” filter. It has:

```text
value_key   # only with an inbound model-visible relationship
meaning
literal
value_type
label       # only when non-null and distinct from meaning and literal
```

`meaning` renders each candidate first, then compares it exactly with the
literal: column meaning, visible label, then rendered source value type.
Failure to find a distinct non-empty candidate stops construction. Source
value type drops exactly one `source_` prefix and renders machine separators
as spaces.

Machine-form `column_meaning`, `section_role` and `row_role` values render `_`
or `-` runs as spaces; genuinely human evidence strings and visible labels
stay exact. The receipt maps every readable form back to its exact authority
value.

Distinct exact identifiers may not collide after mechanical rendering within
one semantic namespace. A collision fails before relationship factoring, so
two backend roles can never be merged merely because their readable strings
match.

An all-`source_reference` bundle with no necessary inbound relationship cannot
produce a readable hierarchy. It fails before lint/transport rather than
emitting an empty document or invented group.

The exact-once rule is keyed by authoritative semantic `source_value_ref`,
not by literal string equality. Two distinct cells that both contain `100`
remain two source occurrences; neither is collapsed. Conversely, a source
literal is never copied into a choice label, relationship, summary, type card
or reason card.

Exact `source_reference` literals never enter model view. Where one is
decision-relevant, the model sees only a readable relationship to an
Evidence-Bundle-derived node or uniquely identifiable visible location. The
exact value remains in the Evidence Bundle and is retrieved through the
`source_value_ref` retained by the private mapping receipt and Typed Option.

Table, row and segment groups use the exact current association/lineage
composite tuples fixed in the contract. The resolver also fixes the maintained
empty/non-overlap semantics: a lineage set seeds an empty candidate set, while
an empty intersection preserves the preceding candidates. Segment, row and
table refs are applied in that order; one unique row/segment leaf wins, then
one unique remaining node, otherwise a deterministic fallback group. A
unique-location phrase is legal only when exactly one visible node of that kind
exists.

## 6. Deterministic local keys

Local keys are disposable request coordinates, not abbreviated global IDs.

| Key | Emission and order |
| --- | --- |
| `value_N` | only values with inbound readable relationships; visible source hierarchy order |
| `structure_N` | only referenced nodes that cannot be named by a unique-location phrase; depth-first visible hierarchy order |
| `type_N` | every authority-derived available type; canonical semantic-contract order |
| `choice_N` | every complete Typed Option; unchanged Candidate Compiler order |

Omitted keys reserve no number. Each suffix is only an ordinal in the
unchanged authority-owned canonical order; it does not copy, encode or permit
recovery of an opaque value. The existing upstream order may itself be
established from private refs or hash-derived identities.

`choice_key` and `label` are deliberately separate. The key is strict response
identity; the label is exactly the mapped Pack title. Labels need not be
unique and do not contain literals or repeat relationships as qualifiers.
Semantically indistinguishable choices remain distinct backend records.
Unclassified is truthful when they leave at least two distinct types
plausible; same-type indistinguishability is the count-one compatibility stop.
Missing, duplicate or cross-mapped keys are technical failures and fail
closed.

## 7. Available type set and type-card completeness

The central correction from the semantic audit is:

```text
AVAILABLE_TYPES != typed_options union blocked_bindings as semantic evidence
```

For each source, V2 derives its available set from the validated
semantic-contract snapshot: every active Pack/Registry type whose
`compatible_source_families` contains the Evidence Bundle
`source_family_id`.

The type IDs observed across compiled options and blocks must equal this set
under the current Compiler, but only as a private technical parity check.
A block proves that construction did not produce a complete option for one
association/type pair. It proves neither semantic plausibility nor semantic
rejection.

Every available type receives a card even when zero choices compiled. Each
card contains the decision-relevant Pack surface:

- local type key;
- exact Pack title and definition;
- exact semantic class;
- compact readable required evidence;
- optional evidence when present;
- both Pack conditional requirements, so optional `date`/`period` and
  `currency`/`unit` roles do not hide their required OR constraints;
- readable forbidden evidence;
- exact Pack synonyms;
- all Pack semantic distinctions, including readable external concepts;
- all Pack examples and counterexamples;
- all Pack ambiguity guidance.
- exact Pack model guidance.

This is the minimum semantically complete surface for applying
`no_registry_type`: the model must be able to compare meaning, required
and conditional evidence, exclusions, distinctions and counterexamples before
ruling out every type. Lifecycle, compatible-source administration, exact
role IDs, identity-role administration, source-ref flags, source-sign
preservation, validation/materialization profiles, tests, compatibility
administration, asset identity and hashes remain private. Identity roles and
sign policy are backend consumers, not model-owned record construction or
transformation decisions.

The current projection does not expose Pack title. GOAL 4 must version and
extend that existing projection; packet code may not read the Pack asset
directly or embed copied wording.

## 8. Necessary semantic relationships

V2 replaces repeated `role=alias` serialization with structured readable
relationships:

```text
role
exactly one of:
  value_key
  structure_key
  location
```

A relationship is visible only when it:

1. binds a Pack semantic-value role to a visible source value;
2. explains a required source-reference eligibility predicate through a
   readable evidence-derived location; or
3. distinguishes selectable choices.

GOAL 2 observed 59 exact binding occurrences in the six choice-bearing frozen
cases. The V2 target factors them into 35 readable relationships while
preserving all 59 exact bindings privately:

```text
SEMANTIC_ROLE_VALUE_RELATIONSHIPS: 23
READABLE_EVIDENCE_PREDICATES: 12
DUPLICATE_VISIBLE_OCCURRENCES_REMOVED: 24
EXACT_PRIVATE_BINDING_OCCURRENCES_RETAINED: 59
```

These are current-suite implementation oracles, not universal schema counts.

A multi-association source requires explicit scope. One readable relationship
used by two or more choices is emitted once in top-level
`shared_relationships`. If it does not apply to all visible choices, its
ordered `applies_to` list names the exact local choice subset. A
single-choice relationship stays inside that choice. This preserves the flat
Compiler choice order, avoids another grouping identity and prevents a
relationship from silently crossing association scope.

The private mapping receipt maps every readable relationship to all covered exact
`{choice_key, role_id, source_value_ref}` rows.

## 9. Managed unclassified reasons and exact semantic rule

The model sees one complete card for each code allowed by current V6 Choice:

```text
code
title
meaning
use_when
do_not_use_when
reciprocal contrasts
```

Exact title, meaning, usage, counter-usage and contrasts come from the managed
catalog. The strict response returns the same adjacent explained code.
Lifecycle, GUI fields, asset hashes, the separate numeric-boundary field and
positive examples remain private. The exact `use_when` and contrast prose
already exposes the necessary zero-versus-two-or-more distinction without
conditioning a later smoke on examples that mirror frozen fixtures.

The semantic decision rule is:

| Outcome | Necessary condition |
| --- | --- |
| typed local choice | exactly one distinct type remains plausible and exactly one complete choice within it is supported; every other type card and choice is ruled out |
| `no_registry_type` | zero plausible distinct available type meanings remain |
| `ambiguous_registry_type` | two or more plausible distinct available type meanings remain |

Choice count, Compiler attempt count and blocked-binding count are never
substitutes for plausible-type count. Binding or association uncertainty
inside one identified type is not cross-type ambiguity.

The present reason vocabulary is intentionally non-total for count `1`: if
one type remains plausible but no complete choice is safe, neither current
reason is truthful. The route must stop; an adapter, normalizer or expected
answer may not force either code.

The unchanged task says “otherwise unclassified”, but the exact catalog
meanings narrow that phrase to count `0` or `2+`. The field/schema boundary is
closed while the semantic response relation remains partial. Production or
unbounded transport is forbidden until a later version makes the unsafe
count-`1` state total or proves it impossible without expected-answer labels.
A bounded later qualification may use only explicitly accepted
`typed_safe_1`, `no_type_0` or `ambiguous_2plus` semantic cases. Exactly one
plausible type without one safe choice remains inadmissible, and all audit
labels remain outside model view.

## 10. Exact response and restoration contract

The canonical V2 document prints the complete provider-neutral response-format
wrapper and both exact request-bound response-schema forms:

- typed branch followed by unclassified branch when choices exist;
- unclassified branch only when no choice exists.

The typed enum is `choice_1` through `choice_N` in unchanged choice order.
The reason enum retains current V6 Choice code order:

```text
ambiguous_registry_type
no_registry_type
```

Reason cards independently retain catalog display order:

```text
no_registry_type
ambiguous_registry_type
```

The join is exact code, never array position.

A typed local response normalizes only through the private
`choice_key -> typed_option_id` mapping:

```json
{"disposition":"typed_input","typed_option_id":"<private exact mapped ID>"}
```

An unclassified local response preserves the returned allowed code:

```json
{"disposition":"unclassified_financial_input","reason_code":"<exact returned code>"}
```

No free text, type ID, binding, source ref or value comes from the model.
Provider adapters do not rename, infer, repair or retry a decision.

## 11. Closed private receipts

The future path uses two closed private objects, not one cross-owner evidence
bag.

The packet-owned mapping receipt binds:

- Context, active packet baseline, managed-family manifest, exact Registry
  snapshot, Pack projection and reason projection identities/hashes;
- exact Pack-baseline parity with the request Registry snapshot;
- a packet-owned integrity-bound type-set witness combining source family,
  Registry/Pack pins and ordered available type IDs without becoming a new
  semantic authority;
- Evidence Bundle, source scope, Candidate Compilation and available-type
  parity;
- every visible field JSON Pointer to its exact authority pointer/hash;
- every local value, keyed structure, type and choice key to exact backend
  identity;
- every hidden deterministic reference to its visible location target;
- every visible relationship to the exact bindings it covers;
- every unprojected exact Typed Option binding in a disjoint backend-only
  partition;
- deterministic presentation and option-permutation identities;
- canonical mapping-receipt integrity.

The packet receipt deliberately contains no Prompt or response-schema identity.
The existing Context Linter consumes it with the Prompt-owned system message
and Choice-owned provider-neutral response format. The linter-owned
sealed-request receipt then binds:

- mapping-receipt integrity and exact Context hash;
- Prompt version/hash;
- local Choice profile, nested response-schema hash and complete
  response-format hash;
- exact model-visible request hash and UTF-8 bytes;
- repository estimator identity/result;
- closed invariant counters and pre-provider status.

This linter status is mechanical only. The linter does not infer plausible
type count or consult expected answers. A later bounded qualification owns a
separate hash-bound private case-admission decision; it does not enter the
packet, linter or model view and cannot modify request bytes.
The sole admission owner is the existing
`Gate2FinancialSemanticV6QualificationFixtureFactory`; the existing
Qualification Preflight factory only consumes and verifies it.

The visible and backend-only binding multisets are disjoint and their union is
the complete Typed Option binding multiset. Value/keyed-structure/type/choice
maps are bijective over emitted keys. Multiple exact reference values may
resolve to one structural target, while each reference row and the exact
binding table preserve total reconstruction.

The historical Slim candidate identity/hash is deliberately excluded. Context
V2 is bound to the unchanged active-packet baseline and must not acquire an
unnecessary implementation dependency on its predecessor. A later provider
attempt separately records the adapter-owned provider-projection identity and
exact projected-request hash.

Neither private receipt is the repository-safe receipt accompanying this
report. Exact source values, refs, customer context and actual request bytes
remain outside Git.

## 12. Frozen compatibility audit

All four current zero-choice frozen cases have the same mechanical state:

```text
CURRENT_VISIBLE_TYPE_CARDS: 0
CURRENT_TYPED_OPTIONS: 0
CURRENT_COMPILER_BLOCKS: 2
CURRENT_BLOCKED_ROLE: amount
CURRENT_BLOCK_REASON: candidate_compiler_required_binding_ambiguous
```

Their semantic interpretations are not equivalent:

| Frozen case | Current expected reason | Evidence-based V2 assessment |
| --- | --- | --- |
| `syn_successor_v2_multiple_compatible` | `ambiguous_registry_type` | source can support two or more available type meanings; the reason remains plausible |
| `syn_successor_v2_detail_vs_subtotal` | `ambiguous_registry_type` | primarily a printed-metric boundary; two distinct registry types are not proven |
| `syn_successor_v2_adjacent_equal` | `ambiguous_registry_type` | primarily within-cash value/association ambiguity; cross-type ambiguity is not proven |
| `syn_successor_v2_adjacent_fx` | `ambiguous_registry_type` | primarily within-cash association ambiguity; cross-type ambiguity is not proven |

Adding authority-derived type cards closes the missing-information defect for
the first case. It cannot by itself validate the latter three expected
answers.

Consequences:

- frozen expected answers remain unchanged in GOAL 3;
- Prompt, Pack, catalog wording and option order remain unchanged;
- the mismatch is not labelled a model error;
- the full benchmark is not run;
- GOAL 4 may implement the candidate but may not claim frozen conformance;
- a separate, evidenced taxonomy/expected-answer decision is required before
  qualification can treat these cases as valid reason-semantic tests.

## 13. Implementation and activation stops

GOAL 4 must remain within existing factories and prove, without provider
calls:

- active packet and Choice byte/hash parity;
- packaged closed-world access to validated catalog and Pack projections;
- deterministic Context V2 rendering and all local mappings;
- exact literal coverage and relationship factoring;
- receipt integrity and binding-partition totality;
- response normalization and tamper rejection.

GOAL 5 owns the V2 linter. GOAL 6 owns persisted exact request,
adapter-extracted simulated answer, restoration, expansion, validation,
materialization, replay and report projection. Provider calls remain forbidden
until those goals are accepted.

Existing provider-profile compatibility is not proven. The current
OpenAI-compatible adapter may wrap a root `anyOf` schema under
`broker_reports_gate2_choice`, while the current Gemini projection may remove
enums for the new `choice` and `reason` fields. GOAL 6 must prove the exact
provider projection locally; until then neither existing profile is admitted
as Context V2-conforming.

This GOAL does not authorize:

- a second packet, Choice, Pack, catalog, projection or linter authority;
- runtime activation or production admission;
- provider/model selection or invocation;
- frozen expectation changes;
- customer-corpus access;
- Prompt, type meaning or reason wording changes.

## 14. Scope and privacy accounting

```text
PROVIDER_CALLS: 0
PROVIDER_RESPONSES: 0
FULL_BENCHMARK_RUNS: 0
RUNTIME_SOURCE_FILES_CHANGED: 0
PROMPT_FILES_CHANGED: 0
PACK_FILES_CHANGED: 0
REASON_ASSET_FILES_CHANGED: 0
CHOICE_SOURCE_FILES_CHANGED: 0
ADAPTER_FILES_CHANGED: 0
VALIDATOR_OR_MATERIALIZER_FILES_CHANGED: 0
STAGE_MUTATIONS: 0
PRODUCTION_MUTATIONS: 0
CUSTOMER_INPUTS_READ: 0
CREDENTIALS_READ: 0
HISTORICAL_REPORTS_OR_RECEIPTS_MODIFIED: 0
```

Only canonical Markdown/instruction files and one repository-safe JSON receipt
are in scope. Synthetic case IDs, aggregate counts and managed-asset hashes
are repository-safe. No customer literal, global customer ref, provider
response ID, raw envelope, filesystem path, credential or hidden reasoning
trace is included.

## 15. Documentation package

Canonical documentation updated in the same change:

- new LLM Semantic Context V2 contract;
- architecture authority map;
- global Gate architecture component map;
- LLM Semantic Context v1 predecessor note;
- Financial Semantic Packet V6;
- Financial Semantic Choice V6;
- Local Choice v1;
- managed Decision Reason Catalog v1;
- managed Financial Domain Asset Family v2;
- Exact Evidence contract;
- service `AGENTS.md`;
- Stage 2 Context Index;
- this report and its safe receipt.

No document was moved or renamed. No redirect entry is required.

Repository-safe machine receipt:
[BROKER_REPORTS_GATE2_MANAGED_SEMANTIC_CONTEXT_GOAL3_CONTEXT_V2_CONTRACT.receipt.safe.json](./BROKER_REPORTS_GATE2_MANAGED_SEMANTIC_CONTEXT_GOAL3_CONTEXT_V2_CONTRACT.receipt.safe.json)

Receipt integrity SHA-256:
`fa916c5bba4fc0f479a025b6932c56318b211b4a88078dee629ab0a80563a359`.

## 16. Verification

Accepted shell: PowerShell.

Working directory for service checks:
`services/broker-reports-gate1-proof`.

The local verification boundary covers:

- managed Pack and reason-catalog integrity;
- unchanged current Packet/Choice/Prompt factories;
- existing local Choice and Context Linter behavior;
- architecture ownership;
- full service regression;
- documentation links;
- repository-safe receipt JSON/integrity;
- privacy scan;
- `git diff --check`.

Executed local results:

```text
MANAGED_ASSET_BUILDERS: PASSED (2/2 CHECK MODES)
FOCUSED_TESTS: PASSED (87 IN 57.60s)
FULL_SERVICE_SUITE: PASSED (1887 PASSED, 20 SKIPPED, 5 WARNINGS IN 526.35s)
DOCUMENTATION_LINKS: PASSED (396 CHECKED, 0 MISSING)
JSON_EXAMPLES_AND_SAFE_RECEIPT_PARSE: PASSED
PRIVACY_SCAN: PASSED (14 FILES, 0 HITS)
GIT_DIFF_CHECK: PASSED
INDEPENDENT_FORMAL_AND_ANCILLARY_REVIEWS: CLEAN
```

The fresh review of the actual GitHub diff remains a remote merge gate. Local
results do not substitute for it.

## 17. Acceptance

```text
CONTEXT_CONTRACT: VERSIONED_V2_CANDIDATE
COMPLETE_MODEL_VISIBLE_BYTE_AND_FIELD_BOUNDARY: CLOSED
SEMANTIC_RESPONSE_RELATION: PARTIAL_AT_COUNT_ONE
UNBOUNDED_OR_PRODUCTION_TRANSPORT: FORBIDDEN
EXACT_SYSTEM_PROMPT: FIXED
EXACT_TASK: FIXED_ONCE
EXACT_RESPONSE_SCHEMA: TWO_REQUEST_BOUND_FORMS_FIXED
PROVIDER_NEUTRAL_REQUEST_ENVELOPE: CLOSED
MODEL_VIEW_AND_INTEGRITY_SERIALIZERS: DISTINCT_AND_FIXED
PROVIDER_PROFILE_COMPATIBILITY: NOT_PROVEN
OPAQUE_GLOBAL_IDS: FORBIDDEN
AUTHORITATIVE_LITERAL_PROJECTION: ONCE_PER_SEMANTIC_SOURCE_OCCURRENCE
NULL_FIELDS: FORBIDDEN
EVERY_VISIBLE_FIELD_JUSTIFIED: YES
AVAILABLE_TYPE_SET: EXACT_REGISTRY_SNAPSHOT_WITH_PACK_BASELINE_PARITY
COMPILER_TYPES: PRIVATE_PARITY_ONLY
TYPE_CARDS_WITH_ZERO_CHOICES: REQUIRED
TYPE_CARDS: PACK_OWNED_AND_SEMANTICALLY_COMPLETE
RELATIONSHIPS: NECESSARY_FACTORED_AND_EXPLICITLY_SCOPED
CHOICE_KEY_AND_LABEL: SEPARATE
UNCLASSIFIED_REASONS: CATALOG_OWNED_AND_EXPLAINED
COUNT_ZERO_VS_TWO_PLUS: EXPLICIT
COUNT_ONE: COMPATIBILITY_STOP
EXACT_ALIAS_MAPPING: DESIGNED
PACKET_MAPPING_RECEIPT: CLOSED_BY_CONTRACT
LINTER_SEALED_REQUEST_RECEIPT: CLOSED_BY_CONTRACT
LINTER_SEMANTIC_ADMISSION: FORBIDDEN
BOUNDED_CASE_ADMISSION_OWNER: Gate2FinancialSemanticV6QualificationFixtureFactory
PRIVATE_BINDING_PARTITION: CLOSED_AND_TOTAL_BY_CONTRACT
PROVIDER_CALLS: ZERO
RUNTIME_ACTIVATION: FALSE
BENCHMARK_CONFORMANCE: NOT_CLAIMED
FOUR_CASE_REASON_COMPATIBILITY: ONE_PLAUSIBLE_THREE_NOT_PROVEN
DOCUMENTATION: UPDATED_IN_SAME_CHANGE
GOAL3: PASSED_AS_DOCUMENTATION_ONLY_VERSIONED_CONTRACT_WITH_COMPATIBILITY_STOP
NEXT_GOAL: GOAL4_ONLY_AFTER_APPROVED_GREEN_MERGE
```
