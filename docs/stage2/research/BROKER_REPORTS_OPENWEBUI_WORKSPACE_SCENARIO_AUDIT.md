# Broker Reports OpenWebUI Workspace Scenario Audit

Status: WORKSPACE_SCENARIO_AUDIT_READY
Date: 2026-07-06
Scope: Stage 2 Broker Reports / XLS NDFL, OpenWebUI Workspace / Workspace Model product shell

## 1. Executive Verdict

Recommended product model:

```text
Scenario = Workspace Model
Client Case = OpenWebUI chat/conversation + case_package artifact
Knowledge = approved methodology/reference/examples only
Chat files = uploaded customer source documents
Backend helper + artifact store = deterministic normalization and private/safe artifacts
Tools/Actions = deterministic operations and same-chat workflow triggers
Prompts/Skills = repeatable workflow steps and behavioral discipline
```

OpenWebUI Workspace is the configuration area for reusable scenario building blocks. It is not itself the client case, file archive, parser, normalizer, tax engine or artifact store.

## 2. Sources Checked

Local repo docs checked:

- `docs/stage2/prd/BROKER_REPORTS_XLS_NDFL_NATIVE_WORKFLOW_PRD.md`
- `docs/reports/2026-07-04/OPENWEBUI_BROKER_REPORTS_XLS_NDFL_NATIVE_WORKFLOW_PRD.report.md`
- `docs/stage2/blueprints/BROKER_REPORTS_DOCUMENT_NORMALIZATION_GATE.blueprint.md`
- `docs/stage2/ux/BROKER_REPORTS_OPENWEBUI_DOCUMENT_NORMALIZATION_UX.md`
- `docs/stage2/contracts/BROKER_REPORTS_DOCUMENT_NORMALIZATION_ARTIFACTS.v0_PROPOSAL.md`
- `docs/stage2/proof/BROKER_REPORTS_GATE1_DOCUMENT_NORMALIZATION_PROOF_PLAN.md`
- `docs/stage2/research/BROKER_REPORTS_GATE1_DOCUMENT_INTAKE_NORMALIZATION_RESEARCH.md`
- `docs/reports/2026-07-06/OPENWEBUI_BROKER_REPORTS_GATE1_DOCUMENT_NORMALIZATION_DOC_PACKET_COMPLETION.report.md`
- `docs/stage2/EXTENSION_FIRST_IMPLEMENTATION_PATTERN.md`
- `docs/stage2/implementation/OPENWEBUI_NATIVE_CAPABILITY_AUDIT.md`
- selected STT/DOCX Action, sidecar and artifact-store docs/reports.

Official OpenWebUI docs checked on 2026-07-06:

- Workspace: https://docs.openwebui.com/features/workspace/
- Workspace Models: https://docs.openwebui.com/features/workspace/models/
- Prompts: https://docs.openwebui.com/features/workspace/prompts/
- Knowledge: https://docs.openwebui.com/features/workspace/knowledge/
- Skills: https://docs.openwebui.com/features/workspace/skills/
- Tools: https://docs.openwebui.com/features/extensibility/plugin/tools/
- Functions: https://docs.openwebui.com/features/extensibility/plugin/functions/
- Action Functions: https://docs.openwebui.com/features/extensibility/plugin/functions/action/
- OpenAPI Tool Servers: https://docs.openwebui.com/features/extensibility/plugin/tools/openapi-servers/
- File Management: https://docs.openwebui.com/features/chat-conversations/data-controls/files/
- Folders & Projects: https://docs.openwebui.com/features/chat-conversations/chat-features/conversation-organization/
- Authentication & Access: https://docs.openwebui.com/features/authentication-access/
- RBAC Groups: https://docs.openwebui.com/features/authentication-access/rbac/groups/
- RBAC Permissions: https://docs.openwebui.com/features/authentication-access/rbac/permissions/
- API Endpoints: https://docs.openwebui.com/reference/api-endpoints/
- Essentials / Basic RAG: https://docs.openwebui.com/getting-started/essentials/

Runtime gap:

- Official docs are current product docs.
- Local reusable audit previously recorded deployed public baseline `0.9.6`.
- Some official docs describe behavior that may require a newer deployed runtime, for example Native tool calling default as of `v0.10.0`.
- Therefore every OpenWebUI capability in this audit is a product-design recommendation until the target runtime proof confirms it.

## 3. Workspace In This Product

OpenWebUI Workspace is best understood as an umbrella/configuration area for reusable AI building blocks:

- Models;
- Knowledge;
- Prompts;
- Skills;
- Tools.

For Broker Reports, Workspace is not a single business object named "client workspace". It is where the admin/AI-methodologist configures the scenario assets.

Use Workspace to manage:

