# Stage 2 Scenario Shortlist

Дата: 2026-06-25

Статус: внутренний draft для отбора первых Stage 2 user stories. Shortlist -
короткий список сценариев-кандидатов. Это не финальный состав работ, не
proof-plan и не production-инструкция.

`Use case` - сценарий использования. `User story` - описание задачи глазами
пользователя. `Workspace` - рабочая зона с моделью, правилами, шаблонами и
доступами. `Knowledge` - база знаний или набор подключенных материалов. `RAG` -
поиск ответа с опорой на документы. `VL OCR` - распознавание документа через
зрительно-языковую модель. `Analytics` - статистика использования.
`Governance` - правила управления: доступы, ограничения, безопасность,
стоимость.

## 1. Research Base

Shortlist основан на уже выполненном research:

- [Corporate AI Workspace Use Cases Research](../research/CORPORATE_AI_WORKSPACE_USE_CASES_RESEARCH.md)
- [Corporate AI Use Case Research Report](../../reports/2026-06-25/OPENWEBUI_CORPORATE_AI_USE_CASE_RESEARCH.report.md)
- [PRD-1](../../prd/OPENWEBUI_CORPORATE_CHAT_PRD_1.md)
- [Customer summary](../../prd/OPENWEBUI_CORPORATE_CHAT_PRD_1_CUSTOMER_SUMMARY.md)
- [Stage 2 Unblocked Work Plan](STAGE2_UNBLOCKED_WORK_PLAN.md)
- [Acceptance Matrix](../acceptance/ACCEPTANCE_MATRIX.md)
- [Synthetic Test Data Index](../testdata/SYNTHETIC_TEST_DATA_INDEX.md)

Опорные факты из research:

- Корпоративные AI-сценарии повторяются вокруг обычной работы: черновики,
  встречи, документы, внутренний поиск по знаниям, внешний поиск, поддержка,
  продажи, разработка, аналитика использования и правила управления.
- Для Stage 2 наиболее подходят управляемые workspace-сценарии: модель,
  доступы, prompts/templates, Knowledge, предупреждения, source visibility,
  analytics и data policy.
- Synthetic data может проверять механику и форму сценария, но не качество на
  реальных документах заказчика.
- Basic analytics отличается от hard billing: видимость использования не равна
  принудительным бюджетам и блокировкам.

Аналитические гипотезы, не доказанные как customer fact:

- Заказчику будет полезнее начинать не с 14 категорий, а с 5-7 управляемых
  сценариев, потому что PRD-1 требует минимум повторяемых рабочих процессов.
- Broker reports / 3-НДФЛ имеют высокий приоритет, но пока хуже подходят для
  первых user stories без реальных отчетов и expected output.
- Sales/marketing, HR, support and Dev/IT support могут быть ценными позже, но
  сейчас уступают сценариям, уже связанным с PRD-1 и unblocked work plan.

## 2. Критерии отбора

Сценарий попадает в первый shortlist, если он:

- повторяется в external research;
- согласуется с PRD-1 и Stage 2 acceptance;
- может быть описан как управляемый workspace, а не разовая функция;
- дает работу, которую можно двигать docs-only без customer data;
- явно отделяет synthetic mechanics от customer acceptance;
- не требует hard gateway, production OCR pipeline, deep fork или full AD
  lifecycle как обязательного первого шага.

## 3. Выбранный shortlist

| # | Scenario | Why selected | Corporate value | Repetition in sources | Can move now | Later customer decisions | Main risks |
| - | -------- | ------------ | --------------- | --------------------- | ------------ | ------------------------ | ---------- |
| 1 | Общий управляемый AI-чат | Базовый вход в controlled workspace, prompts and data policy. | Быстрые черновики, summary, rewrite, единые правила. | High | Да, на synthetic prompts. | Реальные группы, allowed/prohibited data, provider policy. | Утечка данных, ложная уверенность, BYOAI drift. |
| 2 | Встречи / транскрибация / action items | Уже есть STT track; research подтверждает ценность meeting assistants. | Протоколы, решения, задачи, follow-up. | High | Да, через fake transcript и templates. | Реальные media, consent, retention, доступ к transcript. | Персональные данные, неверное резюме, хранение аудио/текста. |
| 3 | Внутренний Knowledge / RAG | Центральный workspace-паттерн: ответ с опорой на документы. | Быстрый поиск по policy, инструкциям, методичкам. | High | Да, на synthetic Knowledge. | Реальная база знаний, владельцы, права доступа, refresh policy. | Устаревшие документы, oversharing, prompt injection, нет источников. |
| 4 | PDF/DOCX document assistant | PRD-1 требует базовую работу с документами без обещания production OCR. | Быстрый разбор простых документов и договоров. | High | Да, на synthetic PDF/DOCX. | Реальные документы, expected outputs, allowed provider class. | Потеря структуры, legal/tax hallucination, неполный extraction. |
| 5 | Web Search / внешние исследования | Есть Stage 2 provider comparison and source-attribution track. | Публичный research с источниками и контролем query policy. | High | Да, через safe public queries. | Rollout scope, logs, cost, allowed data, group defaults. | Private queries, слабые источники, provider leakage, cost. |
| 6 | Usage analytics / отчет по токенам | PRD-1 требует basic analytics/cost visibility; hard billing отделен. | Админ видит нагрузку, модели, токены, примерную стоимость. | High | Да, через report shape. | Нужная детализация, privacy level, hard billing decision. | Подмена analytics биллингом, неполная стоимость, user-level privacy. |
| 7 | OCR / VL OCR candidate benchmark | OCR pilot важен, но production quality customer-blocked. | Ранний отбор candidates для сканов и сложных PDF без реальных данных. | High | Да, только как synthetic candidate story. | Реальные scans, provider/data approval, expected good output. | OCR hallucination, неверные таблицы, privacy, cost, auditability. |

