# RBAC Manager Visibility Research

## 1. Question

Can OpenWebUI support manager visibility into work chats by group/workspace without exposing all personal chats?

## 2. Why it matters for PRD-1

Customer wants manager access early, but privacy/security boundary is mandatory.

## 3. Current assumptions

- Native RBAC/admin surfaces may be insufficient.
- Visibility must be scoped to work chats.

## 4. What to verify

- Groups/RBAC.
- Admin chat visibility.
- Workspace-scoped access.
- Audit/logging options.
- Employee notice options.
- Export/reporting alternatives.

## 5. Sources to check

- OpenWebUI deployed runtime.
- Official RBAC/admin docs.
- PRD-1 policy requirements.

## 6. Test plan / proof plan

Use test group, manager user, employee user, work chat, personal chat. Verify who can see what.

## 7. Risks

- Manager sees too much.
- Manager sees nothing natively.
- No audit trail.
- Work/personal chat boundary unclear.

## 8. Decision options

- Native configuration.
- Policy and training only.
- Audit/backup/export workflow.
- Minimal customization.
- Deferred custom implementation.

## 9. Recommended next step

Run native capability check before promising manager visibility.

## 10. Status

Planned, not verified.
