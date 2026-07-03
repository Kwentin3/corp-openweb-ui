# STT v2 Transcript Post-processing Context Pack

## 1. Executive summary

STT v2 is the next layer above the already implemented base transcription path.
The goal is not to reopen STT ingestion, provider routing, browser media
normalization or sidecar architecture. The next epic should turn a returned
transcript into a practical OpenWebUI workflow: choose a processing template,
apply it to the transcript, return the processed result to the same chat, and
optionally export that processed result to a simple DOCX file.

Current code already has the STT sidecar, OpenWebUI Action, static loader,
browser ffmpeg.wasm normalization config, Lemonfox adapter, transcript result
contracts and speaker fields. Current code now also has a generic message-level
DOCX export path. It still does not have a specialized processed-result-only
DOCX artifact path or a separate native OpenWebUI runtime path for template
management on the target stand.

Recommended implementation posture: native-first, extension-first, no separate
"Meetings" app, no separate transcript history store, no heavy OpenWebUI fork.

## 2. Current STT base status

Base STT is implemented and documented as current-stage closed, ready for
broader testing.

Current user path:

1. User uploads audio or video into OpenWebUI.
2. Static loader shows the media `Транскрибировать` action.
3. Browser loader prepares media when needed through ffmpeg.wasm normalization.
4. Loader uploads prepared audio back to OpenWebUI file storage.
5. OpenWebUI Action sends prepared audio to the private `stage2-stt` sidecar.
6. Sidecar validates input, calls the configured provider adapter and returns a
   normalized transcript result.
7. Action returns `Transcript:\n\n...` content.
8. Loader appends that content into the same OpenWebUI composer/chat workflow.

Important base constraints:

- provider credentials stay server-side;
- the browser does not call Lemonfox directly;
- the sidecar is private and mounted behind OpenWebUI/compose, not exposed as a
  separate user portal;
- transcript history is ordinary OpenWebUI chat history unless the user deletes
  the chat;
- there is no separate "Meetings" section in scope;
- ffmpeg.wasm static assets are generated/provisioned assets and are ignored by
  Git. In the current checkout `deploy/openwebui-static/stage2-assets/ffmpeg/`
  is absent, while docs and historical runtime reports state it is provisioned
  on the target/runtime path when media normalization is tested.

## 3. Product goal

Цель STT v2 - превратить базовую транскрибацию в рабочий сценарий обработки
встреч и аудиозаписей внутри OpenWebUI.

The result should feel like a normal OpenWebUI workflow: the user stays in the
chat, sees practical processing actions after transcript creation, receives the
processed result in the same chat, and can manually edit or export the result.

## 4. User workflow

1. Пользователь создает чат под клиента или задачу.
2. Загружает аудио или видео.
3. Запускает транскрибацию.
4. Получает transcript в этом же чате.
5. Видит набор действий обработки.
6. Выбирает нужное действие.
7. Система применяет шаблон к transcript.
8. Результат возвращается в этот же чат.
9. При необходимости пользователь выгружает результат в простой DOCX.

Do not create a separate meeting app. Do not create a separate transcript
history surface. OpenWebUI chat is the durable user context.

## 5. In-scope features

STT v2 post-processing actions:

- `Краткий пересказ`
- `Подробный пересказ`
- `Протокол встречи`
- `Список задач`
- `Список решений`
- `Открытые вопросы`
- `Итоги для руководителя`
- `Письмо по итогам встречи`

Starter transcript template set:

- simple business-language templates;
- predictable output sections;
- suitable for manual editing;
- safe wording that treats model output as a draft, not as final truth.

Native OpenWebUI template management:

- prefer Workspace Prompts / native prompts/templates if runtime behavior is
  sufficient;
- support shared admin templates where native sharing works;
- support personal user templates only if accepted by policy and verified on
  target runtime;
- use minimal custom UI helper only where native OpenWebUI cannot provide the
  required workflow.

Speaker-aware transcript processing:

- preserve and use speaker structure when provider labels are available;
- let the LLM infer semantic speaker roles only when the text supports that;
- do not promise exact person identification.

Simple DOCX export:

- export processed result, not necessarily the full raw transcript;
- no PDF;
- no branded Word templates;
- no complex WYSIWYG editor;
- document is for manual editing in Microsoft Word or LibreOffice.

## 6. Out-of-scope features

- separate `Meetings` section;
- separate transcript history store;
- calendar meeting workflow;
- CRM/task tracker integration;
- automatic task creation in external systems;
- PDF export;
- branded DOCX generation;
- exact identification of participant names;
- guarantee of perfect transcript/provider output;
- separate complex template editor if native OpenWebUI is sufficient;
- OCR/VL OCR;
- broker reports / NDFL;
- Web Search governance.

## 7. Existing code map

| Area | File/path | What exists | Relevant for STT v2 | Gap |
| --- | --- | --- | --- | --- |
| STT FastAPI app | `services/stage2-stt/stage2_stt/app.py` | Capabilities endpoint, job create/result/cancel routes, internal auth, provider call, normalized response, and message-level DOCX export endpoint. | Can remain the base transcript source and, if needed, host export/post-processing support. | No STT v2 template execution; specialized processed-result-only DOCX artifact path remains future. |
| Job creation/result routes | `app.py`, `jobs.py`, `job_store.py` | In-memory job store, typed status, result retrieval, local cancel semantics. | Result route can return `TranscriptResultV1` with segments if v2 needs structured transcript. | Current OpenWebUI Action consumes create response and only returns flat text to user. |
| Provider adapter | `provider.py` | Adapter factory with Lemonfox implementation. | Keeps provider boundary clean; v2 should not depend on raw provider payloads. | Only Lemonfox adapter is registered. |
| Lemonfox adapter | `lemonfox.py` | `verbose_json` request, optional speaker labels, timestamp flags, normalized transcript segments/words. | Speaker-aware processing can rely on normalized segment/word speaker fields. | Provider labels depend on runtime config and provider output quality. |
| Transcript contracts | `contracts.py` | `TranscriptResultV1`, `TranscriptSegmentV1`, `TranscriptWordV1`, speaker fields, warnings. | Stable internal contract for templates, UI and export. | No v2 processed-result contract yet. |
| Speaker fields | `contracts.py`, `lemonfox.py`, `runtime.py`, compose env defaults | Segment and word speaker fields exist; runtime capabilities report speaker-label support. | Enables bounded speaker-aware output. | Default speaker-label flag is off in compose; user-facing Action currently drops segment structure. |
| OpenWebUI Action | `services/stage2-stt/openwebui_actions/stage2_media_transcription_action.py` | Collects uploaded files, calls sidecar, formats warnings, returns `Transcript:` content. | Existing bridge into OpenWebUI Action runtime. | No post-processing actions; no structured transcript returned to frontend beyond flat text. |
| Static loader | `deploy/openwebui-static/loader.js` | Adds `Транскрибировать` button, prepares media, calls Action, appends returned content to composer. | Likely hook for showing post-processing buttons if native prompts are insufficient. | Loader DOM patching is brittle across OpenWebUI upgrades; no v2 UI yet. |
| ffmpeg normalization | `loader.js`, `stage2-stt-normalization.json` | Browser probe/normalization config and profile definitions. | Keep as base media ingestion; v2 should not change it unless testing needs base STT. | Generated `stage2-assets/ffmpeg/` directory is ignored and absent in current checkout. |
| Validation/storage | `validation.py`, `storage.py` | MIME/profile/size checks, storage decision warnings. | Do not bypass backend validation when v2 touches transcript source/result routes. | Storage/retention policy remains production hardening. |
| Tests | `services/stage2-stt/tests/` | Capabilities, config, provider normalization, job routes, validation/storage/job behavior, Action warning tests, and message-level DOCX export tests. | Add focused v2 tests near any new code. | No template execution, speaker-aware output or specialized processed-result DOCX export tests. |
| Compose/static mount | `compose/openwebui.compose.yml` | Mounts loader/config/assets, configures private `stage2-stt` service and STT env defaults. | Confirms extension-first deployment shape. | No v2 env/config; no code change should happen before runtime path is selected. |
| Native prompts/templates docs | `docs/stage2/implementation/OPENWEBUI_NATIVE_CAPABILITY_AUDIT.md`, handoff docs | Native Workspace Prompts are the preferred path and synthetic proof exists. | First-choice template management route. | Target runtime admin/user sharing behavior still needs manual verification. |

