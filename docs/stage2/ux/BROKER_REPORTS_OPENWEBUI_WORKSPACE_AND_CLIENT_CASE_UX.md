# Broker Reports OpenWebUI Workspace And Client Case UX

Status: WORKSPACE_CLIENT_CASE_UX_READY
Date: 2026-07-06
Scope: Stage 2 Broker Reports / XLS NDFL, Workspace scenario and client case UX

## 1. UX Principle

The user stays in OpenWebUI.

The user should experience Broker Reports as a prepared scenario, not as a generic empty chat and not as a separate sidecar UI.

Plain instruction:

```text
Create a separate chat for each client and tax year.
Do not mix documents from different clients in one chat.
```

## 2. Admin Setup Flow

1. Admin creates or publishes a Workspace Model:

```text
Broker Reports / XLS NDFL Draft Scenario
```

2. Admin shares it only with the approved Broker Reports group.
3. Admin attaches approved Knowledge:

- official references;
- approved customer methodology;
- approved examples;
- review rules.

4. Admin attaches approved Skills if supported by runtime.
5. Admin attaches approved Prompts.
6. Admin attaches only approved Tools/Actions.
7. Admin verifies that raw customer documents are not in Knowledge.

This setup is configuration/proof work, not code.

## 3. User Scenario Flow

1. User selects `Broker Reports / XLS NDFL Draft Scenario`.
2. User creates a new chat for one client/tax year.
3. User uploads documents for that case only.
4. User runs:

```text
Normalize Documents
```

or fallback:

```text
/broker_gate1_normalize
```

5. User sees progress/status.
6. User receives a safe normalization report in the same chat.
7. User selects a `case_group_id`.
8. User starts the next gate:

```text
Extract source facts from selected case group
```

The next gate is not part of Gate 1.

## 4. What "Scenario" Means To User

User sees scenario as:

- a named model/scenario in model picker;
- clear description;
- short warning frame;
- dedicated prompts/actions;
- attached approved references;
- same-chat report.

Suggested description:

```text
Draft workflow for broker report document intake and later review.
Gate 1 normalizes uploaded files and returns a safe package report.
It does not calculate tax, create a declaration, generate XLS/XLSX or file with FNS.
Manual specialist review is required.
```

## 5. What "Client Case" Means To User

Client case is the chat plus case package reference.

User-facing convention:

```text
One client + one tax year + one document package = one chat.
```

Recommended chat title pattern:

```text
Broker Reports - <safe client marker> - <tax year> - <status>
```

Do not put these in chat title:

- full personal name if avoidable;
- full account number;
- INN/passport/ID data;
- phone/email/address;
- private file path.

## 6. Optional Folder/Project UX

If Folders/Projects are enabled and runtime-proofed:

- use a folder/project to group several safe client chats;
- use folder/project context for broad work organization;
- do not use one folder/project as the canonical case record;
- do not mix client files across chats;
- keep `case_package_ref` as the proof workflow record.

Example:

```text
Folder: Broker Reports Pilot
  Chat: Client marker A / 2024 / Gate 1
  Chat: Client marker B / 2024 / Gate 1
```

## 7. Knowledge UX Boundary

The user should understand:

```text
Knowledge contains approved methodology and reference docs.
Uploaded files in this chat are customer source documents for this case.
```

Do not present Knowledge as:

- customer file inbox;
- broker report archive;
- automatic parser;
- storage for private normalized slices.

If a user asks to add customer source documents to Knowledge, the assistant should respond:

```text
Customer source documents are not added to Knowledge automatically.
They first need intake classification, privacy review and explicit approval.
```

## 8. Prompt And Skill UX

Prompts should appear as workflow commands:

- `/broker_gate1_normalize`
- `/broker_gate1_show_report`
- `/broker_select_case_group`
- `/broker_next_gate_source_facts`

Skills should stay invisible or lightly visible as scenario discipline:

- safe output;
- review-only status;
- source evidence boundary;
- methodology gap handling.

The user should not need to understand internal schema names to run the workflow.

## 9. Gate 1 Trigger UX

Recommended:

```text
Action/Tool-triggered normalization from chat
slash prompt as fallback
```

Expected visible progress:

```text
queued
reading_files
profiling_documents
building_slices
classifying_documents
checking_blockers
reporting
completed_with_blockers
```

Expected report:

- file counts;
- recognized containers;
- source-evidence candidates;
- output/calculation artifacts;
- ZIP/raster/unknown review blockers;
- available `case_group_id`;
- recommended next step.

## 10. Example UX Transcript

```text
User:
Нормализуй документы клиента

Assistant/tool:
Запускаю Gate 1 normalization для файлов, загруженных в этот чат.
Проверяю file refs, техническую читаемость и safe document ids.

Assistant:
Gate 1 completed_with_blockers.

Найдено 63 файла.
PDF: 31, CSV: 2, XLSX: 2, TXT/HTML: 4, ZIP: 24.

Source-evidence candidates:
- broker reports: 7
- operations tables: 8
- dividends reports: 7
- fees reports: 2

Review/output artifacts:
- tax base calculations: 5
- calculation templates: 2

Blockers:
- 24 ZIP require unpack/review policy
- 4 raster PDF require OCR/review
- unknown_or_needs_review documents are blocked for source-fact extraction

Available case groups:
- case_group_001: needs_review
- case_group_002: needs_review, recommended proof candidate
- case_group_003: needs_review
- case_group_004: partial
- case_group_005: needs_review
- case_group_006: needs_review

Recommended next step:
Select case_group_002, then run source-fact extraction only after review scope is approved.

Boundary:
Gate 1 did not calculate tax, extract source facts through LLM, create a declaration, generate XLS/XLSX or file with FNS.
```

The example uses safe aggregate counts only.

## 11. User Error Prevention

The UX should prevent:

- mixing different clients in one chat;
- assuming Workspace equals client case;
- assuming Knowledge contains raw case files;
- assuming Gate 1 calculated tax;
- assuming a safe report is a final tax result;
- uploading customer files to reusable Knowledge without review.

## 12. Acceptance Signals

UX is acceptable when:

- allowed user sees the scenario;
- outside user does not see the scenario;
- user can create a dedicated case chat;
- user can upload files in the chat;
- explicit Gate 1 trigger exists;
- same-chat safe report appears;
- report uses `case_group_id` and `document_id`, not raw filenames;
- next gate starts from selected `case_group_id`;
- no separate user-facing UI appears.

## 13. Status

```text
WORKSPACE_CLIENT_CASE_UX_READY
WORKSPACE_MODEL_AS_SCENARIO_UX
CLIENT_CASE_AS_SEPARATE_CHAT_UX
KNOWLEDGE_REFERENCE_BOUNDARY_VISIBLE
READY_FOR_WORKSPACE_RUNTIME_PROOF_REVIEW
```
