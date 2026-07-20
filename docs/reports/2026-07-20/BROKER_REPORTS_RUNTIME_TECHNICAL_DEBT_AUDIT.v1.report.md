# Broker Reports — runtime, capacity, product-path и technical-debt audit v1

Дата: 2026-07-20
Статус: **COMPLETED**
Ветка: `codex/broker-reports-runtime-audit-v1`

## 1. Executive result

Аудит завершён без расширения финансовой семантики и без широкого runtime-
рефакторинга. Данные actual corpus использовались только в ignored private evidence
root; в Git включены агрегаты, хэши, счётчики и безопасные отчёты.

Прямые ответы:

| Вопрос | Ответ |
|---|---|
| Пустая PDF-страница остаётся блокером? | **Нет.** Это `confirmed_empty_source_scope`: identity и lineage сохранены, ожидаемое число таблиц равно нулю, OCR и соседняя страница не используются. |
| Gate 2 действительно регрессировал с 53 до 112 секунд? | **Нет.** Медиана шести контролируемых baseline-прогонов — 53.287363 с против ориентира 53.146799 с, разница 0.26%. Около 110–112 с даёт line/function instrumentation. |
| Где крупнейшая стоимость? | Во всём runtime — Gate 1 PDF full-source build: 552.620891 с aggregate; затем CSV table projection: 429.910332 с. В visual — изолированный two-pass OCR: 461.093189 с. В instrumented Gate 2 — private artifact discovery/validation: 65.893316 с. |
| Почему Gate 1 требует до ~7 GB RSS? | На одном proof одновременно живёт граф из 1531 JSON records размером 1.463 GB, включая 1.221 GB source payloads, плюс decoded Python objects, base64/строки, индексы и глубокие копии. Фактическое отношение peak RSS к сериализованному графу — около 4.8×. Утечка не доказана; доказано большое время жизни графа. |
| Сколько тяжёлых workers безопасно? | Gate 1 — 1; Gate 2 — максимум 2 на измеренном 8-CPU/34-GB host; visual/OCR — 1 в отдельном pool. Дальше обязательна очередь. |
| Может ли Broker Reports случайно вызвать native vectorization? | **Да. P0 guard gap.** Stage и repo одинаковы, но loader принудительно добавляет `process=false` только STT upload, не Broker Reports upload. Native processing может начаться до action. |
| Retention правильно run-scoped? | **Approved flow — да:** 10 target records при 5000 unrelated, unrelated не материализованы и не изменены, global expiry scan отсутствует. Но API ещё не связан с `ArtifactAccessContext`, а повторный/concurrent expiry выполняет дублирующие UPDATE — это P1. |
| Что оптимизировать первым? | Сначала P0 server-authoritative private intake, затем P1 context-bound/idempotent lifecycle. Первый performance GOAL после этого — bounded lifetime Gate 1 graph и CSV projection. |
| Что можно отложить? | SWIG deprecations, report-size cleanup, UI maintainability, preserved orphan cleanup и Gate 2 micro-optimization, пока P0/P1 не закрыты. |

Итог не маскирует найденные дефекты: цель этого GOAL — измерить и
классифицировать, а не объявить runtime бездолговым.

## 2. Re-entry receipt и live state

### Исходное состояние

- локальная и approved remote ветка: `codex/broker-reports-runtime-audit-v1`;
- local/remote HEAD на входе: `21a08b5dc67f79843dbc4c5c00f96ecdc637e329`;
- относительно `origin/main`: ahead 21, behind 0;
- working tree на входе чистый, staged/unstaged/untracked отсутствовали;
- активен один worktree, заброшенных worktree/локальных delivery branches не
  обнаружено;
- `.env` и `local/` входят в ignored state; tracked entries под `local/` — 0;
- customer/private-файлов в audit delta нет.

Все созданные в ходе аудита commits находятся в текущей линейной ветке. Основные
точки: `cdbd815` — empty-scope contract correction, `1f36c70` — корректные phase
markers, `fd5a4c1` — Gate 2 benchmark, `f70de03` — capacity, `e141539` — Gate 1
profiler, `d0b3c4b` — product intake audit, `b43541a` — retention harness,
`3b547fc` — visual profiler, `eb8f8e0` — phase/lifecycle evidence.

### Stage delivery и parity

