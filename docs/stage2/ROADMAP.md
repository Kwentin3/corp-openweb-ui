# Stage 2 Engineering Roadmap

Это roadmap подготовки к реализации, а не реализация.

## Delivery principle

Stage 2 implementation must start from backend/server-side boundaries, policies and proofs.
Frontend/UI work follows after backend contracts are clear.

Frontend must not become the place where security, provider keys, data policy, retention rules or
access rules are decided.

Stage 2 custom capabilities must be isolated behind explicit backend contracts.
OpenWebUI remains the upstream product shell; custom logic should live in bounded
domain services, internal APIs, or thin integration shims.

Contract boundary reference: [CONTRACT_BOUNDARIES.md](CONTRACT_BOUNDARIES.md).

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
- Создать [CONTEXT_USAGE_RULES.md](CONTEXT_USAGE_RULES.md).
- Создать [ROADMAP.md](ROADMAP.md).
- Создать [DOMAIN_MAP.md](DOMAIN_MAP.md).
- Создать [CONTRACT_BOUNDARIES.md](CONTRACT_BOUNDARIES.md).
- Создать [IMPLEMENTATION_GATES.md](IMPLEMENTATION_GATES.md).
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

## Parallel stream. Unblocked documentation and proof planning

Status: active.

Some Stage 2 work can continue without waiting for new customer decisions:
scenario user stories, synthetic test data index, usage analytics proof plan,
VL OCR synthetic benchmark plan, simple document extraction proof plan and
configuration-first scenario proof plan.

Reference:
[STAGE2_UNBLOCKED_WORK_PLAN.md](implementation/STAGE2_UNBLOCKED_WORK_PLAN.md).

This stream is documentation, research, benchmark-plan and proof-plan work. It
does not change runtime, does not use customer data and does not close Gate 7
or Gate 8.

Exit signal:

- user stories and synthetic test data structure are ready;
- proof plans are linked to acceptance and implementation gates;
- customer-blocked acceptance remains explicitly blocked.

## Phase 2. Architecture decisions

Status: next.

### ADR registry order

Это порядок нумерации документов. Он не обязан совпадать с порядком
рассмотрения перед реализацией.

1. ADR-0001 Data Policy by Provider Class.
2. ADR-0002 Manager Visibility Policy.
3. ADR-0003 Chat Deletion, Retention and Audit.
4. ADR-0004 STT Proxy Boundary.
5. ADR-0005 OCR / VL OCR Pilot Scope.
6. ADR-0006 Provider Model Catalog.
7. ADR-0007 Web-search Provider.
8. ADR-0008 Native Analytics vs Hard Billing.

### Recommended execution / review order

Это порядок рассмотрения перед реализацией. Он отражает зависимости.

1. Data Policy by Provider Class.
2. STT Proxy Boundary.
3. Provider Model Catalog.
4. Web-search Provider.
5. Manager Visibility Policy.
6. Chat Deletion / Retention / Audit.
7. OCR / VL OCR Pilot Scope.
8. Native Analytics vs Hard Billing.
9. Runtime smoke/checks where a domain still requires them.
10. Customer test data package.
11. Implementation backlog by slices.

Data Policy goes first because provider setup and document/transcript workflows
depend on allowed data classes by provider class.

STT Proxy goes early because transcription is a priority scenario and requires a
backend boundary before UI/browser integration.

### Related gate document

Review [IMPLEMENTATION_GATES.md](IMPLEMENTATION_GATES.md) before moving from ADR
work into implementation planning.

Review [CONTRACT_BOUNDARIES.md](CONTRACT_BOUNDARIES.md) before any task that
adds custom backend/domain services, internal APIs, thin UI integration or
provider adapters.

Gate sequence:

1. Data Policy approved.
2. STT Proxy Boundary approved.
3. Provider Model Catalog approved.
4. Web-search Provider approved.
5. Manager Visibility and Retention policy approved.
6. OCR / VL OCR pilot scope approved.
7. Runtime proof complete.
8. Customer test data package received.
9. Implementation slices approved.

Exit signal:

- Решения оформлены ADR или documented decision.
- Future slices не смешаны с Practical Stage 2 implementation.
- Provider setup не начат до customer-approved data policy.
- Manager visibility, no-delete, retention and audit are not merged into one implicit feature.

## Phase 3. Implementation planning

Delivered bounded capability, 2026-07-17: PDF Table Intake Gate 1 now has a
versioned native Function contract for table-region detection and deterministic
PNG crops with global `8 %` X/Y page-relative padding. This closes only the
Gate 1 raster-candidate boundary; its 2026-07-17 stage proof is accepted and
recorded in the dated closure report. Canonical table JSON,
dual-VLM comparison and financial semantics remain later slices. See
[the Gate 1 contract](contracts/BROKER_REPORTS_PDF_TABLE_INTAKE_GATE1.v1.md).

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

На этом этапе код, конфигурация, provider setup, runtime changes и OpenWebUI customization не
выполняются.

Implementation order after approval:

1. Backend/server-side boundaries and runtime proofs.
2. Minimal backend/API slice.
3. UI/browser integration.
4. User/admin instructions and acceptance checks.
