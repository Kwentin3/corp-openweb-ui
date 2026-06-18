# Ops And Acceptance Blueprint

## 1. Purpose

Спланировать Stage 2 acceptance, smoke checks, docs handoff and ops boundaries.

## 2. PRD-1 requirements covered

- User/admin docs.
- Smoke/acceptance checks.
- No secrets in git.
- No production change without implementation approval.
- Update/rollback awareness.

## 3. Current known context

PRD-0 has runbooks for deployment, smoke, backup/restore, security and provider setup. Stage 2 planning must reuse them but not execute production changes.

## 4. Target user workflow

Reviewer opens acceptance matrix, confirms test data availability, checks domain blueprints/research, then approves implementation planning.

## 5. Native OpenWebUI first path

Operational proof should prefer native/admin checks before adding tooling. Stage 2 implementation must keep update/rollback path clear.

## 6. Integration / custom implementation path

Any custom module must define smoke, rollback/defer condition, log handling, secret boundary and acceptance evidence.

## 7. Data and security notes

Do not read/print `.env`. Do not store API keys in docs. Use server-local secrets/password manager/Admin UI.

## 8. Dependencies

- All domain blueprints.
- Acceptance matrix.
- Test data requirements.
- PRD-0 runbooks.

## 9. Risks and constraints

- Starting implementation before research approval.
- Missing customer test data.
- Docs drift from runtime truth.
- Secrets accidentally included in docs.

## 10. Open questions

- Who signs off acceptance?
- Are test users available?
- Is stage runtime accessible for read-only capability checks?

## 11. Research links

- [OPENWEBUI_CAPABILITY_RESEARCH](../research/OPENWEBUI_CAPABILITY_RESEARCH.md)

## 12. Acceptance signals

- Acceptance matrix maps each PRD-1 requirement to domain, blueprint, research and test data.
- README links Stage 2 domain.
- Markdown checks pass.

## 13. Implementation readiness

Ready for implementation planning only after roadmap/blueprints/research review.
