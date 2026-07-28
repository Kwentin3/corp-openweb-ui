# Broker Reports Gate 2 — Managed Semantic Decision Context GOAL 2 Alias Necessity and Readability Audit

Date: 2026-07-28

Status:
`PASSED_AS_DOCUMENTATION_ONLY_AUDIT_WITH_CONTEXT_V2_COMPATIBILITY_STOP`

Base revision: `d470b8a0418fad3fc607e5be186fd24dcac0c795`

Branch:
`codex/broker-reports-gate2-managed-context-goal2-alias-audit`

## 1. Outcome

GOAL 2 audited every alias namespace and every visible binding in the exact
non-active Slim v2 + Local Choice projection over all 10 frozen semantic V6
cases.

The result is one closed visibility rule:

> A local reference may be model-visible only when another model-visible
> field must point to it, or when the strict response must return it.
> Otherwise readable nesting and existing semantic labels carry the context,
> while exact identity remains private.

The current candidate is mechanically exact, but not every mechanically used
alias is semantically useful:

```text
SOURCE_VALUE_ALIASES: 45
SOURCE_VALUE_ALIASES_WITH_CURRENT_INBOUND_REFERENCE: 23
SOURCE_VALUE_ALIASES_WITHOUT_CURRENT_INBOUND_REFERENCE: 22
STRUCTURAL_ALIASES: 20
STRUCTURAL_ALIASES_WITH_CURRENT_INBOUND_REFERENCE: 6
STRUCTURAL_ALIASES_WITHOUT_CURRENT_INBOUND_REFERENCE: 14
TYPE_ALIASES: 12
CHOICE_ALIASES: 12
VISIBLE_BINDING_OCCURRENCES: 59
SEMANTIC_VALUE_BINDING_OCCURRENCES: 41
EVIDENCE_OR_IDENTITY_BINDING_OCCURRENCES: 18
OPTION_DIFFERENTIATING_BINDING_OCCURRENCES: 11
OPTION_DIFFERENTIATING_SEMANTIC_BINDINGS: 5
OPTION_DIFFERENTIATING_EVIDENCE_PREDICATES: 6
UNIQUE_READABLE_ELIGIBILITY_RELATIONSHIPS: 35
DUPLICATED_BINDING_OCCURRENCES: 24
```

For the frozen suite, the Context V2 target therefore needs:

- 23 readable value references for unique semantic role/value relationships;
- zero numeric structural aliases;
- a deterministic local type key accompanied by a Pack-owned readable title;
- a deterministic local choice key accompanied by a readable option label;
- 35 factored readable eligibility relationships instead of 59 repeated
  DTO-style binding strings;
- the complete exact 59-binding table in backend authority.

This is a design audit, not a Context V2 implementation. No maintained
runtime source, Prompt/Pack/reason-catalog asset, packet payload, Choice
schema, adapter, validator, materializer, runtime route, frozen expectation or
provider state changed. Canonical Packet/Choice documentation is updated
below; their runtime factories and outputs are not.

## 2. Context Bootstrap and affected authority

Target domain: Gate 2 model-facing financial semantic decision context.

Normative contracts read:

- [architecture authorities](../../stage2/contracts/BROKER_REPORTS_ARCHITECTURE_AUTHORITIES.md);
- [LLM Semantic Context v1](../../stage2/contracts/BROKER_REPORTS_GATE2_LLM_SEMANTIC_CONTEXT.v1.md);
- [Financial Semantic Packet V6](../../stage2/contracts/BROKER_REPORTS_GATE2_FINANCIAL_SEMANTIC_PACKET_V6.md);
- [Financial Semantic Choice V6](../../stage2/contracts/BROKER_REPORTS_GATE2_FINANCIAL_SEMANTIC_CHOICE_V6.md);
- [Local Choice v1](../../stage2/contracts/BROKER_REPORTS_GATE2_FINANCIAL_SEMANTIC_LOCAL_CHOICE.v1.md);
- Financial Semantic Pack, Evidence Bundle, Candidate Compiler and Generic
  Materialization contracts.

Authority remains unchanged:

| Concern | Existing sole owner | GOAL 2 treatment |
| --- | --- | --- |
| model-visible context construction | `Gate2FinancialSemanticV6PacketFactory.create` | audit its non-active projection; no implementation change |
| type and role meaning | Financial Semantic Pack through the existing type-card projection authority | Context V2 must version/extend that projection to carry Pack title; packet code must not bypass it |
| semantic response contract | V6 Choice factory | current active Choice unchanged |
| local answer normalization | existing V6 Choice/expansion authorities | future readable key must map through the same boundary |
| exact values, refs, lineage and retention | Evidence Bundle | remain exact and backend-owned; future Context V2 hides them, while historical active V6 exposure is unchanged |
| complete option bindings | Candidate Compiler and Typed Option | remain complete and authoritative |
| provider projection/parsing | provider adapters | no semantic or alias rewrite |
| validation/materialization | existing factories | unchanged |

