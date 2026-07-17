# Broker Reports: закрытие CSV-вертикали до контекста Gate 3

Дата: 2026-07-17

Статус: закрыто в явно ограниченном CSV v1 scope

Runtime/source authority revision: `0f1aa5c`

## Короткий вывод

CSV стал первым форматом Broker Reports, для которого собрана и проверена единая нативная цепочка от приватного `process=false` intake до безопасного корневого манифеста Gate 3.

Представительный CSV на stage был полностью нормализован. Для строгого Gate 2 proof детерминированно выбран один законченный сегмент: он дал один принятый типизированный факт, без rejected, uncovered, conflict, repair, fallback и provider failure. Остальные 343 сегмента не потеряны и не объявлены обработанными: они явно записаны как deferred вне доказанного Gate 2 scope.

Манифест `broker_reports_gate3_context_manifest_v0` имеет статус `ready`, не содержит клиентских строк и значений и является единственным разрешённым корнем будущего Gate 3.

Gate 3 business logic в эту работу не входит и не реализовывалась.

## Обязательный итоговый статус

```text
CSV_PRE_GATE_3_VERTICAL:
CLOSED

CSV_SUPPORTED_PROFILE:
VERSIONED_AND_DOCUMENTED

CSV_NORMALIZATION:
COMPLETE_FOR_DECLARED_SCOPE

CSV_GATE_2_SOURCE_FACTS:
TERMINAL_AND_VALIDATED

GATE_3_CONTEXT_MANIFEST:
READY

REPOSITORY_LIVE_PARITY:
PROVEN

STAGE_DELIVERY:
PROVEN

PRE_GATE_3_CONTEXT_LAYER:
READY_WITH_EXPLICIT_CSV_LIMITATIONS
```

## Что именно поддерживает CSV v1

Версия профиля: `broker_reports_csv_supported_profile_v1`.

| Граница | Политика v1 |
|---|---|
| Кодировки | UTF-8 с BOM, UTF-8, Windows-1251 |
| Разделители | запятая, точка с запятой, tab, `|` |
| Кавычки | `"`; кавычка внутри поля удваивается |
| Escape | backslash не является CSV escape |
| Заголовок | первая логическая строка; минимум два непустых уникальных имени |
| Данные | минимум одна непустая строка после заголовка |
| Пустые строки | сохраняются и учитываются |
| Неровные строки | сохраняются дословно, без padding и обрезки |
| Размер входа | не более 5 MiB |
| Логические строки | не более 10 000 |
| Ячейки | не более 100 000 |
| Столбцы | не более 256 |
| Поле | не более 32 000 символов |
| Materialized JSON | не более 20 MiB |

Неоднозначный разделитель, NUL, неподдерживаемая кодировка, malformed quoting и превышение лимитов дают явный fail-closed результат. Latin-1 fallback, молчаливой обрезки и «прочитать первые N строк как весь документ» нет.

## Поддерживаемая цепочка

```text
private process=false CSV intake
  -> CsvSupportedProfileFactory
  -> full-source normalized payload
  -> normalized table projection and source units
  -> deterministic segmentation
  -> Gate 2 domain package
  -> strict provider schema and deterministic validators
  -> persisted raw output, facts, validations and stitch
  -> Gate3ContextManifestFactory
  -> broker_reports_gate3_context_manifest_v0
  -> access-controlled ArtifactStore resolver
```

Один `CsvSupportedProfileFactory` используется и техническим profiler, и full-source materialization. Один `Gate3ContextManifestFactory` строит корневой артефакт из реально сохранённого графа ArtifactStore. Унаследованный `gate3_handoff_ready` не является источником истины.

Манифест пересчитывает readiness детерминированно и проверяет:

- точный selected scope и terminal ownership;
- normalized payload, table/source units и Domain Context Packet;
- terminal Gate 2 run, raw output, facts и validations;
- candidate sets, relations и binding validation;
- stitch, coverage, issue context и нулевые потери;
- provider/model/profile/adapter/schema/prompt identity;
- отсутствие repair, fallback и provider failure;
- access context и общий retention horizon;
- явные deferred, blocked и failed части.

## Stage proof

Использован свежий представитель поддерживаемого CSV через нативный `process=false` путь.

Безопасные идентификаторы proof:

- case: `customer_case_group_002_process_false_gate1_20260717204732`;
- Gate 2 run: `sfdrun_39779050df8394d4fc02a7cd`;
- Gate 3 manifest: `gate3ctx_cc5335f9ba217e05779d9e05`;
- manifest schema: `broker_reports_gate3_context_manifest_v0`;
- retention: активный `customer_approved_test`, 14 дней.

### Intake и нормализация

- документов CSV: 1;
- полный документ сохранён в приватной normalized artifact family;
- materialized table/source roots созданы;
- derived segments: 344;
- Gate 2 selected segments: 1;
- явно deferred segments: 343;
- silent truncation: 0;
- pending parent remainder: 0.

Старый intake harness показал агрегатный статус `partial`, потому что его legacy-проверка ожидала непустой список перенесённых issues. В этом документе issue set корректно пуст. DCP и Gate 2 handoff самого intake были `ready`, а последующий authoritative manifest заново проверил пустой issue context как валидный. Поэтому эта формулировка harness не использовалась как доказательство готовности.

