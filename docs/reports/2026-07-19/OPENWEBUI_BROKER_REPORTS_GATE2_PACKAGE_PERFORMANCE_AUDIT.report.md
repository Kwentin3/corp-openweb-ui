# Broker Reports Gate 2 Package Preparation Performance Audit

Дата измерений: 2026-07-19
Статус: завершённый evidence-driven audit; production-оптимизации не выполнялись

## 1. Executive verdict

Ранее наблюдавшаяся задержка воспроизведена на фактическом Gate 1 memory graph.
Ненагруженный baseline завершился за `3519.572 s` (`58:39.572`). Из них
`3509.563 s`, или `99.716%` wall time одного CPU-потока, были заняты локальным
CPU. Provider/LLM calls, retries, tokens, provider latency, package persistence
и package serialization в измеряемом slow path равны нулю.

Главный bottleneck — не package construction и не хранилище, а повторная
детерминированная проверка PDF parent payload внутри discovery/validation:

- `822` PDF units вызвали `822` полных parent-payload validations;
- parent payloads, загруженных для всего run, всего `162`, поэтому даже при
  максимально благоприятном распределении не менее `660` вызовов (`80.3%`)
  повторны;
- детальный trace зарегистрировал `6,812,794` PDF checksum calls;
- нормированная оценка parent-validation вклада в baseline — около `3386 s`
  (`56:26`, `96.2%` trace share);
- прямой узкий замер всей discovery/validation фазы — `3692.409 / 3707.240 s`,
  или `99.600%` контрольного run.

Второй измеренный bottleneck — eager validation `98` table projections, которые
при фактическом `prefer_table_projections=False` не были выбраны ни для одного
из `837` пакетов. Прямой контрольный вклад — `95.885 s`. Внутри этого
валидатора per-ref lookup повторно линейно сканирует `source_value_index`;
контролируемый CSV scaling показывает superlinear рост, приближающийся к
quadratic при увеличении rows.

Следовательно, сначала требуется устранить повторную parent validation,
выполнять input-strategy selection до дорогой валидации невыбранных
представлений и заменить per-ref scans на batch index. Timeout, truncation,
resumable processing, lazy execution и concurrency не являются первой мерой.

## 2. Exact measured slow path

Поддерживаемый entrypoint —
`services/broker-reports-gate1-proof/scripts/prove_gate1_actual_customer_corpus.py:197-202`:

`Gate2InputReadinessFactory(store=store).create().audit_and_build(...)`.

Factory создаёт `Gate2InputReadinessService` в
`services/broker-reports-gate1-proof/broker_reports_gate1/gate2_input_readiness.py:95-109`.
Измеренный slow path начинается в `audit_and_build` на строке 124 и включает:

1. два run-catalog reads (`:135`, `:426`) и DCP/public-boundary resolution;
2. document-memory validation (`:175`), passports и handoff audit;
3. private artifact discovery/validation (`:206`, реализация `:532-729`);
4. scope-readiness indexing;
5. candidate enumeration, in-memory package construction и validation
   (`:256-410`);
6. coverage/accounting, ArtifactStore immutability guard и safe report render.

Этот maintained path заканчивается до provider factory/client, package
persistence и byte serialization. Построенные packages остаются in-memory и
содержат `model_call_performed=False`
(`gate2_input_readiness.py:1201`). Динамические sentinels дополнительно
подтвердили нулевой call count provider client и transport.

## 3. Baseline and repeatability

### Environment

| Параметр | Значение |
|---|---|
| Measured repository revision | `2eadb7e3d6251980e1eee4206d91206bdc0bd92c` |
| Actual run label | `actual_gate1_20260718T182125Z` |
| Workload fingerprint | `8bc80a70c4f228670dcf71acdd824389b63215308f377a9cfe8436c0fccdc9b7` |
| Python / SQLite | `3.11.9` / `3.45.1` |
| psutil / pypdf | `7.1.2` / `6.7.5` |
| Host | Windows Server 2019 `10.0.17763` |
| CPU / RAM | Intel i7-4770, 4 cores / 8 logical; `34,039,119,872` bytes |
| Storage | local fixed NTFS proof root; raw evidence outside Git |
| Gate 1 bundle revision | `99ed3acf67b650444c5919f1030155ce89d5bbdbddb447bfb8671856913f39df` |
| Gate 2 source-fact bundle revision | `6ca9969c1ddd768cf5677259211cc40cb3fd352eb36c96e5a9bbf7c0c9c98645` |
| Gate 2 domain bundle revision | `829dcc885828df206f228a2151752339f0647a8be6d3b0ed1a872931f67d9679` |

