# Broker Reports Gate 2 Source-Fact Extraction Contract v0

Date: 2026-07-10; ownership note reconciled 2026-07-18

Status: `GATE2_SOURCE_FACT_CONTRACT_READY`

## 1. Purpose

This contract defines the Gate 2 run, bounded input-package, validation, persistence, and summary boundaries for extracting source-visible facts from normalized broker-report slices.

Gate 2 starts from validated global Gate 1 artifacts. Historical references to
`Gate 1.5` mean the LLM metadata-passport compatibility sub-stage inside
global Gate 1; they do not define another global product gate. Gate 2 does not
parse raw chat text, raw uploaded files, ordinary OpenWebUI file context,
Knowledge/RAG, or vector results.

Global ownership is defined by the
[Broker Reports gate architecture](../blueprints/BROKER_REPORTS_GATE_ARCHITECTURE.md).

## 2. Contract Family

Required artifact contracts:

```text
broker_reports_source_fact_extraction_run_v0
broker_reports_source_fact_package_v0
broker_reports_source_facts_v0
broker_reports_source_fact_validation_v0
```

Supporting ArtifactStore record types:

```text
broker_reports_source_fact_raw_output_v0
broker_reports_issue_fact_linkage_v0
broker_reports_source_fact_extraction_summary_v0
```

The fact payload contract is specified in `BROKER_REPORTS_GATE2_SOURCE_FACTS.v0.md`. Prompt binding is specified in `BROKER_REPORTS_GATE2_SOURCE_FACT_PROMPT.v0.md`.

## 3. Preconditions

A run may start only when:

- Gate 1 `validation_result_v0` is passed;
- `domain_context_packet_v0` is validated and resolver-accessible;
- `stage_readiness.source_fact_extraction` is `ready` or `ready_with_issue_context`;
- `dropped_source_ready_refs` is empty;
- DCP source-ready refs reconcile exactly with DUC `ready`/`ready_with_issues` refs;
- every DCP issue ref resolves to `gate1_issue_ledger_v0`;
- the handoff supplies authorized private slice refs for selected documents;
- every selected slice validates as `source_unit_provenance_v0`;
- table units expose stable table/row/range/cell/value refs and coverage;
- text units expose stable segment/section/page-or-range/span/value refs and coverage;
- every `source_value_ref` resolves through a private payload path and checksum;
- ArtifactStore user/run/case/chat/workspace, lifecycle, expiry, purge, validation, and source-availability checks pass;
- source intake remains the proven `process=false` private route;
- Knowledge/RAG/vector guards remain false.

Failure of a precondition produces a typed blocked run. It does not fall back to chat, raw files, or Knowledge.

## 4. Canonical Input Rule

The canonical orchestration authority is `domain_context_packet_v0` with resolved linked artifacts. The canonical model-call input is exactly one `broker_reports_source_fact_package_v0`.

`gate2_handoff_v0` is a resolver manifest. `included_document_refs` is not the full source-ready set. Gate 2 must use DCP `next_stage_refs` and handoff `private_slice_refs_by_next_stage_bucket`.

For legacy persisted runs where the full/reduced compatibility handoff record is
blocked but DCP source-fact readiness is valid, an input-readiness audit may
start from the validated DCP and resolve same-scope slice records directly.
It must not read the blocked handoff payload. It may compare only its safe
metadata summary and must report `legacy_compatibility_blocked`. Newly persisted
handoff manifests remain resolver-readable when source-fact readiness is valid,
while retaining the compatibility blocker in their payload.

`Gate2InputReadinessFactory.create` is the only dry-run package-builder
entrypoint. It reads through `ArtifactResolver`, performs no model call and does
not persist packages.

## 5. `broker_reports_source_fact_extraction_run_v0`

### 5.1 Required shape

