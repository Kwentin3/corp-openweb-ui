# OpenWebUI STT v2 Transcript Post-processing Context Pack Report

## 1. Summary

Created engineering context pack:

```text
docs/stage2/context/STT_V2_TRANSCRIPT_POSTPROCESSING_CONTEXT_PACK.md
```

The context pack prepares the next implementation epic:

```text
STT v2: post-processing of transcripts by templates inside OpenWebUI
```

The pack keeps the existing STT MVP architecture intact and scopes the next
work to transcript actions, starter templates, native OpenWebUI prompt/template
reuse, bounded speaker-aware processing and simple DOCX export.

No code, compose or env files were changed by this task.

## 2. Sources reviewed

Mandatory Stage 2/customer sources reviewed:

- `docs/commercial/STAGE2_CUSTOMER_SCOPE_AND_QUESTIONS.md`
- `docs/commercial/STAGE2_CONTRACT_HANDOFF_CONTEXT_PACK.md`
- `docs/commercial/STAGE2_DOCS_REPRESENTATION_MODEL.md`
- `docs/stage2/CONTEXT_INDEX.md`
- `docs/stage2/ENGINEERING_BACKLOG.md`
- `docs/stage2/IMPLEMENTATION_GATES.md`
- `docs/stage2/acceptance/ACCEPTANCE_MATRIX.md`
- `docs/stage2/context/NEW_CHAT_CONTEXT_PACK_STT_STAGE2.md`
- `docs/stage2/contracts/STT_MEDIA_INPUT_NORMALIZATION_CONTRACT.md`

STT reports reviewed under `docs/reports/2026-06-19/`, including:

- `OPENWEBUI_STT_BACKEND_IMPLEMENTATION.report.md`
- `OPENWEBUI_STT_RUNTIME_COMPLETION.report.md`
- `OPENWEBUI_STT_MVP_FEATURE_CLOSURE.report.md`
- `OPENWEBUI_STT_PLAYWRIGHT_UI_PROOF.report.md`
- `OPENWEBUI_STT_FRONTEND_MEDIA_ACTION_PATCH.report.md`
- `OPENWEBUI_STT_FFMPEG_BROWSER_NORMALIZATION_IMPLEMENTATION.report.md`
- `OPENWEBUI_STT_SIDECAR_ROUTING_AUTH_AUDIT.report.md`
- `OPENWEBUI_ADR0004_LEMONFOX_CAPABILITIES_AND_RUNTIME_LIMITS.report.md`
- `OPENWEBUI_ADR0004_OUTPUT_PROFILES_ADAPTER_FACTORY_REFINE.report.md`
- `OPENWEBUI_NATIVE_STT_UX_INTEGRATION_RESEARCH.report.md`

No mandatory document source was missing.

## 3. Code/config audited

Audited STT service and OpenWebUI integration:

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
- `compose/openwebui.compose.yml`

Audit findings:

- transcript result format exists through `TranscriptResultV1`;
- segment and word speaker fields exist;
- Lemonfox verbose JSON normalization exists;
- OpenWebUI Action inserts a flat `Transcript:` result into the chat workflow;
- static loader has a proven media action hook and appends Action output to the
  composer;
- tests cover base STT contracts, provider normalization, job routes and Action
  warning formatting;
- no STT v2 post-processing route/action was found;
- no DOCX implementation or DOCX dependency was found in `services/stage2-stt`;
- `deploy/openwebui-static/stage2-assets/ffmpeg/` is absent in the current
  checkout, which matches repo policy that generated ffmpeg assets are ignored
  and provisioned for runtime separately.

## 4. Current STT base status

Base STT status: implemented, current-stage closed and ready for broader
testing.

Current architecture:

```text
OpenWebUI media attachment
-> static loader Transcribe action
-> browser ffmpeg.wasm normalization where needed
-> OpenWebUI Action Function
-> private stage2-stt sidecar
-> Lemonfox provider adapter
-> transcript returned to OpenWebUI chat workflow
```

The next epic should not reopen this base path unless implementation testing
finds a concrete regression.

## 5. STT v2 scope

In scope:

- post-transcript processing actions;
- starter transcript template set;
- native OpenWebUI prompt/template management where sufficient;
- speaker-aware processing when provider labels are available;
- simple DOCX export of processed result;
- same-chat return path inside OpenWebUI.

Out of scope:

- separate `Meetings` section;
- separate transcript history;
- calendar workflow;
- CRM/task tracker integration;
- automatic external task creation;
- PDF export;
- branded DOCX templates;
- exact participant identification;
- OCR/VL OCR;
- broker reports / NDFL;
- Web Search governance.

## 6. Native OpenWebUI assumptions

Native-first assumptions that must be verified on target runtime:

- admin can create/edit shared Workspace Prompts;
- prompt visibility can be limited to the pilot group;
- personal prompts are either allowed by policy or kept out of the pilot path;
- prompts can be invoked conveniently after transcript creation;
- Action result can expose buttons/structured hints or only plain text;
- static loader can safely add post-processing UI if native prompts are not
  enough;
- OpenWebUI file/artifact behavior can support DOCX download safely;
- the path survives the deployed OpenWebUI version.

## 7. Implementation strategy

Recommended implementation strategy is three-layered:

1. Transcript action discovery.
   Verify native prompts/actions first. If insufficient, add the smallest static
   loader helper to show post-processing actions after transcript creation.

2. Template execution.
   Use the normalized transcript plus selected template and optional user
   context. For speaker-aware templates, preserve `TranscriptResultV1.segments`
   or explicitly serialize speaker-labeled transcript text. Do not depend on
   raw provider JSON.

3. Export.
   Add simple DOCX export for processed result only. Use a minimal backend or
   native artifact path after runtime capability is known.

## 8. Acceptance criteria

STT v2 acceptance criteria added to the context pack:

- user sees processing actions after transcription;
- short summary returns to the same OpenWebUI chat;
- meeting protocol returns structured output to the same chat;
- task extraction marks missing owners/deadlines instead of inventing them;
- speaker labels are used when present;
- processing works when speaker labels are absent;
- DOCX opens in Microsoft Word or LibreOffice;
- DOCX contains no secrets, credentials, internal logs or raw provider payloads;
- no separate STT/meeting portal is created;
- provider credentials do not enter browser or exported content;
- long transcript behavior is explicit;
- target-runtime prompt visibility is verified before production-ready claims.

## 9. Risks and open questions

Key risks:

- native OpenWebUI prompt/template UX may be insufficient;
- static loader hooks are brittle across OpenWebUI upgrades;
- current Action returns flat text and drops structured speaker segments;
- speaker labels depend on provider output and runtime config;
- DOCX export may need a backend endpoint and dependency;
- long transcripts may exceed model context limits;
- generated ffmpeg assets must be provisioned outside Git for runtime tests;
- model output is a draft and requires human review.

Open questions:

- Which transcript templates are mandatory for the first pilot launch?
- Who owns shared template edits after pilot handoff?
- Are personal prompts allowed for pilot users?
- Should DOCX include chat title/date/template name by default?
- What transcript size limit should v2 enforce?
- Which native artifact/export path is available on the target runtime?

## 10. Final verdict

```text
stt_v2_transcript_postprocessing_context_ready
```
