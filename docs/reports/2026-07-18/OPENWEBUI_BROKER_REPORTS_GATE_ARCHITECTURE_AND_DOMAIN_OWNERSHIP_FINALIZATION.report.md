# Broker Reports: финализация архитектуры ворот и владения доменами

Дата: 2026-07-18

Статус: финальный архитектурный отчёт

Нормативная карта:
[Broker Reports Global Gate Architecture](../../stage2/blueprints/BROKER_REPORTS_GATE_ARCHITECTURE.md).

## Короткий вывод

Для Broker Reports зафиксирована одна глобальная продуктовая последовательность
из четырёх ворот:

1. Gate 1 — приём и сохранение представления источника.
2. Gate 2 — локальная для источника финансовая интерпретация.
3. Gate 3 — сборка кейса, междокументная сверка и детерминированные финансовые
   расчёты.
4. Gate 4 — налоговая методология, декларационная модель, проверка и выходные
   материалы.

Это разделение соответствует уже существующим данным и runtime-границам.
Runtime переносить или переименовывать не потребовалось.

Финансовая интерпретация начинается в Gate 2. Междокументное доменное мышление
начинается в Gate 3. Налоговые решения и подготовка декларации принадлежат
Gate 4.

## Схема простыми словами

```text
файл
  -> Gate 1: что физически и структурно есть в источнике
  -> Gate 2: что означает один ограниченный фрагмент источника
  -> broker_reports_gate3_context_manifest_v0
  -> Gate 3: как факты разных фрагментов/документов образуют один кейс
  -> Gate 4: как принятый кейс отражается в налоговой модели и выходе
```

## Авторитетная последовательность

| Gate | Вход | Выход | Запрещённый переход | Текущий статус |
| --- | --- | --- | --- | --- |
| 1. Source Intake and Representation Normalization | Авторизованные file refs/bytes | Нормализованные source artifacts, issue context, `domain_context_packet_v0` | Нельзя назначать финансовый смысл | Реализован; частично закрыт по форматам |
| 2. Source-Local Semantic Interpretation | DCP и resolver-доступные артефакты Gate 1 | Проверенные source facts, validation/stitch, Gate 3 input manifest | Нельзя объединять документы, строить ledger или решать налог | Реализован; закрыт только для явно bounded scopes |
| 3. Case Assembly and Deterministic Reconciliation | Один ready `broker_reports_gate3_context_manifest_v0` | Сверенные события, конфликты, ledgers и calculation traces | Нельзя принимать налоговую/декларационную трактовку | Runtime не начат; контракты proposal |
| 4. Tax and Declaration Output Preparation | Принятый Gate 3 case/ledger root и методология | Declaration model, review state, контролируемый output | Нельзя переписывать source truth или автоматически заявлять filing readiness | Draft/proposal; runtime не начат |

Нормализация заканчивается в Gate 1. Механическое преобразование числа/даты
разрешено, только если оно воспроизводится из source value. Назначение типа
`income`, `withholding_tax`, `trade_operation` и других финансовых ролей уже
является Gate 2.

## Роль broker_reports_gate3_context_manifest_v0

Манифест:

- создаётся и валидируется на выходе Gate 2;
- является единственным поддержанным корнем входа Gate 3 для объявленного
  ready scope;
- хранит refs, counts, identities, coverage, issue context, retention и
  restrictions, но не копирует строки, ячейки или финансовые значения;
- детерминированно пересчитывает `gate3_input_status` по сохранённому графу;
- игнорирует исторический `gate3_handoff_ready` как источник истины;
- не является ledger, результатом Gate 3, готовностью всего документа или
  всего кейса.

Текущий v0 manifest дополнительно запрещает cross-document reconciliation,
duplicate resolution, tax, declaration и XLS/XLSX для своего доказанного
bounded CSV contour. Владение Gate 3 этими будущими обязанностями не отменяет
ограничения конкретного manifest. Расширение требует нового явного input
contract/scope, а не скрытой интерпретации существующего флага.

## Матрица владения