## 4. Не вошли в первый shortlist, но остаются важными

| Scenario | Decision | Why |
| -------- | -------- | --- |
| Broker reports / 3-НДФЛ | Customer-blocked priority | Высокая ценность, но нельзя писать полноценные first stories без реальных отчетов, good-result example and financial data policy. |
| Customer support | Later candidate | Повторяется в research, но нет текущего customer support process в PRD-1 как приоритета. |
| Sales/marketing | Later candidate | Хороший prompt/Web Search workspace, но не первее PRD-1 ядра, STT, docs, Web Search and analytics. |
| HR/onboarding | Later candidate | Полезно, но HR data sensitive; нужен отдельный policy stance. |
| Dev/IT support | Later/future | Ценный enterprise сценарий, но не текущий business focus Stage 2. |
| Hard billing/gateway | Future slice | Требует gateway architecture; native analytics first. |
| Complex Excel parser | Future slice | Формулы, сводные таблицы, внешние ссылки требуют отдельного parser/tool path. |
| Production OCR/layout pipeline | Future slice | Нужны queue, validation UI, audit and human review after pilot. |
| Full data masking/tokenization | Future slice | Нужен защищенный контур, entity detection, mapping store and reverse substitution. |
| Full AD lifecycle / SCIM | Future slice | Не является базовым requirement Practical Stage 2. |
| Deep OpenWebUI fork | Future slice | Только если native/configuration/integration path доказанно недостаточен. |
| Autonomous agent actions in 1C/CRM | Future/non-goal | Не входит в Practical Stage 2; требует отдельной safety architecture. |

## 5. Корзины

### Basket A. Можно двигать сейчас без заказчика

Это draft/user-story/design работа без runtime changes, customer data and
production resources.

| Scenario part | Current action |
| ------------- | -------------- |
| Общий AI-чат | Описать safe summary/rewrite stories, prompts/templates, data warning. |
| Meeting transcript flow | Описать stories для fake transcript: summary, action items, follow-up. |
| Synthetic Knowledge mechanics | Описать question-with-sources and no-source behavior. |
| PDF/DOCX mechanics | Описать simple document summary/risk-question stories on synthetic docs. |
| Web Search safe matrix | Описать public research and sensitive-query block behavior. |
| Usage analytics report shape | Описать нужные поля отчета: user, period, model, tokens, messages, approx cost. |
| OCR/VL OCR candidate story | Описать candidate-comparison story without executing benchmark. |

### Basket B. Нужен заказчик

Эти части нельзя закрывать как acceptance без customer/admin/security decisions.

| Dependency | Needed for |
| ---------- | ---------- |
| Реальные группы, роли, владельцы | Workspace access, manager visibility, scenario ownership. |
| Customer Knowledge | Production RAG relevance and permissions. |
| Реальные broker reports / 3-НДФЛ | Financial/tax pilot and expected output. |
| Реальные scans, PDF tables, XLSX | OCR/VL OCR quality and document classification. |
| Real meeting media and consent policy | STT production acceptance. |
| Provider/data policy | External providers, OCR providers, Web Search, financial docs. |
| Web Search rollout policy | Global/group scope, allowed query classes, logs, cost. |
| No-delete / retention / manager visibility | Chat lifecycle and privacy controls. |
| Hard billing requirement | Gateway or native analytics sufficiency decision. |

### Basket C. Отложить / future slice

| Future slice | Reason |
| ------------ | ------ |
| Hard billing/gateway | Нужны virtual keys, budgets, rate limits and routing architecture. |
| Complex Excel parser | Нужен отдельный parser/tool path, не generic LLM answer. |
| Production OCR/layout pipeline | Pilot first; production needs queue, validation and audit. |
| Full data masking/tokenization | Requires trusted subsystem and mapping store. |
| Full AD lifecycle / SCIM | Optional identity slice, not Practical Stage 2 base. |
| Deep OpenWebUI fork | Only after native/configuration/integration paths fail with proof. |
| Production DOCX/XLSX generation | Needs approved templates, export controls and review. |
| Autonomous agent actions in 1C/CRM | Outside current safe workspace scope. |

## 6. Опасные иллюзии

- "Synthetic data proves customer quality" - no, it proves only mechanics and
  shape.
- "RAG solves knowledge automatically" - no, source quality, extraction,
  access and freshness remain work.
- "OCR reads everything" - no, scans, tables, handwriting, stamps and layout
  need classification and manual review.
- "AI correctly handles any Excel" - no, complex Excel is a future parser/tool
  decision.
- "Native analytics is billing" - no, billing enforcement is a gateway-level
  future decision.
- "Manager visibility means admin sees everything" - no, this needs approved
  work-chat visibility policy.
- "Web Search is safe because the query is public-looking" - no, internal
  context in the query can still leak.

## 7. Выход в user stories

User stories for this shortlist are maintained in:

- [Workspace Scenario User Stories](WORKSPACE_SCENARIO_USER_STORIES.md)

The current story set is intentionally limited to the seven selected scenarios.
It does not cover all research categories and does not claim final customer
scope.
