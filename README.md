# corp-openweb-ui

Инженерный пакет для PRD-0: минимальный self-hosted запуск OpenWebUI как корпоративной точки входа в
LLM-чат для 3-4 пользователей. Репозиторий также содержит документационный контур Stage 2 / PRD-1.

Цель репозитория - blueprint, runbooks и skeleton для безопасного развертывания на домене
`gpt.alpha-soft.ru`. Это не AI-платформа.

## Scope PRD-0

Входит:

- OpenWebUI;
- Docker / Docker Compose;
- Traefik и HTTPS;
- OpenAI + Gemini как API-провайдеры;
- мягкое имя инстанса и warning banner штатными средствами OpenWebUI;
- один primary provider через `.env`;
- второй provider через OpenWebUI Admin UI;
- один администратор;
- 3-4 пользователя;
- persistent volume;
- базовый host hardening: UFW + fail2ban;
- минимальный backup;
- smoke и acceptance checks.

Не входит:

- LiteLLM;
- model gateway;
- SSO/OIDC;
- web-поиск;
- RAG;
- document skills;
- plugins/tools/functions;
- fork OpenWebUI;
- custom frontend;
- logo replacement;
- corporate dashboard;
- white-label;
- маршрутизация провайдеров;
- бюджеты;
- интеграции с внутренними системами.

## Stage 2 / PRD-1

PRD-0 принят и закрыт. Актуальный PRD-1 / source of truth для согласования Stage 2:
[docs/prd/OPENWEBUI_CORPORATE_CHAT_PRD_1.md](docs/prd/OPENWEBUI_CORPORATE_CHAT_PRD_1.md).

Короткое summary для заказчика и переговоров:
[docs/prd/OPENWEBUI_CORPORATE_CHAT_PRD_1_CUSTOMER_SUMMARY.md](docs/prd/OPENWEBUI_CORPORATE_CHAT_PRD_1_CUSTOMER_SUMMARY.md).

Исторический черновик сохранен отдельно:
[docs/prd/OPENWEBUI_CORPORATE_CHAT_PRD_1_INITIAL_DRAFT.md](docs/prd/OPENWEBUI_CORPORATE_CHAT_PRD_1_INITIAL_DRAFT.md).

Краткий список изменений:
[docs/prd/OPENWEBUI_CORPORATE_CHAT_PRD_1_CHANGELOG.md](docs/prd/OPENWEBUI_CORPORATE_CHAT_PRD_1_CHANGELOG.md).

PRD-1 фиксирует развитие OpenWebUI в управляемую корпоративную AI-среду:
рабочие сценарии, общие prompts/templates, документы, транскрибация аудио/видео,
web-search, модельный каталог, basic analytics и policy допустимых данных.

Practical Stage 2 теперь включает адаптацию существующего ffmpeg workflow через
server-side STT proxy, OCR/layout-aware PDF pilot, проверку доступа руководителей
к рабочим чатам и technical check запрета удаления чатов.

LiteLLM/gateway, full AD lifecycle/SCIM, production OCR pipeline и
data masking/tokenization остаются отдельными optional/future slices.

Инженерный домен подготовки к реализации Stage 2:
[docs/stage2/README.md](docs/stage2/README.md).

Внутренний план работ, которые можно выполнять без нового согласования с
заказчиком:
[docs/stage2/implementation/STAGE2_UNBLOCKED_WORK_PLAN.md](docs/stage2/implementation/STAGE2_UNBLOCKED_WORK_PLAN.md).

Research findings актуализированы 2026-06-18. STT MVP current stage закрыт
2026-06-19: private `stage2-stt` sidecar routes, OpenWebUI static `Transcribe`
action, browser ffmpeg.wasm normalization and transcript return to OpenWebUI UX
are implemented/proven. Оставшаяся STT работа - testing/hardening, not
architectural discovery. Known issue as of 2026-06-23: native mobile microphone
dictation can show the recording waveform but produce no audio transcription and
stop after about five seconds; this is native Web Speech API/mobile hardening,
not a `stage2-stt` sidecar failure. Оставшиеся blockers по Stage 2 в целом:
customer test data, provider/data policy decisions, ADR review/status and
production hardening.

