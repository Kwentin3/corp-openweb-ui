# Chat Deletion Retention Research

## 1. Question

Can Stage 2 prevent non-admin users from deleting chats, or otherwise preserve work-chat evidence?

## 2. Why it matters for PRD-1

Customer wants no-delete policy for regular users. This affects manager visibility, audit and retention.

## 3. Current assumptions

- Native support is unknown.
- If native unavailable, alternatives must be explicit.

## 4. What to verify

- User chat deletion settings.
- Admin controls.
- Retention/storage behavior.
- Backup/export options.
- Audit logs.
- Impact on personal/temporary chats.

## 5. Sources to check

- OpenWebUI deployed runtime.
- Official settings/RBAC/admin docs.
- PRD-0 backup/restore runbooks.

## 6. Test plan / proof plan

Use regular user and admin test accounts. Try create/delete chats under allowed test policy. Verify backup/export alternatives.

## 7. Risks

- No native no-delete control.
- Retention conflicts with privacy.
- Backup does not provide usable review access.

## 8. Decision options

- Native no-delete configuration.
- Policy-only.
- Backup/audit/export.
- Minimal patch/customization.
- Deferred implementation.

## 9. Recommended next step

Research with deployed version before committing to implementation.

## 10. Status

Planned, not verified.
