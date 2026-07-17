# PDF Table Intake Gate 1: operator runbook

Дата: 2026-07-17

Статус: поддерживаемая операционная инструкция для закрытой локальной
PDF-возможности.

Authority: этот файл определяет deploy/proof/review procedure. Runtime behavior
и настройки определяет
[versioned contract](../contracts/BROKER_REPORTS_PDF_TABLE_INTAKE_GATE1.v1.md),
а место локального gate в global Broker Reports pipeline —
[architecture entry](../blueprints/BROKER_REPORTS_PDF_TABLE_INTAKE.blueprint.md).

`Gate 1` в имени скриптов означает локальную границу `PDF -> private raster
candidates` внутри global Broker Reports Gate 1. Это не global Gate 2
source-fact acceptance.

## Обычный пользовательский путь

1. Открыть Workspace Model «Брокерские отчёты».
2. Прикрепить PDF.
3. Отправить команду нормализации.
4. Pipe сохранит safe report в чате и private-case артефакты в ArtifactStore.

Пользователь не выбирает поля для каждой таблицы. Принятые stage values:
`0.08` ширины и `0.08` высоты страницы с каждой стороны. PNG и исходные байты
не публикуются в чат.

## Deploy и scoped parity

Из корня репозитория:

```powershell
python services/broker-reports-gate1-proof/scripts/build_openwebui_pipe_bundle.py --target gate1
python services/broker-reports-gate1-proof/scripts/live_update_function_and_passport_prompt.py
python services/broker-reports-gate1-proof/scripts/live_verify_broker_reports_stage2_delivery.py --scope gate1
```

Update-скрипт публикует Function bundle, проверяет SHA и явно выставляет все
принятые PDF Table Intake valves. Старые structural/semantic shadows остаются
выключенными.

Изменение только валидного Function valve применяется к следующему запросу без
пересборки bundle и рестарта OpenWebUI. Для принятой stage-конфигурации не
редактировать отдельный valve вручную: повторить update и scoped verifier,
чтобы сохранить полный configuration proof.

`--scope gate1` подтверждает PDF Table Intake и соседний global Gate 1 runtime,
но намеренно не объявляет parity global Gate 2 Functions. Полный verifier без
`--scope` — отдельная общая проверка; его независимый Gate 2 drift нельзя
приписывать этому локальному gate.

## Operator proof на representative PDF

Запускать только из clean committed tree:

```powershell
python services/broker-reports-gate1-proof/scripts/live_pdf_table_intake_gate1_operator_proof.py `
  --pdf "<путь-к-representative-pdf>" `
  --pdf "<путь-ко-второму-representative-pdf>"
```

`--pdf` можно повторять; каждый файл проверяется в одном proof run. Скрипт:

- подтверждает, что Workspace Model оборачивает `broker_reports_gate1_pipe`;
- загружает PDF в OpenWebUI с `process=false`;
- вызывает обычный `/api/chat/completions`;
- читает run/candidate/attempt/handoff artifacts;
- сверяет PNG SHA, contract versions, 8-процентные поля и raster refs;
- сохраняет PNG в `local/stage2/...` для визуального осмотра;
- удаляет временные OpenWebUI uploads.

`gate2_boundary_ready=true` в результате означает готовность raster refs для
downstream table normalizer. Отдельно проверить global metadata/source
eligibility; он может быть `blocked` и не опровергает успешный crop proof.

## Когда обязателен visual review

Автоматического `passed` недостаточно для product acceptance. Оператор обязан
просмотреть все сохранённые PNG:

- при первом принятии нового representative format;
- после смены detector model или provider profile;
- после изменения prompt, request/response contract, renderer, DPI или padding;
- при повторном formal closure или расследовании geometry regression.

Для обычного неизменённого production path технические проверки продолжают
работать на каждом запуске; новый closure report не создаётся для каждого PDF.

При visual review подтвердить:

- внутри находится ожидаемая таблица;
- табличные заголовки, крайние подписи, строки и итоги не срезаны;
- добавленные поля разумны;
- crop не превратился без необходимости в почти целую страницу.

Итог, representative corpus и конкретные ограничения фиксируются в датированном
acceptance/closure report. Один успешный PDF не является доказательством
универсальной точности на всех брокерских шаблонах.

## Диагностика

- `pdf_table_detector_not_qualified`: stage не подтвердил выбранную модель или
  её возможности.
- `pdf_table_detector_boundary_uncertain`: VLM не смогла надёжно очертить
  таблицу; это корректный явный отказ.
- `pdf_table_detector_output_shape_invalid`: модель вернула ответ вне строгой
  схемы.
- `pdf_table_intake_dpi_invalid`: DPI отличается от поддерживаемого `150`.
- `pdf_table_intake_page_budget_invalid`: page limit вне `1..512`.
- `pdf_table_intake_candidate_budget_invalid`: candidate limit вне `1..64`.
- `pdf_table_intake_padding_invalid` или
  `pdf_table_raster_padding_fraction_invalid`: X/Y padding вне `0..0.25`.
- `pdf_table_raster_dimension_budget_exceeded`: crop превышает размерный лимит.
- `operator_repository_tree_not_clean`: proof запущен не из clean committed
  revision.

Не обходить `PdfTableIntakeRuntimeFactory` и не вызывать Gemini напрямую из
Pipe, smoke или shell-команды.

Принятое доказательство:
[closure report](../../reports/2026-07-17/OPENWEBUI_BROKER_REPORTS_PDF_TABLE_INTAKE_GATE1_CLOSURE.report.md).