```json
{
  "schema_version": "broker_reports_source_fact_extraction_run_v0",
  "extraction_run_id": "sf_run_opaque",
  "normalization_run_id": "norm_run_opaque",
  "case_id": "case_opaque_or_null",
  "chat_id": "chat_opaque_or_null",
  "workspace_model_id": "workspace_opaque_or_null",
  "run_status": "created",
  "input_refs": {
    "domain_context_packet_ref": "art_opaque",
    "document_usage_classification_ref": "art_opaque",
    "gate1_issue_ledger_ref": "art_opaque",
    "gate2_handoff_ref": "art_opaque",
    "gate1_validation_ref": "art_opaque",
    "document_metadata_passport_refs": []
  },
  "selection_policy": {
    "policy_id": "gate2_source_fact_selection_v0",
    "waves": ["primary", "secondary", "duplicate_or_non_primary"],
    "cross_check_context_only": true,
    "declaration_support_context_only": true,
    "audit_context_only": true
  },
  "source_ready_ref_decisions": [],
  "package_policy": {},
  "prompt_snapshot_ref": "art_opaque_or_null",
  "output_schema_id": "broker_reports.source_facts.schema.v0",
  "output_schema_hash": "sha256_hex",
  "model_id": "model_opaque",
  "structured_output_policy": {},
  "package_refs": [],
  "raw_output_refs": [],
  "source_facts_refs": [],
  "validation_refs": [],
  "issue_fact_linkage_ref": "art_opaque_or_null",
  "summary_ref": "art_opaque_or_null",
  "coverage_summary": {},
  "artifactstore_policy": {},
  "vector_knowledge_guard": {},
  "started_at": "2026-07-10T00:00:00Z",
  "finished_at": null
}
```

The example is structural only and contains no customer data.

### 5.2 Run statuses

Allowed `run_status` values:

```text
created
inputs_validated
packages_built
extracting
validating
completed
completed_with_rejections
blocked
failed_safe
privacy_failed
purged
```

Terminal statuses are `completed`, `completed_with_rejections`, `blocked`, `failed_safe`, `privacy_failed`, and `purged`.

`completed_with_rejections` means accepted facts may exist, but at least one package/fact was rejected and its coverage is explicit. It never implies full document or case completeness.

### 5.3 Source-ready decision entry

Every DCP `source_fact_ready_ref` has one entry:

```json
{
  "document_ref": "brdoc_opaque",
  "next_stage_buckets": ["primary_source_extraction_refs"],
  "decision": "selected_primary",
  "reason_codes": ["source_ready_primary"],
  "issue_refs": [],
  "private_slice_refs_count": 1
}
```

Allowed decisions:

```text
selected_primary
selected_secondary
selected_duplicate_or_non_primary
deferred_context_only
blocked_with_reason
```

No source-ready ref may be absent. `deferred_context_only` and `blocked_with_reason` require safe reason codes.

### 5.4 Package policy

The run records, at minimum:

- `table_max_rows`;
- `text_max_chars`;
- `max_estimated_input_tokens`;
- `data_row_overlap=0`;
- `header_context_repeated=true`;
- `silent_truncation_forbidden=true`;
- unit ordering policy;
- model-call concurrency limit;
- selected extraction wave.

These values are configuration snapshots, not implicit defaults.

### 5.5 Structured-output policy

Required fields:

- `required_mode=json_schema`;
- `strict=true`;
- `customer_fallback=none`;
- `synthetic_json_object_fallback_allowed=false|true`;
- `max_repair_attempts=0|1`;
- `validator_is_final_authority=true`.

## 6. `broker_reports_source_fact_package_v0`

### 6.1 Visibility

The package is `private_case` and stored in `project_artifact_payload`. It must never be rendered in chat or stored in Knowledge/RAG/vector storage.

### 6.2 Required shape

