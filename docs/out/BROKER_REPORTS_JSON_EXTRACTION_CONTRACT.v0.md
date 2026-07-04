# Broker Reports JSON Extraction Contract v0

Status: Draft contract for proof
Schema version: `broker_reports_extraction_v0`
Scope: broker document intake, classification, JSON extraction, manual review
Out of scope: XLS/XLSX generation, final 3-НДФЛ, FNS submission, tax correctness guarantee

## 1. Purpose

This contract defines the JSON shape for the first Broker Reports Document Intake + JSON Extraction MVP proof.

The goal is not to prepare a declaration. The goal is to test whether an OpenWebUI-first, schema-first flow can classify user documents, extract tax-relevant facts, attach evidence, surface missing and uncertain data, detect conflicts and prepare questions for a specialist.

## 2. Top-Level Shape

Every model output must be one JSON object:

```json
{
  "schema_version": "broker_reports_extraction_v0",
  "run_summary": {},
  "document_manifest": [],
  "document_quality_summary": {},
  "extracted_tax_facts": {},
  "aggregates": {},
  "missing_data": [],
  "uncertain_data": [],
  "conflicts": [],
  "questions_to_specialist": [],
  "readiness": {},
  "manual_review_warning": ""
}
```

Rules:

- `schema_version` must equal `broker_reports_extraction_v0`.
- All top-level keys are required.
- Empty data uses empty arrays, empty objects or `null`, not omitted keys.
- The result must be valid JSON with no Markdown fences or surrounding prose.
- Any fact without a source wrapper must not be counted as extracted.
- Manual review is mandatory for every run.

## 3. Document Manifest

`document_manifest` is the first acceptance surface. It must describe every input item, including unsupported and unreadable inputs.

Each item:

```json
{
  "document_id": "doc_001",
  "filename": "synthetic_broker_report_text_ru.txt",
  "container_format": "txt",
  "content_representation": "text_layer",
  "detected_document_type": "broker_report",
  "readability_status": "readable",
  "processing_mode": "prompt_only_context",
  "pages_count": null,
  "sheets_count": null,
  "tables_detected": 1,
  "requires_manual_review": true,
  "limitations": [],
  "confidence": "medium"
}
```

Allowed `container_format`:

- `pdf`
- `xls`
- `xlsx`
- `csv`
- `xml`
- `txt`
- `image`
- `pasted_text`
- `unknown`

Allowed `content_representation`:

- `text_layer`
- `machine_readable_table`
- `raster_scan`
- `photo`
- `mixed_text_and_raster`
- `pasted_text`
- `unknown`

Allowed `detected_document_type`:

- `broker_report`
- `operations_table`
- `dividends_report`
- `tax_withholding_report`
- `cashflow_report`
- `positions_report`
- `fees_report`
- `unknown`
- `unsupported`

Allowed `readability_status`:

- `readable`
- `partially_readable`
- `not_readable`
- `unknown`

Allowed `processing_mode`:

- `native_text_extraction`
- `native_table_extraction`
- `vision_llm_experimental`
- `prompt_only_context`
- `unsupported`
- `failed`

Allowed `confidence`:

- `high`
- `medium`
- `low`
- `not_available`

Raster and photo documents must not masquerade as text-layer PDFs. They must use `raster_scan`, `photo` or `mixed_text_and_raster` and must set `requires_manual_review: true`.

## 4. Evidence Wrapper

Every tax-relevant value uses this wrapper:

```json
{
  "field": "field_name",
  "value": null,
  "currency": null,
  "status": "missing",
  "confidence": "not_available",
  "source": {
    "document_id": "doc_001",
    "container_format": "pdf",
    "content_representation": "text_layer",
    "page": null,
    "sheet": null,
    "row": null,
    "column": null,
    "section": null,
    "source_type": "text_layer",
    "excerpt_or_visible_label": null,
    "exact_text_layer_available": true
  },
  "needs_manual_review": true,
  "notes": null
}
```

Allowed `status`:

- `extracted`: value is found and has usable source evidence.
- `missing`: required value is not found.
- `uncertain`: value is found but weak, ambiguous or low-confidence.
- `conflict`: two or more sources disagree.
- `not_applicable`: the field is not applicable for the document/run.

Allowed `source.source_type`:

- `text_layer`
- `table_cell`
- `vision_read`
- `user_pasted_text`
- `inferred`

Important distinction:

- "Not found" means `status: "missing"`.
- "Found but not confident" means `status: "uncertain"`.
- "Contradictory sources" means `status: "conflict"` and a conflict record.
- "Not relevant for this document/run" means `status: "not_applicable"`.
- "Model guesses without a source" must use `source_type: "inferred"` and must not be treated as extracted.

## 5. Suggested Extracted Facts

The first proof should keep fields limited. The exact tax methodology is customer-owned and must not be invented.

Suggested `extracted_tax_facts` shape:

```json
{
  "taxpayer": {
    "name": {},
    "tax_identifier": {},
    "broker_account_id": {}
  },
  "broker": {
    "broker_name": {},
    "report_period": {},
    "report_currency": {}
  },
  "operations": {
    "sales_total": {},
    "purchases_total": {},
    "fees_total": {},
    "dividends_total": {},
    "tax_withheld_total": {},
    "foreign_tax_withheld_total": {}
  },
  "documents": {
    "has_operations_table": {},
    "has_dividends_section": {},
    "has_tax_withholding_section": {}
  }
}
```

Each leaf value must be an evidence wrapper.

## 6. Aggregates

`aggregates` are derived summaries. They must reference source fields, not free-form guesses.

```json
{
  "by_currency": [],
  "by_income_type": [],
  "by_document": [],
  "calculation_limitations": []
}
```

If a numeric aggregate is not calculated by deterministic code, mark it with `confidence: "low"` or put it into `uncertain_data`.

## 7. Missing, Uncertain, Conflicts, Questions

`missing_data` item:

```json
{
  "field": "taxpayer.tax_identifier",
  "reason": "Required for downstream review but not present in provided documents.",
  "blocking": true,
  "question_id": "q_001"
}
```

`uncertain_data` item:

```json
{
  "field": "operations.tax_withheld_total",
  "candidate_values": [],
  "reason": "Value visible only in raster/vision path or ambiguous table label.",
  "source_refs": [],
  "needs_manual_review": true
}
```

`conflicts` item:

```json
{
  "field": "broker.report_period",
  "values": [],
  "source_refs": [],
  "resolution_status": "needs_specialist"
}
```

`questions_to_specialist` item:

```json
{
  "question_id": "q_001",
  "priority": "high",
  "question": "Please provide the taxpayer identifier or confirm that it is intentionally omitted from this proof.",
  "related_fields": ["taxpayer.tax_identifier"],
  "blocking_readiness": true
}
```

## 8. Readiness

`readiness` must not claim final tax readiness.

```json
{
  "status": "not_ready",
  "blocking_reasons": [],
  "manual_review_required": true,
  "can_proceed_to_xls_stage": false,
  "raster_extraction_present": false,
  "tax_correctness_claimed": false,
  "fns_filing_claimed": false
}
```

Allowed `readiness.status`:

- `ready_for_specialist_review`
- `needs_more_data`
- `not_ready`
- `failed`

`can_proceed_to_xls_stage` is only a proof signal. It does not authorize XLS/XLSX generation in this task.

## 9. JSON Schema Draft

