# Broker Reports: аудит готовности контекстного слоя перед Gate 3

Дата: 2026-07-17
Режим: architecture / contracts / runtime / proof audit
Repository revision: `203708446800fefd2bca8dcc1c3a5216c3cd42de`
Рабочая ветка на момент аудита: `main == origin/main`

## 1. Итог простыми словами

Финальный вердикт:

```text
PRE_GATE_3_CONTEXT_LAYER_NOT_READY
```

Gate 3 пока нельзя объявить начатым на поддерживаемом stage-пути.

Причина не в том, что «вся нормализация не работает». Большая часть основания
уже есть и проверена: private intake, ArtifactStore, DCP, issue carry-forward,
полные CSV units, PDF text/layout units, normalized table projections, bounded
source facts, строгая валидация и stitch.

Не хватает трёх конкретных вещей:

1. Нет одного нормативного case-scoped объекта, который Gate 3 обязан получить
   и который связывает scope, DCP, документы, issues, extraction runs,
   validated facts, stitch/coverage и явные исключения.
2. Текущий stage не совпадает с репозиторием по двум Gate 2 Function bundles.
3. Нет свежего активного live proof, где полностью закрытый bounded scope
   сохранён под действующим retention и собран в такой корневой объект. Старый
   реальный DCP при read-only проверке уже дал `artifact_expired`.

Это небольшая pre-Gate-3 граница. Не требуется сначала поддержать все форматы,
дочитать весь PDF-корпус или реализовать raster-table normalization.

## 2. Прямые ответы

| Вопрос | Ответ |
| --- | --- |
| Можно ли начинать Gate 3 сейчас? | Нет, не как stage-backed product proof. Можно проектировать Gate 3, но его нормативный runtime-вход ещё не существует. |
| Что минимально осталось? | Один versioned Gate 3 context manifest с валидатором; repo/live parity двух Gate 2 bundles; свежий bounded CSV proof с нулевыми uncovered/conflict/rejected внутри объявленного scope и активным retention. |
| Что должен потреблять Gate 3? | Новый safe-internal `broker_reports_gate3_context_manifest_v0`, который ссылается на существующие DCP, issue, fact, validation, stitch и coverage artifacts, не копируя private значения. |
| Что безопасно для первого proof? | Только явно ограниченные, complete и budget-fit CSV source units/segments, заново прогнанные через текущий Gate 2. |
| Что исключить из первого proof? | Whole-document PDF, raster PDF tables, HTML, XLSX, TXT, DOCX, ZIP, images, legacy XLS, over-budget/partial/expired artifacts и любой scope с deferred/uncovered/conflict/provider-failed refs. |
| Нужно ли закрывать universal document support? | Нет. |
| Нужно ли ослаблять validators? | Нет. Текущие validators корректно остановили неполный результат. |

## 3. Как читалось доказательство

В отчёте уровни доказательства разделены:

| Уровень | Значение |
| --- | --- |
| Implemented | Код существует в текущем `main`. |
| Contracted | Есть current versioned contract, а не только исторический report. |
| Unit-proven | Наблюдаемое terminal behavior проверено локальными tests. |
| Stage-proven | Repo/runtime или live execution проверялись на stage. |
| Real-document-proven | Использовался approved representative real document без публикации private данных. |
| Product-accepted | Владелец принял конкретную границу и её ограничения. |

Наличие кода или контракта само по себе не считается готовностью формата.

Текущий локальный regression во время аудита:

```text
881 passed, 5 known PyMuPDF/SWIG deprecation warnings
```

## 4. Нормативная карта глобальных gates

| Global product gate | Владелец | Нормативный вход | Нормативный выход | Не входит |
| --- | --- | --- | --- | --- |
| Gate 1 — Document Intake & Normalization | Gate 1 normalizer, ArtifactStore, domain-ingestion code | `process=false` source refs + access/retention context | normalized payloads/units/tables, passports, issue ledger, usage classification, `domain_context_packet_v0`, resolver handoff | source facts, consolidation, tax |
| Gate 2 — Source-Fact Extraction | Gate 2 runtime, domain extractors, validators, stitcher | validated DCP + resolver-authorized normalized artifacts | validator-accepted source facts, validation results, issue/fact links, deterministic coverage/stitch | cross-document consolidation, calculations, declaration |
| Gate 3 — Intermediate Ledgers & Reconciliation | будущий Gate 3 runtime | нормативный manifest validated Gate 2 results | intermediate ledgers, duplicate/cross-document reconciliation, deterministic calculation traces | изменение source facts, сокрытие issues, декларационный output без следующих gates |

