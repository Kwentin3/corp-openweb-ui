# G5.102 — Gemini-native normalized table boxes

## Итог

**Coordinate contract подтверждён: `GEMINI_NORMALIZED_BOX2D_CONTRACT_VALIDATED`.**

Предыдущий провал действительно был в основном ошибкой контракта, а не отсутствием spatial signal у модели. После перехода на документированный Gemini `box_2d=[ymin,xmin,ymax,xmax]` в integer-диапазоне `0…1000` все восемь ответных boxes прошли strict validation и детерминированно спроецировались в PDF points.

Но полный bbox/count stage пока не проходит: `TABLE_INSTANCE_SEPARATION_INSUFFICIENT`. На одной странице модель снова объединила два визуально разных table regions в один box. Получено 8 предложений при 9 ожидаемых таблицах; новый unseen holdout не открывался.

## Проверенная гипотеза

G5.102 изменил только spatial contract и убрал визуальную сетку:

```text
verified full-page PNG
→ existing Gemini provider owner
→ box_2d [ymin, xmin, ymax, xmax], normalized 0..1000
→ strict research-only validator
→ deterministic inverse raster transform
→ PDF top-left points for evaluation only
```

Модель не получала:

- PDF-point coordinates;
- grid/rulers;
- image-pixel coordinates;
- `pdfplumber` settings;
- vertical column lines;
- text, rows, columns, values или финансовые роли.

Это соответствует официальному [Gemini object-detection contract](https://ai.google.dev/gemini-api/docs/generate-content/image-understanding#object-detection): координаты относятся ко всему изображению, нормализованы к `0…1000`, а преобразование в исходную систему выполняет клиент. Schema дополнительно содержала description, integer type и minimum/maximum; это соответствует рекомендациям [Gemini structured outputs](https://ai.google.dev/gemini-api/docs/generate-content/structured-output).

## Ownership и execution path

Переиспользованы существующие owners:

```text
PdfTableRasterFactory.create
→ PdfGridExperimentProviderFactory.create_for_openwebui
→ GeminiNormalizedTableBoxProjectionFactory.create
```

Новый projector research-only, не экспортирован из package API, не вызывает provider, не рендерит PDF, не читает source text и не выполняет table extraction. Он только валидирует документированный response и обращает уже проверенный `source_to_pixel_transform` существующего raster manifest.

G5.100 и G5.101 не изменялись. Product runtime, Canonical, Gate 3+ и generated bundles не затронуты.

## Preflight до внешнего вызова

До inference выполнены:

- byte-identical replay исходных G5.99 full-page renders;
- strict schema checks;
- exact synthetic normalized-image → PDF-points projection;
- rejection неправильного порядка осей, floats, значений вне `0…1000`, extra fields и неверного table order;
- verified full-page raster/transform checks;
- factory/closed-world anchors;
- проверки отсутствия grid, extraction и vertical-line paths.

Результат preflight: Ruff passed, 27 tests passed. Единственный промежуточный test failure был ошибкой самого assertion: он искал вычисленную многострочную константу как физически непрерывную строку в source. Проверка была сужена до anchor identifier и его смысловых частей; execution logic не менялась. Provider до исправления не вызывался.

## Development execution

Использованы те же девять уже открытых страниц G5.99:

- 4 positive pages;
- 5 negative pages;
- 9 ожидаемых таблиц;
- ровно 9 provider calls;
- одна попытка на страницу;
- retry = false;
- best-of-N = false;
- post-result prompt/schema correction = false;
- model = `models/gemini-3.5-flash`;
- thinking level = `minimal`.

Provider завершил все девять ответов штатно. Суммарно использовано 11 772 input tokens и 275 output tokens; provider-duration sum — 17 916 ms.

## Результаты

| Метрика | G5.101: PDF grid | G5.102: native `box_2d` |
|---|---:|---:|
| Expected tables | 9 | 9 |
| Proposed boxes | 8 | 8 |
| Pages с точным count | 8 / 9 | 8 / 9 |
| Invalid positive responses | 4 | **0** |
| Exact expressible truth regions | 0 / 7 | **5 / 7** |
| Regions с полным truth coverage | 0 / 7 | **6 / 7** |
| False boxes на negatives | 0 | 0 |

По страницам:

1. Обе таблицы M1 локализованы точно: frozen line-region coverage 100%, лишних parser lines 0.
2. Все три таблицы сложной IBKR continuation page локализованы точно: coverage 100%, лишних lines 0.
3. Две embedded tables на Merrill explainer page не выражаются contiguous parser-line truth. Их boxes проверены визуально: оба охватывают именно внутренние data grids, а не целые screenshots или соседний поясняющий текст.
4. На другой IBKR continuation page модель вернула один большой box вместо двух: он полностью накрыл оба table regions. Это не coordinate miss, а ошибка instance separation. В агрегате она создаёт 65 extraneous lines у первого ожидаемого региона и отсутствие второго proposal.
5. Все пять negative pages вернули пустой список; false positives — 0.

## Что доказано

Доказано, что для этой модели стабильная навигационная единица — не PDF point, прочитанный с картинки, а документированный normalized image box.

```text
MODEL: normalized image geometry
CODE: deterministic image → PDF transform
PARSER: source text / extraction authority
```

Axis-order ambiguity G5.101 устранена: invalid responses снизились с 4 до 0. Координатный signal стал адресуемым и проверяемым без grid overlay.

## Что не доказано

G5.102 не доказывает:

- надёжное разделение соседних или продолжающихся таблиц;
- column boundaries;
- пригодность `explicit_vertical_lines`;
- успешный `pdfplumber` extraction;
- Canonical materialization;
- repeatability;
- unseen generalization.

Особенно важно: один box, покрывающий две таблицы, геометрически валиден, но структурно недостаточен. Поэтому хороший coordinate contract нельзя автоматически считать готовым table contract.

## KISS verdict и scope stop

Сетка не нужна. Правильная минимальная граница выглядит так:

```text
Gemini-native normalized box_2d
→ one deterministic transform
→ strict PDF-point bbox
```

Это существенно проще и лучше G5.101. Однако development terminal остаётся:

```text
GEMINI_NORMALIZED_BOX2D_COUNT_INSUFFICIENT
```

Не выполнены и не разрешены:

- freeze G5.102;
- unseen holdout;
- повторный inference или prompt repair;
- vertical-line experiment;
- table extraction / Canonical materialization;
- production activation.

Следующий отдельный GOAL, если он будет разрешён, должен проверять только один оставшийся вопрос: можно ли надёжно разделять несколько визуальных table instances, сохраняя тот же frozen normalized `box_2d` protocol. Column geometry нельзя смешивать с этим тестом.
