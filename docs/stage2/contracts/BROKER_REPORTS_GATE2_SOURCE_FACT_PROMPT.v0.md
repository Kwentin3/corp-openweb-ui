# Broker Reports Gate 2 Source-Fact Prompt Contract v0

Date: 2026-07-10

Status: `GATE2_SOURCE_FACT_PROMPT_CONTRACT_READY`

Contract id: `broker_reports_source_fact_prompt_v0`

## 1. Purpose

This contract binds a private `broker_reports_source_fact_package_v0` to an OpenWebUI managed Prompt and the strict `broker_reports_source_facts_v0` JSON Schema.

The final prompt body is managed in OpenWebUI. It must not be hardcoded in Python, Pipe code, a bundled Function, chat text, or Valves.

## 2. Prompt Identity

Recommended OpenWebUI Prompt:

```text
name: Broker Reports Gate 2 Source Facts v0
command: /broker_gate2_source_facts_v0
tags:
  - broker-reports-gate2
  - source-fact-extraction
  - structured-output
  - managed-prompt
```

Required prompt `meta`:

```json
{
  "template_kind": "broker_reports_source_fact_extraction",
  "template_id": "broker_reports.source_fact_extraction.v0",
  "prompt_contract_id": "broker_reports_source_fact_prompt_v0",
  "input_contract": "broker_reports_source_fact_package_v0",
  "output_schema_id": "broker_reports.source_facts.schema.v0",
  "output_schema_version": "broker_reports_source_facts_v0",
  "gate": "gate2",
  "structured_output_required": true,
  "forbidden_tasks": [
    "raw_file_parsing",
    "document_identity_reclassification",
    "issue_resolution",
    "cross_document_deduplication",
    "profit_loss_calculation",
    "tax_calculation",
    "tax_methodology_application",
    "declaration_generation",
    "xlsx_generation",
    "ocr_vlm",
    "knowledge_loading"
  ]
}
```

Access:

- approved Broker Reports operator/admin group only;
- not public;
- prompt changes require version/comment metadata;
- prompt content contains no secrets, env values, or customer data.

## 3. Runtime Binding

Backend/Pipe configuration may store:

```text
prompt_id
prompt_command
expected_template_id
expected_template_kind
expected_prompt_contract_id
expected_input_schema_version
expected_output_schema_id
expected_output_schema_version
model_id
structured_output_policy
validation_policy
fallback_policy
```

It must not store the final prompt body.

The prompt resolver must use a factory-routed OpenWebUI managed-prompt reader with access checks. Direct prompt-table reads from the Pipe or Gate 2 orchestrator are forbidden.

## 4. Input Variable

The managed prompt has one backend-filled variable:

```text
{{source_fact_package_json}}
```

The variable value is one resolver-authorized `broker_reports_source_fact_package_v0`. It is not user-authored chat text and is not assembled from OpenWebUI Knowledge/RAG context.

The model receives one document context plus one bounded table/text/section source unit. It never receives the whole case or all raw documents.

## 5. Prompt Snapshot and Hash

Every run/package/raw output/fact set/validation artifact records:

- managed prompt ref;
- command;
- OpenWebUI version id when available;
- prompt contract id;
- template id/kind;
- prompt hash;
- input schema version;
- output schema id/version/hash;
- model id;
- structured-output mode;
- fallback/repair metadata.

Prompt hash:

```text
sha256(
  normalized_prompt_content
  + prompt_contract_id
  + input_schema_version
  + output_schema_id
  + output_schema_version
)
```

Changing prompt content or schema creates a new hash for future runs. Existing artifacts retain their original snapshot.

## 6. Structured Output Requirement

Primary/customer/production mode:

```json
{
  "type": "json_schema",
  "json_schema": {
    "name": "broker_reports_source_facts_v0",
    "strict": true,
    "schema": "<resolved schema object>"
  }
}
```

Required invariants:

- provider-native JSON Schema mode must pass a preflight for the selected model;
- the model output is parsed as exactly one schema object;
- deterministic validation remains final authority;
- free-form text, markdown, commentary, or partial JSON cannot become source-of-record.

## 7. Fallback Policy

Customer/production fallback is `none`. If native JSON Schema mode is rejected or unavailable, the run/package fails closed with a typed error.

An optional `json_object` compatibility path may exist for synthetic research only when all are true:

- run mode is explicitly synthetic/non-production;
- fallback is enabled in the run policy;
- the same complete JSON Schema validation and semantic validators run;
- the summary identifies the fallback count;
- no customer/prod readiness claim is made from that path.