Реализация Stage 2 должна начинаться с backend/server-side boundaries, policies
и proofs; UI/frontend follows after backend contracts are clear.
Custom Stage 2 capabilities должны быть изолированы за явными backend
contracts. OpenWebUI остается upstream product shell, а frontend не владеет
security, provider keys, data policy, retention, manager visibility or usage
accounting.

Future OpenWebUI-facing Stage 2 features should follow the
[extension-first implementation pattern](docs/stage2/EXTENSION_FIRST_IMPLEMENTATION_PATTERN.md):
native mechanisms first, then Functions/Actions/Tools, thin static loader or UI
shim, private backend sidecar, and deep fork only after proof and owner/ADR
approval.

Подробные отчеты:

- [Stage 2 research
  actualization](docs/reports/2026-06-18/OPENWEBUI_STAGE2_RESEARCH_ACTUALIZATION.report.md)
- [ADR-0004 STT proxy boundary review
  report](docs/reports/2026-06-18/OPENWEBUI_ADR0004_STT_PROXY_BOUNDARY_REVIEW.report.md)
- [ADR-0004 ffmpeg workflow artifact inspection
  report](docs/reports/2026-06-18/OPENWEBUI_FFMPEG_WORKFLOW_ARTIFACT_INSPECTION.report.md)
- [ADR-0004 ffmpeg operator proof update
  report](docs/reports/2026-06-18/OPENWEBUI_ADR0004_FFMPEG_OPERATOR_PROOF_UPDATE.report.md)
- [ADR-0004 Lemonfox capabilities and runtime limits
  report](docs/reports/2026-06-19/OPENWEBUI_ADR0004_LEMONFOX_CAPABILITIES_AND_RUNTIME_LIMITS.report.md)
- [ADR-0004 compact STT contract refine
  report](docs/reports/2026-06-19/OPENWEBUI_ADR0004_COMPACT_STT_CONTRACT_REFINE.report.md)
- [STT runtime completion
  report](docs/reports/2026-06-19/OPENWEBUI_STT_RUNTIME_COMPLETION.report.md)
- [STT ffmpeg browser normalization implementation
  report](docs/reports/2026-06-19/OPENWEBUI_STT_FFMPEG_BROWSER_NORMALIZATION_IMPLEMENTATION.report.md)
- [STT docs implementation drift audit
  report](docs/reports/2026-06-19/OPENWEBUI_STT_DOCS_IMPLEMENTATION_DRIFT_AUDIT.report.md)
- [STT MVP feature closure
  report](docs/reports/2026-06-19/OPENWEBUI_STT_MVP_FEATURE_CLOSURE.report.md)
- [Native Web STT recorder patch
  report](docs/reports/2026-06-19/OPENWEBUI_NATIVE_WEB_STT_RECORDER_PATCH.report.md)
- [Mobile microphone STT anamnesis audit
  report](docs/reports/2026-06-23/OPENWEBUI_MOBILE_MICROPHONE_STT_ANAMNESIS_AUDIT.report.md)
- [Native OpenWebUI capability runtime audit
  report](docs/reports/2026-06-24/OPENWEBUI_NATIVE_CAPABILITY_RUNTIME_AUDIT.report.md)
- [OpenWebUI admin/test-user runtime proof
  report](docs/reports/2026-06-24/OPENWEBUI_ADMIN_TEST_USER_RUNTIME_PROOF.report.md)
- [Stage 2 agent review](docs/reports/2026-06-18/OPENWEBUI_PRD1_STAGE2_AGENT_REVIEW.report.md)
- [Backend-first refine
  report](docs/reports/2026-06-18/OPENWEBUI_STAGE2_BACKEND_FIRST_VL_OCR_REFINE.report.md)
- [VL OCR API provider shortlist research
  report](docs/reports/2026-06-25/OPENWEBUI_VL_OCR_API_PROVIDER_SHORTLIST_RESEARCH.report.md)
