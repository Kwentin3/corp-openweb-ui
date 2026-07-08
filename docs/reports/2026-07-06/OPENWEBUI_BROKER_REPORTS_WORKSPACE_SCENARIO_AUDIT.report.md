# OpenWebUI Broker Reports Workspace Scenario Audit Report

Status: WORKSPACE_SCENARIO_AUDIT_READY
Date: 2026-07-06
Scope: Stage 2 Broker Reports / XLS NDFL Workspace / Workspace Model research-audit

## 1. What Was Done

Created a docs-only audit package clarifying how Broker Reports should use OpenWebUI Workspace, Workspace Model, Prompts, Skills, Knowledge, chat files, Tools/Actions and backend artifacts.

Created:

- `docs/stage2/research/BROKER_REPORTS_OPENWEBUI_WORKSPACE_SCENARIO_AUDIT.md`
- `docs/stage2/blueprints/BROKER_REPORTS_OPENWEBUI_WORKSPACE_PRODUCT_MODEL.blueprint.md`
- `docs/stage2/ux/BROKER_REPORTS_OPENWEBUI_WORKSPACE_AND_CLIENT_CASE_UX.md`
- `docs/stage2/config/BROKER_REPORTS_OPENWEBUI_WORKSPACE_CONFIGURATION.v0_PROPOSAL.md`
- `docs/reports/2026-07-06/OPENWEBUI_BROKER_REPORTS_WORKSPACE_SCENARIO_AUDIT.report.md`

No code, runtime, OpenWebUI resources, Knowledge, Prompts, Skills or customer documents were changed.

## 2. Was Workspace Recommended Earlier?

Yes.

Previous PRD and Gate 1 docs already recommended OpenWebUI as the user-facing shell and Workspace Model as the scenario entrypoint.

This audit refines the recommendation:

```text
Workspace / Workspace Model = scenario and reusable configuration shell
Chat/conversation + case package = specific client case
```

## 3. What Workspace Should Cover

Workspace should cover reusable scenario assets:

- Workspace Model;
- system prompt;
- approved Knowledge;
- Prompts;
- Skills if runtime-proven;
- allowed Tools/Actions;
- group-scoped access.

Workspace should make the scenario easy to select and hard to misuse.

## 4. What Workspace Should Not Cover

Workspace should not cover:

- client case state;
- raw customer document archive;
- private normalized slices;
- deterministic parsing;
- artifact retention/access policy;
- tax calculation;
- declaration generation;
- XLS/XLSX generation;
- FNS filing.

## 5. What Is The Client Case?

Recommended:

```text
Client Case = one OpenWebUI chat/conversation + broker_reports_case_package_ref
```

Optional:

```text
Folder/project = grouping layer if runtime-proofed, not canonical case storage
```

The case package remains the stable proof workflow record.

## 6. Where Customer Uploaded Documents Live

Customer uploaded documents live as chat files in the case chat and as private refs visible to the approved normalizer/helper.

They do not automatically live in Knowledge.

They must not be copied into the repository.

## 7. Where Methodology And Reference Docs Live

Approved methodology/reference docs live in Knowledge:

- official requirements;
- approved customer methodology;
- approved examples;
- review rules;
- safe synthetic fixtures.

Knowledge is not the raw customer source package.

## 8. Where Normalized Artifacts Live

Normalized artifacts live in the backend helper/artifact store boundary:

- normalization run;
- safe inventory;
- technical profile;
- private text/table slices;
- taxonomy candidates;
- blockers;
- safe report projection.

The OpenWebUI chat gets the safe report, not the private artifact payload.

## 9. How Gate 1 Starts

Recommended:

```text
Action or Workspace Tool as primary Gate 1 trigger
slash prompt as fallback
OpenAPI Tool Server/backend helper for parser-heavy normalization
```

Runtime proof must confirm:

- trigger can see uploaded file refs;
- helper can access original bytes under approved boundary;
- safe report returns to same chat;
- no raw filenames/private paths/full rows leak.

## 10. How UX Stays OpenWebUI-Native

The user:

1. selects Broker Reports Workspace Model;
2. creates a client/tax-year chat;
3. uploads files in OpenWebUI;
4. triggers Normalize Documents;
5. receives safe report in the same chat;
6. selects `case_group_id`;
7. starts next gate from the same OpenWebUI workflow.

No separate user-facing sidecar UI is needed.

## 11. Runtime Assumptions To Prove

- Exact deployed OpenWebUI version.
- Group-scoped Workspace Model visibility.
- Base model access through the scenario model.
- Prompt sharing and slash command availability.
- Skill availability or fallback.
- Knowledge access for attached KBs.
- Chat file upload and file id shape.
- Action/Tool access to files.
- OpenAPI Tool Server/helper auth and refs.
- Same-chat status/report behavior.
- Folder/project behavior if used.
- Additive RBAC does not accidentally widen access.

## 12. What To Do Next

Proceed to a small Workspace runtime proof before implementing Gate 1 code:

```text
Admin configures synthetic Broker Reports Workspace Model
-> inside user sees scenario/resources
-> outside user does not
-> inside user uploads synthetic files
-> Action/Tool receives file refs
-> helper stub returns safe report
-> same chat receives report
```

Only after this should the Gate 1 normalizer implementation proof start.

## 13. Constraints Observed

- Code was not changed.
- Runtime was not changed.
- OpenWebUI was not populated.
- Knowledge/Prompts/Skills were not loaded.
- Customer docs were not copied or committed.
- OCR was not performed.
- Tax calculation was not performed.
- Source-fact extraction was not performed.
- XLS/XLSX generation was not performed.
- Production implementation code was not written.
- Separate user-facing sidecar UI was not created.
- Secrets, keys and environment values were not read or printed.

## 14. Final Statuses

```text
WORKSPACE_SCENARIO_AUDIT_READY
WORKSPACE_MODEL_RECOMMENDED_AS_SCENARIO_ENTRYPOINT
CLIENT_CASE_AS_CHAT_PLUS_CASE_PACKAGE_RECOMMENDED
KNOWLEDGE_FOR_APPROVED_METHODOLOGY_ONLY
RAW_CUSTOMER_DOCS_NOT_KNOWLEDGE
GATE1_TRIGGER_ACTION_OR_TOOL_TO_BE_PROVEN
READY_FOR_WORKSPACE_RUNTIME_PROOF_REVIEW
```

## 15. Official Sources Checked

- https://docs.openwebui.com/features/workspace/
- https://docs.openwebui.com/features/workspace/models/
- https://docs.openwebui.com/features/workspace/prompts/
- https://docs.openwebui.com/features/workspace/knowledge/
- https://docs.openwebui.com/features/workspace/skills/
- https://docs.openwebui.com/features/extensibility/plugin/tools/
- https://docs.openwebui.com/features/extensibility/plugin/functions/
- https://docs.openwebui.com/features/extensibility/plugin/functions/action/
- https://docs.openwebui.com/features/extensibility/plugin/tools/openapi-servers/
- https://docs.openwebui.com/features/chat-conversations/data-controls/files/
- https://docs.openwebui.com/features/chat-conversations/chat-features/conversation-organization/
- https://docs.openwebui.com/features/authentication-access/
- https://docs.openwebui.com/features/authentication-access/rbac/groups/
- https://docs.openwebui.com/features/authentication-access/rbac/permissions/
- https://docs.openwebui.com/reference/api-endpoints/
