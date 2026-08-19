# G5.81A — визуальная квалификация Gate 2

Дата: 2026-08-17
Режим: audit-only, human visual oracle, без VLM и без изменений product-кода

## Итог

Все 79 кандидатов, которые были переведены из `REJECTED` в `READY` только заменой проверки `min(row_cell_counts)` на `max(row_cell_counts)`, просмотрены по исходному PDF и точному crop без выборки.

Результат: **77 таблиц, 2 не-таблицы, 0 неоднозначных**. Поэтому общая корректность новой эвристики не доказана. Доказана и локализована её узкая false-positive граница.

| Набор | Всего | Таблица | Не таблица | Неоднозначно |
|---|---:|---:|---:|---:|
| `large_real` promoted | 74 | 72 | 2 | 0 |
| `holdout_real` promoted | 5 | 5 | 0 | 0 |
| Итого promoted | 79 | 77 | 2 | 0 |

Замороженная популяция: `bae2abc528bd168150876af47887103fb1065accc5b86e6ff73197c7166da338`.

## Два false positive

| № | Страница | Candidate | Что видно человеку | Почему это не таблица |
|---:|---:|---|---|---|
| 73 | 64 | `pdftablecand_e42ae0b0bfb9f80e98b4a447` | Нумерованные юридические абзацы | Нет повторяемой структуры записей `строка × колонка` |
| 74 | 65 | `pdftablecand_893c6e585e6889497afe4395` | Продолжение нумерованного текста | Нет повторяемой структуры записей `строка × колонка` |

Оба случая пришли через `ruled_lines_v0`. Детектор посчитал прямоугольники вокруг текстовых строк доказательством разлиновки:

| № | Вертикальные vector lines | Горизонтальные vector lines | Rectangles |
|---:|---:|---:|---:|
| 73 | 0 | 0 | 43 |
| 74 | 0 | 1 | 18 |

Это один общий структурный класс:

`RECTANGLE_ONLY_OR_SINGLE_LINE_TEXT_GEOMETRY_MISTAKEN_FOR_RULED_GRID`

## Квалифицированная граница

Для `ruled_lines_v0` на проверенной популяции достаточным нейтральным различителем оказался минимум один набор из двух параллельных настоящих vector lines:

```text
max(vertical_vector_lines, horizontal_vector_lines) >= 2
```

Это не broker/page rule: две параллельные линии — минимальное свидетельство семейства границ разлинованной таблицы. Проверка сохраняет все 77 истинных promoted-кандидатов и все 10 positive controls, одновременно отклоняя оба новых false positive. Даже пустая табличная схема из promoted-популяции, у которой нет вертикалей, имеет 15 горизонтальных линий.

Это только квалифицированный candidate boundary для рассмотренного корпуса, а не доказанный универсальный product-контракт.

## Controls

Positive controls: 10/10 визуально являются таблицами и проходят существующий Gate 2 path. Девять взяты из реального holdout; один явно помечен как `SYNTHETIC_CALIBRATION` и представляет простой grid 4×3.

Negative controls: 10/10 визуально не являются таблицами. Девять отклоняются до acceptance, но один уже существующий случай принимается ошибочно:

- страница 6 `holdout_real`;
- `pdftablecand_06557cd60d52a6655e046a93`;
- `aligned_text_v0`, 39 строк, 429 ячеек, по 11 ячеек в каждой строке;
- нумерованная проза/глоссарий, а не таблица;
- результат был `READY` и до изменения `min → max`, то есть это отдельный старый false-positive класс.

Итого для negative controls: 9 корректных reject, 1 ошибочный accept.

## Решение

Выбран **стратегический стоп без patch**.

Узкое условие для `ruled_lines_v0` хорошо локализовано, но его внедрение не сделает даже текущие negative controls зелёными: останется независимый false positive в `aligned_text_v0`. Исправлять второй класс в том же GOAL означало бы расширить вопрос и подгонять несколько владельцев сразу. Для KISS и fail-closed поведения это хуже, чем честно остановиться на доказанной границе.

До отдельной квалификации `aligned_text_v0` переход к Gate 3 не разрешён.

## Scope proof

- Просмотрено 79/79 promoted-кандидатов; sampling = 0.
- Positive controls = 10; negative controls = 10.
- VLM как judge не использовалась.
- Финансовая семантика в table detection не добавлялась.
- Broker-specific и page-specific правила не добавлялись.
- Gate 3, decimal, methodology, metadata и VLM paths не менялись.
- Product/runtime-код не менялся.
- Visual oracle остаётся только development evidence и не стал production dependency.
- Приватные PDF, crops и полные machine artifacts находятся только в ignored evidence bundle; в tracked-отчёте нет клиентского содержимого.

## Terminal

```text
PROMOTED_CANDIDATES_79_OF_79_REVIEWED
GATE2_TABLE_HEURISTIC_FALSE_POSITIVE_BOUNDARY_PROVEN
FALSE_POSITIVE_STRUCTURAL_CLASS_LOCALIZED

GATE2_TABLE_HEURISTIC_GENERALIZATION_PROVEN=NO
STRATEGIC_STOP=YES
READY_FOR_GATE3_FAIL_CLOSED_GRANULARITY_AUDIT=NO
BROKER_SPECIFIC_TABLE_FITTING_ZERO
PAGE_SPECIFIC_TABLE_FITTING_ZERO
FINANCIAL_SEMANTICS_IN_TABLE_DETECTION_ZERO
PRODUCTION_VISUAL_DEPENDENCY_ZERO
```
