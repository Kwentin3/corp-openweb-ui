# Broker Reports Document Intake And JSON Extraction MVP Proof Plan

Status: Proof plan
Date: 2026-07-04
Related contract: [BROKER_REPORTS_JSON_EXTRACTION_CONTRACT.v0.md](../contracts/BROKER_REPORTS_JSON_EXTRACTION_CONTRACT.v0.md)

## 1. Purpose

Test whether a native-first OpenWebUI flow can classify broker-related inputs and return valid, reviewable JSON according to `broker_reports_extraction_v0`.

The proof explicitly excludes:

- XLS/XLSX generation;
- final 3-НДФЛ generation;
- FNS integration;
- production OCR support;
- real customer documents;
- production runtime changes.

## 2. Proof Principle

Schema-first. Prompt-only first if structured output is not proven. Structured output when available. Validation always. Repair-loop if needed. Human review mandatory. XLS generation deferred.

## 3. Execution Modes Under Proof

The proof should run the same synthetic inputs across these modes when available:

- Mode A: prompt-only JSON.
- Mode B: provider JSON mode.
- Mode C: provider structured output / JSON Schema.
- Mode D: function/tool calling as structured arguments.
- Mode E: validation plus repair-loop.

If OpenWebUI cannot pass provider-specific structured-output parameters in the current runtime, record this as a gap and continue with Mode A plus external validation.

## 4. Track A: Text / Machine-Readable Extraction

Inputs:

- pasted text;
- text-layer PDF;
- CSV;
- simple XLSX;
- table-heavy XLSX if synthetic generation is feasible.

Checks:

- file classification;
- `document_manifest`;
- prompt-only JSON output;
- JSON parse;
- schema/contract validation;
- `extracted_tax_facts`;
- `missing_data`;
- `uncertain_data`;
- `conflicts`;
- `questions_to_specialist`;
- `readiness`;
- repeatability across 3 runs.

Expected behavior:

- text and table inputs are not marked as raster;
- missing values are not invented;
- facts without evidence wrapper are rejected by validation;
- output never claims final tax correctness.

## 5. Track B: Raster / Vision Extraction Experiment

Inputs:

- synthetic scanned PDF;
- synthetic image/photo;
- raster table image;
- synthetic mixed PDF if feasible.

Checks:

- system identifies raster/photo/mixed inputs;
- does not pretend raster content is text-layer PDF;
- uses `processing_mode: "vision_llm_experimental"` or `unsupported`;
- raster-derived values carry lower trust and manual review;
- source references do not claim exact text-layer excerpts;
- poor image quality produces `uncertain_data` or `missing_data`;
- `readiness.manual_review_required` is always `true`.

Track B is not production OCR support. It is only an experimental proof path.

## 6. Prompt Contract Smoke

Prompt-only smoke:

1. Attach or paste `synthetic_broker_report_text_ru.txt`.
2. Provide the contract skeleton and instruction to return JSON only.
3. Ask for `broker_reports_extraction_v0`.
4. Parse returned JSON.
5. Validate required keys and document manifest.
6. Record whether repair-loop was needed.

Recommended run count: 3 identical runs with temperature low or default deterministic settings where available.

## 7. Validation And Repair Loop

Validation layers:

1. JSON parse.
2. Required top-level keys.
3. `schema_version` exact match.
4. Manifest entry for every input.
5. Enum values for document classification.
6. Evidence wrapper on every extracted fact.
7. Safety invariants:
   - `readiness.manual_review_required == true`;
   - `tax_correctness_claimed == false`;
   - `fns_filing_claimed == false`;
   - no XLS generation claim.

Repair-loop:

- Max attempts: 2.
- Repair prompt includes validation errors only, not hidden expected answers.
- If still invalid after max attempts, fail closed with `readiness.status: "failed"` in the operator result.
- Do not manually edit model output and call it a model pass.

## 8. Failure Behavior Cases

Required cases:

- unsupported document type;
- incomplete document;
- conflicting values across two synthetic docs;
- low-quality raster;
- unrelated input.

Expected behavior:

- unsupported input appears in `document_manifest`;
- incomplete values go to `missing_data`;
- conflicting values go to `conflicts`;
- low-quality raster does not create high-confidence facts;
- unrelated input returns `not_ready` or `failed`, not fabricated broker facts.

## 9. Proof Acceptance Criteria

A1. Scenario/prompt can request JSON extraction without XLS generation.

A2. Output contains `schema_version`.

A3. Output contains `document_manifest` for every input document.

A4. Each document has `container_format`, `content_representation`, `readability_status`, `processing_mode` and `limitations`.

A5. Text/machine-readable documents and raster documents are classified differently.

A6. Raster-derived results are marked experimental/lower-trust and always require manual review.

A7. Important extracted fields use evidence wrapper with source reference.

A8. Missing values are not invented; they appear in `missing_data`.

A9. Uncertain values appear in `uncertain_data`.

A10. Conflicting values appear in `conflicts`.

A11. The model returns `questions_to_specialist`.

A12. The model returns `readiness.status`.

A13. Output is valid JSON or repair-loop produces valid JSON within allowed attempts.

A14. Schema validation success/failure is measurable.

A15. Repeatability is measured across 3 runs.

A16. Result does not claim final tax correctness.

A17. Result does not imply FNS filing or final 3-НДФЛ generation.

A18. XLS generation remains deferred.

## 10. Evidence To Capture

For each run:

- input fixture ids;
- execution mode;
- provider/model path;
- whether OpenWebUI native chat, OpenWebUI API, provider API, or extension path was used;
- whether files were uploaded, pasted, or attached through Knowledge;
- raw model output stored only if synthetic and secret-free;
- parse status;
- validation status;
- repair-loop attempts;
- manifest count;
- missing/uncertain/conflict counts;
- readiness status;
- manual review warning presence;
- notes on hallucination or source-reference drift.

## 11. Blockers Before Runtime Proof

- Target OpenWebUI runtime version and model path must be identified.
- Provider/data policy must allow the selected model path for synthetic data.
- No real customer files may be used.
- If raster Track B needs image input, the selected model must be vision-capable and OpenWebUI must pass image/file context correctly.
- If provider structured output is tested, the path for `response_format`, `json_schema`, `output_config` or equivalent must be proven without printing secrets.

## 12. Proof Outcome Categories

- `PROMPT_ONLY_PROOF_READY`: prompt-only output parses and validates on synthetic text/table inputs.
- `STRUCTURED_OUTPUT_PATH_PROVEN`: provider schema mode is proven through approved runtime path.
- `VALIDATION_REQUIRED`: output can be useful, but external validation/repair is mandatory.
- `RASTER_EXPERIMENT_ONLY`: raster path works only as low-trust experimental evidence.
- `EXTENSION_REQUIRED`: Tool/Function/API helper is needed for validation, parsing, source mapping or structured-output parameter pass-through.
- `BLOCKED_CUSTOMER_INPUT`: cannot proceed to customer-grade proof without samples, methodology, expected outputs or data policy.

## 13. Next Step After Proof

If Track A passes prompt-only plus validation, proceed to a runtime proof report and customer sample intake checklist.

If Track A fails without structured output, test provider JSON mode or structured output through the smallest approved path.

If source mapping, table extraction or validation cannot be made reliable, write an implementation blueprint for a minimal Tool/Function/OpenAPI helper. Do not start XLS/XLSX generation before JSON extraction proof is stable.