```json
{
  "schema_version": "broker_reports_source_fact_package_v0",
  "package_id": "sf_pkg_opaque",
  "extraction_run_id": "sf_run_opaque",
  "normalization_run_id": "norm_run_opaque",
  "case_id": "case_opaque_or_null",
  "document_ref": "brdoc_opaque",
  "source_bucket_roles": ["primary_source_extraction_refs"],
  "document_context": {},
  "source_unit": {},
  "allowed_evidence_refs": [],
  "allowed_source_value_refs": [],
  "issue_context": [],
  "allowed_issue_refs": [],
  "forbidden_assumptions": [],
  "coverage_expectation": {},
  "prompt_contract": {},
  "output_schema": {},
  "privacy_policy": {},
  "created_at": "2026-07-10T00:00:00Z"
}
```

### 6.3 Document context

Allowed document context:

- safe document ref;
- validated passport ref and bounded metadata projection;
- DUC usage modes and readiness;
- DCP bucket roles;
- safe technical profile summary;
- duplicate group safe ref when present;
- document-level issue refs and safe descriptors.

The package builder must not re-run document identity classification. Gate 1 artifacts are authoritative.

### 6.4 Source unit

Allowed unit kinds:

```text
table_row_window
text_slice
section_slice
```

Common required fields:

- `unit_id`;
- `unit_kind`;
- `private_slice_artifact_ref`;
- `slice_ref`;
- `document_ref`;
- `source_checksum_ref`;
- `parser_ref`;
- `slice_payload_checksum_ref`;
- `coverage_ref`;
- private normalized source projection;
- `source_value_index` using payload paths plus checksums.

Table-specific fields:

- `table_ref`;
- normalized safe header descriptors;
- `row_refs`;
- `row_range_ref`;
- `cell_refs`;
- `cell_value_refs`;
- `source_value_refs`.

Text/section-specific fields:

- `text_segment_refs`;
- `section_refs` and safe section labels;
- `page_refs` / `page_range_ref` where available;
- `character_span_refs`;
- `source_value_refs`.

The private package may contain the bounded normalized values needed for extraction. Validated output may reference those values only by opaque refs; it may not copy long text or raw rows.

### 6.5 Issue context entry

```json
{
  "issue_ref": "issue_opaque",
  "issue_type": "metadata_gap",
  "status": "unresolved",
  "scope": "document",
  "impact": "limits_confirmation",
  "criticality": "clarifying",
  "affected_stage": "source_fact_extraction",
  "blocked_stages": [],
  "stages_that_may_continue": ["source_fact_extraction"],
  "evidence_refs": [],
  "reason_codes": [],
  "forbidden_assumption_codes": []
}
```

Allowed `impact` values:

```text
warning
limits_confirmation
blocks_fact
blocks_consolidation
blocks_declaration
```

Impact is assigned by deterministic code, not by the model.

### 6.6 Coverage expectation

Required fields:

- `selected_source_refs` containing row or text-segment refs;
- `ignorable_header_refs`;
- `ignorable_blank_refs`;
- `layout_candidate_refs`;
- `fact_candidate_refs`;
- `required_accounting_total`;
- `coverage_policy_id=gate2_source_unit_coverage_v0`.

Every selected non-ignorable ref must later be associated with at least one accepted fact or a typed no-fact result.

### 6.7 Prompt and schema binding

The package records:

- prompt contract id;
- managed prompt ref/command/version/hash;
- input schema version;
- output schema id/version/hash;
- model id;
- required structured-output mode.

The final prompt body is not embedded in the package or backend code.

For `package_mode=input_readiness_dry_run_no_model_call`, prompt/model/schema
runtime bindings remain explicitly unexecuted. The package must still satisfy
scope, provenance, source-value, issue, privacy and coverage validators. A
passing dry-run package is input-readiness proof, not source-fact schema/model
proof.

## 7. Raw Model Output

`broker_reports_source_fact_raw_output_v0` is private audit evidence, never a trusted fact set.

Required fields:

- run/package/document/unit refs;
- model-call status and typed error code;
- exact model output;
- structured-output mode and response-format type;
- prompt/schema/model snapshots;
- provider/profile/adapter execution metadata;
- fallback and repair metadata;
- created timestamp.

