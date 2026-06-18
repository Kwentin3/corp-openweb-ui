# Stage 2 Context Index

Цель: быстро понять, какие документы читать по конкретной будущей задаче.

## Общий Stage 2 scope

Read first:

- [PRD-1](../prd/OPENWEBUI_CORPORATE_CHAT_PRD_1.md)
- [README](README.md)
- [DOMAIN_MAP](DOMAIN_MAP.md)
- [CONTRACT_BOUNDARIES](CONTRACT_BOUNDARIES.md)
- [IMPLEMENTATION_GATES](IMPLEMENTATION_GATES.md)

Additional context:

- [Customer summary](../prd/OPENWEBUI_CORPORATE_CHAT_PRD_1_CUSTOMER_SUMMARY.md)
- [PRD-0 audit](../reports/2026-06-16/OPENWEBUI_PRD_0_POST_ACCEPTANCE_AUDIT.report.md)

Skip unless needed:

- PRD-0 deploy runbooks.

Comment:

- PRD-1 is the source of truth.
- Stage 2 custom logic must stay behind backend/domain contracts.

## Domain isolation / contract boundaries

Read first:

- [CONTRACT_BOUNDARIES](CONTRACT_BOUNDARIES.md)
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

- [WORKSPACES_AND_RBAC](blueprints/WORKSPACES_AND_RBAC.blueprint.md)
- [IMPLEMENTATION_GATES](IMPLEMENTATION_GATES.md)

Additional context:

- [OPENWEBUI_CAPABILITY_RESEARCH](research/OPENWEBUI_CAPABILITY_RESEARCH.md)
- [RBAC_MANAGER_VISIBILITY_RESEARCH](research/RBAC_MANAGER_VISIBILITY_RESEARCH.md)
- [ACCESS_POLICY](../security/ACCESS_POLICY.md)

Skip unless needed:

- STT/provider pricing docs.

Comment:

- Research is done; runtime proof is still needed for the deployed version.

## Транскрибация

Read first:

- [TRANSCRIPTION_STT](blueprints/TRANSCRIPTION_STT.blueprint.md)
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
- STT proxy ADR must define backend boundary before final UI.
- External ffmpeg workflow contract is inspected and transferable as MP3 /
  `audio/mpeg`; operator manual proof exists for reported mobile/large-file
  cases, but implementation acceptance still needs reproducible proof matrix and
  production dependency decisions.

## Брокерские отчеты / 3-НДФЛ

Read first:

- [BROKER_REPORTS_3NDFL](blueprints/BROKER_REPORTS_3NDFL.blueprint.md)
- [ADR-0001 Data Policy](decisions/ADR-0001-data-policy-by-provider-class.md)
- [IMPLEMENTATION_GATES](IMPLEMENTATION_GATES.md)

Additional context:

- [DOCUMENTS_OCR_EXCEL_RESEARCH](research/DOCUMENTS_OCR_EXCEL_RESEARCH.md)
- [SECURITY_DATA_POLICY](blueprints/SECURITY_DATA_POLICY.blueprint.md)
- [PROVIDERS_MODEL_CATALOG](blueprints/PROVIDERS_MODEL_CATALOG.blueprint.md)

Skip unless needed:

- Ops deployment docs.

Comment:

- AI output is draft/analysis only.
- Scenario is blocked by customer test data.

## Web-search

Read first:

- [WEB_SEARCH](blueprints/WEB_SEARCH.blueprint.md)
- [ADR-0007 Web-search Provider](decisions/ADR-0007-web-search-provider.md)

Additional context:

- [WEB_SEARCH_PROVIDERS_RESEARCH](research/WEB_SEARCH_PROVIDERS_RESEARCH.md)
- Existing [WEB_SEARCH_PROVIDER_RESEARCH](../infra/WEB_SEARCH_PROVIDER_RESEARCH.md)

Skip unless needed:

- STT/OCR docs.

Comment:

- Brave is the first-pilot candidate if foreign search is allowed.
- Yandex Search is the Russian-provider candidate.

## Documents / OCR / Excel

Read first:

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
- Production OCR/layout pipeline remains future.

## Сканы / картинки / PDF OCR

Read first:

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

## Стоимость / analytics

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

Found:

- `README.md`
- `docs/prd/OPENWEBUI_CORPORATE_CHAT_PRD_1.md`
- `docs/prd/OPENWEBUI_CORPORATE_CHAT_PRD_0.md`
- `docs/reports/2026-06-16/OPENWEBUI_PRD_0_POST_ACCEPTANCE_AUDIT.report.md`
- `docs/blueprint/*`
- `docs/infra/*`
- `docs/ops/*`
- `docs/security/*`
- `docs/reports/2026-06-09/*`

Missing:

- `docs/README.md`
