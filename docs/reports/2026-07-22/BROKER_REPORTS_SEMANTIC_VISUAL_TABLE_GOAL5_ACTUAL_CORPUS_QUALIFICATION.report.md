# Broker Reports — Goal 5: квалификация semantic visual-table contract на actual corpus

Дата: 2026-07-22

Результат выполнения: `COMPLETED`

Квалификационный gate: `PASSED`
Production-default: **не активирован**; решение отложено до Goal 6.

## Вывод

Гипотеза подтверждена на ограниченном actual-corpus контуре: модели заметно надёжнее возвращают смысловую таблицу в облегчённом JSON, когда от них не требуется реконструировать координаты, spans и физическую сетку. На восьми заранее поддержанными числовых таблицах все 16 Gemini master executions дали 100% сумм, 100% связи «строка — значение», ноль вымышленных сумм и ноль необъяснённых terminal outcomes.

Это не доказательство универсального парсера. Девятая таблица — long-form prose grid — была классифицирована как `unsupported_layout` до provider execution и осталась fail-closed независимо от того, что ответы моделей прошли JSON schema validation.

## Боль и проверяемое предположение

Предыдущий low-level контракт заставлял VLM одновременно читать текст и угадывать физическое устройство PDF-таблицы: координаты, пустые ячейки, spans, число колонок и геометрические связи. На том же ограниченном контуре он показал:

- contract validity — 80,56%;
- numeric agreement — 67,47%;
- row binding support — 48,03%;
- numeric hallucination rate — 3,653%;
- structurally useful distinct crops — 2 из 9.

Проверяемое предположение Goal 5: если model-facing контракт оставить на уровне `description + rows`, а системную и табличную структуру достраивать кодом, геометрические ошибки перестанут разрушать содержательно правильную транскрипцию.

## Метод

- Использованы 9 существующих source-bound crops, повторно отрендеренных через `PdfTableRasterFactory`; их SHA-256 совпали с замороженными идентичностями.
- Source truth собрана только из sealed delegated reference и замороженного source-only supplement. Provider output и согласие провайдеров не использовались как истина.
- Профиль gate: 8 числовых таблиц; 1 prose layout — unsupported.
- Контракт, prompt и model view не менялись после Goal 4.
- Выполнены 18 Gemini calls: A/B для всех девяти crops.
- Выполнены 9 OpenAI calls как неавторитетный diagnostic control.
- Retry, merge, repair, provider failover и stage mutation не выполнялись.

## Результаты

| Метрика | Gemini master, accepted profile | OpenAI diagnostic control, accepted profile |
|---|---:|---:|
| Executions | 16 | 8 |
| Валидный semantic JSON | 16/16 | 8/8 |
| Exact labels | 186/196 (94,90%) | 97/98 (98,98%) |
| Amount fidelity | 166/166 (100%) | 83/83 (100%) |
| Row/value binding | 156/156 (100%) | 78/78 (100%) |
| Hallucinated labels | 0 | 0 |
| Hallucinated amounts | 0 | 0 |
| Provider failures | 0 | 0 |

Gemini был материально повторяем на 8 из 8 поддерживаемых таблиц. Все проверенные layout families — `borderless`, `simple_grid`, `sparse_cells`, `merged_headers`, `totals_subtotals` и ограниченные `complex_broker_layout` — сохранили 100% сумм и binding в измеренном профиле.

Exact-label показатель Gemini снижен только десятью повторившимися вариантами апострофа: обычный `'` вместо типографского `’` в пяти метках на каждом A/B прогоне. Эти варианты:

- не объявлены точным literal match;
- не объявлены hallucination;
- признаны эквивалентными только для проверки связи строки с её суммой.

OpenAI сохранил все суммы и bindings, но один раз опустил нечисловой верхний заголовок. Поэтому контроль подтверждает полезность OpenAI как потенциального fallback, но не доказывает необходимость always-on вызова: наблюдаемых Gemini failures было ноль, фактическая fallback frequency — 0.

## Коррекция оценщика после live run

Первичный scoring ошибочно пометил gate как failed по двум presentation-only причинам:

1. Currency marker, слитый с суммой без пробела, не распознавался как эквивалент варианта с пробелом.
2. Апостроф `'` вместо `’` нарушал row binding, хотя метка и сумма оставались на одной строке.

Оценщик исправлен без повторных provider calls. Raw JSON, parsed responses и execution evidence не менялись. Exact-label metric сохранил апострофные различия; допуск применяется только к currency-cell projection и binding. Содержательные пороги не снижались.

## Ответы на вопросы Goal 5

**Снизились ли geometry-only failures?** Да, в измеренном числовом профиле: вместо попытки восстановить атомарную геометрию получено 16/16 schema-valid Gemini outputs с полными суммами и binding. Сравнение с прежними 2/9 structurally useful crops показывает сильный практический эффект, но метрики двух контрактов не полностью взаимозаменяемы.

**Сохранилась ли literal completeness?** Суммы — полностью. Метки — содержательно полностью у Gemini, но не byte-exact из-за апострофов; у OpenAI отсутствует один нечисловой header. Поэтому нельзя заявлять 100% exact-label fidelity.

**Надёжен ли Gemini как master?** Для ограниченного accepted profile — да: 8/8 material repeatability, 100% amounts и binding, ноль provider failures. За пределы профиля вывод не переносится.

**Полезен ли OpenAI fallback?** Потенциально да: 8/8 controls прошли обязательные числовые критерии. Наблюдаемой необходимости fallback в этом прогоне не было, поэтому его стоимость и activation policy должен проверить Goal 6.

**Какие layouts пока не поддержаны?** Long-form prose grids остаются unsupported. Cross-page continuations, unreadable/obscured tables и иные не представленные в bounded contour варианты также не квалифицированы и должны завершаться fail-closed.

## Решение

Goal 5 закрывает actual-corpus qualification для ограниченного числового профиля. Это разрешает перейти к диагностике production-default в Goal 6, но само по себе не разрешает менять default, публиковать provider output без последующей системной обработки или ослаблять unsupported boundary.

Evidence identities:

- frozen manifest SHA-256: `2f33d6466d114d8e9ee95da246fb5a2c0f0a4896398d51131ce58e6d9fc335eb`;
- semantic source reference SHA-256: `ac719b8d951921485126fe1a011eab16f3b0d18246b546dddd0e98f38b702af0`;
- safe receipt SHA-256 identity: `96820ec84e1a4bfa167ac4c85090c0295f337ac24d2694d4f6fde0c535ed2ad7`;
- gate SHA-256 identity: `2860e0d181ae4a8137ec4db796b2f26070f2df32e4581f4438107410fc62adbb`.

Private crops, raw provider JSON and literal values остаются только в локальном ignored evidence package; в Git они не добавлены.
