# PDF Table Intake Gate 1 runtime/data contract v2

Дата: 2026-08-04

Статус: `MAINTAINED`; заменяет v1 для текущего runtime. [v1](./BROKER_REPORTS_PDF_TABLE_INTAKE_GATE1.v1.md)
сохранён как исторический контракт fixed-page-padding пути.

Authority: этот файл определяет текущую детерминированную границу
`candidate bbox -> canonical table region -> private PNG`. Место локального
PDF Table Intake внутри global Gate 1 определяет
[архитектурный вход](../blueprints/BROKER_REPORTS_PDF_TABLE_INTAKE.blueprint.md).

## Граница изменения

Detector по-прежнему только предлагает внешний bbox таблицы. DOC17 не меняет
detector prompt, request/response schema, provider profile, model, число вызовов
или downstream table normalization. После строгой проверки предложения
единственный `PdfTableRasterFactory` детерминированно вычисляет одну
`table_region` и использует её для:

- image crop;
- будущего source-text projection;
- provenance;
- diagnostics.

Вторая crop-authority, consumer-local padding и повторное вычисление геометрии
запрещены.

## Canonical Table Crop Contract

`table_region` обязана включать целиком видимую логическую таблицу:

- заголовок таблицы и многоуровневые column headers, если они визуально
  принадлежат таблице;
- крайние левые и правые колонки;
- все видимые строки, continuation-строки и totals;
- непосредственно присоединённые notes/footnotes.

`table_region` обязана исключать:

- соседние таблицы и их заголовки;
- footer, page number и повторяющийся page furniture;
- неприсоединённый narrative text;
- любой чужой фрагмент, попавший в detector bbox.

Fixed global/page-relative padding не применяется. Legacy X/Y padding valves
пока принимаются для совместимости конфигурации, но записываются как
`legacy_configuration_retained_not_applied` и не влияют на crop.
Минимальный внешний raster margin применяется только после структурного
разрешения региона и не заменяет его.

Разрешение основано на общих наблюдаемых свойствах: coordinate-space
translation, text geometry, вертикальные компоненты, расстояния, табличная
плотность, непрерывность повторяемых числовых колонок, полные границы частично
пересечённых text lines, header/caption bands, цифровые и алфавитные attached
note bands, prose barriers, page-furniture isolation и границы ruled regions.
Продолжение нижней границы bounded и прекращается на первой полосе, которая не
подтверждена той же числовой сеткой или тем же text block. Исключения по issuer,
document, table ID, page number или фиксированным координатам запрещены.
Semantic cell reconstruction и финансовая интерпретация не выполняются.

## Координаты и детерминизм

Источник bbox и page bbox проверяются до crop. Поддерживаются identity и
однократная MediaBox-to-CropBox translation. Координаты вне страницы
clamp-ятся после установленного transform. Неоднозначная или неподдерживаемая
rotation/coordinate-space комбинация не угадывается и должна отказать.

Для одинаковых PDF bytes, page, candidate bbox, candidate strategy, config,
PyMuPDF и policy version детерминированы `table_region`, PNG bytes, PNG SHA-256
и manifest hash. Финальный raster строится только для разрешённого региона;
full-page final render запрещён.

## Статусы и failure semantics

Ровно один terminal crop status обязателен:

| Status | Значение | PNG |
| --- | --- | --- |
| `CROP_CLEAN` | регион однозначно разрешён и прошёл структурные проверки | создаётся |
| `CROP_AMBIGUOUS` | два или более сопоставимых табличных компонента нельзя безопасно разделить | не создаётся |
| `CROP_BLOCKED` | coordinate space, geometry, page, checksum или required text geometry не подтверждены | не создаётся |

`CROP_CLEAN` не является заявлением о правильности распознанных значений.
False-clean запрещён: сомнение закрывается terminal отказом, без retry, fallback
или скрытого расширения до страницы.

## Версии

- detector request: `broker_reports_pdf_table_detection_request_v3` (без изменений);
- detector response: `broker_reports_pdf_table_detection_response_v2` (без изменений);
- detection attempt: `broker_reports_pdf_table_detection_attempt_v1`;
- PNG candidate: `broker_reports_pdf_table_candidate_v1`;
- intake run: `broker_reports_pdf_table_intake_run_v1`;
- intake policy: `pdf_table_intake_policy_v4`;
- candidate raster policy: `pdf_table_candidate_raster_policy_v4`;
- canonical region schema: `broker_reports_canonical_table_region_v1`;
- canonical region policy: `canonical_table_region_policy_v3`.

Candidate manifest хранит исходный и transformed bbox, один resolved bbox,
coordinate transform, terminal status, reason codes, безопасные diagnostics,
shared consumers, PNG identity и признак отсутствия per-table exception.

## Privacy и ресурсные границы

Исходный PDF, page images, crops, extracted text и читаемые visual-gold данные
остаются private-case artifacts вне Git. Safe evidence содержит только
allowlisted IDs, классы, counts, версии, хэши и terminal verdicts.

Resolver работает page/candidate-bounded, без LLM и network вызовов. Proof
обязан учитывать число render operations, full-page final renders, время,
peak memory и размер crop. Изменение contract/policy требует synthetic
geometry regressions, visual review реального корпуса, независимый frozen
holdout, deterministic replay, privacy scan и полный relevant service suite.

## Вне scope

Контракт не подтверждает универсальную точность detector, canonical cells,
source facts, Gate 2, налоговые выводы или customer acceptance. Следующий
image-only normalization эксперимент разрешён только после отдельного
подтверждения DOC17 evidence.