| Семейство | Владелец | Роль/доступ | Статус |
| --- | --- | --- | --- |
| Gate 1 OpenWebUI Function и format normalizers | Gate 1 | Runtime; private source + safe report | Implemented/deployed |
| PDF Table Intake Gate 1 | Локальный child Gate 1 | PDF -> private raster refs, без cells/finance | Closed |
| Normalized text/table/source contracts | Gate 1 | Нормативное представление источника; private | Implemented для поддержанных путей |
| DCP и issue ledger | Gate 1 | Safe-internal handoff/context; downstream by ref | Implemented |
| Gate 2 source/domain Functions | Gate 2 | Runtime source-local interpretation | Implemented/deployed |
| Candidate binding, source facts, validation, stitching | Gate 2 | Private facts + safe terminal evidence | Implemented; bounded stage proof |
| `broker_reports_gate3_context_manifest_v0` | Gate 2 exit / Gate 3 input | Safe-internal checked index | Implemented; bounded CSV stage-proven |
| Intermediate ledgers/reconciliation | Gate 3 | Future private case assembly | Proposal; not implemented |
| Declaration model/review/output | Gate 4 | Future private tax/declaration layer | Draft/proposal; not implemented |
| ArtifactStore/resolver/retention/purge | Cross-cutting platform | Механика хранения, доступа и lifecycle; без бизнес-смысла | Implemented |
| Provider registry/adapters/model client factory | Cross-cutting platform с Gate 2 policy contracts | Transport/schema projection; не принимает бизнес-результат | Implemented/deployed |
| Managed prompts | Gate 1 или Gate 2 по задаче; registry delivery — platform | Model proposal only; validator authority unchanged | Implemented/deployed |
| Bundle/parity/operator tooling | Cross-cutting delivery | Operations/evidence only | Implemented |
| Research/closure reports | Evidence | Не переопределяют contracts/architecture | Preserved |

Компоненты, пересекающие границы, пересекают их намеренно:

- DCP принадлежит Gate 1 и читается Gate 2;
- normalized artifacts принадлежат Gate 1 и читаются Gate 2;
- issue ledger принадлежит Gate 1 и переносится дальше только refs;
- Gate 3 context manifest производится на выходе Gate 2 и читается Gate 3;
- ArtifactStore, resolver, retention и provider transport являются платформой,
  а не дополнительными бизнес-воротами.

## Поток артефактов

```text
[Gate 1 private]
source bytes -> normalized payload/unit/table
        |
        +-> [Gate 1 safe] DCP + issue/eligibility refs
                            |
                            v
[Gate 2 private]
bounded package -> raw model output -> validated source facts
        |
        +-> [Gate 2 safe] validation + stitch + terminal summary
                            |
                            v
[Gate 2 safe root / Gate 3 input]
broker_reports_gate3_context_manifest_v0
                            |
                            v
[Gate 3 future private]
case relations -> reconciliation -> ledgers -> deterministic traces
                            |
                            v
[Gate 4 future private]
tax methodology -> declaration model -> review -> controlled output
```

Все private descendants разрешаются через ArtifactResolver. Scope расширяется
новым terminal run и новым immutable root, а не мутацией готового manifest.

## Текущая карта готовности

| Возможность | Статус | Что доказано | Что не доказано |
| --- | --- | --- | --- |
| Global Gate 1 | Implemented; partially closed | Runtime и format-specific контуры | Универсальная поддержка форматов |
| CSV v1 normalization | Closed for bounded supported profile | Полная нормализация принятого CSV под limits | Любой/unlimited CSV |
| PDF Table Intake local Gate 1 | Closed | Region detection и private raster candidates | Canonical cells/table JSON или finance |
| Canonical PDF table reconstruction | Research only/open | История экспериментов | Product acceptance |
| Global Gate 2 | Implemented; partially closed | Bounded typed source-fact paths | Whole-document/full-corpus/all-format coverage |
| CSV pre-Gate-3 vertical | Closed for bounded scope | Один selected segment terminal/validated; 343 deferred | Весь CSV семантически обработан |
| Gate 3 context manifest | Implemented; stage proven | Declared bounded Gate 2 graph ready | Ledger/case/tax readiness |
| Global Gate 3 business runtime | Not started | Proposal contracts only | Reconciliation/ledger/calculations |
| Global Gate 4 | Not started | Draft/proposal contracts only | Tax/declaration/review/export runtime |

Текущий CSV результат поэтому формулируется строго:

- complete CSV v1 normalization — да;
- bounded source-fact extraction — да;
- whole-document semantic coverage — нет;
- ready bounded manifest для Gate 3 — да;
- Gate 3 business logic — нет.

## Терминология и совместимость

