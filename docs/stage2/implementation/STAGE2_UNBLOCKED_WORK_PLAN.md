# Stage 2 Unblocked Work Plan

Статус: внутренний инженерный план. Не является production implementation и не
является техническим заданием для заказчика.

## 1. Назначение

Этот документ фиксирует работы Stage 2, которые можно выполнять сейчас без
нового согласования с заказчиком.

Цель - не менять runtime и не включать новые production-функции, а подготовить
структуру: сценарии, шаблоны, искусственные тестовые данные, планы проверок,
исследования и будущие решения.

Stage 2 остается сценарием развития OpenWebUI вокруг рабочих задач сотрудников:
группы, prompts/templates, Knowledge, документы, STT, Web Search, analytics и
governance. Это не список моделей и не обещание, что любой документ будет
обработан автоматически.

Словарь:

- `user story` - короткое описание задачи глазами пользователя.
- `synthetic data` - искусственные тестовые данные без данных заказчика.
- `proof` - проверка, что механизм реально работает.
- `benchmark` - сравнение вариантов по одним и тем же тестам.
- `VL OCR` - распознавание документа через зрительно-языковую модель.
- `analytics` - статистика использования.
- `gateway` - отдельный шлюз между OpenWebUI и провайдерами.

## 2. Границы

Можно делать без нового согласования:

- проектировать рабочие сценарии;
- готовить `user story` skeletons;
- готовить `synthetic data` index;
- делать research и `benchmark` на искусственных данных;
- готовить `proof` plans;
- актуализировать acceptance/test data docs;
- готовить ADR skeletons и decision notes.

Нельзя делать без заказчика:

- использовать реальные клиентские документы;
- менять production-политику;
- включать Web Search всем как промышленную функцию;
- утверждать data policy;
- подключать новых production-провайдеров;
- внедрять hard billing или `gateway`;
- открывать manager visibility;
- менять no-delete/retention policy.

Отдельная граница: synthetic proof может подтвердить механику, но не заменяет
production acceptance на реальных данных заказчика.

## 3. Работы, которые можно выполнять сейчас

### 3.1. Workspace scenario user stories

Цель:

- описать рабочие сценарии через понятные пользовательские задачи.

Что делаем:

- готовим список сценариев;
- фиксируем роль, входные данные, ожидаемый результат, prompts, Knowledge и
  acceptance signal;
- явно отмечаем, где нужны данные или решение заказчика.

Что не делаем:

- не описываем реальные бизнес-процессы заказчика как утвержденные;
- не создаем production-группы, модели, prompts или Knowledge на стенде.

Входные данные:

- PRD-1;
- native capability audit;
- runtime proof;
- текущие Stage 2 blueprints и backlog.

Ожидаемый результат:

- единый skeleton рабочих сценариев для будущего согласования.

Артефакт:

- [WORKSPACE_SCENARIO_USER_STORIES.md](WORKSPACE_SCENARIO_USER_STORIES.md).

Можно ли делать без заказчика:

- да, как черновую структуру.

Что потом нужно согласовать:

- реальные роли, группы, владельцев сценариев, данные и приоритеты.

Статус:

- ready for documentation / ready to start.

### 3.2. Synthetic test data pack

Цель:

- подготовить структуру искусственных тестовых данных для независимых проверок.

Что делаем:

- описываем нужные типы synthetic data;
- связываем каждый тип с user stories и proof/benchmark задачами;
- фиксируем, что именно такие данные могут и не могут доказать.

Что не делаем:

- не используем реальные документы, имена, реквизиты, private URLs или customer
  data;
- не создаем большой набор файлов, если достаточно индекса.

Входные данные:

- acceptance matrix;
- test data requirements;
- документы по OCR, Web Search, analytics и native capability audit.

Ожидаемый результат:

- понятный список искусственных данных, с которого можно начать proof work.

Артефакт:

- [SYNTHETIC_TEST_DATA_INDEX.md](../testdata/SYNTHETIC_TEST_DATA_INDEX.md).

