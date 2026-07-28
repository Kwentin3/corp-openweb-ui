# Broker Reports Gate 2 LLM Semantic Context V2

Status: `VERSIONED_DOCUMENTATION_CANDIDATE_NOT_IMPLEMENTED_NOT_MODEL_VISIBLE`

Contract identity:
`broker_reports_gate2_llm_semantic_context_v2`

Contract version: `2.0.0`

Candidate schema identity:
`broker_reports_gate2_llm_semantic_context_v2_candidate`

Candidate policy identity:
`broker_reports_gate2_managed_semantic_decision_context_v2`

Local response-profile identity:
`broker_reports_gate2_financial_semantic_local_choice_v2_candidate`

## 1. Purpose

This contract defines the complete model-visible boundary for one future,
non-active Gate 2 financial semantic decision candidate.

It is the successor of
[LLM Semantic Context v1](./BROKER_REPORTS_GATE2_LLM_SEMANTIC_CONTEXT.v1.md),
not an in-place revision of the existing Slim View v2 implementation. The
names are intentionally distinct:

- **Slim View v2** is an implemented historical candidate conforming to
  Context v1;
- **Semantic Context V2** is this new contract and is not implemented.

The target is a short specialist-facing decision card. The model receives
only source meaning, evidence-derived structure, managed type meaning,
readable prebound relationships, selectable local choices and managed
unclassified-reason meaning. Exact identity and record construction remain
code-owned.

The Managed Semantic Decision Context GOAL 3 that created this document is not
the historical staged-program GOAL 3 recorded in Context v1. Historical
receipts and statuses retain their original numbering.

## 2. Complete request boundary

Conformance covers every byte visible to the model:

1. the system message;
2. the complete user-message Context V2 JSON;
3. every response-schema field, enum, title and description;
4. any provider-specific wrapper content that the provider exposes to the
   model.

Transport headers, provider response metadata and raw provider envelopes are
not model-visible. They remain private evidence.

The V2 candidate keeps the current V6 system prompt byte-exact:

```text
Return exactly one JSON object that conforms to the supplied strict response schema. Use only the task and evidence in the user message.
```

Its unchanged authority identity is:

```text
CURRENT_V6_PROMPT_VERSION:
financial_semantic_v6_candidate_choice_v1

CURRENT_V6_PROMPT_HASH:
59143216c08d6e5069bee757346508906cbaf5575b76bebee440d94dede8642b
```

The current generic task instruction is also retained byte-exact and is
printed in section 5. There are no other system or developer messages. GOAL 3
changes no Prompt, option order, Pack wording, reason wording, model or
provider. A provider wrapper is conforming only when it does not inject
additional model-visible instructions, labels or schema prose; any such bytes
would become part of this contract and require a new version.

## 3. Authority and construction boundary

`Gate2FinancialSemanticV6PacketFactory.create` remains the sole packet and
context-candidate construction owner. A later implementation may extend that
factory to return:

- the unchanged active V6 packet;
- the unchanged historical Slim View v2 candidate;
- one non-active Context V2 candidate;
- one packet-owned private Context V2 mapping receipt.

The existing V6 Choice factory remains the sole response-schema owner. It may
later add one non-active local-choice V2 profile that normalizes to the
unchanged canonical V6 Choice.

The existing Context Linter remains the sole complete-request sealer. Its
future V2 extension consumes the packet-owned candidate/mapping receipt plus
the Prompt and Choice-owned schema, then emits a separate private sealed-
request receipt. The packet factory must not import or reconstruct Prompt or
Choice outputs, and the linter receipt must not duplicate the packet mapping.

No second packet builder, Semantic Pack, decision-reason catalog, Choice
authority, binding resolver, provider semantic adapter or materializer is
permitted.

```text
validated Evidence Bundle + Candidate Compilation
validated managed Pack + validated reason catalog
  -> existing Packet factory
     -> non-active Context V2 + private mapping receipt
  -> existing Choice factory
     -> non-active local response schema
  -> existing Context Linter extension
     -> sealed request + private sealed-request receipt
  -> existing normalizer / expansion / validator / materializer / replay
```

The packet factory is a deterministic renderer, not a financial-semantic
author.

## 4. Version-pinned semantic assets

The candidate projects meaning from exactly two existing authorities:

| Meaning | Sole data authority | V2 treatment |
| --- | --- | --- |
| financial types, roles, distinctions and ambiguity guidance | Financial Semantic Pack v1, semantic version `1.0.0` | project exact selected fields through a versioned extension of the existing Pack projection |
| unclassified reason titles, definitions, usage and contrasts | Financial Decision Reason Catalog v1, semantic version `1.0.0` | project exact selected fields in catalog display order |

Pack and catalog identities, versions and integrity hashes are required in the
private mapping receipt and forbidden in the model view.

The GOAL 3 contract pins:

```text
MANAGED_ASSET_FAMILY:
broker_reports_gate2_financial_domain_assets@1.1.0

MANAGED_ASSET_FAMILY_MANIFEST_SHA256:
4e5328554056741ecb783d130a5fd43034a6876484a25c98dfdd5e68bf76499d

MANAGED_ASSET_FAMILY_RUNTIME_ACTIVATION:
false

FINANCIAL_EVIDENCE_REGISTRY:
broker_reports_gate2_financial_evidence_registry@broker_reports_gate2_financial_evidence_registry_v1

FINANCIAL_EVIDENCE_REGISTRY_SHA256:
0bac59aad259b9e11a5037bb73b09642c2a87fd2baca36b8e4db7c5d5e852ac8

FINANCIAL_SEMANTIC_PACK:
broker_reports_managed_financial_semantic_pack@1.0.0

FINANCIAL_SEMANTIC_PACK_INTEGRITY_SHA256:
ab0b5aaaa4cd8133ab26d7dce8e501770c2d14f2c1bd2205cbad3fa2c6e0e7f8

DECISION_REASON_CATALOG:
broker_reports_gate2_financial_decision_reason_catalog@1.0.0

DECISION_REASON_CATALOG_INTEGRITY_SHA256:
d7290593410cafd6b35281ed3a6159802f0d7e87b7a085f3ec2cd2b46f4a3e15

DECISION_CODE_CONTRACT:
broker_reports_gate2_financial_evidence_decision_v1

CONTEXT_V2_PACK_PROJECTION_PROFILE:
broker_reports_gate2_financial_semantic_projection_v2_candidate@2.0.0

CONTEXT_V2_REASON_PROJECTION_PROFILE:
broker_reports_gate2_financial_decision_reason_projection_v1_candidate@1.0.0
```

For each projection profile, the text before `@` is the receipt identity and
the text after it is the receipt version. The projection hash is request-
specific SHA-256 over `context_v2_integrity_json_v1` of that exact private
projection object.

Candidate construction must fail before transport unless the family manifest,
Registry snapshot, Pack and reason-catalog snapshots validate byte/semantic
integrity, code-set parity, Pack `source_baseline` parity with the exact
Registry version/hash, and `runtime_activation=false`. The current
live/closed-world family pointer remains v1.

The current closed-world type projection drops Pack `title`; V2 must
version/extend that existing projection authority. Packet code must not read
the Pack asset directly.

The reason-catalog validator currently belongs to the managed-family build
path. A future runtime-safe candidate implementation must consume a validated,
closed-world snapshot from the same managed-asset authority. It must not
import `scripts/`, read repository files at runtime, embed the human wording
in Python or introduce a second catalog loader.

Family v2 and the reason catalog remain inactive repository drafts. Selecting
their wording for this non-active contract does not publish, activate or
install them.

## 5. Closed top-level model view

The Context V2 JSON object has these ordered fields:

1. `task`;
2. `source`;
3. `type_cards`;
4. `choices`;
5. `shared_relationships`, only when non-empty;
6. `unclassified_reasons`.

No contract identity, schema version, asset identity, hash or provider
metadata is rendered in this object.

`task` is the current exact generic instruction:

```text
Select a typed option only when the visible source uniquely supports its complete prebound record; otherwise select unclassified.
```

The task appears once in the complete request. Pack and reason cards must not
repeat it.

## 6. Readable source projection

### 6.1 Structure

`source.document` is the readable root. Its non-empty hierarchy may contain:

```text
document
  -> table
    -> row
      -> authoritative semantic values
  -> row when table lineage is absent
    -> authoritative semantic values
  -> text segment
    -> authoritative semantic values
  -> evidence group
```

The `document` object contains exactly one non-empty `children` array and no
other fields. Values never attach directly to the document root.

