# PDF Table Intake Gate 1: runbook

Дата: 2026-07-17

## Обычный пользовательский путь

1. Открыть Workspace Model «Брокерские отчёты».
2. Прикрепить PDF.
3. Отправить команду нормализации.
4. Pipe сохранит безопасный отчёт в чате и приватные Gate 1 артефакты в ArtifactStore.

Пользователь не выбирает поля для каждой таблицы. На stage они глобально равны `8 %` ширины и `8 %` высоты страницы с каждой стороны.

## Deploy

Из корня репозитория:

```powershell
python services/broker-reports-gate1-proof/scripts/build_openwebui_pipe_bundle.py --target gate1
python services/broker-reports-gate1-proof/scripts/live_update_function_and_passport_prompt.py
python services/broker-reports-gate1-proof/scripts/live_verify_broker_reports_stage2_delivery.py --scope gate1
```

Update-скрипт публикует собранный Function bundle, проверяет совпадение SHA и явно выставляет рабочие valves Gate 1. Старые structural/semantic shadows остаются выключенными.

Режим `--scope gate1` намеренно не объявляет parity соседних Gate 2 Functions. Полный режим без `--scope` остаётся отдельной общей проверкой и может обнаружить их независимый дрейф.

## Operator proof на реальном PDF

Запускать только из чистого committed tree:

```powershell
python services/broker-reports-gate1-proof/scripts/live_pdf_table_intake_gate1_operator_proof.py `
  --pdf "<путь-к-представительному-real-pdf>" `
  --pdf "<путь-ко-второму-real-pdf>"
```

Скрипт:

- проверяет, что Workspace Model действительно оборачивает `broker_reports_gate1_pipe`;
- загружает PDF в OpenWebUI с `process=false`;
- вызывает обычный `/api/chat/completions`;
- читает сохранённые run/candidate/attempt/handoff артефакты;
- сверяет SHA PNG, версии контрактов, 8-процентные поля и ссылки handoff;
- сохраняет PNG в `local/stage2/...` для визуального осмотра;
- удаляет временные OpenWebUI uploads.

## Обязательная визуальная проверка

Технического `passed` недостаточно. Оператор должен открыть сохранённые PNG и подтвердить:

- внутри находится ожидаемая таблица;
- заголовки и крайние подписи не срезаны;
- добавленные поля разумны;
- кроп не превратился в почти целую страницу без необходимости.

Итог и конкретные кандидаты фиксируются в датированном closure report.

## Диагностика

- `pdf_table_detector_not_qualified`: stage не подтвердил выбранную модель или её возможности.
- `pdf_table_detector_boundary_uncertain`: VLM не смогла надёжно очертить таблицу; это корректный явный отказ.
- `pdf_table_detector_output_shape_invalid`: модель вернула поля вне строгой схемы.
- `pdf_table_raster_padding_fraction_invalid`: X/Y padding вне допустимого диапазона `0..0.25`.
- `pdf_table_raster_dimension_budget_exceeded`: кроп превышает лимит размеров.
- `operator_repository_tree_not_clean`: operator proof запущен не из зафиксированной ревизии.

Не обходить factory и не вызывать Gemini напрямую из Pipe, smoke или shell-команды.