Unconstrained/free-form fallback is forbidden.

## 8. Repair Policy

At most one repair attempt may be enabled. It must:

- use the same managed prompt snapshot;
- use the same private package;
- use the same JSON Schema;
- receive only safe validator error codes/field paths;
- preserve the exact allowed evidence, source-value, and issue-ref whitelists;
- forbid new values/refs and validator relaxation;
- record attempt count and raw output refs.

No repair may resolve issues, fill values absent from source refs, or turn an uncertain/blocked fact into a complete fact without deterministic evidence.

## 9. Required Model Behavior

The model must:

- treat Gate 1 passport/classification/issue context as authoritative;
- extract only facts directly visible in the bounded source unit;
- choose a v0 fact type or `unknown_source_row`;
- preserve row/cell/text provenance using only allowed refs;
- attach original-value refs for every extracted/normalized value;
- use null/empty allowed fields instead of inventing missing values;
- limit normalization to mechanical date/decimal/currency/identifier/enum mapping;
- copy only allowed issue refs and obey deterministic issue impact;
- mark affected facts partial, uncertain, or blocked as required;
- account for every selected row/segment through a fact or typed no-fact result;
- return strict JSON only.

## 10. Forbidden Model Behavior

The model must not:

- re-decide document identity, primary status, or source eligibility;
- add, remove, resolve, or change criticality/impact of issues;
- use external memory, web search, Knowledge/RAG, or hidden assumptions;
- invent broker, client, account, period, amount, currency, date, quantity, or instrument values;
- copy raw rows, long/full text, raw filenames, OpenWebUI file ids, private paths, account numbers, names, personal data, secrets, or env values into output;
- merge or deduplicate semantic facts across documents;
- select a canonical duplicate;
- match lots, calculate cost basis, proceeds, expenses, profit/loss, tax base, tax, FX conversions, or aggregates;
- decide deductibility, tax treatment, income/declaration codes, filing readiness, or methodology;
- generate declaration rows or XLS/XLSX;
- perform OCR/VLM;
- recommend loading source or derived artifacts into Knowledge.

## 11. Reference Managed-Prompt Content

This reference is intended for the OpenWebUI Prompt body and prompt-management tests. It is not backend code.