Only structure established by Evidence Bundle association or lineage may be
rendered. The current Evidence Bundle provides table/row lineage,
`table_row` and `text_segment` associations, and reference-only fallback
groups. It does not own a section-node object or a structural-node label.
Consequently V2 must not emit a `section` node or structural `label`.
Per-value `visible_label` is not promoted into either field. A later
Evidence Bundle version may add either authority only through a new Context
contract version.

Missing levels and containers with neither visible content nor an inbound
relationship are omitted. A reference-only `evidence group` may have no
visible value because its sole purpose is to provide one evidence-derived
target for a necessary relationship. The renderer may not invent a page,
section, table, row, segment, label, role or relationship.

The upstream Evidence Bundle permits an all-`source_reference` value set. If
such a bundle has no necessary inbound relationship, the completed visible
hierarchy is empty. V2 must then fail before lint/transport with
`financial_semantic_context_v2_visible_hierarchy_empty`; it must not emit an
empty `document.children` array or invent a fallback group.

The structural-node grammar is closed per kind. Fields occur in the listed
order and no other combination is valid:

| Kind | Exact allowed fields and omission |
| --- | --- |
| `table` | optional `structure_key`, required `kind`, required non-empty `children`; roles and `values` are forbidden |
| `row` | optional `structure_key`, required `kind`, optional non-null `section_role`, optional non-null `row_role`, required non-empty `values`; `children` is forbidden |
| `text segment` | optional `structure_key`, required `kind`, optional non-null `section_role`, optional non-null `row_role`, required non-empty `values`; `children` is forbidden |
| `evidence group` | optional `structure_key`, required `kind`; roles, `children` and `values` are forbidden |

`structure_key` is present only when a visible relationship must distinguish
or point to the node. Roles are mechanically readable exact Evidence Bundle
roles. The `kind` value is exactly the readable string in the first column.

When one visible node of the required kind is structurally unique, a
relationship may say `the only visible row`, `the only visible table`,
`the only visible text segment` or `the only visible evidence group`.
No numeric structural key is then emitted.

### 6.2 Values

Every validated Evidence Bundle `source_value` whose `value_type` is not
`source_reference` appears exactly once. This is the closed semantic-literal
coverage denominator; the renderer has no relevance filter.

| Field | Rule |
| --- | --- |
| `value_key` | optional request-local key; present only when a visible relationship consumes it |
| `meaning` | first accepted candidate from the exact rendered-candidate algorithm below |
| `literal` | exact authoritative Evidence Bundle literal |
| `value_type` | exact source-value type renderer defined below |
| `label` | exact non-null visible label only when distinct from both `meaning` and `literal` |

Values without a visible consumer keep their literal, meaning, type and
structure but have no `value_key`. Thus the four current zero-choice cases do
not expose 22 unused value aliases.

Two distinct source values with equal text remain two distinct structural
occurrences. They are not collapsed. An authoritative source literal is never
copied into a choice label, relationship, summary, type card or reason card.
Therefore `duplicate_literals_total=0` means that no authoritative semantic
`source_value_ref` is projected more than once; it does not erase two
different source occurrences merely because their literal strings are equal.
The `meaning`/`label` fallbacks also prevent the same occurrence's literal
from being copied immediately into its own metadata.

For Evidence Bundle `column_meaning`, `section_role` and `row_role`, a value
matching the closed machine-identifier form `[a-z][a-z0-9_-]*` replaces every
maximal `_` or `-` run with one ASCII space. Other non-null strings are
preserved byte-exact as already human-readable evidence text. `visible_label`
is always preserved byte-exact.

Source `value_type` is rendered by removing exactly one leading `source_`
when present, then applying the same maximal-run replacement. No other prefix,
suffix, case or vocabulary rewrite is allowed.

`meaning` candidates are evaluated only after their specified rendering, with
exact Unicode code-point comparison and no trim, case-fold or normalization:

1. rendered non-null `column_meaning`;
2. exact non-null `visible_label`;
3. rendered `value_type`.

The first non-empty candidate unequal to `literal` is selected. If none is
available, candidate construction fails closed with
`financial_semantic_context_v2_meaning_unavailable`. The optional `label` is
then emitted only when the exact `visible_label` is non-empty and differs from
both the selected rendered `meaning` and `literal`. Every mechanically
rendered field maps to its exact authority value in the private mapping
receipt.

`source_reference` literals remain entirely code-only. Their readable
eligibility meaning may be represented by a relationship to a structural
location. The exact value remains in the Evidence Bundle and is retrievable
through the `source_value_ref` retained by the private mapping receipt and
Typed Option.

### 6.3 Deterministic hierarchy and local keys

The future renderer uses these closed ordering and assignment rules:

1. iterate every non-reference Evidence Bundle `source_value` in its validated
   canonical order;
2. group a table node by exact non-null `lineage.table_ref`;
3. group a table-row node by the exact tuple
   `{association_ref, lineage.row_ref, lineage.table_ref, section_role,
   row_role}` and attach it to its table when `lineage.table_ref` is non-null,
   otherwise directly to `document`;
4. group a text-segment node by the exact tuple
   `{association_ref, lineage.text_segment_ref, section_role, row_role}` and
   attach it directly to `document`;
5. the first canonical non-reference source-value occurrence fixes sibling
   order, while a table parent precedes its rows;
6. append any necessary reference-only fallback evidence groups in canonical
   reference-value order;
7. traverse the completed visible hierarchy depth-first, pre-order;
8. assign `structure_1`, `structure_2`, ... contiguously only to traversed
   nodes that have an inbound relationship and cannot be named by one of the
   unique-location phrases in section 6.1;
9. assign `value_1`, `value_2`, ... contiguously, in that same hierarchy and
   within-node value order, only to non-reference values with an inbound
   relationship.

Structural reference resolution reuses the maintained resolver's exact
candidate semantics. On creation, a table node is registered under its
non-null `table_ref`; a row under its non-null `association_ref`, `table_ref`
and `row_ref`; a text segment under its non-null `association_ref` and
`text_segment_ref`; and a fallback evidence group under its non-null
`association_ref`, `table_ref`, `row_ref` and `text_segment_ref`. Registration
order is node-creation order and duplicate registration of the same node under
one ref is ignored. `page_ref` and `cell_ref` never register candidates.

For each hidden `source_reference`, in canonical reference-value order:

1. initialize `candidates` to the ordered nodes registered under its
   `association_ref`, or the empty list;
2. visit non-null `lineage.text_segment_ref`, `lineage.row_ref` and
   `lineage.table_ref` in that order;
3. obtain `lineage_candidates` registered under the current ref;
4. if `candidates` is empty, replace it with `lineage_candidates`;
5. otherwise intersect while preserving current candidate order and replace
   `candidates` only when that intersection is non-empty; an empty
   intersection preserves the previous candidates;
6. if exactly one candidate of kind `row` or `text_segment` remains, select
   it; otherwise, if exactly one candidate of any kind remains, select it;
7. otherwise create or reuse one fallback evidence group keyed by the exact
   tuple `{association_ref, lineage.page_ref, lineage.table_ref,
   lineage.row_ref, lineage.text_segment_ref}`, register it as above, and
   select it.

A unique-location phrase is permitted only when the completed model-visible
hierarchy contains exactly one node of that kind. Otherwise the resolved node
must receive `structure_N`.

Each suffix is only a contiguous ordinal in the existing authority-owned
canonical order; it neither copies nor encodes an opaque value and is not
reversible to one. Upstream canonical order may itself be established from
private refs or hash-derived identities, and V2 does not change that order.
Omitted keys do not reserve a number. Repeating the same validated inputs
produces the same hierarchy and local keys.

## 7. Decision type set and type cards

### 7.1 Decision type set

V2 does not equate “available financial type” with “successfully compiled
Typed Option”.

For every semantic source, the private available type set comes from the exact
validated Registry snapshot after its version/hash has passed exact Pack
`source_baseline` parity: every active Registry type whose projected Pack
semantic contract has `compatible_source_families` containing the Evidence
Bundle `source_family_id`. The set is independent of compiled choices and is
ordered by the existing canonical type-contract order.

The unique type IDs observed across Candidate Compilation `typed_options` and
`blocked_bindings` are a private parity signal only. Under the current
Compiler, each available type is attempted for each source association, so
the Compiler-observed type set must equal the authority-derived available
type set for a non-empty semantic route. A mismatch is a technical pipeline
error and prevents transport.

The ordered private `compiler_observed_type_ids` array appends each type ID at
its first occurrence while scanning all `typed_options` in exact Compiler
order, then all `blocked_bindings` in exact Compiler order. Repeated IDs are
ignored after first occurrence.

Blocked status means only that deterministic construction did not produce a
complete option for that association/type pair. It is not evidence that the
type is semantically plausible or implausible. Block codes are never
model-visible.