## 8. Existing document/report evidence

Read-first sources for the next agent:

- `docs/commercial/STAGE2_CUSTOMER_SCOPE_AND_QUESTIONS.md`
- `docs/commercial/STAGE2_CONTRACT_HANDOFF_CONTEXT_PACK.md`
- `docs/commercial/STAGE2_DOCS_REPRESENTATION_MODEL.md`
- `docs/stage2/CONTEXT_INDEX.md`
- `docs/stage2/ENGINEERING_BACKLOG.md`
- `docs/stage2/IMPLEMENTATION_GATES.md`
- `docs/stage2/acceptance/ACCEPTANCE_MATRIX.md`
- `docs/stage2/context/NEW_CHAT_CONTEXT_PACK_STT_STAGE2.md`
- `docs/stage2/contracts/STT_MEDIA_INPUT_NORMALIZATION_CONTRACT.md`

Key report evidence:

- `docs/reports/2026-06-19/OPENWEBUI_STT_BACKEND_IMPLEMENTATION.report.md`
- `docs/reports/2026-06-19/OPENWEBUI_STT_RUNTIME_COMPLETION.report.md`
- `docs/reports/2026-06-19/OPENWEBUI_STT_MVP_FEATURE_CLOSURE.report.md`
- `docs/reports/2026-06-19/OPENWEBUI_STT_PLAYWRIGHT_UI_PROOF.report.md`
- `docs/reports/2026-06-19/OPENWEBUI_STT_FRONTEND_MEDIA_ACTION_PATCH.report.md`
- `docs/reports/2026-06-19/OPENWEBUI_STT_FFMPEG_BROWSER_NORMALIZATION_IMPLEMENTATION.report.md`
- `docs/reports/2026-06-19/OPENWEBUI_ADR0004_LEMONFOX_CAPABILITIES_AND_RUNTIME_LIMITS.report.md`
- `docs/reports/2026-06-19/OPENWEBUI_ADR0004_OUTPUT_PROFILES_ADAPTER_FACTORY_REFINE.report.md`
- `docs/reports/2026-06-19/OPENWEBUI_STT_SIDECAR_ROUTING_AUTH_AUDIT.report.md`
- `docs/reports/2026-06-19/OPENWEBUI_NATIVE_STT_UX_INTEGRATION_RESEARCH.report.md`

Evidence summary:

- base STT MVP is implemented and current-stage closed;
- Lemonfox provider path is the first adapter path;
- browser ffmpeg.wasm normalization has historical runtime proof on synthetic
  media;
- current UI path is an OpenWebUI media action plus a static loader patch;
- speaker fields are modeled and normalized, but not yet used in end-user
  post-processing;
- native Workspace Prompts are preferred but still require target-runtime
  verification for production sharing/visibility behavior;
- generic message-level DOCX export is implemented/proven; specialized
  processed-result-only DOCX export remains future work.

## 9. Native OpenWebUI capabilities to reuse

Reuse before custom building:

- OpenWebUI chat as the only user-facing history surface.
- OpenWebUI Action/Function runtime for the existing transcription bridge.
- Workspace Prompts / native prompts/templates for approved transcript
  processing templates if runtime behavior is sufficient.
- Native group visibility/sharing controls for shared prompts, if verified on
  target runtime.
- Existing static loader only as the minimal helper for media action discovery
  and, if required, post-processing buttons.
- Existing generic message-level DOCX browser download path for selected
  assistant messages.
- OpenWebUI file storage/download behavior remains relevant only if a future
  processed-result-only artifact path needs stored files instead of base64
  browser delivery.

Native assumptions to verify:

- admin can create and edit shared Workspace Prompts for the approved pilot
  group;
