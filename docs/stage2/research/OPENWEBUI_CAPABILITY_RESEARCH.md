# OpenWebUI Capability Research

## 1. Question

Какие native capabilities deployed OpenWebUI реально дает для Stage 2: workspaces, prompts, knowledge, groups/RBAC, STT, web-search, files, analytics, retention and admin surfaces?

## 2. Why it matters for PRD-1

PRD-1 is native-first. Implementation must not start from fork/gateway/custom module without evidence.

## 3. Current assumptions

- PRD-0 deployment was pinned for stability.
- PRD-1 capability map may be newer than deployed runtime.
- Some features may require update or controlled migration.

## 4. What to verify

- Deployed version.
- Groups/RBAC behavior.
- Workspace Models/Prompts/Knowledge.
- File upload limits and retention.
- Native STT configuration.
- Native web-search configuration.
- Analytics views and export.
- Admin visibility and chat deletion controls.

## 5. Sources to check

- Deployed OpenWebUI Admin UI.
- Official OpenWebUI docs for the deployed version.
- PRD-0 runbooks and reports.
- Release notes if update is required.

## 6. Test plan / proof plan

Use read-only/admin-safe checks first. Create test users only during approved implementation planning, not now.

## 7. Risks

- Docs/runtime version mismatch.
- Native permission gaps.
- Update needed before Stage 2.

## 8. Decision options

- Native configuration sufficient.
- Native with policy/workarounds.
- Controlled update required.
- Minimal custom module/fork-slice required.

## 9. Recommended next step

Schedule capability audit before implementation planning.

## 10. Status

Planned, not verified.
