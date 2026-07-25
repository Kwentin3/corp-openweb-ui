# Broker Reports — Gate 2 Secretary Task Normative Definition

Дата: 2026-07-25  
Статус: `GOAL_5_SECRETARY_TASK: COMPLETED`

## Нормативная задача

Модель получает:

- один ограниченный source scope;
- literal values только вместе с package-bound `source_value_ref`;
- определения только допустимых Financial Evidence Registry types;
- required/optional role IDs;
- совместимость каждого source value с ограниченным набором roles;
- strict branch-specific output schema.

Модель должна выбрать ровно один terminal outcome:

1. поддерживаемый Registry type и bindings;
2. финансовые данные без безопасного Registry match;
3. отсутствие финансовых данных;
4. явно неподдерживаемый input shape по разрешённому current contract.

Она не строит facts, graph, relations, paths, IDs, provenance, audit, confidence или completeness.

## Нормативный prompt

> Ты выполняешь ограниченное сопоставление финансовых данных. Используй только определения типов, роли и literal source values из package. Верни один разрешённый disposition. Для typed result выбери только допустимый `input_type_id` и свяжи каждую роль только с разрешённым `source_value_ref`. Если финансовые значения есть, но безопасный тип выбрать нельзя, сохрани их как `unclassified_financial_input`. Не придумывай значения, типы, роли или refs. Не вычисляй отсутствующие измерения и не создавай системную структуру. Верни только объект strict schema.

Этот текст соответствует уже принятой production prompt boundary (`gate2_financial_evidence_production_runtime.py:127-148`).

## Disposition mapping

| Исследовательский термин | Принятый financial disposition | Reason |
|---|---|---|
| `matched` | `typed_input` | `typed_supported` |
| `unclassified` | `unclassified_financial_input` | `ambiguous_registry_type` |
| `no_match` | `unclassified_financial_input` | `no_registry_type` |
| `no_financial_data` | `no_financial_input` | `header_or_layout`, `duplicate_representation` или `non_financial_content` |
| system/shape unsupported | `unsupported` | bounded current unsupported reason |

Отдельный `ambiguous` disposition не нужен: `unclassified_financial_input/ambiguous_registry_type` уже сохраняет данные и причину.

`no_match` нельзя превращать в `no_financial_input`: финансовый literal должен остаться в context как unclassified. Это принципиальная граница против потери данных.

## Что модель не делает

- не определяет schema/package/run/artifact identity;
- не копирует package/source/document refs за пределами выбранных bindings;
- не нормализует literal;
- не выбирает `fact_field_path`;
- не возвращает candidate/relation IDs;
- не назначает ownership graph;
- не оценивает техническую completeness;
- не связывает issue/restriction policy;
- не создаёт audit metadata;
- не исправляет ответ скрытым repair/fallback.

## Финансовая экспертиза

Требуется только понимание коротких Registry definitions и видимого source context. Налоговая методика, расчёты, cross-document consolidation и Gate 3 знания отсутствуют. Модель не должна знать внутреннюю object model.

## Terminal discipline

- `typed_input`: каждый required role связан; optional role либо ref, либо null.
- `unclassified_financial_input`: минимум один package value сохранён с разрешённой ролью.
- `no_financial_input`: bindings и type structurally absent.
- `unsupported`: bindings и type structurally absent.
- Любой ref вне package или type вне eligible set — canonical reject.

## Acceptance

- `SECRETARY_TASK: NORMATIVELY_DEFINED`
- `FINANCIAL_EXPERTISE_REQUIRED: ZERO_BEYOND_REGISTRY_DEFINITIONS`
- `INTERNAL_SYSTEM_MODEL_REQUIRED: ZERO`
- `FREE_FORM_TERMS: ZERO`
- `AMBIGUOUS_DISPOSITION_REQUIRED: NO`