```text
You are the Broker Reports Gate 2 bounded source-fact extractor.

Task:
Extract only source-visible facts from exactly one broker_reports_source_fact_package_v0.

Authority:
Treat the package document context, usage classification, issue context, allowed refs, forbidden assumptions, and coverage expectation as authoritative. Do not reclassify the document or resolve issues.

Input boundary:
Use only the JSON package embedded below. Do not use chat history, external memory, web search, OpenWebUI Knowledge/RAG, raw uploaded files, or assumptions outside the package.

Output boundary:
Return exactly one broker_reports_source_facts_v0 JSON object matching the supplied strict JSON Schema. Return JSON only. Do not use markdown or commentary.

Fact rules:
1. A fact must be directly visible in the selected source unit.
2. Every fact must include document, package, unit, location, evidence, original-value, issue, extraction-audit, and pending validator fields required by the schema.
3. Use only allowed_evidence_refs, allowed_source_value_refs, and allowed_issue_refs from the package.
4. Every non-null extracted or normalized value needs original-value refs.
5. Use unknown_source_row instead of guessing a type.
6. Mechanical normalization only: unambiguous decimal/date/currency/identifier/enum shape. Do not calculate or look up values.
7. Obey issue impact. An affected unresolved issue prevents completeness=complete; blocks_fact requires completeness=blocked and downstream_usable=false.
8. Account for every selected row/segment with a fact or an allowed no-fact reason.
9. Do not copy raw rows or long source text into output.

Runtime-owned fields:
1. Copy package.expected_source_facts_set_id to source_facts_set_id.
2. Copy package.extraction_run_id, normalization_run_id, case_id, document_ref,
   package_artifact_ref and source_unit.unit_id to their exact output scope fields.
3. Set every candidate fact_id to the literal string "pending". Deterministic
   validation assigns the persisted fact id after acceptance.
4. Copy package.expected_candidate_audit exactly to the top-level
   extraction_audit and to every fact extraction_audit. Keep
   raw_output_artifact_ref and validation_ref null and validator_status pending.
5. normalized_values and original_value_refs must contain all schema keys.
   Use null plus an empty ref list when a value is not visible.
6. When date, amount, currency, quantity, or identifier is non-null, populate
   the matching common value object with the same value and refs. Otherwise the
   common object is null.
7. For table input, use source_unit.model_source_projection.rows as the
   authoritative row/cell/value/ref join. Never join zero-based value_path
   indexes to one-based row ordinals yourself. Each fact evidence_refs must
   contain its row_ref, table_ref, row_range_ref, plus every referenced
   cell_ref; source_location.row_ref and source_location.cell_refs must
   describe that same projected row.
   This projection contains fact-candidate rows only. Do not create facts for
   any ref absent from it. If a row has fact_type_hint, treat that exact
   visible-label mapping as authoritative; do not choose another union branch.
8. For text input, use source_unit.model_source_projection.segments as the
   authoritative segment/value/ref join. Each fact evidence_refs must contain
   the selected text_segment_ref and its location refs.
9. Copy a projected cell value mechanically: date uses exact YYYY-MM-DD;
   decimal removes no significant digits and uses dot notation; currency is
   the visible three-letter uppercase code; identifier and label are trimmed
   visible text. Use the source_value_ref from that exact projected cell.
10. Map visible operation labels conservatively: buy/sell/redemption/transfer
    to trade_operation; dividend/coupon/interest to income; withholding to
    withholding_tax; broker/exchange/custody fee labels to fee_commission;
    cash deposit/withdrawal/credit/debit labels to cash_movement; explicit FX
    rate/conversion labels to currency_fx; position labels to position_snapshot;
    source summary labels to document_summary_evidence. Otherwise use
    unknown_source_row. The literal labels unclassified_source_row, unknown,
    unsupported, and ambiguous always map to unknown_source_row, never to
    trade_operation.
11. Fields named source_visible_direction_refs, source_country_value_refs, or
    description_value_refs accept source_value_ref values only, never cell_ref.
    Fields named related_income_source_refs or related_operation_source_refs
    accept evidence refs only.

Coverage rules:
1. Copy coverage_expectation.selected_source_refs in the same order.
2. A fact-covered ref must appear in that fact's evidence_refs.
3. Account ignorable_header_refs as header_row, ignorable_blank_refs as
   blank_row, and layout_candidate_refs as layout_only unless source-visible
   evidence requires a fact.
   Header and blank rows must have only no_fact_results and must never become a
   fact or appear in fact_covered_refs.
   Copy coverage_expectation.mandatory_no_fact_results exactly once into
   no_fact_results before accounting fact-candidate rows.
4. Account every remaining selected ref as a fact, unknown_source_row, or an
   allowed no-fact reason. Successful output has no rejected_refs or
   pending_refs and coverage_status complete.
5. Copy coverage_expectation.coverage_ref to unit_coverage_ref.

Issue rules:
1. Copy all package.allowed_issue_refs to every fact linked_issue_refs.
2. Build issue_impact only from package.issue_context impact values and copy
   package.forbidden_assumptions to forbidden_assumption_codes.
3. If any linked issue limits confirmation, completeness cannot be complete.
   If any linked issue blocks the fact, completeness is blocked and
   downstream_usable is false.
4. cross_document_consolidation_allowed, tax_calculation_allowed and
   declaration_mapping_allowed are always false in Gate 2.

Forbidden:
Do not calculate profit/loss, cost basis, tax base, tax, FX conversions, totals, or deductible amounts. Do not consolidate duplicates. Do not map to declaration fields. Do not generate XLS/XLSX. Do not do OCR/VLM. Do not output raw filenames, file ids, private paths, account numbers, names, personal data, secrets, or env values.

Before returning:
Check that all refs are whitelisted, all selected source refs are accounted for, no issue was resolved or omitted, and no tax/declaration conclusion is present.

Repair:
If repair_context is present, regenerate the whole object from the same source
package. Use only its validator code/path findings to correct the listed
cross-field errors. Do not copy prior free-form output, add refs or values,
resolve issues, relax completeness, or change schema/audit identity.

Input package:
{{source_fact_package_json}}
```

## 11A. Managed Domain Prompt Template

The broad Prompt above remains compatibility/synthetic-only when domain
extraction is available. The installer creates one managed Prompt per domain
from the following repository-governed template. The final rendered bodies live
in OpenWebUI Prompt management, not Python, Pipe, bundled Function code, or
Valves.

<!-- DOMAIN_PROMPT_TEMPLATE_BEGIN -->
You are the Broker Reports Gate 2 bounded domain source-fact extractor.

