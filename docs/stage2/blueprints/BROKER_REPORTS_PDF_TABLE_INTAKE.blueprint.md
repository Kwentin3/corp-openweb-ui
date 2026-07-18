# Broker Reports PDF Table Intake

Дата: 2026-07-17

Статус: `MAINTAINED`; локальный PDF Table Intake Gate 1 закрыт и поддерживается.

Это главный архитектурный вход для PDF Table Intake. Он объясняет место
компонента, его границы и иерархию документации. Точное runtime-поведение,
версии схем и настройки определяет
[версионный контракт](../contracts/BROKER_REPORTS_PDF_TABLE_INTAKE_GATE1.v1.md).

## Задача и поддерживаемый путь

Компонент превращает PDF в приватные растровые кандидаты таблиц, пригодные для
последующей нормализации:

```text
OpenWebUI file refs
-> page rasterization
-> VLM table-region detection
-> strict bbox validation
-> deterministic configurable padding and crop
-> private versioned PNG candidates
-> raster-candidate refs for the downstream table normalizer
```

VLM только предполагает, есть ли на странице таблица, и возвращает её внешний
прямоугольник. Код проверяет ответ, детерминированно сортирует области, добавляет
поля, рендерит PNG, считает хэши и сохраняет артефакты.

## Как читать слово Gate

В репозитории существуют три разных уровня, и их номера нельзя смешивать:

| Обозначение | Значение |
| --- | --- |
| [Stage 2 Implementation Gates](../IMPLEMENTATION_GATES.md) | Общие организационные условия Stage 2. Это не нумерация Broker Reports pipeline. |
| Broker Reports global Gate 1 | Весь этап `Document Intake & Normalization`: приём, техническое профилирование, приватные артефакты и проверяемый handoff. |
| PDF Table Intake Gate 1 | Исторически закрепившееся локальное имя этой узкой PDF-возможности внутри global Broker Reports Gate 1. `Gate 1` здесь означает локальную границу `PDF -> raster candidates`, а не новый глобальный продуктовый этап. |
| Broker Reports global Gate 2 | Извлечение source facts из допущенных и проверенных артефактов global Gate 1. Его готовность этим компонентом не объявляется. |

Фразы `Gate 2 handoff` и `gate2_boundary_ready` в runtime-артефактах PDF Table
Intake означают только, что raster-кандидаты успешно созданы и их ссылки можно
передать следующему потребителю таблиц. Они не означают, что:

- документ прошёл global source eligibility;
- восстановлены строки, столбцы и ячейки;
- получен canonical table JSON;
- выполнен dual-VLM consensus;
- global Broker Reports Gate 2 завершён.

## Место в общей архитектуре

Полную последовательность и владение определяет
[каноническая архитектура Broker Reports](BROKER_REPORTS_GATE_ARCHITECTURE.md).

```text
Broker Reports global Gate 1: Document Intake & Normalization
  -> PDF Table Intake local gate: PDF -> private raster candidates
  -> downstream table normalizer: candidates -> validated canonical table
  -> validated normalized source units
Broker Reports global Gate 2: source-fact extraction
  -> Broker Reports global Gate 3: case assembly/reconciliation
  -> Broker Reports global Gate 4: tax/declaration/output preparation
```

PDF Table Intake является дочерней возможностью broader normalization stage.
Его выход потребляет downstream table normalizer. Canonical reconstruction
должен сохранить provenance до исходного PDF, а уже проверенные нормализованные
единицы могут участвовать в global Gate 2 source-fact extraction.

## Вход, выход и владение

| Boundary | Принимает | Производит | Не производит |
| --- | --- | --- | --- |
| PDF Table Intake | OpenWebUI file refs на PDF и разрешённый доступ к исходным байтам | run/attempt manifests, приватные PNG-кандидаты, `pdf_table_candidate_refs`, версионный блок `pdf_table_intake_contract` | cell JSON, финансовые факты, итоговый документ |
| Downstream table normalizer | Приватные raster-candidate refs и provenance | Проверенную структуру таблицы и canonical representation по отдельному контракту | Автоматическое доказательство source eligibility всего документа |
| Global Gate 2 | Допущенные артефакты global Gate 1 | Source facts с evidence binding | Изменение геометрии исходных кропов |

Приватные PNG и исходные байты не публикуются в чат. В чат попадает только
безопасная сводка. Неопределённая или невалидная область даёт явный отказ, а не
частично успешный кандидат.

