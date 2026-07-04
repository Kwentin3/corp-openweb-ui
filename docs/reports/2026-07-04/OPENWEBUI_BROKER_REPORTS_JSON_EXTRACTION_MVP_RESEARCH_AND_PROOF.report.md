# OpenWebUI Broker Reports JSON Extraction MVP Research And Proof Report

Date: 2026-07-04
Scope: research, feasibility planning, static contract checks
Repository: `corp-openweb-ui`

Outputs:

- [BROKER_REPORTS_JSON_EXTRACTION_CONTRACT.v0.md](../../stage2/contracts/BROKER_REPORTS_JSON_EXTRACTION_CONTRACT.v0.md)
- [BROKER_REPORTS_DOCUMENT_INTAKE_AND_JSON_EXTRACTION_MVP_PROOF_PLAN.md](../../stage2/proof/BROKER_REPORTS_DOCUMENT_INTAKE_AND_JSON_EXTRACTION_MVP_PROOF_PLAN.md)
- [BROKER_REPORTS_STRUCTURED_OUTPUT_EXECUTION_MODES_RESEARCH.md](../../stage2/research/BROKER_REPORTS_STRUCTURED_OUTPUT_EXECUTION_MODES_RESEARCH.md)
- [BROKER_REPORTS_JSON_EXTRACTION_SYNTHETIC_FIXTURES_PLAN.md](../../stage2/testdata/BROKER_REPORTS_JSON_EXTRACTION_SYNTHETIC_FIXTURES_PLAN.md)

## What Was Studied

Local project documents:

- `docs/stage2/prd/BROKER_REPORTS_XLS_NDFL_NATIVE_WORKFLOW_PRD.md`
- `docs/reports/2026-07-04/OPENWEBUI_BROKER_REPORTS_XLS_NDFL_NATIVE_WORKFLOW_PRD.report.md`
- `docs/stage2/EXTENSION_FIRST_IMPLEMENTATION_PATTERN.md`
- `docs/stage2/implementation/OPENWEBUI_NATIVE_CAPABILITY_AUDIT.md`
- `docs/stage2/blueprints/BROKER_REPORTS_3NDFL.blueprint.md`
- `docs/stage2/blueprints/DOCUMENTS_OCR_EXCEL.blueprint.md`
- `docs/stage2/acceptance/TEST_DATA_REQUIREMENTS.md`
- `docs/stage2/acceptance/ACCEPTANCE_MATRIX.md`
- Stage 2 STT/DOCX reports and code patterns around OpenWebUI Actions, prompt drafts, downloads and message-level DOCX export.

Repository keyword search covered:

- `response_format`
- `json_schema`
- `json_object`
- `structured output`
- `tool_call`
- `function_call`
- `tools`
- `actions`
- `openapi`
- `files`
- `upload`
- `rag`
- `xlsx`
- `docx`
- `export`
- `artifact`
- `download`

Public documentation checked on 2026-07-04:

- OpenWebUI Workspace Models, Prompts, file handling, RAG/file API and extensibility docs.
- OpenAI Structured Outputs and strict function calling docs.
- Anthropic/Claude structured output docs.
- Gemini structured output docs.
- DeepSeek JSON mode and function calling docs.
- Alibaba/Qwen JSON mode and Qwen function calling docs.

## Local Repo Findings

The current repository supports a native-first product direction, but it does not yet prove broker report JSON extraction.

Found and relevant:

- OpenWebUI Workspace / Workspace Model remains the preferred scenario shell.
- Prompts and model instructions are suitable for a first proof.
- Existing STT/DOCX work proves useful Action/export/download precedents, but not broker extraction.
- The native capability audit treats file/document handling as partial and does not claim reliable DOCX/XLSX extraction.
- `DOCUMENTS_OCR_EXCEL.blueprint.md` keeps accurate table/Excel handling behind a deterministic parser/tool/code path.
- Broker reports / 3-NDFL remain future/proof-gated in the acceptance docs.

Not found as an existing project capability:

- LLM `response_format/json_schema` pass-through for chat completions.
- Broker-report JSON contract or validator.
- Repeatable structured extraction from broker PDFs/XLSX.
- Raster/OCR production support.
- XLS/XLSX generation for this scenario.

## OpenWebUI And Provider Capabilities

OpenWebUI public docs confirm a useful native shell:

- Workspace Models can combine a base model with instructions, knowledge, tools, skills and parameters.
- Prompts can provide reusable slash-command workflows.
- File upload and RAG/file API paths exist, but uploaded file availability is not the same as reliable structured extraction.
- Tools/Functions/OpenAPI/MCP paths exist for extension work.
- Actions are appropriate for user-triggered message operations.
- Workspace Tools execute privileged server-side Python and must be treated as trusted implementation work.