Gate 3 начинается не с чтения PDF и не с повторной интерпретации таблиц. Он
начинается с потребления уже validated source facts вместе с provenance,
coverage, issue linkage, restrictions и declared scope.

Отдельно существуют:

- общие [Stage 2 Implementation Gates](../../stage2/IMPLEMENTATION_GATES.md) —
  это governance-нумерация, не Broker Reports pipeline;
- локальный accepted [PDF Table Intake Gate 1](../../stage2/blueprints/BROKER_REPORTS_PDF_TABLE_INTAKE.blueprint.md) —
  child capability внутри global Gate 1, только `PDF -> private raster candidates`.

Его закрытие не переоткрывается этим аудитом.

## 5. Что сейчас является корнем, а что им не является

### 5.1 Существующие объекты

| Объект | Что он действительно означает | Почему недостаточен один |
| --- | --- | --- |
| `domain_context_packet_v0` | Нормативный Gate 1 context для source-fact extraction: документы, buckets, issues, readiness, private access contract | Не содержит terminal Gate 2 results |
| `gate2_handoff_v0` | Resolver manifest и compatibility view | `included_document_refs` не являются полным source-ready context |
| `broker_reports_*_source_fact_extraction_run_v0` | Состояние одного extraction run и refs на его artifacts | Может описывать только выбранную wave/batch/unit; не является case completeness authority |
| `broker_reports_source_fact_stitch_result_v0` | Terminal ownership и coverage одного source unit | Не доказывает document/case completeness |
| `broker_reports_document_extraction_packet_v0` | Private aggregate одного документа из E2E runner | Не имеет maintained Gate 3 contract; не покрывает case и сейчас создаётся proof-script, а не общей production factory |

В runtime нет отдельного artifact type наподобие
`broker_reports_gate3_context_manifest_v0`. Поиск current code/contracts нашёл
только per-run/per-unit `gate3_handoff_ready` flags и единичный private document
packet.

### 5.2 Почему текущий readiness flag не является case readiness

В [gate2_domain_runtime.py](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate2_domain_runtime.py)
`gate3_handoff_ready` вычисляется для выбранного runtime slice. Проверяются
terminal status, typed facts, truncation, parent remainder, uncovered и
conflicts, но не требуется `documents.deferred_total == 0`.

Следовательно, флаг может быть корректным для bounded selected scope, но его
нельзя читать как «всё дело готово». Нормативный manifest обязан иметь явные:

- `scope_kind=bounded_source_units|document|case`;
- included refs;
- excluded/deferred/blocked refs и reason codes;
- `scope_complete` отдельно от document/case completeness.

## 6. Рекомендуемый нормативный вход Gate 3

Нужен один новый корневой safe-internal manifest:

```text
broker_reports_gate3_context_manifest_v0
```

Это не новый формат таблицы и не копия всего normalization JSON. Это небольшой
список проверенных ссылок.

Минимальные поля:

- schema/version, manifest id, case/run/workspace identity;
- access-context и retention-policy refs;
- `scope_kind`, scope hash, included documents/units/refs;
- explicit excluded/deferred/blocked/provider-failed/unexamined refs;
- `domain_context_packet_ref`;
- passport, usage-classification и issue-ledger refs;
- normalized payload/unit/table-projection refs только как provenance roots;
- terminal Gate 2 extraction-run refs;
- validated source-fact refs;
- validation, stitch, issue/fact-linkage и coverage refs;
- per-document/per-unit terminal statuses;
- aggregate counts and zero-loss reconciliation;
- restrictions: no cross-scope claim, no tax/declaration claim, no mutation of source facts;
- derived `gate3_input_status=ready_bounded_scope|ready_with_issue_context|blocked`.

