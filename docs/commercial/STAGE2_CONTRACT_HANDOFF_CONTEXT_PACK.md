# Stage 2 Contract Handoff Context Pack

Status: contract-handoff evidence pack.
Date: 2026-06-30.
Final verdict: `stage2_contract_handoff_context_ready`.

This document is not a contract, act, invoice or legal appendix. It is the
evidence base for preparing those external documents later.

## 1. Main Answer

The current contract-scope candidate should be a limited Stage 2 slice, not the
whole PRD-1.

Recommended scope framing:

```text
First functional and architectural Stage 2 slice for corporate OpenWebUI:
implemented base audio/video transcription inside OpenWebUI, implemented base
Web Search provider baseline, Stage 2 architecture and acceptance materials,
and the next bounded STT v2 slice for transcript post-processing by templates.
```

Already done and safe to describe as implemented:

- base audio/video transcription in OpenWebUI;
- browser ffmpeg.wasm media normalization path;
- OpenWebUI Action/static-loader/private STT sidecar integration;
- Lemonfox first-provider adapter path behind a provider boundary;
- base Web Search provider baseline for Brave, Yandex and private SearXNG;
- Stage 2 architecture, extension-first pattern, gates, backlog and acceptance
  matrix.

Current contract-scope candidates still to implement:

- STT v2 transcript post-processing by templates;
- starter transcript-processing template set;
- template management through native OpenWebUI mechanisms where possible;
- speaker-aware transcript post-processing when provider data is available;
- simple DOCX export of processed result for later manual editing;
- ready Web Search usage scenarios;
- general corporate prompt pack;
- short user onboarding pack;
- basic pilot access matrix.

Future scope must stay outside this contract slice:

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

## 2. Required Inputs Recorded

1. PRD-0 is accepted and closed.
2. Stage 2 / PRD-1 is broader than the current contract slice.
3. The current contract scope should be a limited Stage 2 slice, not all PRD-1.
4. The implemented base already includes transcription, Web Search,
   architecture, extension-first routing, acceptance, gates and backlog.
5. The customer wants to gradually move functionality from an existing separate
   audio transcription web app into OpenWebUI.
6. The main new direction for this contract slice is STT v2: transcript
   post-processing by templates.

## 3. Sources Reviewed

Required documentation reviewed:

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
- STT implementation, runtime, ffmpeg/browser-normalization and UI-proof reports
  under `docs/reports/2026-06-19/`
- Web Search provider/runtime reports under `docs/reports/2026-06-20/` and
  `docs/reports/2026-06-23/`
- OCR / VL OCR research and context docs under `docs/stage2/research/`,
  `docs/stage2/context/` and `docs/reports/2026-06-25/`

Missing required source:

- `docs/commercial/STAGE2_CUSTOMER_DISCUSSION_CHECKLIST.md`

## 4. Code And Config Areas Audited

STT implementation:

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

OpenWebUI integration:

- `deploy/openwebui-static/loader.js`
- `deploy/openwebui-static/stage2-stt-normalization.json`
- `deploy/openwebui-static/stage2-assets/ffmpeg/`
- `compose/openwebui.compose.yml`
- `.env.example`

Web Search and deployment boundaries:

- `docs/stage2/WEB_SEARCH_CONTEXT_INDEX.md`
- `docs/stage2/contracts/`
- `docs/stage2/implementation/WEB_SEARCH_CANDIDATE_SET_COMPARISON_PLAN.md`
- `compose/searxng.private.compose.yml`
- `compose/searxng.debug.compose.yml`
- `deploy/searxng/settings.yml`
- `deploy/searxng/limiter.toml`

No code, compose, env or runtime configuration was changed for this handoff.

## 5. Documentation Vs Code