## Что детерминировано

Вероятностная часть — ответ VLM о наличии и внешней границе таблицы.

Детерминированная часть при фиксированных PDF, координатах, конфигурации и
версиях — валидация схемы и bbox, сортировка, поля, clamping к странице,
рендер, candidate identity, PNG SHA-256, manifest hash и сохранение ссылок.

Глобальные stage-поля равны `0.08` ширины страницы по X и `0.08` высоты страницы
по Y с каждой стороны. Это резерв вокруг корректной внешней границы, а не способ
исправить произвольный неверный bbox.

## Иерархия документов

| Приоритет | Документ | Что он определяет |
| --- | --- | --- |
| 1 | Этот архитектурный вход | Место компонента, локальную нумерацию, ownership и границы ответственности. |
| 2 | [Versioned runtime/data contract](../contracts/BROKER_REPORTS_PDF_TABLE_INTAKE_GATE1.v1.md) | Поддерживаемый runtime path, вход/выход, версии схем, настройки, privacy и failure semantics. |
| 3 | [Operator runbook](../operations/BROKER_REPORTS_PDF_TABLE_INTAKE_GATE1_RUNBOOK.md) | Deploy, parity, proof, visual review и диагностику. |
| 4 | [Closure report](../../reports/2026-07-17/OPENWEBUI_BROKER_REPORTS_PDF_TABLE_INTAKE_GATE1_CLOSURE.report.md) | Доказательство принятия конкретной repository/live revision и representative PDF. |
| 5 | Research и forensic reports | Историю гипотез, неудач и отвергнутых подходов; они не определяют production behavior. |

Если документы расходятся, placement и терминологию нужно сверять с этим
файлом, а текущее поведение — с версионным контрактом и соответствующим ему
bundled runtime. Расхождение runtime и контракта является дефектом документации
или поставки; closure и research reports не могут его переопределить.

Предшествующий
[Document Normalization Gate blueprint](BROKER_REPORTS_DOCUMENT_NORMALIZATION_GATE.blueprint.md)
сохранён как историческое архитектурное основание. Текущий global Gate 1
маршрутизируется через
[Normalization Pipeline blueprint](BROKER_REPORTS_GATE1_NORMALIZATION_PIPELINE.blueprint.md),
а эта страница — maintained entrypoint именно для PDF Table Intake.

## Закрытие и ограничения доказательства

Stage acceptance 2026-07-17 подтвердил доставку, scoped parity, строгие
контракты, 8-процентные поля и operator visual acceptance всех 11 кандидатов из
одного 8-страничного representative PDF. Это закрывает поддерживаемую
raster-candidate boundary.

Один PDF не доказывает универсальную точность VLM на любом брокерском шаблоне.
Для нового representative format и после изменения модели, prompt, renderer,
контрактов или геометрических настроек нужен повторный operator proof с
визуальным осмотром. Известное принятое ограничение: у одного кандидата первая
строка формового заголовка частично не попала в кроп, при этом табличные колонки,
строки и итоги сохранены.

Вне ответственности этого закрытия остаются canonical table reconstruction,
dual-VLM consensus, global source eligibility, source-fact extraction,
финансовая интерпретация и customer-wide quality claim.

## Навигация

- [Runtime/data contract](../contracts/BROKER_REPORTS_PDF_TABLE_INTAKE_GATE1.v1.md)
- [Operator runbook](../operations/BROKER_REPORTS_PDF_TABLE_INTAKE_GATE1_RUNBOOK.md)
- [Stage closure evidence](../../reports/2026-07-17/OPENWEBUI_BROKER_REPORTS_PDF_TABLE_INTAKE_GATE1_CLOSURE.report.md)
- [Documentation refinement report](../../reports/2026-07-17/OPENWEBUI_BROKER_REPORTS_PDF_TABLE_INTAKE_DOCUMENTATION_REFINEMENT.report.md)
- [Global Broker Reports Gate 1 pipeline](BROKER_REPORTS_GATE1_NORMALIZATION_PIPELINE.blueprint.md)
- [Normalized table projection contract](../contracts/BROKER_REPORTS_NORMALIZED_TABLE_PROJECTION.v0.md)
- [Global Gate 2 source-fact contract](../contracts/BROKER_REPORTS_GATE2_SOURCE_FACT_EXTRACTION.v0.md)
