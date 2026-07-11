# Stage 2 Engineering Domain

Этот домен не является реализацией Stage 2. Это инженерная карта, roadmap и research findings перед
реализацией.

## 1. Что такое Stage 2

Stage 2 развивает корпоративный OpenWebUI-портал из пилотного AI-чата в управляемую рабочую
AI-среду: рабочие сценарии, группы, prompts/templates, транскрибация, брокерские отчеты, web-search,
документы, провайдеры, basic analytics и контроль доступа.

## 2. Финальная PRD-1

Актуальный источник истины:
[docs/prd/OPENWEBUI_CORPORATE_CHAT_PRD_1.md](../prd/OPENWEBUI_CORPORATE_CHAT_PRD_1.md).

Короткое customer summary:
[docs/prd/OPENWEBUI_CORPORATE_CHAT_PRD_1_CUSTOMER_SUMMARY.md](../prd/OPENWEBUI_CORPORATE_CHAT_PRD_1_CUSTOMER_SUMMARY.md).

## 3. PRD-0 и post-acceptance audit

- PRD-0: [docs/prd/OPENWEBUI_CORPORATE_CHAT_PRD_0.md](../prd/OPENWEBUI_CORPORATE_CHAT_PRD_0.md)
- Post-acceptance audit:
  [PRD-0 post-acceptance audit][prd0-post-acceptance-audit].

[prd0-post-acceptance-audit]: ../reports/2026-06-16/OPENWEBUI_PRD_0_POST_ACCEPTANCE_AUDIT.report.md

## 4. Как пользоваться этим доменом

1. Начать с [CONTEXT_INDEX.md](CONTEXT_INDEX.md), если задача точечная.
2. Открыть [CONTEXT_USAGE_RULES.md](CONTEXT_USAGE_RULES.md), чтобы отличить
   research, report, proposal, ADR, proof plan and docs-only boundaries.
3. Открыть
   [STAGE2_UNBLOCKED_WORK_PLAN.md](implementation/STAGE2_UNBLOCKED_WORK_PLAN.md),
   если задача касается работ, которые можно делать без нового согласования с
   заказчиком.
4. Открыть [DOMAIN_MAP.md](DOMAIN_MAP.md), если нужно понять границы Stage 2.
5. Открыть [CONTRACT_BOUNDARIES.md](CONTRACT_BOUNDARIES.md), если задача касается custom logic,
   provider calls, storage, policy, usage or UI/backend split.
6. Открыть [EXTENSION_FIRST_IMPLEMENTATION_PATTERN.md](EXTENSION_FIRST_IMPLEMENTATION_PATTERN.md)
   для OpenWebUI-facing features.
7. Открыть профильный blueprint в [blueprints/](blueprints/).
8. Открыть связанные research-документы в [research/](research/).
9. Проверить acceptance в [acceptance/ACCEPTANCE_MATRIX.md](acceptance/ACCEPTANCE_MATRIX.md).
10. Проверить implementation gates в [IMPLEMENTATION_GATES.md](IMPLEMENTATION_GATES.md).
11. Не начинать implementation до review roadmap/blueprints/research, ADR по спорным точкам и runtime
   proof.

Stage 2 docs are not implementation by default. A docs-only plan, research
note, customer proposal or proof plan does not authorize runtime proof,
OpenWebUI config changes or creation of users/groups/models/prompts/Knowledge.

Для задач по selected stories, synthetic data и proof prep сначала используйте
route в [CONTEXT_INDEX.md](CONTEXT_INDEX.md) и правила в
[CONTEXT_USAGE_RULES.md](CONTEXT_USAGE_RULES.md). README не дублирует полный
порядок чтения.

## 5. Backend-first delivery principle

Stage 2 implementation must start from backend/server-side boundaries, policies and proofs.
Frontend/UI work follows after backend contracts are clear.

Frontend must not become the place where security, provider keys, data policy, retention rules or
access rules are decided.

Stage 2 custom capabilities must be isolated behind explicit backend contracts.
OpenWebUI remains the upstream product shell; custom Stage 2 logic should live in
bounded domain services, internal APIs, or thin integration shims.

