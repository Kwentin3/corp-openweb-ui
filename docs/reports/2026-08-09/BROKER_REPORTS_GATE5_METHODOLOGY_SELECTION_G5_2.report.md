# Broker Reports Gate 5 — Methodology-driven Financial Case selection (G5.2)

Status: `FINAL`

Goal status: `G5.2_CLOSED`

Proof outcome: `PROVEN`

Product status: `INACTIVE`

Date: 2026-08-09

Implementation commit: `2ebe04a89266f7cdca47e14913263bcc18ccab0c`

## Итог

Утверждение G5.2 доказано на одном минимальном сценарии:

> Внешняя машиночитаемая Tax Methodology может управлять тем, какие данные
> небольшой runtime собирает из существующего Financial Case, без переноса
> конкретной налоговой методики в Gate 4 и без tax-specific hardcode в control
> flow runtime.

Найденный минимальный seam:

```text
external requirements: financial_type + roles
-> Gate5MethodologySelectionRuntimeFactory(...).create()
-> Gate4FinancialCaseRuntimeFactory(...).create()
-> list_by_financial_type(...)
-> found / partial / missing + selected values
```

Gate 4 не изменён. Эксперимент не активирован как продуктовый Tax Engine.

## Проверяемый вопрос

Может ли небольшой runtime получить внешнее машиночитаемое требование и,
не имея заранее зашитого налогового сценария, выбрать по нему данные только
через официальный Gate 4 Financial Case boundary?

Критерий доказательства состоял из трёх наблюдений:

1. Требование перечисляет нужные финансовые типы и роли вне Python control
   flow.
2. Runtime использует это требование для обращения к существующему Financial
   Case.
3. Изменение только требования меняет набор и проекцию результата.

Все три наблюдения получены.

## Реализованный контрактный slice

Вход — закрытый JSON-compatible объект:

```json
{
  "schema_version": "broker_reports_gate5_methodology_requirements_v0",
  "requirements": [
    {
      "requirement_id": "disposal",
      "financial_type": "SECURITY_DISPOSAL",
      "roles": ["date", "asset", "quantity", "amount", "currency"]
    }
  ]
}
```

Runtime перебирает требования одинаковым способом и вызывает публичный Gate 4
query `list_by_financial_type`. Конкретные финансовые типы не участвуют в его
ветвлении.

Выход сохраняет исходное требование и сообщает по каждому пункту:

- `found` — факты найдены, все запрошенные роли присутствуют;
- `partial` — факты найдены, но хотя бы одна запрошенная роль отсутствует;
- `missing` — фактов запрошенного `financial_type` нет;
- `matches[].values` — только запрошенные значения;
- `matches[].missing_roles` — явный список отсутствующих ролей;
- `summary` — число требований по каждому статусу.

Полный экспериментальный контракт: [BROKER_REPORTS_GATE5_METHODOLOGY_SELECTION.v0.md](../../stage2/contracts/BROKER_REPORTS_GATE5_METHODOLOGY_SELECTION.v0.md).

## Representative proof

Синтетический Financial Case содержит:

- один `SECURITY_PURCHASE`;
- один `SECURITY_DISPOSAL`;
- ни одного `TRANSACTION_CHARGE`.

Один и тот же runtime был вызван с тремя вариантами внешнего требования:

| Вариант методологии | Что потребовано | Результат |
| --- | --- | --- |
| M1 | purchase и disposal, по пять ролей | `2 found`, `0 partial`, `0 missing` |
| M2 | M1 плюс transaction charge | `2 found`, `0 partial`, `1 missing` |
| M3 | только disposal: `amount`, `currency` | возвращены только `amount`, `currency` |

Для disposal в M1 получена структурированная проекция синтетического факта:

```json
{
  "date": "2026-02-11",
  "asset": "ACME",
  "quantity": "4",
  "amount": "60.00",
  "currency": "USD"
}
```

В M2 дополнительное требование вернулось как:

```json
{
  "requirement_id": "direct_charge",
  "financial_type": "TRANSACTION_CHARGE",
  "roles": ["date", "amount", "currency"],
  "status": "missing",
  "matches": []
}
```

В M3 код runtime не менялся, но `values` сузился до `amount` и `currency`.
Следовательно, состав выборки и её ролевая проекция действительно управляются
внешним требованием.

## Проверка архитектурной границы

Factory создаёт официальный
`Gate4FinancialCaseRuntimeFactory(store, read_enabled).create()`. Gate 5 runtime
использует только `list_by_financial_type` и не читает:

- broker reports;
- `CanonicalArtifactV1` через reader;
- Gate 3 targets;
- Gate 4 SQL;
- внутренние `read_case`, `list_facts` или `get_fact` обходы.

Антидрейф-тест разбирает исходник и отдельно подтверждает, что в runtime нет
литералов `SECURITY_PURCHASE`, `SECURITY_DISPOSAL`, `TRANSACTION_CHARGE` и иных
налогово значимых финансовых типов из проверяемого списка.

Это не доказывает универсальность для всех будущих налоговых задач. Это
доказывает ровно требуемое: для выбранного сценария налоговый смысл можно
оставить во внешнем требовании, а runtime сделать механическим.

## Fail-closed поведение

До выборки отклоняются:

- неизвестная версия schema;
- лишние или отсутствующие ключи;
- пустой список требований;
- пустые строки;
- повторяющиеся `requirement_id`;
- повторяющиеся роли.

Ошибки существующего Gate 4 для недопустимого financial type, отсутствующего
cache или stale upstream identity не маскируются и проходят наружу.

## KISS-проверка

Для доказательства добавлены:

- один маленький factory-backed runtime module;
- один минимальный закрытый вход;
- один минимальный структурированный выход;
- focused behavior и anti-drift tests;
- экспериментальный контракт и этот отчёт.

Не добавлены Tax Engine, rules DSL, generic query framework, relation layer,
новая БД, Repository/Service chain, workflow, LLM, Tax Model, supplemental
facts, методологический lifecycle или налоговая ontology.

## Evidence

Основные артефакты:

- [gate5_methodology_selection.py](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate5_methodology_selection.py) — runtime и factory;
- [test_broker_reports_gate5_methodology_selection.py](../../../services/broker-reports-gate1-proof/tests/test_broker_reports_gate5_methodology_selection.py) — representative case, изменение требований, closed input и anti-drift proof;
- [BROKER_REPORTS_ARCHITECTURE_AUTHORITIES.md](../../stage2/contracts/BROKER_REPORTS_ARCHITECTURE_AUTHORITIES.md) — маршрутизация экспериментального Gate 5 owner без изменения Gate 4 authority.

Проверка exact deliverable tree:

```text
python -m pytest -q \
  tests/test_broker_reports_gate_architecture.py \
  tests/test_broker_reports_gate4_financial_case_contract.py \
  tests/test_broker_reports_gate4_sql_materialization.py \
  tests/test_broker_reports_gate5_methodology_selection.py \
  tests/test_repository_privacy_guard.py --tb=short

60 passed
```

Дополнительно прошли CI-compatible Ruff, compileall, managed-generator checks,
bundle parity, Markdown link/UTF-8 checks, privacy scan и `git diff --check`.

## Ограничения и stop condition

Доказан только точный selector по `financial_type` и ролевая проекция. Не
доказаны asset/period filters, связи, joins, Boolean expressions, FIFO, cost
basis, расчёт налога, НКД, РЕПО, иностранные налоги и lifecycle методологии.

Конкретного upstream gap Gate 4 для representative case не обнаружено.

`G5.2_CLOSED`. Следующий Gate 5 slice этим отчётом не начинается и не
авторизуется.
