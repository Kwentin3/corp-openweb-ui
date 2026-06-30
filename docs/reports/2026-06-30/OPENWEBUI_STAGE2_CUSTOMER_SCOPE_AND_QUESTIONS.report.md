# OpenWebUI Stage 2 Customer Scope And Questions Report

## 1. Summary

Created a customer-facing Stage 2 agreement draft for the current limited
Stage 2 slice. The document is written in plain Russian, avoids developer-only
terms, includes only hour estimates, and separates current work from future
directions.

Final customer document:

- `docs/commercial/STAGE2_CUSTOMER_SCOPE_AND_QUESTIONS.md`

## 2. Sources reviewed

Reviewed the required Stage 2 evidence and planning sources:

- internal Stage 2 contract handoff context pack;
- internal Stage 2 contract handoff report;
- existing commercial reconciliation document;
- PRD-1 and PRD-1 customer summary;
- Stage 2 README and context index;
- Stage 2 engineering backlog;
- Stage 2 implementation gates;
- Stage 2 acceptance matrix;
- OpenWebUI native capability audit;
- current STT and Web Search implementation evidence referenced by the handoff
  pack.

No required source was missing.

## 3. Customer-facing document created

Created:

- `docs/commercial/STAGE2_CUSTOMER_SCOPE_AND_QUESTIONS.md`

The document explains:

- what Stage 2 means for this project;
- why this composition is proposed;
- what is already implemented;
- what is proposed for the current Stage 2;
- estimated effort in hours;
- what is excluded from this stage;
- questions for customer approval;
- the next step after approval.

## 4. Scope included

The customer-facing document includes F1-F12:

- F1. Base audio/video transcription in OpenWebUI - already implemented.
- F2. Transcript processing by templates - current work.
- F3. Starter transcript template set - current work.
- F4. Template management through OpenWebUI - current work with target-runtime
  verification.
- F5. Speaker-aware transcript processing - current work.
- F6. Simple DOCX export - current work.
- F7. Base Web Search - already implemented as baseline.
- F8. Ready Web Search scenarios - current work.
- F9. General corporate template pack - current work.
- F10. Short user onboarding pack - current work.
- F11. Basic pilot access matrix - current work.
- F12. Stage 2 documentation and acceptance base - already prepared, with final
  packaging after approval.

## 5. Questions included

The customer-facing document includes approval questions across:

- transcription and transcript templates;
- DOCX export;
- Web Search;
- shared and personal templates;
- pilot access;
- acceptance scenarios.

It keeps the original 23 approval questions and adds 5 practical questions:

- which three templates are mandatory for the first launch;
- whether to show a warning before sensitive data is sent to chat or Web Search;
- who maintains templates after the pilot;
- what simple names should be used for user-facing actions;
- what results must be shown during the demonstration.

## 6. Future scope excluded

The document explicitly excludes from current Stage 2:

- broker reports / 3-НДФЛ;
- OCR / VL OCR;
- full PDF/DOCX/XLSX workflow;
- CRM/task tracker integration;
- automatic task creation in external systems;
- separate "Meetings" section;
- complex meeting workflow;
- PDF export;
- branded DOCX formatting;
- manager visibility;
- retention/no-delete/audit enforcement;
- AD/SSO/SCIM;
- full expense analytics;
- full Web Search governance;
- data masking/tokenization.

## 7. Financial data exclusion check

The new customer-facing document and this report were prepared without monetary
values or commercial terms. Only labor estimates in hours are present.

Validation results for the two new files:

- financial-term scan: no matches;
- secret-like pattern scan: no matches;
- whitespace check: passed;
- UTF-8 BOM check: `239 187 191` for both files;
- docs-only staged diff check: passed.

## 8. Agent creative additions

Added conservative customer-facing improvements without expanding current
Stage 2:

- a plain-language explanation of why this composition is proposed;
- customer-friendly action names such as "Расшифровать", "Сделать протокол",
  "Подготовить письмо" and "Найти источники";
- a suggested acceptance mini-scenario around audio, processed transcript,
  DOCX, Web Search and access matrix;
- a short list of items that are practical to move into the contract appendix;
- 5 additional approval questions that clarify launch priorities and ownership.

## 9. Final verdict

stage2_customer_scope_and_questions_ready
