# OpenWebUI Stage 2 Contract Handoff Context Pack Report

## 1. Summary

Created:

- `docs/commercial/STAGE2_CONTRACT_HANDOFF_CONTEXT_PACK.md`
- `docs/reports/2026-06-30/OPENWEBUI_STAGE2_CONTRACT_HANDOFF_CONTEXT_PACK.report.md`

The context pack answers the handoff question: the current contract-scope
candidate is a limited Stage 2 slice, not all PRD-1. The implemented base is
STT + browser normalization + OpenWebUI Action/sidecar integration + Lemonfox
adapter + base Web Search + architecture/acceptance materials. The main new
current-scope direction is STT v2 transcript post-processing by templates.

No code, compose, env or runtime config was changed.

## 2. Sources Reviewed

Reviewed and used:

- `README.md`
- `docs/prd/OPENWEBUI_CORPORATE_CHAT_PRD_0.md`
- `docs/prd/OPENWEBUI_CORPORATE_CHAT_PRD_1.md`
- `docs/prd/OPENWEBUI_CORPORATE_CHAT_PRD_1_CUSTOMER_SUMMARY.md`
- existing Stage 2 commercial scope reconciliation and completed-work audit
  documents under `docs/commercial/`
- `docs/stage2/README.md`
- `docs/stage2/CONTEXT_INDEX.md`
- `docs/stage2/ENGINEERING_BACKLOG.md`
- `docs/stage2/IMPLEMENTATION_GATES.md`
- `docs/stage2/acceptance/ACCEPTANCE_MATRIX.md`
- `docs/stage2/WEB_SEARCH_CONTEXT_INDEX.md`
- `docs/stage2/context/NEW_CHAT_CONTEXT_PACK_STT_STAGE2.md`
- `docs/stage2/implementation/OPENWEBUI_NATIVE_CAPABILITY_AUDIT.md`
- STT implementation, runtime, ffmpeg/browser-normalization and UI-proof reports
  under `docs/reports/2026-06-19/`
- Web Search provider/runtime reports under `docs/reports/2026-06-20/` and
  `docs/reports/2026-06-23/`
- OCR / VL OCR research and context docs under `docs/stage2/research/`,
  `docs/stage2/context/` and `docs/reports/2026-06-25/`

Missing source:

- `docs/commercial/STAGE2_CUSTOMER_DISCUSSION_CHECKLIST.md`

Note: OCR / VL OCR materials were reviewed only as future/research context.

## 3. Code/Config Areas Audited

Audited without edits:

- `services/stage2-stt/`
- `services/stage2-stt/stage2_stt/app.py`
- `services/stage2-stt/stage2_stt/contracts.py`
- `services/stage2-stt/stage2_stt/lemonfox.py`
- `services/stage2-stt/stage2_stt/provider.py`
- `services/stage2-stt/stage2_stt/jobs.py`
- `services/stage2-stt/stage2_stt/job_store.py`
- `services/stage2-stt/stage2_stt/validation.py`
- `services/stage2-stt/stage2_stt/storage.py`
- `services/stage2-stt/openwebui_actions/stage2_media_transcription_action.py`
- `services/stage2-stt/tests/`
- `deploy/openwebui-static/loader.js`
- `deploy/openwebui-static/stage2-stt-normalization.json`
- `deploy/openwebui-static/stage2-assets/ffmpeg/`
- `compose/openwebui.compose.yml`
- `compose/searxng.private.compose.yml`
- `compose/searxng.debug.compose.yml`
- `deploy/searxng/settings.yml`
- `deploy/searxng/limiter.toml`
- `.env.example`

## 4. Documentation Vs Code Findings

Main findings:

- STT base is implemented and report-backed.
- Browser ffmpeg.wasm normalization is implemented and report-backed.
- OpenWebUI Action/static-loader/private-sidecar path is implemented.
- Lemonfox is implemented as first provider adapter, not hardwired architecture.
- Transcript data models preserve speaker fields, but speaker-role
  post-processing is not implemented yet.
- STT v2 transcript post-processing by templates is not implemented yet.
- Native OpenWebUI prompt/template path has synthetic runtime proof, but
  production group behavior must be manually verified.
- Simple DOCX export is not implemented yet.
- Base Web Search is implemented as provider baseline for Brave, Yandex and
  private SearXNG.
- Full Web Search governance is not implemented.
- OCR/VL OCR is research-only for this handoff.
- Broker reports / 3-НДФЛ are future scope.

## 5. Stage 2 Feature Registry Created

Created registry in the context pack with these results:

- R1. Base audio/video transcription in OpenWebUI - DONE.
- R2. STT v2 transcript post-processing by templates -
  TO_IMPLEMENT_IN_CURRENT_SCOPE.
- R3. Starter transcript-processing template set -
  TO_IMPLEMENT_IN_CURRENT_SCOPE.
- R4. Template management through native OpenWebUI -
  TO_IMPLEMENT_IN_CURRENT_SCOPE with runtime verification gate.
- R5. Speaker-aware transcript post-processing -
  TO_IMPLEMENT_IN_CURRENT_SCOPE.
- R6. Simple DOCX export of processed result -
  TO_IMPLEMENT_IN_CURRENT_SCOPE.
- R7. Web Search baseline - DONE.
- R8. Ready Web Search scenarios - TO_IMPLEMENT_IN_CURRENT_SCOPE.
- R9. General corporate prompt pack - TO_IMPLEMENT_IN_CURRENT_SCOPE.
- R10. Short user onboarding pack - TO_IMPLEMENT_IN_CURRENT_SCOPE.
- R11. Basic pilot access matrix - TO_IMPLEMENT_IN_CURRENT_SCOPE.
- R12. Stage 2 architecture and acceptance documentation - DONE.

## 6. Current Contract-Scope Candidates

Recommended current contract-scope candidate:

- preserve implemented base STT and Web Search results;
- include Stage 2 architecture, gates, acceptance and backlog as delivered
  evidence;
- implement STT v2 transcript post-processing by templates;
- provide starter transcript-processing templates;
- use native OpenWebUI prompt/template mechanisms where verified;
- preserve speaker labels in post-processing when provider data exists;
- add simple DOCX export of processed text;
- package ready Web Search usage scenarios;
- package general corporate prompts;
- write a short onboarding/user instruction;
- define a basic pilot access matrix.

## 7. Future Scope Boundaries

Explicitly outside current scope:

- broker reports / 3-НДФЛ;
- OCR / VL OCR as production or accepted pilot;
- full PDF/DOCX/XLSX workflow;
- CRM/task tracker integration;
- automatic task creation in external systems;
- separate "Meetings" product section;
- complex meeting workflow;
- PDF export;
- branded DOCX generation;
- manager visibility;
- retention/no-delete/audit enforcement;
- full usage analytics and hard governance;
- full Web Search governance;
- AD/SSO/SCIM;
- data masking/tokenization.

## 8. Native OpenWebUI Assumptions To Verify

Manual verification still needed before final customer wording:

- admin shared prompt creation/editing on target runtime;
- approved user personal prompt creation if policy allows it;
- prompt sharing/visibility for the pilot group;
- prompt use from the same chat flow after transcript insertion;
- no prompt visibility leak outside pilot group;
- Web Search permission narrowing if group-only rollout is required.

## 9. Financial Data Exclusion Check

The new files were written without financial amounts, provider keys, `.env`
values, SSH credentials, private tokens, customer transcripts or raw technical
logs.

Financial terms remain outside GitHub markdown.

Expected result for the new files: no financial-data matches.

## 10. Final Verdict

`stage2_contract_handoff_context_ready`
