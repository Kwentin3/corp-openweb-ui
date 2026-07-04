# Broker Reports JSON Extraction Prompt Pack

Status: Draft prompts, not loaded
Date: 2026-07-04
Target: OpenWebUI Prompts / slash commands after human review
Contract: `broker_reports_extraction_v0`

## 1. Safety Frame For All Prompts

Every prompt must preserve these rules:

- JSON extraction only.
- Manual specialist review is mandatory.
- Do not claim final tax correctness.
- Do not generate or promise final 3-NDFL.
- Do not claim FNS filing/submission.
- Do not generate XLS/XLSX in this stage.
- Do not use unsupported raster/photo inputs as production OCR.
- Do not invent missing data or methodology.
- Use customer methodology only when approved and present.

## 2. `/broker_intake`

Purpose:

- start a broker reports JSON extraction run;
- collect document list, target period and user intent.

Input requirements:

- user-provided list of attached/pasted documents;
- declared target period if known;
- confirmation that files are synthetic or approved customer-anonymized samples.

Expected output:

- short intake summary;
- document list;
- missing setup questions;
- no JSON extraction yet unless user asks to proceed.

JSON contract section:

- preparation for `document_manifest` and `run_summary`.

Safety warning:

- "This workflow produces JSON extraction for specialist review only."

Failure behavior:

- if user provides real personal/customer documents without approved policy, stop and request approved transfer/anonymization path.

## 3. `/broker_classify_documents`

Purpose:

- classify every input document.

Input requirements:

- filenames/source labels;
- visible text or file processing notes;
- available page/sheet/table information.

Expected output:

- `document_manifest` draft for every input;
- readability and processing-mode notes.

JSON contract section:

- `document_manifest`;
- `document_quality_summary`.

Safety warning:

- unsupported and unreadable documents must still be listed.

Failure behavior:

- if document content is inaccessible, mark `readability_status = "unknown"` or `not_readable` and ask for a text-readable copy.

## 4. `/broker_extract_json`

Purpose:

- produce the full `broker_reports_extraction_v0` JSON output.

Input requirements:

- classified documents;
- extracted text/table context;
- approved methodology if available;
- instruction to return JSON only.

Expected output:

- one valid JSON object;
- all required top-level keys;
- evidence wrapper for every tax-relevant value.

JSON contract section:

- all sections.

Safety warning:

- no Markdown fences, no prose around JSON, no final tax correctness claim.

Failure behavior:

- if required data is unavailable, use `missing_data`, `uncertain_data`, `questions_to_specialist` and `readiness.status`.

## 5. `/broker_find_missing_data`

Purpose:

- identify gaps in an extraction result.

Input requirements:

- current JSON result;
- customer required-field list if available.

Expected output:

- `missing_data` items;
- linked `questions_to_specialist`;
- blocking/non-blocking status.

JSON contract section:

- `missing_data`;
- `questions_to_specialist`;
- `readiness`.

Safety warning:

- do not fill missing fields from assumptions.

Failure behavior:

- if required-field list is absent, mark rule as `requires_customer_methodology`.

## 6. `/broker_detect_conflicts`

Purpose:

- compare values across documents and sections.

Input requirements:

- JSON result;
- source refs;
- document list.

Expected output:

- `conflicts` list with field, values, source refs and resolution status;
- related specialist questions.

JSON contract section:

- `conflicts`;
- `questions_to_specialist`;
- `readiness.blocking_reasons`.

Safety warning:

- do not silently choose a winner without approved source-precedence rules.

Failure behavior:

- if no precedence methodology exists, leave conflict unresolved.

## 7. `/broker_questions_to_specialist`

Purpose:

- generate concise questions for human review.

Input requirements:

- `missing_data`;
- `uncertain_data`;
- `conflicts`;
- customer required-field list if available.

Expected output:

- prioritized `questions_to_specialist`;
- no duplicate/low-value questions.

JSON contract section:

- `questions_to_specialist`.

Safety warning:

- questions must not ask the specialist to validate hallucinated data.

Failure behavior:

- if a question depends on missing methodology, include `requires_customer_methodology`.

## 8. `/broker_readiness_check`

Purpose:

- decide whether a JSON extraction result is ready for specialist review.

Input requirements:

- full JSON result;
- validation errors if any;
- customer proof gate if available.

Expected output:

- `readiness.status`;
- `blocking_reasons`;
- manual review warning check;
- next-step recommendation.

JSON contract section:

- `readiness`;
- `manual_review_warning`.

Safety warning:

- readiness is not tax correctness and not filing readiness.

Failure behavior:

- if JSON is invalid or safety invariants fail, return `failed` or `not_ready`.

## 9. `/broker_raster_extraction_experiment`

Purpose:

- run Track B experimental raster/vision behavior only when approved.

Input requirements:

- synthetic raster/image input;
- explicit statement that runtime supports vision input;
- no real customer documents.

Expected output:

- manifest classification as raster/photo/mixed;
- low-trust or unsupported extraction;
- manual review required;
- missing/uncertain values instead of invented facts.

JSON contract section:

- `document_manifest`;
- `uncertain_data`;
- `missing_data`;
- `readiness`.

Safety warning:

- not production OCR support.

Failure behavior:

- if vision is unavailable, classify as unsupported and do not extract values.

## 10. Prompt Load Gate

Do not load these prompts into OpenWebUI until:

- human review approves wording;
- source registry is approved;
- data policy is approved for the intended model/provider path;
- staging Workspace Model is selected;
- synthetic prompt proof is scheduled.
