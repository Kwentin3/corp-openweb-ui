# ADR-0003 Chat Deletion, Retention and Audit

Status: Proposed
Date: 2026-06-18
Domain: No-delete / retention / audit

## 1. Context

PRD-1 includes a technical check for preventing ordinary users from deleting their chats while admins may delete/administer. OpenWebUI documentation suggests chat deletion can be permissioned, but deployed runtime proof is required.

The customer request for no-delete must not be confused with retention, audit logging or immutable archive.

## 2. Problem

"Users should not delete their chats" is an access-control requirement. It does not define how long chats are stored, whether uploaded files/transcripts are retained, whether backups are enough, or whether legal-grade audit/archive is required.

## 3. Difference Between Controls

- Disabling user delete: normal users cannot delete chats through UI/API.
- Retention: chats, files and transcripts are stored for defined periods.
- Backup: operational restore capability, not user-facing retention.
- Audit log: record of actions/access.
- Immutable archive: legal/audit-grade record that ordinary admins cannot rewrite.

Key rule:

No Delete is not Retention. Retention is not Audit. Audit is not immutable archive.

## 4. What Customer Asked

- Users should not delete their chats.
- Admins may delete/administer.
- Practical Stage 2 should check native capability first.

## 5. Native Proof Needed

- UI delete permission for non-admin.
- API delete behavior for non-admin, if API path is available.
- Additive permissions do not re-enable delete through another role/group.
- Admin override behavior is documented.
- Shared work-chat behavior is checked.

## 6. Retention Policy Questions

- How long are chats stored?
- How long are uploaded files stored?
- How long are transcripts stored?
- Is backup enough for customer needs?
- Is legal/audit archive required?
- Who can delete as admin and under what procedure?
- Are exports required for manager/customer review?

## 7. Fallbacks

- Policy.
- Backup/restore.
- Periodic export.
- DB-level retention.
- Minimal patch.
- Future audit subsystem.

## 8. Non-goals

- No immutable audit archive in Practical Stage 2 unless separately approved.
- No guarantee that backup equals audit.
- No UI-only proof accepted without API/delete-path consideration.

## 9. Acceptance Signals

- Non-admin UI delete proof completed.
- Non-admin API delete behavior checked or documented as unavailable.
- Admin override behavior documented.
- Retention decision documented separately.
- Audit/immutable archive accepted as future/deferred unless separately approved.

## 10. Status

Proposed. Needs runtime proof and customer retention/audit decision.
