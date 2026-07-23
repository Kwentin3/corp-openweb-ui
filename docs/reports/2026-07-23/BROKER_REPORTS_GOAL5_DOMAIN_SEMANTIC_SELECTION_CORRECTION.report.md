# Broker Reports — исправление model-facing контракта Gate 2

Дата: 2026-07-23

Статус: `IMPLEMENTED_AWAITING_RELEASE_REPROOF`

## Итог простыми словами

После пополнения баланса OpenAI повторный полный тест действительно дошёл до
модели: все `41/41` обращения завершились успешно и вернули строгий JSON.
Значит финансовый блокер снят.

При этом выяснилась настоящая техническая проблема. Модель умела заполнить
большой JSON по форме, но в шести пакетах оставляла пустыми именно те значения
и ссылки, без которых финансовый факт нельзя считать подтверждённым. Поэтому
валидатор правильно отклонил эти пакеты.

Исправление реализовано: domain-runtime теперь может просить у модели не
готовый внутренний объект, а короткое смысловое решение. Модель выбирает:

- тип факта либо явный результат «факта нет / смысл не определён»;
- разрешённые ссылки на исходные значения;
- смысловую роль каждой выбранной ссылки, например `amount`.

Все служебные поля, provenance, coverage, стабильные ID и канонический
`broker_reports_source_facts_v0` после этого строит код.

## В чём была боль

Старый model-facing контракт смешивал две разные обязанности:

1. понять смысл изображения или текстового фрагмента;
2. правильно собрать внутреннюю системную структуру со всеми ID, null-полями,
   массивами ссылок, coverage и audit metadata.

Вторую обязанность модель выполняла формально: JSON соответствовал схеме, но
допустимые схемой `null` и пустые массивы делали часть фактов семантически
пустыми. На повторном полном запуске это дало:

- `41` domain package;
- `35` принятых;
- `6` отклонённых;
- `7` непокрытых source refs;
- `7` ошибок отсутствующего обязательного значения;
- `7` ошибок отсутствующей provenance.

## Что изменено

Для domain-runtime подключён уже существующий
`broker_reports_source_fact_selection_v3`. Его model-facing корень содержит
только `decisions`; каждое решение содержит только:

- `decision_type`;
- `value_bindings`.

Для нейтральных визуальных таблиц заголовок `unknown` больше не означает, что
числовую ячейку нельзя использовать. Код проверяет каждую исходную ссылку
всеми разрешёнными механическими нормализаторами и показывает модели только
реально воспроизводимые пары «поле + ссылка». Финансовый смысл выбирает
модель, но само значение код не угадывает и не переписывает.

Если из цельной текстовой строки сумму нельзя воспроизвести отдельной
авторитетной ссылкой, typed financial fact недоступен в provider schema.
Такой источник должен получить явный `unknown` или `no-fact`, а не
правдоподобный, но неподтверждённый факт.

## Что осталось неизменным

- Gate 1 visual-table контракт `description + rows`;
- канонический `broker_reports_source_facts_v0`;
- строгий canonical validator;
- исходные суммы и source-value refs;
- детерминированное владение source refs;
- отдельный экспериментальный candidate-binding режим;
- legacy full-JSON режим для явных compatibility-вызовов;
- запрет Knowledge/RAG/vector;
- границы Gate 3, налоговых расчётов, деклараций и XLS/XLSX.

Одновременное включение semantic selection и candidate binding теперь
отклоняется до model call. В live Pipe semantic selection является новым
default, а явный candidate-binding вызов автоматически остаётся в своём
отдельном режиме.

## Проверка

Локально пройдены:

- domain/source runtime, model boundary и bundled Pipe: `83/83`;
- neutral-table, input-readiness, semantic downstream и table projection:
  `55/55`;
- всего: `138/138`;
- Python compile: passed;
- `git diff --check`: passed;
- повторная сборка двух Gate 2 bundles: SHA-256 не меняется.

Отдельный тест доказал полный путь на нейтральной таблице:

1. provider schema содержит только `decisions`;
2. модель возвращает тип факта и ссылку, без суммы и системных полей;
3. код воспроизводит сумму из авторитетного source-value ref;
4. canonical validator принимает факт;
5. selection validation сохраняется отдельным safe-internal артефактом;
6. Gate 3 manifest разрешает весь граф артефактов без пропуска.

## Ограничение результата

Это исправление реализовано и проверено локально, но ещё не является новым
полным Gate 2 acceptance. Нельзя переносить результат старого запуска на
новый код.

После merge нужен отдельный atomic release, затем повтор того же полного
scope:

- `1` документ;
- `15` parent source units;
- `210` derived source segments;
- `455` selected source refs;
- полный набор domain packages без browser batch boundary;
- fallback `0`;
- repair `0`;
- uncovered `0` либо явная допустимая terminal disposition для каждого ref.

## Безопасность evidence

В Git не записаны клиентские названия, суммы, исходное имя файла, raw provider
output и приватные source refs.

Repository-safe evidence:
[receipt](./BROKER_REPORTS_GOAL5_DOMAIN_SEMANTIC_SELECTION_CORRECTION.receipt.safe.json).

## Решение

`OPENAI_QUOTA_BLOCKER: RESOLVED`

`MODEL_FACING_CONTRACT_CORRECTION: IMPLEMENTED`

`CANONICAL_VALIDATOR: UNCHANGED`

`FULL_GATE2_REPROOF_ON_RELEASED_CODE: REQUIRED`
