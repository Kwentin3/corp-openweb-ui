# Broker Reports / XLS НДФЛ Native Workflow PRD

Status: Product Discovery PRD; full customer pilot remains gated
Date: 2026-07-04
Technical status updated: 2026-07-11
Stage: Stage 2
Owner track: Product / discovery / native-first feasibility

This document is a product discovery PRD, not an implementation blueprint. It defines the intended user workflow, native OpenWebUI product model, MVP boundaries, customer input gates and safety policy for a broker reports / XLS НДФЛ pilot.

## 1. Purpose

The feature should help customer specialists move an existing human-in-the-loop broker report workflow from CloudCowork/Claude into the corporate OpenWebUI environment.

The business task is narrow: a specialist uploads supported, text-readable or machine-readable broker report files, uses approved methodology and prompts, gets structured draft analysis, sees missing or uncertain data, and receives an XLS/XLSX draft for manual review.

The feature is not a tax platform and must not be presented as autonomous 3-НДФЛ preparation, tax advice, declaration filing, FNS integration, or a universal broker report parser.

## 2. Current Stage 2 Context

Stage 2 is an OpenWebUI-first corporate AI environment, built around controlled work scenarios rather than a raw list of models.

Current baseline:

- PRD-0 is closed.
- PRD-1 / Stage 2 positions regular employee tasks as managed work scenarios with prompts, templates, rules, access and constraints.
- STT v2 is current-stage closed: audio/video transcription runs inside the OpenWebUI UX through browser/WASM normalization, OpenWebUI Action/static loader integration, a private `stage2-stt` sidecar, LemonFox provider path, structured transcript artifact, speaker labels where enabled, post-processing prompt draft flow and quick actions.
- Generic message-level DOCX export is implemented through the existing OpenWebUI Action bridge, `stage2-stt` sidecar endpoint and `python-docx` renderer.
- The bounded broker-report normalization and Gate 2 extraction contour is implemented and deployed with repo/live parity. Bounded synthetic semantic acceptance passed for `gpt-5.6-sol` and `models/gemini-3.5-flash`. The current native/PDF customer rerun was not performed because the controlled case had no active source records or DCP. Customer methodology, representative samples, expected XLS/XLSX examples and data-policy decisions still gate the full pilot.
- The existing Stage 2 rule is extension-first: use native OpenWebUI configuration, Workspace Models, Prompts, Knowledge, Skills where supported, Tools/Functions/Actions and minimal extension points before considering any fork.

The broker reports pilot inherits that pattern: OpenWebUI remains the product
shell, while deterministic normalization, bounded model input and validation
use narrow backend/Pipe extension points. The next product gate is a
representative native/PDF customer rerun plus methodology and expected-output
acceptance.

## 3. Product Scope

In scope:

- Work inside OpenWebUI.
- A preconfigured domain scenario for broker reports / XLS НДФЛ draft preparation.
- A curated Workspace Model or equivalent OpenWebUI model entrypoint for the scenario.
- Scenario instructions, warnings and responsibility boundaries.
- Upload of supported text-readable or machine-readable broker report files.
- Use of customer-provided prompts, methodology and examples.
- Knowledge collection for approved methodology, templates and examples.
- Analysis of input data.
- Completeness checks against agreed required fields.
- Questions to the specialist when data is missing or uncertain.
- Structured intermediate draft before export.
- XLS/XLSX draft preparation if feasible through native or minimal extension path.
- Mandatory manual review by a customer specialist.
- Preservation of working context in chat history, subject to retention and data policy.
- Group/RBAC-based access to the scenario and related resources.

Out of scope:

- OCR as the primary epic.
- Scans, photos and raster PDFs as accepted MVP input.
- Guarantee of table extraction from scanned or layout-heavy PDFs.
- A full tax platform.
- A separate declarations cabinet.
- Automatic submission to FNS.
- FNS integration.
- CRM, task tracker or external system integrations.
- Guarantee of tax correctness.
- Final tax advice.
- Universal support for all brokers and all file formats.
- A separate user-facing sidecar UI in the current product discovery variant.
- Deep OpenWebUI fork as the primary path.
- Reading OpenWebUI private database shape as a product contract.
- Storing provider keys in the frontend.

## 4. Target User Workflow

The target workflow is human-in-the-loop:

1. The user selects the preconfigured broker reports scenario, Workspace or Workspace Model in OpenWebUI.
2. The user creates a chat for a client or task.
3. The user sees a short visible frame: supported input types, prohibited inputs, draft-only warning and manual-review requirement.
4. The user uploads broker report files.
5. The system checks readability and allowed formats.
6. The system refuses or limits scan/OCR-style inputs unless a separate approved proof path exists.
7. The system extracts available data or produces a documented extraction limitation.
8. The system shows what it understood: files, periods, broker/source, recognized tables or fields, and uncertain areas.
9. The system asks questions when required data is missing.
10. The system applies the approved customer methodology.
11. The system forms a structured intermediate draft.
12. The user reviews the draft and answers questions.
13. The system forms an XLS/XLSX draft if the export path is proven for the MVP.
14. The specialist manually checks and edits the result inside or outside the agreed customer process.

This workflow must never imply autonomous tax filing. Every result must stay visibly marked as a working draft.

## 5. Native OpenWebUI Product Model

### Workspace

Workspace is a suitable native umbrella for this feature, with one caveat: local Stage 2 docs already note that OpenWebUI does not expose a single product object named "business workspace". The product scenario should therefore be assembled from native pieces:

- Workspace Model as the scenario entrypoint.
- System prompt / model instructions as the responsibility frame.
- Prompts as reusable workflow steps.
- Knowledge as methodology and reference material.
- Skills where the deployed OpenWebUI version supports them.
- Tools/Functions/Actions only for steps that require deterministic execution or file generation.
- Groups/RBAC/resource access for controlled availability.

Verdict: use Workspace as the product shell, but describe the feature as a preconfigured OpenWebUI workflow scenario, not as an empty generic chat.

### Workspace Model

Use a curated Workspace Model named along the lines of `Broker Reports / XLS НДФЛ Draft`.

It should:

- wrap an approved base model;
- carry the scenario system prompt;
- attach approved Knowledge;
- expose only relevant tools/actions;
- be shared only with the allowed group;
- preserve base-model access rules, because OpenWebUI checks access to both the Workspace Model and the underlying base model.

### System Prompt / Model Instructions

System instructions should contain:

- assistant role for broker report draft support;
- explicit draft-only boundary;
- prohibition on final tax advice;
- prohibition on promising automatic declaration generation or filing;
- supported input formats;
- behavior for scans, photos and raster PDFs;
- rule to ask clarifying questions;
- rule to mark uncertain data;
- rule to surface missing fields;
- rule to preserve source references when possible;
- rule to avoid inventing tax facts;
- output structure for intermediate draft and questions.

### Prompts

Use Prompts as reusable slash-command workflow steps:

- initial intake and file checklist;
- supported format/readability check;
- data extraction summary;
- missing data question set;
- methodology application;
- structured draft review;
- XLS/XLSX export readiness check.

Prompts are appropriate for repeatable instructions and user-visible workflow steps. They are not sufficient for deterministic XLSX creation or strict validation by themselves.

### Knowledge

Use Knowledge for:

- customer methodology;
- broker report field glossary;
- approved examples;
- XLS/XLSX output schema description;
- manual review rules;
- known limitations and warning text.

Knowledge is not a document processing pipeline. It stores and retrieves approved methodology and examples; it should not be treated as proof that arbitrary broker reports can be parsed reliably.

### Skills

Skills are useful if supported in the deployed OpenWebUI version. They can hold reusable plain-text playbooks, for example:

- broker report review method;
- НДФЛ draft preparation checklist;
- uncertainty marking rules;
- source-mapping discipline.

If Skills are not available or not proven in the target runtime, the same content should stay in system prompt, Prompts and Knowledge.

### Tools, Functions and Actions

Use extension points only for capability gaps:

- Tool: deterministic extraction, file inspection, table conversion or validation, when the model needs server-side executable help.
- Function / Action Function: message-level or workflow-level button/action, similar in shape to the current STT and DOCX export bridge.
- OpenAPI Tool Server: candidate if a separate internal service exposes safe, narrow operations.
- Minimal backend/helper: candidate only if native file generation or deterministic XLSX handling is not possible.

Tools and Functions execute server-side code and must be restricted to trusted admin-controlled code. They are not a general user customization surface for this scenario.

### Boundary Between Chat and Workflow Scenario

Ordinary chat:

- user chooses any model;
- user writes ad hoc instructions;
- no enforced scenario frame;
- no approved methodology;
- no consistent draft structure;
- weak acceptance surface.

Preconfigured workflow scenario:

- user selects the curated scenario/model;
- system instructions define role and limits;
- prompts expose repeatable steps;
- Knowledge provides approved methodology;
- warnings are visible;
- output has predictable sections;
- group access and data policy apply;
- export readiness is explicit.

The MVP should be the second model: a scenario, not an empty chat.

## 6. Native-First Feasibility Analysis

### Can Be Done Natively

Likely native or configuration-first:

- scenario shell through Workspace / Workspace Model;
- model/system prompt;
- prompt templates and slash commands;
- methodology and examples in Knowledge;
- Skills if supported by target version;
- chat file upload;
- chat history as working context;
- access through groups and resource ACLs;
- visible warnings and disclaimers;
- manual review flow;
- initial structured draft in assistant response;
- customer-facing questions in chat.

### Implemented, Deployed, And Bounded Synthetic Acceptance Proven

- deterministic normalized-table projection for supported native and PDF
  text-layer inputs;
- bounded structured intermediate artifacts;
- row/cell source mapping and original-value reproduction;
- strict validator-controlled acceptance;
- shared provider factory with fail-closed capability policy.

These points are not full-corpus or production-rollout claims. The exact bundle
and managed Prompts have parity, and bounded synthetic runs on `gpt-5.6-sol`
and `models/gemini-3.5-flash` produced validator-accepted facts. The current
native/PDF customer rerun was not performed because no active source records or
DCP were available.

### Still Requires Product Proof Or Samples

Requires target-runtime proof or samples:

- reliable extraction across the agreed broker/PDF layout sample set;
- reliable extraction of workbook semantics from XLS/XLSX;
- XLS/XLSX generation as a downloadable artifact;
- resumable step-by-step workflow state beyond chat history;
- repeatability of output for the same input and methodology;
- native support for Skills in the deployed version;
- native artifact/download behavior suitable for XLSX in the deployed version.

### Current Extension Boundary, Not Sidecar UI

The current bounded technical contour uses a narrow backend/Pipe path for table
projection, candidate binding and validation. Remaining export work may use:

- Tool/Function/Action for deterministic table parsing or XLSX creation.
- OpenAPI Tool Server for a narrow internal generator/validator.
- Existing Action/static-loader pattern as precedent for a download operation.
- Existing message-level DOCX export pattern as a reference for file generation, typed errors and browser download.
- Minimal backend/helper only if native OpenWebUI cannot safely generate and return XLSX.

This is not a reason to create a separate user-facing sidecar UI. If needed, the helper should be backend-only and invoked through OpenWebUI.

## 7. UX Model

The UX stays inside OpenWebUI:

- user selects a broker reports scenario/model;
- scenario page/model description shows a short admissible-data frame;
- user creates a task chat;
- user uploads files through OpenWebUI;
- system responds with file list and readability status;
- unsupported files are refused or marked as out of MVP;
- user starts processing through a prompt, slash command or action;
- system returns staged response:
  - input summary;
  - extracted facts;
  - missing fields;
  - uncertain fields;
  - questions;
  - draft readiness status;
- user reviews and answers questions;
- system generates XLS/XLSX draft if export is available;
- generated result is explicitly labeled as a draft;
- user downloads and manually verifies the result.

Required visible labels:

- `Draft only. Requires specialist review.`
- `No automatic declaration filing.`
- `No FNS integration.`
- `Unsupported scans/photos/raster PDFs in MVP.`
- `Uncertain or missing data is not hidden.`

## 8. System Prompt / Instruction Model

The production prompt should be created later as a controlled content artifact. This PRD defines the skeleton only.

Skeleton:

```text
Role:
You assist customer specialists with broker report analysis and XLS/XLSX draft preparation for manual review.

Responsibility boundary:
You are not a tax advisor, tax platform, declaration filing system, FNS integration, CRM integration or final decision system.

Supported inputs:
Use only supported text-readable or machine-readable broker report files. If the input is a scan, photo, raster PDF or unsupported format, say that it is outside the current MVP or requires a separate OCR proof path.

Methodology:
Use the approved customer methodology from attached Knowledge and approved prompts. Do not invent rules when methodology is missing.

Completeness:
List required fields, present extracted values, mark missing values and ask concise questions.

Uncertainty:
Mark uncertain data. Do not hide gaps. Do not fabricate source values.

Output:
Return staged sections:
1. Input files and readability status
2. Extracted data summary
3. Missing or uncertain data
4. Questions to specialist
5. Draft calculation/preparation notes
6. XLS/XLSX draft readiness
7. Manual review warning

Export boundary:
Generate or request XLS/XLSX export only when the required fields and export path are available. If export is not proven, document the native gap.
```