| Area | Claimed in docs | Evidence in code/config | Evidence in reports | Current status | Notes |
| --- | --- | --- | --- | --- | --- |
| STT base | Stage 2 STT MVP is implemented/proven/current-stage closed. | `services/stage2-stt/stage2_stt/app.py`, `contracts.py`, `jobs.py`, `job_store.py`, tests. | `OPENWEBUI_STT_RUNTIME_COMPLETION.report.md`, `OPENWEBUI_STT_MVP_FEATURE_CLOSURE.report.md`, `NEW_CHAT_CONTEXT_PACK_STT_STAGE2.md`. | DONE | Contract wording can say base transcription path exists. |
| Browser ffmpeg.wasm normalization | Browser-side probe/normalization is part of closed MVP path. | `deploy/openwebui-static/loader.js`, `stage2-stt-normalization.json`, mounted static assets in compose. | `OPENWEBUI_STT_FFMPEG_BROWSER_NORMALIZATION_IMPLEMENTATION.report.md`, ffmpeg proof evidence. | DONE | Use "attempts normalization on supported media", not universal media guarantee. |
| OpenWebUI Action/function integration | Explicit Transcribe action on media attachment. | `stage2_media_transcription_action.py`, loader calls `/api/chat/actions/stage2_media_transcription_action`. | STT runtime and UI proof reports. | DONE | No separate STT GUI and no separate "Meetings" section. |
| Lemonfox provider path | Lemonfox is first provider behind adapter boundary. | `lemonfox.py`, `provider.py`, config defaults, tests. | Lemonfox capability/runtime reports. | DONE | Not hardwired architecture; other providers can be added by adapter. |
| Speaker-aware transcript support / provider JSON support | Provider can return speaker labels and verbose JSON; normalized transcript models preserve speaker fields. | `TranscriptSegmentV1.speaker`, `TranscriptWordV1.speaker`, Lemonfox `speaker_labels` request flag and segment/word normalization. | Lemonfox research and ADR reports. | PARTIAL | Data model supports it; end-user STT v2 speaker-role post-processing is not implemented. |
| STT v2 post-processing | Customer direction: process transcripts by templates. | No STT v2 post-processing route/action found in code. | Scenario/user-story docs mention meeting summaries, decisions and action items. | TO_IMPLEMENT_IN_CURRENT_SCOPE | Main new scope candidate. |
| Template/prompt management | Native OpenWebUI Workspace Prompts are the preferred path. | No new code needed yet; native capability audit proves synthetic shared prompt visibility. | `OPENWEBUI_NATIVE_CAPABILITY_RUNTIME_AUDIT.report.md`, `OPENWEBUI_ADMIN_TEST_USER_RUNTIME_PROOF.report.md`. | TO_IMPLEMENT_IN_CURRENT_SCOPE | Native path exists; production admin/user sharing behavior must be manually verified on the target runtime. |
| DOCX export | PRD-1 contains document/export ambitions, but production document generation is future. | No DOCX export code found in STT service or loader. | PRD/customer summary and backlog place production DOCX/XLSX generation outside base scope. | TO_IMPLEMENT_IN_CURRENT_SCOPE | Only simple DOCX export of processed text should be included. |
| Web Search baseline | Base Web Search provider baseline exists for Brave, Yandex and private SearXNG. | `compose/searxng.private.compose.yml`, `deploy/searxng/`, `.env.example`, native OpenWebUI provider config fields. | Brave/Yandex/SearXNG baseline reports and provider closeout. | DONE | Baseline only, not full governance. |
| Brave provider path | Brave direct-context native baseline. | Native OpenWebUI Web Search config path; no custom sidecar required. | Brave runtime baseline and Web Search context index. | DONE | Primary direct-context baseline. |
| Yandex provider path | Yandex Search API path works by owner/operator Admin UI/native smoke. | `.env.example` and compose expose Yandex Web Search config names. | Yandex runtime baseline report. | DONE | Proof level is operator-confirmed; privacy/data-egress review remains. |
| Private SearXNG path | Private SearXNG comparison path. | `compose/searxng.private.compose.yml`, `deploy/searxng/settings.yml`, `limiter.toml`. | SearXNG private instance and runtime smoke reports. | DONE | Comparison track, not primary provider and not privacy guarantee. |
| Corporate prompt pack | PRD-1 requires shared prompts/templates and native capability audit supports Workspace Prompts. | No final prompt pack code/config artifact found for this slice. | Native capability audit and scenario/user-story docs. | TO_IMPLEMENT_IN_CURRENT_SCOPE | Should be configuration/content work, not fork work. |
| Web Search usage scenarios | PRD/docs require user-ready scenarios for search with sources. | Base provider paths exist; scenario templates are not finalized as user pack. | Web Search context, source attribution contract and selected stories docs. | TO_IMPLEMENT_IN_CURRENT_SCOPE | Include scenario pack, not full governance. |
| Onboarding/user instruction | Docs exist for pilot/user onboarding, but not a short current-scope pack tied to STT v2/Web Search. | No code evidence required. | `docs/pilot/USER_ONBOARDING.md`, Stage 2 docs. | TO_IMPLEMENT_IN_CURRENT_SCOPE | Create a concise user instruction in current scope. |
| Pilot access matrix | Native groups/RBAC synthetic proof exists; production customer matrix is open. | Native capability audit shows groups/resource proof; no production matrix config. | Admin test-user runtime proof and native capability audit. | TO_IMPLEMENT_IN_CURRENT_SCOPE | Basic pilot matrix only; no AD/SSO/SCIM. |
| Architecture/acceptance/backlog | Stage 2 architecture, gates, backlog and acceptance are documented. | Code follows sidecar/adapter/static-loader boundaries. | Stage 2 reports, gates and acceptance matrix. | DONE | May be included as architectural and acceptance documentation result. |
| OCR/VL OCR | Research and infrastructure epic exist. | No production OCR/VL OCR implementation audited for this contract slice. | OCR/VL OCR research V1/V2 and context pack. | RESEARCH_ONLY | Future/research context only. |
| Broker reports / 3-НДФЛ | PRD-1 scenario exists. | No implementation audited for this contract slice. | Broker blueprint and PRD docs. | FUTURE_SCOPE | Not included in current contract scope. |