Manifest должен быть `safe_internal` в `project_artifact_store`. Private facts
остаются `private_case` и разрешаются Gate 3 через тот же user/case/workspace
context. Raw rows, text и values в manifest запрещены.

Нормативная связь:

```text
process=false source custody
  -> Gate 1 normalized payloads/units/table projections
  -> passports + usage classification + issue ledger
  -> domain_context_packet_v0 + gate2_handoff_v0
  -> Gate 2 packages / provider attempts
  -> validated source facts + validations + issue links
  -> per-unit deterministic stitch/coverage
  -> broker_reports_gate3_context_manifest_v0
  -> Gate 3 intermediate ledgers and reconciliation
```

Gate 3 не должен принимать как root чат, один table projection, один
extraction run, один `gate3_handoff_ready` boolean или DCP без Gate 2 results.

## 7. Матрица готовности форматов

`Complete` ниже означает только заявленный mechanical scope. Это не означает
правильность финансовой интерпретации.

| Format/class | Runtime normalization | Доказательство | Gate 2 состояние | Первый Gate 3 proof |
| --- | --- | --- | --- | --- |
| CSV, до 10,000 rows / 100,000 cells на logical unit | Complete full-source unit + normalized table projection | Implemented, contracted, unit-proven; real 1,342-ref source unit и bounded typed facts proven | Bounded source-unit/row path passed; whole CSV coverage не доказана | **Да, только свежий bounded scope** |
| TXT, до 200,000 chars | Complete text payload/unit | Implemented/contracted, synthetic proof | Representative real source-fact vertical не доказан | Нет в первом proof |
| HTML, budget-fit tables/text | Complete per table/outside-text logical unit | Implemented/contracted/unit-proven; real structural preflight есть | Real terminal fact coverage не доказана | Нет в первом proof; следующий кандидат |
| XLSX, без formulas и в member/unit budgets | Conditional complete | Implemented/contracted/unit-proven; real large structural preflight | Formula sheets partial; large packages часто blocked | Нет в первом proof |
| XLSX с formulas/unresolved/over-budget sheets | Partial/blocked, explicit reason | Fail-closed behavior implemented | Не source-complete | Исключить |
| PDF с text layer на каждой странице | Complete только для pypdf page-text projection | Implemented/contracted/unit/stage/real proof; 6 из 8 approved PDFs page-text-complete | Один whole-document run остался partial; visible/image semantics не покрыты | Исключить из первого proof |
| PDF layout/table geometry | Conditional | Implemented/contracted/unit/stage/real preflight; layout-complete 1 из 8 | Bounded geometry units возможны; semantic table truth=false | Исключить из первого proof |
| PDF raster table candidates | Accepted только как private PNG regions | Product-accepted Gate 1 boundary на 1 representative PDF | Rows/cells/canonical projection ещё отсутствуют | Исключить; это не блокер CSV proof |
| Image-only/raster PDF pages | Нет extraction-grade normalized text/table | OCR/VLM source reconstruction не поддержан | Blocked/review | Исключить |
| DOCX | Partial body-text projection | Код явно не доказывает tables/headers/auxiliary parts | Нет complete source unit | Исключить |
| ZIP | Inventory/review only | Profiling есть, full-source parser отсутствует | Unsupported | Исключить |
| Images | Profile/OCR candidate only | Extraction-grade path отсутствует | Unsupported/blocked | Исключить |
| Legacy XLS | Parser отсутствует | Unsupported | Unsupported | Исключить |
| Encrypted/corrupt inputs | Fail-closed | Unit/runtime reasons typed | Blocked | Исключить |

Вывод: «CSV поддерживается» не означает «любой CSV любого размера». Любой
format становится eligible только при complete status, budget fit, valid refs
и terminal coverage объявленного scope.

## 8. Raster PDF table integration без второго table contract

Accepted PDF Table Intake уже правильно заканчивается на
`broker_reports_pdf_table_candidate_v1`: bbox, padded crop, PNG hash и
provenance. Этот результат не надо менять.

Downstream integration должна идти через ту же normalized-table family:

```text
broker_reports_pdf_table_candidate_v1
  -> private raster reconstruction evidence
  -> strict row/column/cell/provenance validator
  -> NormalizedTableProjectionFactory
  -> versioned broker_reports_normalized_table_projection family
  -> existing Gate2TablePackageFactory
```

Требования:

- VLM output остаётся candidate evidence, а не canonical truth;
- если Gemini формально назначена oracle, это должно быть записано как
  `oracle_policy_version`: Gemini candidate может быть выбран для продолжения,
  но отличающееся OpenAI значение и disagreement status обязаны сохраниться;
- каждая строка/ячейка/value получает stable ref, привязанный к source PDF,
  page, crop candidate и reconstruction evidence;
- literal source strings сохраняются private; никакой финансовой
  интерпретации на этом шаге;
- consensus может дать `accepted_candidate`, disagreement — explicit
  conflict/review, но не silent Gemini override;
- missing/extra row/cell, ambiguous column ownership и continuation gap дают
  `partial|blocked`, а не rectangular fake success;
- normalized projection сохраняет crop/provider/model/prompt/schema hashes и
  visual-review evidence;
- Gate 2 видит обычную normalized table projection и не знает отдельный
  конкурирующий «raster table JSON».

Текущий `broker_reports_normalized_table_projection_v0` декларирует
`ocr_vlm_used=false` и `page_rendering_used_for_extraction=false`. Поэтому
raster producer нельзя незаметно записать как v0. Нужна совместимая следующая
версия в той же artifact family либо явное versioned producer-profile
расширение v0-контракта. Создание второго параллельного canonical table schema
не рекомендуется.

Эта работа не требуется до первого CSV-only Gate 3 proof.

## 9. Полнота, большие таблицы и silent loss

### 9.1 Что уже защищено

- DCP no-loss: каждый source-ready document попадает в primary, secondary,
  duplicate/non-primary или audit bucket; `dropped_source_ready_refs=[]`.
- Full-source unit: complete parent имеет exact selected/accounted refs,
  checksums и `parent_remainder_status=not_applicable_parent_complete`.
- Table projection: table/fallback/rejected/non-table refs образуют exact
  partition; duplicate/unaccounted refs fail validation.
- Segmenter: refs complete parent детерминированно делятся на derived units;
  duplicate/unaccounted refs запрещены.
- Stitcher: каждый selected ref получает typed/unknown/no-fact/conflict/
  uncovered disposition; incomplete result остаётся partial.

### 9.2 Где полноты ещё нет

Текущие hard budgets:

| Boundary | Current limit/behavior |
| --- | --- |
| Full-source logical unit | 10,000 rows, 100,000 cells, 200,000 text chars; overflow -> partial, projection omitted |
| Normalized table projection | 10,000 rows, 100,000 cells, 20 MB; overflow -> blocked |
| Gate 2 table package | 250 rows; overflow -> package error |
| Gate 2 segmenter | 8 table refs / 12 text refs by default, но только после успешного package build |

Approved preflight нашёл 54,939 rows / 275,259 cells. Из 81 projections пять
документов были partial/blocked, а 24 Gate 2 packages не прошли 250-row budget.
Worst-case XLSX имел 26,011 rows / 122,766 cells; 11 из 13 projections были
package-budget-blocked.

Данные не были молча обрезаны — это хорошо. Но continuation/windowing до
package boundary для oversized native tables пока нет. Segmenter не может
спасти projection, который уже заблокирован на 250 rows.

Решение для будущего включения больших таблиц: deterministic row windows с
stable parent/range/sibling refs, repeated-header policy, exact union coverage,
continuation cursor и final stitch. Поднимать budgets или отправлять whole
table в model нельзя.

Для первого bounded Gate 3 proof это **operational limitation**, а не global
blocker: over-budget tables явно исключаются manifest-ом.

## 10. Политика статусов и неопределённости

Текущие контракты уже дают достаточную основу, если Gate 3 не смешивает уровни.

