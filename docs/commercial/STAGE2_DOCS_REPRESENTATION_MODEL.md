# Stage 2 Documentation Representation Model

Status: proposal for documentation hygiene.
Date: 2026-06-30.

This document fixes how Stage 2 documentation should be represented after the
customer-facing scope work and internal handoff work. It does not change the
Stage 2 scope.

## 1. Purpose

Stage 2 now has PRD files, customer-facing docs, internal handoff packs,
research, implementation reports and historical commercial notes. The same
facts are useful in different forms, but the same document should not try to be
customer proposal, engineering route and evidence report at once.

The stable model is:

- customer-facing docs explain the agreed scope simply;
- internal engineering docs hold status, evidence, constraints and next steps;
- reports remain dated proof and historical context;
- PRD docs remain product intent, not automatic current contract scope.

## 2. Two documentation audiences

| Audience | Purpose | Style | Should not contain |
| --- | --- | --- | --- |
| Customer-facing | Agree Stage 2 scope, hours, questions, future scope and acceptance frame. | Short Russian text, plain terms, business result first. | Raw reports, code paths, secrets, provider keys, detailed evidence dumps or financial values. |
| Internal engineering | Preserve exact implementation state, evidence, gates, gaps and routing. | Strict, link-backed, status tables and explicit blockers. | Sales wording, vague promises, hidden scope expansion or undocumented runtime assumptions. |

## 3. Customer-facing documents

Primary document:

- `docs/commercial/STAGE2_CUSTOMER_SCOPE_AND_QUESTIONS.md`

Role:

- main customer-facing source of truth for the current Stage 2 scope before
  external contract documents are prepared;
- contains F1-F12, current statuses, hour map, exclusions, questions and the
  next step after agreement.

Optional future document:

- `docs/commercial/STAGE2_CUSTOMER_SCOPE_SUMMARY.md`

Use it only if a shorter one or two page customer summary is needed. Do not
create it just to duplicate the primary customer-facing document.

## 4. Internal engineering documents

Minimum internal set:

- `docs/commercial/STAGE2_CONTRACT_HANDOFF_CONTEXT_PACK.md`
- `docs/stage2/CONTEXT_INDEX.md`
- `docs/stage2/ENGINEERING_BACKLOG.md`
- `docs/stage2/IMPLEMENTATION_GATES.md`
- `docs/stage2/acceptance/ACCEPTANCE_MATRIX.md`
- `docs/stage2/WEB_SEARCH_CONTEXT_INDEX.md`

Roles:

- `STAGE2_CONTRACT_HANDOFF_CONTEXT_PACK.md` is the internal contract-prep and
  evidence bridge. It can repeat customer-facing scope only where the repeated
  line has engineering evidence or risk attached.
- `CONTEXT_INDEX.md` is the route map and document-type rule source.
- `ENGINEERING_BACKLOG.md` owns engineering gaps and next work.
- `IMPLEMENTATION_GATES.md` owns gates before runtime or implementation work.
- `ACCEPTANCE_MATRIX.md` owns acceptance criteria and should clearly separate
  broad PRD acceptance from the current customer-facing contract slice.
- `WEB_SEARCH_CONTEXT_INDEX.md` owns Web Search status and evidence routing.

## 5. Evidence and historical reports

Reports under `docs/reports/YYYY-MM-DD/` are not customer-facing documents.
They answer what was checked, on which date, with which evidence and limits.

Historical commercial documents should not be deleted, but they should not be
treated as live source of truth if superseded by the current customer-facing
scope document or the internal handoff pack.

Known historical commercial files:

- `docs/commercial/STAGE2_SCOPE_RECONCILIATION_150K.md`
- `docs/commercial/STAGE2_COMPLETED_WORK_AUDIT_150K.md`

Their filename marker is a legacy marker and should not be renamed in this
cleanup step.

## 6. Source-of-truth map

| Topic | Source of truth | Supporting docs | Notes |
| --- | --- | --- | --- |
| Stage 2 customer-facing scope | `docs/commercial/STAGE2_CUSTOMER_SCOPE_AND_QUESTIONS.md` | PRD customer summary, internal handoff pack | Current scope is a limited first functional and architectural slice, not all PRD-1. |
| Stage 2 internal contract handoff | `docs/commercial/STAGE2_CONTRACT_HANDOFF_CONTEXT_PACK.md` | Stage 2 core docs and reports | Internal evidence base only. |
| Feature registry F1-F12 | Customer-facing scope doc for customer wording; handoff pack for evidence | Acceptance matrix, backlog | Do not maintain a third live registry. |
| Hour map | Customer-facing scope doc | Handoff rough effort section | Hours can be repeated only as a short pointer elsewhere. |
| Future scope | Customer-facing scope doc for customer exclusions; PRD-1 and backlog for product roadmap | Acceptance matrix | OCR/VL OCR, broker reports, full document workflows and full governance stay outside current contract scope unless separately agreed. |
| STT base evidence | STT reports and `docs/stage2/CONTEXT_INDEX.md` | Acceptance matrix, gates | Base STT is implemented; remaining base work is hardening. |
| STT v2 scope | Customer-facing scope doc and handoff pack | PRD/customer summary | Current/to-implement scope: template post-processing, starter templates, cautious speaker-aware handling and simple DOCX export. |
| Web Search baseline evidence | `docs/stage2/WEB_SEARCH_CONTEXT_INDEX.md` | Brave/Yandex/SearXNG reports | Baseline is implemented; full governance is not closed. |
| Web Search scenarios | Customer-facing scope doc and Web Search docs | Source attribution/privacy contracts | Scenario pack is prompt/content work, not full governance. |
| OCR/VL OCR research | V2 shortlist research and OCR/VL OCR context pack | 2026-06-25 reports | Research/future only for current contract scope. |
| Broker reports future scope | PRD-1 and broker blueprint | Customer-facing exclusions | Future scope, not current implementation. |
| Acceptance criteria | `docs/stage2/acceptance/ACCEPTANCE_MATRIX.md` | Customer-facing scope doc for customer acceptance frame | Keep internal acceptance broad but label current-scope boundaries. |
| Engineering backlog | `docs/stage2/ENGINEERING_BACKLOG.md` | Gates, context index | Backlog owns engineering next actions. |

## 7. What should not be duplicated

Do not keep separate live copies of:

- F1-F12 feature list;
- hour map;
- customer questions;
- current/future scope boundary;
- STT base versus STT v2 status;
- Web Search baseline versus full governance status;
- OCR/VL OCR and broker-report future status;
- extension-first implementation order;
- contract-safe wording.

Duplication is acceptable inside dated reports, because reports are evidence and
history. Duplication should be reduced in live customer-facing and internal
engineering docs.

## 8. How to update docs going forward

Use this update rule:

1. Customer wording changes go first to
   `docs/commercial/STAGE2_CUSTOMER_SCOPE_AND_QUESTIONS.md`.
2. Engineering status, evidence and blockers go to the internal source listed
   in the source-of-truth map.
3. New proof goes to a dated report under `docs/reports/YYYY-MM-DD/`.
4. Research findings stay in `docs/stage2/research/` until an owner decision or
   implementation gate promotes them.
5. Historical commercial docs should receive a short historical notice before
   they are linked from current navigation.
6. GitHub markdown should not gain financial values, provider secrets,
   customer data, `.env` values or raw private logs.