Можно ли делать без заказчика:

- да.

Что потом нужно согласовать:

- реальные customer samples для production acceptance.

Статус:

- ready to start.

### 3.3. Usage analytics proof

Цель:

- проверить, достаточно ли native analytics для базовой видимости использования.

Что делаем:

- готовим proof plan по разрезам: пользователь, день/неделя, модель, токены,
  сообщения и примерная стоимость;
- описываем ожидаемые поля и ограничения;
- отделяем basic analytics от hard billing.

Что не делаем:

- не внедряем gateway;
- не обещаем hard budgets или guaranteed blocking;
- не читаем и не публикуем реальные счета/ключи.

Входные данные:

- usage analytics research;
- native capability audit;
- runtime proof;
- provider/model catalog draft.

Ожидаемый результат:

- план проверки native analytics и список gaps для ADR-0008.

Артефакт:

- proof plan или ADR-0008 decision note.

Можно ли делать без заказчика:

- да, на synthetic usage и без customer data.

Что потом нужно согласовать:

- нужна ли детализация по отделам;
- достаточно ли наблюдаемости или нужен hard billing/gateway.

Статус:

- next independent proof.

### 3.4. VL OCR candidate research + synthetic benchmark

Цель:

- начать сравнение OCR/VL OCR кандидатов без ожидания реальных документов.

Что делаем:

- уточняем candidate shortlist;
- готовим benchmark matrix на synthetic scans, fake forms and table-like
  images;
- фиксируем критерии сравнения: русский текст, таблицы, layout, cost, latency,
  privacy fit.

Что не делаем:

- не отправляем реальные документы заказчика внешним провайдерам;
- не принимаем production OCR decision;
- не заявляем качество на брокерских отчетах.

Входные данные:

- VL OCR provider research;
- documents/OCR/Excel research;
- synthetic data index.

Ожидаемый результат:

- готовый план synthetic benchmark и shortlist для будущего customer pilot.

Артефакт:

- VL OCR benchmark plan или ADR-0005 update.

Можно ли делать без заказчика:

- да, для research и synthetic benchmark.

Что потом нужно согласовать:

- customer samples;
- allowed provider class;
- можно ли использовать зарубежные/RU/cloud OCR providers.

Статус:

- ready for research/benchmark; customer OCR pilot remains blocked by real
  documents.

### 3.5. Simple PDF/DOCX/XLSX synthetic extraction proof

Цель:

- проверить механику простого извлечения документов на искусственных файлах.

Что делаем:

- готовим simple_text_pdf, structured_docx_with_table и simple_xlsx_table;
- проверяем upload/extraction mechanics и visible limitations;
- фиксируем, где нужна отдельная parser/OCR decision.

Что не делаем:

- не проверяем качество на реальных отчетах;
- не обещаем корректность сложного Excel;
- не делаем production document pipeline.

Входные данные:

- synthetic test data index;
- documents/OCR/Excel research;
- acceptance matrix.

Ожидаемый результат:

- mechanical proof plan для простых документов.

Артефакт:

- simple document extraction proof plan.

Можно ли делать без заказчика:

- да, после synthetic data index.

Что потом нужно согласовать:

- реальные PDF/DOCX/XLSX samples и expected outputs.

Статус:

- ready after synthetic data index.

### 3.6. Configuration-first scenario proof

Цель:

- доказать, что рабочий сценарий можно собрать штатными средствами OpenWebUI.

Что делаем:

- проектируем proof через group, Workspace Model, prompt, Knowledge и access;
- используем synthetic сценарий и synthetic Knowledge;
- описываем actor matrix без production изменений.

Что не делаем:

- не создаем реальные customer-группы;
- не используем реальные документы;
- не меняем глобальные defaults без отдельного approval.

Входные данные:

- native capability audit;
- workspace scenario user stories;
- synthetic test data index.

Ожидаемый результат:

- reusable proof plan для configuration-first сценария.