## 6. Stage 2 Feature Registry

| Result | Status | Contract-scope candidate | Evidence | Notes |
| --- | --- | --- | --- | --- |
| R1. Base audio/video transcription in OpenWebUI | DONE | Yes, implemented result. | STT sidecar/action/loader code, STT runtime reports. | User uploads media, starts transcription, result is returned inside OpenWebUI chat UX. No separate "Meetings" section. |
| R2. STT v2 transcript post-processing by templates | TO_IMPLEMENT_IN_CURRENT_SCOPE | Yes, new work. | PRD/customer summary/scenario docs; no code route yet. | Result should return to the same OpenWebUI chat. |
| R3. Starter transcript-processing template set | TO_IMPLEMENT_IN_CURRENT_SCOPE | Yes, new work. | Native prompt capability and scenario docs. | Templates: short summary, detailed summary, meeting protocol, tasks, decisions, open questions, manager summary, follow-up email. |
| R4. Template management through native OpenWebUI | TO_IMPLEMENT_IN_CURRENT_SCOPE | Yes, with verification gate. | Native capability audit proves Workspace Prompts on synthetic actors. | Avoid heavy separate template editor unless native path is insufficient. |
| R5. Speaker-aware transcript post-processing | TO_IMPLEMENT_IN_CURRENT_SCOPE | Yes, bounded. | STT contracts and Lemonfox adapter preserve speaker fields. | Do not promise exact participant identity. |
| R6. Simple DOCX export of processed result | TO_IMPLEMENT_IN_CURRENT_SCOPE | Yes, bounded. | No code yet; PRD distinguishes simple documents from production generation. | DOCX only, no PDF, no branded formatting guarantee. |
| R7. Web Search baseline | DONE | Yes, implemented baseline. | Web Search context, Brave/Yandex/SearXNG reports, SearXNG config. | Do not include full governance as done. |
| R8. Ready Web Search scenarios | TO_IMPLEMENT_IN_CURRENT_SCOPE | Yes, new content/config work. | Source attribution/privacy contracts and selected stories. | Search current info, compare options, verify claims, find official sources, answer with sources. |
| R9. General corporate prompt pack | TO_IMPLEMENT_IN_CURRENT_SCOPE | Yes, new content/config work. | Native prompt proof and scenario docs. | Rewrite, summary, business memo, client email, clarity check, task list, manager brief, client answer. |
| R10. Short user onboarding pack | TO_IMPLEMENT_IN_CURRENT_SCOPE | Yes, new documentation work. | Pilot/user docs exist but need current-scope packaging. | Cover chat naming, transcription, templates, Web Search, forbidden data and error handling. |
| R11. Basic pilot access matrix | TO_IMPLEMENT_IN_CURRENT_SCOPE | Yes, bounded. | Native capability audit synthetic actor matrix. | Basic pilot model only; no enterprise RBAC, AD/SSO/SCIM. |
| R12. Stage 2 architecture and acceptance documentation | DONE | Yes, implemented documentation result. | Stage 2 README/index/backlog/gates/acceptance and commercial audits. | Some docs may need final polish after contract scope is approved. |

## 7. Current Contract-Scope Candidate

Recommended current contract scope:

1. Preserve and document the implemented base:
   - base STT in OpenWebUI;
   - browser ffmpeg.wasm normalization;
   - Action/static-loader/private-sidecar integration;
   - Lemonfox first-provider adapter path;
   - base Web Search provider baseline;
   - Stage 2 architecture, acceptance and backlog.
2. Add STT v2:
   - template-based transcript post-processing;
   - starter transcript-processing templates;
   - speaker-aware use of provider speaker data where available;
   - simple DOCX export of processed text;
   - result returned in the same OpenWebUI chat.
3. Add user-facing readiness:
   - ready Web Search usage scenarios;
   - corporate prompt pack;
   - short onboarding/user instruction;
   - basic pilot access matrix.

## 8. Future Scope Boundaries

Do not include the following as current-scope implemented results:

- broker reports / 3-НДФЛ;
- OCR / VL OCR as production or accepted pilot;
- full PDF/DOCX/XLSX workflow;
- CRM/task tracker integration;
- automatic task creation in external systems;
- separate "Meetings" section;
- complex meeting workflow;
- PDF export;
- branded DOCX generation;
- manager visibility;
- retention/no-delete/audit enforcement;
- full usage analytics and hard governance;
- full Web Search governance;
- AD/SSO/SCIM;
- data masking/tokenization.