It is persisted before validation so failed outputs remain traceable under retention. Any copied private/raw content stays `private_case` and is never projected to safe/chat surfaces.

### 7.1 Provider execution metadata

Every attempted model call carries runtime-authored
`gate2_provider_execution_metadata_v1`:

```json
{
  "schema_version": "gate2_provider_execution_metadata_v1",
  "provider_id": "google",
  "provider_profile_id": "google_gemini",
  "provider_profile_revision": "sha256_hex",
  "adapter_id": "gemini_response_format",
  "adapter_version": "1.5.0",
  "requested_model_id": "models/gemini-3.5-flash",
  "resolved_model_id": "models/gemini-3.5-flash",
  "provider_response_id": "private_exact_or_null",
  "structured_output_mode": "openwebui_response_format_json_schema",
  "response_format_type": "json_schema",
  "response_format_schema_mode": "strict_json_schema",
  "transport_type": "gemini_openai_compatibility_via_openwebui",
  "canonical_request_schema_hash": "sha256_hex",
  "adapted_request_schema_hash": "sha256_hex",
  "schema_transform_count": 7,
  "duration_ms": 13208,
  "input_tokens": 16693,
  "output_tokens": 773,
  "total_tokens": 19057,
  "finish_reason": "stop"
}
```

Rules:

- `requested_model_id` is the model sent by the pipeline;
- `transport_type` is the profile-owned actual transport class; it distinguishes
  OpenWebUI OpenAI/Gemini routes from Anthropic native Messages via the
  OpenWebUI Pipe Function;
- `resolved_model_id` is populated only from the provider/OpenWebUI response and
  remains `null` when unreported;
- when `resolved_model_id` is reported, it must equal the requested exact model
  id or its version-suffixed alias; any other value terminates the attempt with
  `gate2_provider_resolved_model_mismatch` before validation/acceptance;
- token fields remain `null`, not zero, when usage is unreported;
- zero is retained when the provider explicitly reports zero;
- `duration_ms` uses a monotonic clock around the one completion call;
- `failure_class` may record a safe exception class on failed calls, while the
  exact provider exception/error stays only in the private raw payload;
- `provider_response_id` is the provider/OpenWebUI response body `id`, not an
  HTTP request-header id;
- the exact response id is private; safe metadata contains only
  `provider_response_id_present` and its SHA-256 digest;
- `canonical_request_schema_hash` identifies the contract schema before any
  provider adaptation; `adapted_request_schema_hash` identifies the schema
  actually sent through OpenWebUI;
- `schema_transform_count` is zero for pass-through adapters and counts
  adapter-owned schema rewrites. Gemini v1.3 keeps the structural JSON shape
  strict but removes provider-side dynamic constraints (`const`, source-value
  and ref enums, ranges, formats and descriptive annotations) that exceed
  Gemini's schema complexity budget. Small static semantic enums such as
  `completeness`, `confidence` and domain subtype candidates remain in the
  provider schema. The unchanged
  canonical deterministic validator enforces every removed constraint before
  any fact can persist. A conflicting `const`/`enum` pair fails before the
  completion call;
- Prompt bodies, package rows, source values, filenames, API keys, endpoints,
  and arbitrary provider response metadata are forbidden in safe projections.

This metadata is produced by the adapter/runtime. The LLM cannot supply or
override it.

Before a model result can enter the private raw artifact, the client enforces a
deterministic response budget: at most `524288` UTF-8 bytes, `20000` parsed
nodes, depth `64`, and `131072` UTF-8 bytes per string/key. An overflow stores
only a bounded length/hash diagnostic and terminates with
`gate2_model_response_budget_exceeded`; oversized model content is not persisted.

## 8. `broker_reports_source_fact_validation_v0`

### 8.1 Required shape