OpenWebUI-facing features should use the extension-first path before any fork:
native OpenWebUI mechanisms, Functions/Actions/Tools, thin static loader/UI
shim, private backend/domain sidecar, and only then a deep fork if runtime proof
and owner/ADR approval require it.

The frontend must not own security, provider keys, data policy, retention,
manager visibility or usage accounting.

Практический порядок для спорных доменов:

1. ADR / policy decision.
2. Backend contract and runtime proof.
3. Minimal backend/API slice.
4. UI/browser integration.
5. Polish and user-facing instructions.

Этот порядок обязателен для STT proxy, OCR/VL OCR pipeline, manager visibility, no-delete/retention,
provider setup, usage analytics and web-search.

## 6. Карта документов

| Документ | Назначение |
| -------- | ---------- |
| [ROADMAP.md](ROADMAP.md) | Дорожная карта подготовки к реализации. |
| [CONTEXT_INDEX.md](CONTEXT_INDEX.md) | Быстрый индекс: что читать по домену/задаче. |
| [CONTEXT_USAGE_RULES.md](CONTEXT_USAGE_RULES.md) | Правила context routing: source-of-truth hierarchy, document type rules and stop conditions. |
| [OCR_VL_OCR_INFRASTRUCTURE_EPIC_CONTEXT_PACK.md](context/OCR_VL_OCR_INFRASTRUCTURE_EPIC_CONTEXT_PACK.md) | Handoff pack для OCR / VL OCR Infrastructure & Provider Benchmark Epic; `ST2-US-013` paused until provider shortlist, contracts and benchmark plan. |
| [VL_OCR_API_PROVIDER_SHORTLIST_RESEARCH_V2.md](research/VL_OCR_API_PROVIDER_SHORTLIST_RESEARCH_V2.md) | Corrected provider shortlist для raster image -> hosted OCR-VL/VLM document API -> structured JSON/text/tables -> LLM context MVP; рекомендует Alibaba Qwen-OCR/Qwen-VL, Datalab Chandra and hosted PaddleOCR-VL path. |
| [VL_OCR_API_PROVIDER_SHORTLIST_RESEARCH.md](research/VL_OCR_API_PROVIDER_SHORTLIST_RESEARCH.md) | Historical V1 broad baseline; useful for Mistral/Azure/Document AI comparison but not the main corrected OCR-VL shortlist. |
| [DOMAIN_MAP.md](DOMAIN_MAP.md) | Карта инженерных доменов Stage 2. |
| [CONTRACT_BOUNDARIES.md](CONTRACT_BOUNDARIES.md) | Доменные границы и versioned internal contracts. |
| [STT_V2_MESSAGE_DOCX_EXPORT_CONTRACT.md](contracts/STT_V2_MESSAGE_DOCX_EXPORT_CONTRACT.md) | Message-level DOCX export contract; `simple_mvp` fallback and implemented markdown-first `semantic_chat_v1` formatting profile. |
| [EXTENSION_FIRST_IMPLEMENTATION_PATTERN.md](EXTENSION_FIRST_IMPLEMENTATION_PATTERN.md) | Reusable pattern for adding OpenWebUI-facing features without defaulting to a fork. |
| [IMPLEMENTATION_GATES.md](IMPLEMENTATION_GATES.md) | Gates перед implementation planning. |
| [ENGINEERING_BACKLOG.md](ENGINEERING_BACKLOG.md) | Planning backlog без issue-tracker семантики. |
| [proposals/](proposals/) | Customer-facing proposals for agreeing the next Stage 2 direction. |
| [CUSTOMER_STAGE2_RUNTIME_DECISIONS.md](proposals/CUSTOMER_STAGE2_RUNTIME_DECISIONS.md) | Справка для заказчика по решениям после runtime-аудита OpenWebUI. |
| [implementation/](implementation/) | Implementation plans for first backend slices. |
| [STAGE2_UNBLOCKED_WORK_PLAN.md](implementation/STAGE2_UNBLOCKED_WORK_PLAN.md) | Внутренний план работ, которые можно делать без нового согласования с заказчиком. |
| [STAGE2_SCENARIO_SHORTLIST.md](implementation/STAGE2_SCENARIO_SHORTLIST.md) | Короткий список первых Stage 2 сценариев и корзины: можно сейчас, нужен заказчик, future. |
| [WORKSPACE_SCENARIO_USER_STORIES.md](implementation/WORKSPACE_SCENARIO_USER_STORIES.md) | Черновая структура рабочих сценариев через user stories - описания задачи глазами пользователя. |
| [STAGE2_SELECTED_USER_STORIES.md](implementation/STAGE2_SELECTED_USER_STORIES.md) | Первый малый execution-пакет выбранных stories для synthetic data requirements и proof plans. |
| [STAGE2_SELECTED_STORIES_PROOF_PLANS.md](implementation/STAGE2_SELECTED_STORIES_PROOF_PLANS.md) | Планы проверки только на уровне документации для выбранных stories; runtime proof не запускался. |
| [testdata/STAGE2_SELECTED_STORIES_SYNTHETIC_DATA_REQUIREMENTS.md](testdata/STAGE2_SELECTED_STORIES_SYNTHETIC_DATA_REQUIREMENTS.md) | Требования к искусственным тестовым данным для выбранных stories без создания файлов. |
| [CORPORATE_AI_WORKSPACE_USE_CASES_RESEARCH.md](research/CORPORATE_AI_WORKSPACE_USE_CASES_RESEARCH.md) | Внешний research реальных корпоративных AI-workspace сценариев; база для будущего выбора user stories. |
| [OPENWEBUI_NATIVE_CAPABILITY_AUDIT.md](implementation/OPENWEBUI_NATIVE_CAPABILITY_AUDIT.md) | Native capability audit summary and scenario assembly guidance. |
| [testdata/SYNTHETIC_TEST_DATA_INDEX.md](testdata/SYNTHETIC_TEST_DATA_INDEX.md) | Индекс искусственных тестовых данных для проверок и сравнений без данных заказчика. |
| [blueprints/](blueprints/) | Доменные инженерные рамки, не реализация. |
| [research/](research/) | Research findings, источники, blockers и next steps. |
| [decisions/](decisions/) | ADR-шаблон и будущие architecture decisions. |
| [acceptance/](acceptance/) | Acceptance matrix и требования к тестовым данным. |

