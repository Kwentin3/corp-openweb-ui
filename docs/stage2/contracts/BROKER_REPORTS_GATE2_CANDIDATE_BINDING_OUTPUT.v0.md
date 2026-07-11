# Broker Reports Gate 2 Candidate-Binding Output Contract v0

Date: 2026-07-11

Status: `GATE2_CANDIDATE_BINDING_OUTPUT_CONTRACT_READY`

Schema version: `broker_reports_candidate_binding_output_v0`

Validation schema: `broker_reports_candidate_binding_validation_v0`

## 1. Purpose

This is the model-facing semantic selection contract for Gate 2 domain
extraction. The model selects package-bound candidate ids, semantic roles, fact
fields, and relation ids. It does not return or rewrite source values and does
not mint evidence refs.

The output is an intermediate private artifact. Only a validator-passed,
materialized, and strict-source-fact-validator-passed result may become
`broker_reports_source_facts_v0`.

## 2. Required provider mode

Every model call uses provider-native:

```json
{
  "type": "json_schema",
  "json_schema": {
    "name": "broker_reports_candidate_binding_output_v0",
    "strict": true,
    "schema": {}
  }
}
```

Customer fallback is none. JSON-object fallback is not an accepted customer or
live proof result. A provider availability failure such as
`gate2_model_provider_error` is a transport/provider incident, not a contract
rejection.

Provider/profile/adapter/model/usage/latency/response-id and schema-adaptation
metadata is not part of this model output. The adapter and runtime attach
`gate2_provider_execution_metadata_v1` to the private raw attempt and its safe
projection to validation/run audit. A model-supplied field with that meaning
has no authority.

## 3. Output envelope

```json
{
  "schema_version": "broker_reports_candidate_binding_output_v0",
  "package_id": "sfdpkg_opaque",
  "candidate_set_id": "svcset_opaque",
  "candidate_set_hash": "opaque_digest",
  "relation_set_id": "svrelset_opaque",
  "relation_set_hash": "opaque_digest",
  "binding_results": [],
  "no_fact_results": []
}
```

All six identity/version fields are exact package constants. A mismatch fails
closed. The two result arrays together must account for every selected source
ref exactly once.

## 4. Typed binding result

```json
{
  "source_ref": "row_opaque",
  "fact_type": "cash_movement",
  "selected_bindings": [
    {
      "fact_field_path": "normalized_values.amount",
      "candidate_id": "svcand_opaque",
      "semantic_role": "movement_amount"
    }
  ],
  "selected_relation_ids": [],
  "subtype_candidate": "deposit",
  "confidence": "high",
  "completeness": "complete",
  "uncertainty_codes": [],
  "resolved_ambiguity_group_refs": []
}
```

The `(fact_field_path, candidate_id, semantic_role)` triple is one atomic
package-bound choice. A candidate id alone is insufficient because the model,
not the finalizer, owns semantic role assignment.

Allowed values:

- `fact_type`: the package profile domain only;
- `subtype_candidate`: the profile subtype enum;
- `confidence`: `high|medium|low|none`;
- `completeness`: `complete|partial|uncertain|blocked`;
- candidate ids, role/field triples, relation ids, source refs, and ambiguity
  refs: exact package-bound choices only.

An optional field with no suitable candidate is omitted from
`selected_bindings`. A required role cannot be silently null in an accepted
typed fact.

## 5. Unknown result

When evidence is insufficient for the package domain, the model returns:

```json
{
  "source_ref": "row_opaque",
  "fact_type": "unknown_source_row",
  "selected_bindings": [],
  "selected_relation_ids": [],
  "subtype_candidate": "unknown",
  "confidence": "low",
  "completeness": "uncertain",
  "uncertainty_codes": ["candidate_binding_no_safe_semantic_role"],
  "resolved_ambiguity_group_refs": []
}
```

Unknown output must have no candidate bindings or relations and must include at
least one safe uncertainty code. It is explicit coverage, not a hidden drop.

## 6. Deterministic no-fact result

`no_fact_results[]` accounts for a package ref that is structurally not a fact:

```json
{
  "source_ref": "row_opaque",
  "reason_code": "repeated_header"
}
```

Allowed reason codes are:

```text
header_row
blank_row
layout_only
repeated_header
non_fact_annotation
unsupported_source_shape
```

The model cannot use a no-fact entry to erase required coverage or double-own a
row. Coverage validation recomputes the exact partition.

## 7. Package-bound JSON Schema

`candidate_binding_provider_json_schema(package)` creates a fresh schema for
the exact package:

- top-level version, package id, candidate set id/hash, and relation set id/hash
  are `const`;
- every selected source ref has a typed-domain and unknown variant;
- each valid candidate/role/field triple is a separate strict `anyOf` variant
  using `const` values;
- relation ids and ambiguity refs are package-row-bound enums;
- subtype, confidence, completeness, and no-fact reasons are enums;
- objects use `additionalProperties=false` and all declared properties are
  required;
- array budgets are bounded by the exact package inventory;
- no raw or normalized candidate value is embedded in the model output schema.

