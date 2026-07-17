# PDF Table Intake Gate 1

Дата: 2026-07-17

Статус: `CLOSED`; реализация, stage parity и operator proof подтверждены 2026-07-17.

## Что делает Gate 1

Поддерживаемый путь выглядит так:

`PDF -> страницы PNG -> VLM находит области таблиц -> код добавляет поля -> приватные PNG-кандидаты -> ссылки для Gate 2`.

VLM в этом этапе не читает значения таблицы и не строит JSON с ячейками. Она возвращает только:

- есть ли на странице таблица: `present`, `absent` или `uncertain`;
- один или несколько прямоугольников в нормализованных координатах страницы.

Детерминированный код строго проверяет ответ, сортирует области, рассчитывает поля, рендерит PNG и считает контрольные суммы.

## Глобальные поля

Поля задаются один раз для всего запуска:

- по горизонтали: `8 %` ширины страницы с каждой стороны;
- по вертикали: `8 %` высоты страницы с каждой стороны.

Это доля размера страницы, а не доля найденной таблицы. У границы страницы прямоугольник обрезается по странице. Для отдельной таблицы нельзя незаметно задать другое значение.

Настройки OpenWebUI Function:

| Valve | Stage value |
| --- | --- |
| `pdf_table_intake_enabled` | `true` |
| `pdf_table_intake_provider_profile` | `google_gemini` |
| `pdf_table_intake_model_id` | `models/gemini-3.5-flash` |
| `pdf_table_intake_dpi` | `150` |
| `pdf_table_intake_maximum_pages` | `64` |
| `pdf_table_intake_maximum_candidates_per_page` | `32` |
| `pdf_table_intake_horizontal_padding_fraction` | `0.08` |
| `pdf_table_intake_vertical_padding_fraction` | `0.08` |

## Версии контрактов

- запрос детектору: `broker_reports_pdf_table_detection_request_v3`;
- ответ детектора: `broker_reports_pdf_table_detection_response_v2`;
- журнал попытки: `broker_reports_pdf_table_detection_attempt_v1`;
- PNG-кандидат: `broker_reports_pdf_table_candidate_v1`;
- запуск Gate 1: `broker_reports_pdf_table_intake_run_v1`;
- политика рендера: `pdf_table_candidate_raster_policy_v1`.

Request v3 требует именно внешнюю границу: крайние подписи и колонки, полный заголовок, все видимые continuation-строки и итоги. Response v2 запрещает позиционный массив координат: каждая внешняя граница передаётся четырьмя именованными полями `left_x`, `top_y`, `right_x`, `bottom_y`. Это исключает неоднозначность порядка осей. Padding остаётся резервом и не считается заменой правильной границы.

PNG-кандидат хранит исходный документ и страницу, найденный и итоговый прямоугольники, применённые поля, DPI, размеры, SHA-256 PNG, версию рендера и идентичность детектора. Байты PNG остаются приватным артефактом и не попадают в чат.

## Детерминизм

При одинаковых PDF, координатах, конфигурации и версии рендера должны совпасть:

- порядок кандидатов;
- идентификатор кандидата;
- итоговый прямоугольник;
- размеры PNG;
- SHA-256 PNG;
- hash манифеста.

Порядок прямоугольников в ответе VLM не влияет на порядок кандидатов: код сортирует их сверху вниз и слева направо.

## Явные отказы

Gate 1 не создаёт успешный кандидат, если:

- VLM вернула `uncertain`;
- схема ответа или `request_id` не совпали;
- координаты выходят за диапазон или образуют пустой прямоугольник;
- почти одинаковые области создают неоднозначность;
- модель, провайдер, версия PyMuPDF или лимиты не прошли проверку;
- исходный PDF или его SHA-256 не совпали;
- размер страницы или PNG превышает лимит.

Ошибка фиксируется как `failed`; частичный успех не выдаётся за готовую границу Gate 2.

## Граница с Gate 2

Gate 2 получает ссылки `pdf_table_candidate_refs` и версионный блок `pdf_table_intake_contract` в handoff. Gate 1 не передаёт строки, столбцы, ячейки, каноническую таблицу, финансовый смысл или консенсус двух VLM.

Dual-VLM сравнение остаётся отдельным исследовательским слоем для следующих ворот и не является условием успеха этого Gate 1.

## Нативная интеграция

Поддерживаемый entrypoint — `PdfTableIntakeRuntimeFactory.create_for_openwebui`. Pipe не создаёт provider adapter и renderer напрямую. Live proof обязан идти через Workspace Model, чей `base_model_id` равен `broker_reports_gate1_pipe`, и через `/api/chat/completions` с обычными OpenWebUI file refs.

Операционная инструкция: [BROKER_REPORTS_PDF_TABLE_INTAKE_GATE1_RUNBOOK](../operations/BROKER_REPORTS_PDF_TABLE_INTAKE_GATE1_RUNBOOK.md).

## Закрывающее доказательство

- repository revision: `7a960228ff8a3d1a3816c6d9b4c8f8c0c2c03750`;
- live bundle SHA-256: `20d2924386bd4950bda5990d834747c910a2f969d3b1e3f3208d7372c44f529b`;
- representative PDF SHA-256: `c26a89cf4b1e8950eac7fdcff8000b450caeee8c4711418713ab70d51269cce2`;
- 8 страниц, 11 приватных кандидатов, 0 failed pages;
- все 13 автоматических operator checks прошли;
- оператор просмотрел все 11 PNG и подтвердил пригодность строк, колонок, крайних подписей и итогов для Gate 2.

Датированный итог: [closure report](../../../reports/2026-07-17/OPENWEBUI_BROKER_REPORTS_PDF_TABLE_INTAKE_GATE1_CLOSURE.report.md).
