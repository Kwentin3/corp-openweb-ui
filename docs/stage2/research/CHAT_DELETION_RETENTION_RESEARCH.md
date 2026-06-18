# Chat Deletion Retention Research

## 1. Question

Can Stage 2 prevent normal users from deleting work chats, or at least preserve work evidence safely?

## 2. Research status

Status: researched from official OpenWebUI docs on 2026-06-18.

Result type: native permission route appears likely; deployed runtime proof is required.

## 3. Findings

- OpenWebUI RBAC docs describe granular permissions and explicitly use "Can Delete Chats" as an example permission.
- Permission logic is additive. If a user receives delete permission through any role/default/group path, the effective permission may still allow deletion.
- Public chat sharing and group access are separately permissioned. Sharing controls do not automatically equal retention/audit controls.
- PRD-0 has backup/retention for deployment data, but backup retention is not the same as user-level no-delete policy.

## 4. Practical interpretation

Native no-delete should be tested first:

- default user permissions: chat deletion disabled;
- admin remains able to delete/administer;
- no group grants delete back accidentally;
- user UI and API behavior both checked;
- shared work chat behavior checked.

If this works in deployed version, Stage 2 can satisfy the no-delete check without fork.

Key distinction:

No Delete is not Retention. Retention is not Audit. Audit is not immutable archive.

- No Delete: normal users cannot delete chats through UI/API.
- Retention: chats, files and transcripts are kept for a defined period.
- Backup: operational restore capability, not a user-facing audit trail.
- Audit log: records actions/access.
- Immutable archive: separate legal/audit-grade system and not Practical Stage 2 unless separately approved.

## 5. Fallback options

1. Native permission setting.
   - Preferred if runtime proof passes.
   - Low upgrade risk.

2. Policy + backup/export retention.
   - Documents retention expectation and preserves periodic backups.
   - Does not truly block user deletion in UI.

3. Custom patch or server-side guard.
   - Stronger enforcement.
   - Higher OpenWebUI upgrade risk and should be separate ADR/future slice.

## 6. Risks

- Docs/current-version mismatch with pinned v0.9.6.
- Additive permissions can re-enable deletion through another group.
- UI-only tests can miss API delete endpoints.
- Backup can restore data only at coarse granularity and may include secrets/sensitive data.

## 7. Recommended next step

Run a non-admin test user proof after staging/admin approval:

- create chat;
- attempt UI delete;
- attempt API delete if API path is available to the user;
- add/remove group permissions;
- confirm admin override behavior;
- record exact OpenWebUI setting names;
- document retention policy questions: chats, files, transcripts, backup horizon and whether legal/audit archive is required.

## 8. Sources

- https://docs.openwebui.com/features/authentication-access/rbac/
- https://docs.openwebui.com/features/authentication-access/rbac/permissions/
- https://docs.openwebui.com/features/chat-conversations/chat-features/chatshare/

## 9. Status

Research complete. Runtime proof required before marking PRD-1 no-delete as implementable natively.