Every decision-type-set member receives one model-visible type card, including
when no Typed Option was compiled. This closes the Context v1 information gap
in which an `ambiguous_registry_type` decision could be requested while zero
type meanings were visible. It is a contract requirement only; compatibility
is not proven until implementation and local proof.

Cards retain the authority-derived canonical type-contract order.
`type_1`, `type_2`, ... are assigned contiguously in that order. That existing
private order may be established from `input_type_id`; V2 neither changes nor
exposes the identity. Compiler results and provider properties do not reorder
it.

### 7.2 Type-card shape

Each type card contains:

| Field | Rule |
| --- | --- |
| `type_key` | unique deterministic request-local `type_1`, `type_2`, ... |
| `title` | exact Pack-owned title |
| `meaning` | exact Pack-owned definition |
| `semantic_class` | exact Pack-owned semantic class |
| `required_evidence` | non-empty exact Pack required roles projected as readable evidence requirements |
| `optional_evidence` | exact Pack optional roles projected as readable evidence requirements; omitted when empty |
| `conditional_requirements` | ordered mechanically readable Pack `date_period_requirement` then `currency_unit_requirement` rules |
| `forbidden_evidence` | ordered mechanically readable Pack forbidden roles; omitted when empty |
| evidence requirement `role` | mechanically readable Pack role ID |
| evidence requirement `value_type` | mechanically readable Pack value type |
| evidence requirement `cardinality` | mechanically readable exact Pack cardinality |
| `synonyms` | non-empty ordered array of all exact Pack synonyms |
| `distinctions` | all exact Pack-owned semantic distinctions |
| distinction `against_type_key` | local key when the Pack target is another visible type; mutually exclusive with `against_concept` |
| distinction `against_concept` | mechanically readable Pack target when it is not another visible type; exact target stays private |
| distinction `rule` | exact Pack-owned distinction rule |
| `examples` | non-empty ordered array of all exact Pack examples |
| `counterexamples` | non-empty ordered array of all exact Pack counterexamples |
| `unclassified_when` | non-empty ordered array of exact Pack-owned ambiguity-guidance entries |
| `model_guidance` | exact Pack-owned model guidance |

The card omits type ID, lifecycle, compatible-source administration, exact
role IDs and `source_ref_required` flags, identity-role administration,
source-sign preservation policy, materialization/validation profiles,
evidence refs, tests, compatibility administration, Pack identity and hashes.
Identity roles and source-sign policy remain backend-only because the model
does not construct record identity or transform a sign; required/conditional
evidence, definition, distinctions and guidance already state the type-choice
boundary. The card is compact because it retains only fields used to compare
source meaning and evidence against a type, not because it truncates those
decision rules.

The mechanical readable renderer is closed: an external-concept identifier
first drops one terminal `_v` plus decimal version number, then replaces every
maximal `_` or `-` run with one ASCII space; role,
conditional-requirement and cardinality identifiers use the same replacement;
a role whose Pack value type is
`source_reference` also drops one terminal ` ref`; value types first drop one
leading `source_` and then use the same replacement. It performs no
translation, synonym substitution or financial interpretation. Exact source
identifiers remain private and are mapped field-by-field in the receipt.

Mechanical rendering must be injective for distinct exact identifiers within
each request-local semantic namespace: relationship/evidence roles, value
types, cardinalities, conditional requirements and external distinction
targets. Equal exact inputs may repeat, but two different exact inputs may not
produce the same readable string. Such a collision fails before factoring or
lint with `financial_semantic_context_v2_readable_projection_collision`;
factoring may never merge bindings merely because their rendered roles
collide. The same rule applies to distinct machine-form Evidence Bundle
metadata values within their respective `column_meaning`, `section_role` and
`row_role` namespaces.

For two or more visible types, every pair must have an applicable direct
Pack-owned contrast in at least one direction. Missing contrast coverage is a
local semantic-asset/projection defect and prevents transport. The renderer
must not invent the missing wording. Every Pack distinction is retained,
including contrasts against non-visible concepts such as source-detail rows;
only the target identifier is mechanically rendered into readable text and
mapped back to its exact Pack source in the private mapping receipt.

## 8. Necessary readable relationships

Context V2 replaces repeated `role=alias` strings with structured,
human-readable relationships.

A relationship contains:

| Field | Rule |
| --- | --- |
| `role` | mechanically readable form of the exact Pack role ID |
| `value_key` | target semantic value key; mutually exclusive with `structure_key` and `location` |
| `structure_key` | target structural key when several nodes must be distinguished |
| `location` | generic evidence-derived unique-location phrase when no structural key is necessary |
| `applies_to` | ordered local `choice_key` subset; allowed only on a factored top-level relationship that does not apply to every visible choice |

Exactly one target field is present. There are no nulls.

A relationship is model-visible only when:

1. it binds a Pack-declared semantic-value role to a visible source value; or
2. it states that a required Pack `source_reference` eligibility role is
   bound to an evidence-derived visible location; or
3. it distinguishes otherwise selectable choices.

All other exact bindings remain backend-only.

Factoring preserves the unchanged flat Candidate Compiler choice order:

- one readable role/target relationship used by two or more choices is
  emitted exactly once in top-level `shared_relationships`;
- `applies_to` is omitted only when the relationship applies to every visible
  choice;
- otherwise `applies_to` lists the affected `choice_key` values in canonical
  choice order;
- a relationship used by exactly one choice is emitted once in that choice's
  `relationships`;
- no relationship is both shared and choice-local, and empty relationship
  arrays are omitted.

Thus a multi-association source does not broaden a relationship from one
choice subset to another, does not duplicate that relationship and does not
introduce a second grouping identity.

For the current frozen suite this rule is expected to factor 59 exact binding
occurrences into 35 readable relationships:

- 23 semantic role/value relationships;
- 12 readable scope or printed-label-evidence predicates;
- 24 duplicate occurrences removed from the model view;
- all 59 exact role/source-ref bindings retained privately.

Those counts are a GOAL 4 implementation oracle, not V2 schema constants.

## 9. Readable choices

Each selectable Typed Option is represented by:

| Field | Rule |
| --- | --- |
| `choice_key` | unique deterministic request-local `choice_1`, `choice_2`, ... |
| `label` | exact Pack title |
| `type_key` | local key of its visible type card |
| `relationships` | only choice-specific readable relationships; omitted when empty |

The label is presentation, not identity. It:

- need not be unique;
- never replaces `choice_key`;
- never contains a canonical option/type ID or hash;
- never repeats a source literal;
- never restates a relationship as a qualifier.

If semantically indistinguishable choices leave two or more distinct type
meanings plausible, both keys/mappings remain present and
`ambiguous_registry_type` is truthful. Indistinguishable choices within one
remaining type hit the count-one compatibility stop in section 11; no current
reason may be forced. A label collision is not a technical pipeline failure.
Duplicate/missing keys or a changed mapping are technical failures and fail
closed.

The choice order remains the current canonical Candidate Compiler order.
`choice_1`, `choice_2`, ... are assigned contiguously in that order. The label
is copied from the mapped type card's exact Pack title, so it has no
independent qualifier algorithm. GOAL 3 does not change option order.

## 10. Managed unclassified-reason cards

`unclassified_reasons` contains exactly one card for every code permitted by
the current V6 Choice, in the catalog's `display_order`.

Each card contains exact catalog-owned data:

| Field | Catalog source |
| --- | --- |
| `code` | `code` |
| `title` | `human_title` |
| `meaning` | `meaning` |
| `use_when` | `use_when` |
| `do_not_use_when` | `do_not_use_when` |
| `contrasts` | `contrast_with_neighbouring_reasons` |
| contrast `against_reason_code` | catalog `reason_code` |
| contrast `distinction` | catalog `distinction` |

Catalog lifecycle, GUI administration, positive examples, numeric selection
boundaries, asset identity and integrity are private. The exact `use_when`
text and reciprocal contrast already state the `0` versus `2+` distinction in
human language. Positive examples are omitted to keep the decision card short
and to avoid conditioning a later semantic smoke on examples that mirror
existing frozen fixtures. Adding either field later requires a new
consumer-oriented contract justification.

The code is allowed model-visible because the adjacent card fully explains it
and the same code is required by the strict response schema.

For private receipt hashing, the Choice-owned decision-code view is exactly:

```json
{
  "identity": "broker_reports_gate2_financial_evidence_decision_v1",
  "unclassified_reason_codes": [
    "ambiguous_registry_type",
    "no_registry_type"
  ]
}
```

`decision_code_contract_hash` is SHA-256 of
`context_v2_integrity_json_v1` applied to that exact view.