Измерялся repository proof path, а не deployed stage bundle. Bundle hashes
приведены для связи с принятым Gate 1 corpus; runtime/stage delivery в этом
аудите не требовалась.

### Full-corpus runs

| Run | Cache / contention | Wall, s | CPU user+system, s | Incremental peak RSS | Outcome |
|---|---|---:|---:|---:|---|
| Baseline | first process | `3519.572` | `3509.563` | `4,282,335,232 B` | terminal fail-closed |
| Narrow counters | warm, большую часть времени рядом шёл 1-core diagnostic trace | `3707.240` | `3696.984` | `4,282,568,704 B` | тот же outcome |
| Detailed trace | warm; intentionally high overhead | `14372.412` | `14340.906` | `4,282,490,880 B` | тот же outcome |

Detailed trace замедлил run в `4.083x` относительно baseline. Поэтому его
абсолютная длительность не считается продуктовой; он используется для call
counts и относительной attribution. Narrow mode не использует line tracing и
per-hash timers. Совпадение narrow direct phase share и нормированного detailed
phase share лучше `0.1` процентного пункта подтверждает главную фазу.

Полный corpus не повторялся несколько раз в идентичном baseline mode из-за
стоимости около часа. Вместо ложной точности использованы три семантически
эквивалентных full runs с разной нагрузкой instrumentation и по три независимых
повтора каждой controlled scaling point. Во всех full runs совпали package,
error, warning, I/O и immutability outcomes.

## 4. Phase timing decomposition

Аддитивная декомпозиция основана на narrow run. Вложенные resolver/store и
validator времена показаны далее как cross-cut attribution и не складываются
повторно с фазами.

| Additive phase | Narrow direct, s | Доля | Baseline-equivalent estimate, s | Метод |
|---|---:|---:|---:|---|
| Gate 1/DCP boundary, catalog, handoff, scope/coverage/report | `0.619-0.842` | `0.017-0.023%` | `0.59-0.80` | direct lower bound + residual upper bound |
| Private artifact discovery, resolution and preselection validation | `3692.409` | `99.600%` | `3505.49` | direct phase timer, share applied to baseline |
| Candidate enumeration, package construction and package validation | `13.989-14.212` | `0.377-0.383%` | `13.28-13.49` | direct construction+validation lower bound, residual upper bound |
| Package byte serialization | `0` | `0%` | `0` | call counter |
| Package persistence | `0` | `0%` | `0` | call counter |
| Provider/LLM | `0` | `0%` | `0` | client/transport sentinels |
| **Total** | **`3707.240`** | **`100%`** | **`3519.572`** | observed |

Cross-cut timings внутри discovery/validation:

| Operation | Calls | Narrow direct / normalized estimate | Interpretation |
|---|---:|---:|---|
| PDF parent payload validation | `822` | baseline estimate `3385.63 s` | primary bottleneck; estimate normalized from detailed trace |
| Table projection validation | `98` | direct `95.885 s`; baseline-equivalent `91.03 s` | all 98 were unselected in actual package output |
| Resolver resolve | `1254` | direct inclusive `21.145 s` | includes record lookup and payload read |
| ArtifactStore payload read + JSON decode | `1254` | direct inclusive `20.290 s` | secondary; `1,455,533,632 B` |
| SQLite SELECT execution | `1256` | direct cumulative `0.342 s` | N+1 exists, but is not primary |
| Source-fact package validation | `837` | direct `11.425 s` | post-discovery secondary cost |
| Source-fact package construction | `837` | direct `2.564 s` | eager, but not the time bottleneck |
| Safe report render | `1` | direct `0.053 s` | negligible |

Heavy trace cross-check:

- private discovery/validation: `14328.018 / 14372.412 s` (`99.691%`);
- package enumeration/construction/validation: `42.336 s` (`0.295%`);
- PDF parent validation: `13825.434 s` (`96.194%`);
- table projection validation: `413.513 s` (`2.877%`).

## 5. Provider/LLM attribution

| Metric | Actual baseline / instrumented full run |
|---|---:|
| Provider client calls | `0` |
| Provider transport/completion calls | `0` |
| Provider retries/fallback calls | `0` |
| Provider latency | `0.000 s` |
| Input tokens | `0` |
| Output tokens | `0` |
| Packages claiming model call | `0 / 837` |
| Provider share of observed delay | `0%` |

Ответ: наблюдавшаяся задержка LLM не включала. Provider inference начинается в
другом, более позднем execution path; смешивать его будущую latency с package
preparation нельзя.

## 6. Package fan-out map

Actual corpus содержит `104` source records и `80` logical documents. Persisted
Gate 1 run catalog содержит `1531` artifact records и `104` document ids;
archives/promoted members объясняют отличие от logical-document count.

| Fan-out stage | Count |
|---|---:|
| DCP source-ready refs | `103` |
| Package candidates enumerated | `928` |
| Packages built and passed | `837` |
| Visual candidates explicitly deferred | `63` |
| Other candidates not built because their documents fail readiness | `28` |
| Packageable documents | `51` |
| Unpackageable source-ready documents | `52` |
| Duplicate package ids | `0` |

`928 = 837 + 63 + 28`; silent candidate loss не обнаружен.

Пакетов на packageable document: min `1`, mean `16.412`, max `65`.

| Unit kind | Packages |
|---|---:|
| PDF page text | `533` |
| PDF table candidate | `194` |
| PDF line cluster | `30` |
| Table row window | `41` |
| Text slice | `39` |
| **Total** | **`837`** |

Все `837` actual packages используют `source_input_mode=full_source_unit`.
Package list создаётся eagerly (`packages=[]`, затем `append`) и полностью
остаётся в памяти. Однако измеренные construction+package-validation занимают
около `14 s`, поэтому lazy generation может уменьшить memory/backpressure, но
не устранит почти часовую причину.

### Representative formats

| Workload | Sources | Wall, s | Candidates | Built | Explicit outcome |
|---|---:|---:|---:|---:|---|
| CSV | 1 | `0.072` | 1 | 1 | passed |
| HTML | 1 | `0.077` | 3 | 3 | passed |
| PDF | 1 | `0.064` | 2 | 2 | passed |
| XML | 1 | `0.317` | 1 | 0 | fail-closed memory-policy mismatch |
| ZIP with promoted members | 1 | `0.357` | 3 | 2 | XML member fail-closed |
| review_required visual | 1 | `0.059` | 3 | 2 | 1 visual explicitly deferred |
| Mixed 6 formats | 6 | `0.818` | 13 | 10 | explicit XML/visual outcomes |

Provider calls во всех representative runs равны нулю.

## 7. Resolver, store and query profile

| Metric | Actual full run |
|---|---:|
| Catalog traversals | `2` |
| Records in each catalog | `1531` |
| Resolver resolves | `1254` |
| Unique payloads read | `1254` |
| Duplicate payload reads | `0` |
| Records returned, including two catalogs | `4316` |
| Payload bytes read/materialized | `1,455,533,632` |
| SQLite queries | `1256 SELECT` |
| SQLite cumulative execute time | `0.342 s` |

ArtifactResolver сначала выполняет отдельный `get_record_unchecked`, затем
`read_payload` (`artifact_resolver.py:22-30`). ArtifactStore открывает SQLite
connection/query на каждый get и отдельный query для catalog
(`artifact_store.py:166-185`), после чего читает JSON payload file
(`artifact_store.py:209-219`). Это подтверждённый N+1 pattern: два catalog
queries плюс один SELECT на каждый из `1254` artifacts.

Но N+1 — вторичный долг. Query execute занимает `0.342 s`, весь resolver
inclusive — `21.145 s`, тогда как discovery/validation — `3692.409 s`.
Повторного чтения одного immutable payload в одном run нет; обычный artifact
payload cache не является первой оптимизацией.

