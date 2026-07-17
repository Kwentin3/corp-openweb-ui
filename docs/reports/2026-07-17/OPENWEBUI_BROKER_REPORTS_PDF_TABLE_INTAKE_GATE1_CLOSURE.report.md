# PDF Table Detection And Cropping Gate 1 — closure report

Дата: 2026-07-17

Статус отчёта: implementation и local regression завершены; stage delivery и operator visual review ещё не внесены.

## Короткий вывод

Реализован отдельный поддерживаемый Gate 1, который решает только одну задачу: находит области таблиц в PDF и превращает их в воспроизводимые приватные PNG-кандидаты с глобальными полями `8 %` по X и `8 %` по Y с каждой стороны.

Этот контур намеренно не строит строки, столбцы, ячейки или canonical JSON таблицы, не интерпретирует финансовые значения и не сравнивает две VLM. Dual-VLM материалы сохранены как исследовательский слой для следующих ворот.

Формальное закрытие нельзя объявлять до live stage proof и визуального осмотра полученных кропов.

## Реализованный путь

`OpenWebUI file refs -> broker_reports_gate1_pipe -> PdfTableIntakeRuntimeFactory -> page raster -> configured Gemini detector -> strict bbox validator -> deterministic 8 % crop -> ArtifactStore -> Gate 2 handoff refs`.

Поддерживаемый VLM-контракт допускает только:

- `table_presence`;
- список `outer_bbox_normalized` с отдельными полями `left_x`, `top_y`, `right_x`, `bottom_y`.

Любые дополнительные поля, неопределённая граница, неверные координаты или почти дублирующие области дают явный отказ.

## Поля и воспроизводимость

- `horizontal_padding_fraction = 0.08` ширины страницы на сторону;
- `vertical_padding_fraction = 0.08` высоты страницы на сторону;
- X и Y настраиваются независимо;
- итоговый прямоугольник ограничивается границами страницы;
- per-table override запрещён;
- одинаковые PDF, bbox, config и renderer дают одинаковые candidate id, bbox, PNG SHA-256 и manifest hash.

## Контракты

- `broker_reports_pdf_table_detection_request_v3`;
- `broker_reports_pdf_table_detection_response_v2`;
- `broker_reports_pdf_table_detection_attempt_v1`;
- `broker_reports_pdf_table_candidate_v1`;
- `broker_reports_pdf_table_intake_run_v1`;
- `pdf_table_candidate_raster_policy_v1`.

Gate 2 handoff дополнен `pdf_table_candidate_refs`, `pdf_table_candidate_refs_by_document` и `pdf_table_intake_contract`. PNG остаются private-case артефактами и не попадают в чат.

## Local proof

- новый Gate 1 набор: `8 passed`;
- Pipe/bundle и связанные проверки: `46 passed` в целевом наборе;
- полный сервисный регресс: `879 passed, 5 warnings`;
- предупреждения относятся к SWIG/PyMuPDF deprecation и не являются падениями;
- Ruff для изменённых Python-файлов: passed;
- compileall: passed;
- bundle собирается из репозиторных модулей, включая `pdf_table_intake_runtime`.

Тесты реально рендерят PDF через PyMuPDF, проверяют точные поля, clamping, повторяемость PNG, строгий отказ на лишнюю семантику, отсутствие success-кандидата после невалидного ответа, приватное сохранение и ссылки в handoff.

## Stage iteration 1: автоматический pass, визуальный fail

Ревизия `f3145ef31ab5b6eaf4c2a4d20e842ff375e827b5` была доставлена на stage. Gate 1 scoped parity прошёл; реальный публичный `bny-pershing-tax-sample.pdf` дал 13 кандидатов на 8 страницах без технических ошибок. Все SHA, ArtifactStore records, detector attempts и handoff refs совпали.

Тем не менее product acceptance не была принята. Визуальный осмотр показал, что кандидаты `005`, `007`, `009`, `010`, `011`, `012` и `013` обрезали крайние левые подписи; `011` дополнительно обрывал продолжение таблицы по высоте. 8-процентный padding был рассчитан правильно, но входной bbox Gemini описывал внутреннюю область данных вместо внешней границы.

Это доказало, что hash/contract pass недостаточен без operator review. Detector request повышен до v2: теперь он явно требует внешний контур, крайние подписи и колонки, полный заголовок, все видимые continuation-строки и итоги. Padding объявлен только резервом, а не заменой корректной границы. После этой правки требуется повтор того же stage PDF.

## Stage iteration 2: высота исправлена, неоднозначность осей подтверждена

Ревизия `68eb977225868878474d7805c4661337cece2cd8` повторно прошла технический proof на том же PDF: 13 кандидатов, 8 страниц, 0 технических ошибок. Продолжение большой таблицы в кандидате `011` теперь вошло по высоте полностью.

Визуальный осмотр всё же снова отклонил набор. Кандидаты `003`, `005`, `011`, `012` и `013` теряли левую часть; кандидат `007` был лишь отдельным заголовочным фрагментом, а не полной таблицей. На кандидате `011` причина проявилась однозначно: Gemini вернула значения, соответствующие порядку `top, left, bottom, right`, при том что позиционный массив контракта трактовался как `left, top, right, bottom`.

Это не ошибка 8-процентного padding и не основание для скрытого увеличения полей. Детекторный контракт повышен до request v3 / response v2: позиционный bbox-массив удалён, а оси передаются только именованными полями `left_x`, `top_y`, `right_x`, `bottom_y`. Legacy-массив теперь даёт явный contract failure. Следующий stage proof должен подтвердить исправление на изображениях; до него формальный статус остаётся pending.

## Factory и closed-world boundary

- Pipe использует `PdfTableIntakeRuntimeFactory`;
- provider connection берётся из текущей OpenWebUI provider infrastructure;
- Pipe и operator smoke не создают Gemini adapter напрямую;
- live Function содержит собранные репозиторные модули и pin `PyMuPDF==1.26.5`;
- stage verifier проверяет SHA bundle, valves, renderer version и factory markers.

## Документация

- [версионный контракт](../../stage2/contracts/BROKER_REPORTS_PDF_TABLE_INTAKE_GATE1.v1.md);
- [operator runbook](../../stage2/operations/BROKER_REPORTS_PDF_TABLE_INTAKE_GATE1_RUNBOOK.md);
- ссылки добавлены в Stage 2 README, context index, roadmap и Broker Reports blueprint.

## Незакрытые доказательства

До финального статуса нужны:

1. commit и push implementation revision;
2. обновление live OpenWebUI Function;
3. repo/live bundle SHA parity;
4. явные stage valves с `0.08/0.08`;
5. operator proof через Workspace Model и реальные PDF;
6. сохранённые candidate/attempt/handoff артефакты;
7. ручной визуальный осмотр PNG-кандидатов;
8. финальный parity check из чистого дерева.

## Текущие формальные статусы

- `GATE_1_TABLE_DETECTION_AND_CROPPING: PENDING_STAGE_PROOF`
- `PRODUCT_ACCEPTANCE: PENDING_OPERATOR_REVIEW`
- `STAGE_DELIVERY: NOT_YET_PROVEN`
- `DOWNSTREAM_BOUNDARY: LOCALLY_VERIFIED`