Активный stage container fingerprint:
`sha256:8dbfafc61b79cfdf6bbe7c08da6b65ad6d91ca249c801175f77092ccf0210175`,
container creation timestamp `2026-07-03T13:06:34.991381926Z`.

Повторный live verifier завершился `passed`:

- 18/18 итоговых checks;
- 3/3 active function bundles exact SHA-256 match;
- 12/12 managed prompts exact match;
- 21/21 repository factory-boundary checks;
- stage PyMuPDF 1.26.5 равен required 1.26.5;
- PDF table intake включён и сконфигурирован;
- structural/guided/semantic shadows выключены;
- Sber neutral-table profile выключен и release-gated.

| Runtime object | Repo SHA-256 | Live SHA-256 | Результат |
|---|---|---|---|
| Gate 1 bundle | `9b3895b5…1df` | `9b3895b5…1df` | exact |
| Gate 2 source bundle | `168a3095…f96` | `168a3095…f96` | exact |
| Gate 2 domain bundle | `eb1a9851…54e` | `eb1a9851…54e` | exact |
| Static loader | `28c5eadf…3b2` | `28c5eadf…3b2` | exact |

Следовательно, accepted XML, ZIP, visual и confirmed-empty semantics существуют
не только в локальном source: поддерживаемые bundles доставлены, а generated Gate 1
bundle не stale.

## 3. Confirmed empty source scope

Минимальная contract-hygiene correction выполнена отдельным commit. Итоговая
accounting model:

| Категория | Число |
|---|---:|
| Material visual scopes requiring recovery | 10 |
| Accepted recovered scopes | 10 |
| Confirmed empty source scopes | 1 |
| Unresolved visual scopes | 0 |
| Unsupported visual scopes | 0 |
| Canonical tables / cells | 17 / 623 |

Пустая страница сохраняет source/page identity и render lineage, но не считается
missing, OCR failure или unresolved recovery. Adjacent-page inference и model
invention не применялись. Downstream accounting видит typed empty terminal;
zero-silent-loss остаётся passed. Replay: 10/10 material scopes accepted,
1 confirmed empty, 0 unresolved, 0 Gate 2 errors, 0 provider calls.

## 4. Controlled Gate 2 benchmark

### Методика

Accepted серия выполнена на revision
`1f36c70cba25b96b2ea178744c33d4f81b72f1ea`: Python 3.11.9, SQLite 3.45.1,
Windows, 8 logical CPU, 34.04 GB RAM, один workload fingerprint, 1531 records и
1.463 GB immutable input graph. Выполнены три cold fresh-process, три после
полного OS-cache prewarm и три instrumented warm прогона. Конкурирующие audit
jobs во время accepted измерений отсутствовали.

Во всех девяти прогонах: 681/681 packages passed, 75 source-ready documents,
0 errors, 0 warnings, 0 provider calls; ArtifactStore до/после идентичен.

| Режим | N | Median wall | Диапазон | Median peak RSS |
|---|---:|---:|---:|---:|
| Cold fresh-process | 3 | 53.326727 с | 53.247568–53.354346 с | 4.0117 GB |
| Warm OS cache | 3 | 53.279008 с | 53.200649–53.295719 с | 4.0118 GB |
| Warm instrumented | 3 | 109.639739 с | 109.553120–109.772349 с | 4.0114 GB |

Baseline median 53.287363 с / historical 53.146799 с = 1.002645. Разница 0.26%
классифицирована как `no_regression_measurement_noise`. Полная identity старого
исторического запуска не сохранилась, поэтому не утверждается побитовое равенство
окружений; однако текущий контролируемый путь стабилен и не имеет продуктовой
задержки 112 с.

### Фазовая атрибуция

Instrumented profile нельзя сравнивать по wall с baseline: tracing почти удваивает
время. Он применим для относительной фазовой карты:

| Фаза | Median |
|---|---:|
| Private artifact discovery and validation | 65.893316 с |
| Package enumeration, construction and validation | 40.247032 с |
| Scope readiness reconciliation | 1.100843 с |
| Catalog and DCP resolution | 0.827250 с |
| Store immutability guard | 0.827161 с |
| Coverage/parity aggregation | 0.370397 с |
| Safe-report rendering | 0.231831 с |

Внутри профиля: 935 SQLite queries занимают около 0.228 с, 933 resolver calls
дают 933 unique payload reads и 0 duplicate reads, прочитано 1.324 GB payloads.
Выполнены 45 полных PDF parent validations и 532 cache hits. Следовательно:

- SQLite и reconciliation не являются текущими bottleneck;
- позднее число ~112 с объясняется instrumentation;
- крупная CPU-стоимость находится в строгой повторной validation/checksum работе
  над immutable units и packages;
- cache допустим только в пределах run/context и по integrity identity; глобальный
  persistent cache нарушил бы access/immutability boundary.

## 5. Gate 1 и visual phase performance

### Gate 1 actual profile

Фактический прогон: 104/104 sources получили terminal outcome, normalization
1167.199110 с, full proof 1295.886413 с, profiler total 1298.028570 с, peak RSS
7,045,357,568 bytes. Knowledge/RAG отсутствуют; zero-silent-loss passed.

| Фаза | Calls | Aggregate wall | Интерпретация |
|---|---:|---:|---|
| PDF full-source build | 50 | 552.620891 с | Неизбежный parse + дорогой materialized graph; главный aggregate cost |
| CSV table projection | 2 | 429.910332 с | Непропорциональная цена для 2597 rows / 27,241 cells; safe optimization debt |
| PDF layout parse, nested | — | 298.667163 с | Часть full-source, не складывать повторно |
| PDF text-layer parse, nested | — | 152.773792 с | Часть full-source |
| Operator review tooling | — | 64.524225 с | Proof/review cost, не чистый product normalization |
| Domain ingestion | — | 47.339172 с | Typed domain work |
| Artifact persistence | — | 42.826203 с | Secondary, не главный bottleneck |
| Artifact validation | — | 23.450368 с | Корректностная стоимость |
| Private reload | — | 20.859482 с | Proof overhead |
| XML projections | — | 9.278376 с | Низкая стоимость |
| Visual unit materialization/render | — | 7.249301 / 7.148804 с | Не объясняет 20+ минут |
| PDF projections | — | 3.828653 с | Низкая стоимость |
| ZIP expansion | — | 0.025084 с | Не bottleneck |

Source-byte reads суммарно занимают порядка 0.014 с; storage discovery не причина
задержки. Proof добавляет примерно 128.7 с поверх normalization за operator review,
validation, persistence/reload и итоговые проверки. Это необходимо отделять от
latency обычного product job.

### Memory explanation

Persisted graph содержит 1531 records / 1,462,961,493 serialized JSON bytes:

- 162 source payloads / 1,221,494,446 bytes;
- 934 source units / 149,431,937 bytes;
- 259 projections / 76,319,687 bytes;
- 49 text slices / 13,123,966 bytes.

`normalizer.py:77-83` удерживает списки payloads, units, projections и summaries до
сборки результата; `normalizer.py:246-271` строит full source и projection подряд;
`normalizer.py:474-480` возвращает весь private graph. `full_source.py:284-292`,
`747-803`, `853-911` и другие участки глубоко копируют крупные вложенные структуры.
Одновременно живут decoded bytes, Python dict/list/string objects, base64/JSON,
provenance indexes и сериализованные представления. Это правдоподобно и измеримо
объясняет ~4.8× amplification. Leak или duplicate byte-read loop не доказаны.

Безопасная граница будущей оптимизации: не удалять representations, а сократить их
одновременное время жизни, ввести компактное internal representation и писать
sealed chunks до перехода к следующей source family. Source identities,
review-required memory и zero-silent-loss должны оставаться полными.

### Visual recovery

Actual visual contour: total 530.582069 с, peak RSS 4,119,752,704 bytes,
10/10 material terminal + 1 confirmed empty, 17 tables / 623 cells, 0 errors,
0 provider calls, ArtifactStore unchanged.

| Фаза | Wall |
|---|---:|
| Observation/reconstruction | 461.199209 с |
| Isolated two-pass OCR, 18 calls | 461.093189 с |
| Gate 2 handoff | 59.291924 с |
| Resolver, 1231 reads | 20.972227 с |
| Persist / clone | 3.254221 / 2.197680 с |
| Orientation / grid | 1.574494 / 1.420993 с |
| Decode / canonical validation | 0.354188 / 0.234237 с |

`prove_visual_neutral_tables_actual_corpus.py:272-277` создаёт isolated spawn для
каждого crop; `:185-196` загружает три Paddle models. Таким образом 18 crops
повторно платят за process startup и model loading. Process isolation само по себе
полезно для memory cleanup; debt — lifecycle granularity. Безопасная цель — один
bounded worker на job/model-set с явным terminal shutdown, а не in-process global
OCR singleton.