Артефакт:

- configuration-first scenario proof plan.

Можно ли делать без заказчика:

- да, как план и synthetic proof, если отдельный runtime proof будет разрешен.

Что потом нужно согласовать:

- реальные группы, роли, владельцы и policies.

Статус:

- ready after user stories and synthetic data.

### 3.7. Web Search safe comparison matrix

Цель:

- подготовить безопасную матрицу сравнения Web Search путей.

Что делаем:

- описываем safe RU/EN queries, freshness cases, conflicting-source cases и
  no-sufficient-evidence cases;
- связываем matrix с Brave, Yandex and private SearXNG comparison track;
- фиксируем forbidden query examples.

Что не делаем:

- не включаем Web Search всем как production rollout;
- не используем customer/private queries;
- не считаем SearXNG полной privacy-защитой.

Входные данные:

- Web Search context index;
- candidate set comparison plan;
- acceptance matrix;
- test data requirements.

Ожидаемый результат:

- safe comparison matrix для будущего proof.

Артефакт:

- Web Search query matrix / proof plan update.

Можно ли делать без заказчика:

- да, для безопасных synthetic/ordinary queries.

Что потом нужно согласовать:

- rollout scope, allowed data classes, logs, cost policy and group defaults.

Статус:

- ready to document; runtime rollout remains policy-gated.

### 3.8. STT hardening/regression pack

Цель:

- подготовить regression checklist для уже закрытого текущего STT MVP path.

Что делаем:

- фиксируем mobile, large file, low-memory browser, cancel, retention and
  transcript workflow checks;
- не перепланируем STT from zero.

Что не делаем:

- не меняем sidecar architecture;
- не добавляем отдельный user-facing STT GUI;
- не запускаем smoke без разрешения.

Входные данные:

- STT MVP closure reports;
- ADR-0004;
- STT media input normalization contract.

Ожидаемый результат:

- hardening/regression checklist для будущей проверки.

Артефакт:

- STT hardening checklist or ADR-0004 follow-up note.

Можно ли делать без заказчика:

- да, как documentation checklist.

Что потом нужно согласовать:

- customer media samples, retention, limits and production policy.

Статус:

- ready to document; customer/large/mobile proof data later.

### 3.9. Provider/model catalog skeleton

Цель:

- подготовить skeleton каталога моделей без подключения новых production
  providers.

Что делаем:

- фиксируем поля каталога: provider class, exact model ID, use case, status,
  data policy, cost, limit, owner decision;
- отделяем production, pilot, research and rejected labels.

Что не делаем:

- не подключаем новые keys/accounts;
- не утверждаем provider data policy;
- не заменяем ADR-0006.

Входные данные:

- provider research;
- PRD-1;
- data policy ADR skeleton.

Ожидаемый результат:

- skeleton для ADR-0006 и будущего admin handoff.

Артефакт:

- provider/model catalog skeleton.

Можно ли делать без заказчика:

- да, как черновой формат.

Что потом нужно согласовать:

- exact accounts, allowed providers and data classes.

Статус:

- ready to document; production setup blocked by customer decision.

### 3.10. Data policy draft matrix

Цель:

- подготовить черновую матрицу классов данных и классов провайдеров.

Что делаем:

- описываем foreign, Russian, local/self-hosted and future masked/tokenized
  paths;
- собираем allowed/prohibited examples;
- фиксируем вопросы к заказчику.

Что не делаем:

- не утверждаем финальную policy;
- не обещаем automatic masking;
- не подключаем providers.

Входные данные:

- ADR-0001;
- security/data policy blueprint;
- customer governance proposal.

Ожидаемый результат:

- readable draft для согласования.

Артефакт:

- data policy draft matrix или ADR-0001 update.

Можно ли делать без заказчика:

- да, как draft.

Что потом нужно согласовать:

- реальные allowed/prohibited examples and owner approval.

Статус:

- ready to document; final policy blocked by customer approval.

### 3.11. Customer test data intake package

