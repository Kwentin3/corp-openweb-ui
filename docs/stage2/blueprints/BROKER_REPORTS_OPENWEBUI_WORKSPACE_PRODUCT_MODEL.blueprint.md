# Broker Reports OpenWebUI Workspace Product Model Blueprint

Status: WORKSPACE_PRODUCT_MODEL_BLUEPRINT_READY
Date: 2026-07-06
Scope: Stage 2 Broker Reports / XLS NDFL Workspace/Scenario product model

## 1. Current Problem And Risk

The Gate 1 document normalization pack already selected the OpenWebUI-native direction:

```text
OpenWebUI chat/project
-> uploaded broker/customer files
-> explicit Normalize Documents trigger
-> backend-only normalizer
-> safe/private artifacts
-> safe report in same chat
```

The remaining product risk is conceptual drift:

- treating Workspace as a client case;
- treating Knowledge as customer-source storage;
- treating RAG as a normalizer;
- treating Prompts as deterministic parser logic;
- treating OpenWebUI chat history as the artifact store;
- letting a backend helper become a separate customer-facing UI.

This blueprint fixes the ownership model before runtime proof.

## 2. Target Product Model

```text
Workspace / Workspace Model:
Broker Reports / XLS NDFL Draft Scenario

Client case:
OpenWebUI chat/conversation + case_package_ref

Knowledge:
official refs + approved methodology + examples

Prompts:
workflow entrypoints

Skills:
playbooks and operator discipline

Tools/Actions:
Gate 1 normalizer and later deterministic helpers

Backend helper:
normalization and artifacts

Artifact store:
private/safe artifacts
```

## 3. Domain And Ownership Map

| Domain | Owner | Responsibilities | Non-responsibilities |
| --- | --- | --- | --- |
| Workspace | Admin/AI-methodologist | Reusable scenario assets: models, prompts, skills, knowledge, tools. | Client case state, raw source archive, normalization engine. |
| Workspace Model | Admin/AI-methodologist | Scenario entrypoint, base model binding, system prompt, attached resources, allowed capabilities. | Customer file storage, private artifacts, tax calculation. |
| Chat/conversation | User/specialist | One client/tax-year working context, uploads, same-chat Gate reports, next actions. | Canonical artifact state, reusable methodology. |
| Folder/project | User/admin if runtime-proven | Optional grouping of related chats and project-level context. | Replacement for case package or artifact store. |
| Case package | Backend/proof workflow | Stable case id, case status, `case_group_id`, refs between artifacts. | Embedded raw files or full child artifacts. |
| Knowledge | Admin/AI-methodologist | Approved reference/methodology/examples. | Raw customer source docs by default. |
| Prompts | Admin/AI-methodologist | Repeatable slash-command steps and forms. | Deterministic file parsing. |
| Skills | Admin/AI-methodologist | Plain-text review discipline and reusable playbooks. | Executable code or parser logic. |
| Tools/Actions | Admin/backend | Deterministic operations and explicit trigger UX. | Arbitrary user customization. |
| Backend helper | Backend | Parser dependencies, byte access, normalization, safe/private artifact split. | Customer-facing UI. |
| Artifact store | Backend | Private slices, technical profiles, safe refs, retention/access policy. | OpenWebUI chat UX. |

## 4. Boundary Contracts

### Scenario Contract

```json
{
  "scenario_id": "broker_reports_xls_ndfl_draft",
  "workspace_model_id": null,
  "allowed_group_refs": [],
  "knowledge_refs": [],
  "prompt_refs": [],
  "skill_refs": [],
  "tool_or_action_refs": [],
  "capability_flags": {}
}
```

This is a configuration concept, not a production schema yet.

### Client Case Contract

Use the existing case package proposal:

- `broker_reports_case_package_v0_proposal`;
- one `case_id`;
- optional `case_group_ref`;
- refs to Gate 1 and later artifacts;
- safety flags.

Recommended UI binding:

```json
{
  "case_id": null,
  "openwebui_chat_ref_private": null,
  "case_package_ref": null,
  "selected_case_group_id": null
}
```

### Knowledge Boundary Contract

```text
Allowed in Knowledge:
- official requirements;
- approved methodology;
- approved examples;
- safe synthetic fixtures;
- reviewed public layout samples.

Blocked from Knowledge by default:
- raw customer source docs;
- private normalized slices;
- full financial operation rows;
- customer samples pending review.
```

### Tool/Action Boundary Contract

Tool/Action inputs should be refs, not raw rows:

```json
{
  "operation": "broker_reports_gate1_normalize",
  "chat_ref_private": null,
  "file_refs_private": [],
  "case_package_ref": null
}
```

Tool/Action chat-visible output should be a safe report projection only.

## 5. Workspace Model As Scenario Entrypoint

The Workspace Model should be named:

```text
Broker Reports / XLS NDFL Draft Scenario
```

It owns:

- scenario description;
- base model selection;
- system prompt;
- bound Knowledge;
- bound Skills where available;
- allowed Tools/Actions;
- capability flags;
- group visibility.

