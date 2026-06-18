# Stage 2 Engineering Roadmap

Это roadmap подготовки к реализации, а не реализация.

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

## Phase 2. Architecture decisions

Status: next.

- Transcription module strategy.
- STT proxy design.
- OCR pilot scope.
- Web-search provider selection.
- Provider model catalog.
- Manager visibility policy.
- Chat deletion restriction approach.
- Data policy.
- Billing approach: native analytics vs gateway.

Exit signal:

- Решения оформлены ADR или documented decision.
- Future slices не смешаны с Practical Stage 2 implementation.

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