## 8. CPU, memory and I/O

Baseline:

- wall: `3519.572 s`;
- CPU user: `3503.844 s`;
- CPU system: `5.719 s`;
- CPU/wall одного потока: `99.716%`;
- incremental sampled peak RSS: `4,282,335,232 B` (`3.99 GiB`);
- disk reads: `19,380` operations / `1,513,838,243 B`;
- disk writes observed by process: `2,686` / `10,973,438 B`;
- ArtifactStore before/after catalog identity: unchanged.

Средняя physical-read пропускная способность за wall interval меньше
`0.5 MB/s`; процесс почти непрерывно расходует CPU, а не ждёт диск. Высокий RSS
объясняется eager retention всех parent payload dicts и всех unit/projection
graphs, затем deep copies крупных provenance/index structures при package build
(`gate2_input_readiness.py:935-1011`). GC pressure правдоподобна, но отдельно
не измерялась и потому не объявляется самостоятельной причиной.

## 9. Scaling behavior

Каждая точка ниже — median трёх отдельных warm-OS-cache narrow runs; min/max
указаны для noise control. Gate 1 setup и synthetic persistence находились вне
timed contour.

### Rows внутри одного CSV document

| Rows | Wall median, s | Min-max, s | Private phase, s | Table validation, s | Packages |
|---:|---:|---:|---:|---:|---:|
| 10 | `0.0268` | `0.0265-0.0277` | `0.0120` | `0.0033` | 1 |
| 25 | `0.0380` | `0.0375-0.0410` | `0.0207` | `0.0085` | 1 |
| 50 | `0.0608` | `0.0605-0.0618` | `0.0383` | `0.0203` | 1 |
| 100 | `0.1247` | `0.1227-0.1258` | `0.0902` | `0.0569` | 1 |
| 200 | `0.3129` | `0.3099-0.3175` | `0.2472` | `0.1747` | 1 |
| 400 | `0.9426` | `0.9320-0.9528` | `0.7815` | `0.6090` | 1 |

При удвоении `100→200→400` table validation растёт примерно `3.07x` и
`3.49x`. Код подтверждает причину: `TableProjectionValidator` проходит каждый
`source_value_ref` (`table_projection.py:689`) и вызывает
`resolve_source_value`, который снова линейно сканирует весь index
(`source_provenance.py:747-755`). Рядом уже есть batch implementation с
однократной индексацией (`source_provenance.py:758-775`). Timing не используется
как единственное доказательство formal complexity; вместе с кодом он
характеризует этот участок как superlinear, приближающийся к quadratic.

### Число документов при фиксированных 50 CSV rows

| Documents | Wall median, s | Private phase, s | Table validation, s | Packages | Reads |
|---:|---:|---:|---:|---:|---:|
| 1 | `0.0616` | `0.0393` | `0.0208` | 1 | 9 |
| 2 | `0.1132` | `0.0781` | `0.0414` | 2 | 13 |
| 4 | `0.2185` | `0.1566` | `0.0836` | 4 | 21 |
| 8 | `0.4211` | `0.3130` | `0.1655` | 8 | 37 |
| 16 | `0.8691` | `0.6590` | `0.3343` | 16 | 69 |
| 32 | `1.7182` | `1.3122` | `0.6784` | 32 | 133 |

Document fan-out при фиксированном размере приблизительно линейный. Reads
следуют формуле `5 + 4N`; packages — `N`.

### Простые PDF documents

| Documents | Wall median, s | Private phase, s | Packages | Reads |
|---:|---:|---:|---:|---:|
| 1 | `0.0267` | `0.0115` | 2 | 10 |
| 2 | `0.0416` | `0.0218` | 4 | 15 |
| 4 | `0.0721` | `0.0436` | 8 | 25 |
| 8 | `0.1390` | `0.0912` | 16 | 45 |
| 16 | `0.2654` | `0.1808` | 32 | 85 |

Небольшие одинаковые PDFs масштабируются приблизительно линейно по documents
и units. Поэтому фактическая аномалия — не сам формат PDF, а повторная полная
валидация крупных shared parent graphs для множества units.