Code-set mismatch, a missing card, an extra card, incomplete contrast coverage
or non-validated catalog integrity prevents transport. Provider adapters must
not add, shorten, translate, reinterpret or repair reason meaning.

## 11. Exact semantic decision rule

The model assesses the whole visible source against every available type card.
A compiled choice count, Compiler attempt count or blocked-binding count is
not a semantic type-plausibility count.

The only truthful outcomes are:

1. return `{"choice": "<choice_key>"}` only when exactly one distinct
   available type meaning remains plausible and, within that type, exactly
   one complete visible choice is supported by the source and its readable
   relationships; every other type card and choice must be ruled out;
2. return unclassified with `no_registry_type` only when every available type
   card can be ruled out, leaving zero plausible distinct types;
3. return unclassified with `ambiguous_registry_type` only when two or more
   distinct available type meanings remain plausible after all visible
   evidence is considered.

Zero choices does not imply either unclassified reason. Two blocked Compiler
attempts do not imply two plausible types. Value, association or binding
uncertainty within one already identified type is not
`ambiguous_registry_type`.

If exactly one type remains plausible but no complete visible choice is safe,
neither current reason code is truthful. The current response relation is not
semantically total for that state; qualification stops and no adapter,
normalizer or expected-answer policy may force one of the two codes.

The unchanged generic task's word `otherwise` does not authorize a false
reason: the visible catalog cards and strict code meanings narrow it to the
two truthful unclassified states above. Consequently this V2 contract has a
closed byte/field boundary but a deliberately acknowledged partial semantic
response relation. It is ineligible for unbounded or production transport
until a separately versioned reason/policy decision makes count `1` total or
an upstream authority can prove that state impossible without expected-answer
labels. A later bounded qualification may transport only explicitly accepted
cases whose audited state is one of: exactly one plausible type with exactly
one supported choice (`typed_safe_1`), zero plausible types (`no_type_0`), or
two or more plausible distinct types (`ambiguous_2plus`). The inadmissible
state is exactly one plausible type without one safe choice. Audit labels
never enter model view.

## 12. Non-active response schema

The existing Choice factory owns one future local V2 response profile.

Typed response:

```json
{
  "choice": "choice_1"
}
```

Unclassified response:

```json
{
  "choice": "unclassified",
  "reason": "no_registry_type"
}
```

The exact request-bound schema shape when choices exist is:

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
          "enum": ["choice_1", "choice_2"]
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

`["choice_1", "choice_2"]` represents the complete request-local choice list:
the renderer emits exactly `choice_1` through `choice_N` in unchanged
Candidate Compiler order, with neither omissions nor other values. When
`choices` is empty, the typed branch is absent and the exact schema is:

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

The reason enum retains the current V6 Choice code order. Reason cards retain
catalog `display_order`; code, not array position, joins them to the schema.
There are no schema `description` fields. Object-key and branch ordering is
exactly as printed. The strict provider-facing response-format wrapper is:

```text
{
  "type": "json_schema",
  "json_schema": {
    "name": "semantic_choice",
    "strict": true,
    "schema": <the exact request-bound schema object above>
  }
}
```

The angle-bracket value names the inserted JSON object; it is not a string
sent to a provider. A provider projection may translate this wrapper only
when the resulting provider mechanism exposes the identical closed schema
and no additional model-visible prose.

The exact provider-neutral request envelope has fields in this order:

```text
{
  "messages": [
    {"role": "system", "content": <exact system-message string>},
    {"role": "user", "content": <Context V2 serialized as one minified JSON string>}
  ],
  "response_format": <complete response-format object above>
}
```

The envelope has exactly two message items. Each item has exactly `role` then
`content`; roles are exactly `system` then `user`. User `content` is a JSON
string whose decoded characters are exactly
`context_v2_model_json_v1(Context V2)`, not an embedded object. No other
message field or item is permitted.

The schema forbids extra properties, nullable fields, free-form reasons and
all exact `typed_option_id`, type ID, source ref, hash or receipt identity.

The complete response schema is request-bound. A local typed answer normalizes
through `choice_key -> typed_option_id` to the unchanged canonical response:

```json
{
  "disposition": "typed_input",
  "typed_option_id": "<private exact mapped ID>"
}
```

A local unclassified answer normalizes without semantic repair to:

```json
{
  "disposition": "unclassified_financial_input",
  "reason_code": "<exact returned allowed code>"
}
```

## 13. Closed model-visible field allowlist

The full allowlist is:

| Surface | Allowed fields |
| --- | --- |
| system message | current exact generic V6 system prompt only |
| provider-neutral request root | `messages`, `response_format` |
| message item | exactly `role`, `content`; exactly two items ordered `system`, `user` |
| context root | `task`, `source`, `type_cards`, `choices`, optional `shared_relationships`, `unclassified_reasons` |
| source root | `document` |
| document object | one non-empty `children` array |
| table node | optional `structure_key`, `kind`, required non-empty `children` |
| row node | optional `structure_key`, `kind`, optional `section_role`, optional `row_role`, required non-empty `values` |
| text-segment node | optional `structure_key`, `kind`, optional `section_role`, optional `row_role`, required non-empty `values` |
| evidence-group node | optional `structure_key`, `kind` |
| value | optional `value_key`, `meaning`, `literal`, `value_type`, optional `label` |
| type card | `type_key`, `title`, `meaning`, `semantic_class`, non-empty `required_evidence`, optional non-empty `optional_evidence`, non-empty `conditional_requirements`, optional non-empty `forbidden_evidence`, non-empty `synonyms`, non-empty `distinctions`, non-empty `examples`, non-empty `counterexamples`, non-empty `unclassified_when`, `model_guidance` |
| type evidence requirement | `role`, `value_type`, `cardinality` |
| type distinction | exactly one of `against_type_key` or `against_concept`, plus `rule` |
| shared relationship | `role`, exactly one of `value_key`, `structure_key`, `location`, and optional non-empty `applies_to` |
| choice relationship | `role` plus exactly one of `value_key`, `structure_key`, `location`; `applies_to` forbidden |
| choice | `choice_key`, `label`, `type_key`, optional non-empty `relationships` |
| reason card | `code`, `title`, `meaning`, `use_when`, `do_not_use_when`, non-empty `contrasts` |
| reason contrast | `against_reason_code`, `distinction` |
| response | typed `{choice}` or unclassified `{choice, reason}` |
| response-format wrapper | `type`, `json_schema`; nested `name`, `strict`, `schema` |
| response-schema root | `title`, `anyOf` |
| response-schema branch | `type`, `additionalProperties`, `properties`, `required` |
| response-schema property | `type`, `enum` |

Field justification is closed as follows:

| JSON path/field | Authority | Decision purpose and consumer | Cardinality/omission | Private provenance |
| --- | --- | --- | --- | --- |
| request `messages` | existing request builder | preserve the exact system/user sequence; provider/model | exactly one two-item array | request-profile/hash |
| message `role` | existing request builder | distinguish instruction from Context; provider/model | exactly `system`, then `user` | request-profile/hash |
| message `content` | Prompt/packet owners | carry exact Prompt and minified Context bytes; provider/model | exactly one string per item | Prompt/Context/request hashes |
| system message | current V6 Prompt owner | require one strict JSON answer; model | exactly one, byte-exact | Prompt version/hash |
| `task` | current packet generic task | state typed-versus-unclassified operation; model | exactly one | task identity/hash |
| `source.document` | Evidence Bundle | establish readable source root; model | exactly one object containing only non-empty `children` | bundle/scope identity and ordered top-level lineage |
| node `structure_key` | packet renderer + receipt | disambiguate a referenced node; relationships/model | zero or one; omit without inbound consumer | exact association/lineage mapping |
| node `kind` | Evidence Bundle association/lineage | explain hierarchy level; model | exactly one per node | exact association kind and lineage |
| node `section_role` | Evidence Bundle | retain readable non-null section semantics; model | row/text-segment only; zero or one, omit when absent | exact source-value metadata pointer/render mapping |
| node `row_role` | Evidence Bundle | retain readable non-null row semantics; model | row/text-segment only; zero or one, omit when absent | exact source-value metadata pointer/render mapping |
| node `children` | Evidence Bundle | preserve nested evidence structure; model | table only; exactly one non-empty array | ordered exact child lineage |
| node `values` | Evidence Bundle | locate authoritative values; model | row/text-segment only; exactly one non-empty array | ordered exact source-value refs |
| value `value_key` | packet renderer + receipt | let a visible relationship point to the value; model/normalizer | zero or one; omit without inbound consumer | bijective exact source-value mapping |
| value `meaning` | Evidence Bundle | explain the literal's source meaning without copying it; model | exactly one non-empty string; column meaning/label must differ from literal or renderer uses the next fallback | exact column meaning/label/type fallback source |
| value `literal` | Evidence Bundle | provide authoritative source fact; model | exactly one occurrence per semantic source value | exact source-value ref |
| value `value_type` | Evidence Bundle | distinguish decimal/date/currency/text semantics; model | exactly one | exact technical value type |
| value `label` | Evidence Bundle | retain a distinct exact visible label; model | zero or one; omit when absent/equal to meaning or literal | exact visible-label pointer |
| `type_cards` | semantic-contract snapshot | enumerate source-family-compatible available meanings; model | one array; empty only when the semantic authority has no compatible type | private ordered available type IDs |
| type `type_key` | packet renderer + receipt | stable local cross-reference for cards/choices; model/normalizer | exactly one per card | bijective exact type mapping |
| type `title` | Financial Semantic Pack | scan-friendly type name; model/choice label | exactly one | exact Pack JSON Pointer/hash |
| type `meaning` | Financial Semantic Pack | define the financial type; model | exactly one | exact Pack definition pointer/hash |
| type `semantic_class` | Financial Semantic Pack | expose state-versus-aggregate class without inferring it; model | exactly one | exact semantic-class pointer/hash |
| type `required_evidence` | Financial Semantic Pack roles | determine whether type evidence can be complete; model | non-empty | exact required-role pointers/hash |
| type `optional_evidence` | Financial Semantic Pack roles | prevent absence of optional evidence being mistaken for rejection; model | omit when Pack list is empty | exact optional-role pointers/hash |
| type `conditional_requirements` | Financial Semantic Pack | preserve date-or-period and currency-or-unit OR requirements that individual optional roles cannot express; model | exactly two ordered readable rules for the pinned Pack | exact requirement pointers/hashes |
| type `forbidden_evidence` | Financial Semantic Pack roles | expose evidence that rules the type out; model | omit when Pack list is empty | exact forbidden-role pointers/hash |
| evidence requirement `role/value_type/cardinality` | Financial Semantic Pack role entry | explain required/optional evidence shape; model | all three mechanically readable fields required per entry | exact role entry pointer/hash |
| type `synonyms` | Financial Semantic Pack | recognize Pack-owned equivalent type language without adapter dictionaries; model | non-empty ordered exact strings | exact synonym pointers/hash |
| type `distinctions` | Financial Semantic Pack | contrast neighbouring and external concepts; model | non-empty for the current Pack | exact distinction pointers/hash |
| distinction target/rule | Financial Semantic Pack | identify contrasted meaning without opaque ID and preserve exact rule; model | exactly one target plus rule | exact `against` value and rule pointer/hash |
| type `examples` | Financial Semantic Pack | show positive type boundary; model | non-empty | exact examples pointers/hash |
| type `counterexamples` | Financial Semantic Pack | support safe rejection and `no_registry_type`; model | non-empty | exact counterexample pointers/hash |
| type `unclassified_when` | Financial Semantic Pack | state type-specific uncertainty boundary; model | non-empty | exact ambiguity-guidance pointers/hash |
| type `model_guidance` | Financial Semantic Pack | preserve the complete Pack-owned choice rule, including conditional evidence; model | exactly one | exact model-guidance pointer/hash |
| `shared_relationships` | Typed Options + Pack roles + receipt | show common prebound evidence once; model | omit when empty | exact common role/source-ref table |
| relationship `role` | Financial Semantic Pack role | explain the binding/predicate; model | exactly one | exact role ID |
| relationship target | Evidence Bundle + receipt | point to one semantic value or structural location; model/normalizer | exactly one of key/key/location | exact source ref and association/lineage |
| shared relationship `applies_to` | Candidate Compilation order + receipt | constrain a factored relationship to its exact choice subset; model | omit for all choices, otherwise at least two ordered keys | exact covered-choice/binding rows |
| `choices` | Candidate Compilation Typed Options | enumerate selectable complete records; model/schema | one array; empty is meaningful | ordered exact option IDs |
| choice `choice_key` | Choice factory + receipt | strict disposable response identity; model/normalizer | exactly one per choice | bijective exact option mapping |
| choice `label` | Pack title | make the choice readable; model | exactly one, not required unique | exact Pack title pointer/hash |
| choice `type_key` | Pack projection + receipt | bind choice to visible type meaning; model | exactly one | exact type mapping |
| choice `relationships` | Typed Option + receipt | show only variant-specific evidence; model | omit when empty | exact variant role/source-ref table |
| `unclassified_reasons` | managed reason catalog + Choice code set | explain every allowed unclassified code; model/schema | exactly one card per allowed code | catalog/code-contract identities and entry pointers |
| reason `code` | current Choice/decision contract | strict response identity; model/schema/normalizer | exactly one unique code | exact code-set entry |
| reason `title/meaning/use_when/do_not_use_when` | managed reason catalog | explain positive and negative semantic boundary; model | all required | exact catalog field pointers/hash |
| reason `contrasts` | managed reason catalog | distinguish neighbouring reasons; model | non-empty reciprocal set | exact contrast pointers/hash |
| reason contrast fields | managed reason catalog | bind contrast to response code and exact distinction; model | code plus distinction required | exact neighbour-code/distinction pointer |
| response `choice` | existing Choice factory local profile | return one local choice or `unclassified`; parser/normalizer | exactly one | response-schema and request hashes |
| response `reason` | existing Choice code set | return exact reason only for unclassified; parser/normalizer | required only for unclassified, forbidden for typed | code-set/catalog parity receipt |
| wrapper `type` | existing request/provider contract | select strict JSON Schema response mode; provider | exactly `json_schema` | request-profile/hash |
| wrapper `json_schema.name` | existing request/provider contract | stable provider schema label; provider | exactly `semantic_choice` | request-profile/hash |
| wrapper `json_schema.strict` | existing request/provider contract | prohibit permissive provider output; provider | exactly boolean `true` | request-profile/hash |
| wrapper `json_schema.schema` | existing Choice factory V2 profile | carry the exact request-bound schema; provider/model | exactly one schema object | response-schema hash |
| schema `title` | existing Choice factory V2 profile | human schema label; provider/model | exactly `Semantic choice` | response-schema hash |
| schema `anyOf` | existing Choice factory V2 profile | separate typed and unclassified shapes; parser/model | typed then unclassified when choices exist, otherwise unclassified only | response-schema hash and choice-set receipt |
| branch `type/additionalProperties` | existing Choice factory V2 profile | require closed objects; parser/model | exactly `object` and boolean `false` | response-schema hash |
| branch `properties/required` | existing Choice factory V2 profile | close conditional response fields; parser/model | exact fields and order printed in section 12 | response-schema hash |
| property `type/enum` | existing Choice factory V2 profile | constrain local choice and reason codes; parser/model | exactly `string` plus request-bound enum in section 12 order | response-schema, mapping and catalog parity hashes |

Anything not listed is forbidden until a later contract version provides a
semantic or structural justification.

## 14. Forbidden model-visible content

The following are forbidden anywhere in messages, response schema, enum
descriptions or provider-visible wrappers:

- global source, association, evidence, provenance, document, package, scope,
  row, cell, segment or storage refs;
- canonical `input_type_id`, `typed_option_id`, record IDs and asset IDs;
- schema, policy, prompt, packet, candidate, receipt, content or integrity
  hashes;
- repository or filesystem paths;
- provider metadata, response IDs, raw envelopes or hidden reasoning;
- expected answers, benchmark labels or audit outcomes;
- exact `source_reference` literals;
- repeated authoritative source literals;
- null fields, empty labels and invented placeholders;
- full Pack role-administration objects, including exact role IDs,
  identity-role status, `source_ref_required` and validation or
  materialization controls; section 7.2's compact readable
  required/optional/forbidden evidence projection is explicitly allowed;
- blocked-binding diagnostics, materializability, validation, retention or
  replay administration;
- unexplained semantic codes;
- technical bindings that do not meet section 8;
- summaries that restate an already visible literal or relationship.

Allowed field names do not launder forbidden values. A global ref under
`label`, `location` or another allowed key remains forbidden.

## 15. Private mapping and sealed-request receipts

Two owners emit two separate closed private receipts. The packet factory emits
the Context-to-authority mapping receipt. It does not import Prompt or Choice.
The existing Context Linter consumes that mapping receipt together with the
Prompt-owned system message and Choice-owned response format, then emits the
sealed-request receipt. It references the mapping receipt by integrity hash and
does not duplicate its mappings.

### 15.1 Packet-owned mapping receipt

`schema_version` is exactly
`broker_reports_gate2_llm_semantic_context_v2_mapping_receipt_v1` and
`policy_version` is exactly
`broker_reports_gate2_managed_semantic_decision_context_v2`. The exact
top-level field set, in order, is:

```text
schema_version
policy_version
identities
scope
visible_field_sources
local_mappings
binding_partition
presentation_order
provider_calls_total
integrity_hash
```

The nested groups are also closed:

| Group | Exact contents |
| --- | --- |
| `identities` | exactly `context_contract_identity`, `context_contract_version`, `active_packet_identity`, `active_packet_hash`, `context_view_hash`, `managed_asset_family_identity`, `managed_asset_family_version`, `managed_asset_family_manifest_sha256`, `registry_identity`, `registry_version`, `registry_hash`, `semantic_pack_identity`, `semantic_pack_version`, `semantic_pack_integrity_sha256`, `semantic_pack_projection_identity`, `semantic_pack_projection_version`, `semantic_pack_projection_hash`, `reason_catalog_identity`, `reason_catalog_version`, `reason_catalog_integrity_sha256`, `reason_projection_identity`, `reason_projection_version`, `reason_projection_hash`, `decision_code_contract_identity`, `decision_code_contract_hash` |
| `scope` | exactly `evidence_bundle_id`, `evidence_bundle_integrity_hash`, `source_scope_ref`, `candidate_compilation_integrity_hash`, `type_set_snapshot`, ordered private `compiler_observed_type_ids`, boolean `type_set_parity` |
| each `visible_field_sources` row | exactly `json_pointer`, `authority_kind`, `authority_pointer`, `field_content_hash`; exact coverage and hashing are defined below |
| `local_mappings` | exactly arrays `value_keys`, `structure_keys`, `evidence_reference_targets`, `type_keys`, `choice_keys` |
| each `value_keys` row | exactly `value_key`, `json_pointer`, `source_value_ref` |
| each `structure_keys` row | exactly `structure_key`, `json_pointer`, `node_identity`; the closed node-identity union is defined below |
| each `evidence_reference_targets` row | exactly `source_value_ref`, `target_kind`, `target`; `target_kind` is `structure_key` or `location`, `target` is its exact local value, and the full source lineage remains retrievable from the Evidence Bundle by `source_value_ref` |
| each `type_keys` row | exactly `type_key`, `json_pointer`, `input_type_id` |
| each `choice_keys` row | exactly `choice_key`, `json_pointer`, `typed_option_id`, `association_ref`, `type_key` |
| `binding_partition` | exactly arrays `visible_relationships`, `backend_only_bindings` |
| each `visible_relationships` row | exactly `json_pointer`, `classification`, `sharing`, `covered_bindings`; classification is `semantic_value` or `evidence_predicate`, sharing is `shared` or `choice_specific`, and each covered binding has exactly `choice_key`, `role_id`, `source_value_ref` |
| each `backend_only_bindings` row | exactly `choice_key`, `role_id`, `source_value_ref` |
| `presentation_order` | exactly ordered arrays `value_keys`, `structure_keys`, `type_keys`, `choice_keys`, `reason_codes`, followed by `presentation_identity` and `permutation_identity`; `reason_codes` is exactly Context `unclassified_reasons` card order (catalog display order), not response-schema enum order |

`scope.type_set_snapshot` is the packet-owned derived witness for the exact
request type set. It is not a new semantic authority. Its closed field set, in
order, is:

```text
schema_version
source_family_id
registry_identity
registry_version
registry_hash
semantic_pack_identity
semantic_pack_version
semantic_pack_integrity_sha256
pack_registry_baseline_parity
available_type_ids
integrity_hash
```

`schema_version` is exactly
`broker_reports_gate2_context_v2_type_set_snapshot_v1`.
`available_type_ids` is the ordered result of section 7.1.
`integrity_hash` is SHA-256 of `context_v2_integrity_json_v1` applied to the
snapshot payload excluding that field. The witness is reconstructable from the
bound Evidence Bundle, Registry and Pack projection and must match all three;
it cannot override them.

The `node_identity` union has no other fields:

```text
table:
  kind, table_ref

row:
  kind, association_ref, row_ref, table_ref, section_role, row_role

text_segment:
  kind, association_ref, text_segment_ref, section_role, row_role

evidence_group:
  kind, association_ref, page_ref, table_ref, row_ref, text_segment_ref
```

`kind` is exactly `table`, `row`, `text_segment` or `evidence_group`.
Fields listed for a variant are always present in the private mapping receipt; nullable
Evidence Bundle lineage/role fields retain JSON null. `cell_ref` is not a node
identity field: a visible row can contain multiple cells, and exact value
lineage is recovered by `source_value_ref`.

`visible_field_sources` contains exactly one row for every primitive JSON leaf
in the Context V2 object and one row for each required empty `type_cards` or
`choices` array. It contains no row for a non-empty object/array container,
system message, response format or response schema. `json_pointer` is the
unique RFC 6901 pointer from the Context root, including numeric array
segments and mandatory `~0`/`~1` escaping.

`authority_kind` is exactly one of `packet_task`, `evidence_bundle`,
`type_set_snapshot`, `semantic_pack_projection`, `candidate_compilation`,
`reason_catalog_projection` or `decision_code_contract`. Each names the exact
version/hash-bound private JSON authority view already present in
`identities` or `scope`; the active packet task view, sealed Evidence Bundle,
derived type-set witness, versioned Pack projection, Candidate Compilation
with its Typed Options, versioned reason projection, and Choice-owned canonical
reason-code view, respectively. `authority_pointer` is an RFC 6901 pointer
from that authority view's root to the exact source field from which the
rendered leaf or empty-set decision is derived. Type-card membership, order and
the required empty-array decision point to the type-set witness; individual
type-card semantic fields point to the Pack projection. Missing targets,
non-canonical escaping and pointers into a different authority kind fail
closed.
For a decision derived from multiple fields, the pointer targets the smallest
authority container that contains every input; the empty-string RFC 6901 root
pointer is allowed when no narrower container exists.

`field_content_hash` is SHA-256 of
`context_v2_integrity_json_v1(<exact rendered JSON leaf or required empty
array>)`. It hashes model-visible content, not the private authority value;
the authority identity/hash plus `authority_pointer` bind the source value and
the contract binds the rendering rule. Rows are unique by `json_pointer`.

`presentation_identity` is SHA-256 over
`context_v2_integrity_json_v1` of the object containing only the five
presentation arrays. `permutation_identity` is SHA-256 over
`context_v2_integrity_json_v1` of the private `typed_option_id` array obtained
by resolving `presentation_order.choice_keys` in that exact order; the
zero-choice value is therefore the hash of `[]`.

`provider_calls_total` is integer zero for all pre-provider local candidates.
`integrity_hash` is SHA-256 of `context_v2_integrity_json_v1` applied to the
mapping-receipt payload excluding that field. No other field is permitted. In
particular, Prompt and response
schema identities are absent because they are outside packet ownership. The
historical Slim candidate identity/hash is also absent: V2 is bound to the
unchanged active packet baseline, not coupled to its predecessor candidate.

Value, keyed-node, type and choice mappings are bijective over their emitted
keys. Evidence-reference target resolution may be many-to-one because multiple
exact deterministic-reference values may legitimately resolve to one
evidence-derived node. The exact
`{choice_key, role_id, source_value_ref}` partition preserves total
reconstruction. Its visible and backend-only multisets are disjoint and their
union equals the complete Typed Option binding multiset. A shared relationship
covers at least two choices; its exact covered choice set equals its
`applies_to` list, or all visible choices when `applies_to` is omitted.

The mapping receipt is an index into the Registry snapshot, Evidence Bundle,
Candidate Compilation and Typed Options. It never replaces those authorities.

### 15.2 Linter-owned sealed-request receipt

`schema_version` is exactly
`broker_reports_gate2_llm_semantic_context_v2_sealed_request_receipt_v1` and
`policy_version` is the same exact Context policy version as section 15.1. Its
exact top-level field set, in order, is:

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

`request_profile` is exactly
`broker_reports_gate2_financial_semantic_v6_request_v2_candidate`. The
`invariant_counters` object is closed and contains, in order:

```text
opaque_global_ids
duplicate_literal_projections
null_fields
unexplained_reason_codes
unused_or_orphan_keys
visible_fields_total
visible_fields_covered_total
semantic_literals_total
semantic_literals_covered_total
relationship_mappings_total
relationship_mappings_covered_total
binding_rows_total
binding_rows_covered_total
```