```json
{
  "schema_version": "broker_reports_source_fact_validation_v0",
  "validation_id": "sf_validation_opaque",
  "extraction_run_id": "sf_run_opaque",
  "package_ref": "art_opaque",
  "document_ref": "brdoc_opaque",
  "source_unit_ref": "unit_opaque",
  "raw_output_artifact_ref": "art_opaque",
  "provider_execution": {},
  "validator_status": "passed",
  "accepted_fact_ids": [],
  "rejected_fact_ids": [],
  "errors": [],
  "warnings": [],
  "coverage": {},
  "issue_carry_forward": {},
  "privacy_status": "passed",
  "boundary_status": "passed",
  "prompt_schema_model_audit": {},
  "validated_at": "2026-07-10T00:00:00Z"
}
```

Allowed `validator_status` values:

```text
passed
passed_with_warnings
failed
privacy_failed
blocked
```

Only `passed` and `passed_with_warnings` facts may enter the validated source-facts artifact. Warnings cannot waive schema, scope, provenance, value, privacy, issue, coverage, or boundary failures.

`provider_execution` in validation is the safe projection copied from the
linked raw-output attempt. It must not contain the exact provider response id or
raw provider response.

### 8.2 Required validator families

- schema/version/required/enum/format;
- run/case/document/package/unit scope;
- prompt/schema/model/response-format audit;
- ArtifactStore ref existence, ownership, lifecycle, and validation;
- evidence/source-value/issue whitelist membership;
- type-specific fields and mutual exclusions;
- deterministic normalized-value reproduction;
- no invention or unsupported high confidence;
- issue carry-forward and completeness restrictions;
- unit coverage and duplicate fact ids;
- forbidden fields/content and privacy;
- Gate 2/Gate 3 semantic boundary.

### 8.3 Minimum typed error codes

```text
source_fact_schema_mismatch
source_fact_missing_field
source_fact_unknown_field
source_fact_scope_mismatch
source_fact_unknown_evidence_ref
source_fact_unknown_value_ref
source_fact_unknown_issue_ref
source_fact_ref_cross_scope
source_fact_provenance_missing
source_fact_normalized_value_unreproducible
source_fact_invented_value
source_fact_issue_not_carried
source_fact_completeness_overstated
source_fact_coverage_gap
source_fact_duplicate_id
source_fact_private_field_forbidden
source_fact_raw_content_forbidden
source_fact_tax_conclusion_forbidden
source_fact_declaration_mapping_forbidden
source_fact_duplicate_resolution_forbidden
source_fact_prompt_audit_mismatch
source_fact_structured_output_required
source_fact_privacy_failed
```

Error subjects in safe artifacts use opaque refs or safe field paths only.

### 8.4 Repair attempts and final acceptance

A failed validation attempt may be retained as diagnostic evidence when the
same bounded package is regenerated under `repair_context`. The run is accepted
only when a later attempt persists validator-passed source facts and the domain
package, stitch result, and coverage summary are terminal `completed`.

Repair-attempt error counts do not by themselves prove final failure, but they
must remain visible in safe audit output. A run with persisted validated facts
must still prove:

- provider-native `response_format=json_schema` with strict schema mode;
- `fallback_used=false` for every raw output used in the accepted path;
- final `domain_packages.rejected=0`;
- `coverage.uncovered_total=0` and `coverage.conflict_total=0`;
- private raw output and private validated source-fact persistence;
- no Knowledge/RAG/vector/file/document-table delta.

### 8.5 Table candidate-bound provider schema

For `source_input_mode=normalized_table_projection`, the provider schema must
be projected from `deterministic_value_candidates` before the live call:

- a normalized field may contain only an exact candidate string or `null`;
- its original-value ref array may contain only refs belonging to that field's
  candidates and at most one selected ref;
- a field without a candidate is schema-bound to `null` and an empty ref array;
- multiple candidates remain model choices and are never resolved by the
  package builder;
- the post-validator still re-resolves the chosen ref and checksum and rejects
  mismatched value/ref pairs.

This is a pre-call narrowing control, not validator repair or semantic
hardcoding.