- prompt visibility can be limited to the approved group;
- user personal prompts are either allowed by policy or disabled/ignored;
- user can conveniently invoke a prompt after transcript appears;
- Action result can expose buttons or structured hints, or only plain text;
- static loader can safely add post-processing UI without breaking normal chat;
- this path survives the currently deployed OpenWebUI version;
- chat/file storage behavior is acceptable for transcript and DOCX artifacts;
- there is a native artifact/export mechanism worth reusing.

## 10. Proposed implementation strategy

### Layer 1. Transcript action discovery

First verify whether native OpenWebUI can make transcript templates visible and
easy to invoke immediately after the transcript appears. If native UX is enough,
prefer it and avoid extra loader logic.

If native UX is not enough, extend the static loader in the smallest possible
way:

- detect the successful STT insertion point;
- render a compact post-processing action set near the transcript status or
  transcript block;
- keep labels business-readable;
- do not expose provider details or internal sidecar routes;
- do not add a separate page.

### Layer 2. Template execution

Canonical processing shape:

```text
transcript + selected_template + optional_user_context + optional_speaker_structure
-> OpenWebUI model path
-> processed_result
-> same OpenWebUI chat
```

Template execution should depend on normalized transcript data, not raw Lemonfox
payloads. For speaker-aware output, v2 must preserve structured
`TranscriptResultV1.segments` or explicitly serialize a speaker-labeled
transcript. The current Action path only forwards `result.text`, so it is not
enough for full speaker-aware processing by itself.

Do not add a new provider integration for post-processing unless the existing
OpenWebUI model path cannot run the template flow.

### Layer 3. Export

Generic message-level DOCX export is already implemented as the current
extension path. Add a specialized processed-result-only DOCX export only if the
product needs a stricter artifact contract around `PostProcessingResultV1`.
Keep layout intentionally simple:

```text
title
date/chat name if available
template name
body
```

No PDF, no branded Word template, no complex document editor.

## 11. Transcript template set

| Template | User label | Output shape |
| --- | --- | --- |
| Short summary | `Краткий пересказ` | 5-8 bullets, key topic, outcome, caveats. |
| Detailed summary | `Подробный пересказ` | Structured sections by topic, important details, unresolved areas. |
| Meeting protocol | `Протокол встречи` | Topic, participants if known, agenda, discussion, decisions, tasks, open questions. |
| Action items | `Список задач` | Task, owner if inferable, deadline if mentioned, source phrase/context. |
| Decisions | `Список решений` | Decision, rationale, affected area, uncertainty if any. |
| Open questions | `Открытые вопросы` | Question, context, who should answer if inferable. |
| Manager brief | `Итоги для руководителя` | Short management summary, risks, required approvals, next steps. |
| Follow-up email | `Письмо по итогам встречи` | Polite email draft, concise recap, tasks, next contact. |

Template rules:

- output is a draft for human review;
- missing facts must be marked as missing, not invented;
- speaker names/roles are tentative unless explicitly present in transcript;
- keep business tone and avoid provider/internal terminology;
- preserve important uncertainty.

## 12. Speaker-aware processing

Current backend support:

- `TranscriptSegmentV1.speaker` exists;
- `TranscriptWordV1.speaker` exists;
- Lemonfox adapter normalizes segment and word speakers from verbose JSON;
- runtime capabilities can report `supports_speaker_labels`;
- compose defaults currently keep speaker labels disabled unless explicitly
  enabled in runtime config.

STT v2 requirement:

- if speaker labels exist, include them in template input as stable normalized
  structure;
- if labels are absent, templates must still work without error;
- if labels are anonymous (`speaker_0`, `speaker_1` or similar), keep them as
  labels and optionally ask the model to infer semantic roles from context;
- safe wording: "Система может предложить смысловые роли говорящих по тексту,
  если это возможно из контекста."

Implementation warning: the current OpenWebUI Action returns only flat text. A
speaker-aware implementation must either keep the structured transcript result
available to the post-processing step or produce a speaker-labeled transcript
text format before invoking templates.

## 13. DOCX export

Current status:

- generic message-level DOCX export exists through
  `POST /stage2-api/message-docx/exports`;