It must not own:

- customer documents;
- private slices;
- parser diagnostics;
- source facts;
- ledgers;
- tax calculation;
- XLS/XLSX generation.

## 6. Client Case As Chat Plus Case Package

Use one separate chat per client/tax-year/package.

User-facing instruction:

```text
Create a separate chat for each client and tax year.
Do not mix documents from different clients in one chat.
```

The chat is the user's working surface. The case package is the durable proof workflow record.

Optional folder/project use:

- create a folder/project for a client only if the runtime proof confirms project settings and access behavior;
- keep one chat per tax year/package even inside the folder;
- do not let project/folder context replace `case_package_ref`.

## 7. Knowledge Model

Recommended Knowledge collections:

- `Broker Reports Official Requirements`
- `Broker Reports Approved Customer Methodology`
- `Broker Reports Approved Examples`
- `Broker Reports Review Rules`

Do not attach raw customer upload Knowledge collections to the scenario model by default.

Customer methodology can enter Knowledge only after:

- customer approval;
- privacy review;
- source/version recorded;
- access group assigned.

Customer source files remain chat uploads and Gate artifacts.

## 8. Prompts And Skills Model

Prompts:

- `/broker_gate1_normalize`
- `/broker_gate1_show_report`
- `/broker_select_case_group`
- `/broker_next_gate_source_facts`
- `/broker_questions_to_specialist`

Skills:

- `Broker Reports Review Discipline`
- `Broker Reports Safe Output Rules`
- `Broker Reports Source Evidence Boundary`
- `Broker Reports Methodology Gap Handling`

If Skills are not runtime-proven, put their content into system prompt, Prompts and Knowledge.

## 9. Tools And Actions Model

Primary Gate 1 trigger candidates:

1. Action button: explicit user control and good same-chat status UX if file refs are visible.
2. Workspace Tool: model-mediated deterministic operation if tool access and file refs are proven.
3. OpenAPI Tool Server: preferred helper boundary if parser dependencies live outside OpenWebUI.
4. Slash prompt fallback: acceptable launcher, not enough as authoritative normalizer.

No hidden magic trigger as the only UX.

## 10. Backend Helper And Artifact Store

The helper owns:

- original-byte access under approved boundary;
- SHA-256;
- MIME/container detection;
- PDF/XLSX/CSV/TXT/DOCX profiles;
- ZIP member inventory;
- private text/table slices;
- taxonomy candidates;
- blockers;
- safe report projection.

The artifact store owns:

- private registry;
- private slices;
- technical profiles;
- safe refs;
- retention;
- access checks;
- typed refusal on access failure.

Existing STT artifact-store implementation is a reusable pattern, not an already approved Broker Reports implementation.

## 11. What Is Not A Workspace Responsibility

Workspace must not be responsible for:

- storing raw customer source packages as reusable knowledge;
- byte-level hashing;
- deterministic parsing;
- private normalized slices;
- source-fact extraction;
- intermediate ledgers;
- tax calculation;
- declaration generation;
- XLS/XLSX generation;
- retention and access policy for private artifacts;
- backend helper authorization.

## 12. Proposed Runtime Proof Slices

Slice 1: Workspace Model setup proof.

- restricted model visible to allowed group;
- hidden from outside group;
- base model access works;
- system prompt contains boundaries.

Slice 2: Knowledge boundary proof.

- approved reference Knowledge attached;
- raw customer docs not attached;
- user access to attached KB is proven.

Slice 3: Prompt/Skill proof.

- slash prompts visible to allowed group;
- Skills available or fallback recorded.

Slice 4: Gate 1 trigger proof.

- Action or Tool sees file refs;
- OpenAPI/helper path receives refs;
- same-chat safe report returns.

Slice 5: Artifact ref proof.

- case package receives `normalization_run_id`;
- private artifact refs are opaque;
- safe report does not leak raw filenames/paths.

## 13. Risks

- Official docs may describe a newer OpenWebUI than deployed.
- Group permissions are additive; a broad default can bypass intended scoping.
- Attached tools/knowledge still require user access; model sharing alone is insufficient.
- Folders/projects may tempt users to mix multiple clients.
- Knowledge can become an accidental raw-customer-data repository.
- Actions/Tools execute privileged code and need admin-only governance.
- Artifact refs may be mistaken for access grants unless backend checks context.

## 14. Deferred Work

- production implementation code;
- loading OpenWebUI resources;
- real customer document proof;
- OCR provider decision;
- source-fact extraction;
- tax calculation;
- declaration/XLSX generation;
- separate user-facing sidecar UI.

## 15. Status

```text
WORKSPACE_PRODUCT_MODEL_BLUEPRINT_READY
WORKSPACE_MODEL_RECOMMENDED_AS_SCENARIO_ENTRYPOINT
CLIENT_CASE_AS_CHAT_PLUS_CASE_PACKAGE_RECOMMENDED
RAW_CUSTOMER_DOCS_NOT_KNOWLEDGE
READY_FOR_WORKSPACE_RUNTIME_PROOF_REVIEW
```