Mixed subsets `6→12` дают `1.954→3.908 s`, то есть примерно линейное
удвоение. Оба результата fail-closed из-за уже описанного XML memory-status
разрыва, а не из-за timeout.

## 10. Confirmed bottleneck register

| Severity | Issue and measured impact | Exact path | Workload / correctness risk |
|---|---|---|---|
| Critical | Full PDF parent revalidated `822` times; at least `660` duplicate calls; `6.81M` checksum calls; ≈`3386 s` baseline estimate | `gate2_input_readiness.py:623-650`; `pdf_text_layer.py:841-951`, especially `:926` | Actual PDF-heavy corpus. Optimization must retain one full validation per immutable parent and per-unit linkage checks. |
| High | All `98` ready table projections validated before selection although all `837` packages use full units; direct `95.885 s` | load/validate `gate2_input_readiness.py:572-603`; selection only `:687-714`; default `:85` | Actual corpus and table-heavy inputs. Scope/accounting must explicitly record unselected representations. |
| High | Per-ref full-index scans in table and PDF source-value lookup; CSV doubling approaches quadratic | `table_projection.py:689-693`; `source_provenance.py:747-755`; `pdf_layout_units.py:1007-1028` | Large tables/PDF layout indices. Batch map must preserve uniqueness and checksum errors. |
| Medium | Eager load/retention of `162` parent payloads, `934` units, `98` selected-for-validation projections and compatibility slices; peak +`4.28 GB` RSS | `gate2_input_readiness.py:558-681` | Actual corpus. Selection cannot silently omit refs or weaken access/lifecycle enforcement. |
| Medium | PDF unit validation occurs once through `validate_full_source_unit` and again with parent linkage; 822 inner + 822 parent calls | `full_source.py:1885-1928`; `gate2_input_readiness.py:623-650` | PDF units. Split reusable unit validation from parent-specific validation without dropping either contract. |
| Low/medium | N+1 SQLite record lookup: `1256` SELECTs, but only `0.342 s` execute time | `artifact_resolver.py:22-30`; `artifact_store.py:166-185` | All formats. Query consolidation is safe after hot validation fixes. |
| Low for latency, medium for memory | Eager construction/deep-copy of all `837` packages; ≈`14 s`, large copied indices | `gate2_input_readiness.py:256-410`, `:935-1011` | Actual corpus. Lazy iteration may reduce peak graph size, but cannot substitute for duplicate-validation removal. |

Latent but not exercised in actual default route: when table projections are
selected, builder validates the projection/package and the outer readiness
path validates the package again (`gate2_table_packages.py:49,271` and
`gate2_input_readiness.py:317,372`). Это отдельный regression target, но ему не
приписывается measured actual-corpus time.

## 11. Rejected hypotheses

- **LLM/provider latency:** rejected; exact calls/retries/tokens/latency `0`.
- **Provider rejection causes local recomputation:** rejected for this path;
  provider boundary не достигнут.
- **Package persistence/serialization:** rejected; calls and output bytes `0`;
  safe report render `0.053 s`, probe JSON serialization находится после timer.
- **SQLite/storage as primary cause:** rejected; query `0.342 s`, payload
  read+decode `20.290 s` против `3692.409 s` discovery/validation.
- **Repeated read of the same immutable payload:** rejected; `1254` reads,
  `1254` unique, `0` duplicate.
- **Full manifest traversal per package:** rejected; catalog traversal ровно
  два раза на весь run, не `837` раз.
- **Duplicate package construction:** rejected; duplicate package ids `0`.
- **Simple document/package fan-out is superlinear:** rejected; fixed-size
  document и simple-PDF scaling приблизительно линейны.
- **Hidden retry/compatibility provider loop:** rejected. Compatibility input
  paths действительно валидируются eagerly, но provider calls отсутствуют.
- **SQLite lock contention:** unsupported; все `1256` statements — SELECT,
  cumulative execute time negligible.
- **Arbitrary timeout as optimization:** rejected; он только обрежет полный
  scope и создаст false completeness.

## 12. Correctness finding outside performance-only scope