## 9. Persistence Rules

| Artifact | Default visibility | Storage backend | Validation requirement |
| --- | --- | --- | --- |
| extraction run | `safe_internal` | `project_artifact_store` | input validation before `inputs_validated` |
| input package | `private_case` | `project_artifact_payload` | validated Gate 1 refs and resolver scope |
| segmentation plan | `safe_internal` | `project_artifact_store` | exact parent-ref partition and explicit remainder status |
| selected derived source unit | `private_case` | `project_artifact_payload` | preserved provenance/checksums and complete bounded coverage |
| raw output | `private_case` | `project_artifact_payload` | model-call audit; never fact acceptance |
| validated facts | `private_case` | `project_artifact_payload` | passed source-fact validator |
| validation result | `safe_internal` | `project_artifact_store` | deterministic validator output |
| issue/fact linkage | `safe_internal` | `project_artifact_store` | opaque refs only |
| compact summary | `chat_visible` | `openwebui_chat` and/or safe store | whitelist and privacy validation |

The terminal extraction-run payload also contains
`gate2_provider_execution_summary_v1`: attempt/error/failure-class counts,
provider-profile/adapter/transport/requested/resolved-model counts, reported/unreported
usage counts, provider-reported token totals, observed latency totals/max,
adapted-schema hash counts and total schema-transform count. It contains no
provider response ids and no raw model/provider content.

Source-fact payloads default to `private_case` because amounts, dates, instruments, and transactions are sensitive. A safe-internal projection may contain ids, types, counts, statuses, and issue linkage only unless a separate field sensitivity policy proves more is safe.

No artifact may be stored in `openwebui_knowledge`.

## 10. Compact Summary Contract

`broker_reports_source_fact_extraction_summary_v0` may contain only:

- safe run ref;
- terminal status;
- documents/packages/units counts;
- fact counts by type and completeness;
- accepted/rejected/blocked counts;
- issue-linked fact counts;
- coverage summary counts;
- selected/deferred/blocked document counts by bucket;
- safe next step;
- explicit statement that no tax/declaration/XLS work was performed.

It must not contain fact values, source text/rows, filenames, file ids, private paths, document titles with private data, account/personal data, evidence payloads, secrets, or env values.

## 11. Gate 3 Handoff Rule

For a supported ready scope, Gate 3 receives one
`broker_reports_gate3_context_manifest_v0`. The manifest is produced at the
Gate 2 exit boundary, indexes the terminal ArtifactStore refs below and is
resolved under the same authorized context. A raw fact ref, DCP, run or
readiness boolean is not an alternative Gate 3 root.

Gate 2 does not emit intermediate ledger rows, consolidated facts,
case-level profit/loss, tax base, tax, declaration fields, filing status or
XLS/XLSX. Gate 3 owns case assembly/ledgers; Gate 4 owns tax/declaration/output
preparation.

## 12. Invariants

### 12.1 Domain-specific customer execution refinement

The broad `broker_reports_source_fact_package_v0` extractor remains a
compatibility/synthetic path. When the domain router and managed domain Prompts
are available, customer execution must prefer:

```text
source-unit router
  -> broker_reports_source_unit_domain_route_v0
  -> broker_reports_domain_extraction_package_v0
  -> strict domain extractor(s)
  -> unchanged source-fact validator in domain mode
  -> broker_reports_source_fact_stitch_result_v0
```

The runner deterministically owns routing, narrow provenance projection,
allowed fact types, issue whitelists, audit constants, and coverage planning.
The stitcher deterministically owns final row/segment ownership, conflicts,
unknown/no-fact reconciliation, duplicate fact ids, and final unit coverage.

A row cannot silently become multiple accepted typed facts. V0 has no
multi-fact rule; more than one validator-passed typed claim is a conflict.
`unknown_source_row` is valid coverage-preserving output. The LLM cannot change
the route, decide final ownership, consolidate documents, resolve issues, or
declare readiness.

