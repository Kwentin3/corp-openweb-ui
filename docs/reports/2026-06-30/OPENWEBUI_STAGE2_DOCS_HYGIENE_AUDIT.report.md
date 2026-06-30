# OpenWebUI Stage 2 Docs Hygiene Audit Report

Date: 2026-06-30.
Scope: documentation-only audit and representation proposal.

## 1. Summary

Stage 2 documentation is usable, but it has accumulated three risks:

- current customer-facing scope, internal handoff, old commercial notes and PRD
  docs repeat the same scope facts in different detail levels;
- PRD-1 is broader than the current Stage 2 contract slice and can be mistaken
  for current scope if read without the newer customer-facing document;
- historical commercial docs still look active unless the reader already knows
  which newer documents supersede them.

No evidence reports were deleted or rewritten. The recommended model is:

- customer-facing source of truth:
  `docs/commercial/STAGE2_CUSTOMER_SCOPE_AND_QUESTIONS.md`;
- internal contract/evidence bridge:
  `docs/commercial/STAGE2_CONTRACT_HANDOFF_CONTEXT_PACK.md`;
- engineering source set: Stage 2 context index, backlog, gates, acceptance
  matrix and Web Search context index;
- reports remain dated evidence and historical context.

## 2. Files reviewed

Commercial / customer-facing:

- `docs/commercial/STAGE2_CUSTOMER_SCOPE_AND_QUESTIONS.md`
- `docs/commercial/STAGE2_CONTRACT_HANDOFF_CONTEXT_PACK.md`
- `docs/commercial/STAGE2_SCOPE_RECONCILIATION_150K.md`
- `docs/commercial/STAGE2_COMPLETED_WORK_AUDIT_150K.md`

Stage 2 core:

- `docs/stage2/README.md`
- `docs/stage2/CONTEXT_INDEX.md`
- `docs/stage2/ENGINEERING_BACKLOG.md`
- `docs/stage2/IMPLEMENTATION_GATES.md`
- `docs/stage2/acceptance/ACCEPTANCE_MATRIX.md`
- `docs/stage2/WEB_SEARCH_CONTEXT_INDEX.md`

PRD:

- `docs/prd/OPENWEBUI_CORPORATE_CHAT_PRD_0.md`
- `docs/prd/OPENWEBUI_CORPORATE_CHAT_PRD_1.md`
- `docs/prd/OPENWEBUI_CORPORATE_CHAT_PRD_1_CUSTOMER_SUMMARY.md`

STT evidence and context:

- `docs/stage2/context/NEW_CHAT_CONTEXT_PACK_STT_STAGE2.md`
- `docs/stage2/contracts/STT_MEDIA_INPUT_NORMALIZATION_CONTRACT.md`
- representative reports under `docs/reports/2026-06-19/`, including STT
  implementation, runtime completion, ffmpeg/browser normalization, MVP closure
  and Playwright/UI proof reports.

Web Search evidence and context:

- `docs/stage2/WEB_SEARCH_CONTEXT_INDEX.md`
- Web Search contracts under `docs/stage2/contracts/`
- representative reports under `docs/reports/2026-06-20/` and
  `docs/reports/2026-06-23/`, including Brave, Yandex, SearXNG and provider
  baseline closeout reports.

OCR / VL OCR:

- `docs/stage2/context/OCR_VL_OCR_INFRASTRUCTURE_EPIC_CONTEXT_PACK.md`
- `docs/stage2/research/VL_OCR_API_PROVIDER_SHORTLIST_RESEARCH.md`
- `docs/stage2/research/VL_OCR_API_PROVIDER_SHORTLIST_RESEARCH_V2.md`
- representative reports under `docs/reports/2026-06-25/`.

All requested key files that are currently expected in the repository were
found.

## 3. Documentation role classification