- [Source-of-truth sync
  report](docs/reports/2026-06-18/OPENWEBUI_PRD1_SOURCE_OF_TRUTH_SYNC.report.md)

Быстрые входы:

- [roadmap](docs/stage2/ROADMAP.md)
- [context index](docs/stage2/CONTEXT_INDEX.md)
- [domain map](docs/stage2/DOMAIN_MAP.md)
- [contract boundaries](docs/stage2/CONTRACT_BOUNDARIES.md)
- [implementation gates](docs/stage2/IMPLEMENTATION_GATES.md)
- [extension-first implementation
  pattern](docs/stage2/EXTENSION_FIRST_IMPLEMENTATION_PATTERN.md)

## Быстрый старт на сервере

Полный порядок см. в [docs/ops/DEPLOYMENT_RUNBOOK.md](docs/ops/DEPLOYMENT_RUNBOOK.md). Коротко:

```bash
git clone https://github.com/Kwentin3/corp-openweb-ui.git /opt/openwebui-prd0
cd /opt/openwebui-prd0
cp .env.example .env
chmod 600 .env
vi .env
bash scripts/preflight.sh
bash scripts/network-hardening-check.sh
docker compose --env-file .env -f compose/openwebui.compose.yml up -d
bash scripts/smoke-test.sh --strict-tls
```

Реальный `.env` не коммитить.
Перед запуском закрыть операторские решения в
[docs/ops/DEPLOYMENT_DECISIONS.md](docs/ops/DEPLOYMENT_DECISIONS.md).

## Навигация

- PRD-0: [docs/prd/OPENWEBUI_CORPORATE_CHAT_PRD_0.md](docs/prd/OPENWEBUI_CORPORATE_CHAT_PRD_0.md)
- PRD-1 / Stage 2 source of truth:
  [docs/prd/OPENWEBUI_CORPORATE_CHAT_PRD_1.md](docs/prd/OPENWEBUI_CORPORATE_CHAT_PRD_1.md)
- PRD-1 Stage 2 customer summary:
  [docs/prd/OPENWEBUI_CORPORATE_CHAT_PRD_1_CUSTOMER_SUMMARY.md](docs/prd/OPENWEBUI_CORPORATE_CHAT_PRD_1_CUSTOMER_SUMMARY.md)
- Предложение по развитию Stage 2:
  [docs/stage2/proposals/CUSTOMER_STAGE2_GOVERNANCE_PROPOSAL.md](docs/stage2/proposals/CUSTOMER_STAGE2_GOVERNANCE_PROPOSAL.md)
- Решения после runtime-аудита OpenWebUI:
  [docs/stage2/proposals/CUSTOMER_STAGE2_RUNTIME_DECISIONS.md](docs/stage2/proposals/CUSTOMER_STAGE2_RUNTIME_DECISIONS.md)
- Stage 2 Unblocked Work Plan:
  [docs/stage2/implementation/STAGE2_UNBLOCKED_WORK_PLAN.md](docs/stage2/implementation/STAGE2_UNBLOCKED_WORK_PLAN.md)
- Stage 2 selected story proof prep:
  [selected stories](docs/stage2/implementation/STAGE2_SELECTED_USER_STORIES.md),
  [synthetic data requirements](docs/stage2/testdata/STAGE2_SELECTED_STORIES_SYNTHETIC_DATA_REQUIREMENTS.md),
  [proof plans](docs/stage2/implementation/STAGE2_SELECTED_STORIES_PROOF_PLANS.md)
- Stage 2 VL OCR API provider shortlist research:
  [docs/stage2/research/VL_OCR_API_PROVIDER_SHORTLIST_RESEARCH.md](docs/stage2/research/VL_OCR_API_PROVIDER_SHORTLIST_RESEARCH.md)
- PRD-1 initial historical draft:
  [docs/prd/OPENWEBUI_CORPORATE_CHAT_PRD_1_INITIAL_DRAFT.md](docs/prd/OPENWEBUI_CORPORATE_CHAT_PRD_1_INITIAL_DRAFT.md)