The canonical private fact system-of-record remains
`broker_reports_source_facts_v0`; the domain wrapper and stitch result reference
it without copying private values.

### 12.2 Typed derived-unit customer path

The narrow customer runtime refines the path to:

```text
Gate2InputReadinessFactory
  -> parent Gate2SourceUnitRouterFactory
  -> Gate2SourceUnitSegmenterFactory
  -> safe segmentation plan + private selected derived unit
  -> derived Gate2SourceUnitRouterFactory
  -> Gate2DomainPackageBuilderFactory
  -> managed domain Prompt + strict JSON Schema
  -> unchanged Gate2SourceFactValidatorFactory
  -> Gate2SourceFactStitcherFactory
```

The safe segmentation plan is
`broker_reports_source_unit_segmentation_plan_v0` in
`project_artifact_store`. A selected derived unit is
`broker_reports_derived_source_unit_v0`, `private_case`, in
`project_artifact_payload`. Unselected derived units are represented as
deferred plan entries and are not sent to a model.

The compact Russian summary may state only the number of completely covered
bounded fragments and the number of incomplete parent remainders awaiting
repeat preparation. It must not expose source rows, values, names, ids, or
paths.

Primary expansion and Gate 3 input readiness require no truncated derived unit, no
truncated parent, no pending parent remainder, at least one typed validated
fact, complete conflict-free selected coverage and a valid
`broker_reports_gate3_context_manifest_v0`. Readiness applies only to the
manifest-declared scope. A successful bounded typed vertical with
`pending_gate1_reslice` does not satisfy expansion readiness.

```text
NO_SOURCE_FACT_WITHOUT_PROVENANCE
NO_MODEL_OUTPUT_WITHOUT_STRICT_VALIDATION
NO_UNRESOLVED_ISSUE_SILENTLY_RESOLVED
NO_AFFECTED_FACT_MARKED_COMPLETE
NO_SOURCE_READY_REF_SILENTLY_DROPPED
NO_SELECTED_ROW_OR_SEGMENT_SILENTLY_DROPPED
NO_ROW_OR_SEGMENT_SILENTLY_DOUBLE_CLAIMED
NO_DOMAIN_EXTRACTOR_OUTSIDE_ALLOWED_FACT_TYPES
NO_STITCH_SUCCESS_WITH_CONFLICT_OR_UNCOVERED_REF
NO_DERIVED_UNIT_WITH_UNPARTITIONED_PARENT_REFS
NO_BOUNDED_DERIVED_UNIT_CLAIMED_AS_WHOLE_DOCUMENT_COMPLETE
NO_GATE2_TAX_OR_DECLARATION_CONCLUSION
NO_CUSTOMER_OR_DERIVED_PRIVATE_ARTIFACT_IN_KNOWLEDGE_RAG
ARTIFACTSTORE_IS_SYSTEM_OF_RECORD
```

## 13. Status

```text
GATE2_SOURCE_FACT_CONTRACT_READY
GATE2_STRUCTURED_OUTPUT_INVARIANT_READY
GATE2_ISSUE_CONTEXT_CARRY_FORWARD_READY
GATE2_ARTIFACTSTORE_PLAN_READY
```

## 14. Full-source parent requirement (2026-07-10)

Gate 2 input packages MUST prefer `private_normalized_source_unit_v0` resolved
in the same user/run/case-or-chat/workspace scope. Such a package records:

- `source_input_mode=full_source_unit`;
- parent payload/unit checksum refs;
- `source_slice_truncated=false`;
- `parent_remainder_status=not_applicable_parent_complete`;
- exact selected/accounted coverage.

Legacy table/text slices may still produce a bounded proof package, but its
mode is `legacy_bounded_preview_fallback`, whole-parent coverage is false, and
limited primary expansion readiness is false. Validator, issue, privacy,
stitching and no-Gate-3 rules are unchanged.

## 15. PDF text-layer source-unit preconditions (2026-07-10)

