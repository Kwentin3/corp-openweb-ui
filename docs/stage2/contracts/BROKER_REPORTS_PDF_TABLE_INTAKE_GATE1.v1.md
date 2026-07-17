# PDF Table Intake Gate 1 runtime/data contract

Дата: 2026-07-17

Статус: `CLOSED`; реализация, scoped stage parity и operator proof подтверждены
2026-07-17.

Authority: этот файл определяет поддерживаемое runtime-поведение, версии данных,
настройки, privacy и failure semantics. Место компонента и значение локального
имени `Gate 1` определяет
[архитектурный вход](../blueprints/BROKER_REPORTS_PDF_TABLE_INTAKE.blueprint.md).

## Локальная граница

`PDF Table Intake Gate 1` — локальное имя дочерней PDF-возможности внутри
global Broker Reports Gate 1 `Document Intake & Normalization`. Это не Stage 2
Implementation Gate 1 и не отдельный глобальный продуктовый Gate 1.

Поддерживаемый путь:

```text
PDF -> страницы PNG -> VLM находит внешние области таблиц
-> строгая проверка bbox -> детерминированные поля и crop
-> приватные PNG-кандидаты -> refs для downstream table normalizer
```

VLM не читает значения таблицы и не строит JSON с ячейками. Она возвращает
только:

- наличие таблицы: `present`, `absent` или `uncertain`;
- один или несколько внешних прямоугольников в нормализованных координатах
  страницы.

Код строго проверяет ответ, сортирует области, рассчитывает поля, рендерит PNG,
считает контрольные суммы и сохраняет артефакты.

## Вход и выход

Вход runtime:

- обычные OpenWebUI file refs из запроса Workspace Model;
- исходные байты PDF под разрешённой private-case boundary;
- текущие Function valves;
- provider connection из OpenWebUI provider infrastructure.

Успешный выход:

- safe summary запуска без исходных байтов и PNG;
- приватные detection-attempt и PNG-candidate records;
- `pdf_table_candidate_refs` и `pdf_table_candidate_refs_by_document`;
- версионный блок `pdf_table_intake_contract` в `gate2_handoff_v0`.

Выход не содержит строки, столбцы, ячейки, canonical table JSON, dual-VLM
consensus, source facts или финансовую интерпретацию.

## Глобальные поля

Поля задаются один раз для всего запуска:

- по горизонтали: `8 %` ширины страницы с каждой стороны;
- по вертикали: `8 %` высоты страницы с каждой стороны.

Это доля размера страницы, а не найденной таблицы. У границы страницы
прямоугольник обрезается по странице. Per-table override запрещён. Padding —
резерв вокруг корректной внешней границы, а не замена правильного bbox.

## Конфигурация

| Valve | Bundle default | Accepted value | Accepted stage value |
| --- | --- | --- | --- |
| `pdf_table_intake_enabled` | `false` | boolean | `true` |
| `pdf_table_intake_provider_profile` | `google_gemini` | configured OpenWebUI provider profile | `google_gemini` |
| `pdf_table_intake_model_id` | `models/gemini-3.5-flash` | qualified exact model id | `models/gemini-3.5-flash` |
| `pdf_table_intake_dpi` | `150` | только `150` | `150` |
| `pdf_table_intake_maximum_pages` | `64` | `1..512` | `64` |
| `pdf_table_intake_maximum_candidates_per_page` | `32` | `1..64` | `32` |
| `pdf_table_intake_horizontal_padding_fraction` | `0.08` | `0..0.25` | `0.08` |
| `pdf_table_intake_vertical_padding_fraction` | `0.08` | `0..0.25` | `0.08` |

Отсутствующие valves получают bundle defaults; поэтому отсутствующий
`pdf_table_intake_enabled` не включает возможность. Неверный тип или значение
вне диапазона отклоняются Pydantic/runtime factory до provider call. Stage
update-скрипт выставляет все принятые значения явно и verifier сверяет их с
ожидаемыми.

Изменение валидного valve не требует пересборки Function bundle или рестарта
OpenWebUI: оно применяется к следующему запросу. Deploy/update route всё равно
обязан повторно проверить bundle SHA и полную stage-конфигурацию по runbook.

## Версии контрактов