| File | Current role | Intended audience | Keep / Merge / Archive / Refine | Source of truth? | Notes |
| --- | --- | --- | --- | --- | --- |
| `docs/commercial/STAGE2_CUSTOMER_SCOPE_AND_QUESTIONS.md` | CUSTOMER_FACING, CONTRACT_PREP | Customer, owner | KEEP_AS_IS | Yes | Primary current-scope document for customer agreement: F1-F12, hours, questions, exclusions and next step. |
| `docs/commercial/STAGE2_DOCS_REPRESENTATION_MODEL.md` | INTERNAL_ENGINEERING, CONTRACT_PREP | Team, owner | KEEP_AS_IS | Yes | New model for document roles and source-of-truth split. |
| `docs/commercial/STAGE2_CONTRACT_HANDOFF_CONTEXT_PACK.md` | INTERNAL_ENGINEERING, CONTRACT_PREP | Team, agent, owner | KEEP_AS_IS, later SHORTEN | Yes | Internal evidence bridge for preparing external documents. Not customer-facing. |
| `docs/commercial/STAGE2_SCOPE_RECONCILIATION_150K.md` | HISTORICAL_CONTEXT, CONTRACT_PREP | Team | MARK_HISTORICAL | No | Useful historical narrowing of scope, but superseded for current customer wording. |
| `docs/commercial/STAGE2_COMPLETED_WORK_AUDIT_150K.md` | HISTORICAL_CONTEXT, EVIDENCE_REPORT, CONTRACT_PREP | Team | MARK_HISTORICAL, later SHORTEN | No | Useful as first-slice completed-work history; too detailed for current customer-facing use. |
| `docs/stage2/README.md` | INTERNAL_ENGINEERING | Team, agent | KEEP_AS_IS | Yes | Stage 2 navigation hub. |
| `docs/stage2/CONTEXT_INDEX.md` | INTERNAL_ENGINEERING | Team, agent | KEEP_AS_IS | Yes | Main context router and document-type rule source. |
| `docs/stage2/ENGINEERING_BACKLOG.md` | INTERNAL_ENGINEERING | Team | KEEP_AS_IS | Yes | Engineering gaps and next work. |
| `docs/stage2/IMPLEMENTATION_GATES.md` | INTERNAL_ENGINEERING | Team | KEEP_AS_IS | Yes | Gates before implementation/runtime changes. |
| `docs/stage2/acceptance/ACCEPTANCE_MATRIX.md` | INTERNAL_ENGINEERING | Team, owner | REFINE later | Yes | Broad acceptance matrix; should label current-scope versus full PRD acceptance more visibly. |
| `docs/stage2/WEB_SEARCH_CONTEXT_INDEX.md` | INTERNAL_ENGINEERING | Team, agent | KEEP_AS_IS | Yes | Web Search route, baseline evidence and open governance status. |
| `docs/prd/OPENWEBUI_CORPORATE_CHAT_PRD_0.md` | PRD_SOURCE, HISTORICAL_CONTEXT | Team, owner | KEEP_AS_IS | Yes for PRD-0 | Accepted baseline history, not Stage 2 current scope. |
| `docs/prd/OPENWEBUI_CORPORATE_CHAT_PRD_1.md` | PRD_SOURCE | Team, owner | KEEP_AS_IS | Yes for broad product target | Broader than current Stage 2 contract slice. |
| `docs/prd/OPENWEBUI_CORPORATE_CHAT_PRD_1_CUSTOMER_SUMMARY.md` | CUSTOMER_FACING, PRD_SOURCE | Customer, owner | KEEP_AS_IS | Supporting only | Explains broad PRD-1; not the current contract-scope source after the newer customer scope doc. |
| STT reports under `docs/reports/2026-06-19/` | EVIDENCE_REPORT | Team, agent | KEEP_AS_IS | Evidence only | Preserve as dated proof; do not rewrite into customer proposal. |
| Web Search reports under `docs/reports/2026-06-20/` and `docs/reports/2026-06-23/` | EVIDENCE_REPORT | Team, agent | KEEP_AS_IS | Evidence only | Prove provider baseline; do not imply full rollout. |
| OCR/VL OCR V1 research and reports | RESEARCH, HISTORICAL_CONTEXT | Team | MARK_HISTORICAL | No | Keep as baseline history; V2 is preferred for current shortlist. |
| OCR/VL OCR V2 research and context pack | RESEARCH, EVIDENCE_REPORT | Team | KEEP_AS_IS | Yes for research | Research/future scope only, not implementation proof. |

## 4. Duplicate / overlap findings