The affected authority is only the documented future presentation policy
inside the existing packet/Choice owners. No second packet builder, Choice
factory, Pack, registry, binding resolver or GUI mechanism is introduced.

## 3. Active and non-active runtime truth

The alias surface audited here is not the current active V6 request.

```text
ACTIVE_V6_PACKET:
exact four-block packet with global refs and exact option IDs

ACTIVE_V6_CHOICE:
exact typed_option_id or unclassified reason_code

INACTIVE_CANDIDATE:
Slim View v2 + Local Choice v1

SLIM_ACTIVE:
false

LOCAL_CHOICE_ACTIVE:
false

CURRENT_QUALIFICATION_AND_CONTRACT_ROUTE:
packet.payload + current exact-ID Choice

PRODUCT_PRODUCTION_ADMISSION:
empty
```

The non-active candidate was used by the already terminal bounded GOAL 4
diagnostic. That historical authorization is not reopened. GOAL 2 performs no
provider submission and makes no model-quality claim.

## 4. Inspection method and decision test

The audit reconstructed each exact frozen qualification case through the
existing public factories and inspected:

1. the Slim payload;
2. the private alias receipt;
3. the Local Choice response enum;
4. the exact compiler-owned role bindings;
5. every model-visible inbound alias reference.

Provider adapters may wrap the canonical strict schema for an exact provider,
but they do not introduce another alias namespace or option binding. GOAL 2
does not select a provider and therefore does not claim a new exact
provider-specific final schema.

The 12-case frozen manifest contains 10 semantic cases and two
technical-preclose cases. The two technical cases never enter the semantic
model route and are excluded from alias counts.

An alias or binding passes the necessity test only if at least one condition
is true:

1. another visible field must point to one of several visible values or
   structural nodes;
2. selectable variants bind the same semantic role differently;
3. two options of the same type need an evidence-derived discriminator;
4. a Pack-owned distinction depends on a visible role/value relationship that
   cannot be read unambiguously from the hierarchy;
5. the strict response must return the local selection key.

Mechanical lookup, materializability, provenance, receipt integrity or replay
alone do not justify exposing a binding. Those are backend responsibilities.

## 5. Exact frozen-case census

`v ref` is the number of source-value aliases targeted by at least one current
choice binding. `struct ref` counts structural aliases targeted by current
bindings, even when those bindings are later classified evidence-only.

| Frozen semantic case | Choices | `v total/ref/unused` | `struct total/ref/unused` | Type aliases | Choice aliases | Bindings semantic/evidence |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `syn_successor_v2_unique_cash` | 2 | `4/4/0` | `2/1/1` | 2 | 2 | `7/3` |
| `syn_successor_v2_unique_printed_total` | 2 | `4/4/0` | `2/1/1` | 2 | 2 | `7/3` |
| `syn_successor_v2_multiple_compatible` | 0 | `6/0/6` | `2/0/2` | 0 | 0 | `0/0` |
| `syn_successor_v2_no_registry_type` | 2 | `4/4/0` | `2/1/1` | 2 | 2 | `7/3` |
| `syn_successor_v2_missing_discriminator` | 2 | `3/3/0` | `2/1/1` | 2 | 2 | `6/3` |
| `syn_successor_v2_detail_vs_subtotal` | 0 | `5/0/5` | `2/0/2` | 0 | 0 | `0/0` |
| `syn_successor_v2_adjacent_equal` | 0 | `5/0/5` | `2/0/2` | 0 | 0 | `0/0` |
| `syn_successor_v2_adjacent_fx` | 0 | `6/0/6` | `2/0/2` | 0 | 0 | `0/0` |
| `syn_successor_v2_optional_missing` | 2 | `4/4/0` | `2/1/1` | 2 | 2 | `7/3` |
| `syn_successor_v2_forbidden_neighbour` | 2 | `4/4/0` | `2/1/1` | 2 | 2 | `7/3` |
| **Total** | **12** | **`45/23/22`** | **`20/6/14`** | **12** | **12** | **`41/18`** |

The 45 `vN` aliases cover only semantic values. Twenty additional
`source_reference` values remain code-only and are represented by structural
resolution in the private receipt. Thus the complete Evidence Bundle still
accounts for all 65 frozen source values.