Gate 2 may consume a PDF source unit only when the resolver proves:

- parent `private_normalized_source_payload_v0` and nested
  `pdf_text_layer_projection_v0` are complete for the declared text-layer
  projection;
- the PDF unit satisfies `private_normalized_source_unit_v0` and the PDF
  extension contract;
- source/page/payload/unit checksums reproduce;
- every selected page/block/line/word/span/value ref resolves exactly once;
- selected/accounted coverage is complete and duplicate-free;
- parent and child are untruncated with no pending remainder;
- OCR/VLM and page rendering were not used for extraction;
- Knowledge/RAG/vector guards remain false.

The model receives only a bounded page, section, line-cluster or table-candidate
projection. It never receives the whole PDF. `pdf_table_candidate_unit` remains
a geometry candidate; an ambiguous candidate routes to text/line extraction or
`unknown_source_row` without losing provenance.

Complete text-layer projection does not authorize facts derived only from
images and does not establish whole visible-document or whole-case coverage.
Existing structured-output, source-value, issue, privacy, coverage and stitch
validators remain unchanged and may not be weakened for PDF.

```text
PDF_TEXT_LAYER_GATE2_INPUT_CONTRACT_READY
PDF_TEXT_LAYER_GATE2_INPUT_READINESS_NO_MODEL_PASSED
PDF_TEXT_LAYER_SOURCE_FACT_MODEL_RUNTIME_NOT_EXECUTED
```

## 16. PDF layout unit input readiness (2026-07-10)

The no-model readiness builder now validates and copies only bounded layout
refs, values, exact unit coverage and non-semantic candidate metadata from
ArtifactStore. It accepts `pdf_line_cluster_unit` and
`pdf_table_candidate_unit`, sets whole-parent coverage false and leaves the
store unchanged. This proves input readiness, not source-fact model output.

```text
PDF_GATE2_LAYOUT_INPUT_READINESS_DRY_RUN_PASSED
PDF_LAYOUT_SOURCE_FACT_MODEL_RUNTIME_NOT_EXECUTED
```

## 17. Bounded normalized-table input (2026-07-11)

The no-model readiness path may explicitly select `broker_reports_normalized_table_projection_v0` by setting `prefer_table_projections=True`. `Gate2TablePackageFactory` supplies bounded rows, repeated headers, cells, source-value refs, issues, structural quality and PDF fallback metadata; whole PDFs/pages are excluded. The router classifies later rows/facts, not table geometry. Default model-runtime selection remains the prior full-source path until the table-domain extraction slice is separately authorized.

## 18. Cross-domain candidate-binding mode (2026-07-11)

`candidate_binding_enabled=True` is an explicit package/runtime opt-in. It adds
the private candidate set, relation set and domain profile contracts, then
replaces only the model-facing source-facts proposal with
`broker_reports_candidate_binding_output_v0`. Candidate ids, relation ids and
role/path triples are exact package-bound provider-schema variants. Raw values
are not model output.

The generic binding validator first verifies set identity, candidate scope,
source-value/checksum reproduction, domain/role/field policy, ambiguity,
reuse, relations, issues and complete selected-ref accounting. Only a passed
selection is materialized and sent through the existing domain finalizer,
unchanged strict source-fact validator and stitcher. Repair receives the same
set/profile/relation identities. Legacy packages without the mode stay on the
compatibility source-facts path; no persisted artifact is reinterpreted or
mutated.

Normative intermediate contracts:

- [source value candidates](./BROKER_REPORTS_GATE2_SOURCE_VALUE_CANDIDATES.v0.md);
- [candidate relations](./BROKER_REPORTS_GATE2_CANDIDATE_RELATIONS.v0.md);
- [domain binding profiles](./BROKER_REPORTS_GATE2_DOMAIN_BINDING_PROFILES.v0.md);
- [candidate-binding output](./BROKER_REPORTS_GATE2_CANDIDATE_BINDING_OUTPUT.v0.md).