| Topic | Files where duplicated | Recommended source of truth | What to remove or shorten elsewhere |
| --- | --- | --- | --- |
| Stage 2 composition | Customer scope doc, handoff pack, PRD-1 customer summary, old commercial docs, acceptance matrix | Customer scope doc for customer wording; handoff pack for internal evidence | Mark old commercial docs historical; avoid adding another live scope list. |
| F1-F12 / R1-R12 registry | Customer scope doc, handoff pack | Customer scope doc for customer F-list; handoff pack for internal evidence registry | If another doc needs this list, link to the source instead of copying. |
| Future scope boundaries | Customer scope doc, handoff pack, PRD-1 customer summary, old commercial docs, acceptance matrix | Customer scope doc for exclusions; PRD-1/backlog for roadmap | Shorten old commercial restatements after historical notice is added. |
| STT base status | Context index, gates, acceptance matrix, handoff pack, STT reports, old completed-work audit | STT reports plus context index for current status | Customer docs should keep only plain-language result and limits. |
| STT v2 scope | Customer scope doc, handoff pack, PRD customer summary | Customer scope doc plus handoff pack | Do not create a separate "Meetings" feature doc for the same scope. |
| Web Search baseline status | Web Search context index, handoff pack, acceptance matrix, old commercial docs, reports | Web Search context index plus provider baseline reports | Customer docs should say baseline is implemented and governance is outside current scope. |
| OCR/VL OCR status | PRD docs, acceptance matrix, gates, context index, OCR research, old commercial docs | V2 shortlist research and OCR/VL OCR context pack | Keep OCR/VL OCR out of current customer-facing contract scope unless separately agreed. |
| Hours | Customer scope doc, handoff pack rough estimate, PRD customer summary older estimate | Customer scope doc | Keep handoff estimate as internal support only; avoid copying hour map into reports. |
| Customer questions | Customer scope doc, PRD customer summary and proposals | Customer scope doc | Use customer scope doc as the live checklist. |
| Contract-safe wording | Handoff pack, old completed-work audit, current customer scope | Handoff pack for internal draft-safe wording; customer scope doc for approval wording | Mark old completed-work wording historical before linking it. |
| Extension-first architecture | Context index, contract boundaries, extension-first pattern, handoff pack, reports | `docs/stage2/EXTENSION_FIRST_IMPLEMENTATION_PATTERN.md` and `docs/stage2/CONTEXT_INDEX.md` | Customer docs should keep only the practical consequence: native OpenWebUI first where possible. |
| Limitations | Customer scope doc, handoff pack, acceptance matrix, reports | Customer scope doc for customer limits; acceptance matrix/gates for engineering limits | Avoid duplicating full engineering limitation lists in customer docs. |

## 5. Drift / contradiction findings

1. Current Stage 2 is correctly framed in the newest customer-facing and
   handoff docs as a limited first functional and architectural slice, not all
   PRD-1.
2. PRD-1 and the PRD-1 customer summary remain broader than the current slice.
   They must be read as product target, not as current contract scope.
3. STT base is consistently described as implemented/current-stage closed in
   core engineering docs. STT v2 is correctly to-implement: template
   post-processing, starter templates, cautious speaker-aware handling and
   simple DOCX export.
4. The current docs do not promise a separate "Meetings" section as current
   scope. Transcript history correctly stays in ordinary OpenWebUI chat.
5. PDF export and branded DOCX generation are excluded from current scope. DOCX
   is only simple export for manual editing.
6. Web Search baseline is consistently described as implemented. Full
   governance, group rollout, extended logging, hard limits, forbidden-query
   policy and cost visibility are not closed.
7. Web Search scenarios can be current-scope prompt/scenario packaging. They
   should not be described as full governance.
8. OCR/VL OCR and broker-report workflows appear in PRD and research materials,
   but current customer-facing scope correctly excludes them from this contract
   slice.
9. The main stale-status risk is not a single contradiction; it is discoverable
   navigation. A reader can still land on old commercial docs and treat them as
   current unless they know the new source-of-truth split.

## 6. Source-of-truth recommendation

| Topic | Source of truth | Supporting docs | Notes |
| --- | --- | --- | --- |
| Stage 2 customer-facing scope | `docs/commercial/STAGE2_CUSTOMER_SCOPE_AND_QUESTIONS.md` | PRD customer summary, handoff pack | Use for customer approval. |
| Stage 2 internal contract handoff | `docs/commercial/STAGE2_CONTRACT_HANDOFF_CONTEXT_PACK.md` | Stage 2 core docs and reports | Use for evidence-backed prep. |
| Feature registry F1-F12 | Customer scope doc | Handoff pack | Do not maintain a third live copy. |
| Hour map | Customer scope doc | Handoff rough estimate | Hours only, no financial values. |
| Future scope | Customer scope doc for customer exclusions; PRD-1/backlog for roadmap | Acceptance matrix | Keep current slice narrow. |
| STT base evidence | STT 2026-06-19 reports and context index | Gates, acceptance matrix | Implemented; remaining work is hardening. |
| STT v2 scope | Customer scope doc and handoff pack | PRD customer summary | To implement in current scope. |
| Web Search baseline evidence | `docs/stage2/WEB_SEARCH_CONTEXT_INDEX.md` | Brave/Yandex/SearXNG reports | Baseline implemented; rollout/gov gaps open. |
| Web Search scenarios | Customer scope doc and Web Search docs | Source attribution/privacy contracts | Scenario pack only. |
| OCR/VL OCR research | V2 provider shortlist and OCR/VL OCR context pack | 2026-06-25 reports | Research/future for current scope. |
| Broker reports future scope | PRD-1 and broker blueprint | Customer-facing exclusions | Future scope. |
| Acceptance criteria | Acceptance matrix | Customer scope doc | Split broad PRD acceptance from current-scope acceptance when refined. |
| Engineering backlog | Engineering backlog | Gates, context index | Owns internal next actions. |

## 7. Customer-facing representation recommendation

Use one primary customer-facing document:

- `docs/commercial/STAGE2_CUSTOMER_SCOPE_AND_QUESTIONS.md`