- the `Broker Reports / XLS NDFL Draft Scenario` Workspace Model;
- scenario prompts;
- scenario skills/playbooks;
- approved methodology/reference Knowledge;
- approved tools/actions and their access;
- group-scoped sharing.

Do not use Workspace as:

- the customer case record;
- the raw customer file archive;
- the normalization engine;
- the tax calculation state;
- the private artifact store.

## 4. Workspace Model

Workspace Model is the recommended scenario entrypoint.

It should represent:

```text
Broker Reports / XLS NDFL Draft Scenario
```

It should bind:

- approved base model;
- scenario system prompt;
- approved Knowledge;
- Skills/playbooks if available in target runtime;
- allowed Tools/Actions;
- capability flags;
- group-scoped visibility.

It should not store:

- raw customer documents;
- private normalized slices;
- full source rows;
- case package state;
- final tax results.

The Workspace Model is the closest OpenWebUI-native equivalent of a product scenario. It is not the client case itself.

## 5. Client Case Model

Recommended model:

```text
Client Case = one OpenWebUI chat/conversation + broker_reports_case_package_ref
```

Optional organization layer:

```text
Folder/Project = grouping area for related chats, if enabled and proven in runtime
```

Why:

- a chat holds the same-chat working conversation, uploaded files, Gate 1 report and next-gate instructions;
- the case package holds stable refs, status and child artifact refs;
- folders/projects can group related chats and apply project context, but they do not replace case contracts or artifact storage;
- the case package can outlive UI naming changes and can be validated independently.

Recommended naming convention:

```text
Broker Reports - <safe client marker> - <tax year> - <case_group_id or pending>
```

The visible name must not contain full account numbers, passport/ID data, private paths or raw sensitive filenames.

## 6. Knowledge Boundary

Use Knowledge for approved reusable reference material:

- official FNS forms, instructions and electronic format docs;
- approved customer methodology;
- approved review rules;
- approved output examples and layout samples;
- broker help articles or public layout references after review;
- safe synthetic fixtures where explicitly labeled.

Do not automatically put these in Knowledge:

- raw customer broker reports;
- uploaded customer source files before explicit approval;
- private normalized text/table slices;
- full financial operation rows;
- private parser diagnostics;
- customer samples pending review.

Reason:

- Knowledge is a retrieval/RAG collection, not an audit-grade normalizer.
- Knowledge collections are reusable across chats and can be attached to models.
- Customer source documents are case-specific evidence, not reusable methodology.
- Gate 1 must first classify documents and decide whether they can be source evidence, methodology, layout-only or blocked.

Recommended rule:

```text
Knowledge = approved reusable references.
Chat files + artifact store = case-specific customer evidence.
```

## 7. Prompts, Skills, System Prompt And Tools

### System Prompt

Owns scenario behavior:

- role;
- boundaries;
- draft-only warning;
- no tax advice;
- no filing/FNS claim;
- no XLS/XLSX claim unless a later export path is proven;
- Knowledge boundary;
- safe reporting rules;
- "do not treat RAG as authoritative Gate 1 normalization";
- ask for missing/uncertain data instead of inventing facts.

### Prompts

Own repeatable user-visible steps:

- `/broker_gate1_normalize`;
- `/broker_gate1_show_report`;
- `/broker_select_case_group`;
- `/broker_next_gate_extract_source_facts`;
- `/broker_questions_to_specialist`.

Prompts are workflow entrypoints and forms. They are not deterministic parsing.

### Skills

Own reusable plain-text playbooks:

- broker reports review discipline;
- source-evidence vs methodology distinction;
- safe-output checklist;
- uncertainty/conflict handling;
- specialist-review discipline.

Skills are useful if the deployed runtime supports them and access is proven. If not, the same content belongs in system prompt, Prompts and Knowledge.

### Tools / Actions

Own deterministic operations:

- Gate 1 normalizer;
- later validators;
- future deterministic helpers if approved.

Tools/Actions must be admin-controlled. Regular users should not be able to create arbitrary tools/functions for this scenario.

## 8. Gate 1 Trigger Options

| Trigger | UX | File-id access | Same-chat reporting | Complexity | Runtime proof requirement | Privacy/access risk |
| --- | --- | --- | --- | --- | --- | --- |
| Slash prompt | User types `/broker_gate1_normalize`. | Weak unless prompt can pass selected file refs to a tool/action. | Good as chat text. | Low. | Prove it can identify current chat files or delegate to a tool. | User may think prompt alone normalized files. |
| Action button | User clicks "Normalize Documents". | Strong if Action receives `body.files` or message/chat file context. | Strong; Actions can emit status and return content. | Medium. | Prove file ids/bytes handoff and action visibility. | Action code is privileged and must be reviewed. |
| Workspace Tool | Model calls normalizer after user intent. | Strong if tool receives file ids from message/context. | Good via model response/tool result. | Medium. | Prove model-attached tool access and file refs. | Tool access is per-user; tool code may be powerful. |
| OpenAPI Tool Server | OpenWebUI calls backend helper over HTTP. | Depends on passed refs. | Good through tool result or Action wrapper. | Medium-high. | Prove auth, refs, bytes access and response projection. | Must protect helper auth and avoid raw content leaks. |
| Manual chat command | User writes natural language. | Weak. | Good. | Low. | Not enough as only trigger. | Hidden/magic behavior and accidental overreach. |