## 6. Capacity envelope

Реальный Gate 2 contour измерен на revision `14efda4` сначала одним, затем двумя
fresh-process workers. Производственные customer jobs не затрагивались.

| Показатель | 1 worker | 2 workers |
|---|---:|---:|
| Group wall | 54.497682 с | 59.865303 с |
| Worker wall | 53.731399 с | 58.768772 / 59.031550 с |
| Aggregate peak RSS | 4.011 GB | 8.018 GB |
| Minimum available host RAM | 7.645 GB | 3.940 GB |
| Max CPU | 70.8% | 87.5% |
| Swap-in / swap-out delta | 0 / 0 | 0 / 0 |
| Lock errors / retries / failures | 0 / 0 / 0 | 0 / 0 / 0 |

Wall degradation — 1.0808×, throughput — 1.8207×. Каждый worker сохранил
681/681 packages passed, provider calls = 0, store unchanged. Третий worker не
запускался: два оставили 3.94 GB host headroom, а третий ожидаемо требует ещё
~4.01 GB и убирает запас ОС/page cache/transient allocations.

| Workload | Max | Фактический peak | Minimum planning RAM | Container limit | Routing |
|---|---:|---:|---:|---:|---|
| Gate 1 actual normalization/proof | 1 | до исторических ~7.43 GB | 8 GiB | 10 GiB | Обязательная очередь |
| Gate 2 package preparation | 2 | ~4.01 GB/worker | 4.5 GiB | 5 GiB/worker | >2 только через очередь |
| Visual/OCR | 1 | ~4.12 GB parent + child transient | 5 GiB | 6 GiB | Отдельный pool |

Capacity limit не является timeout. Job обязан получить terminal outcome или
остаться в очереди; произвольный wall cutoff запрещён. Перенос envelope на host с
другими CPU/RAM/storage требует короткой повторной capacity qualification.

## 7. Product intake и vectorization safety

Статус: **P0 — `GUARD_GAP_IDENTIFIED`**.

Repo/live loader hash одинаков, поэтому дефект не является deployment drift.
`deploy/openwebui-static/loader.js:419-425` распознаёт Broker Reports document, но
`withProcessFalse()` применяет только к `sttUploadFile`. На `:428-439` Broker file
запоминается уже после успешного original upload. Reload path на `:687-695` снова
получает общий file list, а action на `:1566-1591` использует существующие refs.
Backend pipe на `openwebui_actions/broker_reports_gate1_pipe.py:193-205` принимает
file refs и не имеет feature-owned upload receipt/native-processing-state guard.

Следствие: generic `/api/v1/files/` может начать native document processing до
Broker action. UI convention не является safety boundary. Explicit diagnostic
`process=false` smoke доказал 0 Knowledge/RAG/vector deltas только для явно
правильного маршрута, но не для всего user-facing feature.

Нужен узкий fix:

1. server-owned Broker Reports upload endpoint;
2. сервер принудительно устанавливает `process=false`, client override отсутствует;
3. endpoint выдаёт typed feature receipt с file identity и processing invariant;
4. action принимает только receipt или server-verified equivalent;
5. native-processed/incompatible file ref отклоняется до normalization;
6. post-upload invariant проверяет отсутствие Knowledge/RAG/vector/native state;
7. cleanup остаётся defense in depth, а не основным механизмом безопасности.

UI integrity: действие сейчас видимо и имеет running/completed/error feedback, но
состояние безопасности не выражено серверным контрактом. После fix UI должен
показывать upload rejection и не предлагать run для несовместимого ref; бизнес-
проверка остаётся вне DOM-loader.

## 8. Retention и lifecycle

### Что доказано

Disposable real SQLite/filesystem audit с 5000 unrelated + 10 target records:

| Показатель | Результат |
|---|---:|
| Target examined / changed | 10 / 10 |
| Unrelated materialized / changed | 0 / 0 |
| SQL | 1 SELECT + 10 UPDATE |
| SQL execute time | 0.001898 с |
| Operation wall | 0.008314 с |
| Transaction | одна connection transaction |
| Approved-flow global expiry scan | отсутствует |