- PRD-1 changelog:
  [docs/prd/OPENWEBUI_CORPORATE_CHAT_PRD_1_CHANGELOG.md](docs/prd/OPENWEBUI_CORPORATE_CHAT_PRD_1_CHANGELOG.md)
- Stage 2 engineering domain: [docs/stage2/README.md](docs/stage2/README.md)
- Stage 2 roadmap: [docs/stage2/ROADMAP.md](docs/stage2/ROADMAP.md)
- Stage 2 context index: [docs/stage2/CONTEXT_INDEX.md](docs/stage2/CONTEXT_INDEX.md)
- Stage 2 context usage rules:
  [docs/stage2/CONTEXT_USAGE_RULES.md](docs/stage2/CONTEXT_USAGE_RULES.md)
- Stage 2 domain map: [docs/stage2/DOMAIN_MAP.md](docs/stage2/DOMAIN_MAP.md)
- Stage 2 contract boundaries:
  [docs/stage2/CONTRACT_BOUNDARIES.md](docs/stage2/CONTRACT_BOUNDARIES.md)
- Stage 2 implementation gates:
  [docs/stage2/IMPLEMENTATION_GATES.md](docs/stage2/IMPLEMENTATION_GATES.md)
- Stage 2 extension-first implementation pattern:
  [docs/stage2/EXTENSION_FIRST_IMPLEMENTATION_PATTERN.md](docs/stage2/EXTENSION_FIRST_IMPLEMENTATION_PATTERN.md)
- Stage 2 STT backend implementation plan:
  [docs/stage2/implementation/STT_BACKEND_IMPLEMENTATION_PLAN.md](docs/stage2/implementation/STT_BACKEND_IMPLEMENTATION_PLAN.md)
- Stage 2 native capability audit:
  [docs/stage2/implementation/OPENWEBUI_NATIVE_CAPABILITY_AUDIT.md](docs/stage2/implementation/OPENWEBUI_NATIVE_CAPABILITY_AUDIT.md)
- Stage 2 research actualization report:
  [OPENWEBUI Stage 2 research actualization report][stage2-research-actualization-report]
- ADR-0004 STT proxy boundary review report:
  [OPENWEBUI ADR-0004 STT proxy boundary review report][adr0004-stt-proxy-boundary-review-report]
- ADR-0004 ffmpeg workflow artifact inspection report:
  [OPENWEBUI ADR-0004 ffmpeg workflow artifact inspection report][adr0004-ffmpeg-workflow-inspection-report]
- ADR-0004 ffmpeg operator proof update report:
  [OPENWEBUI ADR-0004 ffmpeg operator proof update report][adr0004-ffmpeg-operator-proof-update-report]
- ADR-0004 Lemonfox capabilities and runtime limits report:
  [OPENWEBUI ADR-0004 Lemonfox capabilities and runtime limits report][adr0004-lemonfox-capabilities-report]
- ADR-0004 compact STT contract refine report:
  [OPENWEBUI ADR-0004 compact STT contract refine report][adr0004-compact-stt-contract-report]
- STT runtime completion report:
  [OPENWEBUI STT runtime completion report][stt-runtime-completion-report]
- STT ffmpeg browser normalization implementation report:
  [OPENWEBUI STT ffmpeg browser normalization implementation report][stt-ffmpeg-normalization-report]
- STT docs implementation drift audit report:
  [OPENWEBUI STT docs implementation drift audit report][stt-docs-drift-audit-report]
- STT MVP feature closure report:
  [OPENWEBUI STT MVP feature closure report][stt-mvp-feature-closure-report]
- Stage 2 agent review:
  [OPENWEBUI PRD-1 Stage 2 agent review][stage2-agent-review-report]
- Stage 2 backend-first / VL OCR refine report:
  [OPENWEBUI Stage 2 backend-first / VL OCR refine report][stage2-backend-vl-ocr-report]
- Stage 2 PRD-1 source-of-truth sync report:
  [OPENWEBUI PRD-1 source-of-truth sync report][stage2-source-of-truth-sync-report]