| Состояние | Нормативное значение для Gate 3 |
| --- | --- |
| accepted / validator-passed | Детерминированный validator принял schema, refs, values, provenance и issue impact. Это не автоматически `complete`. |
| `completeness=complete` | Все обязательные поля данного fact type видимы; linked issue не ограничивает подтверждение. |
| `partial` | Факт существует, но ожидаемые поля отсутствуют. Можно хранить/показывать с ограничением; нельзя объявлять полный ledger/case. |
| `uncertain` | Тип или значение неоднозначны либо ограничены issue. Нельзя молча выбирать трактовку. |
| `blocked` | Evidence сохраняется, но fact не используется downstream. |
| disagreement/conflict | Обе позиции и evidence сохраняются в conflict/reconciliation group; last-writer-wins запрещён. |
| review-required | Это stage-specific issue, а не универсальный stop. Продолжать можно только в `stages_that_may_continue`; blocked stages остаются закрыты. |
| rejected/provider-failed/uncovered/unexamined | Не совместимо с complete declared scope; должно быть явно видно в manifest. |

Gate 1 issue ledger уже различает `unresolved|resolved`, criticality,
`blocked_stages` и `stages_that_may_continue`. Gate 3 должен уважать эти поля,
а не превращать любой unresolved issue в stop или в resolved.

## 11. Какие issues блокируют, а какие переносятся

### Блокируют включённый Gate 3 scope

- expired/purged/wrong-context/unresolvable artifact;
- validator rejection либо missing provenance/value checksum;
- uncovered или conflict ref внутри declared included scope;
- provider-failed/unexamined/deferred ref внутри scope, объявленного complete;
- truncated parent, pending parent remainder или budget-blocked included unit;
- отсутствие нормативного root manifest;
- repo/live mismatch на runtime, создающем proof artifacts.

### Могут переноситься как explicit context

- non-critical metadata gaps;
- source-role policy uncertainty, если конкретный source unit уже readable и
  явно включён policy;
- unresolved issue с разрешением продолжать source extraction/ledger slice;
- duplicate/canonical-choice issue, если первый proof не выполняет
  cross-document consolidation этой группы;
- partial/uncertain accepted fact, если Gate 3 output остаётся restricted и не
  объявляет completeness;
- исключённые форматы/documents с reason codes и без claims по ним.

Duplicate resolution, cross-document reconciliation и relation decisions —
это уже собственная работа Gate 3, а не обязательная Gate 2 семантика.

## 12. Почему whole-document Gate 2 остался partial

### 12.1 Старый baseline

Первый six-page PDF run имел:

- 175 provider calls;
- 51 Gemini HTTP 400 на `document_summary_evidence`;
- 4.58M input tokens;
- 120 rejected packages;
- 113 provenance errors;
- 2,175 uncovered из 2,489 refs.

Причина была комбинацией schema/package fan-out, неверной applicability
boundary и missing provenance. Это не было доказательством плохого PDF parser:
parent accounting был 2,489/2,489 без truncation/remainder.

### 12.2 Текущее состояние после context v2 refactor

Повтор снизил calls на 73.7%, input tokens на 94.8% и uncovered до 231. Все 46
реальных Gemini calls прошли без HTTP 400. Остались:

- 146 packages, механически заблокированных до provider из-за отсутствующих
  roles/role-groups/relations;
- 11 refs с `source_fact_provenance_missing` в unknown path;
- один `fee_commission` package identity mismatch;
- 231 uncovered refs, zero conflicts.

Следовательно, старый Gemini strict-schema 400 уже не главный blocker.
Текущая partial причина — Gate 2 applicability/candidate/unknown terminal
ownership contract и отсутствие document/case completion authority. Validators
сработали правильно; их ослабление создало бы ложный green.

Whole-document PDF closure не требуется для первого bounded CSV Gate 3 proof,
но требуется до claims по complete PDF document или multi-document case.

## 13. ArtifactStore, access, retention и purge

### Реализовано и доказано локально

- private artifacts -> `project_artifact_payload`;
- safe manifests -> `project_artifact_store`;
- same user/case/chat/workspace checks;
- wrong user/case/chat/workspace denial;
- expiry, source-delete cascade, run/chat/case purge и tombstones;
- Knowledge backend forbidden для private/customer artifacts;
- Gate 2 fact refs fail closed после source delete/expiry;
- `broker_reports_document_extraction_packet_v0` разрешён только как private payload.