Gate 1 document-memory validation считает `ready_with_restrictions` допустимым
готовым состоянием (`document_memory.py:909`), а Gate 2 input readiness при
required enforcement принимает только точное `ready`
(`gate2_input_readiness.py:266-270`).

Наблюдаемые последствия:

- representative XML: `1` candidate, `0` packages,
  `gate2_source_ready_document_memory_blocked`;
- ZIP with promoted XML: `3` candidates, `2` packages, XML member blocked;
- mixed subsets наследуют тот же fail-closed outcome;
- actual corpus: `52` source-ready documents blocked и один aggregate
  `gate2_source_ready_documents_not_packageable` error.

Это не silent loss: кандидаты и remaining scope имеют явные ошибки, run не
объявляется successful/complete. Но это контрактное решение, а не performance
оптимизация. В текущем аудите семантика не менялась; finding должен быть
рассмотрен отдельно до provider expansion.

## 13. Ranked optimization opportunities

| Rank | Recommendation | Expected impact | Implementation / contract risk | Classification / confidence |
|---:|---|---|---|---|
| 1 | Validate each immutable PDF parent once per `audit_and_build`; cache validation by `(parent ref, payload checksum)` only inside run; keep per-unit ref/checksum/membership checks | Removes at least `660/822` full parent validations; targets ≈`96%` measured delay | Medium implementation, low/medium contract risk if full parent validation remains mandatory | **Required before expanding Gate 2; very high confidence** |
| 2 | Apply input strategy and source-ready scope before resolving/validating unselected table projections and legacy compatibility artifacts; emit explicit unselected accounting | Saves measured `95.885 s`, payload materialization and memory in actual default route | Medium; must preserve zero-loss inventory, access checks and explicit remaining/unselected scope | **Required; high confidence** |
| 3 | Replace per-ref scans with pre-indexed/batch resolver for table and PDF source values; reuse existing `resolve_source_values` semantics where applicable | Removes measured superlinear growth; benefit increases with rows/cells/words | Medium; preserve duplicate/missing-ref and checksum failure semantics | **Required for large inputs; high confidence** |
| 4 | Separate one-time unit validation from parent-specific linkage; avoid validating the same PDF unit contract twice | Smaller than rank 1, but removes 822 duplicate unit passes and repeated lookups | Medium; regression tests must prove identical errors | Useful, non-blocking after rank 1; high confidence |
| 5 | Reuse catalog records or add bulk resolver/store read to remove per-artifact SQLite connection/query | Removes `1254` point gets / `1256` SELECT N+1 | Low/medium; resolver access/lifecycle checks must remain centralized | Useful but non-blocking; high confidence, low measured impact |
| 6 | Select before package materialization and expose lazy package iterator/consumer backpressure | Reduces peak memory and deep copies; current time saving limited because build+validate ≈`14 s` | Medium/high contract risk around terminal coverage and iterator exhaustion | Useful after ranks 1-3; medium confidence |
| 7 | Add deterministic waves/checkpoints only if optimized full run remains operationally long | Operational recovery, not raw speed | High semantic work: cursor, completed/remaining scope, idempotence | Operational hardening; defer until remeasurement |
| 8 | Add concurrency only after duplicate work and memory amplification are removed | Unknown; current path is single-core CPU-bound | High resource/ordering risk; 4.28 GB per eager run can multiply | Deferred; insufficient benefit evidence |

### Cache safety

Безопасен узкий in-run cache результата deterministic validation только для
resolver-authorized immutable payload, keyed by identity and checksum. Cache
не должен переживать retention/lifecycle boundary и не должен заменять
per-unit linkage validation. Persistent/general cache пока не обоснован.

### Lazy execution and batching

Batch lookup внутри уже выбранного payload сохраняет контракты, если
uniqueness/checksum errors идентичны. Lazy package generation может сохранить
контракты только при явном terminal consumer protocol: exhausted iterator не
равен successful run без coverage accounting. Обычный silent generator stop
неприемлем.

### Is resumable execution required?

