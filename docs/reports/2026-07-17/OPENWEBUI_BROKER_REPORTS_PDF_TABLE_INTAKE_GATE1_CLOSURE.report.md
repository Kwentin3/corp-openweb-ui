# PDF Table Detection And Cropping Gate 1 — closure report

Дата: 2026-07-17

Статус отчёта: финальный; Gate 1 закрыт, stage delivery и operator visual review подтверждены.

## Короткий вывод

Реализован отдельный поддерживаемый Gate 1, который решает только одну задачу: находит области таблиц в PDF и превращает их в воспроизводимые приватные PNG-кандидаты с глобальными полями `8 %` по X и `8 %` по Y с каждой стороны.

Этот контур намеренно не строит строки, столбцы, ячейки или canonical JSON таблицы, не интерпретирует финансовые значения и не сравнивает две VLM. Dual-VLM материалы сохранены как исследовательский слой для следующих ворот.

Формальное закрытие подтверждено live stage proof и визуальным осмотром всех полученных кропов.

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

- новый Gate 1 набор: `10 passed`;
- Pipe/bundle и связанные проверки: `46 passed` в целевом наборе;
- полный сервисный регресс: `881 passed, 5 warnings`;
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

## Stage iteration 3: accepted operator proof

- repository revision: `7a960228ff8a3d1a3816c6d9b4c8f8c0c2c03750`;
- live Function bundle SHA-256: `20d2924386bd4950bda5990d834747c910a2f969d3b1e3f3208d7372c44f529b`;
- input: `bny-pershing-tax-sample.pdf`, SHA-256 `c26a89cf4b1e8950eac7fdcff8000b450caeee8c4711418713ab70d51269cce2`, 351004 bytes;
- Workspace Model: `test`, `base_model_id=broker_reports_gate1_pipe`;
- configured detector: `google_gemini / models/gemini-3.5-flash`, exact model match;
- `pdf_table_intake_policy_v3`, response contract v2;
- 8 страниц, 11 кандидатов, 0 failed pages;
- все 13 operator checks: passed;
- repo/live scoped Gate 1 parity: passed.

Именованные координаты устранили перестановку осей. На странице 3 четыре самостоятельные таблицы получили правильные левые границы около `x=0.034/0.488`; глобальный padding `0.08` довёл крайние кропы до страницы без per-table tuning. На страницах 4–8 больше нет отдельных заголовочных fragments, а continuation-таблицы содержат колонки, все видимые строки и итоги.

Оператор открыл все 11 PNG. Кандидаты признаны пригодными для downstream VLM: крайние подписи и числовые значения читаемы, totals не потеряны, боковые таблицы не склеены. На первом листе 1099-B (`candidate-009`) первая строка формового заголовка частично осталась за пределом кропа, но табличные заголовки колонок, все строки и итог сохранены. Это записано как известное ограничение визуального детектора, а не скрытое изменение 8-процентной политики.

Candidate identity и PNG SHA-256:

| Page | Candidate | PNG SHA-256 |
| --- | --- | --- |
| 2 | `pdftable_42dbea662fc41eb8a6e42b6d` | `0bdb2eb8d2851b65a1500ef4afcda35db7ea70de54991040a829d94267d3eb8b` |
| 3 | `pdftable_b7d5e60b252b9f6d3ce5c504` | `628d31d941e4bfeed738a9108a12218a1cba5bd9d38d4aba2efe85658b07b09f` |
| 3 | `pdftable_b15c204bb093a0669857270a` | `b9ffdd1c2d4b13887b068795932974f5d9279f5ce83799735c3ddf19c50cc3f4` |
| 3 | `pdftable_fac29e833a0151f9053b2f58` | `49d68a8357ed117edaa77e93f21c22962b70e106dbd93ee168fb1a03957c38d7` |
| 3 | `pdftable_6fb8d4179bb2bc51f79323d1` | `cb80e1abe07b1141c84e8a8c48127f8bd96ddf784fa2d2a071d5bbece5ee3c18` |
| 4 | `pdftable_41f3bf9206b3ad2238212b78` | `8dc46d8539682da3fc34e4f9d7c85c701eaa4cb00ab2cc4e4d02b82436cb28df` |
| 4 | `pdftable_4a3f2151f2d4f0ee27f9a6d0` | `345a3509bfcdb926531f938e8c2ebf539a8fcf1a3c372ae1753305c4016c5578` |
| 5 | `pdftable_519983679de77f14727ae272` | `091bf128701aa428bf234dee9566af51ea30fe0af634ce4647c76b3c482bc279` |
| 6 | `pdftable_d36e3d7335cd67f691185330` | `c896777feffb15e4667f22470b89c6b866fe89e903d2fb100adea0af1c3ef945` |
| 7 | `pdftable_1b32268e8c968e0720917cd8` | `3ca28172a0961f83c24fcc96386fb85f466d9e7c11d6ecb88e9948572e14116c` |
| 8 | `pdftable_b975bd3cf7f09eb894f999d9` | `bdee7d026cada0c5b8005f2f4a5bb310e5c130d89a3e93de1cad89b382f210d4` |

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

## Known limitations и соседние границы

- VLM detection остаётся вероятностным: строгая схема ловит malformed output, но не гарантирует идеальную геометрию на любом новом шаблоне. Поэтому runbook сохраняет обязательный visual review для новых representative formats.
- Stage proof подтверждает Gate 1 raster-candidate boundary, а не качество будущего canonical table JSON.
- Полный `--scope all` verifier ранее обнаружил независимый repo/live drift соседних Gate 2 source/domain bundles. Этот delivery его не менял и не объявляет full Stage 2 parity; Gate 1 scoped parity подтверждён отдельно.
- Metadata/source eligibility handoff для canary PDF остался blocked из-за `encrypted_file`, но `pdf_table_intake_contract.gate2_boundary_ready=true` и все 11 raster refs доступны. Это разные границы: таблицы готовы для Gate 2 normalizer, документ не объявлен пригодным для source-fact extraction.
- Dual-VLM consensus, canonical table JSON и финансовая интерпретация отложены в Gate 2 и не входят в это закрытие.

## Финальные статусы

- `GATE_1_TABLE_DETECTION_AND_CROPPING: CLOSED`
- `PRODUCT_OWNER_ACCEPTED: TRUE`
- `PRODUCT_ACCEPTANCE: ACCEPTED`
- `STAGE_DELIVERY: PROVEN`
- `DOWNSTREAM_BOUNDARY: READY_FOR_GATE_2`