### Stage/real evidence

- Gate 1 live retention smoke доказал writable store, resolver, expiry,
  purge/tombstones и zero Knowledge delta;
- real Gate 2 runs persisted raw output, facts, validations, stitch results и
  document packet under inherited customer retention;
- текущий read-only re-resolution старого real case остановился на
  `artifact_expired`, то есть expiry guard реально действует.

### Недостающая closure

Для нового Gate 3 root ещё нет:

- artifact type + maintained contract;
- local graph test: manifest -> all referenced descendants;
- live active same-context resolution;
- wrong-context/expired/purged denial для root;
- доказательства, что root и descendants имеют согласованный retention horizon.

Это required pre-Gate-3 closure. Старые expired artifacts не надо восстанавливать;
нужен новый proof run.

## 14. Repository/live alignment на 2026-07-17

Read-only `live_verify_broker_reports_stage2_delivery.py --scope all` дал:

```text
status=failed
all_managed_prompts_match=true
repository_factory_boundary_passed=true
provider registry/model namespaces match=true
```

Function parity:

| Function | Repository SHA-256 | Live SHA-256 | Result |
| --- | --- | --- | --- |
| `broker_reports_gate1_pipe` | `20d2924386bd4950bda5990d834747c910a2f969d3b1e3f3208d7372c44f529b` | same | passed |
| `broker_reports_gate2_source_fact_pipe` | `ac5d8d7d9d9d30501ddd815f751d71f66c3de01415ca3aede1a413d8fc09aa64` | `c6594db1aa434361be6a4989e53dc26b214fb04f91c9398a5c827e85995b5953` | failed |
| `broker_reports_gate2_domain_source_fact_pipe` | `2b5e5a80d91f6645c4dd99c0c2b8586b4765a9a5ba31791091610f761054a026` | `0ecfd182f7baf17a64b3afe39ccd09ab65b6df9658e8e9aad033e55d61a3fe5b` | failed |

Все 12 managed prompts совпали. SHA mismatch сам по себе не доказывает
semantic defect, но он запрещает называть текущий pre-Gate-3 stage path
репозиторно-воспроизводимым. Исторические reports с прошедшей parity описывают
свои revisions и не отменяют текущую проверку.

## 15. Register: blockers, carry-forward и лишняя работа

| Gap / concern | Класс | Решение |
| --- | --- | --- |
| Нет normative case/scope root для Gate 3 | **Gate 3 blocker** | Добавить один manifest contract/factory/validator, refs-only |
| Gate 2 source/domain live bundle drift | **Required pre-Gate-3 closure** | Доставить current bundles и получить `--scope all` pass |
| Нет свежего active bounded proof + root manifest | **Gate 3 blocker** | Новый CSV bounded run под explicit retention |
| `gate3_handoff_ready` неоднозначен по scope | **Required pre-Gate-3 closure** | Manifest validator recomputes readiness from declared scope; не доверять boolean как case status |
| Root/descendant lifecycle не доказан live | **Required pre-Gate-3 closure** | Same/wrong-context + active retention proof; synthetic purge after proof |
| Whole six-page PDF coverage partial | Operational limitation | Исключить из первого proof; чинить до PDF claims |
| Raster candidate -> normalized cells отсутствует | Operational limitation | Downstream extension той же table projection family; не блокирует CSV proof |
| Oversized native tables не windowed до package | Operational limitation / later optimization | Exclude by explicit budget reason; реализовать row windows перед включением |
| HTML/TXT/XLSX real fact vertical недостаточен | Operational limitation | Добавлять по одному format-specific proof после CSV closure |
| Metadata/source-policy uncertainty | Safe carry-forward | Сохранить issue refs и blocked stages |
| Duplicate/canonical choice | Safe carry-forward в bounded proof; Gate 3 work для consolidation | Не включать спорную группу в первый scope |
| Cross-domain event/relation model | Gate 3-owned work | Не делать условием начала bounded ledger proof |
| Gemini `document_summary_evidence` HTTP 400 baseline | Obsolete historical concern | Context v2 live rerun дал 0 HTTP 400 |
| Старый OCR false positive для mixed PDFs | Obsolete historical concern | Text-layer parser разделяет text/mixed/image-only |
| Direct whole-PDF provider experiments | Research-only / unnecessary before Gate 3 | Не заменять ими canonical normalization path |
| Universal DOCX/ZIP/image/XLS support | Later optimization | Не требовать до bounded proof |
| Folder-map/RAG/vector agent architecture | Unnecessary before Gate 3 | Если позже нужен retrieval, только ref-addressed; customer data в Knowledge/vector запрещены |

