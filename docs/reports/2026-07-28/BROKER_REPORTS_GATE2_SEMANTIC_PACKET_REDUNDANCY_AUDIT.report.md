# Broker Reports Gate 2 — Semantic Packet redundancy audit

Date: 2026-07-28

Base revision: `bad7fec635afcc05dd41e96672cf091763ac7b2b`

Status: GOAL 2 research complete for review; proposed Slim Semantic View is
not implemented, not active and not provider-qualified.

## Executive conclusion

The current V6 packet is semantically complete and technically safe, but its
model-facing representation repeats the same evidence at several levels.
The largest removable duplication is inside `typed_options`:

- each prebound binding repeats its exact literal;
- repeats its value type;
- repeats its opaque source ref;
- repeats its full visible context;
- then repeats the same role/value pair again as `human_summary`.

Across the 10 frozen semantic cases, 59 prebound bindings repeat information
already present in the 65-item source-value catalog. Raw refs also recur in
association membership and per-value association fields.

A conservative Human-readable Slim View can keep:

- the same task meaning;
- source literals exactly once under local aliases;
- document/group/value structure;
- non-null semantic and structural metadata;
- Pack-owned meanings, distinctions and ambiguity rules;
- readable role-to-alias bindings;
- every exact canonical `option_id`;
- the existing unclassified reason codes.

Opaque refs, exact provenance and deterministic binding complexity remain in
the Evidence Bundle, Candidate Compilation and private evidence. The existing
canonical Choice schema remains byte-identical; no alternative choice schema
or alias-to-Choice adapter is proposed.

An offline projection over all 10 frozen semantic cases reduces model-view
UTF-8 bytes by a projected 73.4% and the repository estimator by 63.5%.
These are deterministic planning estimates, not provider-token measurements
and not evidence of model-quality improvement.

## Scope and authority

Affected authority: model-facing presentation owned by the existing
`Gate2FinancialSemanticV6PacketFactory.create` boundary.

Authority evidence:

- the [Architecture Authority Map](../../stage2/contracts/BROKER_REPORTS_ARCHITECTURE_AUTHORITIES.md)
  assigns the four-block packet, Prompt, provider-neutral minimal Choice and
  deterministic expansion to the Semantic Matcher and forbids an alternative
  choice schema;
