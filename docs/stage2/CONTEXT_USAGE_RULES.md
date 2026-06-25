# Stage 2 Context Usage Rules

Статус: внутренние правила чтения Stage 2 документации для будущих агентов.
Это не implementation plan, не customer-facing document и не разрешение на
runtime changes.

`Context routing` - правила выбора документов: если задача относится к
конкретному домену, агент читает нужные документы в правильном порядке и не
делает действий, которые эти документы не разрешают.

## 1. Context acquisition checklist

1. Определи тип задачи: docs-only planning, selected stories, synthetic data,
   proof execution, implementation planning, customer-facing proposal, research
   update или runtime investigation.
2. Открой [CONTEXT_INDEX.md](CONTEXT_INDEX.md) и найди подходящий route.
3. Прочитай `Read first`.
4. Прочитай `Additional context`, если задача затрагивает соседний домен,
   status, blockers или acceptance.
5. Перед implementation/runtime задачей обязательно открой
   [IMPLEMENTATION_GATES.md](IMPLEMENTATION_GATES.md) и
   [CONTRACT_BOUNDARIES.md](CONTRACT_BOUNDARIES.md).
6. Если документы противоречат друг другу, не продолжай silently. Зафиксируй
   conflict: какие документы, какие строки, какой статус расходится, что нужно
   решить владельцу.
7. Если нужен customer data, provider account, `.env`, runtime proof or config
   change, остановись до отдельного approval.

## 2. Source-of-truth hierarchy

| Level | Document type | Rule |
| ----- | ------------- | ---- |
| 1 | PRD-1 | Главный продуктовый источник Stage 2. |
| 2 | Stage 2 README / CONTEXT_INDEX | Навигация и context routing, не реализация. |
| 3 | ROADMAP | Порядок движения и phase/status frame. |
| 4 | IMPLEMENTATION_GATES | Условия перехода к implementation/runtime work. |
| 5 | CONTRACT_BOUNDARIES | Границы backend/frontend/custom logic/provider calls. |
| 6 | ENGINEERING_BACKLOG | Текущий planning/status backlog. |
| 7 | ADRs | Решения только если approved; proposed ADR is not final decision. |
| 8 | Reports | Evidence: что было проверено и с каким результатом. |
| 9 | Research | Контекст, варианты и blockers; не команда к реализации. |
| 10 | Proposals | Customer-facing documents; не engineering backlog. |
| 11 | User stories / selected stories | Planning artifacts; не production scope. |
| 12 | Synthetic data docs | Mechanics only; не customer acceptance. |
| 13 | Proof plans | Планы проверок; not executed proof. |

Если более низкий уровень выглядит шире или смелее, чем gate/contract/ADR,
используй более высокий уровень как ограничение.

## 3. Document type rules

- Research не является решением.
- Report не является планом реализации.
- Proposal не является backlog.
- Draft/proposed ADR не является approved decision.
- Customer-facing document нельзя использовать как engineering source без
  связанного internal doc.
- User story не является production scope.
- Synthetic data не доказывает качество на реальных данных заказчика.
- Proof plan не означает, что proof выполнен.
- Runtime proof report показывает evidence конкретного запуска; он не
  разрешает повторный runtime proof без approval.
- Web Search technical proof is not Web Search rollout approval.
- OCR/VL OCR synthetic benchmark is not production OCR acceptance.
- Docs-only document не разрешает runtime changes, config changes,
  provider setup or user/group/model/prompt/Knowledge creation.

## 4. Global guardrails

Запрещено без отдельного approval:

- не читать `.env`, secrets, tokens, credentials or private URLs;
- не использовать customer data;
- не запускать runtime proof or smoke;
- не подключать provider accounts;
- не менять OpenWebUI config;
- не создавать users, groups, models, prompts or Knowledge;
- не писать production code;
- не считать synthetic proof production acceptance;
- не считать proposed ADR approved;
- не считать customer proposal implementation task.
- Web Search smoke/proven connectivity does not approve production rollout.
  Техническая связность не означает, что Web Search можно включать всем
  пользователям.
- OCR/VL OCR synthetic benchmark does not prove production OCR readiness.
  Synthetic data не заменяет реальные документы заказчика для acceptance.
- Provider setup requires approved data policy and explicit provider/account
  approval.

## 5. Selected stories route

Для задач про selected stories, synthetic data, proof plans or first execution
package читать строго в этом порядке:

1. [STAGE2_SELECTED_USER_STORIES.md](implementation/STAGE2_SELECTED_USER_STORIES.md)
2. [STAGE2_SELECTED_STORIES_SYNTHETIC_DATA_REQUIREMENTS.md](testdata/STAGE2_SELECTED_STORIES_SYNTHETIC_DATA_REQUIREMENTS.md)
3. [STAGE2_SELECTED_STORIES_PROOF_PLANS.md](implementation/STAGE2_SELECTED_STORIES_PROOF_PLANS.md)
4. [OPENWEBUI_STAGE2_SELECTED_STORIES_PROOF_PREP.report.md](../reports/2026-06-25/OPENWEBUI_STAGE2_SELECTED_STORIES_PROOF_PREP.report.md)
5. [SYNTHETIC_TEST_DATA_INDEX.md](testdata/SYNTHETIC_TEST_DATA_INDEX.md)
6. [ACCEPTANCE_MATRIX.md](acceptance/ACCEPTANCE_MATRIX.md)
7. [IMPLEMENTATION_GATES.md](IMPLEMENTATION_GATES.md)

Boundary:

- synthetic files are not created yet unless a later task explicitly says so;
- proof plans are not executed unless a later task approves runtime proof;
- runtime changes require separate approval;
- customer acceptance remains blocked for real documents, real groups,
  provider/data policy and customer decisions.

## 6. Stop conditions

Stop and report a typed blocker if:

- source-of-truth hierarchy gives conflicting status;
- route lacks a needed gate or boundary document;
- selected task requires customer data, but only synthetic data exists;
- proof plan is being treated as executed proof;
- proposed ADR is being treated as approved;
- customer-facing proposal is being treated as implementation backlog;
- Web Search smoke/proven connectivity is being treated as rollout approval;
- OCR/VL OCR synthetic benchmark is being treated as production acceptance;
- provider setup is being started without approved data policy and explicit
  provider/account approval;
- runtime/config/provider action is implied by a docs-only document;
- expected output depends on real groups, real documents, provider policy,
  customer decisions or expected output samples that are missing.