All zero-target counters describe violations in the complete model-visible
request, not private-receipt content. `opaque_global_ids`, `null_fields` and
`unexplained_reason_codes` scan the exact system message, Context V2 user
message and complete provider-neutral response format directly.
`duplicate_literal_projections` joins visible literal leaves through the
mapping receipt to authoritative `source_value_ref` and counts only excess
visible occurrences, never equal raw strings from distinct refs.
`unused_or_orphan_keys` joins visible definitions/consumers with the mapping
receipt and counts only model-view key defects. Private refs, hashes and
nullable node-identity lineage used by those joins are not themselves visible
violations. The remaining totals compare the Context
leaf/required-empty-array denominator, literals, relationships and
mapping-receipt binding rows with their bound private authorities.

`status` is exactly `passed` or `failed`. Transport requires `passed`; every
zero-target invariant must be zero, each `*_covered_total` must equal its
corresponding total, and both receipt integrities must validate.

The Context Linter is mechanical and must not infer plausible-type count,
consult expected answers or admit a semantic case. For any later bounded
provider qualification, the existing qualification owner must separately
record a hash-bound private case-admission decision under the accepted
`typed_safe_1`, `no_type_0` or `ambiguous_2plus` policy.
`Gate2FinancialSemanticV6QualificationFixtureFactory` is the sole admission
owner; `Gate2FinancialSemanticV6QualificationPreflightFactory` may consume and
verify it. That decision is not a packet/linter input, never enters model view
and may not change request bytes.

`response_schema_hash` covers the nested schema object.
`response_format_hash` covers the complete provider-neutral
`{type,json_schema}` wrapper from section 12.
`model_visible_request_hash` covers `context_v2_model_json_v1` with the exact
ordered fields `messages` and `response_format`; `messages` is exactly the
system message followed by the minified Context V2 user-message string. The
byte counter is the length of that exact UTF-8 payload.
`provider_calls_total` is integer zero before provider transport.
`integrity_hash` is SHA-256 of `context_v2_integrity_json_v1` applied to the
sealed-receipt payload excluding that field.

A later provider attempt must additionally bind the adapter-owned provider
projection identity and exact projected-request hash in provider evidence.
Provider-specific projection is not owned by either receipt above and may not
rewrite semantic content.

Validation fails closed on collision, missing/extra/orphan mapping, wrong
scope, wrong option, changed ordering, incomplete exact-binding coverage,
Registry/Pack baseline mismatch, managed-asset mismatch, wrapper/request hash
mismatch or receipt tampering.

## 16. Restore, expansion and replay

A conforming future local proof must preserve and restore:

1. the exact final model-visible system message;
2. the exact Context V2 JSON;
3. the exact response schema;
4. the exact adapter-extracted local answer;
5. the exact provider-neutral response-format wrapper;
6. the packet-owned private mapping receipt;
7. the linter-owned private sealed-request receipt;
8. the normalized canonical V6 Choice;
9. the expanded canonical decision;
10. validation and materialization results;
11. the final transparent report projection.

Typed restoration obtains the exact existing Typed Option and does not trust
the model for type, role, binding or source identity. Unclassified restoration
preserves the complete existing retention set. Provider adapters perform only
provider projection/parsing and usage normalization; they never rename keys,
choose reasons, repair semantics or reconstruct records.

## 17. Determinism and future linter obligations

The later GOAL 4 implementation and GOAL 5 linter must prove:

- exact active V6 packet, Prompt and Choice byte/hash parity;
- deterministic Context V2 bytes for identical inputs;
- deterministic key assignment and presentation order;
- authoritative semantic literal coverage `100%`;
- each authoritative source literal occurrence `1`;
- opaque global IDs `0`;
- null fields `0`;
- unexplained reason codes `0`;
- unused/orphan/unmapped keys `0`;
- type-card required/optional/conditional/forbidden evidence coverage complete;
- type-card synonym, example, counterexample, distinction, ambiguity and model-guidance coverage complete;
- type-card direct contrast coverage complete;
- reason-card/code/schema parity exact;
- complete exact option-binding coverage in the mapping receipt;
- total typed and unclassified restoration;
- collision, order, scope, asset, mapping and receipt tampering rejected;
- exact minified UTF-8 bytes and repository estimator result recorded.

All model-view and receipt arrays have a closed order:

| Array | Exact order |
| --- | --- |
| source siblings/values | section 6.3 canonical hierarchy construction |
| type cards | canonical authority-derived type-contract order |
| required/optional/forbidden evidence, synonyms, distinctions, examples, counterexamples, ambiguity guidance | exact corresponding Pack array order |
| conditional requirements | Pack `date_period_requirement`, then `currency_unit_requirement` |
| choices | unchanged Candidate Compiler Typed Option order |
| choice-local relationships | existing Typed Option `role_bindings` order after shared signatures are removed |
| shared relationships | first occurrence while scanning choices in Compiler order and each choice's exact `role_bindings` order |
| shared `applies_to` | canonical choice order |
| reason cards | catalog `display_order` |
| reason contrasts | exact catalog array order |
| response typed enum | canonical choice order |
| response reason enum | current V6 Choice code order |
| mapping-receipt type-set-snapshot `available_type_ids` | Registry declaration order after source-family compatibility filter |
| mapping-receipt `compiler_observed_type_ids` | first occurrence while scanning Compiler `typed_options`, then `blocked_bindings` |
| mapping-receipt visible-field-source rows | Context JSON Pointer lexicographic order |
| mapping-receipt value/structure/type/choice mapping rows | numeric local-key order |
| mapping-receipt evidence-reference targets | validated Evidence Bundle reference-value order |
| mapping-receipt visible relationships | model-view presentation order |
| mapping-receipt covered/backend-only binding rows | canonical choice order, then exact Typed Option `role_bindings` order |
| mapping-receipt presentation arrays | the corresponding model-view orders above |

For factoring, a readable relationship signature is the exact rendered
`{role, target_kind, target}` triple. First occurrence fixes presentation;
the private mapping receipt may map that one signature to multiple exact
bindings.

V2 separates model-view serialization from integrity canonicalization.

`context_v2_model_json_v1` is exactly JSON serialization with original
Unicode characters (`ensure_ascii=false`), no optional whitespace
(`separators=(",", ":")`), finite numbers only (`allow_nan=false`) and no key
sorting. Producers insert every object field in the exact contract order.
This serializer produces the user-content string, nested response schema,
complete response format and provider-neutral request envelope.

`context_v2_integrity_json_v1` uses the same Unicode, whitespace and finite-
number rules but sorts every object key lexicographically (`sort_keys=true`).
It is used only for receipt integrity, `field_content_hash`,
`presentation_identity` and `permutation_identity`; it does not define
model-visible object order.

`system_prompt_hash` remains the exact current V6 Prompt authority hash:
SHA-256 of `context_v2_integrity_json_v1` applied to the exact Prompt string.
`context_view_hash`, `response_schema_hash`, `response_format_hash` and
`model_visible_request_hash` cover the exact UTF-8 bytes produced by
`context_v2_model_json_v1` for their respective object/string boundary.
`model_visible_utf8_bytes` is the byte length of the exact serialized
provider-neutral request envelope. Both receipts bind these hashes as defined
in section 15.

Provider token, cost and latency measurements are required only in a later
GOAL that explicitly authorizes provider calls.

## 18. Structural shape template

The angle-bracket values below are contract metavariables and are never
emitted literally. Managed financial and reason prose is deliberately not
copied into this document because the Pack and catalog remain their sole
meaning authorities. A single placeholder member in a Pack-owned array denotes
one member shape, not the array cardinality: an implementation emits every
authority member in exact Pack order as required by sections 7 and 17.