- `python-docx` is declared in `services/stage2-stt/pyproject.toml`;
- markdown-first `semantic_chat_v1` preserves headings, lists, tables,
  blockquotes, links and code blocks when canonical message markdown or
  sanitized selected-message HTML is available;
- browser save/open proof was confirmed by operator on the deployed runtime;
- customer scope still includes only a simple DOCX draft for manual editing.

Recommended scope:

- export the processed result, not the full raw transcript by default;
- include template name and date/chat title if safely available;
- include warnings that the result is a draft if template output contains
  uncertainty;
- ensure file opens in Microsoft Word and LibreOffice;
- do not include internal logs, provider payloads, tokens, sidecar URLs or
  hidden prompt/config values.

Potential implementation paths to compare only for future specialized
processed-result artifacts:

- native OpenWebUI artifact/download mechanism, if available;
- small sidecar endpoint that accepts processed text and returns DOCX;
- Action-level generated file if OpenWebUI supports safe file return from
  Actions.

## 14. Data/security boundaries

- Provider credentials and internal sidecar auth stay server-side.
- Browser UI never receives Lemonfox credentials or raw provider response.
- Template execution uses transcript content and approved template text only.
- Do not commit real customer media, transcripts, prompts containing private
  data, raw runtime logs or provider responses.
- Do not log full transcripts in backend logs for proof.
- DOCX export must contain only user-visible processed content and safe metadata.
- If post-processing uses speaker structure, pass normalized internal fields,
  not raw provider JSON.
- Long transcripts need explicit limits, chunking or refusal behavior before
  production use.
- User-facing output remains a draft requiring human review.

## 15. Acceptance criteria

A1. After transcription, the user sees available transcript-processing actions.

A2. `Краткий пересказ` applies the transcript and returns the processed result
to the same OpenWebUI chat.

A3. `Протокол встречи` applies the transcript and returns a structured meeting
protocol to the same chat.

A4. `Список задач` extracts action items from the transcript and marks missing
owners/deadlines instead of inventing them.

A5. If transcript speaker labels exist, post-processing uses them.

A6. If speaker labels are absent, all templates still work without error.

A7. DOCX export creates a file that opens in Microsoft Word or LibreOffice.

A8. DOCX export contains no secrets, provider credentials, raw internal logs or
raw provider payloads.

A9. User stays in OpenWebUI; no separate STT/meeting portal is created.

A10. Provider credentials do not enter browser code, static config, chat output
or exported documents.

A11. Long transcript behavior is explicit: process, chunk or fail with a clear
user-facing message.

A12. Template management path is verified for admin/shared visibility on the
target runtime before claiming production readiness.

## 16. Risks and open questions

Risks:

- native OpenWebUI prompts/templates may be insufficient for the full desired
  post-transcript UX;
- static loader UI hooks are brittle across OpenWebUI upgrades;
- Action result shape may not support buttons or structured UI;
- speaker labels depend on provider output and runtime config;
- the current Action drops structured segment data unless changed;
- DOCX export may require a backend endpoint and a new dependency;
- long transcripts may exceed model context limits;
- prompt outputs require human review and can omit or distort details;
- generated ffmpeg assets are not present in Git and must be provisioned for
  media-normalization runtime tests.

Open questions:

- Which three transcript templates are mandatory for the first pilot launch?
- Should users be allowed to create personal transcript templates?
- Who owns shared template edits after pilot handoff?
- Should DOCX include chat title/date/template name by default?
- What maximum transcript size should be accepted for v2 post-processing?
- Is the target runtime's native prompt visibility sufficient for group-scoped
  templates?
- Does the target OpenWebUI version provide a safe artifact/download mechanism?

## 17. Recommended first implementation task

Recommended first task:

```text
Audit native OpenWebUI prompt/template/action capabilities on target runtime and
choose the minimal implementation path for transcript post-processing
buttons/actions.
```

Reason: documents and code are enough to start design, but the production path
depends on target-runtime behavior that was not re-verified in this docs-only
context-pack task: shared Workspace Prompts visibility, Action result UI shape,
post-transcript invocation ergonomics and artifact/export support.
