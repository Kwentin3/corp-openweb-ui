# Stage 2 Engineering Roadmap

Это roadmap подготовки к реализации, а не реализация.

## Delivery principle

Stage 2 implementation must start from backend/server-side boundaries, policies and proofs. Frontend/UI work follows after backend contracts are clear.

Frontend must not become the place where security, provider keys, data policy, retention rules or access rules are decided.

Recommended slice order for risky domains:

1. ADR / policy decision.
2. Backend contract and runtime proof.
3. Minimal backend/API slice.
4. UI/browser integration.
5. Polish and instructions.

## Phase 0. Documentation domain setup

Status: complete.

- Создать `docs/stage2/README.md`.
- Создать [CONTEXT_INDEX.md](CONTEXT_INDEX.md).
- Создать [ROADMAP.md](ROADMAP.md).
- Создать [DOMAIN_MAP.md](DOMAIN_MAP.md).
- Создать доменные blueprints.
- Создать research docs.
- Создать acceptance matrix и test data requirements.
- Обновить root [README.md](../../README.md).

Exit signal:

- Stage 2 documentation domain связан ссылками.
- Будущий агент может открыть context index и найти нужный домен без чтения всей PRD-1.

## Phase 1. Capability research

Status: documentation research complete on 2026-06-18; runtime proof still required where marked.

Completed research topics:

- OpenWebUI deployed-version evidence and native feature docs.
- Workspaces, prompts, knowledge, groups, RBAC.
- STT, Lemonfox, supported formats and limits.
- Existing ffmpeg browser workflow integration boundary.
- Web-search providers: Brave and Yandex Search API.
- Documents/OCR/Excel handling.
- Provider catalog: OpenAI mini, Claude API, DeepSeek, YandexGPT, GigaChat.
- Manager visibility and chat access model.
- Chat deletion/retention controls.
- Usage analytics and cost visibility.
- Future data masking/tokenization boundary.

Exit signal:

- По каждому research topic есть проверенные источники, proof plan result или documented blocker.
- Нельзя переходить к implementation на основании предположений.

Remaining blockers:

- Deployed/staging Admin UI capability proof for pinned OpenWebUI version.
- Customer test files for broker/OCR/XLSX.
- Customer provider/data policy approval.
- Existing ffmpeg workflow artifact inspection.
- Customer approval for manager visibility, no-delete and retention/audit policy boundaries.
- OCR/VL OCR pilot test set and provider/candidate list.

## Phase 2. Architecture decisions

Status: next.

ADR items:

1. ADR-0001 Data Policy by Provider Class.
2. ADR-0002 Manager Visibility Policy.
3. ADR-0003 Chat Deletion, Retention and Audit.
4. ADR-0004 STT Proxy Boundary.
5. ADR-0005 OCR / VL OCR Pilot Scope.
6. ADR-0006 Provider Model Catalog.
7. ADR-0007 Web-search Provider.
8. Billing approach: native analytics vs gateway.

Recommended next sequence:

1. Data Policy ADR.
2. STT Proxy Boundary ADR.
3. Provider Model Catalog ADR.
4. Web-search Provider ADR.
5. Manager Visibility ADR.
6. Chat Deletion/Retention ADR.
7. OCR/VL OCR Pilot Scope ADR.
8. Runtime proof matrix.
9. Customer test data package.
10. Implementation backlog by slices.

Data Policy goes first because provider setup and document/transcript workflows depend on allowed data classes by provider class.

STT Proxy goes early because transcription is a priority scenario and requires a backend boundary before UI/browser integration.

Exit signal:

- Решения оформлены ADR или documented decision.
- Future slices не смешаны с Practical Stage 2 implementation.
- Provider setup не начат до customer-approved data policy.
- Manager visibility, no-delete, retention and audit are not merged into one implicit feature.

## Phase 3. Implementation planning

Status: after ADRs and runtime/customer blockers.

- Разбить работы на slices.
- Определить dependencies.
- Подготовить acceptance matrix.
- Подготовить test data requirements.
- Оценить risks.
- Подготовить реализационные задачи.

Exit signal:

- Каждый implementation slice имеет owner, input docs, acceptance signal и rollback/defer condition.

## Phase 4. Implementation

Implementation starts only after roadmap/blueprints/research/ADRs are reviewed and approved.

На этом этапе код, конфигурация, provider setup, runtime changes и OpenWebUI customization не выполняются.

Implementation order after approval:

1. Backend/server-side boundaries and runtime proofs.
2. Minimal backend/API slice.
3. UI/browser integration.
4. User/admin instructions and acceptance checks.