Approved pipe получает normalization run из server-side normalization result и
вызывает `expire_run`. Query на `artifact_store.py:260-271` использует indexed
`normalization_run_id` predicate; unrelated records не читаются. Cleanup exception
на реальном filesystem path propagates, false terminal success не выдаётся,
record остаётся `purge_pending`; purged/tombstoned payload не разрешается.

### Contract gaps

- `artifact_store.py:224-237` принимает только строковый run id, не
  `ArtifactAccessContext`; внутри API нет совмещённого `user_id/case_id/run_id`
  predicate. В approved flow строка trusted, но API нельзя безопасно расширять на
  новые callers без context binding.
- `:272-294` повторно UPDATE-ит уже expired records и меняет `updated_at`;
  terminal state верен, но audit idempotence не строгая.
- два concurrent callers оба выполнили работу и суммарно сообщили 20 changes для
  10 records; ошибок/потери нет, но duplicate work существует.
- `:221-222` сохраняет публичный global `expire_artifacts`; approved flow его не
  использует, однако misuse surface остаётся.
- source deletion, chat purge и case purge используют `_active_records()` на
  `:316-375`, а `:495-505` выполняет global active scan.
- `purge_run` на `:297-314` последовательно меняет состояние, удаляет файл и снова
  открывает transactions; failure semantics честные, но операция не batch-atomic.

Поэтому required status честно формулируется так: `RETENTION_RUN_SCOPE: PROVEN`
и `GLOBAL_EXPIRY_SCAN: ABSENT_IN_APPROVED_FLOW`, одновременно P1 context/idempotence
debt остаётся открытым.

## 9. Полный technical-debt register

