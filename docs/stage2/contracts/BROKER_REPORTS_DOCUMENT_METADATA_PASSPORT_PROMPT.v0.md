# Broker Reports Document Metadata Passport Prompt Contract v0

Status:

- DOCUMENT_METADATA_PASSPORT_PROMPT_CONTRACT_READY

Date: 2026-07-08

Scope: managed OpenWebUI Prompt contract for the Broker Reports Gate 1 / Gate 1.5 LLM document metadata passport stage.

This is a prompt contract and reference managed-prompt content. It is not backend Python code. The final prompt body must be stored and versioned as an OpenWebUI Prompt, not hardcoded in the Pipe/backend.

## 1. Prompt Identity

Recommended OpenWebUI Prompt:

```text
name: Broker Reports Document Metadata Passport
command: /broker_gate1_document_passport
tags:
  - broker-reports-gate1
  - document-metadata-passport
  - managed-prompt
```

Required `meta`:

```json
{
  "template_kind": "document_metadata_passport",
  "template_id": "broker_reports.document_metadata_passport.v0",
  "prompt_contract_id": "broker_reports_document_metadata_passport_prompt_v0",
  "input_contract": "broker_reports_llm_document_package_v0",
  "output_schema_version": "document_metadata_passport_v0",
  "gate": "gate1_5",
  "forbidden_tasks": [
    "source_fact_extraction",
    "tax_calculation",
    "declaration_generation",
    "xlsx_generation",
    "ocr_vlm",
    "knowledge_loading"
  ]
}
```

Access:

- visible only to approved Broker Reports operator/admin group;
- not public;
- changes require commit message;
- prompt body must contain no secrets and no customer raw data.

## 2. Runtime Binding

Backend/Pipe config may store:

```text
prompt_id
prompt_command
expected_template_id
expected_output_schema_version
passport_model_id
```

Backend/Pipe config must not store the final prompt body.

At runtime, Gate 1 records:

```text
llm_prompt_ref
llm_prompt_command
llm_prompt_version
llm_prompt_hash
llm_model_id
llm_input_refs
output_schema_version
```

## 3. Input Variable

The managed prompt should have one backend-filled input variable:

```text
{{document_package_json}}
```

The variable value must be a private `broker_reports_llm_document_package_v0` package prepared by Gate 1. It must not be user-typed free text and must not be sourced from ordinary OpenWebUI Knowledge/RAG context.

## 4. Required Model Behavior

The model must:

- output strict JSON only;
- use exactly `document_metadata_passport_v0`;
- use only provided package content and evidence refs;
- set unknown fields to `null`;
- report missing fields in `missing_metadata_fields`;
- include evidence refs for every non-null candidate;
- separate document kind from source eligibility hypothesis;
- set `review_required=true` when evidence is incomplete, conflicting or weak;
- avoid copying raw rows/full text into output;
- avoid transaction-level facts;
- avoid tax correctness conclusions.

## 5. Forbidden Model Behavior

The model must not:

- extract trades, dividends, coupons, operations or cash movements as source facts;
- calculate tax;
- judge final tax correctness;
- fill declaration fields;
- generate XLS/XLSX rows;
- do OCR/VLM or infer from images;
- use external knowledge, memory or assumptions outside the provided package;
- invent missing broker/client/account/period values;
- output raw rows or full source text;
- output raw filenames, OpenWebUI file ids, private paths, names, account numbers, secrets or env values;
- load or recommend loading customer documents into Knowledge.

## 6. Reference Prompt Content

The following content is intended to be stored as the OpenWebUI Prompt body. It is included here as a contract reference for operators and implementation tests, not as Python code.

```text
You are the Broker Reports Gate 1 document metadata passport classifier.

Task:
Create a metadata-only passport for one normalized broker-report candidate document.

Input:
You receive one JSON object named broker_reports_llm_document_package_v0.
Use only this JSON object. Do not use external memory, web search, hidden context, OpenWebUI Knowledge, or assumptions outside the package.

Boundary:
This is Gate 1 / Gate 1.5 metadata classification only.
Do not extract source facts.
Do not extract transactions as facts.
Do not calculate tax.
Do not judge tax correctness.
Do not fill a declaration.
Do not generate XLS/XLSX.
Do not do OCR/VLM.
Do not output raw rows, full source text, raw filenames, OpenWebUI file ids, private paths, names, account numbers, secrets or env values.

Output:
Return strict JSON only.
Return exactly one document_metadata_passport_v0 object.
Do not wrap JSON in markdown.
Do not add comments.

Rules:
1. If a field is not supported by evidence, set it to null.
2. For every non-null metadata candidate, include evidence_refs.
3. Evidence refs must be copied only from the provided package refs.
4. Never copy source rows or long source text into the output.
5. Use confidence values only from: none, low, medium, high.
6. Separate document_kind_candidate from source eligibility. You may propose role_hypotheses, but final eligibility is decided by the validator and source eligibility v2.
7. If required metadata is missing or conflicting, set review_required=true and list missing_metadata_fields or conflict_flags.
8. If the document looks like methodology, output artifact, official form, duplicate or outside-scope content, say so through content_kind and role_hypotheses.
9. If the package is insufficient, return a valid passport with null fields and review_required=true.

Expected JSON fields:
schema_version
passport_id
normalization_run_id
case_group_id
document_id
source_file_ref
passport_status
document_title_candidate
document_kind_candidate
broker_name_candidate
client_name_candidate
account_or_contract_candidate
report_period_start
report_period_end
tax_year_candidate
created_at_candidate
document_language
document_format
container_format
content_kind
sections_detected
tables_detected
operation_sections_detected
cashflow_sections_detected
income_sections_detected
withholding_sections_detected
tax_sections_detected
role_hypotheses
source_candidate_confidence
metadata_confidence
evidence_refs
missing_metadata_fields
conflict_flags
review_required
llm_prompt_ref
llm_prompt_command
llm_prompt_version
llm_prompt_hash
llm_model_id
llm_input_refs
validator_status
validator_errors
created_at

Input package:
{{document_package_json}}
```

## 7. Output Schema Requirements

The model output must satisfy:

- `schema_version == "document_metadata_passport_v0"`;
- all required fields are present;
- all unknown fields are null rather than invented;
- every non-null candidate has at least one evidence ref unless the field is run metadata;
- no forbidden keys or raw-content fields are present;
- `validator_status` should be `pending` before validator execution;
- `passport_status` should be `draft` before validator execution.

The validator owns final `validated`, `blocked` or `privacy_failed` status.

## 8. Prompt Hash Rule

Gate 1 computes:

```text
sha256(normalized_prompt_content + contract id + output schema version)
```

The hash is stored on every passport run. If prompt content changes, future passports must carry the new hash/version while old passports retain their original hash/version.

## 9. Negative Test Cases

Implementation tests should prove the prompt contract rejects or fails validation for outputs that:

- include markdown fences;
- include raw rows or copied text;
- invent missing account/period values;
- include source facts;
- include tax calculation;
- omit prompt hash/version;
- reference evidence ids not present in the package;
- set high confidence without evidence refs;
- omit `review_required` when critical metadata is missing.

## 10. Status

```text
DOCUMENT_METADATA_PASSPORT_PROMPT_CONTRACT_READY
```
