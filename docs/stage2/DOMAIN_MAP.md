# Stage 2 Domain Map

Delivery principle: Stage 2 implementation starts from backend/server-side
boundaries, policies and proofs. Frontend/UI follows after backend contracts
are clear.

Frontend must not become the place where security, provider keys, data policy,
retention rules or access rules are decided.

Stage 2 custom capabilities must be isolated behind explicit backend contracts.
OpenWebUI remains the upstream product shell; custom Stage 2 logic should live
in bounded domain services, internal APIs, or thin integration shims.

Related contract map: [CONTRACT_BOUNDARIES.md](CONTRACT_BOUNDARIES.md).

## Boundary map

### OpenWebUI core

- auth/session surface;
- users/groups/RBAC where native;
- chat/workspace UI;
- prompts/knowledge/workspace models where native;
- native analytics if sufficient.

### Stage 2 backend/domain services

- STT proxy/job service;
- provider adapters;
- policy resolver;
- usage event collector;
- transcript normalization;
- retention/export lifecycle;
- OCR/VL OCR pilot adapters;
- internal health/smoke endpoints.

### Frontend/thin UI

- user interaction;
- upload/progress/cancel UX;
- calls internal Stage 2 APIs;
- never stores provider API keys;
- never decides data policy.

### External providers

- STT provider;
- LLM providers;
- web-search providers;
- OCR/VL OCR providers.

## Workspaces / RBAC / shared prompts

Goal:

- Собрать управляемые рабочие сценарии, группы, prompts/templates and shared knowledge.

Why needed:

- Без этого Stage 2 останется набором разрозненных чатов.

Owner type:

- Engineering.
- Admin.
- AI-methodologist.

Inputs:

- PRD-1.
- ACCESS_POLICY.
- OpenWebUI docs research.

Outputs:

- Workspace/RBAC blueprint.
- Capability research.
- Implementation slices.

Risks:

- Docs/runtime mismatch.
- Additive permissions.
- Путаница между workspace and file storage.

Dependencies:

- OpenWebUI capabilities.
- Customer groups.

Open questions:

- Какие группы/роли финальные?
- Кто owner templates?

Status:

- Research complete; runtime proof needed.

## Transcription / STT / ffmpeg browser workflow

Goal:

- Дать priority transcription scenario для audio/video через backend STT proxy boundary.

Why needed:

- Это главный customer priority и technical asset исполнителя.

Owner type:

- Engineering.
- Admin.

Inputs:

- PRD-1.
- Transcription research.

Outputs:

- STT blueprint.
- ffmpeg research.
- Lemonfox research.
- STT proxy decision.

Risks:

- API keys in browser.
- File size.
- Progress/cancel.
- Storage.
- OpenWebUI integration.

Dependencies:

- Browser workflow.
- STT provider.
- Server-side proxy.
- Data policy.

Open questions:

- Где actual ffmpeg artifact?
- Какие лимиты файлов?

Status:

- Research complete; ADR needed before UI.

## Broker reports / 3-НДФЛ

Goal:

- Оформить сценарий анализа брокерских отчетов.

Why needed:

- Приоритетный бизнес-сценарий заказчика.

Owner type:

- AI-methodologist.
- Customer.
- Engineering.

Inputs:

- PRD-1.
- Test data.
- Claude example.

Outputs:

- Broker blueprint.
- Prompts.
- Acceptance cases.

Risks:

- Налоговые обещания.
- Extraction quality.
- Sensitive data.

Dependencies:

- Documents/OCR.
- Providers.
- Data policy.

Open questions:

- Какие реальные отчеты есть?
- Что считается good result?

Status:

- Blocked by customer test data.

## Web-search

Goal:

- Дать всем управляемый web-search через policy, limits and backend/provider boundary.

Why needed:

- Нужен всем пользователям, но требует лимитов и cost visibility.

Owner type:

- Engineering.
- Admin.

Inputs:

- PRD-1.
- Web-search provider research.

Outputs:

- Web-search blueprint.
- Provider selection ADR.

Risks:

- Privacy.
- Cost spikes.
- Weak sources.
- Provider limits.

Dependencies:

- Provider choice.
- Data policy.
- Analytics.

Open questions:

- Brave vs Yandex Search?
- Какие smoke queries?

Status:

- Research complete; provider ADR needed.

## Documents / OCR / VL OCR / Excel

Goal:

- Разделить простые documents, OCR/VL OCR pilot and future production pipeline.

Why needed:

- Брокерские отчеты и рабочие документы не всегда plain text.
- Сканы и сложные PDF могут требовать vision-language OCR.

Owner type:

- Engineering.
- AI-methodologist.

Inputs:

- PRD-1.
- Test data.
- VL OCR research.

Outputs:

- Documents/OCR blueprint.
- Research.
- Test data requirements.
- OCR/VL OCR pilot decision.

Risks:

- Сканированные PDF.
- Tables.
- Excel formulas.
- Hallucinated OCR.
- Ложные обещания.

Dependencies:

- Broker scenario.
- OCR tools.
- Parser/tool path.
- Data policy.

Open questions:

- Какая доля сканов?
- Какие XLSX реально встречаются?
- Можно ли отправлять samples external providers?

Status:

- Research complete; samples needed.

## Provider catalog / models

Goal:

- Описать models, costs and allowed use cases after data policy.

Why needed:

- Пользователям нужен curated catalog, админам - контроль.

Owner type:

- Engineering.
- Admin.

Inputs:

- PRD-1.
- Provider plans.
- ADR-0001.

Outputs:

- Provider catalog blueprint.
- Provider research.

Risks:

- Claude Code confusion.
- API compatibility.
- Quotas.
- Costs.
- Data policy.

Dependencies:

- Customer keys.
- Model access.
- Approved data policy.

Open questions:

- Какие providers production vs research?

Status:

- Research complete; data policy first; catalog ADR needed.

## Usage analytics / cost visibility

Goal:

- Получить basic visibility по usage/cost.

Why needed:

- Stage 2 должен быть управляемым по расходам.

Owner type:

- Engineering.
- Admin.

Inputs:

- PRD-1.
- OpenWebUI analytics research.

Outputs:

- Analytics blueprint.
- Billing decision.

Risks:

- Hard billing may require gateway.
- Native analytics may be version-dependent.

Dependencies:

- Provider catalog.
- Web-search/STT usage.

Open questions:

- Достаточно native analytics?
- Нужен gateway?

Status:

- Research complete; runtime proof needed.

## Security / data policy / future masking

Goal:

- Зафиксировать allowed data by provider class before provider setup and future masking boundary.

Why needed:

- Финансовые/персональные данные нельзя отправлять без правил.

Owner type:

- Security.
- Admin.
- Customer.

Inputs:

- PRD-1.
- Security docs.

Outputs:

- Security blueprint.
- Data masking research.
- ADR-0001.

Risks:

- False security from simple replacement.
- Provider exposure.
- Lack of leak tests.

Dependencies:

- Provider catalog.
- Workspaces.
- Broker/docs/transcription scenarios.

Open questions:

- Какие данные разрешены для foreign/RU/local providers?

Status:

- Research complete; policy decision needed before provider setup.

## Manager visibility / no-delete / retention / audit policy

Goal:

- Проверить рабочий доступ руководителей, запрет удаления, retention and audit separately.

Why needed:

- Customer wants this early, but privacy boundary is critical.

Owner type:

- Engineering.
- Admin.
- Customer.

Inputs:

- PRD-1.
- RBAC research.
- Retention research.

Outputs:

- Manager visibility blueprint.
- ADR-0002.
- ADR-0003.
- Runtime proof matrix.

Risks:

- Руководитель видит слишком много.
- Native limitation.
- Audit gaps.
- Смешение no-delete и retention.

Dependencies:

- OpenWebUI RBAC.
- Retention/storage.
- Policy.

Open questions:

- Какие чаты считаются рабочими?
- Видит ли сотрудник правило?
- Сколько храним chats/files/transcripts?

Status:

- Research complete; runtime/customer proof needed.

## Operations / acceptance / testing

Goal:

- Сформировать acceptance, smoke, update/rollback and handoff.

Why needed:

- Stage 2 должен приниматься проверками, не впечатлением.

Owner type:

- Engineering.
- Admin.

Inputs:

- PRD-1.
- PRD-0 ops docs.

Outputs:

- Ops blueprint.
- Acceptance matrix.
- Test data requirements.

Risks:

- Runtime changes without rollback.
- Missing test data.

Dependencies:

- All domains.

Open questions:

- Кто проводит acceptance?
- Есть ли test users/files?

Status:

- Planned after ADRs.
