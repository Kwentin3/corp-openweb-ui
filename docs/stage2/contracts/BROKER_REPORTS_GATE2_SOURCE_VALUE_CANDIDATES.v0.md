# Broker Reports Gate 2 Source-Value Candidates Contract v0

Date: 2026-07-11

Status: `GATE2_SOURCE_VALUE_CANDIDATE_CONTRACT_READY`

Schema version: `broker_reports_source_value_candidate_set_v0`

## 1. Purpose

This private contract is the deterministic boundary between a bounded Gate 2
source unit and semantic domain extraction. It exposes only values that the
runtime can reproduce from an existing `source_value_ref` and checksum. It does
not decide what a value means in the business domain.

The contract is source-format-neutral at the boundary. The v0 discovery
implementation consumes normalized table rows, whether their validated source
origin is native or PDF geometry. It does not reconstruct tables, invoke OCR,
or read ordinary upload, Knowledge, RAG, vector, or external sources.

## 2. Ownership and factory route

The production route is:

```text
normalized table projection / bounded source unit
-> Gate2DomainPackageBuilderFactory.create
-> Gate2CandidateBindingKernelFactory.create
-> broker_reports_source_value_candidate_set_v0
```

Only the candidate-binding kernel discovers candidates. A Pipe, Prompt, model,
finalizer, validator, or stitcher must not mint, widen, drop, or reinterpret the
candidate set.

## 3. Candidate-set envelope

```json
{
  "schema_version": "broker_reports_source_value_candidate_set_v0",
  "candidate_set_id": "svcset_opaque",
  "package_id": "sfdpkg_opaque",
  "extractor_domain": "income",
  "candidates": [],
  "candidate_ids": [],
  "candidate_set_hash": "opaque_digest",
  "max_candidates": 96,
  "visibility": "private_case",
  "storage_backend": "project_artifact_payload",
  "validation_status": "passed"
}
```

Required invariants:

- `candidate_set_id` is stable for the exact package and ordered candidate ids;
- `candidate_ids` is the exact ordered projection of `candidates[].candidate_id`;
- `candidate_set_hash` binds the complete candidate payload, not only counts;
- `package_id` and `extractor_domain` equal the containing domain package;
- no candidate belongs to a row or value outside the narrow package;
- an empty candidate set is explicit and is never replaced with guessed values.

## 4. Candidate shape

Each `candidates[]` entry contains:

| Field | v0 rule |
| --- | --- |
| `candidate_id` | Stable opaque id bound to package, row, cell, source-value ref, kind, and reproduced normalized value. |
| `candidate_kind`, `value_kind` | Mechanical value kind; they are equal in v0. |
| `document_ref`, `source_unit_ref`, `table_projection_ref`, `row_ref` | Existing package scope only. |
| `cell_refs`, `source_value_refs` | Existing source refs supporting the candidate. v0 uses one source value per candidate. |
| `character_span_refs` | Existing span refs when applicable; empty for the current table-row implementation. |
| `column_ref`, `column_ordinal` | Existing structural column evidence. |
| `header_refs`, `safe_header_descriptors` | Bounded structural evidence; never a business-role assertion. |
| `normalized_value`, `normalization_kind` | Deterministically reproduced private value and the exact reproduction rule. |
| `value_checksum_refs` | Existing checksum refs for independent source-value resolution. |
| `sign_evidence`, `direction_evidence` | Mechanical visible signals only. |
| `currency_context_refs`, `date_context_refs`, `instrument_context_refs` | Existing context refs when a future builder can prove them; empty in the current v0 builder. |
| `allowed_semantic_roles` | Roles derived from the selected domain profile and candidate kind. |
| `allowed_fact_types`, `allowed_fact_field_paths` | Exact package/profile allowlists. |
| `ambiguity_group_ref` | Shared opaque ref for equal normalized values of the same kind and row that have distinct source refs; otherwise null. |
| `composite_group_ref` | Existing mechanically proven composite group when available; null in the current v0 builder. |
| `candidate_scope` | `single_source_value` in v0. |
| `reason_codes` | Deterministic discovery and ambiguity reason codes. |
| `evidence_quality` | Deterministic quality; `high` only after reproduction succeeds. |
| `visibility`, `storage_backend` | Always `private_case` and `project_artifact_payload`. |

