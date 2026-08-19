# PDF Table Intake Gate 1: operator runbook

Дата: 2026-08-19

Статус: поддерживаемая операционная инструкция для закрытой локальной
PDF-возможности.

Authority: этот файл определяет deploy/proof/review procedure. Runtime behavior
и настройки определяет
[versioned contract](../contracts/BROKER_REPORTS_PDF_SOURCE_BOUND_TABLE_NORMALIZATION.v1.md),
а место локального gate в global Broker Reports pipeline —
[pipeline contract](../contracts/BROKER_REPORTS_PIPELINE_GATES.v1.md).

`Gate 1` в имени скриптов означает локальную границу `PDF -> source-bound
normalized tables` внутри global Broker Reports Gate 1. Это не global Gate 2
source-fact acceptance.

## Обычный пользовательский путь

1. Открыть Workspace Model «Брокерские отчёты».
2. Прикрепить PDF.
3. Отправить команду нормализации.
4. Pipe сохранит safe report в чате и private-case артефакты в ArtifactStore.

Пользователь не выбирает геометрию для каждой таблицы. VLM указывает только
отдельные области таблиц в координатах страницы. Детерминированный код переводит
координаты в систему PDF, а `pdfplumber` восстанавливает строки, столбцы и
исходные значения. Значения VLM и выбранные моделью настройки парсера не могут
стать источником данных. PNG, исходные байты и сырой ответ модели не публикуются
в чат или операторский proof.

## Deploy и scoped parity

Из корня репозитория:

```powershell
$revision = git rev-parse HEAD
python services/broker-reports-gate1-proof/scripts/live_release_broker_reports_atomic_stage.py --source-revision $revision
python services/broker-reports-gate1-proof/scripts/live_release_broker_reports_atomic_stage.py --source-revision $revision --apply --prove-rollback
python services/broker-reports-gate1-proof/scripts/live_verify_broker_reports_atomic_stage_release.py --source-revision $revision --rollback-identity-sha256 "<identity from release receipt>"
python services/broker-reports-gate1-proof/scripts/live_verify_broker_reports_stage2_delivery.py --scope gate1
```

Atomic release публикует ровно утверждённые Function bundles, доказывает
rollback и проверяет их чтением с сервера. Source-bound route включён; прежние
transcription, dual-VLM и research routes остаются выключенными. Отдельные
valves вручную не редактировать.

`--scope gate1` подтверждает PDF Table Intake и соседний global Gate 1 runtime,
но намеренно не объявляет parity global Gate 2 Functions.

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
- читает только безопасные метаданные run/attempt/source-unit/projection и
  handoff artifacts;
- проверяет, что числу найденных областей соответствует число source-bound
  таблиц, а их значения принадлежат `pdfplumber`, не VLM;
- подтверждает отсутствие retry, provider failover и legacy candidate route;
- сохраняет только безопасный `proof.json` в `local/stage2/...`;
- удаляет временные OpenWebUI chat и uploads.

`gate2_boundary_ready=true` означает, что проверенные private source units
готовы к существующей границе Gate 2. Это не означает, что любой PDF любого
брокера будет распознан без ошибок.

## Когда обязателен visual review

Автоматического `passed` недостаточно для гарантии на новый неизвестный формат.
Отдельное сравнение исходного PDF с восстановленной таблицей нужно:

- при первом принятии нового representative format;
- после смены detector model или provider profile;
- после изменения prompt, координатного контракта или стратегии `pdfplumber`;
- при расследовании geometry или structure regression.

Для обычного неизменённого production path техническая проверка подтверждает
контракт автоматически. Реальная ширина поддержки брокерских форматов
уточняется в тестовой эксплуатации продукта.

## Диагностика

- `pdf_table_detector_not_qualified`: stage не подтвердил выбранную модель или
  её возможности.
- `pdf_table_locator_response_shape_invalid`: модель вернула ответ вне строгой
  схемы.
- `pdf_table_locator_box_invalid`, `pdf_table_locator_box_out_of_range` или
  `pdf_table_locator_box_order_invalid`: координаты не прошли строгую проверку.
- `pdf_table_locator_page_failed`: страница не получила подтверждённых областей.
- `pdf_table_locator_region_native_table_not_found_failed`: внутри области
  `pdfplumber` не подтвердил таблицу; это корректный явный отказ.
- `pdf_table_locator_region_native_table_ambiguous_failed`: внутри одной области
  осталось несколько конкурирующих таблиц; автоматическое слияние запрещено.
- `pdf_table_intake_dpi_invalid`: DPI отличается от поддерживаемого `150`.
- `pdf_table_intake_page_budget_invalid`: page limit вне `1..512`.
- `pdf_table_intake_candidate_budget_invalid`: candidate limit вне `1..64`.
- `pdf_table_intake_padding_invalid` или
  `pdf_table_raster_padding_fraction_invalid`: legacy X/Y valve вне `0..0.25`;
  валидное значение принимается для совместимости, но не меняет locator region.
- `operator_repository_tree_not_clean`: proof запущен не из clean committed
  revision.

Не обходить `PdfTableIntakeRuntimeFactory` и не вызывать Gemini напрямую из
Pipe, smoke или shell-команды.

Принятое доказательство:
[implementation report](../../reports/2026-08-19/BROKER_REPORTS_PDF_SOURCE_BOUND_NORMALIZATION_IMPLEMENTATION.report.md).

## DOC32 canonical normalization handoff

Table intake remains Full Evidence and does not publish consumer-visible
document meaning by itself. The Gate 2 PDF adapter must consume validated text
units and table projections through `CanonicalNormalizerFactory`, represent
every ready table exactly once, terminally classify non-ready projections, and
emit `canonical_pdf_completeness_v1`. A non-empty PDF with zero logical nodes or
less than 100% source-atom accounting is a terminal failure and must not change
the active pointer. Parser/VLM payloads and page rasters remain private
resolver-backed evidence; a projector may consume only `CanonicalReader`
output.
