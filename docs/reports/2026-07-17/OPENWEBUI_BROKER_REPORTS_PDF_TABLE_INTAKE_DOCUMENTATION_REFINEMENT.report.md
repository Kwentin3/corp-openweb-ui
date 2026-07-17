# Broker Reports PDF Table Intake documentation refinement

Дата: 2026-07-17

Статус: завершено; runtime не изменялся.

## Результат

PDF Table Intake теперь имеет один понятный maintained route:

```text
project/stage overview
-> architecture and gate mapping
-> versioned runtime/data contract
-> operator runbook
-> dated closure evidence
-> historical research, только при необходимости
```

Главный архитектурный вход:
[BROKER_REPORTS_PDF_TABLE_INTAKE](../../stage2/blueprints/BROKER_REPORTS_PDF_TABLE_INTAKE.blueprint.md).

## Найденные несогласованности

1. `Gate 1` мог означать Stage 2 implementation gate, global Broker Reports
   `Document Intake & Normalization` или локальную PDF raster boundary.
2. `Gate 2 handoff` и `gate2_boundary_ready` можно было ошибочно прочитать как
   global source eligibility или завершённую canonical reconstruction.
3. Architecture, runtime contract, runbook, closure и research не имели явно
   записанного порядка authority.
4. Ранний Document Normalization blueprint сохранял open questions и readiness
   markers как будто они всё ещё актуальны; global Gate 1 pipeline называл Pipe
   текущим stub.
5. Overview/navigation вели сразу в контракт, минуя architecture mapping; одна
   относительная ссылка contract -> closure была фактически сломана.
6. Dual-VLM и ранние cropping reports содержали полезную историю, но не каждый
   файл сразу обозначал её как non-normative.

## Принятая модель

- Architecture entry определяет placement, ownership, локальную нумерацию и
  границы ответственности.
- Versioned contract определяет runtime path, вход/выход, schema versions,
  configuration, privacy и failure semantics.
- Runbook определяет deploy, scoped parity, operator proof и visual review.
- Closure report доказывает принятие конкретных repository/live revisions и
  representative PDF, но не определяет текущее поведение.
- Research reports сохраняют evidence неудачных и отложенных гипотез и не могут
  переопределять production contract.

Локальный PDF Table Intake Gate 1 теперь явно является child capability внутри
global Broker Reports Gate 1. Его выход — private raster candidates для
downstream table normalizer. Canonical table JSON, dual-VLM consensus, global
document source eligibility, source-fact extraction и финансовая интерпретация
не входят в это закрытие.

## Изменённая документация

- добавлен maintained
  [architecture entry](../../stage2/blueprints/BROKER_REPORTS_PDF_TABLE_INTAKE.blueprint.md);
- уточнены
  [runtime/data contract](../../stage2/contracts/BROKER_REPORTS_PDF_TABLE_INTAKE_GATE1.v1.md)
  и [operator runbook](../../stage2/operations/BROKER_REPORTS_PDF_TABLE_INTAKE_GATE1_RUNBOOK.md);
- closure report явно обозначен как evidence record и отделён от current spec;
- global Gate 1 pipeline reconciled с delivered runtime, а ранний normalization
  blueprint помечен `SUPERSEDED_HISTORICAL_ARCHITECTURE`;
- Stage 2 Implementation Gates получили явное предупреждение о другой
  нумерации;
- root README, Stage 2 README, context index, roadmap и 3NDFL blueprint ведут в
  новый архитектурный вход, затем в contract/runbook/closure;
- пять связанных forensic/benchmark/dual-VLM reports помечены
  `HISTORICAL_RESEARCH_NON_NORMATIVE` без удаления их evidence;
- исправлена broken relative link из runtime contract в closure report.

Redirect registry не менялся: файлы не перемещались и не переименовывались.

## Runtime и stage alignment

Документация сверена с репозиторным runtime:

- request `broker_reports_pdf_table_detection_request_v3`;
- response `broker_reports_pdf_table_detection_response_v2`;
- attempt `broker_reports_pdf_table_detection_attempt_v1`;
- candidate `broker_reports_pdf_table_candidate_v1`;
- run `broker_reports_pdf_table_intake_run_v1`;
- policy `pdf_table_intake_policy_v3`;
- raster policy `pdf_table_candidate_raster_policy_v1`;
- global page-relative padding `0.08` по X и Y на сторону;
- `DPI=150`, maximum pages `64`, maximum candidates/page `32`;
- stage detector `google_gemini / models/gemini-3.5-flash`.

Read-only live verifier `--scope gate1` прошёл 2026-07-17:

- status `passed`;
- repository/live bundle SHA совпал:
  `20d2924386bd4950bda5990d834747c910a2f969d3b1e3f3208d7372c44f529b`;
- intake enabled, provider/model/DPI/padding configured;
- required PyMuPDF `1.26.5` совпал;
- legacy structural/guided/semantic shadows выключены;
- factory boundary и managed prompt parity прошли.

Это scoped Gate 1 evidence. Оно не объявляет full Stage 2 или global Gate 2
parity.

## Проверки документационной правки

- targeted PDF Table Intake tests: `22 passed, 5 warnings`;
- warnings: только известные SWIG/PyMuPDF deprecation warnings;
- compileall для runtime/raster/Pipe: passed;
- относительные inline links всех изменённых Markdown files: passed;
- `git diff --check`: passed;
- runtime files: не изменены;
- новый operator visual proof не требовался, потому что model, prompt, renderer,
  runtime schema versions, DPI и padding не менялись.

Stage acceptance по одному 8-страничному representative PDF остаётся честно
ограниченным доказательством: оно закрывает поддерживаемую raster-candidate
boundary, но не доказывает универсальную VLM accuracy на всех брокерских
шаблонах.

## Финальный статус

```text
PDF_TABLE_INTAKE_DOCUMENTATION:
REFINED_AND_CONSISTENT
```