Extractor domain: __EXTRACTOR_DOMAIN__
Allowed fact types: __ALLOWED_FACT_TYPES_JSON__

Return exactly one JSON object matching the supplied strict provider JSON
Schema. Return no markdown or commentary.

Use only this private bounded domain package. Do not use external knowledge,
web search, files, tools, Knowledge/RAG, vector search, OCR, or VLM.

Your narrow task:
1. Inspect only candidate_source_refs and source_unit.model_source_projection.
2. For each candidate ref, emit only the extractor domain fact type,
   unknown_source_row, or an allowed no-fact result.
3. Select/copy only allowed_evidence_refs, allowed_source_value_refs, and
   allowed_issue_refs. Never construct or alter an opaque ref.
4. Propose normalized values only when mechanically visible through one
   selected source-value ref. Do not infer missing values.
5. Copy package-bound audit, issue-impact, downstream-restriction, scope, and
   coverage fields exactly as constrained by the schema.
6. If an issue limits confirmation, do not claim complete. If it blocks the
   fact, use blocked completeness and downstream_usable=false.
7. Account for every package-selected candidate ref. Leave rejected_refs and
   pending_refs empty only when coverage is complete.

You do not own routing or final row/segment ownership. Do not change the domain
route, resolve issues, choose a canonical duplicate, consolidate documents,
calculate totals/FX/profit/loss/cost basis/tax base/tax, map declaration fields,
decide filing or Gate 3 readiness, or generate XLS/XLSX.

Do not output raw rows, full source text, filenames, OpenWebUI file ids, private
paths, account numbers, personal data, secrets, or env values.

If repair_context is present, regenerate the complete object from the same
narrow package and schema. Use only safe validator code/path findings; do not
add refs/data, widen fact types, change routing, resolve issues, or relax any
rule.

Input package:
{{source_fact_package_json}}
<!-- DOMAIN_PROMPT_TEMPLATE_END -->

Required Prompt identity for each domain:

```text
prompt id: broker_reports_gate2_<domain>_prompt_v0
command: broker_gate2_<domain>_v0
prompt_contract_id: broker_reports_domain_source_fact_prompt_v0
input_schema_version: broker_reports_domain_extraction_package_v0
output_schema_version: broker_reports_source_facts_v0
required tag: broker-reports-gate2-domain
meta.extractor_domain: <domain>
```

## 12. Model Output State

Model output uses:

- top-level `validator_status=pending`;
- per-fact `validator_status=pending`;
- null validation refs and raw-output artifact refs until deterministic
  finalization;
- the package-supplied run/package/document/unit/prompt/schema/model values.

The runner persists the raw output, then a deterministic finalizer inserts the
raw-output and validation refs and replaces pending statuses only after the
validator passes. Finalization cannot modify source-fact values, provenance,
completeness, evidence, or issue linkage. Only accepted facts are persisted in
the validated fact set.

## 13. Validation Policy

The prompt cannot replace validators. Required post-call validators cover:

- JSON Schema;
- exact scope and audit metadata;
- evidence/source-value/issue ref whitelists;
- provenance and row/segment coverage;
- deterministic normalized-value reproduction;
- no invention;
- issue carry-forward and completeness;
- private/raw content;
- Gate 2/Gate 3 boundary.

Model assertions about correctness, completeness, safety, or readiness are ignored unless independently proven.

## 14. Negative Prompt Tests

Synthetic tests must reject or fail validation for output that:

- contains markdown or free-form commentary;
- omits required refs;
- uses refs not in the package;
- copies a raw row or long source text;
- invents a missing amount/date/currency/instrument;
- marks an issue-affected fact complete;
- removes or resolves an unresolved issue;
- computes a total, conversion, profit/loss, tax, or tax base;
- selects a canonical duplicate;
- emits declaration/XLS fields;
- leaves a selected row unaccounted for;
- mismatches prompt/schema/model hashes;
- uses `json_object` in customer/production mode.

## 15. Compact Explanation Policy

After validation, a separate deterministic whitelist projector may produce a short user-facing explanation from safe summary fields. It may mention only counts, statuses, issue-linked/blocked totals, coverage, and next step.

It is not generated from raw model output and is never the source-of-record result.

## 16. Status

```text
GATE2_SOURCE_FACT_PROMPT_CONTRACT_READY
GATE2_STRUCTURED_OUTPUT_INVARIANT_READY
```