## 16. Минимальный roadmap до Gate 3

### Slice A — normative context manifest

1. Добавить contract `broker_reports_gate3_context_manifest_v0`.
2. Добавить ArtifactStore type и factory-first deterministic builder.
3. Валидатор обязан разрешить все refs, проверить declared scope, DCP/issues,
   terminal facts/validations/stitch, zero unexplained refs и restrictions.
4. Готовность вычисляется валидатором, а не LLM и не inherited boolean.

Это не Gate 3 financial implementation.

### Slice B — delivery parity

1. Собрать current Gate 2 source/domain bundles.
2. Доставить их через существующий OpenWebUI Function workflow.
3. Получить `live_verify... --scope all: passed` с теми же 12 prompts и provider registry.

### Slice C — первый active bounded proof

1. Взять один complete, budget-fit native CSV source unit.
2. Объявить scope точным списком selected source-unit/segment refs.
3. Выполнить Gate 2 с неизменёнными validators.
4. Получить минимум один validated typed fact, zero rejected packages,
   zero uncovered/conflicts, zero truncation/remainder внутри scope.
5. Сохранить manifest, разрешить его и private facts same-context.
6. Доказать wrong-context/expired/purged fail-closed на synthetic twin graph;
   реальный active proof не purge до чтения Gate 3.

После этих трёх slices можно объявить:

```text
PRE_GATE_3_CONTEXT_LAYER_READY_WITH_EXPLICIT_LIMITATIONS
```

Ограничение будет честным: ready только для `bounded_source_units`, а не для
whole document/case.

## 17. Acceptance criteria первого limited Gate 3 proof

### Input/context gate

- repo `HEAD == origin/main`, clean tree;
- all three Function bundles and all managed prompts match live;
- manifest schema/version и factory markers match repo/live;
- `scope_kind=bounded_source_units`;
- один или несколько complete CSV units/segments, точный scope hash;
- все excluded case documents/formats перечислены с reasons;
- DCP, passport/usage, issue-ledger and retention refs resolve.

### Gate 2 terminal gate

- source parent/unit complete;
- no truncated unit, parent truncation или pending remainder;
- selected refs exact and unique;
- provider/model identity exact, no hidden failover;
- final accepted path has no repair fallback;
- `domain_packages.rejected=0` within scope;
- validated typed facts `>=1`;
- `uncovered=0`, `conflict=0`;
- issue refs reconciled, including valid empty set;
- raw output/facts private, validation/stitch safe, all refs persisted.

### Storage/privacy gate

- explicit retention active through the proof window;
- same user/case/workspace resolver pass;
- wrong context, expired and purged refs fail closed;
- no OpenWebUI Knowledge/RAG/vector use;
- document/file/Knowledge/vector deltas remain zero except explicit
  `process=false` source custody allowed by policy;
- manifest contains no customer rows, values, filenames, ids or paths.

### Product claim gate

- Gate 3 consumes only the manifest and resolves facts by refs;
- it may create an intermediate ledger for the bounded scope;
- it must display `bounded scope`, exclusions and carried issues;
- it must not claim whole-document, whole-case, tax, declaration or XLS/XLSX readiness.

## 18. Что не надо делать перед первым Gate 3 proof

- не переписывать нормализатор;
- не переоткрывать accepted PDF Table Intake;
- не завершать dual-VLM/raster canonicalization;
- не чинить все large-table paths;
- не добиваться whole-PDF или whole-case coverage;
- не добавлять новые providers или auto-failover;
- не реализовывать folder-wide agent retrieval;
- не переносить customer data в Knowledge/RAG/vector;
- не решать все metadata/duplicate issues вне bounded scope;
- не реализовывать tax, declaration или XLS/XLSX output.

