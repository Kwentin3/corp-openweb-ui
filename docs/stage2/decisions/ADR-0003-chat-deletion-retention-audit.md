# ADR-0003 Chat Deletion, Retention and Audit

Status: Proposed

## 1. Context

PRD-1 includes a technical check for preventing ordinary users from deleting
their chats while admins may delete/administer. OpenWebUI documentation suggests
chat deletion can be permissioned, but deployed runtime proof is required.

The customer request for no-delete must not be confused with retention, audit
logging or immutable archive.

## 2. Problem

"Users should not delete their chats" is an access-control requirement. It does
not define how long chats are stored, whether uploaded files/transcripts are
retained, whether backups are enough, or whether legal-grade audit/archive is
required.

## 3. Decision needed

Approve separate decisions for:

- disabling user delete;
- retention periods;
- backup expectations;
- audit logging;
- whether immutable archive is required later.

## 4. Options

Option 1. Native no-delete permission.

- Preferred if deployed runtime proof passes.
- Lowest upgrade risk.

Option 2. Policy + backup/export fallback.

- Documents the limitation.
- Does not truly block deletion in UI/API if native proof fails.

Option 3. Minimal patch or server-side guard.

- Stronger enforcement.
- Higher OpenWebUI upgrade risk.
- Should be separate implementation decision.

## 5. Recommended option

Test Option 1 first. Keep Option 2 as fallback if native no-delete does not pass.
Do not promise Option 3 without explicit implementation approval.

Key distinction:

No Delete is not Retention. Retention is not Audit. Audit is not immutable
archive.

## 6. Consequences

- UI-only proof is insufficient.
- API delete behavior must be checked where possible.
- Admin override must be documented.
- Retention policy must be written separately from no-delete.
- Immutable audit archive remains future unless separately approved.

## 7. Runtime proof needed

- UI delete permission for non-admin.
- API delete behavior for non-admin, if API path is available.
- Additive permissions do not re-enable delete through another role/group.
- Admin override behavior is documented.
- Shared work-chat behavior is checked.

## 8. Customer input needed

- How long are chats stored?
- How long are uploaded files stored?
- How long are transcripts stored?
- Is backup enough for customer needs?
- Is legal/audit archive required?
- Who can delete as admin and under what procedure?
- Are exports required for manager/customer review?

## 9. Acceptance signals

- Non-admin UI delete proof completed.
- Non-admin API delete behavior checked or documented as unavailable.
- Admin override behavior documented.
- Retention decision documented separately.
- Audit/immutable archive accepted as future/deferred unless separately approved.

## 10. Links

- [MANAGER_VISIBILITY_AND_RETENTION](../blueprints/MANAGER_VISIBILITY_AND_RETENTION.blueprint.md)
- [CHAT_DELETION_RETENTION_RESEARCH](../research/CHAT_DELETION_RETENTION_RESEARCH.md)
- [ACCEPTANCE_MATRIX](../acceptance/ACCEPTANCE_MATRIX.md)