Prompt content must avoid promising final tax correctness. It should force human review and make gaps visible.

## 9. Customer Input Requirements

Request from the customer before proof or implementation:

- Existing CloudCowork/Claude prompts.
- Current methodology.
- Current templates.
- 3-5 anonymized broker reports.
- At least one simple report and one table-heavy report, if available.
- XLS/XLSX broker report input if such reports are actually used.
- 1-2 correct XLS/XLSX output examples.
- Description of target XLS structure.
- Required fields.
- Date, number and currency formats.
- Rules for handling missing fields.
- Rules for manual verification.
- Acceptance criteria for the pilot.
- Named pilot reviewer or reviewer role.
- Allowed data classes by provider class.
- Whether foreign providers may process broker/tax/financial data.
- Retention requirements for uploaded files, chat history and generated drafts.
- Secure transfer method for test data.
- Whether samples must be manually anonymized before use.

Do not use real customer documents until data policy and transfer method are approved.

## 10. Data Policy And Safety

Risk classes:

- personal data;
- financial data;
- tax-related data;
- broker account data;
- uploaded files;
- generated drafts;
- chat history;
- logs and traces;
- foreign provider restrictions;
- accidental overclaiming;
- false confidence from LLM output;
- hidden spreadsheet data, formulas, comments and external references.

Required controls:

- approved provider/data policy before real samples;
- group-scoped scenario access;
- no provider keys in frontend;
- no secrets in prompts, Knowledge, reports or git;
- clear upload and retention policy;
- visible draft-only warning;
- mandatory manual review warning;
- refusal/limitation for scans and OCR inputs in MVP;
- no claim of final tax correctness;
- no automatic external submission.

Required visible warnings:

```text
This result is an XLS/XLSX draft for manual specialist review.
It is not final tax advice and not a final 3-НДФЛ declaration.
The system does not submit data to FNS and does not integrate with FNS.
Missing or uncertain data must be checked by a specialist.
Scans, photos and raster PDFs are outside the native-first MVP unless a separate OCR proof is approved.
```

## 11. Acceptance Criteria

A1. User can select a preconfigured OpenWebUI broker reports scenario/model.

A2. Scenario has dedicated instructions, scope and visible draft-only warnings.

A3. User can upload supported text-readable or machine-readable files.

A4. System explicitly refuses or limits scans, photos and raster/OCR inputs for MVP.

A5. Customer methodology and approved prompts are used.

A6. System shows extracted draft or structured summary.

A7. System shows missing and uncertain data.

A8. System asks specialist-facing questions when required data is missing.

A9. XLS/XLSX draft is generated, or the native gap is documented if generation is not proven.

A10. If XLS/XLSX generation is in MVP, the result opens in Excel/LibreOffice and is marked as draft.

A11. Result always states that manual specialist review is required.

A12. No FNS, CRM, task tracker or other external submission occurs.

A13. No separate user-facing sidecar UI is introduced.

A14. No deep OpenWebUI fork is required for MVP.

A15. OpenWebUI update-safety is preserved: native/config/extension path remains the default.

A16. Data policy, provider class and retention boundaries are documented before real customer data.

## 12. Open Questions

- Is a Workspace Model sufficient as the primary user entrypoint, or is an additional prompt/action launcher needed?
- Which deployed OpenWebUI version is the target for this pilot?
- Are Skills available and acceptable on that version?
- Should steps be launched by slash prompts, message Action, Tool call, or a combination?
- Does the target runtime provide a native artifact/download path suitable for XLSX?
- Can the existing message-level DOCX export pattern be reused as a product reference for XLSX download?
- Can XLSX generation be done without a separate helper?
- What XLS structure is expected?
- Which broker report formats are most important for the pilot?
- Are broker PDFs text-readable, table-heavy, scanned, or mixed?
- What fields are mandatory for the draft?
- What source mapping is required: file only, page/table, row, or cell-level reference?
- Which customer materials are still missing?
- What provider classes may process broker/tax/financial data?
- What counts as a successful pilot: time saved, fewer missed fields, specialist confidence, or export correctness?

## 13. Recommended Next Step

The next engineering checkpoint is a representative native/PDF customer rerun
when approved active source records or DCP are available, not another
prompt-only feasibility exercise.

It should test only the product-critical uncertainties that remain:

- current native/PDF input through the deployed provider factory;
- one bounded native table and one bounded text-layer PDF table path;
- exact linkage from every accepted value back to an original row/cell value;
- fail-closed behavior for an unapproved provider profile and unsupported image-only input;
- absence of raw document content from chat and Knowledge/RAG;
- explicit separation of local evidence from live evidence;
- whether an Action/Tool/Function is required for XLSX generation;
- whether XLSX can be returned as a safe downloadable artifact;
- whether existing DOCX export pattern can be adapted in principle;
- visible warning coverage.

Expansion from the bounded technical contour to the customer pilot should come
only after:

- customer methodology and prompts are received;
- anonymized samples are received through approved transfer;
- target XLS/XLSX expected outputs are received;
- provider/data policy is approved;
- retention and group access decisions are recorded;
- native feasibility proof identifies exact gaps.

## 14. Product Verdict

OpenWebUI Workspace can be treated as the main native product shell for this feature, but the feature should be framed as a preconfigured workflow scenario assembled from Workspace Model, system instructions, Prompts, Knowledge, optional Skills, group access and narrow extension points.

Without sidecar UI, the MVP can cover scenario selection, upload, methodology-guided analysis, structured draft, missing/uncertain data, specialist questions, manual review flow and draft labeling.

The current technical core already uses deterministic parsing, bounded table
projection, candidate-bound model interpretation, strict validation and source
mapping behind OpenWebUI. XLS/XLSX generation remains a separate product slice.
If native OpenWebUI cannot safely generate/download XLSX, the next acceptable
path is a minimal Tool/Function/Action or OpenAPI Tool Server/helper behind
OpenWebUI, not a separate user-facing UI and not a deep fork.

Synthetic and bounded technical proof may proceed without customer documents.
The full customer pilot and its export cannot be accepted until customer
prompts, methodology, approved representative reports, expected XLS/XLSX
outputs, required fields, review rules and provider/data policy are available.

## Sources Reviewed

Local project docs:

- [OPENWEBUI_CORPORATE_CHAT_PRD_1.md](../../prd/OPENWEBUI_CORPORATE_CHAT_PRD_1.md)
- [Stage 2 README](../README.md)
- [Stage 2 Context Index](../CONTEXT_INDEX.md)
- [Stage 2 Domain Map](../DOMAIN_MAP.md)
- [Contract Boundaries](../CONTRACT_BOUNDARIES.md)
- [Implementation Gates](../IMPLEMENTATION_GATES.md)
- [Extension-First Implementation Pattern](../EXTENSION_FIRST_IMPLEMENTATION_PATTERN.md)
- [OpenWebUI Native Capability Audit](../implementation/OPENWEBUI_NATIVE_CAPABILITY_AUDIT.md)
- [Broker Reports 3NDFL Blueprint](../blueprints/BROKER_REPORTS_3NDFL.blueprint.md)
- [Documents OCR Excel Blueprint](../blueprints/DOCUMENTS_OCR_EXCEL.blueprint.md)
- [Security Data Policy Blueprint](../blueprints/SECURITY_DATA_POLICY.blueprint.md)
- [Providers Model Catalog Blueprint](../blueprints/PROVIDERS_MODEL_CATALOG.blueprint.md)
- [Acceptance Matrix](../acceptance/ACCEPTANCE_MATRIX.md)
- [Test Data Requirements](../acceptance/TEST_DATA_REQUIREMENTS.md)
- [Stage 2 Unblocked Work Plan](../implementation/STAGE2_UNBLOCKED_WORK_PLAN.md)

Public OpenWebUI docs checked on 2026-07-04:

- https://docs.openwebui.com/features/workspace/
- https://docs.openwebui.com/features/workspace/models/
- https://docs.openwebui.com/features/workspace/prompts/
- https://docs.openwebui.com/features/workspace/knowledge/
- https://docs.openwebui.com/features/workspace/skills/
- https://docs.openwebui.com/features/extensibility/plugin/
- https://docs.openwebui.com/features/extensibility/plugin/tools/
- https://docs.openwebui.com/features/extensibility/plugin/functions/
- https://docs.openwebui.com/features/chat-conversations/data-controls/files/
- https://docs.openwebui.com/troubleshooting/rag/
- https://docs.openwebui.com/reference/api-endpoints/
- https://docs.openwebui.com/features/authentication-access/rbac/
- https://docs.openwebui.com/getting-started/advanced-topics/hardening/
