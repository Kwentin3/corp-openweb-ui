# Broker Reports — повторная проверка Gate 2 после пополнения OpenAI

Дата: 2026-07-23

Статус: `NOT_CLOSED`

## Короткий итог

Финансовый блокер OpenAI снят. Полный повторный прогон дошёл до модели и
выполнил все `41/41` вызова `gpt-5.6-sol`:

- provider calls passed: `41/41`;
- strict JSON Schema outputs: `41/41`;
- schema: `broker_reports_source_fact_selection_v3` — `41/41`;
- fallback outputs: `0`;
- repair attempts: `0`;
- model-generated system metadata: `0`;
- terminal workload status: `completed_with_rejections`.

Но сам Gate 2 не закрыт:

- domain packages: `41`;
- accepted packages: `21`;
- rejected packages: `20`;
- selected source refs: `455`;
- uncovered source refs: `42`;
- source ownership conflicts: `0`;
- stitch conflicts: `0`;
- duplicate fact IDs: `0`.

Значит, прежний блокер действительно был связан с балансом, но после его
устранения проявился следующий, уже содержательный дефект контракта.

## Что именно сломалось

Все ответы модели соответствовали строгой JSON Schema. Однако `20` пакетов
не прошли следующий детерминированный semantic validation.

В `41` selection validation зафиксировано `37` ошибок двух типов:

| Код | Количество |
|---|---:|
| `source_fact_selection_unknown_binding_forbidden` | 27 |
| `source_fact_selection_no_fact_binding_forbidden` | 10 |

Модель выбирала решение `unknown` или `no_fact`, но одновременно возвращала
непустые `value_bindings`. Текущая provider schema такую комбинацию
синтаксически разрешает, а канонический валидатор затем правильно отклоняет
её как семантически противоречивую.

Таким образом, проблема находится не в JSON как формате и не в способности
OpenAI вернуть упрощённый объект. Проблема в том, что строгая схема пока
описывает допустимые поля по отдельности, но не выражает зависимость между
ними:

`decision_type = unknown/no_fact` → `value_bindings` должны быть пустыми.

Короткая инструкция модели «верни решения и разрешённые bindings» тоже не
объясняет это правило достаточно явно.

## Что эксперимент уже доказал

Идея облегчённого model-facing JSON жизнеспособна:

- модель стабильно вернула минимальный объект только с решениями и
  bindings;
- все внутренние идентификаторы, provenance, coverage и канонические
  структуры по-прежнему строит код;
- модель не генерировала системные metadata-поля;
- старый тяжёлый JSON-контракт для этого не понадобился;
- Markdown runtime и Markdown parser не понадобились;
- Knowledge/RAG/vector не использовались;
- candidate-binding контур не включался;
- скрытых fallback и repair не было.

Одновременно эксперимент показал важную границу: уменьшить число полей
недостаточно. В минимальном контракте должны оставаться все смысловые
инварианты, иначе strict JSON гарантирует только форму, но не согласованность
решения.

## Сравнение с предыдущим прогоном

До semantic-selection correction полный прогон давал `35/41` принятых
пакетов и `7` uncovered refs. Новый контракт дал `21/41` принятых пакетов и
`42` uncovered refs.

Следовательно, текущую released-версию нельзя считать улучшением на
реальном полном корпусе, несмотря на успешные модульные проверки и успешный
provider transport. Нужен отдельный узкий corrective slice и новый live
reproof.

## Узкое исправление

Owning component:
`Gate2 source-fact semantic-selection provider schema and task instruction`.

Следующий отдельный corrective slice должен:

1. сделать provider schema условной по `decision_type`;
2. для `unknown` и `no_fact` разрешать только пустой `value_bindings`;
3. для фактов оставлять только воспроизводимые field/ref bindings;
4. явно повторить то же правило в model instruction;
5. не ослаблять канонический валидатор;
6. не менять Gate 1 `description + rows`, внутренний
   `broker_reports_source_facts_v0`, Knowledge/RAG, UI или Gate 3;
7. после отдельного merge и atomic release повторить тот же полный набор из
   `41` model packages.

До этого исправления запуск Gate 3 на полученном результате запрещён:
контекст неполон.

## Чистота и безопасность

- answer context не создавался;
- Gate 3 manifest не создавался;
- Knowledge rows delta: `0`;
- Document rows delta: `0`;
- vector collections/files/bytes delta: `0`;
- owned workload дошёл до терминального состояния;
- приватные клиентские названия, суммы, имя исходного файла, raw provider
  output и source refs в Git не записаны.

Private live evidence SHA-256:
`60a6a57b8371c5acb5c960c03305790878376c21da5d1cb35c85b28e6f4ffc68`.

Repository-safe evidence:
[receipt](./BROKER_REPORTS_ISOLATED_GOAL2_GATE2_SEMANTIC_SELECTION_REPROOF_NOT_CLOSED.receipt.safe.json).

## Решение

`OPENAI_QUOTA_BLOCKER: RESOLVED`

`GOAL_2_GATE2_SEMANTIC_SELECTION_REPROOF: NOT_CLOSED`

`FAILED_INVARIANT: SEMANTIC_SELECTION_DECISION_BINDING_CONSISTENCY`

`NARROWEST_CORRECTIVE_SLICE: CONDITIONAL_DECISION_BINDING_SCHEMA`