## 19. Evidence anchors

Current contracts:

- [Domain Context Packet](../../stage2/contracts/BROKER_REPORTS_DOMAIN_CONTEXT_PACKET.v0.md)
- [Gate 2 Source-Fact Extraction](../../stage2/contracts/BROKER_REPORTS_GATE2_SOURCE_FACT_EXTRACTION.v0.md)
- [Gate 2 Source Facts](../../stage2/contracts/BROKER_REPORTS_GATE2_SOURCE_FACTS.v0.md)
- [Gate 2 Stitching](../../stage2/contracts/BROKER_REPORTS_GATE2_SOURCE_FACT_STITCHING.v0.md)
- [Normalized Table Projection](../../stage2/contracts/BROKER_REPORTS_NORMALIZED_TABLE_PROJECTION.v0.md)
- [Extraction Source Units](../../stage2/contracts/BROKER_REPORTS_GATE1_EXTRACTION_SOURCE_UNITS.v0.md)
- [Issue Ledger](../../stage2/contracts/BROKER_REPORTS_GATE1_ISSUE_LEDGER.v0.md)
- [Artifact Lifecycle](../../stage2/contracts/BROKER_REPORTS_ARTIFACT_LIFECYCLE_CONTRACT.v0.md)

Current implementation:

- [full_source.py](../../../services/broker-reports-gate1-proof/broker_reports_gate1/full_source.py)
- [table_projection.py](../../../services/broker-reports-gate1-proof/broker_reports_gate1/table_projection.py)
- [gate2_source_unit_segmentation.py](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate2_source_unit_segmentation.py)
- [gate2_domain_runtime.py](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate2_domain_runtime.py)
- [gate2_source_fact_stitching.py](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate2_source_fact_stitching.py)
- [artifact_store.py](../../../services/broker-reports-gate1-proof/broker_reports_gate1/artifact_store.py)

Representative proof/research evidence, not runtime specifications:

- [Full-source coverage](../2026-07-10/OPENWEBUI_BROKER_REPORTS_GATE1_FULL_SOURCE_RESLICE_COVERAGE.report.md)
- [PDF text-layer Slice 1](../2026-07-10/OPENWEBUI_BROKER_REPORTS_PDF_TEXT_LAYER_NORMALIZATION_SLICE1.report.md)
- [PDF layout Slice 2](../2026-07-10/OPENWEBUI_BROKER_REPORTS_PDF_LAYOUT_RICH_NORMALIZATION_SLICE2.report.md)
- [Table representation preflight](../2026-07-11/OPENWEBUI_BROKER_REPORTS_TABLE_REPRESENTATION_AND_PDF_TABLE_HARDENING.report.md)
- [Single-PDF whole-document partial result](../2026-07-12/OPENWEBUI_BROKER_REPORTS_SINGLE_PDF_WHOLE_DOCUMENT_GATE2_E2E.report.md)
- [LLM context recovery rerun](../2026-07-12/OPENWEBUI_BROKER_REPORTS_GATE2_LLM_CONTEXT_REFACTOR_AND_SINGLE_PDF_RECOVERY.report.md)
- [Second real domain / multi-provider bounded proof](../2026-07-12/OPENWEBUI_BROKER_REPORTS_GATE2_SECOND_REAL_DOMAIN_MULTI_PROVIDER_CLOSURE.report.md)
- [Accepted PDF Table Intake boundary](OPENWEBUI_BROKER_REPORTS_PDF_TABLE_INTAKE_GATE1_CLOSURE.report.md)

## 20. Closure decision

Контекстный слой не пуст и не требует большого перезапуска. Он почти готов для
узкого Gate 3 proof, но сейчас ещё нет нормативного корня, текущей stage parity
и active terminal proof.

Самая консервативная и достаточная последовательность:

```text
one refs-only manifest
-> current Gate 2 bundle parity
-> one fresh bounded complete CSV proof
-> limited Gate 3 ledger proof with explicit exclusions
```

После этого raster PDFs, large tables, HTML/XLSX and whole-document coverage
можно подключать по одному, не меняя корневой Gate 3 contract.
