# Broker Reports Gate 2 Source-Unit Routing Contract v0

Date: 2026-07-10

Contract id: `broker_reports_source_unit_domain_route_v0`

## 1. Purpose

This contract deterministically maps every selected row/segment ref in one
Gate 2 source unit to a bounded extractor candidate set or a deterministic
no-fact coverage result. It does not extract facts.

Production entrypoint:
`Gate2SourceUnitRouterFactory.create().route(...)`.

## 2. Required shape

```json
{
  "schema_version": "broker_reports_source_unit_domain_route_v0",
  "route_id": "sfroute_opaque",
  "extraction_run_id": "sfdrun_opaque",
  "normalization_run_id": "run_opaque",
  "case_id": "case_or_null",
  "document_ref": "document_opaque",
  "source_unit_ref": "unit_opaque",
  "base_package_id": "sfpkg_opaque",
  "routing_policy_version": "gate2_source_unit_domain_routing_v1",
  "fallback_domain": "unknown_source_row",
  "route_entries": [],
  "selected_source_refs": [],
  "issue_refs": [],
  "ownership_policy": {},
  "coverage": {}
}
```

Every route entry requires:

```json
{
  "source_ref": "row_or_segment_ref",
  "source_kind": "table_row|text_segment|coverage_only|unprojected_selected_ref",
  "route_kind": "model_candidate|deterministic_no_fact",
  "safe_header_signals": [],
  "safe_source_signals": {
    "value_kinds": [],
    "passport_document_kind": null,
    "usage_modes": [],
    "fact_type_hint_present": false,
    "derived_segment_signal_present": false
  },
  "candidate_domains": [],
  "primary_suggested_domain": null,
  "allowed_extractor_ids": [],
  "issue_refs": [],
  "reason_codes": [],
  "confidence": "high|medium|low",
  "fallback_domain": "unknown_source_row",
  "multi_fact_rule_id": null
}
```

## 3. Domain and extractor registry

| Domain | Extractor id |
| --- | --- |
| `trade_operation` | `trade_operation_extractor` |
| `income` | `income_extractor` |
| `withholding_tax` | `withholding_tax_extractor` |
| `fee_commission` | `fee_commission_extractor` |
| `cash_movement` | `cash_movement_extractor` |
| `currency_fx` | `currency_fx_extractor` |
| `position_snapshot` | `position_snapshot_extractor` |
| `document_summary_evidence` | `document_summary_evidence_extractor` |
| `unknown_source_row` | `unknown_source_row_extractor` |

## 4. Allowed signals

The router may use only:

- normalized safe header descriptors and per-cell header labels;
- exact visible helper labels already inside the private bounded projection;
- non-content value-kind signals;
- document passport safe projection;
- DUC usage modes;
- DCP/issue refs;
- row/segment provenance and coverage kind;
- existing deterministic `fact_type_hint`.

Regex/pattern matching may normalize helper tokens or detect a value kind. It
must not mint a fact, normalized value, evidence ref, issue conclusion, or
source-of-record parsing result.

## 5. Coverage invariants

- `route_entries[*].source_ref` must equal `selected_source_refs` in the same
  order, exactly once each.
- A model candidate has one or two candidate domains.
- A deterministic no-fact entry has no candidate domain or extractor.
- No-signal rows route to the unknown fallback.
- Header, blank, and layout coverage is deterministic and not delegated to an
  LLM.
- No selected ref may be omitted because it is ambiguous or unsupported.

## 6. Ownership policy

The route contains a suggested primary domain, not final ownership. Final
ownership belongs to the stitcher after domain validation.

In v0:

- silent double claim is forbidden;
- no explicit multi-fact rule is enabled;
- more than one validator-passed typed claim creates a conflict;
- unknown is a valid coverage-preserving result;
- the LLM cannot change the route or assign final ownership.

## 7. Persistence and privacy

The route is `safe_internal` in `project_artifact_store`. It may contain opaque
refs, safe labels, value kinds, reason codes, confidence, policy ids, issue
refs, and aggregate counts. It must not contain raw rows, full source text,
filenames, OpenWebUI file ids, paths, accounts, personal data, secrets, or env
values.

Knowledge/RAG and vector backends are forbidden.