It is currently the right document to show for agreement because it has:

- plain Russian explanations;
- current scope and future scope;
- F1-F12 with status and hour ranges;
- key questions and full question checklist;
- acceptance preparation frame.

Do not expose raw evidence reports as customer-facing docs. Create an optional
short summary only if a one or two page version is actually needed.

## 8. Internal engineering representation recommendation

Use this internal set:

- `docs/commercial/STAGE2_CONTRACT_HANDOFF_CONTEXT_PACK.md`
- `docs/stage2/CONTEXT_INDEX.md`
- `docs/stage2/ENGINEERING_BACKLOG.md`
- `docs/stage2/IMPLEMENTATION_GATES.md`
- `docs/stage2/acceptance/ACCEPTANCE_MATRIX.md`
- `docs/stage2/WEB_SEARCH_CONTEXT_INDEX.md`

The internal set should keep strict status, evidence and blocker language. It
should not try to be customer-facing prose. If a customer-facing sentence needs
evidence, link back to the handoff pack or reports instead of copying report
details.

## 9. Files recommended for refine / merge / historical marking

| File | Problem | Recommended action |
| --- | --- | --- |
| `docs/commercial/STAGE2_CUSTOMER_SCOPE_AND_QUESTIONS.md` | Current primary customer-facing document; no blocking hygiene issue found. | KEEP_AS_IS |
| `docs/commercial/STAGE2_CONTRACT_HANDOFF_CONTEXT_PACK.md` | Correct role, but overlaps with customer doc and old commercial docs. | KEEP_AS_IS, later SHORTEN |
| `docs/commercial/STAGE2_SCOPE_RECONCILIATION_150K.md` | Historical narrowing doc can look current. | MARK_HISTORICAL |
| `docs/commercial/STAGE2_COMPLETED_WORK_AUDIT_150K.md` | Historical completed-work audit is too long and mixes evidence, contract-prep and customer-ish wording. | MARK_HISTORICAL, later SHORTEN |
| `docs/prd/OPENWEBUI_CORPORATE_CHAT_PRD_1_CUSTOMER_SUMMARY.md` | Broader than current contract slice. | REFINE later with pointer to current customer scope |
| `docs/stage2/acceptance/ACCEPTANCE_MATRIX.md` | Broad PRD acceptance and current-slice acceptance sit together. | REFINE |
| `docs/stage2/CONTEXT_INDEX.md` | Strong router, but should eventually link the representation model. | REFINE |
| OCR/VL OCR V1 shortlist docs | V1 baseline can be mistaken for current shortlist. | MARK_HISTORICAL |
| Dated reports | Intentional duplication as evidence. | KEEP_AS_IS |

No file is recommended for deletion in this task.

## 10. Financial scan results

The requested financial-expression scan over `docs` and `README.md` returned
no content matches.

Classification:

| Finding | Classification | Action |
| --- | --- | --- |
| No content matches from the requested scan | false positive not applicable | No rewrite needed. |
| `_150K` in two legacy commercial filenames | legacy accepted | Do not rename in this task. |

No financial values were added by this task.

## 11. Encoding / BOM findings

Sampled key markdown files show mixed BOM state:

| File group | BOM status | Note |
| --- | --- | --- |
| Newer customer-facing and Stage 2 docs | UTF-8 with BOM observed in several files | Current Windows-authored docs often use BOM. |
| Older commercial files with `_150K` marker | No BOM observed in sampled files | Legacy mixed state. |
| New files from this task | UTF-8 with BOM intended after normalization | Keeps current Windows documentation convention for new Russian markdown. |

No existing file was rewritten only to change BOM in this task. A separate
encoding policy cleanup can remove or standardize BOM later if desired.

## 12. Changes made in this task

Created:

- `docs/commercial/STAGE2_DOCS_REPRESENTATION_MODEL.md`
- `docs/reports/2026-06-30/OPENWEBUI_STAGE2_DOCS_HYGIENE_AUDIT.report.md`

Not changed:

- no code files;
- no compose files;
- no env files;
- no existing Stage 2 docs;
- no evidence reports;
- no file names.

## 13. Next recommended docs cleanup tasks

1. Add short historical notices to the two legacy commercial docs.
2. Add a pointer from `docs/stage2/CONTEXT_INDEX.md` to the representation
   model for docs hygiene tasks.
3. Refine `docs/stage2/acceptance/ACCEPTANCE_MATRIX.md` so broad PRD
   acceptance and current-scope acceptance are visually separated.
4. Mark OCR/VL OCR V1 shortlist as historical where it is linked next to V2.
5. Shorten the handoff pack after customer scope is accepted, keeping only
   evidence-backed deltas and risks.
6. Create a short customer summary only if a one or two page external handout is
   actually needed.

## 14. Final verdict

`stage2_docs_hygiene_audit_ready`