This schema is intentionally compact for proof v0. Production should generate schema from typed contracts to avoid drift.

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "BrokerReportsExtractionV0",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "schema_version",
    "run_summary",
    "document_manifest",
    "document_quality_summary",
    "extracted_tax_facts",
    "aggregates",
    "missing_data",
    "uncertain_data",
    "conflicts",
    "questions_to_specialist",
    "readiness",
    "manual_review_warning"
  ],
  "properties": {
    "schema_version": {
      "const": "broker_reports_extraction_v0"
    },
    "run_summary": {
      "type": "object"
    },
    "document_manifest": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": [
          "document_id",
          "filename",
          "container_format",
          "content_representation",
          "detected_document_type",
          "readability_status",
          "processing_mode",
          "pages_count",
          "sheets_count",
          "tables_detected",
          "requires_manual_review",
          "limitations",
          "confidence"
        ],
        "properties": {
          "document_id": { "type": "string" },
          "filename": { "type": "string" },
          "container_format": { "enum": ["pdf", "xls", "xlsx", "csv", "xml", "txt", "image", "pasted_text", "unknown"] },
          "content_representation": { "enum": ["text_layer", "machine_readable_table", "raster_scan", "photo", "mixed_text_and_raster", "pasted_text", "unknown"] },
          "detected_document_type": { "enum": ["broker_report", "operations_table", "dividends_report", "tax_withholding_report", "cashflow_report", "positions_report", "fees_report", "unknown", "unsupported"] },
          "readability_status": { "enum": ["readable", "partially_readable", "not_readable", "unknown"] },
          "processing_mode": { "enum": ["native_text_extraction", "native_table_extraction", "vision_llm_experimental", "prompt_only_context", "unsupported", "failed"] },
          "pages_count": { "type": ["integer", "null"], "minimum": 0 },
          "sheets_count": { "type": ["integer", "null"], "minimum": 0 },
          "tables_detected": { "type": ["integer", "null"], "minimum": 0 },
          "requires_manual_review": { "type": "boolean" },
          "limitations": { "type": "array", "items": { "type": "string" } },
          "confidence": { "enum": ["high", "medium", "low", "not_available"] }
        }
      }
    },
    "document_quality_summary": { "type": "object" },
    "extracted_tax_facts": { "type": "object" },
    "aggregates": { "type": "object" },
    "missing_data": { "type": "array" },
    "uncertain_data": { "type": "array" },
    "conflicts": { "type": "array" },
    "questions_to_specialist": { "type": "array" },
    "readiness": {
      "type": "object",
      "required": [
        "status",
        "blocking_reasons",
        "manual_review_required",
        "can_proceed_to_xls_stage",
        "raster_extraction_present",
        "tax_correctness_claimed",
        "fns_filing_claimed"
      ],
      "properties": {
        "status": { "enum": ["ready_for_specialist_review", "needs_more_data", "not_ready", "failed"] },
        "blocking_reasons": { "type": "array", "items": { "type": "string" } },
        "manual_review_required": { "const": true },
        "can_proceed_to_xls_stage": { "type": "boolean" },
        "raster_extraction_present": { "type": "boolean" },
        "tax_correctness_claimed": { "const": false },
        "fns_filing_claimed": { "const": false }
      }
    },
    "manual_review_warning": {
      "type": "string",
      "minLength": 1
    }
  }
}
```

## 10. Minimal Valid Example

```json
{
  "schema_version": "broker_reports_extraction_v0",
  "run_summary": {
    "input_count": 1,
    "proof_mode": "synthetic_prompt_only"
  },
  "document_manifest": [
    {
      "document_id": "doc_001",
      "filename": "synthetic_broker_report_text_ru.txt",
      "container_format": "txt",
      "content_representation": "text_layer",
      "detected_document_type": "broker_report",
      "readability_status": "readable",
      "processing_mode": "prompt_only_context",
      "pages_count": null,
      "sheets_count": null,
      "tables_detected": 1,
      "requires_manual_review": true,
      "limitations": ["Synthetic proof input; not customer data."],
      "confidence": "medium"
    }
  ],
  "document_quality_summary": {
    "all_documents_require_manual_review": true,
    "raster_documents_present": false
  },
  "extracted_tax_facts": {},
  "aggregates": {
    "by_currency": [],
    "by_income_type": [],
    "by_document": [],
    "calculation_limitations": ["No deterministic tax calculation in v0 proof."]
  },
  "missing_data": [
    {
      "field": "taxpayer.tax_identifier",
      "reason": "Not present in synthetic input.",
      "blocking": true,
      "question_id": "q_001"
    }
  ],
  "uncertain_data": [],
  "conflicts": [],
  "questions_to_specialist": [
    {
      "question_id": "q_001",
      "priority": "high",
      "question": "Provide the taxpayer identifier or confirm it is intentionally omitted from the synthetic proof.",
      "related_fields": ["taxpayer.tax_identifier"],
      "blocking_readiness": true
    }
  ],
  "readiness": {
    "status": "needs_more_data",
    "blocking_reasons": ["taxpayer.tax_identifier missing"],
    "manual_review_required": true,
    "can_proceed_to_xls_stage": false,
    "raster_extraction_present": false,
    "tax_correctness_claimed": false,
    "fns_filing_claimed": false
  },
  "manual_review_warning": "Synthetic JSON extraction output only. Manual specialist review is mandatory. No final tax correctness or FNS filing is claimed."
}
```

## 11. Acceptance Notes

For proof v0, success means:

- JSON parses.
- Required top-level keys are present.
- Every input document appears in `document_manifest`.
- Missing, uncertain and conflict states are explicit.
- Raster/vision-derived values, if any, are marked experimental and manual-review-only.
- The output never claims final tax correctness, final 3-НДФЛ generation or FNS filing.

Full JSON Schema validation is recommended as a next proof step. It was not implemented as production code in this task.