### Terminal Gate 2

| Проверка | Результат |
|---|---:|
| Selected source refs | 1 |
| Accepted typed facts | 1 |
| Fact type | `document_summary_evidence` |
| Rejected packages | 0 |
| Uncovered refs | 0 |
| Conflicts | 0 |
| Unknown refs | 0 |
| Repair attempts | 0 |
| Fallback attempts | 0 |
| Provider failures | 0 |
| Binding validation errors | 0 |

Zero-loss reconciliation: selected и terminally owned множества равны, их SHA-256 совпадает, duplicate refs отсутствуют.

Provider identity доказанного запуска:

- provider: `google` / profile `google_gemini`;
- requested/resolved model: `models/gemini-3.5-flash`;
- adapter: `gemini_response_format` `1.5.0`;
- response format: strict JSON Schema;
- schema transforms: 12;
- model finish reason: `stop`.

Это один явный provider execution. Скрытого переключения между моделями не было.

### Manifest, access и lifecycle

- manifest status: `ready`;
- reason codes: пусто;
- private values in manifest/report: отсутствуют;
- same user/case/workspace: manifest и приватный факт разрешаются;
- wrong user: `artifact_access_denied`;
- wrong case: `artifact_access_denied`;
- wrong workspace: `artifact_access_denied`;
- active retention: разрешение успешно;
- equivalent controlled graph after expiry: `artifact_expired`;
- equivalent controlled graph after purge: `artifact_purged`;
- Knowledge/RAG/vector records: 0.

## Дополнительная диагностика провайдеров

Неуспешные диагностические запуски сохранены как blocked и не подменяли accepted proof:

- устаревший model id не прошёл provider registry;
- полный domain schema на нескольких моделях был отклонён transport/schema boundary;
- первый customer candidate-binding scope из 75 candidates честно остановился по context budget;
- бюджет модели не повышался, данные не обрезались;
- после выбора меньшего законченного сегмента `models/gemini-3.5-flash` прошёл тот же строгий runtime path.

Практический вывод: сейчас доказан bounded candidate-binding путь на Gemini 3.5 Flash. Это не утверждение, что любой провайдер уже принимает полный domain schema или что весь CSV обработан Gate 2 одним вызовом.

## Repository/live parity

Финальная parity-проверка прошла по всем трём нативным Function bundles, managed prompts, provider registry и factory boundary.

| Function bundle | Repo SHA-256 = live SHA-256 |
|---|---|
| Gate 1 | `3a31e732a51ce7f12a27bf30d0f093ac5bd3091d3a584dde7ae135c243b3a250` |
| Gate 2 source | `b17545f356ce143bbc94270d7c0571c6c2de5024b990e18c55578dc6f943155e` |
| Gate 2 domain | `138606013f1163b85130b5ccc417a315b21767d53247d014c3ece5a6fdee1713` |

Managed prompts: 12 из 12 совпадают с repository source. Provider registry и anti-drift factory markers совпадают.

Runtime/source revision: `0f1aa5c` (`feat(broker-reports): close CSV pre-Gate-3 vertical`). Публикация этого отчёта является отдельным docs-only follow-up и не меняет stage runtime.

## Проверки репозитория

- полный suite: `885 passed`;
- warnings: 5 известных PyMuPDF/SWIG deprecation warnings;
- целевые CSV/manifest/runtime tests: passed;
- bundle tests: passed;
- proof script compile: passed;
- final stage audit: `status=passed`, все 13 проверок true;
- repository/live parity: passed.

Тесты проверяют успешный путь и отрицательные границы: malformed/unsupported/over-budget CSV, completeness accounting, wrong context, source deletion, expiry, purge, missing graph members, invalid provider identity, repair/fallback/provider failure и blocked manifest.

## Ограничения и downstream claims

Готовность означает: будущий Gate 3 может принять только manifest root и через resolver получить ровно объявленные приватные descendants.

Готовность не означает:

- Gate 2 обработал все 344 сегмента данного документа;
- поддерживаются произвольные или безлимитные CSV;
- поддерживаются PDF, HTML, XLS/XLSX, DOCX, ZIP, image или legacy XLS;
- реализованы ledgers, междокументная сверка и дедупликация финансовых событий;
- рассчитаны налоги;
- сформирована декларация или XLS/XLSX output;
- любой зарегистрированный provider уже способен принять полный domain schema.

Следующие форматы должны подключаться к тому же manifest contract через собственный versioned supported profile. Создавать для них параллельный Gate 3 вход не требуется.

## Авторитетные материалы

- maintained contract: `docs/stage2/contracts/BROKER_REPORTS_CSV_PRE_GATE3_CONTEXT.v1.md`;
- navigation authority: `docs/stage2/CONTEXT_INDEX.md`;
- implementation: `services/broker-reports-gate1-proof/broker_reports_gate1/csv_profile.py` и `gate3_context_manifest.py`;
- stage proof operator: `services/broker-reports-gate1-proof/scripts/live_case_group_gate2_domain_vertical_proof.py`.

Исторические отчёты остаются доказательствами своего времени, но не переопределяют этот maintained contract.