| ID / priority / class | Path и измеренное evidence | Product impact / likelihood / severity | Owner и contract risk | Complexity / timing | Acceptance proof |
|---|---|---|---|---|---|
| TD-01 / **P0** / product-route, privacy/security | `loader.js:419-439`; pipe `:193-205`; live/repo exact. Broker upload не forced false до generic upload. | Возможны embeddings/vector/native artifacts; likelihood medium, severity critical. | Upload/API + Broker action. Риск privacy boundary высокий. | M; немедленно, следующий GOAL. | Browser/API test не может override false; incompatible ref rejected; pre/post Knowledge/RAG/vector diff = 0; retries/reload covered. |
| TD-02 / **P1** / lifecycle, correctness/privacy | `artifact_store.py:224-237`: run string без `ArtifactAccessContext`. Approved caller trusted, API predicate не tenant/case-bound. | Ошибочный trusted caller сможет выбрать чужой run; likelihood low сейчас/high при reuse, severity high. | ArtifactStore API. Access contract risk высокий. | M; до scale/reuse. | Wrong user/case/run denied одним SQL predicate; same-context path passes; cross-run rows untouched. |
| TD-03 / **P1** / lifecycle, concurrency | `:272-294`; repeat обновляет 10/10 снова, concurrent callers сообщают duplicate 20. | Лишние writes/audit noise и race surface; likelihood high under scheduler overlap, severity medium-high. | ArtifactStore lifecycle. Terminal correctness risk medium. | M; вместе с TD-02. | Conditional atomic UPDATE only from eligible states; second run reports 0; concurrent total unique changes = 10; timestamps stable. |
| TD-04 / **P1** / performance, memory/capacity | `normalizer.py:77-83,246-271,474-480`; `full_source.py` deep copies. 1.463 GB serialized graph, peak 7.05 GB, normalization 1167 с. | Ограничивает Gate 1 одним worker, повышает OOM risk; likelihood high, severity high before scale. | Gate 1 normalizer/full source. Immutability/zero-loss risk высокий. | L; первый performance GOAL. | Same 104/104 terminals and digests; peak RSS materially lower; no representation/source identity dropped; failure resume/cleanup proven. |
| TD-05 / **P1** / capacity/operations | Measured safe max: Gate1 1, Gate2 2, visual 1; production enforcement/queue not part of audit. | Без admission control возможен OOM/host starvation; likelihood medium, severity high. | Runtime scheduler/deployment. Terminal-state risk medium. | M; before concurrency scale. | Queue/load test respects class limits; no timeout; terminal and cleanup outcomes under saturation. |
| TD-06 / **P2** / visual performance | OCR spawn/model load per crop at visual proof `:185-196,272-277`; 18 calls / 461.09 с. | ~87% visual wall, slow feedback; likelihood certain, severity medium. | Visual worker. Isolation/cleanup risk high. | M; after P0/P1. | Reusable job-scoped isolated worker; identical canonical hashes/uncertainty; bounded RSS; crash/restart cleanup; materially lower wall. |
| TD-07 / **P2** / Gate 1 performance | `normalizer.py:257-270`, table projection factory; two CSVs / 27,241 cells cost 429.91 с. | Непропорциональная latency на CSV; likelihood high for large tables, severity medium. | Table projection. Provenance risk high. | M. | Operation-count profiler; identical cell/source provenance and checksums; wall reduction on frozen CSV corpus. |
| TD-08 / **P2** / Gate 2 performance/store | 933 resolver reads / 1.324 GB; 219,654 PDF and 365,989 provenance checksum operations; discovery/validation 65.89 instrumented. | CPU и memory bandwidth; likelihood certain, severity medium. | Gate2 readiness/resolver. Validation strictness risk high. | M. | Run-scoped bulk resolve + integrity-key cache; 681/681 identical; corrupt mutation always invalidates; provider/store invariants unchanged. |
| TD-09 / **P2** / lifecycle performance | `artifact_store.py:316-375,495-505`: source/chat/case cleanup traverses all active records. | Повторение retention global-scan incident на delete/purge; likelihood grows with store, severity medium-high. | ArtifactStore cleanup. Cross-scope risk medium. | M; with lifecycle GOAL. | Indexed source/chat/case predicates; thousands unrelated not materialized/changed; query/lock bounds measured. |
| TD-10 / **P2** / lifecycle correctness | `purge_run :297-314` — status/file/status across multiple transactions. Failure leaves honest pending, но batch progress не formalized. | Долгий/частичный cleanup требует retry semantics; likelihood medium, severity medium. | ArtifactStore purge. No-false-success contract risk medium. | M. | Fault injection at each boundary; resumable pending state; repeated purge converges; tombstones unresolvable. |
| TD-11 / **P2** / observability, product | Long jobs have coarse phase events, no durable per-document progress/cancellation contract. Gate1 19+ min, visual 8.8 min. | Пользователь не отличает progress от stall; unsafe manual retries; likelihood high, severity medium. | Job orchestration/UI. Cleanup risk high. | M. | Typed phase/document progress; cooperative cancel produces terminal cancelled + cleanup; no partial success. |
| TD-12 / **P2** / dependency/operations | Paddle model cache under non-ASCII host path required ASCII junction for actual proof. | Audit/runtime portability failure on Windows Unicode path; likelihood environment-dependent, severity medium. | OCR bootstrap/deployment. Privacy risk low. | S–M. | Fresh non-ASCII path smoke without junction or documented owned ASCII cache root; exact model digests. |
| TD-13 / **P3** / dependency | Full regression: five PyMuPDF SWIG deprecations (`SwigPyPacked`, `SwigPyObject`, `swigvarlink`). | Future upgrade noise/compatibility, no current product failure; likelihood medium horizon, severity low. | Dependency maintenance. Contract risk low. | S research + pinned upgrade. | Clean supported-version matrix, 976+ tests, layout/PDF live smoke, zero warning regression. |
| TD-14 / **P3** / privacy hygiene | Один unrelated pre-existing orphan vector directory сохранён; audit не создавал свежих orphan. | Storage clutter/unclear ownership; current customer impact not proven, severity low. | OpenWebUI vector lifecycle owner. Deletion risk high без ownership proof. | S after owner classification. | Typed ownership inventory; delete only proven orphan; before/after unrelated state unchanged. |
| TD-15 / **P3** / report maintainability | Gate1 safe aggregate около 144 KB. Customer values отсутствуют, но schema растёт. | Review/CI ergonomics, не runtime; likelihood high, severity low. | Evidence/reporting. Audit completeness risk medium. | S–M. | Versioned summary/detail split; validators prove counts/digests equivalent; privacy scan passes. |
| TD-16 / **P3** / UI maintainability | Static loader monkey-patches fetch и восстанавливает files через generic list. | DOM/API drift может ломать UX; current stage parity exact, severity low-medium. | UI integration. Product-route risk medium, отдельный от TD-01. | M, после server endpoint. | Browser regression: upload/reload/retry/status/accessibility; feature logic не зависит от DOM inference. |
| TD-17 / **P3** / customer-debt status | Sber same-family positive holdout не получен; valve false. | Блокирует только включение frozen profile, не общий runtime audit. | Product/customer acceptance. Financial correctness risk critical при преждевременном enable. | External acceptance. | Owner-approved holdout passes frozen contract; valve enable отдельным release decision. |
| TD-18 / **P3** / documentation/status | Исторические отчёты используют 11/11 recovery accounting; актуальная модель 10 material + 1 empty. | Риск неверной управленческой интерпретации, runtime не затронут. | Documentation/status. Contract risk low. | S. | Current index/closure documents point to typed accounting; historical evidence остаётся immutable. |