[stage2-research-actualization-report]: docs/reports/2026-06-18/OPENWEBUI_STAGE2_RESEARCH_ACTUALIZATION.report.md
[adr0004-stt-proxy-boundary-review-report]: docs/reports/2026-06-18/OPENWEBUI_ADR0004_STT_PROXY_BOUNDARY_REVIEW.report.md
[adr0004-ffmpeg-workflow-inspection-report]: docs/reports/2026-06-18/OPENWEBUI_FFMPEG_WORKFLOW_ARTIFACT_INSPECTION.report.md
[adr0004-ffmpeg-operator-proof-update-report]: docs/reports/2026-06-18/OPENWEBUI_ADR0004_FFMPEG_OPERATOR_PROOF_UPDATE.report.md
[adr0004-lemonfox-capabilities-report]: docs/reports/2026-06-19/OPENWEBUI_ADR0004_LEMONFOX_CAPABILITIES_AND_RUNTIME_LIMITS.report.md
[adr0004-compact-stt-contract-report]: docs/reports/2026-06-19/OPENWEBUI_ADR0004_COMPACT_STT_CONTRACT_REFINE.report.md
[stt-runtime-completion-report]: docs/reports/2026-06-19/OPENWEBUI_STT_RUNTIME_COMPLETION.report.md
[stt-ffmpeg-normalization-report]: docs/reports/2026-06-19/OPENWEBUI_STT_FFMPEG_BROWSER_NORMALIZATION_IMPLEMENTATION.report.md
[stt-docs-drift-audit-report]: docs/reports/2026-06-19/OPENWEBUI_STT_DOCS_IMPLEMENTATION_DRIFT_AUDIT.report.md
[stt-mvp-feature-closure-report]: docs/reports/2026-06-19/OPENWEBUI_STT_MVP_FEATURE_CLOSURE.report.md
[stage2-agent-review-report]: docs/reports/2026-06-18/OPENWEBUI_PRD1_STAGE2_AGENT_REVIEW.report.md
[stage2-backend-vl-ocr-report]: docs/reports/2026-06-18/OPENWEBUI_STAGE2_BACKEND_FIRST_VL_OCR_REFINE.report.md
[stage2-source-of-truth-sync-report]: docs/reports/2026-06-18/OPENWEBUI_PRD1_SOURCE_OF_TRUTH_SYNC.report.md
- Blueprint:
  [docs/blueprint/OPENWEBUI_PRD_0_BLUEPRINT.md](docs/blueprint/OPENWEBUI_PRD_0_BLUEPRINT.md)
- Architecture: [docs/blueprint/ARCHITECTURE_OVERVIEW.md](docs/blueprint/ARCHITECTURE_OVERVIEW.md)
- Scope/non-goals: [docs/blueprint/SCOPE_AND_NON_GOALS.md](docs/blueprint/SCOPE_AND_NON_GOALS.md)
- Infra target: [docs/infra/INFRA_TARGET.md](docs/infra/INFRA_TARGET.md)
- Traefik plan: [docs/infra/DOMAIN_AND_TRAEFIK_PLAN.md](docs/infra/DOMAIN_AND_TRAEFIK_PLAN.md)
- Compose plan: [docs/infra/DOCKER_COMPOSE_PLAN.md](docs/infra/DOCKER_COMPOSE_PLAN.md)
- Env variables: [docs/infra/ENVIRONMENT_VARIABLES.md](docs/infra/ENVIRONMENT_VARIABLES.md)
- Provider plan: [docs/infra/PROVIDER_CONNECTIONS_PLAN.md](docs/infra/PROVIDER_CONNECTIONS_PLAN.md)
- Web search provider research:
  [docs/infra/WEB_SEARCH_PROVIDER_RESEARCH.md](docs/infra/WEB_SEARCH_PROVIDER_RESEARCH.md)
