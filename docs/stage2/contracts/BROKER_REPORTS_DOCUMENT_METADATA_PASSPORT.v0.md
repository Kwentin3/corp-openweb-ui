# Broker Reports Document Metadata Passport Contract v0

Status:

- DOCUMENT_METADATA_PASSPORT_CONTRACT_READY

Date: 2026-07-08

Scope: safe metadata-only contract for LLM-assisted Broker Reports Gate 1 / Gate 1.5 document passport.

This contract does not allow source-fact extraction, tax calculation, declaration generation, XLS/XLSX export, OCR/VLM, Knowledge loading or ordinary OpenWebUI upload. It does not allow raw rows, full source text, raw filenames, file ids, private paths, names, account numbers, secrets or env values in safe surfaces.

## 1. Contract Name

```text
document_metadata_passport_v0
```

The passport describes what a document appears to be and whether its metadata is sufficient for source eligibility review. It is not a source-fact artifact and is not tax evidence by itself.

## 2. Ownership

Producer:

```text
Broker Reports Gate 1 LLM passport stage
```

Validator:

```text
Broker Reports Gate 1 validator
```

Consumer:

```text
source eligibility v2
```

Gate 2 may receive only validated safe refs and selected metadata. Gate 2 must still resolve private slices through ArtifactStore and must not parse chat JSON.

## 3. Required Top-Level Shape

```json
{
  "schema_version": "document_metadata_passport_v0",
  "passport_id": "passport_opaque",
  "normalization_run_id": "normrun_opaque",
  "case_group_id": "case_group_opaque",
  "document_id": "brdoc_opaque",
  "source_file_ref": {
    "provider": "openwebui",
    "safe_ref": "source_ref_opaque"
  },
  "passport_status": "validated",
  "document_title_candidate": null,
  "document_kind_candidate": null,
  "broker_name_candidate": null,
  "client_name_candidate": null,
  "account_or_contract_candidate": null,
  "report_period_start": null,
  "report_period_end": null,
  "tax_year_candidate": null,
  "created_at_candidate": null,
  "document_language": null,
  "document_format": null,
  "container_format": null,
  "content_kind": null,
  "sections_detected": [],
  "tables_detected": [],
  "operation_sections_detected": [],
  "cashflow_sections_detected": [],
  "income_sections_detected": [],
  "withholding_sections_detected": [],
  "tax_sections_detected": [],
  "role_hypotheses": [],
  "source_candidate_confidence": "none",
  "metadata_confidence": "none",
  "evidence_refs": [],
  "missing_metadata_fields": [],
  "conflict_flags": [],
  "review_required": true,
  "llm_prompt_ref": "prompt_opaque",
  "llm_prompt_command": null,
  "llm_prompt_version": null,
  "llm_prompt_hash": "sha256_hex",
  "llm_model_id": "model_opaque",
  "llm_input_refs": [],
  "validator_status": "pending",
  "validator_errors": [],
  "created_at": "2026-07-08T00:00:00Z"
}
```

The example is structural only. It intentionally contains no real customer metadata.