### Rejected hypotheses

| Гипотеза | Решение и evidence |
|---|---|
| Gate 2 имеет подтверждённую 2.1× regression | Отклонена: accepted baseline 53.287 с; 109.64 с только instrumented. |
| Reconciliation — текущий 67-секундный bottleneck | Отклонена: корректные dynamic markers дали 1.100843 с. Старые line boundaries были stale. |
| SQLite — Gate 2 bottleneck | Отклонена: 935 queries / ~0.228 с. |
| Duplicate resolver reads — главный Gate 2 defect | Отклонена в текущем call: 933/933 reads unique. Bulk access всё ещё P2 из-за общего объёма. |
| Source byte I/O объясняет Gate 1 20 минут | Отклонена: source byte reads ~0.014 с; CPU parse/projection доминируют. |
| Visual render/orientation/grid доминируют | Отклонена: вместе единицы секунд против OCR 461 с. |
| Наблюдается memory leak | Не доказана. Доказан большой одновременно живущий Python/JSON graph; leak требует отдельного repeated-process heap proof. |
| Stage/local PyMuPDF drift | Отклонена: 1.26.5 = 1.26.5 и live verifier passed. |

## 10. Ranked optimization opportunities

Рейтинг учитывает не только wall benefit, но correctness/privacy risk.

| Rank | Кандидат | Expected benefit / confidence | Risk и границы | Проверка | Next GOAL? |
|---:|---|---|---|---|---|
| 1 | Server-authoritative private intake + native-state rejection | Устраняет P0 vectorization race; confidence high. Не speed optimization. | Implementation M; privacy risk снижается; immutability/zero-loss не меняются. | API/browser negative tests, forced false, typed receipt, state diff 0. | **Да, немедленно** |
| 2 | Context-bound conditional expiry + indexed cleanup | Закрывает cross-run misuse и duplicate writes; confidence high. | SQL/transaction change, correctness risk medium. | Wrong-context/concurrent/repeat/failure suite на тысячах unrelated. | **Да, вторым** |
| 3 | Bounded streaming/lifetime Gate 1 graph | Потенциально существенно снижает ~7 GB peak и даёт capacity margin; confidence medium-high. | Высокий риск потерять lineage/representation; только small slices. | Frozen actual aggregate digests, 104/104 terminal, peak/phase before-after. | **Да, первый performance GOAL** |
| 4 | CSV projection identity maps и сокращение repeated cell work | Снижает до 429.9 с на двух CSV; confidence high по phase time, exact mechanism требует operation probe. | Provenance/ordering risk medium-high. | Same 27,241 cell identities/checksums, operation counts и wall. | В составе rank 3 GOAL |
| 5 | Job-scoped reusable isolated OCR worker | Может убрать многократную загрузку трёх models на 18 crops; confidence high. | Crash cleanup/model state leakage; global singleton запрещён. | Identical 17 tables/623 cells, per-crop uncertainty, bounded RSS, failure recovery. | После Gate 1 memory slice |
| 6 | Run-scoped immutable validation/checksum cache + bulk resolver API | Сокращает CPU на 933 reads/сотнях тысяч checksum operations; confidence medium-high. | Stale/unscoped cache опасен; persistent global cache запрещён. | Mutation invalidation, context denial, 681/681 digest parity. | Отдельный поздний GOAL |
| 7 | Typed progress и cooperative cancellation | Не ускоряет compute, но снижает false retries и улучшает длинный UX; confidence high. | Нельзя превращать cancel в silent partial success. | Durable phase states, terminal cancelled, cleanup and resume tests. | Вместе с worker orchestration |
| 8 | Safe report summary/detail split и dependency cleanup | Maintainability only; confidence high, product benefit low. | Не потерять audit evidence. | Validator parity, full regression, privacy scan. | Нет, P3 batch |