Recommended route:

```text
Action or Workspace Tool as primary trigger
slash prompt as fallback
OpenAPI Tool Server/backend helper for parser-heavy normalization
```

## 9. Access And RBAC

OpenWebUI access model is additive. Design with least privilege:

- keep global defaults minimal;
- create a dedicated Broker Reports pilot group;
- share the Workspace Model only to that group;
- share Prompts, Skills, Knowledge and Tools to the same group;
- do not make raw customer resources public;
- restrict Workspace Tools/Functions creation/import to trusted admins;
- disable direct user-added tool servers unless specifically approved;
- verify that model-attached tools/knowledge are visible to the user, because attached resources still require user access.

Backend helper must enforce its own checks:

- caller identity;
- user/group authorization;
- chat/case context;
- file refs belong to the current approved context;
- artifact refs are opaque and insufficient by themselves;
- private slices require approved access;
- no raw filenames/private paths in safe report;
- no customer docs written to repository.

## 10. Artifact Ownership

| Owner | Owns | Does not own |
| --- | --- | --- |
| OpenWebUI | chat UX, file upload UX, selected scenario model, same-chat report display | private normalization store, parser diagnostics, tax logic |
| Workspace Model | scenario entrypoint, system behavior, attached resources/capabilities | client case state, raw docs, artifacts |
| Chat/conversation | working context, uploaded customer files, visible Gate reports | reusable methodology, private slices, canonical status |
| Case package | stable case id, selected `case_group_id`, refs, status, safety flags | raw files, full child artifacts |
| Backend helper | normalization run, parser work, technical profiles, private slices | user-facing UI, final tax calculation |
| Artifact store | private artifacts, safe refs, retention/access policy | OpenWebUI model selection, chat UX |
| Knowledge | approved references and methodology | raw customer source package |

Existing STT artifact-store work is a useful pattern: opaque refs, factory-first store access, typed access errors and private storage. It is not yet a Broker Reports artifact store; Gate 1 must prove its own storage/access boundary.

## 11. Runtime Assumptions To Prove

- Exact OpenWebUI deployed version.
- Workspace Model visibility and group access.
- Base model access under the restricted Workspace Model.
- Prompt sharing and slash command availability.
- Skill availability and model binding in the deployed runtime.
- Knowledge attachment and per-user access behavior.
- Chat file upload behavior and file id shape.
- Whether Action receives uploaded file refs.
- Whether Tool/OpenAPI Tool Server can receive file refs safely.
- Whether the helper can read original bytes under approved boundary.
- Whether same-chat Action/Tool result can show progress and safe report.
- Whether folder/project context should be used for client grouping.
- Whether native function calling changes Knowledge behavior for the selected model.

## 12. Gaps

- Target runtime may lag behind current official docs.
- Workspace itself is not a full case/project record.
- Folder/project behavior is useful but not yet accepted as canonical case model.
- File upload/RAG is not an authoritative normalization pipeline.
- Knowledge can blur reference docs and customer source docs if policy is weak.
- Action vs Tool vs OpenAPI trigger is still runtime-proof gated.
- Artifact retention/access rules are not finalized.
- No production Broker Reports artifact store exists yet.

## 13. Final Recommendation

Use this product model for the next proof:

```text
Workspace / Workspace Model:
Broker Reports / XLS NDFL Draft Scenario

Client case:
OpenWebUI chat/conversation + case_package_ref

Knowledge:
official refs + approved methodology + approved examples

Prompts:
workflow entrypoints

Skills:
review discipline and safe-output playbooks

Tools/Actions:
Gate 1 normalizer trigger and later deterministic helpers

Backend helper:
normalization and private/safe artifact creation

Artifact store:
private artifacts, safe refs, retention/access policy
```

## 14. Status

```text
WORKSPACE_SCENARIO_AUDIT_READY
WORKSPACE_MODEL_RECOMMENDED_AS_SCENARIO_ENTRYPOINT
CLIENT_CASE_AS_CHAT_PLUS_CASE_PACKAGE_RECOMMENDED
KNOWLEDGE_FOR_APPROVED_METHODOLOGY_ONLY
RAW_CUSTOMER_DOCS_NOT_KNOWLEDGE
GATE1_TRIGGER_ACTION_OR_TOOL_TO_BE_PROVEN
READY_FOR_WORKSPACE_RUNTIME_PROOF_REVIEW
```
