# G5.103 — разделение визуальных экземпляров таблиц

## Итог

**На development-наборе гипотеза сработала: `TABLE_INSTANCE_SEPARATION_DEVELOPMENT_VALIDATED`.**

Проблемная пара таблиц больше не слита. На тех же девяти уже изученных страницах модель вернула 9 boxes для 9 ожидаемых таблиц; все пять отрицательных страниц остались пустыми. Все семь машинно выразимых truth regions совпали полностью, без лишних parser lines.

Это ещё не доказательство обобщения. Формулировка создана после разбора ошибки G5.102, поэтому оставшийся blocker — `UNSEEN_HOLDOUT_NOT_EXECUTED`.

## Контекст для возврата: не наступить на те же грабли

Исходная боль: parser хорошо сохраняет literals, refs и координаты, но теряет часть видимой структуры таблиц. VLM хорошо видит таблицы, однако её текст нельзя считать source truth, а попытка заставить её сразу управлять extraction оказалась ненадёжной.

Цепочка экспериментов в одном предложении:

```text
whole-page transcription
→ rich layout/breadcrumb contract
→ native table engine
→ прямые PDF/pdfplumber coordinates
→ видимая coordinate grid
→ Gemini-native normalized bbox
→ явный one-table-instance = one-bbox contract
```

### Грабли, к которым не возвращаемся

| Грабли | Что выяснили |
|---|---|
| Заменить parser whole-page VLM-текстом | VLM лучше видит layout, но меняет literals, иногда не отвечает и не сохраняет source addressability. |
| Передать VLM богатый breadcrumb/layout contract | Работало на одном development family, но cross-document дало `0` correct resolutions и четыре false localizations. Больше полей не гарантирует переносимость. |
| Надеяться, что native `pdfplumber` сам решит задачу | Он хорошо строит rows/cells **после** точной локализации, но не решает, где находится нужная таблица. |
| Просить у VLM сразу PDF points и настройки extraction | Мы проверяли одновременно зрение модели, порядок осей, пересчёт координат и знание `pdfplumber`; полностью корректных таблиц было `0/9`. |
| Нарисовать сетку и линейки | Сетка удобна человеку, но не привязала модель к PDF coordinates и ухудшила acceptance. |
| Добавлять tolerances, broker vocabulary или новые поля после ошибки | Это чинит не тот слой, повышает риск подгонки и может создать false positives. |

### Находки, которые реально сдвинули вопрос

1. **Visual presence/count у модели сильные.** На сложном наборе она неоднократно находила правильное число таблиц и оставляла negative pages пустыми.
2. **Модель должна указывать область, а не считать координаты движка.** Gemini-native `box_2d` в `0…1000` устранил axis/coordinate mismatch; перевод в PDF points должен делать детерминированный код.
3. **Parser остаётся source authority.** Значения, literals, refs и последующая extraction берутся только из PDF; VLM не поставляет body values.
4. **Единица `table instance` должна быть явной.** Правило `one visually independent grid = one bbox` убрало наблюдавшееся слияние: `9/9` tables, `7/7` exact regions, negatives `0`.

Рабочий принцип:

```text
VLM указывает визуальные table regions
→ код переводит normalized coordinates
→ parser/pdfplumber извлекает и привязывает source data
```

### Текущая точка и следующий шаг

Сейчас доказан только development-механизм G5.103. Следующий тест должен заморозить exact prompt, schema, model policy и выполнить один untouched cross-document holdout без последующего prompt repair. Если holdout провалится, нужно классифицировать первый divergence, а не дописывать ещё одно поле на уже открытых страницах.

К column geometry и `pdfplumber` extraction можно переходить только после успешного holdout table-region stage; смешивать эти задачи в одном тесте снова нельзя.

## Что именно изменено

G5.102 уже содержал короткую инструкцию `Keep visually distinct tables separate`. Следовательно, G5.103 не добавлял идею разделения с нуля, а сделал единицу результата операционной:

- на изображении может быть ноль, один или несколько table instances;
- один визуально самостоятельный data grid должен давать ровно один bbox;
- один bbox не должен охватывать два разных grids или самостоятельно озаглавленных table sections;
- отдельный title/header вместе с whitespace или разрывом grid/row continuity означает новый instance;
- непрерывный grid нельзя делить только из-за внутренних section rows, повторной шапки или continuation status.

