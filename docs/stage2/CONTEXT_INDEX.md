# Stage 2 Context Index

Цель: быстро понять, какие документы читать по конкретной будущей задаче.

| Задача / домен | Что читать сначала | Дополнительный контекст | Что не читать без необходимости | Комментарий |
| -------------- | ------------------ | ----------------------- | ------------------------------- | ----------- |
| Общий Stage 2 scope | [PRD-1](../prd/OPENWEBUI_CORPORATE_CHAT_PRD_1.md), [README](README.md), [DOMAIN_MAP](DOMAIN_MAP.md) | [Customer summary](../prd/OPENWEBUI_CORPORATE_CHAT_PRD_1_CUSTOMER_SUMMARY.md), [PRD-0 audit](../reports/2026-06-16/OPENWEBUI_PRD_0_POST_ACCEPTANCE_AUDIT.report.md) | PRD-0 deploy runbooks | PRD-1 - source of truth. |
| Рабочие пространства / RBAC | [WORKSPACES_AND_RBAC](blueprints/WORKSPACES_AND_RBAC.blueprint.md) | [OPENWEBUI_CAPABILITY_RESEARCH](research/OPENWEBUI_CAPABILITY_RESEARCH.md), [RBAC_MANAGER_VISIBILITY_RESEARCH](research/RBAC_MANAGER_VISIBILITY_RESEARCH.md), [ACCESS_POLICY](../security/ACCESS_POLICY.md) | STT/provider pricing docs | Research done; runtime proof needed for deployed version. |
| Транскрибация | [TRANSCRIPTION_STT](blueprints/TRANSCRIPTION_STT.blueprint.md) | [TRANSCRIPTION_STT_RESEARCH](research/TRANSCRIPTION_STT_RESEARCH.md), [FFMPEG_BROWSER_WORKFLOW_RESEARCH](research/FFMPEG_BROWSER_WORKFLOW_RESEARCH.md), [LEMONFOX_STT_RESEARCH](research/LEMONFOX_STT_RESEARCH.md) | Broker/tax docs | API keys never in browser; ADR should define STT proxy. |
| Брокерские отчеты / 3-НДФЛ | [BROKER_REPORTS_3NDFL](blueprints/BROKER_REPORTS_3NDFL.blueprint.md) | [DOCUMENTS_OCR_EXCEL_RESEARCH](research/DOCUMENTS_OCR_EXCEL_RESEARCH.md), [SECURITY_DATA_POLICY](blueprints/SECURITY_DATA_POLICY.blueprint.md), [PROVIDERS_MODEL_CATALOG](blueprints/PROVIDERS_MODEL_CATALOG.blueprint.md) | Ops deployment docs | AI output is draft/analysis only; blocked by test data. |
| Web-search | [WEB_SEARCH](blueprints/WEB_SEARCH.blueprint.md) | [WEB_SEARCH_PROVIDERS_RESEARCH](research/WEB_SEARCH_PROVIDERS_RESEARCH.md), existing [WEB_SEARCH_PROVIDER_RESEARCH](../infra/WEB_SEARCH_PROVIDER_RESEARCH.md) | STT/OCR docs | Brave first-pilot candidate; Yandex Search is Russian-provider candidate. |
| Documents / OCR / Excel | [DOCUMENTS_OCR_EXCEL](blueprints/DOCUMENTS_OCR_EXCEL.blueprint.md) | [DOCUMENTS_OCR_EXCEL_RESEARCH](research/DOCUMENTS_OCR_EXCEL_RESEARCH.md), [TEST_DATA_REQUIREMENTS](acceptance/TEST_DATA_REQUIREMENTS.md) | Provider setup runbook unless integration reaches provider calls | OCR is pilot; production pipeline is future. |
| Provider catalog / models | [PROVIDERS_MODEL_CATALOG](blueprints/PROVIDERS_MODEL_CATALOG.blueprint.md) | [PROVIDERS_YANDEX_GIGACHAT_DEEPSEEK_CLAUDE_RESEARCH](research/PROVIDERS_YANDEX_GIGACHAT_DEEPSEEK_CLAUDE_RESEARCH.md), [PROVIDER_CONNECTIONS_PLAN](../infra/PROVIDER_CONNECTIONS_PLAN.md) | Runtime `.env` | Claude API is provider; Claude Code is not chat provider; exact model IDs required. |
| Стоимость / analytics | [USAGE_ANALYTICS_AND_COSTS](blueprints/USAGE_ANALYTICS_AND_COSTS.blueprint.md) | [USAGE_ANALYTICS_BILLING_RESEARCH](research/USAGE_ANALYTICS_BILLING_RESEARCH.md), [PROVIDERS_MODEL_CATALOG](blueprints/PROVIDERS_MODEL_CATALOG.blueprint.md) | Gateway deployment docs until decision | Native analytics first; hard billing is separate ADR. |
| Data policy / masking | [SECURITY_DATA_POLICY](blueprints/SECURITY_DATA_POLICY.blueprint.md) | [DATA_MASKING_FUTURE_RESEARCH](research/DATA_MASKING_FUTURE_RESEARCH.md), [SECRETS_POLICY](../security/SECRETS_POLICY.md), [SECURITY_MINIMUM](../security/SECURITY_MINIMUM.md) | Implementation code | Data masking is future slice. |
| Руководители и чаты | [MANAGER_VISIBILITY_AND_RETENTION](blueprints/MANAGER_VISIBILITY_AND_RETENTION.blueprint.md) | [RBAC_MANAGER_VISIBILITY_RESEARCH](research/RBAC_MANAGER_VISIBILITY_RESEARCH.md), [CHAT_DELETION_RETENTION_RESEARCH](research/CHAT_DELETION_RETENTION_RESEARCH.md) | Provider pricing docs | Privacy/security decision and runtime proof required. |
| Operations / acceptance | [OPS_AND_ACCEPTANCE](blueprints/OPS_AND_ACCEPTANCE.blueprint.md) | [ACCEPTANCE_MATRIX](acceptance/ACCEPTANCE_MATRIX.md), [SMOKE_TESTS](../ops/SMOKE_TESTS.md), [ACCEPTANCE_TESTS](../ops/ACCEPTANCE_TESTS.md), [UPDATE_ROLLBACK_RUNBOOK](../ops/UPDATE_ROLLBACK_RUNBOOK.md) | Feature-specific research unless needed | No production changes in planning phase. |

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