## 7. Домены Stage 2

1. Workspaces / RBAC / shared prompts.
2. Transcription / STT / ffmpeg browser workflow.
3. Broker reports / 3-НДФЛ.
4. Web-search.
5. Documents / OCR / VL OCR / Excel.
6. Provider catalog / models.
7. Usage analytics / cost visibility.
8. Security / data policy / future masking.
9. Manager visibility / no-delete / retention / audit policy.
10. Operations / acceptance / testing.

## 8. Что уже согласовано с заказчиком

- PRD-1 является source of truth для Stage 2.
- Приоритеты: транскрибация, брокерские отчеты, web-search.
- Транскрибация использует существующий ffmpeg workflow как technical asset.
- STT provider call должен идти через server-side proxy; API keys не попадают в браузер.
- Lemonfox - приоритетный STT candidate.
- Web-search нужен всем пользователям, но с rules, limits, result count, concurrency и cost
  visibility.
- Для брокерских PDF с текстовым слоем реализован отдельный deterministic
  normalization/table path; OCR для сканов и страниц без текстового слоя
  остаётся отдельным pilot/research и не включается по умолчанию.
- Доступ руководителей к рабочим чатам включен как requirement/check, но не как просмотр всех личных
  чатов.
- Запрет удаления чатов пользователями требует technical check.
- No Delete, Retention, Audit and immutable archive are separate decisions.
- Provider setup не стартует до утверждения data policy by provider class.
- OCR pilot должен отдельно проверить VL OCR / vision-language OCR candidates на сканах,
  изображениях, сложных PDF и таблицах.
- Data masking/tokenization - future security slice, не implementation текущего Practical Stage 2.
- Custom capabilities изолируются за backend/domain contracts; OpenWebUI core не патчится глубоко без
  отдельного rationale.

## 9. Research snapshot от 2026-06-18

Research выполнен по первичным источникам и локальным repo evidence. Это не runtime implementation и
не настройка провайдеров.

Подробный отчет:
[Research actualization report][research-actualization-report].

[research-actualization-report]: ../reports/2026-06-18/OPENWEBUI_STAGE2_RESEARCH_ACTUALIZATION.report.md

### OpenWebUI native capabilities

Finding:

- Native-first оправдан для RBAC/groups, shared resources, web-search, RAG/docs and analytics.
- 2026-06-24 runtime audit confirmed deployed public version `0.9.6`, public
  health endpoints, protected unauthenticated `/api/models`, and the served
  Stage 2 STT static loader.
- 2026-06-24 Admin/Test-User proof used approved local `.env` variable names
  without printing values, proved authenticated admin API access, created
  temporary synthetic four-actor proof resources, completed the actor matrix
  and deleted all proof entities. The proof remains partial for concrete
  runtime gaps: no-delete is not enforced, Web Search is globally enabled,
  manager positive shared-list visibility did not confirm, and analytics did
  not show immediate synthetic user rows. Details are in
  [OPENWEBUI_ADMIN_TEST_USER_RUNTIME_PROOF.report.md](../reports/2026-06-24/OPENWEBUI_ADMIN_TEST_USER_RUNTIME_PROOF.report.md).

Next action:

- Resolve customer decisions for no-delete, manager visibility, Web Search
  scope/default policy and analytics expectations.
- Use the reusable native capability page:
  [OPENWEBUI_NATIVE_CAPABILITY_AUDIT.md](implementation/OPENWEBUI_NATIVE_CAPABILITY_AUDIT.md).
- Full audit report:
  [OPENWEBUI_NATIVE_CAPABILITY_RUNTIME_AUDIT.report.md](../reports/2026-06-24/OPENWEBUI_NATIVE_CAPABILITY_RUNTIME_AUDIT.report.md).
- Admin/Test-User proof report:
  [OPENWEBUI_ADMIN_TEST_USER_RUNTIME_PROOF.report.md](../reports/2026-06-24/OPENWEBUI_ADMIN_TEST_USER_RUNTIME_PROOF.report.md).

### Transcription / STT

Finding:

- Lemonfox подходит как priority candidate, но PRD-1 workflow требует server-side STT proxy/adapter.

Current implementation baseline, 2026-06-19:

- Private `stage2-stt` sidecar job routes, `LemonfoxSttAdapter`, internal auth,
  OpenWebUI static `Transcribe` action and browser ffmpeg.wasm normalization
  are implemented/proven for the MVP path.
- Stage 2 STT MVP status: implemented/proven/current-stage closed and ready
  for broader testing. Remaining work is testing/hardening, not architectural
  discovery.
- Native OpenWebUI Web API microphone dictation is patched through a pinned
  OpenWebUI image layer; Stage 2 static loader no longer post-processes native
  microphone input.
- Known issue as of 2026-06-23: native mobile microphone dictation can show the
  recording waveform but produce no audio transcription and stop after about
  five seconds. This is tracked as native Web Speech API/mobile hardening, not
  as a `stage2-stt` sidecar failure. See
  [OPENWEBUI_MOBILE_MICROPHONE_STT_ANAMNESIS_AUDIT.report.md](../reports/2026-06-23/OPENWEBUI_MOBILE_MICROPHONE_STT_ANAMNESIS_AUDIT.report.md).
- Prepared MP3, MP4 with audio and WebM generated proof media pass through the
  Action/sidecar path; unsupported/decode-failed and no-audio media fail safely
  before provider handoff.
- ADR-0004 still needs human review/status decision and production-hardening
  decisions remain open.

Read next:

- Human review of [ADR-0004 STT Proxy Boundary](decisions/ADR-0004-stt-proxy-boundary.md).
- Review browser normalization implementation report:
  [OPENWEBUI_STT_FFMPEG_BROWSER_NORMALIZATION_IMPLEMENTATION.report.md](../reports/2026-06-19/OPENWEBUI_STT_FFMPEG_BROWSER_NORMALIZATION_IMPLEMENTATION.report.md).
- Review runtime completion report:
  [OPENWEBUI_STT_RUNTIME_COMPLETION.report.md](../reports/2026-06-19/OPENWEBUI_STT_RUNTIME_COMPLETION.report.md).
- Review docs implementation drift audit:
  [OPENWEBUI_STT_DOCS_IMPLEMENTATION_DRIFT_AUDIT.report.md](../reports/2026-06-19/OPENWEBUI_STT_DOCS_IMPLEMENTATION_DRIFT_AUDIT.report.md).