Provider docs confirm structured-output options at the provider API level:

- OpenAI supports Structured Outputs with JSON Schema and strict function calling.
- Anthropic/Claude documents JSON outputs and strict tool use as separate capabilities.
- Gemini supports structured output with a JSON schema subset.
- DeepSeek supports JSON Output and function calling, with strict function mode in a beta path.
- Alibaba/Qwen documents JSON mode; Qwen function calling uses JSON Schema-style parameters.

Important limitation:

The reviewed OpenWebUI docs and local repository do not prove that the current OpenWebUI deployment can reliably pass provider-specific `response_format`, `json_schema`, `output_config.format` or equivalent structured-output parameters through native chat for every provider. Treat provider structured output as a separate runtime proof, not as an assumed capability.

## Execution Modes

Mode A. Prompt-only JSON:

- Best first proof path.
- Requires schema-first prompt discipline and external validation.
- No production code needed.
- Expected weakness: valid JSON and schema adherence are not guaranteed without repair.

Mode B. JSON mode:

- Useful if the provider/OpenWebUI path can pass the required parameter.
- Improves JSON parse success but does not guarantee schema adherence.
- Needs provider-specific runtime proof.

Mode C. Provider structured output / JSON Schema:

- Strongest format-control path when supported.
- Provider API support exists for some providers.
- OpenWebUI pass-through is unproven in this task.
- Still does not prove factual correctness; evidence and validation remain mandatory.

Mode D. Function/tool calling:

- Potentially useful for structured arguments, deterministic parsing and validation.
- Not required for the first proof.
- Adds trusted server-side execution/security review and implementation scope.

Mode E. Validation plus repair-loop:

- Required safety layer for all modes.
- Must parse JSON, validate required fields, reject unsupported claims and return format errors for repair.
- Full automation can wait until prompt-only proof shows value.

## Recommended First MVP Mode

Start with Mode A plus Mode E:

1. Use a Workspace Model/system prompt or slash prompt that embeds the contract.
2. Use only synthetic pasted text / text-layer examples first.
3. Require `broker_reports_extraction_v0`.
4. Validate JSON externally.
5. Add repair-loop only if invalid JSON appears.
6. Record 3-run repeatability before any XLS/XLSX stage.

Do not start with Tool/Function unless prompt-only proof fails on format or table/source mapping becomes the blocking gap.

## JSON Contract v0

The created contract defines:

- top-level `schema_version: broker_reports_extraction_v0`;
- mandatory `document_manifest`;
- document classification fields;
- evidence wrapper for extracted values;
- explicit missing/uncertain/conflict states;
- specialist questions;
- readiness status;
- manual review warning;
- no tax correctness claim;
- no FNS filing claim;
- no XLS/XLSX generation authorization.

The contract intentionally separates:

- missing value;
- found but uncertain value;
- conflict;
- not applicable value;
- unsupported/raster-only value;
- model inference without source, which must not count as extracted evidence.

## Raster / Vision Position

Raster/vision is included only as Track B experimental proof.

Track B must show that the workflow:

- classifies raster/photo/mixed inputs correctly;
- does not pretend raster content is a text-layer PDF;
- marks raster-derived values as lower-trust or unsupported;
- requires manual review;
- avoids exact text-layer source excerpts when no text layer exists;
- fails closed on poor image quality.

This is not production OCR support.

## Synthetic Fixtures

The fixture plan defines:

- `synthetic_broker_report_text_ru.txt`
- `synthetic_broker_report_text_pdf.md`
- `synthetic_operations.csv`
- `synthetic_operations_simple.xlsx`
- `synthetic_dividends_report_scan.png`
- `synthetic_broker_report_scan.pdf`
- `synthetic_mixed_pdf_case.md`
- `expected_broker_reports_extraction_v0.json`

The plan requires synthetic names, synthetic broker labels and synthetic values only. Real customer documents and real personal/broker/tax/financial data remain out of scope.

## Feasibility Tests Performed

No production code or production runtime was changed.

Static checks performed:

- Parsed JSON blocks from `BROKER_REPORTS_JSON_EXTRACTION_CONTRACT.v0.md`.
- Parsed the JSON Schema draft and the minimal valid example with local PowerShell JSON parsing.
- Checked that the minimal example contains all required top-level keys.
- Checked `schema_version == broker_reports_extraction_v0`.
- Checked that `document_manifest` contains at least one document.
- Checked required document manifest keys.
- Checked that the minimal example does not proceed to XLS stage.
- Checked a negative required-key case where `document_manifest` is missing.