The candidate payload is private because `normalized_value`, source refs, and
structural context can reveal customer data. Safe artifacts and reports may
expose only opaque ids, kinds, counts, allowed role names, statuses, and safe
reason codes.

## 5. Candidate kinds

The v0 kernel supports:

```text
decimal_amount
date
currency_code
quantity
instrument_identifier
instrument_label
explicit_fx_rate
short_visible_label
categorical_direction
source_provided_total
unknown_mechanical_value
```

`unknown_mechanical_value` means that a bounded source-visible value was
reproduced but no more specific mechanical kind was proven. It does not permit
the model to treat that value as any field. A candidate is retained only when
the active domain profile allows at least one role for its kind.

## 6. Deterministic discovery rules

Discovery may use only the narrow source unit, existing source-value index,
existing structural refs, bounded header descriptors, row role, and mechanical
normalizers.

Current reproduction rules are:

- decimal-like values: `decimal_dot`;
- exact ISO dates: `iso_date_exact`;
- visible three-letter currencies: `currency_code_visible`;
- bounded labels and identifiers: `trimmed_text`.

Structural headers guide mechanical kinds: `quantity`, `rate`, `instrument`,
`operation`, and `description` have bounded handling. A summary/subtotal decimal
may also become `source_provided_total`. A visible explicit FX operation token
may allow a decimal candidate of kind `explicit_fx_rate`.

These rules do not assign `gross`, `net`, `base`, `quote`, `fee`, `tax`, trade
date, settlement date, or any other semantic role.

If reproduction fails, the candidate is absent. The kernel must not repair,
coerce, approximate, aggregate, or infer a value.

## 7. Identity, duplicates, and ambiguity

Candidates with the same visible value remain different when they come from
different source refs. Their ids include their source location and value ref.

For candidates in the same row with the same kind and reproduced value but
different source refs, the kernel assigns one `ambiguity_group_ref` and adds
`equal_value_distinct_source_refs`. The model must explicitly select the
candidate id and list that ambiguity group as resolved. Deterministic code must
not prefer the first, leftmost, or otherwise convenient candidate.

Exact duplicate candidate ids are deterministically deduplicated. This does
not merge distinct source refs.

## 8. Budget and no-silent-truncation rule

The default package budget is `max_candidates=96`.

If discovery produces more candidates, package construction fails with:

```text
candidate_binding_candidate_budget_exceeded
```

The kernel must not truncate, sample, rank away, or silently omit candidates.
Callers may create a smaller validated source unit and rebuild a new package;
they must not alter a persisted package in place.

## 9. Model and finalizer boundary

The provider schema may expose candidate ids and their allowed field/role
triples. It must not expose raw candidate values as output choices.

The model may select an allowed `candidate_id`; it cannot mint an id, change a
candidate, or return a free-form normalized value. The finalizer may copy the
selected candidate's normalized value and existing refs. It must not select the
candidate or its role.

The strict source-fact validator remains final authority and independently
resolves source refs, reproduces normalized values, and verifies checksums.

## 10. Versioning and compatibility

Candidate binding is opt-in. A domain package participates only when it carries
`candidate_binding_mode=candidate_ids_and_semantic_roles_v0` and the complete
candidate, relation, and profile contracts.

Legacy packages without this contract stay on the legacy compatibility runtime.
They must not be silently interpreted as candidate-binding packages. Persisted
legacy artifacts are immutable.

## 11. Forbidden behavior

The candidate layer must not:

- claim semantic table truth;
- select a business role or fact type;
- invent, rewrite, aggregate, or calculate a value;
- collapse equal values from different refs;
- resolve ambiguity;
- cross rows, packages, documents, or cases;
- use Knowledge, RAG, vectors, OCR/VLM, or external data;
- expose private values or source content in safe output;
- perform tax, declaration, consolidation, or Gate 3 work.
