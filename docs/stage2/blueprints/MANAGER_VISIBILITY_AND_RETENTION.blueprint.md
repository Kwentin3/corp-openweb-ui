# Manager Visibility And Retention Blueprint

## 1. Purpose

Спланировать доступ руководителей к рабочим чатам, retention and no-delete policy without exposing
all personal chats.

## 2. PRD-1 requirements covered

- Customer wants manager access to employee chats early.
- Access must be work-chat visibility within groups/workspaces.
- Need native OpenWebUI check.
- Need chat deletion restriction check.
- If native unavailable: policy/audit/backup/export/minimal customization options.

## 3. Current known context

PRD-0 did not include manager visibility. PRD-1 requires privacy/security decision. Руководитель не
должен видеть вообще все личные/черновые чаты automatically.

Manager Visibility is a policy/security-controlled capability. It is not just a permission toggle.

No Delete is not Retention. Retention is not Audit. Audit is not immutable archive.

## 4. Target user workflow

Employee creates work chat in approved workspace. Manager of that group can see approved work chats
under policy. Employee knows the rule. Admin can audit/export or enforce retention according to
selected approach.

## 4.1. Manager visibility boundary

Controlled manager visibility means:

- manager sees only assigned group/workspace chats approved as work chats;
- no hidden access to unrelated personal/draft chats;
- employee awareness / policy notice is required;
- admin visibility is defined separately;
- fallback options include explicit shared workspace model, export/audit, reporting, policy-only,
  minimal customization or deferred custom supervisory view.

Runtime proof must create test users/groups and verify:

- manager sees approved work chats for assigned group/workspace;
- manager does not see unrelated personal/draft chats without policy;
- employee outside group is not exposed;
- sharing/group behavior is recorded with exact OpenWebUI settings.

## 4.2. No-delete, retention and audit boundary

These are separate controls:

- disabling user delete: normal users cannot delete chats through UI/API if native proof passes;
- retention: how long chats, uploaded files and transcripts are kept;
- backup: operational restore point, not user-level retention;
- audit log: record of actions/access;
- immutable archive: separate legal/audit-grade subsystem, not Practical Stage 2 unless separately
  approved.

## 5. Native OpenWebUI first path

- Groups/RBAC.
- Admin surfaces.
- Workspace access.
- Native deletion/settings/retention if available.

## 6. Integration / custom implementation path

- Policy-only with documented limitations.
- Backup/audit/export procedure.
- Minimal customization for no-delete if native unavailable.
- Deferred custom implementation if risk too high.

## 7. Data and security notes

Manager visibility is sensitive. It must define visible chats, actors, purpose, employee notice,
audit logging and retention.

Frontend/UI must not become the place where visibility and retention rules are decided.

## 8. Dependencies

- OpenWebUI capability research.
- RBAC manager visibility research.
- Chat deletion/retention research.
- Customer privacy policy.

## 9. Risks and constraints

- Overbroad access.
- No native no-delete control.
- Incomplete audit trail.
- Unclear distinction between work and personal chats.

## 10. Open questions

- Which chats are work chats?
- Can employees opt into/out of visibility?
- Who can delete chats?
- Is export acceptable instead of live visibility?

## 11. Research links

- [RBAC_MANAGER_VISIBILITY_RESEARCH](../research/RBAC_MANAGER_VISIBILITY_RESEARCH.md)
- [CHAT_DELETION_RETENTION_RESEARCH](../research/CHAT_DELETION_RETENTION_RESEARCH.md)
- [OPENWEBUI_CAPABILITY_RESEARCH](../research/OPENWEBUI_CAPABILITY_RESEARCH.md)

## 12. Acceptance signals

- Native support confirmed or limitation documented.
- Manager sees only approved work chats in test.
- Chat deletion restriction has native/policy/export/patch decision.
- No-delete UI/API proof completed for non-admin user and admin override.
- Retention policy decision is documented separately from no-delete.
- Audit/immutable archive is explicitly accepted or deferred.

## 13. Implementation readiness

Needs ADR-0002, ADR-0003, capability proof and customer privacy/security decision before
implementation.