- [`Gate2FinancialSemanticV6PacketFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate2_financial_semantic_v6_packet.py)
  is the sole V6 packet builder;
- [`_source_context`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate2_financial_semantic_v6_packet.py)
  copies source values, refs, associations and visible context;
- [`_typed_options`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate2_financial_semantic_v6_packet.py)
  repeats bound values, refs, types, visible context and summaries;
- [`_compact_type_card`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate2_financial_semantic_v6_packet.py)
  copies the six current card fields;
- the Evidence Bundle retains document identity, complete source values,
  lineage, associations, provenance and retention outside the model view.

This GOAL changes documentation only. It creates no builder, renderer,
response DTO, adapter, alias resolver or runtime flag.

## Method

The audit used only current repository factories and saved synthetic
evidence. Provider calls were zero.

1. Build the canonical 10-case V6 qualification fixture.
2. Traverse every scalar path in each exact `packet.payload`.
3. Count occurrences, case coverage and null coverage.
4. Trace each field to the Packet, Evidence Bundle, Candidate Compilation,
   Pack projection, Choice schema, validator/materializer and replay owner.
5. Construct an in-memory analysis-only Slim View; do not write or activate
   it as code.
6. Keep the current system Prompt and exact Choice response schema.
7. Replace only the user-message packet content for deterministic size
   measurement.
8. Measure minified UTF-8 bytes and
   `compact_request_utf8_bytes_div_4_plus_64_v1`.

The estimator includes `messages` and `response_format`; it is intentionally
not described as a provider tokenizer.

## Current surface

The exact model-visible packet contains four ordered blocks:

```text
task
source_context
available_type_cards
typed_options
```

The model also sees two surfaces outside `packet.payload`:

- the frozen system Prompt;
- the strict Choice response schema, including typed `option_id` enums and
  the unclassified disposition/reason-code enums.

The packet dataclass envelope also stores schema/policy versions, authority
hashes and the packet hash, but those envelope fields are not placed in the
model message today.

### Frozen-corpus field census

| Exact scalar path | Occurrences | Cases | Null observations |
| --- | ---: | ---: | ---: |
| `task.semantic_operation` | 10 | 10 | 0 |
| `task.ambiguity_rule` | 10 | 10 | 0 |
| `source_context.source_values[].source_value_ref` | 65 | 10 | 0 |
| `source_context.source_values[].value_type` | 65 | 10 | 0 |
| `source_context.source_values[].source_value` | 65 | 10 | 0 |
| `source_context.source_values[].association_ref` | 65 | 10 | 0 |
| `source_context.source_values[].association_kind` | 65 | 10 | 0 |
| `source_context.source_values[].visible_context.section_role` | 65 | 10 | 65 |
| `source_context.source_values[].visible_context.row_role` | 65 | 10 | 20 |
| `source_context.source_values[].visible_context.column_meaning` | 65 | 10 | 20 |
| `source_context.source_values[].visible_context.visible_label` | 65 | 10 | 65 |
| `source_context.associations[].association_ref` | 20 | 10 | 0 |
| `source_context.associations[].association_kind` | 20 | 10 | 0 |
| `source_context.associations[].source_value_refs[]` | 65 | 10 | 0 |
| `source_context.associations[].human_summary` | 20 | 10 | 0 |
| `available_type_cards[].input_type_id` | 12 | 6 | 0 |
| `available_type_cards[].short_meaning` | 12 | 6 | 0 |
| `available_type_cards[].required_roles[].role_id/value_type` | 36 + 36 | 6 | 0 |
| `available_type_cards[].optional_roles[].role_id/value_type` | 54 + 54 | 6 | 0 |
| `available_type_cards[].key_semantic_distinctions[].against/rule` | 24 + 24 | 6 | 0 |
| `available_type_cards[].ambiguity_rule` | 12 | 6 | 0 |
| `typed_options[].option_id` | 12 | 6 | 0 |
| `typed_options[].input_type_id` | 12 | 6 | 0 |
| `typed_options[].prebound_role_values[].role_id` | 59 | 6 | 0 |
| `typed_options[].prebound_role_values[].source_value_ref` | 59 | 6 | 0 |
| `typed_options[].prebound_role_values[].value_type` | 59 | 6 | 0 |
| `typed_options[].prebound_role_values[].source_value` | 59 | 6 | 0 |
| `typed_options[].prebound_role_values[].visible_context.*` | 59 per subfield | 6 | 18 or 59 |
| `typed_options[].prebound_role_values[].human_summary` | 59 | 6 | 0 |

Four cases have no Typed Options, so their type-card and option lists are
empty by construction.

The benchmark gives no positive observation for `section_role` or
`visible_label`: both are null in all 65 source values. That is an evidence
gap, not proof that non-null values are useless on actual documents.

## Classification legend

| Class | Meaning in this audit |
| --- | --- |
| `SEMANTICALLY_REQUIRED` | Affects understanding of financial meaning or ambiguity. |
| `STRUCTURALLY_REQUIRED` | Connects document/group/value/type/option concepts. |
| `CODE_OR_EVIDENCE_ONLY` | Required for ownership, validation, mapping, replay or audit but not as raw model text. |
| `DUPLICATED` | Repeats information already visible elsewhere in the same request. |
| `OPAQUE_NOISE` | Has no readable semantic content for the model in its current representation. |

Classification is field-specific. For example, source identity is
structurally required, while the full global `source_value_ref` string is
code/evidence-only and should be represented to the model by a local alias.

## Field-by-field classification

| Current field | Class | Evidence and proposed treatment |
| --- | --- | --- |
| `task.semantic_operation` | `SEMANTICALLY_REQUIRED` | Keep as one short human instruction; do not add another Prompt rule. |
| `task.ambiguity_rule` | `SEMANTICALLY_REQUIRED` | Keep its meaning once in the task. |
| source `source_value` | `SEMANTICALLY_REQUIRED` | Keep every authoritative literal exactly once. |
| source `value_type` | `SEMANTICALLY_REQUIRED` | Keep a readable compact type once beside the literal; it disambiguates decimal/date/currency/text/reference values. |
| source `source_value_ref` | `CODE_OR_EVIDENCE_ONLY` | The raw global ref is unreadable. Keep it in Evidence Bundle/private mapping; show `v1`, `v2`, ... locally. |
| per-value `association_ref` | `DUPLICATED` | Repeats group membership already expressed by the association list. Place the value under one local group instead. |
| per-value `association_kind` | `DUPLICATED` | Move the readable kind to the local group once. |
| `visible_context.section_role` | `SEMANTICALLY_REQUIRED` when non-null | Omit nulls; retain a non-null readable section role. Frozen cases do not test this path. |
| `visible_context.row_role` | `STRUCTURALLY_REQUIRED` when non-null | Move the row role to the local group once; omit nulls. |
| `visible_context.column_meaning` | `SEMANTICALLY_REQUIRED` when non-null | Keep as the value's readable meaning. |
| `visible_context.visible_label` | `SEMANTICALLY_REQUIRED` when non-null | Keep once; omit nulls. Frozen cases do not test this path. |
| association `association_ref` | `CODE_OR_EVIDENCE_ONLY` | Keep exact ref in Evidence Bundle; expose local `g1`, `g2`, ... aliases. |
| association `association_kind` | `STRUCTURALLY_REQUIRED` | Render as `table row`, `text segment`, or another readable structural kind. |
| association `source_value_refs[]` | `CODE_OR_EVIDENCE_ONLY` | Replace exact refs by local membership: values are nested under the group. |
| association `human_summary` | `DUPLICATED` | It mechanically restates kind and member count. The proposed structure is already human-readable. |
| deterministic-reference source values | `OPAQUE_NOISE` | Their literal is the same opaque row/scope ref. Keep them in Evidence Bundle and option bindings; render the binding target as its group alias. |
| card `input_type_id` | `STRUCTURALLY_REQUIRED` | Keep once as a readable card name and bind options through a local type alias. |
| card `short_meaning` | `SEMANTICALLY_REQUIRED` | Keep exact Pack-owned text. |
| card `required_roles[]` | `CODE_OR_EVIDENCE_ONLY` | Candidate Compiler already proved completeness; option bindings show the roles actually present. Retain the schema in the Pack/Compilation. |
| card `optional_roles[]` | `CODE_OR_EVIDENCE_ONLY` | Unbound possibilities do not help choose among already materializable options; retain in the Pack. |
| card distinction `against` | `STRUCTURALLY_REQUIRED` | Replace repeated raw type ID with a local card alias when the competing card is visible. |
| card distinction `rule` | `SEMANTICALLY_REQUIRED` | Keep Pack-owned distinction text. |
| card `ambiguity_rule` | `SEMANTICALLY_REQUIRED` | Conservative proposal keeps exact text. Splitting semantic and binding clauses requires separate Pack-owner evidence and is not part of this GOAL. |
| option `option_id` | `STRUCTURALLY_REQUIRED` | Keep the exact canonical return ID once per option; current Choice schema remains unchanged. |
| option `input_type_id` | `DUPLICATED` | Replace the second raw type ID with the local card alias. |
| binding `role_id` | `SEMANTICALLY_REQUIRED` | Keep readable role-to-alias bindings such as `amount=v1`. |
| binding `source_value_ref` | `DUPLICATED` | Replace with the existing value/group alias; exact ref remains in the Typed Option. |
| binding `value_type` | `DUPLICATED` | Already visible in the value catalog and validated by the compiler. |
| binding `source_value` | `DUPLICATED` | Already visible exactly once in the value catalog. |
| binding `visible_context.*` | `DUPLICATED` | Already visible on the source value/group; do not repeat it for every option. |
| binding `human_summary` | `DUPLICATED` | Mechanically derives from role and value. `role=alias` plus the value catalog is shorter and clearer. |
| Choice-schema `typed_option_id` enum | `CODE_OR_EVIDENCE_ONLY` but contract-required | It duplicates option IDs across request surfaces, but removing it would change the frozen Choice schema. Keep it unchanged. |
| Choice-schema unclassified disposition/reasons | `SEMANTICALLY_REQUIRED` | Keep visible in the Slim View and unchanged in the strict schema. |
| packet envelope hashes/versions | `CODE_OR_EVIDENCE_ONLY` | Already excluded from the model message; continue storing them in private evidence/replay. |
| Evidence Bundle document/page/table/row/cell lineage | `STRUCTURALLY_REQUIRED` as readable structure | Raw refs remain code-only. Project only local document/table/row/group aliases and non-null roles. |

## Document structure finding

The current packet does not expose an explicit
`document → page → section/table → row/text segment → value` hierarchy.
Instead, it exposes:

- opaque association refs;
- association kinds and flat membership;
- per-value row/section/column/label context.

The Evidence Bundle already retains exact document identity and per-value
lineage (`page_ref`, `table_ref`, `row_ref`, `cell_ref`,
`text_segment_ref`). Therefore the Slim View does not require a new source of
truth. It can project local readable paths while keeping every exact lineage
ref private and hash-linked.

The projection must omit hierarchy levels that are absent; it must not invent
a page, table, section, row label or visible role.

## Repeated-information map

### Source identity

One exact source ref can occur:

1. on the source value;
2. in association membership;
3. once for every option binding that uses it.

The identity is necessary for code, but the full string is not necessary for
the model. A local alias preserves identity within the view.

### Literal and type

Each bound option currently repeats both the literal and `value_type` already
present in `source_context`. With 59 bindings, the current frozen workload
contains 59 such repetitions.

### Visible context

Each binding repeats the complete four-field `visible_context` of its source
value. This includes 59 repeated `section_role` values and 59 repeated
`visible_label` values even though all are null in the frozen workload.

### Human summaries

`human_summary` is mechanically derived:

```text
<role_id> is prebound to <source_value>
```

It adds no field not already present in the same binding object.

### Type and role schema

Type IDs occur on cards and options. Full required/optional role schemas also
appear before a list of already-complete option bindings. The compiler and
Typed Option authority—not the model—own structural completeness.

### Generic association summaries

`human_summary` for an association repeats its kind and member count. A nested
readable group makes the relationship visible without a second sentence.

## Proposed Slim Semantic View

The normative research proposal is
[Broker Reports Gate 2 Financial Semantic Slim View](../../stage2/proposals/BROKER_REPORTS_GATE2_FINANCIAL_SEMANTIC_SLIM_VIEW.proposal.md).

Its model-visible shape is:

```text
task
source
  document
  groups[]
    local alias
    readable kind and non-null roles
    values[]
      local alias
      readable meaning
      exact literal
      compact value type
type_cards[]
  local alias
  exact type name
  Pack-owned short meaning
  Pack-owned distinctions
  Pack-owned ambiguity rule
choices[]
  optional display alias
  exact canonical return_id
  local type-card alias
  role=source/group-alias bindings
unclassified[]
  existing reason codes
```

The model still returns the exact `return_id` through the unchanged canonical
Choice schema. Local source/group/type aliases are presentation-only and
never become canonical refs.

## Full mapping

```text
Gate 1 normalized evidence
  → authoritative Evidence Bundle
    - exact literals and global source refs
    - exact document/value lineage
    - associations, provenance and retention
  → existing Candidate Compiler
    - exact Typed Options and role bindings
  → existing V6 Packet owner
    - current full packet remains canonical during implementation proof
    - deterministic local-alias receipt is built from existing authorities
    - non-active Slim View is rendered from the same construction
  → unchanged Prompt + unchanged strict Choice schema
  → model returns exact typed option_id or unclassified reason_code
  → existing deterministic expansion
    - option_id resolves to the original code-owned Typed Option
    - unclassified retains the full Evidence Bundle
  → existing validator/materializer
  → existing exact evidence and replay
```

There is no model-generated ref, binding, type ID or retained-value set.

## Lossless alias design

Aliases are local to one packet and assigned in deterministic source order:

- values: `v1`, `v2`, ...;
- structural groups: `g1`, `g2`, ...;
- visible type cards: `type1`, `type2`, ...;
- optional display-only choices: `A`, `B`, ...;
- exact option `return_id`: unchanged.

The private alias receipt contains:

```text
source_packet_hash
slim_view_hash
value_alias → exact source_value_ref
group_alias → exact association/lineage ref
location_alias → exact page/table/row/text-segment ref
type_alias → exact input_type_id
display_choice_alias → exact option_id
evidence_only_source_refs
integrity_sha256
```

Required invariants:

- alias keys are unique within their namespace;
- every displayed literal maps to exactly one Evidence Bundle value;
- every displayed group maps to exact existing association/lineage;
- every displayed location level maps to one exact existing lineage ref;
- every displayed option uses an exact compiled option ID;
- every displayed binding target resolves to its original value or group;
- deterministic reference values may be omitted from the model view only
  when they remain in the Typed Option and alias receipt;
- no alias is accepted in the canonical Choice;
- unclassified expansion still retains the complete Evidence Bundle;
- alias receipt and Slim View hashes are preserved privately for replay.

## Token-size baseline and projection

### Measurement boundary

- cases: all 10 frozen semantic-model cases;
- current bytes: minified UTF-8 of exact `packet.payload`;
- proposed bytes: minified UTF-8 of the analysis-only conservative view;
- request estimate: current Prompt and exact response format with only the
  user-message packet replaced;
- estimator: `compact_request_utf8_bytes_div_4_plus_64_v1`;
- provider calls: zero.

The conservative view retains exact Pack `short_meaning`, distinction rules
and full ambiguity rules. It does not count a more aggressive rewrite of type
semantics.

### Per-case measurements

| Case | Options | Values | Current packet bytes | Slim bytes | Byte reduction | Current est. tokens | Slim est. tokens | Token reduction |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `syn_successor_v2_unique_cash` | 2 | 6 | 9,638 | 2,763 | 71.3% | 2,937 | 1,077 | 63.3% |
| `syn_successor_v2_unique_printed_total` | 2 | 6 | 9,905 | 2,761 | 72.1% | 3,004 | 1,077 | 64.1% |
| `syn_successor_v2_multiple_compatible` | 0 | 8 | 4,246 | 837 | 80.3% | 1,393 | 494 | 64.5% |
| `syn_successor_v2_no_registry_type` | 2 | 6 | 9,770 | 2,758 | 71.8% | 2,970 | 1,076 | 63.8% |
| `syn_successor_v2_missing_discriminator` | 2 | 5 | 9,145 | 2,659 | 70.9% | 2,797 | 1,047 | 62.6% |
| `syn_successor_v2_detail_vs_subtotal` | 0 | 7 | 3,822 | 772 | 79.8% | 1,278 | 474 | 62.9% |
| `syn_successor_v2_adjacent_equal` | 0 | 7 | 3,724 | 768 | 79.4% | 1,253 | 473 | 62.3% |
| `syn_successor_v2_adjacent_fx` | 0 | 8 | 4,066 | 841 | 79.3% | 1,348 | 495 | 63.3% |
| `syn_successor_v2_optional_missing` | 2 | 6 | 9,779 | 2,761 | 71.8% | 2,973 | 1,077 | 63.8% |
| `syn_successor_v2_forbidden_neighbour` | 2 | 6 | 9,875 | 2,762 | 72.0% | 2,997 | 1,077 | 64.1% |
| **Total** | 12 | 65 | **73,970** | **19,682** | **73.4%** | **22,950** | **8,367** | **63.5%** |

Ranges:

- current estimator: 1,253–3,004 tokens;
- proposed estimator: 473–1,077 tokens;
- median projected token reduction: 63.55%;
- private alias receipts: 11,136 UTF-8 bytes total, not model-visible.

### Representative current block anatomy

| Case | Task | Source context | Type cards | Typed Options |
| --- | ---: | ---: | ---: | ---: |
| `syn_successor_v2_unique_cash` | 218 B | 2,950 B | 2,630 B | 3,772 B |
| `syn_successor_v2_no_registry_type` | 218 B | 3,035 B | 2,630 B | 3,819 B |

Typed Options are the largest block in both two-option smoke cases even
though they mainly repeat source-catalog fields.

### Observed provider counts

The saved exact executions reported:

| Model | Typed case | Unclassified case |
| --- | ---: | ---: |
| Nano | 2,484 input tokens | 2,500 input tokens |
| Haiku | 3,319 input tokens | 3,359 input tokens |

The canonical requests differed only at `$.model`, but provider token counts
are model/provider-specific. These observed values validate neither the
repository estimator nor the projected Slim count and must not be used as an
exact cross-provider comparison.

## Removal and reduction risk register

| Removed or reduced model field | Why model does not need the current form | Where exact data remains | Deterministic mapping | Main risk | Required next implementation test |
| --- | --- | --- | --- | --- | --- |
| global `source_value_ref` strings | They are opaque identifiers, not financial meaning. | Evidence Bundle, Typed Options, private evidence. | `vN → exact ref` in hash-bound alias receipt. | collision or wrong value | bijection, stable order, tamper and collision rejection |
| raw association refs | The model needs grouping, not global row IDs. | Evidence Bundle associations and lineage. | `gN → exact association/lineage ref`. | values grouped under wrong row | exact member-set and lineage parity tests |
| per-value association ref/kind | Repeats the enclosing group. | Evidence Bundle and group mapping. | nesting under `gN`. | relation silently lost | every displayed value has exactly one resolved group |
| deterministic reference literals | They repeat opaque row/scope IDs and add no readable meaning. | Evidence Bundle and exact option bindings. | binding target uses `gN`; option ID still resolves to exact binding. | loss of statement scope or label evidence | exact option-binding parity, materialization and replay tests |
| null visible-context fields | Null carries no readable fact. | Evidence Bundle exact value object. | omission is normalized to original null in the receipt. | absent confused with unknown non-null | omission-only-for-null property tests |
| repeated option literal | Already visible once in the source catalog. | Evidence Bundle and Typed Option. | option binding points to `vN`. | wrong displayed value | role-to-value alias resolution equality |
| repeated option `value_type` | Already visible once and code validates compatibility. | Evidence Bundle, Pack role schema and compiler receipt. | `vN` lookup. | hidden incompatible binding | compiler parity and negative tamper tests |
| repeated option visible context | Already visible once on value/group. | Evidence Bundle and source section of view. | `vN`/`gN` lookup. | option loses discriminating context | binding target resolves to exact context object |
| binding `human_summary` | Fully derivable from role and resolved alias. | No authority depends on the sentence. | deterministic readable render. | readability regression | golden readable-view snapshots and duplicate-text test |
| option's repeated raw `input_type_id` | Card already owns the type name. | Candidate Compilation and card. | local `typeN → exact type ID`. | option linked to wrong card | type-alias bijection and option/card parity |
| card required-role schemas | Code has already proven option completeness; bound roles are visible. | Semantic Pack and Candidate Compilation. | exact option remains unchanged. | model used schema for type distinction | structural parity now; separately authorized semantic qualification before activation |
| card optional-role schemas | Unbound possibilities do not alter an existing materializable record. | Semantic Pack. | none needed in model view. | useful discriminator removed | frozen-view snapshot plus separately authorized qualification before activation |
| distinction `against` raw IDs | Local visible card link is enough. | Semantic Pack exact card. | `typeN → exact type ID`. | comparison points to wrong card | cross-card alias parity |
| generic association summary | Restates group kind and member count. | It is derived, not authoritative. | readable group render. | less readable structure | human-readable snapshot and required group labels |

Non-null `section_role`, `column_meaning`, `visible_label` and readable
association kinds are not on the removal list.

## Relationship to the Nano/Haiku forensic

The merged GOAL 1 report proved:

- Nano and Haiku received exact-equal Prompt, Packet and response schema;
- the only canonical-request difference was `$.model`;
- Haiku matched both expected answers;
- Nano selected the first typed option in both cases.

That differential supports `OPTION_CONFUSION` and
`MODEL_IGNORED_UNCLASSIFIED` for the two Nano observations. It does not prove
that opaque refs or packet length caused the errors.

Therefore this GOAL makes two separate claims:

1. redundancy/noise exists by exact field provenance and repetition;
2. removing it is a justified design hypothesis, not a proven semantic fix.

No Prompt, Pack or expected answer should be changed in response to the Nano
result without a separate causal proof.

## Exact next implementation boundary

One narrow code-only GOAL is permitted:

1. Reuse `Gate2FinancialSemanticV6PacketFactory.create` as the sole builder.
2. Extend the same owner to compute a non-active Slim candidate and private
   alias receipt alongside the unchanged current payload.
3. Keep current `packet.payload`, `packet_hash`, Prompt, request route and
   Choice schema byte-identical.
4. Do not add a second packet module, factory, compiler or alternative Choice
   schema.
5. Preserve exact option IDs in the candidate view.
6. Preserve all omitted refs/lineage/bindings in Evidence Bundle,
   Compilation and private evidence.
7. Add deterministic candidate-render and alias-parity tests.
8. Record exact size metrics from the implemented candidate.
9. Make zero provider calls.
10. Do not activate the candidate in runtime.

Required deterministic tests:

- current payload/hash regression is byte-identical;
- alias namespaces are deterministic and collision-free;
- each displayed literal is exact and appears once;
- displayed structure resolves to exact lineage/association membership;
- all non-null semantic metadata is preserved;
- null-only fields are omitted and reconstruct as null;
- every choice uses an exact compiled option ID;
- every displayed role binding resolves to the exact original source/group;
- deterministic-reference bindings remain exact code-side;
- canonical Choice schema hash is unchanged;
- unclassified retention set remains the full Evidence Bundle;
- private alias/view hashes fail closed on tampering;
- evidence replay and total materialization remain exact;
- architecture test proves there is no second builder or choice schema.

Those tests can close structural and mapping risks. They cannot prove that a
model reasons equally well with shorter context.

## Later qualification and activation boundary

After the code-only candidate is accepted and merged, a separate explicitly
authorized qualification GOAL must:

1. show the exact Slim input and exact output;
2. run the same two frozen smoke cases first;
3. stop before the full benchmark if either case fails;
4. run the full frozen benchmark only after both smoke cases pass;
5. compare exact current-view and Slim-view semantic outcomes;
6. keep fallback/repair/hidden retry at zero;
7. preserve separate technical, semantic and product verdicts.

Runtime activation requires another parity proof. The current report does not
authorize provider calls or activation.

## Acceptance

| Item | Result |
| --- | --- |
| `CURRENT_PACKET_FIELDS` | `FULLY_INVENTORIED` |
| `FIELD_CLASSIFICATION` | `COMPLETE` |
| `DUPLICATED_INFORMATION` | `IDENTIFIED` |
| `OPAQUE_MODEL_NOISE` | `IDENTIFIED` |
| `SEMANTIC_METADATA` | `EXPLICIT` |
| `DOCUMENT_STRUCTURE_METADATA` | `EXPLICIT_WITH_CURRENT_GAP` |
| `PROPOSED_SLIM_VIEW` | `HUMAN_READABLE` |
| `LOSSLESS_ALIAS_MAPPING` | `DESIGNED` |
| `TOKEN_BASELINE` | `10_CASE_DETERMINISTIC` |
| `PROJECTED_TOKEN_REDUCTION` | `63.5_PERCENT_ESTIMATOR` |
| `RUNTIME_BEHAVIOR_CHANGED` | `NO` |
| `PROVIDER_CALLS` | `ZERO` |
| `PROMPT_OR_PACK_CHANGE` | `ZERO` |
| `CANONICAL_CHOICE_CHANGE` | `ZERO` |
| `DOCUMENTATION` | `CURRENT_IN_THIS_PR` |

## Verification

```text
Current factory semantic cases: 10
Current source values: 65
Current source associations: 20
Current type cards: 12
Current prebound bindings: 59
Representative Slim JSON: PARSED
Representative task vs current task: EXACT
Representative option IDs vs compiled options: EXACT
Representative Slim bytes: 2,763
Representative request estimate: 1,077
Provider calls: 0
Privacy scan: PASSED
Markdown relative links: 9 checked, 0 broken
Focused packet/architecture regression: 27 passed
Full service suite: 1846 passed, 20 skipped, 5 SWIG-only warnings
git diff --check: PASSED
```

## Privacy and evidence boundary

All measurements use frozen synthetic cases and current repository
factories. The report contains no credential, provider response ID, private
filesystem path, raw provider envelope, hidden reasoning or customer value.

Actual-corpus aliases, literals and hierarchy remain private. Repository-safe
evidence may publish only classifications, counts, aggregate size metrics,
view/alias hashes and redacted examples.
