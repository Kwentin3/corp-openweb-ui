# Broker Reports — Gate 2 Stage Necessity And Topology Audit

Дата: 2026-07-25  
Статус: `GOAL_3_STAGE_NECESSITY: COMPLETED`

## Однозначный ответ

Отдельные source LLM и domain LLM не нужны. Нужен один bounded semantic decision call, и он уже существует как financial-evidence decision. Рекомендуемая topology — вариант D:

```text
Gate 1 evidence
  → deterministic segmentation/router/package scopes
  → existing Financial Evidence decision LLM
  → deterministic materialization
  → source-bound Gate 2 financial context
```

Это не означает немедленное удаление legacy stages. Это целевая архитектура и предмет отдельного implementation/qualification program.

## Проверка уникальной работы stages

### Source LLM

Gate 1 уже даёт:

- literal values и их точное написание;
- source refs/source-value refs;
- page/table/row/cell/text provenance;
- source-unit kind и coverage scope.

Source runtime добавляет главным образом legacy representation. Compact selection refactor уже показал, что IDs, normalized structures, provenance, audit, restrictions и coverage достраиваются кодом. Уникальной source-LLM способности, которая нужна financial context и не выражается последующим Registry match, не найдено.

Вердикт: `SOURCE_LLM_NECESSITY: REJECTED`.

### Domain LLM

Domain router и package builder уже детерминированно:

- создают candidate domain allowlist;
- сужают source projection;
- фиксируют разрешённые refs/evidence;
- создают candidate graph и relations;
- сохраняют fallback `unknown_source_row`.

Экспериментальный domain LLM затем выбирает type/role bindings, то есть выполняет ту же семантическую работу, что и financial-evidence decision. Его дополнительные outputs — internal paths, relation cardinality, subtype, confidence, completeness — либо детерминируемы, либо не нужны.

Вердикт: `DOMAIN_LLM_NECESSITY: REJECTED`.

## Сравнение четырёх вариантов

| Вариант | Последовательность | LLM calls на semantic scope | Плюсы | Основной дефект | Решение |
|---|---|---:|---|---|---|
| A | Gate 1 → source → domain → financial | 3 | минимальные изменения topology | повторная семантика, максимальная стоимость и поверхность отказа | отклонён |
| B | Gate 1 → deterministic source → domain → financial | 2 | убирает самый тяжёлый source output | domain и financial всё ещё дублируют type/bindings | отклонён |
| C | Gate 1 → один новый source/domain secretary → materialization/context | 1 | чистый минимальный новый контракт | создаёт второй authority рядом с уже принятым financial contract | резерв |
| D | Gate 1 → deterministic scopes → existing financial decision → materialization/context | 1 | повторно использует qualified contract, Registry и четыре dispositions | требует выделить deterministic package entrypoint из current domain runtime | предпочтён |

Стоимость дана сравнительно: D удаляет два лишних semantic calls относительно A. Абсолютная full-scope стоимость не оценивается без нового provider run, запрещённого программой.

## Почему не вариант C

Новый `secretary_decision_v1` почти дословно повторил бы:

- `disposition`;
- Registry type ID;
- role/source-value bindings;
- bounded reason.

Эти поля уже существуют в `broker_reports_gate2_financial_evidence_decision_v1`. Создание новой семантически эквивалентной authority увеличит migration и comparator surface без новой product ability. Вариант C допустим только если implementation slice докажет, что current financial scope не может представить нужную source ownership. В current archaeology такого gap не найдено.

## Нужные deterministic seams

Current financial production runtime принимает persisted domain packages (`gate2_financial_evidence_production_runtime.py:159-280`). Поэтому вариант D нельзя реализовывать bypass-ом:

1. выделить factory, который из Gate 1 package запускает существующие segmentation/router/package-builder rules без domain model;
2. сохранить те же package-bound source refs, evidence, lineage и coverage identity;
3. передать packages в существующий financial scope factory;
4. оставить materializer, validator и context authority неизменными;
5. только после shadow equivalence исключать legacy LLM calls из write path.

## Coverage semantics

Каждый selected source ref обязан получить terminal ownership:

- включён в typed/unclassified financial input;
- признан no financial input;
- отклонён как unsupported на явной contract/system границе.

Unknown не является потерей coverage. Это сохранённый `unclassified_financial_input`. Silent drop запрещён.

## Failure modes и stop conditions

- package не воспроизводит все authoritative values → fail closed до модели;
- ref вне package → canonical reject;
- required role отсутствует → unclassified, не heuristic repair;
- incompatible role/type → canonical reject;
- context loses literal/provenance → stop rollout;
- full-scope coverage ниже frozen baseline → rollback;
- потребовалось расширение Registry → отдельная программа, не workaround.

## Acceptance

- `SOURCE_LLM_NECESSITY: REJECTED`
- `DOMAIN_LLM_NECESSITY: REJECTED`
- `ALTERNATIVES: COMPARED`
- `RECOMMENDED_STAGE_TOPOLOGY: OPTION_D`
- `SEPARATE_SOURCE_DOMAIN_MODEL_CALLS: ZERO_IN_TARGET`