Observed static check result:

- `json_fences=12`
- `schema_required_count=12`
- `minimal_required_keys_ok=true`
- `minimal_document_manifest_count=1`
- `negative_missing_document_manifest_detected=true`

Not executed:

- Live OpenWebUI chat smoke.
- Provider API structured-output smoke.
- Vision/raster runtime smoke.
- Full JSON Schema validation with `jsonschema`/`ajv`.
- Repeatability across 3 model runs.

Reason: the task forbids runtime/provider changes, secrets, real documents and production code. The local environment did not provide a JSON Schema validator package, and no new dependency was installed.

## Proof Gaps

Before implementation or XLS/XLSX work, close these gates:

- Target OpenWebUI runtime version and provider path are identified.
- Prompt-only synthetic text proof produces parseable JSON.
- Contract validation succeeds or repair-loop succeeds within allowed attempts.
- `document_manifest` is complete for every input.
- Missing/uncertain/conflict states are measured.
- Source references are reviewable and not fabricated.
- 3-run repeatability is measured.
- Raster Track B is either proven experimental or explicitly marked unsupported.
- Provider structured output pass-through is proven if Mode B/C is desired.
- Provider/data policy for real broker/tax documents is approved.
- Customer supplies anonymized examples, expected fields, review rules and expected good outputs.

## Answers To Expected Questions

1. Can we start with prompt-only JSON extraction?

Yes. It is the lowest-risk first proof if validation is mandatory and results are limited to specialist review.

2. Is system prompt plus JSON contract enough for the first proof?

Enough for proof entry, not enough for production. The first proof must still parse, validate and measure repeatability.

3. Is there an OpenWebUI/provider path for structured output?

Provider APIs support several structured-output variants. OpenWebUI pass-through for this deployment is not proven by the reviewed docs or local repo and needs a separate runtime probe.

4. Is Tool/Function needed now?

No for first proof. Yes later if validation/repair, deterministic parsing, source mapping, provider pass-through or artifact generation must be automated.

5. What contract should be used?

Use `broker_reports_extraction_v0` from `BROKER_REPORTS_JSON_EXTRACTION_CONTRACT.v0.md`.

6. How to test raster/vision without claiming production OCR?

Run synthetic raster inputs only as Track B. Require experimental/low-trust marking, manual review and fail-closed behavior.

7. What fixtures are needed?

Use the eight synthetic fixtures listed in `BROKER_REPORTS_JSON_EXTRACTION_SYNTHETIC_FIXTURES_PLAN.md`.

8. What gates are required before XLS/XLSX?

Stable JSON extraction, validation, source references, repeatability, customer data policy and expected-output agreement.

9. What customer inputs remain mandatory?

Anonymized broker documents, required fields, specialist methodology, examples of good output, review rules, accepted source-reference format and provider/data policy approval.

10. What is the next step?

Run a prompt-only synthetic runtime proof in the target OpenWebUI deployment, then decide whether a minimal Tool/Function/OpenAPI helper is justified.

## Sources

OpenWebUI:

- https://docs.openwebui.com/features/workspace/models/
- https://docs.openwebui.com/features/workspace/prompts/
- https://docs.openwebui.com/features/chat-conversations/data-controls/files/
- https://docs.openwebui.com/reference/api-endpoints/
- https://docs.openwebui.com/features/extensibility/
- https://docs.openwebui.com/features/extensibility/plugin/tools/development/

Provider docs:

- https://developers.openai.com/api/docs/guides/structured-outputs
- https://developers.openai.com/api/docs/guides/function-calling#strict-mode
- https://platform.claude.com/docs/en/build-with-claude/structured-outputs
- https://ai.google.dev/gemini-api/docs/structured-output
- https://api-docs.deepseek.com/guides/json_mode
- https://api-docs.deepseek.com/guides/function_calling
- https://www.alibabacloud.com/help/en/model-studio/qwen-structured-output
- https://qwen.readthedocs.io/en/latest/framework/function_call.html

## Verdict

`Broker Reports Document Intake + JSON Extraction MVP` is feasible as a schema-first, prompt-only, synthetic-data proof with mandatory validation and human review. It is not yet proven as production extraction, structured-output pass-through, OCR support or XLS/XLSX generation.

Recommended next state: `PROMPT_ONLY_PROOF_READY`, with runtime proof still pending.
