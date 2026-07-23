# Broker Reports — изолированный Goal 2: полный Gate 2

Дата: 2026-07-23

Статус: `NOT_CLOSED`

## Итог

После пополнения баланса OpenAI финансовый блокер снят. Повторный полный
технический Gate 2 выполнил все `41/41` обращения к `gpt-5.6-sol` через
существующий OpenWebUI provider boundary:

- provider calls passed: `41/41`;
- strict JSON Schema outputs: `41/41`;
- fallback: `0`;
- repair attempts: `0`;
- workload: `completed`;
- temporary workload scope: `cleaned`.

Однако acceptance Gate 2 не достигнут:

- domain packages: `41`;
- accepted packages: `35`;
- rejected packages: `6`;
- validations passed: `35/41`;
- selected source refs: `455`;
- terminally accounted refs: `448`;
- uncovered refs: `7`;
- source ownership conflicts: `0`;
- stitch conflicts: `0`;
- duplicate fact IDs: `0`.

Поэтому успешный transport и синтаксически строгий JSON нельзя объявить
успешным Gate 2.

## Полнота технического scope

До запуска выполнен отдельный full-scope preflight:

- source-ready documents: `1`;
- parent source units: `15`;
- derived source segments: `210`;
- selected parent refs: `455`;
- domain model packages: `41`;
- неполных, потерянных или усечённых scope: `0`;
- browser default batch limits не использовались как acceptance boundary.

Фактический run сохранил `210` route decisions, `210` segmentation/stitch
scope и обработал все `41` запланированный model package. Молчаливого
пропуска вызова модели не было.

## Точная причина `NOT_CLOSED`

Все шесть отклонений относятся к двум доменам:

| Домен | Passed | Rejected |
|---|---:|---:|
| `document_summary_evidence` | 6 | 4 |
| `fee_commission` | 5 | 2 |
| `income` | 2 | 0 |
| `position_snapshot` | 13 | 0 |
| `unknown_source_row` | 9 | 0 |

В семи отклонённых фактах валидатор зафиксировал:

- `source_fact_missing_field`: `7`;
- `source_fact_provenance_missing`: `7`;
- отсутствующее воспроизводимое значение: `7`;
- отсутствующие `original_value_refs`: `7`.

Для четырёх summary-фактов не было ни одного непустого normalized value. Для
трёх fee-фактов отсутствовал обязательный amount и его авторитетная ссылка.
Именно эти семь source refs остались uncovered.

## Анализ границы контракта

Provider schema допускает `null` в normalized values и пустые массивы
`original_value_refs`. Поэтому все ответы формально прошли строгую JSON
Schema. Канонический валидатор затем правильно потребовал содержательный
финансовый факт и воспроизводимую provenance и отклонил пустые bindings.

Это измеренный разрыв между:

1. model-facing разрешённой формой;
2. детерминированной материализацией;
3. каноническим semantic validator.

Валидатор ослаблять нельзя. Он не создал ложные факты и тем самым сохранил
fail-closed поведение.

Live default `candidate_binding_enabled=false`; именно этот production default
использован в тесте. Отдельный cross-domain candidate-binding режим не
подменял acceptance. Positional source-selection v2 является другим
поддерживаемым контрактом.

## Что уже доказано

- Блокер OpenAI quota устранён.
- Полный разрешённый технический scope действительно дошёл до провайдера.
- OpenAI способен вернуть строгий JSON по всем `41` пакетам.
- Hidden fallback и repairs отсутствуют.
- Source ownership и deterministic fact identity не конфликтуют.
- Answer context не создавался.
- Gate 3 manifest не создавался.
- Knowledge rows: `0`.
- Document rows: `0`.
- Vector identity не изменилась: `595` files,
  `309808908` bytes.

## Что не доказано

- `ACCEPTED_OR_EXPLICIT_TERMINAL_DISPOSITION: ALL`;
- `COVERAGE_UNCOVERED: ZERO`;
- отсутствие необъяснимых rejected packages;
- возможность восстановить контрольные метрики только из принятого Gate 2.

Goal 3 запускать на этом результате нельзя: он получил бы заведомо неполный
Gate 2 context.

## Узкий corrective slice

Owning component:
`Gate 2 domain model-facing response projection and deterministic
materialization boundary`.

Исправление должно:

- оставить канонический `broker_reports_source_facts_v0` и его валидатор без
  ослабления;
- не менять Gate 1 semantic visual-table JSON `description + rows`;
- убрать из model-facing domain-ответа обязанность конструировать внутренние
  normalized/provenance поля;
- переиспользовать существующий capability-aware semantic-selection подход:
  модель выбирает смысл и разрешённые value bindings, код строит системные
  поля, provenance, coverage и canonical facts;
- fail-closed отклонять scope, для которого нет воспроизводимого value
  candidate;
- после отдельного merge и atomic release повторить тот же полный Gate 2.

Новый VLM-проект, OCR, Markdown runtime, Knowledge/RAG, UI, automatic handoff
и Gate 3 для исправления не нужны.

## Безопасное evidence

- private full-scope preflight SHA-256:
  `a4bb33dc5bae04da5965c5d39aa50af8d5bdf7d7ddb08cfe74d00e30c333c368`;
- private post-funding terminal recovery SHA-256:
  `85decec1f7171a495ea29b11e11325c7524f90105fc5a8c91454a6fb1636db01`.

Клиентские названия, суммы, исходное имя, raw provider output и приватные
source refs в Git не записаны.

Repository-safe evidence:
[receipt](./BROKER_REPORTS_ISOLATED_GOAL2_GATE2_NOT_CLOSED.receipt.safe.json).

## Решение

`OPENAI_QUOTA_BLOCKER: RESOLVED`

`GOAL_2_GATE2_FULL_SCOPE_REPROOF: NOT_CLOSED`

`FAILED_INVARIANT: COVERAGE_UNCOVERED_7`

`NARROWEST_CORRECTIVE_SLICE: DOMAIN_SEMANTIC_SELECTION_MATERIALIZATION`