- Review STT MVP feature closure report:
  [OPENWEBUI_STT_MVP_FEATURE_CLOSURE.report.md](../reports/2026-06-19/OPENWEBUI_STT_MVP_FEATURE_CLOSURE.report.md).
- Review native Web STT recorder patch report:
  [OPENWEBUI_NATIVE_WEB_STT_RECORDER_PATCH.report.md](../reports/2026-06-19/OPENWEBUI_NATIVE_WEB_STT_RECORDER_PATCH.report.md).
- Review mobile native microphone STT issue audit:
  [OPENWEBUI_MOBILE_MICROPHONE_STT_ANAMNESIS_AUDIT.report.md](../reports/2026-06-23/OPENWEBUI_MOBILE_MICROPHONE_STT_ANAMNESIS_AUDIT.report.md).
- Reuse the extension-first pattern for future OpenWebUI-facing features:
  [EXTENSION_FIRST_IMPLEMENTATION_PATTERN.md](EXTENSION_FIRST_IMPLEMENTATION_PATTERN.md).
- Review latest ADR-0004 Lemonfox capabilities/runtime limits report:
  [OPENWEBUI_ADR0004_LEMONFOX_CAPABILITIES_AND_RUNTIME_LIMITS.report.md](../reports/2026-06-19/OPENWEBUI_ADR0004_LEMONFOX_CAPABILITIES_AND_RUNTIME_LIMITS.report.md).
- Review final compact STT contract refine report:
  [OPENWEBUI_ADR0004_COMPACT_STT_CONTRACT_REFINE.report.md](../reports/2026-06-19/OPENWEBUI_ADR0004_COMPACT_STT_CONTRACT_REFINE.report.md).
- Treat backend implementation plan as historical baseline:
  [STT_BACKEND_IMPLEMENTATION_PLAN.md](implementation/STT_BACKEND_IMPLEMENTATION_PLAN.md).
- Treat frontend patch plan as historical baseline:
  [STT_FRONTEND_MEDIA_ACTION_PATCH_PLAN.md](implementation/STT_FRONTEND_MEDIA_ACTION_PATCH_PLAN.md).
- Continue with testing/hardening: mobile/large/low-memory browser proof,
  duration/cancel policy, storage/retention, Opus default proof if selected,
  permissions, monitoring and transcript workflow. Optional ffmpeg smoke can
  run during implementation/debug.

### ffmpeg browser workflow

Finding:

- Browser ffmpeg viable as sidecar/module. External workflow contract is
  inspected and transferable: MP3 / `audio/mpeg` output through browser-side
  ffmpeg, then presigned/internal upload and backend STT orchestration.
- Owner/operator proof accepts the workflow for ADR planning across two
  same-stack projects, including mobile and large-file cases.

Current implementation:

- Use [STT media input normalization contract](contracts/STT_MEDIA_INPUT_NORMALIZATION_CONTRACT.md)
  and the browser normalization report as the current implementation record.
- Current static browser profile is `mp3_high_compat`; Opus remains a candidate
  until provider proof and production policy select it.
- Decide output format, asset hosting hardening, licensing/ops and file limits
  before production acceptance.

### Web-search

Finding:

- Brave `brave_llm_context` is best first pilot if foreign provider is allowed.
- Yandex Search API is a working Russian-provider path after 2026-06-23 Admin
  UI/native smoke; rollout still needs policy/cost approval.

Next action:

- Provider ADR and customer cost/privacy approval.

### Documents / OCR / Excel

Finding:

- OpenWebUI has extraction engines.
- Broker-report PDFs with a text layer now have a bounded deterministic
  normalization/table path; corpus-wide acceptance still waits for customer
  samples.
- OCR remains a separate unproven path for scanned/image-only pages and is not
  the default PDF route.
- VL OCR is promising but unproven.
- Corrected VL OCR API provider shortlist V2 now recommends first synthetic
  benchmark candidates: Alibaba Qwen-OCR/Qwen-VL, Datalab Chandra and a
  hosted PaddleOCR-VL path. Mistral OCR, Azure Document Intelligence and other
  classic Document AI/OCR services are baseline-only, not the main OCR-VL path.
- `ST2-US-013` is paused as user-story proof until OCR / VL OCR infrastructure
  epic defines provider shortlist, input/output contracts and benchmark plan.

