# G5.100 — VLM → Minimal Native pdfplumber Table Plan

## Итог

**STOP: `VLM_NATIVE_TABLE_PLAN_UNSAFE`.**

Прямая KISS-гипотеза дала полезный, но отрицательный результат. VLM безошибочно определила наличие и число визуальных таблиц на development-корпусе G5.99: 9 ожидаемых таблиц, 9 предложений, 0 ложных предложений на пяти отрицательных страницах. Но координатные инструкции оказались недостаточно надёжными: полностью корректно извлечено **0 из 9** таблиц.

Вторичное наблюдение — `NATIVE_PDFPLUMBER_PLAN_PROMISING_BUT_INCOMPLETE`: сам узкий native path работает на контролях и способен собрать source-bound таблицу в существующий Canonical. Проблема находится не в переносе значений, а раньше — в точности VLM-plan и в одном сложном source-binding классе.

Prompt/schema/whitelist/execution не замораживались. Новый unseen holdout не открывался.

## Research pinned API

Проект и окружение используют:

- `pdfplumber==0.11.10`;
- `pdfminer.six==20260107`.

Проверены version-pinned официальные [table API и стратегии](https://github.com/jsvine/pdfplumber/blob/v0.11.10/README.md#extracting-tables), реализация [`TableSettings`/`TableFinder`](https://github.com/jsvine/pdfplumber/blob/v0.11.10/pdfplumber/table.py) и реализация [`Page.crop`/`find_tables`](https://github.com/jsvine/pdfplumber/blob/v0.11.10/pdfplumber/page.py).

Существенные свойства 0.11.10:

- `crop` принимает `(x0, top, x1, bottom)`;
- `find_tables` возвращает native `Table` с `bbox`, `rows`, `columns`, `cells`;
- `explicit_vertical_lines` — штатная настройка;
- `horizontal_strategy` штатно допускает `lines` и `text`;
- все snap/join/intersection/text tolerances имеют встроенные defaults и не обязаны становиться частью VLM-контракта.

## Минимальный проверенный whitelist

В VLM-plan были разрешены только четыре native-понятия:

1. `bbox` — нужен, чтобы отделить несколько таблиц и соседний обычный текст.
2. `vertical_strategy="explicit"` — фиксированный native режим, без выбора между стратегиями.
3. `explicit_vertical_lines` — нужен для широких/секционных таблиц; на G5.99 p18 обычный `lines` локально дробил один визуальный grid на четыре native tables, а явные вертикальные границы собирали один grid.
4. `horizontal_strategy="lines"|"text"` — единственный выбор модели, необходимый для ruled и borderless layouts.

Разрешено **0 extraction tolerance knobs**. `explicit_horizontal_lines`, `snap_*`, `join_*`, `intersection_*`, `text_*_tolerance`, `min_words_*` запрещены schema/validator.

Координаты пересчитываются только масштабированием каждой оси:

```text
pdf_x = image_x * pdf_width / image_width
pdf_top = image_y * pdf_height / image_height
```

Поиска текста, ranking, axis reconstruction, resolver или broker-specific правил нет.

## Реализованный boundary

Исследовательский `VisualPdfPlumberTableAdapterFactory.create`:

```text
page render → strict native plan → mechanical scale → Page.crop().find_tables()
            → PDF words in native cells → existing PdfLayoutUnitBuilder
            → existing NormalizedTableProjectionFactory
            → existing CanonicalNormalizerFactory → CanonicalArtifactV1
```

Plan остаётся private-контрактом одного Gate 2 adapter. Он не экспортирован из package API и не попал в product routing. Gate 3+, Gate 4/5 и tax methodology не менялись.

Старые G5.96–G5.98 resolver/materializer paths не импортируются и не используются как fallback/repair.

Render используется только для получения plan. В Canonical не переносятся VLM literals или сам plan; существующий флаг visual fallback остаётся false, поскольку значения извлекаются из PDF text layer, а не из render/OCR.

## Проверки до реального development

Шесть fail-closed тестов подтвердили:

- exact schema и отклонение body values/tolerances/лишних полей;
- чистый coordinate scaling;
- ruled native table → один существующий Canonical;
- borderless `horizontal_strategy="text"` → source-bound table;
- пустой plan → обычный текст без ложной таблицы;
- отсутствие imports старых repair paths.

На synthetic ruled, borderless и prose controls:

- Canonical validation passed;
- source-atom accounting = 100%;
- duplicate refs = 0;
- unaccounted refs = 0;
- VLM body values used = 0;
- invented source literals = 0.

## Development G5.99

Режим исполнения:

- 9 уже открытых страниц G5.99;
- 9 provider calls;
- одна попытка на страницу;
- retry = false;
- best-of-N = false;
- model change = false;
- post-result prompt/schema correction = false.

### Aggregate

| Метрика | Результат |
|---|---:|
| Development pages | 9 |
| Positive / negative pages | 4 / 5 |
| Expected visual tables | 9 |
| VLM table proposals | 9 |
| Pages с точным presence/count | 9 / 9 |
| False plans на negatives | 0 |
| Strictly invalid plans | 1 |
| Native table objects, дошедшие до Canonical | 2 |
| Native grids, найденные до fail-closed source binding | ещё 2 |
| Полностью корректные таблицы | **0 / 9** |
| Valid Canonical pages | 6 / 9 |
| Exact-accounted Canonical pages | 6 / 9 |
| VLM body values used | 0 |
| Invented source literals | 0 |

### First divergence

1. Две таблицы fair-value: оба crop выбрали соседние, но неверные parser-line диапазоны; покрытие двух frozen truth regions — 0% и 0%. `pdfplumber.find_tables` вернул 0.
2. Ruled continuation page: два native objects дошли до Canonical, но crop покрыли только 57,1% и 53,8% frozen truth regions. Остаток страницы сохранился как обычный текст, поэтому source accounting формально 100%, однако rows/table regions восстановлены неполно.
3. Страница с тремя секциями: VLM вернула координаты в переставленном порядке осей/полей. Strict validator остановил plan до `pdfplumber`.
4. Два embedded statement examples: `pdfplumber` механически нашёл grids `3×4` и `12×5`, но существующий Gate 2 assembly fail-closed остановился на `pdf_layout_line_page_text_mismatch`, `pdf_layout_word_page_text_mismatch` и `pdf_layout_unaccounted_refs`.

## Почему не добавлена следующая native knob

Ни один наблюдаемый failure не исправляется tolerance-параметром:

- tolerance не перемещает crop в истинный регион;
- tolerance не исправляет переставленные bbox fields/axes;
- tolerance не возвращает строки, обрезанные bbox;
- tolerance не устраняет interleaved page-text/source-binding conflict.

Поэтому открывать `snap_*`, `join_*` или `intersection_*` модели не обосновано. Это лишь расширило бы пространство ошибок.

## Whole-page completeness

На шести успешно собранных страницах существующие owners дали:

- source-atom accounting 100%;
- unresolved source atoms 0;
- duplicate layout refs 0;
- unaccounted layout refs 0.

Это доказывает корректность механизма `ordinary text + accepted tables → one Canonical`, но не доказывает полноту table representation: на ruled positive page часть истинных table rows осталась ordinary text из-за короткого crop. На трёх других positive pages Canonical с новым plan вообще не был принят.

## Source truth

VLM-ответ содержит только geometry/settings. Cell values создаются только из настоящих parser words внутри native `Table.cells`, затем получают существующие source refs через `PdfLayoutUnitBuilder` и `NormalizedTableProjectionFactory`.

Итог:

```text
VLM BODY VALUES USED = 0
INVENTED SOURCE LITERALS = 0
SOURCE ATOM ACCOUNTING ON ACCEPTED CANONICAL = 100%
```

Ни один model literal не стал Canonical authority.

## Простота и TCO

Положительная часть гипотезы подтверждена структурно:

- custom resolver logic = 0;
- extraction thresholds = 0;
- custom ranking/retry = 0;
- custom row/column reconstruction = 0;
- диагностическая цепочка фактически состоит из трёх мест: plan validation → native `find_tables` → source binding/Canonical.

Размеры reference implementation:

| Артефакт | Строк |
|---|---:|
| G5.100 private adapter | 817 |
| G5.100 one-shot research harness | 537 |
| G5.100 focused tests | 247 |
| G5.98 breadcrumb harness с resolver | 1370 |
| G5.97 native-engine research harness | 1584 |
| G5.96 visual-contract harness | 1563 |
| Старые visual contracts + review + materialization owners | 2351 суммарно |

Сравнение строк не является прямым product diff: harnesses исследовательские и частично дублируют evidence plumbing. Но новый execution core действительно удаляет breadcrumbs/resolver/ranking и использует существующие Gate 2 owners.

Этого недостаточно для архитектурного GO: качество координатного plan не выдержало открытый development.

## Управляемость

Локализация каждого провала заняла три проверки:

1. VLM вернула schema-valid и геометрически правдоподобный plan?
2. `pdfplumber` нашёл ровно одну native table на plan?
3. Existing source binding и Canonical accounting сошлись?

Диагностически путь существенно проще G5.96–G5.98. Но простота диагностики не компенсирует 0/9 полностью корректных таблиц.

## KISS verdict и scope stop

Native subset сам по себе достаточно мал и не требует tolerances. Controlled extraction и Canonical assembly технически жизнеспособны. Однако модель надёжно решает **table presence/count**, но ненадёжно задаёт точную геометрию extraction engine.

Следовательно:

```text
VLM_NATIVE_TABLE_PLAN_UNSAFE
```

Не выполнены и не разрешены:

- freeze G5.100;
- unseen cross-document holdout;
- production activation;
- Gate 3+ изменения;
- repair через G5.98/G5.96;
- новый PDF DSL, OCR ensemble или best-of-N.

Следующего автоматического GOAL нет. Любая новая попытка изменить coordinate contract/model/render protocol должна быть отдельным явно разрешённым research GOAL, а не продолжением или repair G5.100.