Цель:

- подготовить пакет запроса данных у заказчика.

Что делаем:

- структурируем список нужных файлов и expected outputs;
- разделяем broker reports, OCR scans, XLSX, media, groups, provider policy and
  cost examples;
- добавляем правила safe intake.

Что не делаем:

- не получаем и не храним реальные документы в этом задании;
- не просим секреты, keys, private URLs or credentials.

Входные данные:

- test data requirements;
- acceptance matrix;
- synthetic data index.

Ожидаемый результат:

- clear checklist for customer data intake.

Артефакт:

- customer test data intake checklist.

Можно ли делать без заказчика:

- да, как checklist.

Что потом нужно согласовать:

- сами файлы, legal/data policy and secure transfer method.

Статус:

- ready to document; data itself blocked by customer.

### 3.12. ADR skeletons / decision notes

Цель:

- подготовить decision structure до реализации.

Что делаем:

- готовим skeletons или updates для ADR-0001...ADR-0008;
- отмечаем decision owner, options, risks, proof needed and deferred work.

Что не делаем:

- не принимаем решения за заказчика;
- не смешиваем future slices с Practical Stage 2.

Входные данные:

- roadmap;
- implementation gates;
- current backlog.

Ожидаемый результат:

- ADR/decision notes ready for review.

Артефакт:

- ADR skeletons / decision notes.

Можно ли делать без заказчика:

- да, как drafts.

Что потом нужно согласовать:

- approval/status of each ADR and production scope.

Статус:

- ready to draft.

## 4. Рекомендуемый порядок выполнения

1. User stories.
2. Synthetic test data index.
3. Usage analytics proof plan.
4. VL OCR synthetic benchmark plan.
5. Simple document extraction proof plan.
6. Configuration-first scenario proof plan.
7. Остальные треки после этого.

Такой порядок сначала задает сценарии и безопасные данные, а потом уже строит
proof/benchmark вокруг них.

## 5. Связь с PRD-1

План следует PRD-1: Stage 2 строится вокруг рабочих сценариев, а не вокруг
хаотичного списка моделей.

Связанные PRD-1 домены:

- рабочие сценарии и группы;
- prompts/templates;
- Knowledge;
- документы и OCR/VL OCR;
- STT;
- Web Search;
- analytics and cost visibility;
- provider/data governance.

План не меняет PRD-1 и не закрывает customer gates. Он подготавливает
артефакты, которые позволяют двигаться без ожидания реальных клиентских данных.

## 6. Связь с customer decisions

Следующие работы позже упираются в решения заказчика:

- реальные группы и роли;
- реальные документы и expected outputs;
- provider/data policy;
- no-delete/retention;
- manager visibility;
- Web Search rollout;
- hard billing/gateway.

До этих решений допускаются только internal docs, synthetic data, drafts,
research, benchmark plans and proof plans.

## 7. Ссылки

- [PRD-1](../../prd/OPENWEBUI_CORPORATE_CHAT_PRD_1.md)
- [Customer runtime decisions](../proposals/CUSTOMER_STAGE2_RUNTIME_DECISIONS.md)
- [OpenWebUI Admin/Test-User Runtime Proof](../../reports/2026-06-24/OPENWEBUI_ADMIN_TEST_USER_RUNTIME_PROOF.report.md)
- [OpenWebUI Native Capability Audit](OPENWEBUI_NATIVE_CAPABILITY_AUDIT.md)
- [Acceptance Matrix](../acceptance/ACCEPTANCE_MATRIX.md)
- [Test Data Requirements](../acceptance/TEST_DATA_REQUIREMENTS.md)
- [Engineering Backlog](../ENGINEERING_BACKLOG.md)
- [Implementation Gates](../IMPLEMENTATION_GATES.md)
- [Workspace Scenario User Stories](WORKSPACE_SCENARIO_USER_STORIES.md)
- [Synthetic Test Data Index](../testdata/SYNTHETIC_TEST_DATA_INDEX.md)