```json
{
  "task": "<exact current generic task>",
  "source": {
    "document": {
      "children": [
        {
          "kind": "table",
          "children": [
            {
              "kind": "row",
              "row_role": "<readable evidence row role>",
              "values": [
                {
                  "value_key": "value_1",
                  "meaning": "<readable evidence meaning>",
                  "literal": "<exact source literal>",
                  "value_type": "decimal"
                },
                {
                  "meaning": "<readable evidence meaning>",
                  "literal": "<exact source literal>",
                  "value_type": "text"
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
      "type_key": "type_1",
      "title": "<exact Pack title>",
      "meaning": "<exact Pack definition>",
      "semantic_class": "<exact Pack semantic class>",
      "required_evidence": [
        {
          "role": "<readable Pack role>",
          "value_type": "<readable Pack value type>",
          "cardinality": "<readable Pack cardinality>"
        }
      ],
      "optional_evidence": [
        {
          "role": "<readable Pack role>",
          "value_type": "<readable Pack value type>",
          "cardinality": "<readable Pack cardinality>"
        }
      ],
      "conditional_requirements": [
        "<readable Pack date/period requirement>",
        "<readable Pack currency/unit requirement>"
      ],
      "forbidden_evidence": [
        "<readable Pack forbidden role>"
      ],
      "synonyms": [
        "<exact Pack synonym>"
      ],
      "distinctions": [
        {
          "against_type_key": "type_2",
          "rule": "<exact Pack direct distinction>"
        },
        {
          "against_concept": "<readable external Pack concept>",
          "rule": "<exact Pack external distinction>"
        }
      ],
      "examples": [
        "<exact Pack example>"
      ],
      "counterexamples": [
        "<exact Pack counterexample>"
      ],
      "unclassified_when": [
        "<exact Pack ambiguity guidance>"
      ],
      "model_guidance": "<exact Pack model guidance>"
    },
    {
      "type_key": "type_2",
      "title": "<exact Pack title>",
      "meaning": "<exact Pack definition>",
      "semantic_class": "<exact Pack semantic class>",
      "required_evidence": [
        {
          "role": "<readable Pack role>",
          "value_type": "<readable Pack value type>",
          "cardinality": "<readable Pack cardinality>"
        }
      ],
      "optional_evidence": [
        {
          "role": "<readable Pack role>",
          "value_type": "<readable Pack value type>",
          "cardinality": "<readable Pack cardinality>"
        }
      ],
      "conditional_requirements": [
        "<readable Pack date/period requirement>",
        "<readable Pack currency/unit requirement>"
      ],
      "forbidden_evidence": [
        "<readable Pack forbidden role>"
      ],
      "synonyms": [
        "<exact Pack synonym>"
      ],
      "distinctions": [
        {
          "against_type_key": "type_1",
          "rule": "<exact Pack direct distinction>"
        },
        {
          "against_concept": "<readable external Pack concept>",
          "rule": "<exact Pack external distinction>"
        }
      ],
      "examples": [
        "<exact Pack example>"
      ],
      "counterexamples": [
        "<exact Pack counterexample>"
      ],
      "unclassified_when": [
        "<exact Pack ambiguity guidance>"
      ],
      "model_guidance": "<exact Pack model guidance>"
    }
  ],
  "choices": [
    {
      "choice_key": "choice_1",
      "label": "<exact Pack title>",
      "type_key": "type_2",
      "relationships": [
        {
          "role": "printed label evidence",
          "location": "the only visible row"
        }
      ]
    },
    {
      "choice_key": "choice_2",
      "label": "<exact Pack title>",
      "type_key": "type_1"
    }
  ],
  "shared_relationships": [
    {
      "role": "amount",
      "value_key": "value_1"
    },
    {
      "role": "statement scope",
      "location": "the only visible row"
    }
  ],
  "unclassified_reasons": [
    {
      "code": "no_registry_type",
      "title": "<exact catalog title>",
      "meaning": "<exact catalog meaning>",
      "use_when": "<exact catalog use_when>",
      "do_not_use_when": "<exact catalog do_not_use_when>",
      "contrasts": [
        {
          "against_reason_code": "ambiguous_registry_type",
          "distinction": "<exact catalog distinction>"
        }
      ]
    },
    {
      "code": "ambiguous_registry_type",
      "title": "<exact catalog title>",
      "meaning": "<exact catalog meaning>",
      "use_when": "<exact catalog use_when>",
      "do_not_use_when": "<exact catalog do_not_use_when>",
      "contrasts": [
        {
          "against_reason_code": "no_registry_type",
          "distinction": "<exact catalog distinction>"
        }
      ]
    }
  ]
}
```

## 19. Compatibility stops and non-goals

This contract does not prove implementation or benchmark compatibility.

Explicit stops:

1. The four frozen zero-choice ambiguity cases must receive the complete
   authority-derived available type set under V2, but that projection does
   not exist yet.
2. Catalog count `1` remains outside both managed reason boundaries. A single
   plausible type with no safely selectable prebound choice must not be
   silently relabelled.
3. The reason catalog and family v2 remain inactive drafts; packaged
   closed-world candidate consumption is not yet implemented.
4. Context V2 linter, persisted restore/replay and report projection are later
   GOALs.
5. No frozen expected answer, Prompt, Pack type meaning, reason wording,
   option order or provider/model selection changes in GOAL 3.
6. A valid all-`source_reference` bundle with no necessary inbound
   relationship is explicitly ineligible because it cannot produce the
   required non-empty readable hierarchy.
7. Existing provider-profile compatibility is `NOT_PROVEN`. The maintained
   OpenAI-compatible adapter can wrap a root `anyOf` schema under
   `broker_reports_gate2_choice`; the maintained Gemini projection can remove
   enums for the new `choice`/`reason` fields. Neither transformation is
   accepted as Context V2 conformance without a later exact local
   provider-projection proof. The existing adapter authorities must be
   versioned/fixed in place if needed; no second semantic adapter is allowed.

The current four frozen zero-choice cases all expose zero cards, zero options
and two technical Compiler blocks for ambiguous `amount` binding. Their
expected answers remain frozen, but the semantic audit is not uniform:

| Case | Contract-level semantic assessment |
| --- | --- |
| `syn_successor_v2_multiple_compatible` | visible source can support two or more distinct available type meanings; `ambiguous_registry_type` remains plausible |
| `syn_successor_v2_detail_vs_subtotal` | detail-versus-subtotal is primarily a printed-metric boundary and does not prove two distinct registry types |
| `syn_successor_v2_adjacent_equal` | primarily value/association ambiguity within cash semantics, not proven cross-type ambiguity |
| `syn_successor_v2_adjacent_fx` | primarily association ambiguity within cash semantics, not proven cross-type ambiguity |

Adding the missing available type cards can make the first case decidable, but
cannot by itself prove the latter three expected
`ambiguous_registry_type` answers. Context V2 therefore preserves the frozen
expectations as historical inputs while explicitly stopping benchmark
conformance pending a separate expected-answer/taxonomy decision.

GOAL 3 does not:

- implement or activate Context V2;
- change the active V6 packet or exact-ID Choice;
- replace the historical Slim View v2 or Local Choice v1;
- run a provider or benchmark;
- admit a model or production route;
- modify stage, production or customer evidence.

## 20. GOAL 3 acceptance

```text
CONTEXT_CONTRACT: VERSIONED_V2_CANDIDATE
COMPLETE_MODEL_VISIBLE_BYTE_AND_FIELD_BOUNDARY: CLOSED
SEMANTIC_RESPONSE_RELATION: PARTIAL_AT_COUNT_ONE
UNBOUNDED_OR_PRODUCTION_TRANSPORT: FORBIDDEN
TASK: CURRENT_EXACT_GENERIC_TASK
SOURCE_STRUCTURE: EVIDENCE_DERIVED
AUTHORITATIVE_LITERALS: EXACTLY_ONCE
OPAQUE_GLOBAL_IDS: FORBIDDEN
NULL_FIELDS: FORBIDDEN
TYPE_CARDS: PACK_OWNED_COMPACT_AND_SEMANTICALLY_COMPLETE
AVAILABLE_TYPE_SET: ACTIVE_SOURCE_FAMILY_COMPATIBLE_PACK_TYPES
COMPILER_TYPE_SET: PRIVATE_PARITY_SIGNAL_ONLY
TYPE_CARDS_WITH_ZERO_CHOICES: REQUIRED
RELATIONSHIPS: NECESSARY_READABLE_AND_FACTORED
CHOICE_KEY_AND_LABEL: SEPARATE
UNCLASSIFIED_REASONS: CATALOG_OWNED_AND_FULLY_EXPLAINED
REASON_SEMANTIC_BOUNDARIES: EXACT_USE_WHEN_AND_CONTRAST
CATALOG_NUMERIC_SELECTION_BOUNDARY_FIELD_MODEL_VISIBLE: NO
REASON_POSITIVE_EXAMPLES_MODEL_VISIBLE: NO
RESPONSE_SCHEMA: LOCAL_STRICT_AND_REQUEST_BOUND
PROVIDER_NEUTRAL_REQUEST_ENVELOPE: CLOSED
PROVIDER_PROFILE_COMPATIBILITY: NOT_PROVEN
EXACT_PRIVATE_MAPPING: DESIGNED
EXACT_BACKEND_BINDINGS: PRESERVED
STRUCTURE_KEY_MAPPING: BIJECTIVE_OVER_EMITTED_KEYED_NODES
REFERENCE_TARGET_RESOLUTION: MANY_TO_ONE_ALLOWED_WITH_EXACT_SOURCE_VALUE_ROWS
EMPTY_VISIBLE_HIERARCHY: FAIL_CLOSED
PROVIDER_CALLS: ZERO
RUNTIME_ACTIVATION: FALSE
BENCHMARK_CONFORMANCE: NOT_CLAIMED
FOUR_CASE_REASON_COMPATIBILITY: ONE_PLAUSIBLE_THREE_NOT_PROVEN
```
