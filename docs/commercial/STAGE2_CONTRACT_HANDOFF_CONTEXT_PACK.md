# Stage 2 Contract Handoff Context Pack

Status: contract-handoff evidence pack, updated after STT v2 closure.
Date: 2026-07-05.
Final verdict: `stage2_contract_handoff_context_updated_after_stt_v2_closure`.

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
implemented STT v2 transcript post-processing in current-scope MVP form, and
implemented message-level DOCX export for selected completed assistant messages.
```

Already done and safe to describe as implemented:

- base audio/video transcription in OpenWebUI;
- browser ffmpeg.wasm media normalization path;
- OpenWebUI Action/static-loader/private STT sidecar integration;
- Lemonfox first-provider adapter path behind a provider boundary;
- STT v2 transcript post-processing quick actions;
- starter STT v2 template set: short summary and meeting protocol;
- native OpenWebUI Prompt catalog path for the STT v2 MVP templates;
- speaker-aware raw transcript projection when provider labels are available;
- message-level DOCX export for selected completed assistant messages;
- base Web Search provider baseline for Brave, Yandex and private SearXNG;
- Stage 2 architecture, extension-first pattern, gates, backlog and acceptance
  matrix.

Current contract-scope candidates still to implement:

- ready Web Search usage scenarios;
- general corporate prompt pack;
- short user onboarding pack;
- basic pilot access matrix.
- broker reports / 3-НДФЛ limited pilot, if approved as the next active epic.

Future scope must stay outside this contract slice:

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
6. STT v2 transcript post-processing and message-level DOCX export are now
   closed in the current Stage 2 scope.
7. The next active functional direction is the broker reports / 3-НДФЛ limited
   pilot, while Web Search scenarios, general prompt pack, onboarding and access
   matrix remain packaging/readiness work.

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
| Speaker-aware transcript support / provider JSON support | Provider can return speaker labels and verbose JSON; normalized transcript models preserve speaker fields. | `TranscriptSegmentV1.speaker`, `TranscriptWordV1.speaker`, Lemonfox `speaker_labels` request flag, Action speaker-turn formatter. | Gate 1-2 proof and readable raw transcript projection report. | DONE / CLOSED_IN_CURRENT_SCOPE | Uses generic speaker labels when available; exact real participant names remain out of scope. |
| STT v2 post-processing | Current scope: process transcripts by approved templates and return result in the same chat. | `post_processing.py`, post-processing routes in `app.py`, Action operations `list_postprocessing_templates`, `execute_postprocessing`, `draft_postprocessing_prompt`, loader quick actions. | Gate 3, Gate 4, Gate 5 and native prompt quick-action reports. | DONE / CLOSED_IN_CURRENT_SCOPE | Closed for two MVP templates; chunking/map-reduce and larger template library remain future. |
| Template/prompt management | Native OpenWebUI Prompts are the current MVP path. | `prompt_catalog.py`, post-processing prompt draft route, Action prompt-draft operation. | Prompt catalog, prompt access/version proof and native quick-action reports. | DONE / CLOSED_IN_CURRENT_SCOPE | Separate complex template editor and Prompt API adapter remain future. |
| DOCX export | Generic message-level DOCX export is implemented for selected completed assistant messages. | `message_docx.py`, `POST /stage2-api/message-docx/exports`, Action `export_message_docx`, loader DOCX toolbar button. | Message-level DOCX export proof report; operator save/open proof. | DONE / CLOSED_IN_CURRENT_SCOPE | Specialized processed-result-only DOCX artifact path, PDF and branded Word templates remain future. |
| Web Search baseline | Base Web Search provider baseline exists for Brave, Yandex and private SearXNG. | `compose/searxng.private.compose.yml`, `deploy/searxng/`, `.env.example`, native OpenWebUI provider config fields. | Brave/Yandex/SearXNG baseline reports and provider closeout. | DONE | Baseline only, not full governance. |
| Brave provider path | Brave direct-context native baseline. | Native OpenWebUI Web Search config path; no custom sidecar required. | Brave runtime baseline and Web Search context index. | DONE | Primary direct-context baseline. |
| Yandex provider path | Yandex Search API path works by owner/operator Admin UI/native smoke. | `.env.example` and compose expose Yandex Web Search config names. | Yandex runtime baseline report. | DONE | Proof level is operator-confirmed; privacy/data-egress review remains. |
| Private SearXNG path | Private SearXNG comparison path. | `compose/searxng.private.compose.yml`, `deploy/searxng/settings.yml`, `limiter.toml`. | SearXNG private instance and runtime smoke reports. | DONE | Comparison track, not primary provider and not privacy guarantee. |
| Corporate prompt pack | PRD-1 requires shared prompts/templates and native capability audit supports Workspace Prompts. | No final prompt pack code/config artifact found for this slice. | Native capability audit and scenario/user-story docs. | TO_IMPLEMENT_IN_CURRENT_SCOPE | Should be configuration/content work, not fork work. |
| Web Search usage scenarios | PRD/docs require user-ready scenarios for search with sources. | Base provider paths exist; scenario templates are not finalized as user pack. | Web Search context, source attribution contract and selected stories docs. | TO_IMPLEMENT_IN_CURRENT_SCOPE | Include scenario pack, not full governance. |
| Onboarding/user instruction | Docs exist for pilot/user onboarding, but not a short current-scope pack for the closed Stage 2 capabilities. | No code evidence required. | `docs/pilot/USER_ONBOARDING.md`, Stage 2 docs. | TO_IMPLEMENT_IN_CURRENT_SCOPE | Create a concise user instruction in current scope. |
| Pilot access matrix | Native groups/RBAC synthetic proof exists; production customer matrix is open. | Native capability audit shows groups/resource proof; no production matrix config. | Admin test-user runtime proof and native capability audit. | TO_IMPLEMENT_IN_CURRENT_SCOPE | Basic pilot matrix only; no AD/SSO/SCIM. |
| Architecture/acceptance/backlog | Stage 2 architecture, gates, backlog and acceptance are documented. | Code follows sidecar/adapter/static-loader boundaries. | Stage 2 reports, gates and acceptance matrix. | DONE | May be included as architectural and acceptance documentation result. |
| OCR/VL OCR | Research and infrastructure epic exist. | No production OCR/VL OCR implementation audited for this contract slice. | OCR/VL OCR research V1/V2 and context pack. | RESEARCH_ONLY | Future/research context only. |
| Broker reports / 3-НДФЛ | PRD-1 scenario exists. | No implementation audited for this contract slice. | Broker blueprint and PRD docs. | FUTURE_SCOPE | Not included in current contract scope. |

## 6. Stage 2 Feature Registry

| Result | Status | Contract-scope candidate | Evidence | Notes |
| --- | --- | --- | --- | --- |
| R1. Base audio/video transcription in OpenWebUI | DONE | Yes, implemented result. | STT sidecar/action/loader code, STT runtime reports. | User uploads media, starts transcription, result is returned inside OpenWebUI chat UX. No separate "Meetings" section. |
| R2. STT v2 transcript post-processing by templates | DONE / CLOSED_IN_CURRENT_SCOPE | Yes, implemented result. | Post-processing service/routes, Action quick actions, native prompt quick-action proof. | Result returns to the same OpenWebUI chat flow. |
| R3. Starter transcript-processing template set | DONE / CLOSED_IN_CURRENT_SCOPE | Yes, implemented result. | Prompt catalog proof and OpenWebUI prompt records. | Closed starter set: short summary and meeting protocol. Additional templates remain future. |
| R4. Template management through native OpenWebUI | DONE / CLOSED_IN_CURRENT_SCOPE | Yes, implemented result. | Prompt catalog/access/version proof. | Native OpenWebUI Prompts path; no heavy separate template editor. |
| R5. Speaker-aware transcript post-processing | DONE / CLOSED_IN_CURRENT_SCOPE | Yes, bounded implemented result. | STT contracts, Lemonfox adapter, Action speaker-turn projection, tests. | Do not promise exact participant identity. |
| R6. Simple DOCX export of processed result | DONE / CLOSED_IN_CURRENT_SCOPE | Yes, implemented result. | Message-level DOCX endpoint, renderer, Action/loader, proof report. | Generic selected-message export; no PDF, no branded formatting guarantee. |
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
2. Preserve closed STT v2 current-scope results:
   - template-based transcript post-processing;
   - starter transcript-processing templates;
   - speaker-aware use of provider speaker data where available;
   - message-level DOCX export for selected completed assistant messages;
   - result returned in the same OpenWebUI chat.
3. Add user-facing readiness:
   - ready Web Search usage scenarios;
   - corporate prompt pack;
   - short onboarding/user instruction;
   - basic pilot access matrix.
4. Prepare broker reports / 3-НДФЛ limited pilot as the next active functional
   epic only after customer test data and methodology inputs are available.

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
| R2. STT v2 transcript post-processing by templates | DONE / CLOSED_IN_CURRENT_SCOPE | Completed | Two MVP quick actions are implemented and deployed. |
| R3. Starter transcript-processing template set | DONE / CLOSED_IN_CURRENT_SCOPE | Completed | Short summary and meeting protocol are implemented. |
| R4. Template management through native OpenWebUI | DONE / CLOSED_IN_CURRENT_SCOPE | Completed | Native OpenWebUI Prompts path is used for the MVP. |
| R5. Speaker-aware transcript post-processing | DONE / CLOSED_IN_CURRENT_SCOPE | Completed | Speaker labels are used when provider data is available. |
| R6. Simple DOCX export of processed result | DONE / CLOSED_IN_CURRENT_SCOPE | Completed | Generic selected assistant-message DOCX export is implemented. |
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

Current repo evidence supports the native-first path and closes the two-template
MVP path. Production group behavior still needs manual runtime verification
before wording it as a broader closed operational control.

## 12. Key Discrepancies And Limits

- Documentation describes broad PRD-1; code and runtime evidence close only the
  limited implemented slice.
- STT v2 post-processing is implemented for the current MVP scope, but long
  transcript chunking/map-reduce and the full template library are future work.
- Template/prompt management is implemented through native OpenWebUI Prompts for
  the MVP; broader customer production group policy remains to verify.
- DOCX export is implemented as generic selected-message export; specialized
  processed-result-only artifact export, PDF and branded Word templates are
  future work.
- Speaker-aware output is implemented when labels exist; exact real participant
  identity remains outside the guarantee.
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