Не рекомендуются arbitrary timeouts, truncation packages/tables, dropping
review-required scopes, ослабление validation, удаление source identities,
model canonical authority, whole-document provider upload, unbounded concurrency
или unscoped persistent caches.

## 11. Recommended GOAL sequence

### Next engineering GOAL

`Broker Reports — Server-Authoritative Private Intake And Native-Processing Rejection v1`

Минимальный objective: все Broker Reports uploads проходят feature-owned server
boundary с forced `process=false`; action принимает только typed receipt и
отклоняет native-processed/incompatible refs. Knowledge/RAG/vector/native state
до и после upload/retry/reload остаётся неизменным. Cleanup — только defense in
depth. Не менять normalizer semantics.

### Следующая очередь

1. `Broker Reports — Context-Bound Idempotent Lifecycle And Indexed Cleanup v1`.
2. `Broker Reports — Gate1 Bounded Graph Lifetime And CSV Projection Performance v1`.
3. `Broker Reports — Reusable Isolated OCR Worker And Workload Queue Separation v1`.
4. `Broker Reports — Gate2 Bulk Resolution And Immutable Validation Cache v1`.

Каждый GOAL должен иметь один domain boundary, before/after measurement и
отдельное доказательство invariants. Не следует объединять upload security,
ArtifactStore transaction redesign и Gate 1 memory refactor в один delivery.

## 12. Verification, evidence integrity и limitations

- Full service regression: **976 passed**, 5 dependency warnings, 0 failed.
- Пять warnings точно относятся к SWIG/PyMuPDF import deprecations, а не к product
  contract.
- Ruff: all checks passed для 21 maintainable Python files, изменённых этим GOAL.
  Generated bundled file исключён из generic E402 lint, поскольку является
  детерминированной concatenation; его проверяют bundle tests и exact live hash.
- Live parity: 18/18; bundles 3/3; prompts 12/12; factory checks 21/21.
- JSON safe evidence parse и privacy/path/token scan: passed.
- Gate 1/visual actual raw profiles, corpus, SQLite clones, payload graphs и OCR
  images не коммитились.
- Один pre-existing unrelated vector orphan сохранён: без ownership proof удаление
  было бы более опасно, чем консервативное сохранение.
- Capacity относится к измеренному 8-CPU/34-GB host. Disk queue depth portable
  sampler не дал; вывод опирается на wall, RSS, available RAM, CPU, bytes, lock/
  retry/failure и terminal correctness.

Связанные подробные evidence:

- `BROKER_REPORTS_GATE2_CONTROLLED_BENCHMARK.v1.report.md`;
- `BROKER_REPORTS_GATE1_AND_VISUAL_PHASE_PERFORMANCE.v1.report.md`;
- `BROKER_REPORTS_CAPACITY_AND_CONCURRENCY.v1.report.md`;
- `BROKER_REPORTS_PRODUCT_INTAKE_AND_VECTORIZATION.v1.report.md`;
- `BROKER_REPORTS_RETENTION_AND_LIFECYCLE.v1.report.md`;
- `BROKER_REPORTS_RUNTIME_TECHNICAL_DEBT_AUDIT.v1.safe.json`.

## 13. Required final status

```text
BROKER_REPORTS_RUNTIME_AND_TECHNICAL_DEBT_AUDIT:
COMPLETED

CONFIRMED_EMPTY_SOURCE_SCOPE:
RECORDED_AND_NOT_A_BLOCKER

REPOSITORY_LIVE_REENTRY:
PROVEN

GATE2_PERFORMANCE_STATUS:
NO_REGRESSION

GATE1_PERFORMANCE:
PHASE_ATTRIBUTED

CAPACITY_ENVELOPE:
MEASURED

PRODUCT_PROCESS_FALSE_PATH:
GUARD_GAP_IDENTIFIED

RETENTION_RUN_SCOPE:
PROVEN

GLOBAL_EXPIRY_SCAN:
ABSENT_IN_APPROVED_FLOW

TECHNICAL_DEBT:
CLASSIFIED_AND_PRIORITIZED

OPTIMIZATION_CANDIDATES:
RANKED_BY_EVIDENCE

CORRECTNESS_ZERO_SILENT_LOSS_AND_PRIVACY:
PRESERVED

NEXT_ENGINEERING_GOAL:
READY
```
