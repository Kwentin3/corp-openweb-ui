# Broker Reports Gate 2 Candidate Relations Contract v0

Date: 2026-07-11

Status: `GATE2_CANDIDATE_RELATION_CONTRACT_READY`

Schema version: `broker_reports_candidate_relation_set_v0`

## 1. Purpose

This private contract records mechanically supported groupings between
package-bound source-value candidates. A relation says that source structure
supports the grouping. It does not assign business meaning to the participants.

The relation layer is required because independent exact values are not enough
to prove coupled selections such as the two amounts and two currencies of one
FX row.

## 2. Ownership and route

```text
broker_reports_source_value_candidate_set_v0
-> Gate2CandidateBindingKernelFactory.create
-> deterministic relation discovery
-> broker_reports_candidate_relation_set_v0
```

Only the shared kernel creates relations. Domain profiles state which relation
kinds are required. The model selects existing relation ids. Neither the model
nor the finalizer may create, edit, merge, or reinterpret a relation.

## 3. Relation-set envelope

```json
{
  "schema_version": "broker_reports_candidate_relation_set_v0",
  "relation_set_id": "svrelset_opaque",
  "package_id": "sfdpkg_opaque",
  "extractor_domain": "currency_fx",
  "relations": [],
  "relation_ids": [],
  "relation_set_hash": "opaque_digest",
  "max_relations": 128,
  "visibility": "private_case",
  "storage_backend": "project_artifact_payload",
  "validation_status": "passed"
}
```

Required invariants:

- all participating candidate ids exist in the exact candidate set;
- `package_id` and domain equal the containing package/profile;
- `relation_ids` is the exact ordered projection of `relations[].relation_id`;
- the set id and hash bind the complete relation inventory;
- relation discovery never widens the package or changes candidate ownership.

## 4. Relation shape

Each `relations[]` entry contains:

| Field | v0 rule |
| --- | --- |
| `relation_id` | Stable opaque id bound to package, row, kind, and participating candidate ids. |
| `candidate_ids` | Existing candidate ids in deterministic order. |
| `relation_kind` | Mechanical relation kind. |
| `shared_source_scope` | `same_row` in v0. |
| `row_refs` | Exactly one package row in v0. |
| `cell_refs`, `header_refs`, `section_refs` | Existing structural support refs; `section_refs` is empty in the current row implementation. |
| `allowed_domains` | Exact profile domain. |
| `allowed_semantic_role_combinations` | Mechanically provable combinations when defined; empty in the current v0 builder, so the profile remains authoritative. |
| `cardinality` | Exact `minimum` and `maximum` participant count for this relation instance. |
| `candidate_reuse_policy` | `profile_controlled`. |
| `ambiguity_state` | `explicit_selection_required`. |
| `reason_codes` | Deterministic relation-discovery reason codes. |
| `validation_status` | `passed` only for a mechanically valid relation. |

## 5. Supported v0 relation kinds

The implemented v0 kernel produces only:

| Relation kind | Mechanical condition | Business meaning explicitly not claimed |
| --- | --- | --- |
| `same_row_candidate_group` | More than one candidate belongs to one row. | Participants form one fact or should be consolidated. |
| `amount_with_currency` | One amount/total and one currency candidate share one row. | Amount is gross, net, fee, tax, base, or quote. |
| `quantity_with_instrument` | One quantity and one instrument candidate share one row. | Quantity is a trade, position, opening, or closing balance. |
| `base_quote_amount_currency_group` | An FX-domain row has at least two amounts and two currencies; the first bounded set is ordered by source column. | Which amount/currency is base or quote, or whether the conversion is taxable. |

The names below are legitimate future contract extensions but are not produced
by the current v0 builder and must not appear in v0 model output unless a later
version implements and validates them:

```text
date_with_source_row
unit_price_with_quantity
base_amount_with_base_currency
quote_amount_with_quote_currency
explicit_rate_with_currency_pair
gross_net_amount_pair
income_with_explicit_withholding
operation_with_explicit_fee
source_total_with_section
same_table_section_group
```

## 6. Semantic boundary

A mechanically valid relation never means that:

- a tax is creditable;
- an amount is gross, net, base, quote, fee, or withholding;
- a currency is base or quote;
- a date is trade, settlement, payment, snapshot, or rate date;
- a fee is deductible;
- an income and withholding should be linked;
- rows should be aggregated or consolidated.

Those are semantic choices by the domain model, constrained by its profile and
then independently validated. Tax, declaration, and consolidation decisions
remain outside Gate 2.

## 7. Model selection and validation

The package-bound provider schema restricts `selected_relation_ids` to relation
ids from the same selected row. The candidate-binding validator then checks:

- relation existence in the exact relation set;
- `validation_status=passed`;
- exact row scope;
- allowed domain;
- presence of every profile-required relation kind;
- declared minimum cardinality.

Typed failures include:

```text
candidate_binding_relation_not_found
candidate_binding_relation_invalid
candidate_binding_cross_row_relation
candidate_binding_relation_domain_forbidden
candidate_binding_required_relation_missing
candidate_binding_relation_cardinality_invalid
candidate_binding_relation_selection_mismatch
candidate_binding_relation_candidate_not_found
candidate_binding_relation_scope_invalid
candidate_binding_relation_set_integrity_failed
```

A relation failure rejects the binding selection. It is never converted into
an accepted partial fact by the finalizer.

## 8. Candidate reuse

Relation membership does not authorize candidate reuse. Reuse is controlled
only by the active domain profile. In v0 every shipped profile has an empty
`candidate_reuse` map, so assigning one candidate to more than one role fails
closed.

## 9. Budget and repair invariants

The default package budget is `max_relations=128`. Exceeding it fails with:

```text
candidate_binding_relation_budget_exceeded
```

No truncation, sampling, or silent relation loss is allowed. A repair attempt
uses the original `relation_set_id`, `relation_set_hash`, and package-bound
schema. The model may revise only its selection; it cannot revise the relation
inventory.

## 10. Privacy and storage

The complete relation set is `private_case` in
`project_artifact_payload`. It can reveal row and cell structure even when
candidate values are omitted. Safe artifacts and reports may expose only
opaque relation ids, kinds, counts, validation statuses, and safe reason/error
codes.

Relations are forbidden in Knowledge, RAG, vector storage, ordinary processed
upload, and customer chat output.

## 11. Compatibility

The relation contract is active only with
`candidate_binding_mode=candidate_ids_and_semantic_roles_v0`. Legacy packages
remain on their explicit compatibility runtime. Missing relation contracts are
not inferred from legacy rows and persisted artifacts are not mutated in place.