## 9. Rough Effort Estimate

These are rough labor ranges, not financial terms.

| Result | Status | Rough effort, hours | Notes |
| --- | --- | --- | --- |
| R1. Base audio/video transcription in OpenWebUI | DONE | Completed | Evidence exists in code and reports. |
| R2. STT v2 transcript post-processing by templates | TO_IMPLEMENT_IN_CURRENT_SCOPE | 16-32 h | Depends on native prompt/action path selected. |
| R3. Starter transcript-processing template set | TO_IMPLEMENT_IN_CURRENT_SCOPE | 8-16 h | Includes initial template text and smoke examples. |
| R4. Template management through native OpenWebUI | TO_IMPLEMENT_IN_CURRENT_SCOPE | 8-16 h | Requires runtime verification for admin/shared/personal behavior. |
| R5. Speaker-aware transcript post-processing | TO_IMPLEMENT_IN_CURRENT_SCOPE | 8-16 h | Data model exists; UX/post-processing path remains. |
| R6. Simple DOCX export of processed result | TO_IMPLEMENT_IN_CURRENT_SCOPE | 8-16 h | Simple export only. |
| R7. Web Search baseline | DONE | Completed | Evidence exists in docs/reports/config. |
| R8. Ready Web Search scenarios | TO_IMPLEMENT_IN_CURRENT_SCOPE | 4-8 h | Prompt/scenario packaging. |
| R9. General corporate prompt pack | TO_IMPLEMENT_IN_CURRENT_SCOPE | 8-16 h | Configuration/content work. |
| R10. Short user onboarding pack | TO_IMPLEMENT_IN_CURRENT_SCOPE | 4-8 h | Short user-facing instruction. |
| R11. Basic pilot access matrix | TO_IMPLEMENT_IN_CURRENT_SCOPE | 4-8 h | Matrix only, not AD/SCIM. |
| R12. Stage 2 architecture and acceptance documentation | DONE | Completed | May need final contract-scope polish after approval. |

## 10. Draft-Safe Wording For Contract Appendix

Use these as draft-safe wording only. Final legal text belongs outside this
repository.

### General Scope

```text
The first functional and architectural Stage 2 slice of corporate OpenWebUI
includes development of the audio/video transcription module, transcript
post-processing by templates, base Web Search, a starter set of corporate
templates, a user instruction and a basic pilot access model.
```

### STT v2

```text
After receiving a transcript, the user can select one of the prepared text
processing scenarios: short summary, detailed summary, meeting protocol, task
list, decision list, unanswered questions, manager summary or follow-up email.
The system applies the selected template to the transcript text and returns the
result in the OpenWebUI interface.
```

### DOCX

```text
A simple export of the processed result to DOCX is included for later manual
editing by the user. Branded formatting, PDF export and preparation of a final
document without human review are outside the current scope.
```

### Speaker-Aware Processing

```text
If the transcription provider returns speaker labels, the system uses them
during transcript post-processing. The system may also infer semantic speaker
roles from the text when the context supports it. Exact identification of
participant full names is not guaranteed.
```

### Web Search

```text
Base Web Search gives users the ability to search for current information
through the LLM with connected provider paths. Limit policies, extended logging,
hard governance and full Web Search governance are outside the current scope.
```

## 11. Native OpenWebUI Assumptions To Verify

Before using native OpenWebUI as the production template-management path, verify
on the target runtime:

- admin can create and edit shared Workspace Prompts for the approved pilot
  group;
- an approved user can create personal prompts if this is accepted by policy;
- sharing behavior is clear enough for the pilot;
- prompts can be used from the same chat flow as STT transcript output;
- prompt visibility does not leak outside the approved group;
- the current global Web Search permission model is acceptable or can be
  narrowed for the pilot group.

Current repo evidence supports the native-first path, but production group
behavior still needs manual runtime verification before wording it as a
closed operational control.

## 12. Key Discrepancies And Limits

- Documentation describes broad PRD-1; code and runtime evidence close only the
  limited implemented slice.
- STT v2 post-processing is not implemented in code yet.
- Template/prompt management is native-proven on synthetic actors, not finalized
  for the customer production group.
- DOCX export is not implemented yet and should be scoped as simple export only.
- Speaker fields are preserved in transcript models, but end-user speaker-role
  processing is future work.
- Web Search baseline is implemented, but group rollout, forbidden-query policy,
  extended logs and hard governance are not closed.
- OCR/VL OCR and broker reports remain research/future scope, not completed
  contract results.

## 13. Financial And Secret Handling

This context pack intentionally contains no financial amounts, provider keys,
`.env` values, SSH credentials, private tokens, customer transcripts or raw
technical logs.

Financial terms must stay in external contracts, acts and invoices, not in
GitHub markdown.