## 8. Derived source-unit segmentation

Before customer extraction, the factory-backed domain runtime may create a
deterministic segmentation plan:

```text
validated bounded Gate 1 source unit
  -> parent route
  -> broker_reports_source_unit_segmentation_plan_v0
  -> broker_reports_derived_source_unit_v0
  -> derived-unit route v1
```

`Gate2SourceUnitSegmenterFactory.create()` is the only production entrypoint.
It may split by contiguous route cluster, deterministic no-fact class, safe
text section, and non-overlapping row/segment window. It must not parse facts,
change source values, mint source provenance, or silently omit a parent ref.

Every parent-selected row/segment ref appears exactly once in a derived unit.
The plan records selected and deferred derived units, duplicate/unaccounted
refs, and the parent remainder status. A bounded unit derived from a truncated
legacy slice sets:

```text
source_slice_truncated=false
parent_source_slice_truncated=true
coverage_scope=complete_within_parent_projection
parent_remainder_status=pending_gate1_reslice
```

This means the derived unit is complete for its selected refs, not that the
whole customer document is complete. The plan preserves the parent source and
slice-payload checksum refs. The derived private projection preserves original
row/cell/segment/source-value refs and rebases only private payload indices.

The v1 router may reuse a derived segment's uniform high-confidence domain
signal only when it was deterministically produced from a contiguous parent
route cluster and its candidate domain set contains exactly that one typed
domain. The model cannot create or alter this signal.

## 9. Status

`GATE2_SOURCE_UNIT_ROUTER_READY` requires passing deterministic coverage,
ambiguity, unknown, no-fact, and no-drop tests.

## 10. Complete parent routing (2026-07-10)

When the parent is `private_normalized_source_unit_v0`, routing and segmentation
must preserve:

- `parent_source_slice_truncated=false`;
- ordered partition of every selected parent ref;
- `parent_remainder_status=not_applicable_parent_complete`;
- parent payload/source/unit checksum refs;
- original row/cell/text/source-value refs.

Derived package construction copies only the narrowed projection and small
metadata. Copying the complete parent projection into every derived segment is
forbidden because it violates model budget intent and creates avoidable memory
amplification. Legacy parent slices keep `pending_gate1_reslice` when truncated.

## 11. PDF text-layer routing boundary (2026-07-10)

For a validated PDF source unit, `source_kind` may additionally distinguish
`pdf_page_text`, `pdf_line_cluster`, `pdf_section_text` and
`pdf_table_candidate`. The router may use only safe unit kind, layout policy
refs, value kinds, page/section ordinals, candidate strategy/confidence, DCP
metadata and existing issue refs. Raw PDF text remains inside the bounded
private package.

Routing rules:

- each selected text/line/table-candidate ref appears exactly once;
- blank/layout/non-text coverage is deterministic;
- low-confidence or conflicting table geometry never routes as an
  authoritative table row;
- candidate fallback text refs preserve coverage but do not become a second
  coverage owner;
- no-signal PDF text routes to `unknown_source_row`;
- the LLM cannot change page order, candidate status, coverage or final
  ownership;
- derived segmentation remains contiguous and records every deferred sibling.

PDF routing requires a complete parent PDF unit. Partial payloads, hidden
remainder, checksum mismatch or unresolved source-value refs are rejected
before routing. Slice 1 proves the upstream no-model input-readiness package
with page/text/value refs. Domain router and source-fact model execution were
not run and remain a later bounded slice.

```text
PDF_TEXT_LAYER_INPUT_READINESS_ROUTING_BOUNDARY_READY
PDF_DOMAIN_ROUTER_AND_MODEL_EXECUTION_DEFERRED
```

## 12. PDF layout-unit routing runtime (2026-07-10)

The no-model router and segmenter now accept validated line-cluster and
table-candidate packages. Narrowing rebases only selected layout values into
bounded spans, preserves exact parent-ref partition and carries candidate
strategy/confidence without promoting semantic truth. Model execution remains
deferred.

```text
PDF_LAYOUT_UNIT_ROUTER_READY
PDF_LAYOUT_UNIT_SEGMENTER_READY
PDF_LAYOUT_MODEL_EXECUTION_DEFERRED
```
