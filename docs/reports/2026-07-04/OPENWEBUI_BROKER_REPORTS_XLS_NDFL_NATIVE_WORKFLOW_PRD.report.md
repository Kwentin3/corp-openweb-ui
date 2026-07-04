# OpenWebUI Broker Reports / XLS НДФЛ Native Workflow PRD Report

Date: 2026-07-04
Output: [BROKER_REPORTS_XLS_NDFL_NATIVE_WORKFLOW_PRD.md](../../stage2/prd/BROKER_REPORTS_XLS_NDFL_NATIVE_WORKFLOW_PRD.md)
Scope: documentation audit, public OpenWebUI docs check, product PRD creation

## What Was Studied

Local project documents:

- `docs/prd/OPENWEBUI_CORPORATE_CHAT_PRD_1.md`
- `docs/stage2/README.md`
- `docs/stage2/CONTEXT_INDEX.md`
- `docs/stage2/DOMAIN_MAP.md`
- `docs/stage2/CONTRACT_BOUNDARIES.md`
- `docs/stage2/IMPLEMENTATION_GATES.md`
- `docs/stage2/EXTENSION_FIRST_IMPLEMENTATION_PATTERN.md`
- `docs/stage2/implementation/OPENWEBUI_NATIVE_CAPABILITY_AUDIT.md`
- `docs/stage2/blueprints/BROKER_REPORTS_3NDFL.blueprint.md`
- `docs/stage2/blueprints/DOCUMENTS_OCR_EXCEL.blueprint.md`
- `docs/stage2/blueprints/SECURITY_DATA_POLICY.blueprint.md`
- `docs/stage2/blueprints/PROVIDERS_MODEL_CATALOG.blueprint.md`
- `docs/stage2/acceptance/ACCEPTANCE_MATRIX.md`
- `docs/stage2/acceptance/TEST_DATA_REQUIREMENTS.md`
- `docs/stage2/implementation/STAGE2_UNBLOCKED_WORK_PLAN.md`
- Stage 2 STT/DOCX reports and code structure around Action bridge, message-level DOCX export and prompt draft flow.

Public OpenWebUI docs checked on 2026-07-04:

- Workspace, Models, Prompts, Knowledge, Skills.
- Tools and Functions / Actions.
- File uploads, RAG limits, file API.
- RBAC and hardening docs.
- File browser/download docs as a candidate artifact model, not as confirmed deployed capability.

## Documents Found

Relevant existing local documents:

- PRD-1 already names broker reports / 3-НДФЛ as a priority scenario and defines the native-first pattern.
- `BROKER_REPORTS_3NDFL.blueprint.md` exists, but it is a small implementation-oriented blueprint and keeps the scenario blocked by customer documents and good-result examples.
- `DOCUMENTS_OCR_EXCEL.blueprint.md` states that accurate Excel handling needs parser/tool/code path and that complex Excel parser is separate/future.
- `OPENWEBUI_NATIVE_CAPABILITY_AUDIT.md` classifies files/documents as native-partial and notes DOCX/XLSX placeholder upload without extraction claim.
- `ACCEPTANCE_MATRIX.md` keeps broker reports / 3-НДФЛ as `FUTURE_SCOPE`; customer data remains required.
- `TEST_DATA_REQUIREMENTS.md` asks for broker reports, XLSX if used, expected good result, OCR/scans and provider/data policy examples.
- STT v2 and message-level DOCX export are now useful implementation precedents, but they do not prove XLSX generation.

## Current Conclusion

OpenWebUI Workspace can be used as the main native product shell, but the product should be framed as a preconfigured workflow scenario assembled from native pieces:

- Workspace Model;
- system prompt/model instructions;
- Prompts;
- Knowledge;
- Skills if supported by the deployed version;
- Groups/RBAC/resource access;
- Tools/Functions/Actions only for deterministic gaps.

The MVP should not look like an empty generic chat. It should look like a controlled OpenWebUI scenario with visible scope, warnings, prompt steps, methodology and draft-only output.

## Suitable Native OpenWebUI Entities

- Workspace: suitable umbrella and configuration area.
- Workspace Model: best scenario entrypoint.
- System prompt/model instructions: responsibility boundary and output discipline.
- Prompts: reusable workflow steps and slash commands.
- Knowledge: approved methodology, templates, examples and manual review rules.
- Skills: useful instruction bundles if available in target runtime.
- Tools/Functions/Actions: appropriate only for deterministic parsing, validation or file generation gaps.
- File upload/chat history: suitable for the working context, subject to retention and data policy.
- Groups/RBAC: required for scenario access.

## Gaps Found

- Target deployed OpenWebUI version must be verified against current public docs.
- Native Skills availability is not proven in this runtime.
- Native XLS/XLSX generation/download path is not proven.
- Reliable broker table extraction from PDF/XLSX is not proven.
- Strict required-field validation is not proven.
- Source mapping from XLS row to original report source is not proven.
- Repeatable structured intermediate output is not proven.
- Customer samples, prompts, methodology and correct XLS/XLSX outputs are missing.
- Provider/data policy for broker/tax/financial data is not approved.

## What Must Not Be Done Now

- Do not change application code.
- Do not change production runtime.
- Do not connect new providers.
- Do not use real customer documents.
- Do not read or print secrets, keys or env values.
- Do not create a separate sidecar UI.
- Do not make a deep OpenWebUI fork the primary route.
- Do not claim tax correctness or automatic 3-НДФЛ filing.
- Do not turn this PRD into an implementation blueprint.

## Recommended Next Documents / Actions

1. Prepare `Native Workflow Feasibility Proof Plan` for the broker reports scenario.
2. Request customer materials: prompts, methodology, anonymized reports, expected XLS/XLSX outputs, required fields and review rules.
3. Close provider/data policy and retention decisions before real samples.
4. Prove target OpenWebUI runtime support for Workspace Model, Prompts, Knowledge, Skills, file upload and artifact/download behavior.
5. Only after proof, write an Implementation Blueprint for the minimal extension path if XLSX generation or strict validation cannot be solved natively.

## Verdict

Native-first product discovery is justified. Workspace is a suitable shell, but XLS/XLSX generation, strict validation, reliable extraction and source mapping are proof-gated gaps. The next step is a feasibility proof plan, not code and not a sidecar UI.