Next action:

- Prepare OCR / VL OCR synthetic benchmark plan and `DocumentExtractionResultV1`
  adapter contract; do not run benchmark or provider API yet.

### Providers / model catalog

Finding:

- Use exact model IDs.
- Claude API is not Claude Code.
- DeepSeek/YandexGPT/GigaChat need policy/procurement decision.

Next action:

- Provider catalog ADR.

### Analytics / costs

Finding:

- Native analytics may satisfy basic visibility.
- Hard budgets require gateway/future ADR.

Next action:

- Runtime analytics proof with test users/groups.

### Manager visibility / no-delete

Finding:

- Native RBAC/sharing and chat-delete permission are plausible.
- Manager supervision and no-delete need runtime proof.

Next action:

- Test user matrix and customer privacy policy.

### Data masking

Finding:

- Useful building blocks exist, but masking/tokenization is future security slice.

Next action:

- Data policy now; masking ADR later.

## 10. Что не является production acceptance на текущем шаге

- STT MVP current stage is closed, but ADR-0004 is still `Proposed` and
  production hardening is pending.
- STT v2 current-scope post-processing, speaker-aware projection and
  message-level DOCX export are closed for the current Stage 2 scope.
- Нет нового provider setup в документации.
- Этот docs view не вносит новых compose/env/scripts changes.
- Нет OpenWebUI fork.
- Нет API keys.
- Нет production changes.

## 11. ADR order and execution order

ADR registry order:

1. [ADR-0001 Data Policy by Provider Class](decisions/ADR-0001-data-policy-by-provider-class.md).
2. [ADR-0002 Manager Visibility Policy](decisions/ADR-0002-manager-visibility-policy.md).
3. [ADR-0003 Chat Deletion, Retention and
   Audit](decisions/ADR-0003-chat-deletion-retention-audit.md).
4. [ADR-0004 STT Proxy Boundary](decisions/ADR-0004-stt-proxy-boundary.md).
5. [ADR-0005 OCR / VL OCR Pilot Scope](decisions/ADR-0005-ocr-vl-ocr-pilot-scope.md).
6. [ADR-0006 Provider Model Catalog](decisions/ADR-0006-provider-model-catalog.md).
7. [ADR-0007 Web-search Provider](decisions/ADR-0007-web-search-provider.md).
8. [ADR-0008 Native Analytics vs Hard
   Billing](decisions/ADR-0008-native-analytics-vs-hard-billing.md).

Recommended execution / review order:

1. Data Policy by Provider Class.
2. STT Proxy Boundary.
3. Provider Model Catalog.
4. Web-search Provider.
5. Manager Visibility Policy.
6. Chat Deletion / Retention / Audit.
7. OCR / VL OCR Pilot Scope.
8. Native Analytics vs Hard Billing.
9. Optional implementation smoke checklist.
10. Customer test data package.
11. Implementation backlog by slices.

Numbers are the ADR registry order. Execution order reflects implementation
dependencies.

## 12. Следующий шаг

For STT, do not re-plan the MVP architecture. Review
[ADR-0004 STT Proxy Boundary](decisions/ADR-0004-stt-proxy-boundary.md) for
production policy/hardening decisions and continue broader testing.

The bounded technical contour for
[Broker reports / 3-НДФЛ](CONTEXT_INDEX.md#брокерские-отчеты--3-ндфл) is
implemented and deployed with repository/live bundle and Prompt parity. The
first post-deploy strict candidate-binding canary is quota-blocked, so accepted
fact proof must close before the limited customer pilot expands.

После ADR/gates можно готовить implementation slices and acceptance sequence.

## 13. Source inventory

Найдены и использованы как контекст:

- `README.md`
- `docs/prd/OPENWEBUI_CORPORATE_CHAT_PRD_1.md`
- `docs/prd/OPENWEBUI_CORPORATE_CHAT_PRD_0.md`
- `docs/reports/2026-06-16/OPENWEBUI_PRD_0_POST_ACCEPTANCE_AUDIT.report.md`
- `docs/blueprint/*`
- `docs/infra/*`
- `docs/ops/*`
- `docs/security/*`
- `docs/reports/2026-06-09/*`

Отсутствует:

- `docs/README.md`