| Историческое имя | Канонический смысл | Решение |
| --- | --- | --- |
| Stage 2 Gate 1..9 | Общие governance/implementation conditions | Сохранено; отделено ссылкой от product gates |
| Gate 1.5 | LLM metadata-passport sub-stage внутри global Gate 1 | Сохранено как compatibility alias |
| PDF Table Intake Gate 1 | Локальный `PDF -> raster candidates` child global Gate 1 | Сохранено без rename |
| `gate2_handoff_v0` / Gate 2 handoff | Выход Gate 1 и вход Gate 2 | Не означает завершение Gate 2 |
| CSV pre-Gate-3 vertical | Вертикальный proof через Gate 1 + bounded Gate 2 + manifest | Не является Gate 3 closure |
| `broker_reports_gate3_context_manifest_v0` | Gate 2 exit / Gate 3 input | Versioned name сохранено |
| `gate3_handoff_ready` | Legacy local hint | Поле совместимости; не authority |
| `STAGE2_GATE2_ARCHITECTURE_CLOSURE_READY` | Исторический architecture/proof marker | Не global product acceptance |
| `gate3_ledger_candidate` | Downstream hint/restriction | Не ledger item и не Gate 3 decision |

Деструктивных rename и параллельной нумерации не добавлено.

## Найденные несогласованности и исправления

Исправлено:

- Gate 2 blueprint раньше складывал Gate 3 ledgers, methodology, tax,
  declaration и XLS/XLSX в один владелец; теперь Gate 3 и Gate 4 разделены;
- `Gate 1.5` встречался как будто отдельный глобальный этап; теперь это явно
  compatibility sub-stage внутри Gate 1;
- contract-family flow начинался с case/document inventory и не показывал
  нормализованное представление и Gate 3 input manifest;
- flow mapping допускал прямой source-fact -> declaration переход; теперь
  lineage разрешён только внутри Gate 4 через принятый Gate 3 scope/root;
- Gate 2 handoff описывался набором refs без единого current root; для
  поддержанного ready scope закреплён manifest v0;
- общий 3NDFL blueprint называл customer pilot «отдельным gate»; теперь это
  acceptance milestone, не новый номер;
- Stage 2 implementation gates получили прямую ссылку на отдельную product
  architecture;
- maintained navigation теперь начинает Broker Reports с одной канонической
  карты.

Не изменялось:

- runtime behavior;
- deployed Function bundles;
- validators и completeness;
- versioned artifact names/shapes;
- accepted PDF Table Intake closure;
- Gate 3/Gate 4 business functionality;
- research history.

## Что уже закрыто и что открыто

Закрыто:

- локальный PDF Table Intake Gate 1 в принятом bounded scope;
- CSV v1 normalization для поддержанного профиля;
- CSV pre-Gate-3 vertical для одного declared bounded segment;
- manifest factory/validator, access, retention и zero-loss проверки для этого
  scope;
- repository/live parity текущих Gate 1/Gate 2 bundles и managed prompts.

Открыто:

- общая format coverage Gate 1, включая OCR/image-only;
- canonical PDF table reconstruction;
- whole-document/full-corpus/all-format Gate 2 semantic coverage;
- Gate 3 case assembly, cross-document reconciliation и ledgers;
- Gate 4 tax methodology, declaration review и export.

## Проверка repository/runtime alignment

На 2026-07-18 выполнен read-only full-scope verifier:

- все три Function bundles: repo SHA-256 = live SHA-256;
- 12/12 managed prompts: content/metadata/version/command parity;
- provider registry/profile/model namespaces: match;
- repository factory boundary: passed;
- итоговый status: `passed`.

Текущий repository `HEAD=fc5966b` — docs-only follow-up. Последняя
runtime-affecting revision — `0f1aa5c`. В рамках этой финализации изменялись
только Markdown-документы; stage delivery не требовался.

Локальный service suite из канонического cwd
`services/broker-reports-gate1-proof`:

```text
python -m unittest discover -s tests -v
Ran 704 tests
OK
```

Дополнительно:

- `git diff --check` — passed;
- 26 изменённых/новых Markdown-файлов проверены на относительные ссылки:
  missing = 0;
- non-Markdown diff: 0.

## Следующая цель

Рекомендуемое имя:

```text
Broker Reports Global Gate 3 — Bounded Case Assembly and Intermediate Ledger v0
```

Владелец: global Gate 3.

Первый slice должен принять один ready manifest, не выходить за его declared
scope/restrictions, построить traceable bounded ledger/case-assembly artifact и
остановиться до tax methodology, declaration mapping и export.

## Обязательный финальный статус

```text
BROKER_REPORTS_GATE_ARCHITECTURE:
FINALIZED

DOMAIN_OWNERSHIP:
CONSISTENT

LOCAL_GLOBAL_GATE_TERMINOLOGY:
RECONCILED

DOCUMENTATION_RUNTIME_ALIGNMENT:
PROVEN

FUTURE_GATE_ASSIGNMENT_MODEL:
READY
```