- detector request: `broker_reports_pdf_table_detection_request_v3`;
- detector response: `broker_reports_pdf_table_detection_response_v2`;
- detection attempt: `broker_reports_pdf_table_detection_attempt_v1`;
- PNG candidate: `broker_reports_pdf_table_candidate_v1`;
- intake run: `broker_reports_pdf_table_intake_run_v1`;
- intake policy: `pdf_table_intake_policy_v3`;
- candidate raster policy: `pdf_table_candidate_raster_policy_v1`.

Request v3 требует внешний контур: крайние подписи и колонки, полный заголовок,
все видимые continuation-строки и итоги. Response v2 запрещает позиционный
массив: bbox передаётся именованными полями `left_x`, `top_y`, `right_x`,
`bottom_y`.

PNG-candidate record хранит provenance исходного документа и страницы,
найденный и итоговый bbox, применённые поля, DPI, размеры, PNG SHA-256, версию
рендера и идентичность детектора. Байты PNG остаются private-case артефактом и
не попадают в чат.

## Вероятностное и детерминированное

Вероятностны table presence и внешний bbox, предложенные VLM. Строгая схема
отсекает malformed output, но не доказывает идеальную геометрию для любого
шаблона.

При одинаковых PDF, координатах, конфигурации и версии рендера детерминированы:

- порядок и идентификатор кандидатов;
- итоговый bbox и размеры PNG;
- PNG SHA-256 и manifest hash;
- ссылки и версионные метаданные.

Порядок bbox в ответе VLM не влияет на итоговый порядок: код сортирует области
сверху вниз и слева направо.

## Privacy и явные отказы

Исходный PDF, page rasters, candidate PNG и model attempts остаются приватными.
Чат получает только безопасную сводку без исходного содержимого.

Успешный кандидат не создаётся, если:

- VLM вернула `uncertain`;
- schema version или `request_id` не совпали;
- координаты выходят за диапазон, образуют пустой bbox или почти дублируются;
- модель, provider, PyMuPDF version или лимиты не прошли проверку;
- исходный PDF или его SHA-256 не совпали;
- размер страницы или PNG превышает лимит.

Ошибка фиксируется как `failed`. Частичный успех не выдаётся за готовую
raster-candidate boundary.

## Downstream boundary

`pdf_table_intake_contract.gate2_boundary_ready=true` означает только, что
локальный intake run завершён и versioned raster refs доступны downstream table
normalizer. Название поля сохранено ради совместимости текущего runtime
контракта.

Этот флаг не подтверждает global document source eligibility, canonical table
reconstruction или завершение global Broker Reports Gate 2. Например,
metadata/source eligibility может оставаться `blocked`, когда raster-кандидаты
уже готовы. Эти статусы должны читаться независимо.

Canonical reconstruction, dual-VLM comparison и financial source-fact
extraction регулируются отдельными downstream контрактами и не являются
условием успеха PDF Table Intake.

## Нативная интеграция

Единственный поддерживаемый live entrypoint —
`PdfTableIntakeRuntimeFactory.create_for_openwebui`. Pipe не создаёт provider
adapter и renderer напрямую. Live proof идёт через Workspace Model с
`base_model_id=broker_reports_gate1_pipe` и `/api/chat/completions` с обычными
OpenWebUI file refs.

Операционная инструкция:
[operator runbook](../operations/BROKER_REPORTS_PDF_TABLE_INTAKE_GATE1_RUNBOOK.md).

## Закрывающее доказательство

- repository revision: `7a960228ff8a3d1a3816c6d9b4c8f8c0c2c03750`;
- live bundle SHA-256: `20d2924386bd4950bda5990d834747c910a2f969d3b1e3f3208d7372c44f529b`;
- representative PDF SHA-256: `c26a89cf4b1e8950eac7fdcff8000b450caeee8c4711418713ab70d51269cce2`;
- 8 страниц, 11 приватных кандидатов, 0 failed pages;
- все 13 automated operator checks прошли;
- operator просмотрел все 11 PNG и принял raster-candidate boundary.

Proof подтверждает поддерживаемый путь на этом representative PDF, но не
универсальную точность VLM на любом будущем шаблоне. Известное принятое
ограничение: у одного кандидата частично отсутствует первая строка формового
заголовка, а табличные колонки, строки и итоги сохранены.

Датированный итог:
[closure report](../../reports/2026-07-17/OPENWEBUI_BROKER_REPORTS_PDF_TABLE_INTAKE_GATE1_CLOSURE.report.md).