## 4. Field Requirements

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `schema_version` | string | yes | Exact `document_metadata_passport_v0`. |
| `passport_id` | string | yes | Opaque id. |
| `normalization_run_id` | string | yes | Must match current run. |
| `case_group_id` | string/null | yes | Required for customer-approved cases. |
| `document_id` | string | yes | Must match document inventory. |
| `source_file_ref` | object | yes | Safe opaque source ref only. |
| `passport_status` | enum | yes | `draft`, `validated`, `blocked`, `privacy_failed`. |
| `document_title_candidate` | string/null | yes | Safe short title candidate; no raw filename. |
| `document_kind_candidate` | enum/null | yes | See section 5. |
| `broker_name_candidate` | string/null | yes | Candidate only; validator may redact or hash in safe reports. |
| `client_name_candidate` | string/null | yes | Candidate only; never printed in chat. |
| `account_or_contract_candidate` | string/null | yes | Candidate only; never printed in chat. |
| `report_period_start` | date/null | yes | ISO date or null. |
| `report_period_end` | date/null | yes | ISO date or null. |
| `tax_year_candidate` | integer/null | yes | Candidate year, not a tax decision. |
| `created_at_candidate` | date/null | yes | Document creation/report date if visible. |
| `document_language` | enum/null | yes | Example: `ru`, `en`, `mixed`, `unknown`. |
| `document_format` | enum/null | yes | Human-readable document format candidate. |
| `container_format` | enum/null | yes | Must align with technical profile. |
| `content_kind` | enum/null | yes | See section 5. |
| `sections_detected` | array | yes | Section labels with evidence refs. |
| `tables_detected` | array | yes | Table descriptors, no raw rows. |
| `role_hypotheses` | array | yes | Ordered hypotheses with confidence and evidence refs. |
| `source_candidate_confidence` | enum | yes | `none`, `low`, `medium`, `high`. |
| `metadata_confidence` | enum | yes | `none`, `low`, `medium`, `high`. |
| `evidence_refs` | array | yes | Opaque refs only. |
| `missing_metadata_fields` | array | yes | Required when fields are null. |
| `conflict_flags` | array | yes | Explicit uncertainty/conflicts. |
| `review_required` | boolean | yes | True when evidence is incomplete or conflicts exist. |
| `llm_prompt_ref` | string | yes | OpenWebUI Prompt id or opaque ref. |
| `llm_prompt_command` | string/null | yes | Optional command for audit. |
| `llm_prompt_version` | string/null | yes | OpenWebUI version id if available. |
| `llm_prompt_hash` | string | yes | SHA-256 hex. |
| `llm_model_id` | string | yes | Safe model identifier. |
| `llm_input_refs` | array | yes | Private input package refs. |
| `validator_status` | enum | yes | `pending`, `passed`, `failed`, `privacy_failed`. |
| `validator_errors` | array | yes | Safe error codes only. |
| `created_at` | datetime | yes | UTC timestamp. |

## 5. Enumerations

Allowed `document_kind_candidate` values:

```text
broker_activity_statement
broker_annual_report
broker_tax_report
dividend_report
withholding_report
fees_report
cashflow_report
operations_table
currency_rate_table
methodology_document
calculation_template
tax_output_or_declaration_artifact
official_form
duplicate_or_cover
unknown
```

Allowed `content_kind` values:

```text
source_report_candidate
methodology_or_reference
output_or_calculation_artifact
duplicate_candidate
outside_case_scope
unsupported_or_unreadable
unknown
```

Allowed confidence values:

```text
none
low
medium
high
```

Allowed `passport_status` values:

```text
draft
validated
blocked
privacy_failed
```

## 6. Section Descriptor Shape

Each item in a section array should use:

```json
{
  "label": "operations",
  "normalized_label": "operations",
  "present": true,
  "confidence": "medium",
  "evidence_refs": ["slice_ref_opaque"]
}
```

Allowed normalized labels:

```text
summary
account_information
report_period
positions
operations
trades
cashflow
dividends
coupons
interest
fees
withholding
tax
currency
other_income
unknown
```

Section labels must be short and must not copy full source headings if those headings contain private identifiers.

## 7. Table Descriptor Shape

Each item in `tables_detected` should use:

```json
{
  "table_ref": "table_ref_opaque",
  "normalized_label": "operations",
  "header_signals": ["date", "amount", "currency"],
  "rows_count_bucket": "present",
  "confidence": "medium",
  "evidence_refs": ["table_slice_ref_opaque"]
}
```

`header_signals` are normalized safe labels, not raw customer headers when headers contain private identifiers.

Allowed `rows_count_bucket`:

```text
none
present
many
unknown
```

## 8. Role Hypothesis Shape

Each item in `role_hypotheses` should use:

```json
{
  "role": "source_broker_report",
  "confidence": "medium",
  "reason_codes": ["broker_report_metadata_present"],
  "evidence_refs": ["slice_ref_opaque"],
  "source_policy_effect": "requires_policy_review"
}
```

Allowed roles:

```text
source_broker_report
source_operations_table
source_dividend_report
source_withholding_report
source_cashflow_report
methodology_or_reference
calculation_or_output_artifact
official_form_or_declaration
duplicate_candidate
outside_case_scope
unknown
```

Allowed `source_policy_effect`:

```text
accepted_candidate_if_policy_allows
requires_policy_review
metadata_review_required
excluded_from_gate2
no_effect
```

## 9. Evidence Ref Rules

Evidence refs must be opaque refs to current-run artifacts:

- document inventory safe ref;
- technical profile safe ref;
- private text slice ref;
- private table slice ref;
- LLM package section ref.

Evidence refs must not contain:

- raw filenames;
- raw OpenWebUI file ids;
- private filesystem paths;
- raw text;
- raw table rows;
- account numbers or personal identifiers.

The validator must reject unknown refs and refs from another document, run, case or user context.

## 10. Validator Rules

The validator must:

1. Require exact schema version.
2. Require all top-level fields, even when values are null.
3. Require same run/document/case scope as the current Gate 1 package.
4. Require prompt ref/version/hash/model id.
5. Verify `llm_prompt_hash` is 64-char lowercase SHA-256 hex.
6. Verify date and datetime formats.
7. Verify enums.
8. Verify evidence refs exist and belong to the same run/document.
9. Reject forbidden field names: `raw_text`, `raw_rows`, `rows`, `content`, `path`, `filename`, `file_id`, `private_ref`.
10. Reject long copied text fragments in candidate strings.
11. Require `missing_metadata_fields` for null critical metadata.
12. Require `review_required=true` when conflicts or missing critical fields exist.
13. Require `source_candidate_confidence` not to be `high` without evidence refs.
14. Keep safety flags false for source facts, tax, declaration, XLS/XLSX, OCR/VLM and Knowledge.

## 11. Critical Metadata Fields

Critical fields for source eligibility:

```text
document_kind_candidate
broker_name_candidate
account_or_contract_candidate
report_period_start
report_period_end
content_kind
sections_detected
role_hypotheses
evidence_refs
```

`client_name_candidate` can be null if provider/privacy policy requires redaction, but the passport must then add a safe missing/conflict flag.

## 12. Source Eligibility Mapping

Eligibility v2 may use a validated passport as follows:

| Passport condition | Eligibility effect |
| --- | --- |
| validated source report, required metadata present, policy allows | `accepted_for_gate2` or `accepted_as_source_candidate_for_gate2` |
| validated source report, source policy not explicit | `source_policy_review_required` |
| source role plausible but critical metadata missing | `metadata_review_required` |
| methodology/reference/output content kind | `methodology_or_output_artifact` |
| duplicate candidate | `duplicate_needs_canonical_choice` |
| validator failed | `metadata_review_required` or blocker |
| privacy failed | blocks safe report publication |

`source_candidate_confidence` alone never grants Gate 2 eligibility.

## 13. ArtifactStore Placement

Recommended storage:

| Payload | Artifact type | Visibility | Storage |
| --- | --- | --- | --- |
| LLM input package | `llm_document_package_v0` | `private_case` | `project_artifact_payload` |
| Raw LLM JSON | `llm_passport_raw_output_v0` | `private_case` | `project_artifact_payload` |
| Validated passport | `document_metadata_passport_v0` | `safe_internal` | `project_artifact_store` |
| Validation result | `document_metadata_passport_validation_v0` | `safe_internal` | `project_artifact_store` |

The chat-visible report may include only aggregate passport status counts and safe next-step wording.

## 14. Status

```text
DOCUMENT_METADATA_PASSPORT_CONTRACT_READY
```