The provider schema is a pre-call control, not final authority. The validator
repeats all scope and semantic checks after the call.

## 8. Candidate-binding validation

`Gate2CandidateBindingRuntimeFactory.create` is the only production validation
and materialization entrypoint. It validates before materialization.

The safe validation artifact contains status, counts, ids, and typed errors; it
does not contain source values or raw output.

Typed error codes include:

```text
candidate_binding_structured_output_required
candidate_binding_schema_mismatch
candidate_binding_contract_mismatch
candidate_binding_cross_package_scope
candidate_binding_unknown_has_bindings
candidate_binding_unknown_has_relations
candidate_binding_unknown_reason_missing
candidate_binding_subtype_forbidden
candidate_binding_confidence_forbidden
candidate_binding_completeness_forbidden
candidate_binding_fact_type_forbidden
candidate_binding_foreign_candidate_id
candidate_binding_cross_row_candidate
candidate_binding_candidate_domain_forbidden
candidate_binding_candidate_scope_invalid
candidate_binding_candidate_set_scope_invalid
candidate_binding_candidate_set_integrity_failed
candidate_binding_candidate_id_list_mismatch
candidate_binding_candidate_value_unreproducible
candidate_binding_candidate_checksum_mismatch
candidate_binding_semantic_role_forbidden
candidate_binding_fact_field_forbidden
candidate_binding_candidate_kind_forbidden
candidate_binding_duplicate_role
candidate_binding_duplicate_fact_field
candidate_binding_ambiguity_unresolved
candidate_binding_ambiguity_resolution_invalid
candidate_binding_source_value_ref_missing
candidate_binding_checksum_ref_missing
candidate_binding_candidate_reuse_forbidden
candidate_binding_required_role_missing
candidate_binding_required_role_group_missing
candidate_binding_relation_not_found
candidate_binding_relation_invalid
candidate_binding_cross_row_relation
candidate_binding_relation_domain_forbidden
candidate_binding_relation_scope_invalid
candidate_binding_relation_candidate_not_found
candidate_binding_relation_set_scope_invalid
candidate_binding_relation_set_integrity_failed
candidate_binding_relation_id_list_mismatch
candidate_binding_relation_selection_mismatch
candidate_binding_duplicate_relation
candidate_binding_required_relation_missing
candidate_binding_relation_cardinality_invalid
candidate_binding_issue_limited_completeness
candidate_binding_no_fact_reason_forbidden
candidate_binding_duplicate_source_ownership
candidate_binding_coverage_gap
```

Candidate or relation budget failures occur before the model call:

```text
candidate_binding_candidate_budget_exceeded
candidate_binding_relation_budget_exceeded
```

No failed binding selection may be converted to an accepted fact.

## 9. Generic materializer boundary

After binding validation passes, the materializer may:

- resolve selected candidate ids from the exact set;
- copy their mechanically normalized values;
- bind their existing source-value refs;
- populate the selected normalized or extracted fact field;
- carry source row, package, document, unit, audit, issue, completeness, and
  downstream-restriction constants fixed by the package/runtime;
- create pending deterministic placeholders required by the existing source
  fact finalizer and validator route.

It must not:

- choose or replace a candidate, role, field, relation, subtype, or fact type;
- choose between equal candidates;
- infer gross/net, base/quote, trade/settlement, fee/tax, or fact linkage;
- fill a missing required semantic choice;
- resolve an issue;
- create an additional fact or hide a selected row.

The materialized legacy-shaped candidate then passes through the existing
domain finalizer and unchanged strict source-fact validator. That validator
independently resolves refs, reproduces values, verifies checksums, issue
carry-forward, audit constants, provenance, and coverage.

## 10. Repair invariant

A repair call uses the same narrow package, candidate set id/hash, relation set
id/hash, profile, selected refs, and package-bound schema. The raw initial and
repair outputs remain separate private artifacts.

Repair may change only the model's selection within the unchanged choices. It
must not add candidates, relations, rows, values, refs, or issue state. An
identity/hash change fails with `candidate_binding_contract_mismatch`.

## 11. Privacy and persistence

Raw initial/repair outputs, candidate values, source refs, and materialized
pre-validation facts are private case artifacts in project-owned artifact
payload storage. Safe reports may expose only ids, counts, domain names,
selected role names, statuses, and reason/error codes.

The exact provider response id and raw provider exception remain private. Safe
validation/run metadata may expose only allowlisted execution fields and a
response-id presence flag/hash plus canonical/adapted schema hashes and the
transform count.

The route performs no Knowledge/RAG/vector writes, ordinary processed upload,
OCR/VLM, page rendering, tax calculation, declaration generation, spreadsheet
generation, or cross-document consolidation.

## 12. Backward compatibility

The new output contract is active only when the package carries
`candidate_binding_mode=candidate_ids_and_semantic_roles_v0`. Candidate binding
is disabled by default until its proof gates pass.

Legacy domain packages and `broker_reports_domain_source_facts_v0` output stay
on the explicit legacy runtime. They are not silently parsed as candidate
binding output and persisted artifacts are never mutated in place.