## 6. Alias necessity decisions

### 6.1 Source-value aliases

Current state:

- 45 `vN` aliases are visible;
- 23 are targeted by current bindings;
- 22 have no inbound reference;
- all 22 unreferenced aliases occur in the four cases with zero choices.

After duplicate bindings are factored, all 23 currently referenced semantic
values still participate in one unique readable role/value relationship:
18 common `amount`, `as_of_date` and `currency` relations plus five
option-specific `source_label` relations. The other 22 values have no visible
consumer because their cases expose no choices.

Context V2 decision:

- keep every exact literal, meaning and technical value type once;
- omit a reference key when nothing visible points to the value;
- keep a deterministic request-local value key only when a visible
  relationship needs it, and always show the exact Evidence Bundle
  `column_meaning` or visible label beside it;
- never expose the exact `source_value_ref`;
- reject missing, duplicate or mismapped keys without requiring the human
  label itself to be globally unique.

Examples of readable concepts are `amount`, `currency`, `as of date` and
`description`; these are evidence projections, not a new semantic catalog.

### 6.2 Structural aliases

The frozen candidate creates exactly 10 table aliases and 10 row aliases.

- all 10 `t1` aliases have no inbound reference;
- six `r1` aliases are targeted only by `statement_scope` and
  `printed_label_evidence_ref`;
- four `r1` aliases have no inbound reference;
- `segN`, `gN` and an actual section-node alias have zero positive frozen
  observations.

Readable nesting already establishes document → table → row → value.
Removing a structural alias does not remove the structural node, its kind,
its non-null role or its values.

Context V2 decision:

- omit all numeric structural aliases in the frozen projection;
- allow a structural handle only when a permitted semantic relationship must
  point to one of several visible nodes and nesting is insufficient;
- use a deterministic local key plus exact visible label/role when present;
- show `row`, `table`, `text segment` or another readable kind, not only a
  bare `r1`, `t1`, `seg1` or `g1`;
- keep every exact association and lineage identity private.

The v1 contract names `sN` as a target namespace, but the current candidate
does not construct section nodes; it emits only non-null `section_role`
metadata. This is target allowance, not implemented coverage.

### 6.3 Type aliases

All 12 `TN` aliases are currently referenced by choice records and reciprocal
type-card distinctions. A deterministic local cross-reference key is
necessary; the token `T1` alone does not communicate the type.

The existing Pack already owns readable titles:

```text
Cash balance snapshot
Printed financial metric
```

Context V2 must pair the local key with the Pack-owned title. The maintained
V5/V6 type-card projection currently drops `title`, so the new contract must
version and extend that existing projection authority. Packet code must
consume the validated projection; it must not read the managed asset through
a bypass. It must not expose canonical `input_type_id`, create a Python title
table or copy financial wording into an adapter.

### 6.4 Choice aliases

All 12 `A/B` aliases are current response keys, so a unique local selection
key is mechanically necessary. The letters themselves carry only order, but a
human label is not a safe replacement for identity: two valid options may
legitimately share a type title or lack a unique evidence label.

Context V2 decision:

- keep one unique deterministic request-local `choice_key` that maps to the
  exact `typed_option_id`;
- add a `choice_label` from the Pack-owned type title and, when available, an
  exact evidence-derived discriminator;
- never ask the readable label to serve as canonical or unique identity;
- keep key, visible option content and private mapping together under
  permutation;
- when two options remain semantically indistinguishable, keep their distinct
  keys visible and allow the model to select `unclassified`;
- fail closed only on duplicate/missing key, mapping, scope or integrity
  defects.

The current Local Choice v1 and its `A/B` normalizer remain intact and
non-active. The audit rejects `A/B` as the sole presentation, but does not
pretend that replacing the key with a label is safe. The exact key spelling
belongs to the separately versioned Context V2 contract.

## 7. Binding-by-binding decision

The exact current bindings are:

| Role | Current occurrences | Target kind | Decision contribution | Context V2 treatment |
| --- | ---: | --- | --- | --- |
| `amount` | 12 | semantic value | common source fact; identical across both options in all six choice-bearing cases | render one shared readable role/value relation per case |
| `as_of_date` | 12 | semantic value | common temporal eligibility fact; identical across options | render one shared readable role/value relation per case |
| `currency` | 12 | semantic value | common dimension eligibility fact; identical across options | render one shared readable role/value relation per case |
| `source_label` | 5 | semantic value | option-specific and distinguishes the printed-metric variant | retain as a readable option qualifier/reference |
| `statement_scope` | 12 | deterministic evidence reference | Pack guidance makes bound scope relevant; exact target is common to both options | render one shared readable “scope is bound to this row” relation; exact ref stays backend |
| `printed_label_evidence_ref` | 6 | deterministic evidence reference | option-specific eligibility proof required by printed-metric guidance | render a readable bound-evidence predicate; exact ref stays backend |
| **Total** | **59** | **41 semantic / 18 evidence** | **35 unique readable eligibility relationships** | **24 duplicate occurrences removed; all 59 exact bindings retained privately** |

Forty-eight occurrences are the same four common bindings repeated across two
options in six cases: `amount`, `as_of_date`, `currency` and
`statement_scope`. Factoring them once removes 24 duplicate occurrences.
Eleven occurrences differ between options: six
`printed_label_evidence_ref` predicates and five `source_label` relations.
The exact evidence targets remain backend-only, but their readable
eligibility predicates remain visible because current Pack guidance asks the
model to determine whether scope and printed-label evidence are bound.

This classification is frozen-suite evidence, not an assertion that
structural relationships can never matter. A future Context V2 linter may use
“this row” when the target is structurally unique; multiple visible nodes
require a readable structural key under the decision test in section 4. It
may not expose the raw exact binding.

## 8. Readable naming derivation and fail-closed rules

Readable labels must come from current authorities:

| Concept | Authoritative naming source | Collision treatment |
| --- | --- | --- |
| value reference | exact Evidence Bundle column meaning or visible label | evidence-derived row/section/label qualifier |
| structural reference | deterministic local key plus readable node kind and exact visible label/role when present | key remains unique even when no semantic label exists |
| type reference | deterministic local key plus exact Financial Semantic Pack title | key remains unique even when labels collide |
| choice reference | deterministic local key plus Pack title and optional exact evidence-derived option label | semantic indistinguishability remains a valid route to `unclassified` |
| unclassified reason | stable code plus managed reason-catalog human meaning | catalog remains inactive until Context V2 |

The renderer may mechanically replace underscores with spaces. It may not
invent financial wording, use a hash, expose a global ID or turn a local name
into stable persisted identity.

Local keys and readable labels satisfy separate rules:

- keys are unique, request-bound, disposable, mapped in the private receipt
  and non-conflicting with `unclassified`;
- labels come only from Pack/evidence authorities and need not be unique;
- key-to-option meaning moves with the visible option under permutation;
- a semantic label collision offers `unclassified`; it is not a technical
  integrity failure;
- duplicate or missing keys, changed mapping/scope or integrity mismatch are
  rejected.

## 9. Private mapping and evidence preservation

No backend mapping is deleted. A future receipt must still preserve:

- visible value key → exact `source_value_ref`;
- visible structural key → composite exact association/lineage node;
- readable type key → exact `input_type_id`;
- readable choice key → exact `typed_option_id`;
- all code-only deterministic-reference values;
- the complete exact role-binding table for every option, including bindings
  hidden from the model;
- active packet, candidate request and response-schema bindings;
- integrity and replay hashes.

The v1 statement that all aliases are bijective needs one qualification:
semantic value, type and choice aliases are bijective, while multiple exact
evidence-reference values may legitimately resolve to one visible structural
node. Exact reconstruction remains total because the receipt also preserves
the full `{role_id, source_value_ref}` table. A many-to-one structural
resolution must not be described as a lost or merged exact binding.

The model still owns no exact ref, binding, retention decision, record ID,
validation or materialization.

## 10. Documentation corrections found by the audit

Five documentation discrepancies or missing future-boundary qualifications
are corrected in the canonical
documents with this report:

1. the V6 Choice document said GOAL 3 still had to add the Context Linter,
   although the linter and later diagnostic already exist;
2. the LLM Context example used `role` while the allowlist and candidate use
   `row_role`;
3. section aliases and structural labels were described without distinguishing
   target allowance from current candidate coverage;
4. Pack titles were selected as the readable type-label authority without
   recording that the existing type-card projection currently drops them and
   must be versioned rather than bypassed;
5. a readable choice label was previously treated as replacement identity,
   which would turn legitimate semantic ambiguity into a mapping failure.

The audit also records the many-to-one evidence-reference qualification and
the future readable-name requirement. None of these documentation corrections
changes runtime behavior.

## 11. Benchmark compatibility stop

The four frozen `ambiguous_registry_type` cases with zero Typed Options are:

- `syn_successor_v2_multiple_compatible`;
- `syn_successor_v2_detail_vs_subtotal`;
- `syn_successor_v2_adjacent_equal`;
- `syn_successor_v2_adjacent_fx`.

They contain:

```text
VISIBLE_CHOICES: 0
VISIBLE_TYPE_CARDS: 0
UNREFERENCED_VALUE_ALIASES: 22
UNREFERENCED_STRUCTURAL_ALIASES: 8
```

Removing those aliases improves readability but does not provide the two or
more plausible type meanings required by the managed
`ambiguous_registry_type` boundary. GOAL 2 therefore does not decide whether
the proven defect is context coverage, expected-answer policy or the reason
vocabulary.

Consequences:

- frozen expected answers remain unchanged;
- count `1` remains outside both managed reason boundaries;
- Context V2 implementation and benchmark conformance are not claimed;
- the full benchmark is not run;
- no Prompt, Pack or reason wording changes automatically;
- GOAL 3 may define the versioned Context V2 contract only after this audit is
  accepted and merged, and it must preserve this compatibility stop.

## 12. Verification

Repository/runtime boundary:

```text
PROVIDER_CALLS: 0
PROVIDER_RESPONSES: 0
FULL_BENCHMARK_RUNS: 0
RUNTIME_SOURCE_FILES_CHANGED: 0
PROMPT_FILES_CHANGED: 0
PACK_FILES_CHANGED: 0
CHOICE_SOURCE_FILES_CHANGED: 0
ADAPTER_FILES_CHANGED: 0
VALIDATOR_OR_MATERIALIZER_FILES_CHANGED: 0
STAGE_MUTATIONS: 0
PRODUCTION_MUTATIONS: 0
CUSTOMER_INPUTS_READ: 0
CREDENTIALS_READ: 0
HISTORICAL_REPORTS_OR_RECEIPTS_MODIFIED: 0
```

Local verification replays the maintained factories and tests for:

- all 10 frozen candidate projections;
- exact binding resolution;
- alias/choice determinism and permutation;
- collision, orphan, unmapped and tamper rejection;
- canonical expansion/materialization parity;
- current active packet and Choice parity.

The audit contains only frozen synthetic counts and repository-safe
identifiers. It contains no customer context, credentials, provider response
IDs, raw provider envelopes, private paths or reasoning traces.

## 13. Documentation

Canonical documents updated in the same change:

- architecture authority map;
- global Gate architecture component map;
- LLM Semantic Context v1;
- Financial Semantic Packet V6;
- Financial Semantic Choice V6;
- Local Choice v1;
- Stage 2 Context Index;
- this report and its safe receipt.

No document was moved or renamed, so no redirect entry is required.

## 14. Acceptance

```text
EVERY_VISIBLE_ALIAS_JUSTIFIED_OR_TARGETED_FOR_REMOVAL: YES
UNUSED_VALUE_ALIASES_IDENTIFIED: 22
UNUSED_STRUCTURAL_ALIASES_IDENTIFIED: 14
FROZEN_REQUIRED_VALUE_KEYS: 23
FROZEN_TARGET_NUMERIC_STRUCTURAL_ALIASES: 0
FROZEN_REQUIRED_TYPE_KEYS_WITH_READABLE_LABELS: 12
FROZEN_REQUIRED_CHOICE_KEYS_WITH_READABLE_LABELS: 12
VISIBLE_BINDINGS_CURRENT: 59
VISIBLE_UNIQUE_ELIGIBILITY_RELATIONSHIPS_TARGET_FROZEN: 35
VISIBLE_DUPLICATE_BINDING_OCCURRENCES_REMOVED: 24
EXACT_BACKEND_BINDINGS_PRESERVED: 59_OF_59
SEMANTIC_BINDINGS_SEPARATED_FROM_TECHNICAL_BINDINGS: YES
READABLE_NAMES_FROM_EXISTING_AUTHORITIES: YES
SEMANTICALLY_INDISTINGUISHABLE_CHOICES_ALLOW_UNCLASSIFIED: YES
KEY_MAPPING_AND_INTEGRITY_DEFECTS_FAIL_CLOSED: YES
PROVIDER_CALLS: ZERO
RUNTIME_CHANGED: NO
PRODUCT_PRODUCTION_ADMISSION: EMPTY
BENCHMARK_CONFORMANCE: NOT_CLAIMED
DOCUMENTATION: UPDATED_IN_SAME_CHANGE
```

GOAL 3 may start only after this GOAL is freshly reviewed, approved, green and
merged. It must create a separate versioned Context V2 contract; it may not
silently activate or implement the candidate through this audit.