- Stage 2 Web Search context:
  [docs/stage2/WEB_SEARCH_CONTEXT_INDEX.md](docs/stage2/WEB_SEARCH_CONTEXT_INDEX.md)
  - Current status: Brave `brave_llm_context` native smoke baseline proven on
    2026-06-23; Yandex Search also passed Admin UI/native smoke on 2026-06-23
    as a working RU-provider path; private SearXNG native smoke passed in
    snippet/bypass mode and remains a comparison track.
  - Known deferred issue: vectorized Web Search retrieval can return `0`
    sources after successful search/embedding. Fix later only if we need long
    page loading, classic `brave`, SearXNG page loading, or full RAG over
    fetched content.
- Deployment runbook: [docs/ops/DEPLOYMENT_RUNBOOK.md](docs/ops/DEPLOYMENT_RUNBOOK.md)
- Docker bootstrap: [docs/ops/BOOTSTRAP_DOCKER_UBUNTU.md](docs/ops/BOOTSTRAP_DOCKER_UBUNTU.md)
- Host hardening runbook: [docs/ops/HOST_HARDENING_RUNBOOK.md](docs/ops/HOST_HARDENING_RUNBOOK.md)
- Provider setup runbook: [docs/ops/PROVIDER_SETUP_RUNBOOK.md](docs/ops/PROVIDER_SETUP_RUNBOOK.md)
- Deployment decisions: [docs/ops/DEPLOYMENT_DECISIONS.md](docs/ops/DEPLOYMENT_DECISIONS.md)
- Backup/restore: [docs/ops/BACKUP_RESTORE_RUNBOOK.md](docs/ops/BACKUP_RESTORE_RUNBOOK.md)
- Smoke tests: [docs/ops/SMOKE_TESTS.md](docs/ops/SMOKE_TESTS.md)
- Acceptance tests: [docs/ops/ACCEPTANCE_TESTS.md](docs/ops/ACCEPTANCE_TESTS.md)
- Security minimum: [docs/security/SECURITY_MINIMUM.md](docs/security/SECURITY_MINIMUM.md)
- Firewall/fail2ban:
  [docs/security/FIREWALL_AND_FAIL2BAN.md](docs/security/FIREWALL_AND_FAIL2BAN.md)
- Pilot checklist: [docs/pilot/PILOT_CHECKLIST.md](docs/pilot/PILOT_CHECKLIST.md)
- PRD-0 post-acceptance audit:
  [OPENWEBUI PRD-0 post-acceptance audit][prd0-post-acceptance-audit-report]
- Engineering report:
  [OPENWEBUI PRD-0 engineering package report][prd0-engineering-package-report]
- REFINE-2 report:
  [OPENWEBUI PRD-0 REFINE-2 report][prd0-refine-2-report]

[prd0-refine-2-report]: docs/reports/2026-06-09/OPENWEBUI_PRD_0_REFINE_2_PROVIDERS_AND_HARDENING.report.md
[prd0-post-acceptance-audit-report]: docs/reports/2026-06-16/OPENWEBUI_PRD_0_POST_ACCEPTANCE_AUDIT.report.md
[prd0-engineering-package-report]: docs/reports/2026-06-09/OPENWEBUI_PRD_0_ENGINEERING_PACKAGE.report.md
- REFINE-3 report:
  [OPENWEBUI PRD-0 REFINE-3 report][prd0-refine-3-report]

[prd0-refine-3-report]: docs/reports/2026-06-09/OPENWEBUI_PRD_0_REFINE_3_LOW_COST_CUSTOMIZATION.report.md

## Skeleton

- Compose: [compose/openwebui.compose.yml](compose/openwebui.compose.yml)
- Env example: [.env.example](.env.example)
- Preflight: [scripts/preflight.sh](scripts/preflight.sh)
- Network hardening check: [scripts/network-hardening-check.sh](scripts/network-hardening-check.sh)
- Backup: [scripts/backup.sh](scripts/backup.sh)
- Restore notes: [scripts/restore.md](scripts/restore.md)
- Smoke test: [scripts/smoke-test.sh](scripts/smoke-test.sh)

## Безопасность

Не коммитить реальные API-ключи, пароли, токены, private keys, `.env` и backup-архивы. Точный SSH
endpoint хранится только локально в ignored-файле `local/INFRA_TARGET.local.md`.