Фраза «это брокерский отчёт» и предположение «таблиц обязательно много» не добавлялись. Это сознательно сохраняет правило нейтральным к документу и не подталкивает модель к false positives.

## Контролируемый эксперимент

Изменена только `visual_table_instance_definition_in_prompt`.

Без изменений остались:

- те же девять full-page PNG byte-for-byte;
- `models/gemini-3.5-flash` и `thinking=minimal`;
- response schema и Gemini `box_2d=[ymin,xmin,ymax,xmax]`, integer `0…1000`;
- raster, provider и projection factories;
- одна попытка на страницу;
- retry, best-of-N, repair и failover выключены;
- frozen count/region evaluation.

Execution path:

```text
PdfTableRasterFactory.create
→ PdfGridExperimentProviderFactory.create_for_openwebui
→ GeminiNormalizedTableBoxProjectionFactory.create
```

Product runtime, Canonical, table extraction, column geometry, values и Gate 3+ не затронуты.

## Pre-provider seam

До inference выполнены:

- Ruff и `py_compile`;
- 38 focused tests;
- проверка точечной замены единственного prompt anchor;
- exact reuse G5.102 schema/projector;
- factory/closed-world anchors;
- fail-closed terminal tests;
- проверка отсутствия broker/domain hint, grid, extraction и product route.

Первый pytest command остановился до запуска тестов из-за двух неверно названных test paths; код не менялся, команда была повторена с существующими файлами. Затем collection выявил неверное место переноса строки в буквальном G5.102 prompt anchor; исправлен только anchor, новый prompt contract не менялся. После этого 38 тестов прошли.

Первый execution command также завершился до импорта harness и до provider call: прямой запуск файла не включил service root в Python import path. Повтор выполнен штатным module route `python -m scripts.local_table_instance_separation_g5103`. Evidence-директории до него отсутствовали.

После execution финальная релевантная регрессия G5.94–G5.103 прошла: 77 tests passed. Ruff и `py_compile` повторно прошли; пять warnings относятся к прежней PyMuPDF/SWIG deprecation и не являются test failures.

## Development execution

- pages: 9;
- positive / negative: 4 / 5;
- provider inference calls: 9;
- attempts per page: 1;
- hidden retry: false;
- provider failover: false;
- model resolved exactly to `models/gemini-3.5-flash`;
- all finish reasons: `STOP`;
- input / output / total tokens: 12 726 / 362 / 13 088;
- provider-duration sum: 19 235 ms.

## Результаты

| Метрика | G5.102 | G5.103 |
|---|---:|---:|
| Expected tables | 9 | 9 |
| Proposed boxes | 8 | **9** |
| Pages с точным count | 8 / 9 | **9 / 9** |
| Exact expressible truth regions | 5 / 7 | **7 / 7** |
| Regions с полным truth coverage | 6 / 7 | **7 / 7** |
| Mean truth coverage | 85,7% | **100%** |
| Extraneous parser lines | 65 | **0** |
| False boxes на negatives | 0 | **0** |
| Invalid responses | 0 | **0** |

На ранее проблемной continuation page модель вернула три отдельных boxes вместо двух, то есть разделила ранее слитую пару. Оба ожидаемых региона получили точное frozen line-region совпадение.

Две embedded tables на странице-иллюстрации не имеют contiguous parser-line truth. Они проверены визуально: оба bbox охватывают внутренние data grids, а не целые screenshots и не соседний поясняющий текст — 2 / 2.

## Критическая интерпретация

Результат поддерживает нашу гипотезу, но не доказывает, что модель «сама всегда понимает количество таблиц». Он показывает более узкую вещь: прежний prompt оставлял `visually distinct` слишком расплывчатым, а явная единица `one independent grid = one bbox` устранила наблюдавшееся слияние на development.

Есть два риска:

1. правило подогнано после известной ошибки;
2. более агрессивное разделение может начать дробить единую таблицу на новом документе.

Именно поэтому нельзя ещё менять runtime или переходить к column geometry.

## KISS verdict и scope stop

Нейтральное уточнение контракта оказалось достаточным на development; доменная подсказка про брокерский отчёт не потребовалась.

Разрешён только следующий независимый шаг:

```text
freeze exact G5.103 prompt + schema + model policy
→ one untouched holdout run
→ no post-holdout prompt repair
```

Не выполнены:

- unseen holdout;
- repeatability run;
- column/vertical-line experiment;
- `pdfplumber` table extraction;
- Canonical materialization;
- production activation;
- commit или push.
