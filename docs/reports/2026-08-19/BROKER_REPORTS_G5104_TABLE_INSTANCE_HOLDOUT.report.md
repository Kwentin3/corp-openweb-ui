# G5.104 — cross-report holdout для разделения таблиц

## Итог

**Уточнённый G5.103 prompt прошёл проверку на двух других отчётах: `TABLE_INSTANCE_SEPARATION_CROSS_REPORT_HOLDOUT_PASSED`.**

Без изменения prompt, schema и model policy выполнен один frozen-прогон: 5 страниц, из них 3 табличные и 2 отрицательные. Получено 3 bbox для 3 ожидаемых таблиц; count точен на 5 / 5 страницах, ложных boxes на negatives нет. Ручная проверка подтвердила 3 / 3 рамки: каждая охватывает одну data grid без соседнего текста, заголовка или другой таблицы.

## Что это исправляет в прежнем выводе

G5.103 уже проверял не одну таблицу, а 9 таблиц на четырёх positive pages плюс пять negative pages. Его слабое место было другим: все страницы были development-набором, а формулировка prompt появилась после разбора известного слияния.

G5.104 добавил именно недостающий тест переноса:

- два других document hashes, отсутствовавших в G5.102/G5.103 development;
- три разных вида таблиц: borderless/wrapped, full-page financial statement и небольшая embedded table;
- две cover pages как negative control;
- exact G5.103 prompt, schema и model без repair после просмотра результата;
- одна попытка на страницу, без retry, best-of-N и failover.

Подсказка «это брокерский отчёт» не добавлялась. Нейтрального определения `one independent grid = one bbox` оказалось достаточно и на этом наборе.

## Результат

| Проверка | Результат |
|---|---:|
| Документы | 2 |
| Страницы positive / negative | 3 / 2 |
| Ожидаемые / найденные таблицы | 3 / 3 |
| Страницы с точным count | 5 / 5 |
| Визуально корректные positive boxes | 3 / 3 |
| False boxes на negatives | 0 |
| Merge / split failures | 0 / 0 |
| Invalid responses | 0 |
| Provider calls / retries | 5 / 0 |
| Tokens input / output / total | 7 070 / 98 / 7 168 |
| Сумма provider duration | 17 577 ms |

Literal values модель не поставляла: она только локализовала regions; source authority остаётся у PDF/parser.

## Ограничения

Это честный cross-report holdout относительно G5.103, но не глобально новый корпус: документы раньше входили в отдельный structural benchmark. Repeatability не проверялась. Один предварительно выбранный rotated page был исключён до provider call, потому что frozen G5.102 projection seam поддерживает только rotation 0; контракт ради теста не расширяли.

Поэтому вывод узкий: prompt больше не выглядит починкой одной известной таблицы и переносится на два других layout family. Это ещё не доказательство работы на любых PDF и не разрешение на production.

## Следующая стратегия

Prompt разделения теперь замораживаем и больше не «подкручиваем» на этих страницах. Следующий отдельный GOAL можно посвятить bounded parser/pdfplumber extraction внутри уже найденных regions. Column geometry, extraction quality и rotation support нельзя смешивать с этим завершённым тестом.

Не выполнены: production activation, Canonical materialization, Gate 3+ changes, commit или push.
