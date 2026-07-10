# Broker Reports Gate 2 Source-Fact Stitching Contract v0

Date: 2026-07-10

Contract id: `broker_reports_source_fact_stitch_result_v0`

## 1. Purpose

The stitcher is the deterministic fan-in and final row/segment ownership and
coverage authority for domain extraction. It never reads unvalidated model
output and never recalculates facts.

Production entrypoint:
`Gate2SourceFactStitcherFactory.create().stitch(...)`.

## 2. Inputs

- exactly one validator-passed route artifact;
- zero or more validator-passed domain source-facts outputs with ArtifactStore
  refs;
- explicit rejected domain package outcomes and safe validator codes.

An output with `validator_status != passed` is forbidden from the accepted
input list.

## 3. Required result

```json
{
  "schema_version": "broker_reports_source_fact_stitch_result_v0",
  "stitch_result_id": "sfstitch_opaque",
  "extraction_run_id": "sfdrun_opaque",
  "normalization_run_id": "run_opaque",
  "case_id": "case_or_null",
  "document_ref": "document_opaque",
  "source_unit_ref": "unit_opaque",
  "route_ref": "art_opaque",
  "routing_policy_version": "gate2_source_unit_domain_routing_v0",
  "stitch_policy_version": "gate2_source_fact_stitching_v0",
  "accepted_fact_refs_by_domain": {},
  "rejected_candidate_refs": [],
  "ownership_map": [],
  "conflicts": [],
  "unknown_source_row_refs": [],
  "no_fact_results": [],
  "uncovered_refs": [],
  "issue_fact_linkage": [],
  "coverage": {},
  "issue_refs": [],
  "downstream_restrictions": {}
}
```

## 4. Ownership algorithm

For each route-selected ref, in route order:

1. A deterministic header/blank/layout no-fact entry is owned as
   `deterministic_no_fact`; model claims cannot override it.
2. More than one validator-passed typed fact claim creates
   `multiple_typed_domain_claims`; owner remains null.
3. Exactly one typed fact claim owns the ref.
4. With no typed claim, one or more unknown claims collapse deterministically
   to one `unknown_source_row` owner.
5. With no fact claim, an allowed validator-passed no-fact claim accounts for
   the ref.
6. Otherwise the ref is uncovered.

A typed claim plus unknown claim resolves to the typed claim. Unknown is not a
second typed domain claim. Duplicate fact ids create an explicit run conflict.

No v0 multi-fact rule exists. Future rules require a new contract/policy id and
must be present in the route before extraction.

## 5. Coverage result

Coverage counts require:

- selected refs;
- accepted fact-owned refs;
- unknown refs;
- no-fact refs;
- conflict refs;
- uncovered refs.

Status:

- `complete`: no conflict and no uncovered ref;
- `conflicted`: at least one ownership or duplicate-id conflict;
- `partial`: no conflict, but at least one uncovered ref.

`all_selected_refs_accounted=true` does not imply success when conflicts exist.
Expansion requires `coverage_status=complete` and `conflict_free=true`.

## 6. Rejections and issue linkage

`rejected_candidate_refs` records domain, package ref, validation ref,
candidate refs, and safe error codes. Rejected private output content is never
copied.

`issue_fact_linkage` is built only from validator-passed facts and preserves
issue ref, fact id, source-facts ref, and domain. The stitcher does not change
issue status or impact.

## 7. Downstream restrictions

The result always sets these false:

- `cross_document_consolidation_allowed`;
- `tax_calculation_allowed`;
- `declaration_mapping_allowed`;
- `xls_xlsx_generation_allowed`.

`gate3_handoff_allowed` may be true only for complete conflict-free unit
coverage. It is still not proof of whole-document/case completeness,
intermediate-ledger readiness, tax readiness, or declaration readiness.

## 8. Persistence and privacy

The result is `safe_internal` in `project_artifact_store`. It contains opaque
refs, safe codes, ids, counts, ownership, and restrictions only. It must not
contain private fact fields, raw rows/text, filenames, file ids, paths,
accounts, personal data, secrets, or env values.

Knowledge/RAG and vector backends are forbidden.

## 9. Status

`GATE2_SOURCE_FACT_STITCHER_READY` requires passing conflict, unknown,
no-fact, rejection, duplicate-id, issue-linkage, and complete/no-drop coverage
tests.
