# Stage 2 Context Index

Цель: быстро понять, какие документы читать по конкретной будущей задаче.

Этот файл - главный маршрутизатор контекста Stage 2. Правила чтения и
ограничения вынесены в [CONTEXT_USAGE_RULES.md](CONTEXT_USAGE_RULES.md).

Статус: навигационный индекс. Не является разрешением на implementation,
runtime changes, provider setup или использование customer data.

## Gate 2 LLM-friendly context, 2026-07-12

- [Исследование состава и дублирования Gate 2 LLM-контекста](../reports/2026-07-12/OPENWEBUI_BROKER_REPORTS_GATE2_LLM_CONTEXT_RESEARCH.report.md)
- [Рефакторинг контекста и повтор одного реального PDF](../reports/2026-07-12/OPENWEBUI_BROKER_REPORTS_GATE2_LLM_CONTEXT_REFACTOR_AND_SINGLE_PDF_RECOVERY.report.md)

## How to use this index

1. Определи тип задачи и домен: planning, selected stories, synthetic data,
   proof execution, implementation planning, customer-facing proposal, Web
   Search, STT, OCR/VL OCR, analytics, provider/model catalog, data policy,
   manager visibility/retention or operations.
2. Открой соответствующий route ниже.
3. Сначала прочитай `Read first`.
4. Затем прочитай `Additional context`, если задача касается статуса,
   blockers, соседнего домена or acceptance.
5. Перед runtime/implementation обязательно открой
   [IMPLEMENTATION_GATES.md](IMPLEMENTATION_GATES.md) and
   [CONTRACT_BOUNDARIES.md](CONTRACT_BOUNDARIES.md).
6. Если статусы противоречат друг другу, не продолжай silently. Зафиксируй
   conflict: документы, строки, расхождение and owner decision needed.

Do not read `.env`, secrets, tokens, credentials, private URLs or customer data
unless a separate task explicitly approves it. Do not run runtime proof, change
OpenWebUI config or create users/groups/models/prompts/Knowledge from a
docs-only route.

Compact route map:

- selected stories / synthetic data / proof prep: start with
  [Selected stories / synthetic data / proof prep](#selected-stories--synthetic-data--proof-prep);
- first route choice: use
  [Task-specific routing shortcuts](#task-specific-routing-shortcuts);
- runtime/proof tasks: use
  [Proof execution / runtime checks](#proof-execution--runtime-checks);
- implementation tasks: use [Implementation planning](#implementation-planning);
- provider setup/accounts: use
  [Provider setup / provider accounts](#provider-setup--provider-accounts);
- Web Search and OCR/VL OCR: use [Web-search](#web-search) or
  [Documents / OCR / Excel](#documents--ocr--excel); OCR / VL OCR epic starts
  from [OCR / VL OCR Infrastructure Epic Context Pack](context/OCR_VL_OCR_INFRASTRUCTURE_EPIC_CONTEXT_PACK.md);
- customer-facing materials: use
  [Customer-facing proposals](#customer-facing-proposals).

## Stage 2 documentation representation

Current documentation split:

- Customer-facing source of truth:
  [STAGE2_CUSTOMER_SCOPE_AND_QUESTIONS](../commercial/STAGE2_CUSTOMER_SCOPE_AND_QUESTIONS.md)
  Current note, 2026-07-05: STT v2 current-scope items are closed there;
  broker reports / 3-НДФЛ remains the next active functional epic candidate.

- Internal contract/evidence handoff:
  [STAGE2_CONTRACT_HANDOFF_CONTEXT_PACK](../commercial/STAGE2_CONTRACT_HANDOFF_CONTEXT_PACK.md)

- Documentation representation model:
  [STAGE2_DOCS_REPRESENTATION_MODEL](../commercial/STAGE2_DOCS_REPRESENTATION_MODEL.md)

- Reports:
  dated evidence and historical context, not customer-facing source documents.

## Source of truth hierarchy

| Level | Source | Rule |
| ----- | ------ | ---- |
| 1 | [PRD-1](../prd/OPENWEBUI_CORPORATE_CHAT_PRD_1.md) | Главный продуктовый источник. |
| 2 | [Stage 2 README](README.md) / this index | Навигация and context routing. |
| 3 | [ROADMAP](ROADMAP.md) | Порядок движения и phase/status frame. |
| 4 | [IMPLEMENTATION_GATES](IMPLEMENTATION_GATES.md) | Условия перехода к implementation/runtime work. |
| 5 | [CONTRACT_BOUNDARIES](CONTRACT_BOUNDARIES.md) | Границы backend/frontend/custom logic/provider calls. |
| 6 | [ENGINEERING_BACKLOG](ENGINEERING_BACKLOG.md) | Текущий planning/status backlog. |
| 7 | ADRs | Решения только если approved; proposed ADR is not final decision. |
| 8 | Reports | Evidence: что было проверено. |
| 9 | Research | Контекст and варианты; не команда к реализации. |
| 10 | Proposals | Customer-facing documents; not engineering backlog. |
| 11 | User stories / selected stories | Planning artifacts; not production scope. |
| 12 | Synthetic data docs | Mechanics only; not customer acceptance. |
| 13 | Proof plans | Plans only; not executed proof. |

Если более низкий уровень противоречит gate/contract/approved ADR, используй
gate/contract/approved ADR как ограничение и зафиксируй conflict.

## Document type rules

- Research не является решением.
- Report не является планом реализации.
- Proposal не является backlog.
- Draft/proposed ADR не является approved decision.
- Synthetic data не доказывает качество на реальных данных.
- Docs-only document не разрешает runtime changes.
- Customer-facing document не должен использоваться как engineering source без
  связанного internal doc.
- Proof plan не означает, что proof выполнен.

## Global guardrails

Запрещено без отдельного approval:

- не использовать customer data;
- не запускать runtime proof or smoke;
- не читать `.env`, secrets, tokens, credentials or private URLs;
- не подключать provider accounts;
- не создавать users/groups/models/prompts/Knowledge;
- не менять OpenWebUI config;
- не писать production code;
- не считать synthetic proof production acceptance;
- не считать proposed ADR approved;
- не считать customer proposal implementation task.
- Web Search smoke/proven connectivity does not approve production rollout.
  Если Web Search smoke прошёл, это значит только, что техническая связность
  проверена. Это не значит, что Web Search можно включать всем пользователям.
- OCR/VL OCR synthetic benchmark does not prove production OCR readiness. Если
  benchmark пройден на synthetic data, это не значит, что OCR готов к реальным
  документам заказчика.

## Общий Stage 2 scope

Read first:

- [PRD-1](../prd/OPENWEBUI_CORPORATE_CHAT_PRD_1.md)
- [README](README.md)
- [CONTEXT_USAGE_RULES](CONTEXT_USAGE_RULES.md)
- [Stage 2 Unblocked Work Plan](implementation/STAGE2_UNBLOCKED_WORK_PLAN.md)
- [DOMAIN_MAP](DOMAIN_MAP.md)
- [CONTRACT_BOUNDARIES](CONTRACT_BOUNDARIES.md)
- [EXTENSION_FIRST_IMPLEMENTATION_PATTERN](EXTENSION_FIRST_IMPLEMENTATION_PATTERN.md)
- [IMPLEMENTATION_GATES](IMPLEMENTATION_GATES.md)

Additional context:

- [OpenWebUI native capability audit](implementation/OPENWEBUI_NATIVE_CAPABILITY_AUDIT.md)
- [OpenWebUI native capability runtime audit report](../reports/2026-06-24/OPENWEBUI_NATIVE_CAPABILITY_RUNTIME_AUDIT.report.md)
- [OpenWebUI admin/test-user runtime proof report](../reports/2026-06-24/OPENWEBUI_ADMIN_TEST_USER_RUNTIME_PROOF.report.md)
- [Customer Stage 2 Governance Proposal](proposals/CUSTOMER_STAGE2_GOVERNANCE_PROPOSAL.md)
- [Customer runtime decisions / решения после runtime-аудита](proposals/CUSTOMER_STAGE2_RUNTIME_DECISIONS.md)
- [Workspace scenario user stories](implementation/WORKSPACE_SCENARIO_USER_STORIES.md)
- [Synthetic test data index](testdata/SYNTHETIC_TEST_DATA_INDEX.md)
- [Customer summary](../prd/OPENWEBUI_CORPORATE_CHAT_PRD_1_CUSTOMER_SUMMARY.md)
- [PRD-0 audit](../reports/2026-06-16/OPENWEBUI_PRD_0_POST_ACCEPTANCE_AUDIT.report.md)

Skip unless needed:

- PRD-0 deploy runbooks.

Comment:

- PRD-1 is the source of truth.
- Stage 2 custom logic must stay behind backend/domain contracts.
- OpenWebUI-facing features should follow the extension-first order before a
  fork: native mechanisms, Functions/Actions/Tools, thin static loader/UI shim,
  private sidecar, then fork only with proof and owner/ADR approval.
- For STT, user-facing UX must remain inside OpenWebUI; the sidecar is
  backend-only.
- MVP STT trigger is explicit `Transcribe` action on an audio/video media
  attachment.

## Selected stories / synthetic data / proof prep

Use this route for tasks about selected stories, synthetic data requirements,
proof plans, first execution package or follow-up proof preparation.

Read first:

1. [Stage 2 Selected User Stories](implementation/STAGE2_SELECTED_USER_STORIES.md)
2. [Stage 2 Selected Stories Synthetic Data Requirements](testdata/STAGE2_SELECTED_STORIES_SYNTHETIC_DATA_REQUIREMENTS.md)
3. [Stage 2 Selected Stories Proof Plans](implementation/STAGE2_SELECTED_STORIES_PROOF_PLANS.md)
4. [Selected Stories Proof Prep Report](../reports/2026-06-25/OPENWEBUI_STAGE2_SELECTED_STORIES_PROOF_PREP.report.md)
5. [Synthetic Test Data Index](testdata/SYNTHETIC_TEST_DATA_INDEX.md)
6. [Acceptance Matrix](acceptance/ACCEPTANCE_MATRIX.md)
7. [Implementation Gates](IMPLEMENTATION_GATES.md)

Additional context:

- [Stage 2 Scenario Shortlist](implementation/STAGE2_SCENARIO_SHORTLIST.md)
- [Workspace Scenario User Stories](implementation/WORKSPACE_SCENARIO_USER_STORIES.md)
- [Stage 2 Unblocked Work Plan](implementation/STAGE2_UNBLOCKED_WORK_PLAN.md)
- [Corporate AI Workspace Use Cases Research](research/CORPORATE_AI_WORKSPACE_USE_CASES_RESEARCH.md)

Do not do:

- do not create synthetic files unless the task explicitly asks for it;
- do not execute proof plans without separate runtime approval;
- do not use customer data;
- do not create users, groups, models, prompts or Knowledge;
- do not change OpenWebUI config.

Blockers / gates:

- customer acceptance remains blocked for real documents, real groups,
  provider/data policy, expected outputs and customer decisions;
- proof plans have `Runtime changes needed: none` for the docs-only package;
- runtime proof requires a separate approved task and Gate 7 context.

## Task-specific routing shortcuts

Use this table to choose the detailed route below.

| Task type | Start route | Must also read | Do not do | Blockers / gates |
| --------- | ----------- | -------------- | --------- | ---------------- |
| Unblocked planning | Unblocked planning | Context usage rules, backlog, acceptance | Runtime/config/customer-data actions | Customer decisions still open. |
| Scenario selection / user stories | Selected stories or Unblocked planning | Shortlist, user stories, research report | Treat draft stories as production scope | Real roles, owners and customer workflows. |
| Synthetic data creation | Selected stories / synthetic data / proof prep | Synthetic index, test data requirements | Use real names, customer docs, secrets or private URLs | Customer acceptance still needs real data. |
| Proof plan execution | Operations / acceptance plus selected proof plans | Implementation gates, contract boundaries, acceptance matrix | Run proof from docs-only task | Separate runtime approval and Gate 7 context. |
| Implementation planning | Domain isolation / contract boundaries | ROADMAP, gates, backlog, ADRs | Start code/config before gates | Gates 1-9 as applicable. |
| Web Search | Web-search | Data policy, usage/cost, selected proof route if query matrix task | Use private/customer queries or rollout globally | Rollout policy, logs, cost, group defaults. |
| STT | Транскрибация | ADR-0004, gates, contract boundaries | Re-plan STT MVP from zero | Production hardening, retention, media samples. |
| OCR / VL OCR | Documents / OCR / Excel | OCR / VL OCR epic context pack, test data requirements, ADR-0005 | Execute ST2-US-013 as proof or promise production OCR quality | Infrastructure epic, customer samples and provider/data policy. |
| Usage analytics | Usage/cost visibility / analytics | ADR-0008, selected proof route for report shape | Promise hard billing or invoice parity | Native proof, visibility policy, provider catalog. |
| Provider/model catalog | Provider catalog / models | Data policy, ADR-0006 | Connect provider accounts | Provider/data approval and exact model IDs. |
| Provider setup / provider accounts | Provider setup / provider accounts | Data policy, provider catalog, gates, contract boundaries, secrets/security docs | Read/print keys, create/change accounts, update production provider config | Approved data policy and explicit provider/account approval. |
| Data policy | Data policy / masking | ADR-0001, security docs | Promise automatic masking | Customer/security approval. |
| Customer-facing proposal | General scope plus proposals | PRD-1, customer summary, internal matching docs | Treat proposal as implementation backlog | Owner/customer approval required. |
| Manager visibility / no-delete / retention | Руководители и чаты; Retention / audit / no-delete | ADR-0002, ADR-0003, runtime proof reports | Treat manager visibility as admin sees everything | Customer privacy/retention policy and runtime proof. |

## Unblocked planning / work without new customer approval

Read first:

- [CONTEXT_USAGE_RULES](CONTEXT_USAGE_RULES.md)
- [Stage 2 Unblocked Work Plan](implementation/STAGE2_UNBLOCKED_WORK_PLAN.md)
- [Stage 2 Scenario Shortlist](implementation/STAGE2_SCENARIO_SHORTLIST.md)
- [Workspace scenario user stories](implementation/WORKSPACE_SCENARIO_USER_STORIES.md)
- [Stage 2 selected user stories](implementation/STAGE2_SELECTED_USER_STORIES.md)
- [Stage 2 selected stories proof plans](implementation/STAGE2_SELECTED_STORIES_PROOF_PLANS.md)
- [Stage 2 selected stories synthetic data requirements](testdata/STAGE2_SELECTED_STORIES_SYNTHETIC_DATA_REQUIREMENTS.md)
- [Synthetic test data index](testdata/SYNTHETIC_TEST_DATA_INDEX.md)
- [ENGINEERING_BACKLOG](ENGINEERING_BACKLOG.md)
- [ACCEPTANCE_MATRIX](acceptance/ACCEPTANCE_MATRIX.md)

Additional context:

- [OpenWebUI native capability audit](implementation/OPENWEBUI_NATIVE_CAPABILITY_AUDIT.md)
- [Customer runtime decisions](proposals/CUSTOMER_STAGE2_RUNTIME_DECISIONS.md)
- [CORPORATE_AI_WORKSPACE_USE_CASES_RESEARCH](research/CORPORATE_AI_WORKSPACE_USE_CASES_RESEARCH.md)
- [USAGE_ANALYTICS_BILLING_RESEARCH](research/USAGE_ANALYTICS_BILLING_RESEARCH.md)
- [VL_OCR_PROVIDER_RESEARCH](research/VL_OCR_PROVIDER_RESEARCH.md)
- [DOCUMENTS_OCR_EXCEL_RESEARCH](research/DOCUMENTS_OCR_EXCEL_RESEARCH.md)
- [WEB_SEARCH_CANDIDATE_SET_COMPARISON_PLAN](implementation/WEB_SEARCH_CANDIDATE_SET_COMPARISON_PLAN.md)

Skip unless separately approved:

- Runtime `.env`.
- Customer documents.
- Stand runtime smoke/proof.

Comment:

- This stream is for internal documentation, skeletons, synthetic data,
  research, benchmark plans and proof plans.
- Corporate AI workspace use-case research is available as fact base before
  expanding or selecting user stories.
- Scenario shortlist and first draft user stories are available as a docs-only
  selection layer before synthetic data or proof planning.
- First selected stories, synthetic data requirements and proof plans are now
  documented for `ST2-US-001`, `ST2-US-002`, `ST2-US-003`, `ST2-US-009`,
  `ST2-US-011` and `ST2-US-013`.
- Synthetic proof can support mechanics and candidate comparison, but it does
  not close customer acceptance or implementation gates.
- VL OCR research and synthetic benchmark can start now; customer OCR pilot
  remains blocked by real samples and data policy.
- Usage analytics proof should target user/day/week/model/token/message and
  approximate-cost breakdown before any hard billing/gateway decision.

## Proof execution / runtime checks

Read first:

- [CONTEXT_USAGE_RULES](CONTEXT_USAGE_RULES.md)
- [IMPLEMENTATION_GATES](IMPLEMENTATION_GATES.md)
- [CONTRACT_BOUNDARIES](CONTRACT_BOUNDARIES.md)
- [ACCEPTANCE_MATRIX](acceptance/ACCEPTANCE_MATRIX.md)
- domain-specific proof plan or report for the task.

Additional context:

- [ENGINEERING_BACKLOG](ENGINEERING_BACKLOG.md)
- [TEST_DATA_REQUIREMENTS](acceptance/TEST_DATA_REQUIREMENTS.md)
- selected route above if the task starts from selected stories.

Do not do:

- do not run runtime proof from a docs-only task;
- do not read `.env` or credentials unless separately approved;
- do not create users/groups/models/prompts/Knowledge unless the proof task
  explicitly approves it and cleanup expectations are defined.

Blockers / gates:

- runtime proof requires separate approval, approved test data or synthetic
  test plan, and clear cleanup/rollback expectations;
- customer data requires customer-approved intake and data policy.

## Customer-facing proposals

Read first:

- [PRD-1](../prd/OPENWEBUI_CORPORATE_CHAT_PRD_1.md)
- [Customer summary](../prd/OPENWEBUI_CORPORATE_CHAT_PRD_1_CUSTOMER_SUMMARY.md)
- [CONTEXT_USAGE_RULES](CONTEXT_USAGE_RULES.md)
- [Customer Stage 2 Governance Proposal](proposals/CUSTOMER_STAGE2_GOVERNANCE_PROPOSAL.md)
- [Customer runtime decisions / решения после runtime-аудита](proposals/CUSTOMER_STAGE2_RUNTIME_DECISIONS.md)

Additional context:

- matching internal route for the topic, for example Web-search, analytics,
  OCR/VL OCR, manager visibility or data policy.

Do not do:

- do not treat customer proposal text as engineering backlog;
- do not add implementation commitments that are not backed by internal docs,
  gates and customer decisions.

Blockers / gates:

- customer-facing wording must stay aligned with PRD-1, gates and internal
  status; unresolved runtime/customer decisions remain unresolved.

## Implementation planning

Read first:

- [CONTEXT_USAGE_RULES](CONTEXT_USAGE_RULES.md)
- [ROADMAP](ROADMAP.md)
- [IMPLEMENTATION_GATES](IMPLEMENTATION_GATES.md)
- [CONTRACT_BOUNDARIES](CONTRACT_BOUNDARIES.md)
- [ENGINEERING_BACKLOG](ENGINEERING_BACKLOG.md)
- relevant ADRs and blueprint for the domain.

Additional context:

- relevant proof reports;
- relevant research;
- [ACCEPTANCE_MATRIX](acceptance/ACCEPTANCE_MATRIX.md);
- [TEST_DATA_REQUIREMENTS](acceptance/TEST_DATA_REQUIREMENTS.md).

Do not do:

- do not start production code, provider setup or OpenWebUI config changes from
  planning docs;
- do not treat proposed ADRs as approved decisions.

Blockers / gates:

- implementation planning starts only after applicable gates, owner decisions
  and proof/customer-data blockers are explicit.

## Domain isolation / contract boundaries

Read first:

- [CONTEXT_USAGE_RULES](CONTEXT_USAGE_RULES.md)
- [CONTRACT_BOUNDARIES](CONTRACT_BOUNDARIES.md)
- [EXTENSION_FIRST_IMPLEMENTATION_PATTERN](EXTENSION_FIRST_IMPLEMENTATION_PATTERN.md)
- [DOMAIN_MAP](DOMAIN_MAP.md)
- [ROADMAP](ROADMAP.md)

Additional context:

- [IMPLEMENTATION_GATES](IMPLEMENTATION_GATES.md)
- [decisions/README](decisions/README.md)
- [Docs format and gates refine report](../reports/2026-06-18/OPENWEBUI_STAGE2_DOCS_FORMAT_AND_GATES_REFINE.report.md)

Skip unless needed:

- Provider setup runbooks.
- Runtime `.env`.

Comment:

- OpenWebUI remains upstream product shell.
- Stage 2 custom capabilities live in bounded domain services, internal APIs or
  thin integration shims.
- Frontend does not own security, provider keys, data policy, retention, manager
  visibility or usage accounting.

## Рабочие пространства / RBAC

Read first:

- [OPENWEBUI_NATIVE_CAPABILITY_AUDIT](implementation/OPENWEBUI_NATIVE_CAPABILITY_AUDIT.md)
- [WORKSPACES_AND_RBAC](blueprints/WORKSPACES_AND_RBAC.blueprint.md)
- [IMPLEMENTATION_GATES](IMPLEMENTATION_GATES.md)

Additional context:

- [OPENWEBUI_NATIVE_CAPABILITY_RUNTIME_AUDIT report](../reports/2026-06-24/OPENWEBUI_NATIVE_CAPABILITY_RUNTIME_AUDIT.report.md)
- [OPENWEBUI_ADMIN_TEST_USER_RUNTIME_PROOF report](../reports/2026-06-24/OPENWEBUI_ADMIN_TEST_USER_RUNTIME_PROOF.report.md)
- [OPENWEBUI_CAPABILITY_RESEARCH](research/OPENWEBUI_CAPABILITY_RESEARCH.md)
- [RBAC_MANAGER_VISIBILITY_RESEARCH](research/RBAC_MANAGER_VISIBILITY_RESEARCH.md)
- [ACCESS_POLICY](../security/ACCESS_POLICY.md)

Skip unless needed:

- STT/provider pricing docs.

Comment:

- Research is done and public runtime version/health proof was captured on
  2026-06-24. Admin/test-user proof is still needed for RBAC, model visibility,
  prompts, knowledge, analytics, no-delete and manager visibility.

## Транскрибация

Read first:

- [OpenWebUI STT ffmpeg browser normalization implementation report](../reports/2026-06-19/OPENWEBUI_STT_FFMPEG_BROWSER_NORMALIZATION_IMPLEMENTATION.report.md)
- [OpenWebUI STT MVP feature closure report](../reports/2026-06-19/OPENWEBUI_STT_MVP_FEATURE_CLOSURE.report.md)
- [OpenWebUI STT runtime completion report](../reports/2026-06-19/OPENWEBUI_STT_RUNTIME_COMPLETION.report.md)
- [Extension-first implementation pattern](EXTENSION_FIRST_IMPLEMENTATION_PATTERN.md)
- [STT backend implementation plan](implementation/STT_BACKEND_IMPLEMENTATION_PLAN.md)
  (historical traceability)
- [STT OpenWebUI media action probe plan](implementation/STT_OPENWEBUI_MEDIA_ACTION_PROBE_PLAN.md)
  (historical traceability)
- [STT frontend media action patch plan](implementation/STT_FRONTEND_MEDIA_ACTION_PATCH_PLAN.md)
  (historical traceability)
- [STT media input normalization contract](contracts/STT_MEDIA_INPUT_NORMALIZATION_CONTRACT.md)
- [OpenWebUI STT Frontend Media Action Patch Report](../reports/2026-06-19/OPENWEBUI_STT_FRONTEND_MEDIA_ACTION_PATCH.report.md)
- [OpenWebUI STT Playwright UI Proof](../reports/2026-06-19/OPENWEBUI_STT_PLAYWRIGHT_UI_PROOF.report.md)
- [OpenWebUI-native STT UX Integration Research](../reports/2026-06-19/OPENWEBUI_NATIVE_STT_UX_INTEGRATION_RESEARCH.report.md)
- [OpenWebUI mobile microphone STT anamnesis audit](../reports/2026-06-23/OPENWEBUI_MOBILE_MICROPHONE_STT_ANAMNESIS_AUDIT.report.md)
- [TRANSCRIPTION_STT](blueprints/TRANSCRIPTION_STT.blueprint.md)
- [STT_V2_TRANSCRIPT_POSTPROCESSING](blueprints/STT_V2_TRANSCRIPT_POSTPROCESSING.blueprint.md)
- [STT v2 Gate 1-2 goal](goals/STT_V2_GATE_1_2_GOAL.md)
- [STT v2 artifact contracts](contracts/STT_V2_ARTIFACT_CONTRACTS.md)
- [STT v2 artifact storage/retention contract](contracts/STT_V2_ARTIFACT_STORAGE_RETENTION_CONTRACT.md)
- [STT v2 diarization proof contract](acceptance/STT_V2_DIARIZATION_PROOF_CONTRACT.md)
- [STT v2 Gate 1-2 env contract](config/STT_V2_GATE_1_2_ENV_CONTRACT.md)
- [STT v2 backward compatibility contract](contracts/STT_V2_BACKWARD_COMPATIBILITY_CONTRACT.md)
- [STT v2 message-level DOCX export contract](contracts/STT_V2_MESSAGE_DOCX_EXPORT_CONTRACT.md)
- [STT v2 message-level DOCX export runbook](operations/STT_V2_MESSAGE_DOCX_EXPORT_RUNBOOK.md)
- [STT v2 message-level DOCX export implementation proof](../reports/2026-07-03/STT_V2_MESSAGE_DOCX_EXPORT_IMPLEMENTATION_PROOF.report.md)
- [STT v2 Gate 1-2 acceptance matrix](acceptance/STT_V2_GATE_1_2_ACCEPTANCE_MATRIX.md)
- [STT v2 Gate 1-2 implementation boundary](implementation/STT_V2_GATE_1_2_IMPLEMENTATION_BOUNDARY.md)
- [STT v2 Gate 1-2 proof report template](acceptance/STT_V2_GATE_1_2_PROOF_REPORT_TEMPLATE.md)
- [STT v2 Gate 1-2 engineering docs design report](../reports/2026-07-02/STT_V2_GATE_1_2_ENGINEERING_DOCS_DESIGN.report.md)
- [ADR-0004 STT Proxy Boundary](decisions/ADR-0004-stt-proxy-boundary.md)
- [CONTRACT_BOUNDARIES](CONTRACT_BOUNDARIES.md)

Additional context:

- [TRANSCRIPTION_STT_RESEARCH](research/TRANSCRIPTION_STT_RESEARCH.md)
- [FFMPEG_WORKFLOW_ARTIFACT_INSPECTION](research/FFMPEG_WORKFLOW_ARTIFACT_INSPECTION.md)
- [FFMPEG_BROWSER_WORKFLOW_RESEARCH](research/FFMPEG_BROWSER_WORKFLOW_RESEARCH.md)
- [LEMONFOX_STT_RESEARCH](research/LEMONFOX_STT_RESEARCH.md)

Skip unless needed:

- Broker/tax docs.

Comment:

- API keys never go to the browser.
- STT proxy ADR still defines the backend boundary; ADR-0004 remains
  `Proposed`.
- Private sidecar job routes, the OpenWebUI media attachment `Transcribe`
  action and browser ffmpeg.wasm normalization are implemented/proven for the
  MVP path.
- Stage 2 STT MVP and STT v2 current-scope post-processing are closed and ready
  for broader testing.
- Current-scope STT v2 closure includes two native-prompt quick actions, prompt
  catalog/access/version proof, speaker-aware transcript projection when labels
  exist, ArtifactStore-backed `transcript_ref`, and message-level DOCX export.
  Remaining STT work is hardening or future extension, not architectural
  discovery.
- Prepared-MP3 frontend MVP passed through a static OpenWebUI loader patch.
- MP4-with-audio and WebM generated proof media passed through browser
  normalization into the existing Action/sidecar path.
- Broad input support is capability-based: declared source formats are hints,
  while actual support requires configured ffmpeg.wasm probe/decode,
  audio-stream detection and normalization to an approved output profile.
- A dedicated transcription workspace/history/export/protocol flow is future,
  not MVP.
- External ffmpeg workflow contract is inspected and transferable as MP3 /
  `audio/mpeg`; owner/operator proof is accepted for ADR planning, while
  production dependency decisions remain open.
- Remaining STT hardening: mobile, low-memory browser, large/customer media,
  cancel during ffmpeg, duration-limit policy, Opus provider proof if selected,
  production storage/retention, transcript history/export/workflow and
  multi-user/group permission hardening.
- Known issue as of 2026-06-23: native mobile microphone dictation can show the
  recording waveform but produce no audio transcription and stop after about
  five seconds. Track this as native Web Speech API/mobile hardening, not as a
  `stage2-stt` sidecar failure.
- Do not re-plan STT from zero and do not introduce a separate user-facing STT
  sidecar GUI for the MVP.
- Message-level DOCX export is a separate Gate 8 extension path. The implemented
  fallback profile is `simple_mvp`; markdown-first semantic chat formatting is
  implemented as `semantic_chat_v1` in the message-level DOCX contract.
- Future STT items: chunking/map-reduce for long transcripts, OpenWebUI Prompt
  API Adapter, full additional template set, processed-result-only DOCX artifact
  path, Meetings/history UI, PDF and branded Word templates.

## Брокерские отчеты / 3-НДФЛ

Current routing note, 2026-07-12: the bounded Gate 1/Gate 2 technical contour is
implemented and deployed with repo/live parity. A bounded real `income` target
passed the same candidate-binding contract through Gemini
`models/gemini-3.1-flash-lite`, native Anthropic
`claude-haiku-4-5-20251001` and OpenAI `gpt-5.6-luna`, with strict structured
output, canonical validation and complete stitch. A full single-PDF
whole-document Gate 2 run now exists and produced a private document packet, but
the result is partial: Gemini Flash-Lite rejected `document_summary_evidence`
strict-schema calls and complete document coverage was not proven. The
cross-domain and multi-provider architecture gap is closed; full-document
quality remains open.

VLM-guided PDF intake note, 2026-07-15: the already implemented deterministic
evidence, product router, bounded structural proposal, source binder, and
validator were connected into a sealed development gate. The binary result is
`DOES_NOT_WORK_ON_DEVELOPMENT_CORPUS`. The fresh unseen holdout and live canary
are `NOT_RUN`; production authority remains disabled.

Detection, technical processability, and holdout selection remain independent.
Inventory overflow preserves the completed parser prefix. Candidate/page model
requests may propose bounded physical regions and topology, but every adjusted
bbox and accepted structure must bind completely to exact source atoms.

Read first:

- [BROKER_REPORTS_3NDFL](blueprints/BROKER_REPORTS_3NDFL.blueprint.md)
- [PDF structural repair consensus contract](contracts/BROKER_REPORTS_PDF_STRUCTURAL_REPAIR_CONSENSUS.v2.md)
- [PDF VLM-guided intake contract](contracts/BROKER_REPORTS_PDF_VLM_GUIDED_INTAKE.v1.md)
- [PDF semantic header projection contract](contracts/BROKER_REPORTS_PDF_SEMANTIC_HEADER_PROJECTION.v1.md)
- [PDF VLM-guided intake shadow runbook](operations/BROKER_REPORTS_PDF_VLM_GUIDED_INTAKE_SHADOW_RUNBOOK.md)
- [Gate 2 source-fact extraction blueprint](blueprints/BROKER_REPORTS_GATE2_SOURCE_FACT_EXTRACTION.blueprint.md)
- [Normalized table projection contract](contracts/BROKER_REPORTS_NORMALIZED_TABLE_PROJECTION.v0.md)
- [Single PDF whole-document Gate 2 E2E proof](proof/BROKER_REPORTS_SINGLE_PDF_WHOLE_DOCUMENT_GATE2_E2E.md)
- [Cross-domain candidate-binding research](research/BROKER_REPORTS_GATE2_CROSS_DOMAIN_CANDIDATE_BINDING_RESEARCH.md)
- [ADR-0001 Data Policy](decisions/ADR-0001-data-policy-by-provider-class.md)
- [IMPLEMENTATION_GATES](IMPLEMENTATION_GATES.md)

Additional context:

- [DOCUMENTS_OCR_EXCEL_RESEARCH](research/DOCUMENTS_OCR_EXCEL_RESEARCH.md)
- [SECURITY_DATA_POLICY](blueprints/SECURITY_DATA_POLICY.blueprint.md)
- [PROVIDERS_MODEL_CATALOG](blueprints/PROVIDERS_MODEL_CATALOG.blueprint.md)
- [Single PDF whole-document Gate 2 E2E report](../reports/2026-07-12/OPENWEBUI_BROKER_REPORTS_SINGLE_PDF_WHOLE_DOCUMENT_GATE2_E2E.report.md)
- [PDF structural repair full closeout](../reports/2026-07-14/OPENWEBUI_BROKER_REPORTS_PDF_STRUCTURAL_REPAIR_FULL_CLOSEOUT.report.md)
- [Fresh holdout structural failure audit](../reports/2026-07-14/OPENWEBUI_BROKER_REPORTS_FRESH_HOLDOUT_STRUCTURAL_FAILURE_AUDIT.report.md)
- [Structural consensus architecture research](../reports/2026-07-14/OPENWEBUI_BROKER_REPORTS_STRUCTURAL_CONSENSUS_ARCHITECTURE_RESEARCH.report.md)
- [PDF structural and semantic closeout](../reports/2026-07-15/OPENWEBUI_BROKER_REPORTS_PDF_STRUCTURAL_AND_SEMANTIC_CLOSEOUT.report.md)
- [PDF table intake filter audit](../reports/2026-07-15/OPENWEBUI_BROKER_REPORTS_PDF_TABLE_INTAKE_FILTER_AUDIT.report.md)
- [PDF VLM-guided intake E2E closeout](../reports/2026-07-15/OPENWEBUI_BROKER_REPORTS_PDF_VLM_GUIDED_INTAKE_E2E_CLOSEOUT.report.md)
- [PDF VLM-guided intake refactor report](../reports/2026-07-15/OPENWEBUI_BROKER_REPORTS_PDF_VLM_GUIDED_INTAKE_REFACTOR.report.md)

Skip unless needed:

- Ops deployment docs.

Comment:

- AI output is draft/analysis only.
- Deterministic code restores supported table structure and reproducible source
  values; the LLM selects business roles only inside a bounded candidate set;
  validators decide whether the result can be accepted.
- Text-layer PDFs do not use OCR. Image-only/scanned pages remain outside this
  contour and require a separately approved OCR path.
- A raw PDF or an unbounded raw-text dump is not a Gate 2 model input.
- Single-PDF whole-document orchestration, packet persistence, issue
  carry-forward and no-Knowledge/no-vector guards are proven on one real PDF.
  Complete source-fact validation and complete document coverage are not proven.
  Do not start a multi-document proof until the `document_summary_evidence`
  provider/schema blocker and candidate-binding provenance gaps are resolved or
  explicitly accepted for another bounded diagnostic.

## Web-search

Read first:

- [WEB_SEARCH_CONTEXT_INDEX](WEB_SEARCH_CONTEXT_INDEX.md)
- [WEB_SEARCH](blueprints/WEB_SEARCH.blueprint.md)
- [ADR-0007 Web-search Provider](decisions/ADR-0007-web-search-provider.md)
- [OpenWebUI Web Search Integration Boundary](contracts/OPENWEBUI_WEB_SEARCH_INTEGRATION_BOUNDARY.md)

Additional context:

- [WEB_SEARCH_EXTERNAL_RESEARCH_2026-06-20](research/WEB_SEARCH_EXTERNAL_RESEARCH_2026-06-20.md)
- [WEB_SEARCH_PROVIDERS_RESEARCH](research/WEB_SEARCH_PROVIDERS_RESEARCH.md)
- [WEB_SEARCH_PRIVACY_BOUNDARY_CONTRACT](contracts/WEB_SEARCH_PRIVACY_BOUNDARY_CONTRACT.md)
- [WEB_SEARCH_USAGE_EVENT_CONTRACT](contracts/WEB_SEARCH_USAGE_EVENT_CONTRACT.md)
- [WEB_SEARCH_SOURCE_ATTRIBUTION_CONTRACT](contracts/WEB_SEARCH_SOURCE_ATTRIBUTION_CONTRACT.md)
- [WEB_SEARCH_NATIVE_PILOT_PLAN](implementation/WEB_SEARCH_NATIVE_PILOT_PLAN.md)
- [WEB_SEARCH_CANDIDATE_SET_COMPARISON_PLAN](implementation/WEB_SEARCH_CANDIDATE_SET_COMPARISON_PLAN.md)
- [WEB_SEARCH_RUNTIME_PROBE report](../reports/2026-06-20/OPENWEBUI_WEB_SEARCH_RUNTIME_PROBE.report.md)
- [WEB_SEARCH_DOMAIN_AND_PROBE report](../reports/2026-06-20/OPENWEBUI_WEB_SEARCH_DOMAIN_AND_PROBE.report.md)
- Existing [WEB_SEARCH_PROVIDER_RESEARCH](../infra/WEB_SEARCH_PROVIDER_RESEARCH.md)

Skip unless needed:

- STT/OCR docs.

Comment:

- Native OpenWebUI Web Search is the first path.
- Brave `brave_llm_context` is the current working native direct-context
  baseline.
- The current Brave baseline uses result count `3`, search concurrency `1`,
  web-loader bypass and web-search embedding/retrieval bypass.
- Known deferred issue: vectorized Web Search retrieval can create
  `web-search-*` collections after search/embedding but return `0` sources on
  follow-up retrieval. Revisit only for long pages, classic `brave`, SearXNG
  page loading or full RAG over fetched content.
- Private SearXNG is the self-hosted meta-search comparison track. It gives a
  private instance boundary, but upstream engines can still receive minimized
  queries. Runtime smoke passed in snippet/bypass mode on 2026-06-23.
- Yandex Search is a working Russian-provider path after 2026-06-23 Admin
  UI/native smoke; broaden use only after metadata-forwarding, allowed data
  class and cost-mode review.
- Current closeout status: Brave, Yandex and private SearXNG provider
  connectivity is proven; production rollout and full provider comparison are
  pending.
- Smoke/proven connectivity is only a technical connectivity result. It does
  not approve production rollout, group defaults or enabling Web Search for all
  users.
- No sidecar/fork/custom gateway until native runtime smoke proves a concrete
  gap.

## Documents / OCR / Excel

Read first:

- [OCR / VL OCR Infrastructure Epic Context Pack](context/OCR_VL_OCR_INFRASTRUCTURE_EPIC_CONTEXT_PACK.md)
- [VL OCR API Provider Shortlist Research V2](research/VL_OCR_API_PROVIDER_SHORTLIST_RESEARCH_V2.md)
- [VL OCR API Provider Shortlist Research V1, broad baseline](research/VL_OCR_API_PROVIDER_SHORTLIST_RESEARCH.md)
- [DOCUMENTS_OCR_EXCEL](blueprints/DOCUMENTS_OCR_EXCEL.blueprint.md)
- [ADR-0005 OCR / VL OCR Pilot Scope](decisions/ADR-0005-ocr-vl-ocr-pilot-scope.md)

Additional context:

- [DOCUMENTS_OCR_EXCEL_RESEARCH](research/DOCUMENTS_OCR_EXCEL_RESEARCH.md)
- [VL_OCR_PROVIDER_RESEARCH](research/VL_OCR_PROVIDER_RESEARCH.md)
- [TEST_DATA_REQUIREMENTS](acceptance/TEST_DATA_REQUIREMENTS.md)

Skip unless needed:

- Provider setup runbook until integration reaches provider calls.

Comment:

- OCR/VL OCR is a pilot.
- Corrected V2 provider shortlist exists for the raster image MVP path. First
  synthetic benchmark candidates are Alibaba Qwen-OCR/Qwen-VL, Datalab Chandra
  and a hosted PaddleOCR-VL path. Mistral OCR, Azure Document Intelligence,
  Google Document AI, AWS Textract and OCR.space are baseline-only.
- `ST2-US-013` user-story proof execution is paused until the OCR / VL OCR
  infrastructure epic defines provider shortlist, contracts and benchmark plan.
- Production OCR/layout pipeline remains future.
- Synthetic benchmark results can prepare a pilot, but they do not prove
  production OCR readiness for real customer documents.

## Сканы / картинки / PDF OCR

Read first:

- [OCR / VL OCR Infrastructure Epic Context Pack](context/OCR_VL_OCR_INFRASTRUCTURE_EPIC_CONTEXT_PACK.md)
- [VL OCR API Provider Shortlist Research V2](research/VL_OCR_API_PROVIDER_SHORTLIST_RESEARCH_V2.md)
- [VL OCR API Provider Shortlist Research V1, broad baseline](research/VL_OCR_API_PROVIDER_SHORTLIST_RESEARCH.md)
- [DOCUMENTS_OCR_EXCEL](blueprints/DOCUMENTS_OCR_EXCEL.blueprint.md)
- [VL_OCR_PROVIDER_RESEARCH](research/VL_OCR_PROVIDER_RESEARCH.md)
- [TEST_DATA_REQUIREMENTS](acceptance/TEST_DATA_REQUIREMENTS.md)

Additional context:

- [DOCUMENTS_OCR_EXCEL_RESEARCH](research/DOCUMENTS_OCR_EXCEL_RESEARCH.md)

Skip unless needed:

- Full document management docs.

Comment:

- Classify by document type.
- Do not use "OCR works for everything" as acceptance.
- Do not route ST2-US-013 directly into proof execution before infrastructure
  epic contracts and benchmark plan exist.

## Provider catalog / models

Read first:

- [PROVIDERS_MODEL_CATALOG](blueprints/PROVIDERS_MODEL_CATALOG.blueprint.md)
- [ADR-0006 Provider Model Catalog](decisions/ADR-0006-provider-model-catalog.md)

Additional context:

- [PROVIDERS_YANDEX_GIGACHAT_DEEPSEEK_CLAUDE_RESEARCH](research/PROVIDERS_YANDEX_GIGACHAT_DEEPSEEK_CLAUDE_RESEARCH.md)
- [PROVIDER_CONNECTIONS_PLAN](../infra/PROVIDER_CONNECTIONS_PLAN.md)
- [ADR-0001 Data Policy](decisions/ADR-0001-data-policy-by-provider-class.md)

Skip unless needed:

- Runtime `.env`.

Comment:

- Claude API is a provider.
- Claude Code is not a chat provider.
- Exact model IDs are required.

## Provider setup / provider accounts

Use this route for tasks about provider setup, provider accounts, model/provider
access, keys handoff, safe smoke preparation or production provider config.

Read first:

1. [PROVIDERS_MODEL_CATALOG](blueprints/PROVIDERS_MODEL_CATALOG.blueprint.md)
2. [ADR-0001 Data Policy](decisions/ADR-0001-data-policy-by-provider-class.md)
3. [ADR-0006 Provider Model Catalog](decisions/ADR-0006-provider-model-catalog.md)
4. [ENGINEERING_BACKLOG](ENGINEERING_BACKLOG.md)
5. [IMPLEMENTATION_GATES](IMPLEMENTATION_GATES.md)
6. [CONTRACT_BOUNDARIES](CONTRACT_BOUNDARIES.md)
7. [PROVIDERS_YANDEX_GIGACHAT_DEEPSEEK_CLAUDE_RESEARCH](research/PROVIDERS_YANDEX_GIGACHAT_DEEPSEEK_CLAUDE_RESEARCH.md)
8. [SECRETS_POLICY](../security/SECRETS_POLICY.md)
9. [SECURITY_MINIMUM](../security/SECURITY_MINIMUM.md)

Additional context after approval:

- [PROVIDER_CONNECTIONS_PLAN](../infra/PROVIDER_CONNECTIONS_PLAN.md)
- [PROVIDER_SETUP_RUNBOOK](../ops/PROVIDER_SETUP_RUNBOOK.md)

Do not do:

- do not read or print provider keys;
- do not create or change provider accounts;
- do not update production provider config;
- do not start provider setup before approved data policy;
- do not treat provider research as approval.

Provider setup нельзя начинать до утверждённой политики данных по классам
провайдеров.

Blockers / gates:

- Gate 1: data policy by provider class;
- Gate 3: provider model catalog;
- explicit provider/account approval by customer/operator;
- safe key handoff procedure that does not expose secrets in docs, logs or git.

## Usage/cost visibility / analytics

Read first:

- [USAGE_ANALYTICS_AND_COSTS](blueprints/USAGE_ANALYTICS_AND_COSTS.blueprint.md)
- [ADR-0008 Native Analytics vs Hard
  Billing](decisions/ADR-0008-native-analytics-vs-hard-billing.md)

Additional context:

- [USAGE_ANALYTICS_BILLING_RESEARCH](research/USAGE_ANALYTICS_BILLING_RESEARCH.md)
- [PROVIDERS_MODEL_CATALOG](blueprints/PROVIDERS_MODEL_CATALOG.blueprint.md)

Skip unless needed:

- Gateway deployment docs until decision.

Comment:

- Native analytics first.
- Hard billing is a separate ADR/future slice.

## Data policy / masking

Read first:

- [SECURITY_DATA_POLICY](blueprints/SECURITY_DATA_POLICY.blueprint.md)
- [ADR-0001 Data Policy](decisions/ADR-0001-data-policy-by-provider-class.md)
- [IMPLEMENTATION_GATES](IMPLEMENTATION_GATES.md)

Additional context:

- [DATA_MASKING_FUTURE_RESEARCH](research/DATA_MASKING_FUTURE_RESEARCH.md)
- [SECRETS_POLICY](../security/SECRETS_POLICY.md)
- [SECURITY_MINIMUM](../security/SECURITY_MINIMUM.md)

Skip unless needed:

- Implementation code.

Comment:

- Provider setup must wait for data policy.
- Masking/tokenization remains future.

## Data policy / provider data classes

Read first:

- [SECURITY_DATA_POLICY](blueprints/SECURITY_DATA_POLICY.blueprint.md)
- [ADR-0001 Data Policy](decisions/ADR-0001-data-policy-by-provider-class.md)

Additional context:

- [DATA_MASKING_FUTURE_RESEARCH](research/DATA_MASKING_FUTURE_RESEARCH.md)

Skip unless needed:

- Provider setup runbook until approval.

Comment:

- Read before Claude, DeepSeek, Yandex, GigaChat or OpenAI setup.

## Руководители и чаты

Read first:

- [MANAGER_VISIBILITY_AND_RETENTION](blueprints/MANAGER_VISIBILITY_AND_RETENTION.blueprint.md)
- [ADR-0002 Manager Visibility Policy](decisions/ADR-0002-manager-visibility-policy.md)

Additional context:

- [RBAC_MANAGER_VISIBILITY_RESEARCH](research/RBAC_MANAGER_VISIBILITY_RESEARCH.md)

Skip unless needed:

- Provider pricing docs.

Comment:

- Controlled work-chat visibility.
- This is not "manager sees everything".

## Retention / audit / no-delete

Read first:

- [MANAGER_VISIBILITY_AND_RETENTION](blueprints/MANAGER_VISIBILITY_AND_RETENTION.blueprint.md)
- [ADR-0003 Chat Deletion, Retention and Audit](decisions/ADR-0003-chat-deletion-retention-audit.md)

Additional context:

- [CHAT_DELETION_RETENTION_RESEARCH](research/CHAT_DELETION_RETENTION_RESEARCH.md)

Skip unless needed:

- Provider pricing docs.

Comment:

- No Delete is not Retention.
- Retention is not Audit.
- Audit is not immutable archive.

## Operations / acceptance

Read first:

- [OPS_AND_ACCEPTANCE](blueprints/OPS_AND_ACCEPTANCE.blueprint.md)
- [ACCEPTANCE_MATRIX](acceptance/ACCEPTANCE_MATRIX.md)
- [IMPLEMENTATION_GATES](IMPLEMENTATION_GATES.md)

Additional context:

- [SMOKE_TESTS](../ops/SMOKE_TESTS.md)
- [ACCEPTANCE_TESTS](../ops/ACCEPTANCE_TESTS.md)
- [UPDATE_ROLLBACK_RUNBOOK](../ops/UPDATE_ROLLBACK_RUNBOOK.md)

Skip unless needed:

- Feature-specific research.

Comment:

- No production changes in planning phase.

## Source status

Current routing entrypoints:

- `README.md`
- `docs/stage2/README.md`
- `docs/stage2/CONTEXT_INDEX.md`
- `docs/stage2/CONTEXT_USAGE_RULES.md`
- `docs/prd/OPENWEBUI_CORPORATE_CHAT_PRD_1.md`
- `docs/stage2/ROADMAP.md`
- `docs/stage2/ENGINEERING_BACKLOG.md`
- `docs/stage2/IMPLEMENTATION_GATES.md`
- `docs/stage2/CONTRACT_BOUNDARIES.md`
- `docs/stage2/blueprints/*`
- `docs/stage2/research/*`
- `docs/stage2/decisions/*`
- `docs/stage2/implementation/*`
- `docs/stage2/acceptance/*`
- `docs/reports/YYYY-MM-DD/*`

No separate `docs/README.md` is expected for Stage 2. Use root `README.md`
and `docs/stage2/README.md`.