Пока нет. Измерения показывают доминирующую устранимую повторную работу, поэтому
resumable processing до ranks 1-3 маскировал бы defect. После оптимизации нужен
повторный full-corpus baseline. Если остаточное время останется неприемлемым,
resumable design обязан иметь:

- explicit completed scope;
- explicit remaining scope;
- deterministic cursor/checkpoint;
- non-terminal interrupted status;
- idempotent resume;
- no duplicate provider decisions;
- no false completeness;
- durable progress accounting.

### Timeouts and budgets

Конкретный production timeout или package-count limit не рекомендуется и не
вводился. После оптимизации и, при необходимости, resumable semantics допустим
только watchdog, который переводит run в явное non-terminal interrupted
состояние и сохраняет remaining scope. Его число должно исходить из новых
распределений времени, не из текущего неоптимизированного часа.

## 14. Recommended next engineering goal and deferred debt

### Next goal: Gate 2 deterministic package-preparation hot-path optimization

Предлагаемый узкий goal:

1. Зафиксировать characterization tests actual-shaped PDF parent/unit fan-out.
2. Ввести per-run parent validation memoization через существующий factory path.
3. Разделить parent validation и unit-parent linkage без изменения error set.
4. Выполнять default input selection до expensive table/legacy validation с
   явным accounting unselected artifacts.
5. Перевести table/PDF source-value checks на one-pass index/batch resolution.
6. Повторить тот же baseline и scaling suite.

Acceptance invariants следующего goal:

- те же candidate/package ids and counts;
- те же explicit deferred/blocked outcomes, пока correctness contract отдельно
  не изменён;
- ArtifactStore unchanged;
- provider calls `0` на preparation path;
- parent full-validation calls не больше числа уникальных parent payload refs;
- unused table-validation calls `0` при `prefer_table_projections=False`, но
  unselected scope явно учтён;
- никакого timeout, truncation или false terminal status.

### Debt that may remain deferred

- bulk SQLite/query consolidation после ranks 1-3;
- lazy package streaming после memory remeasurement;
- concurrency;
- persistent validation cache;
- resumable waves/checkpoints, если optimized baseline не требует их;
- latent double table-package validation, защищённая отдельным regression test.

## Plain answers

- **Did the observed delay involve the LLM?** Нет.
- **How many provider calls occurred?** `0`.
- **Which phase consumed the most time?** Private artifact discovery/validation,
  `99.600%` narrow run.
- **Is there duplicated work?** Да: PDF parent validation `822` раз при не более
  чем `162` parent payloads; минимум `660` повторов.
- **Is there an N+1 access pattern?** Да: `1256` SELECTs, но это вторичный долг.
- **Is package generation eager or lazy?** Eager.
- **How many packages?** `837` из `928` candidates; `1-65` на packageable
  document, mean `16.412`.
- **Linear or superlinear?** Documents/simple PDFs приблизительно linear;
  per-table row/value validation superlinear, с doubling ratios, приближающимися
  к quadratic.
- **Narrowest safe target?** One full PDF parent validation per immutable parent
  per run, затем отдельные unit linkage checks.
- **Would batching/caching/lazy preserve contracts?** In-run checksum-keyed
  validation cache и batch index — да при идентичных errors; lazy — только с
  explicit exhaustion/coverage protocol.
- **Is resumable required now?** Нет; сначала устранить measured duplication.
- **Which timeout should be considered?** Никакой конкретный до оптимизации и
  resumable terminal semantics.

## Final status

BROKER_REPORTS_GATE2_PACKAGE_PERFORMANCE_AUDIT:
COMPLETED

SLOW_PATH:
REPRODUCED_AND_ATTRIBUTED

PROVIDER_LLM_CONTRIBUTION:
MEASURED

DETERMINISTIC_CODE_CONTRIBUTION:
MEASURED

PRIMARY_BOTTLENECK:
IDENTIFIED

SCALING_BEHAVIOR:
CHARACTERIZED

OPTIMIZATION_CANDIDATES:
RANKED_BY_EVIDENCE

CORRECTNESS_AND_ZERO_LOSS:
PRESERVED

PRODUCTION_TIMEOUT_OR_TRUNCATION:
NOT_INTRODUCED

NEXT_ENGINEERING_GOAL:
READY
