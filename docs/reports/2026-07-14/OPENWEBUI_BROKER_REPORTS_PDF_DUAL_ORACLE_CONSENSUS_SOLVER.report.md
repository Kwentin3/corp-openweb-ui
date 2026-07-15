> Этот исследовательский снимок сохранён как история. Текущий итог: [OPENWEBUI_BROKER_REPORTS_PDF_STRUCTURAL_AND_SEMANTIC_CLOSEOUT.report.md](../2026-07-15/OPENWEBUI_BROKER_REPORTS_PDF_STRUCTURAL_AND_SEMANTIC_CLOSEOUT.report.md).

# Broker Reports PDF Dual-Oracle Consensus Solver

> Historical v1 replay report. `accepted_unique_consensus`,
> `solver_search_complete` and `uniqueness_proven` below are deprecated artifact
> names and must not be read as proof of global structural uniqueness. Use the
> v2 structural-repair contract and the 2026-07-15 closeout for current status.

Дата: 2026-07-14

Режим: research, contract design, bounded prototype

Исходная ревизия: `6ed92eeb3674fcb5cf877568e78723a2f2833d07`

## Вердикт

Старый parser-seeded путь для нового прототипа убран. Модель больше не получает готовую сетку строк и колонок и не переставляет значения из legacy-таблицы.

Новый путь работает так:

1. parser отдаёт неизменяемые слова, значения, координаты и provenance;
2. отдельный geometry observer отдаёт только сырые линии PDF;
3. VLM видит crop и анонимные атомы `id + bbox + order`, без значений и parser grid;
4. детерминированный assembler совмещает visual topology с линиями и координатами;
5. строгий solver либо принимает единственную сетку, либо возвращает typed block.

На трёх development-таблицах финальный replay дал:

```text
accepted_unique_consensus: 3/3
diagnostic exact cells:    147/147
all atoms exactly once:    178/178
invented values:           0
omitted candidates:        0
new provider calls:        0
```

Это полезный результат: механизм уже сам исправляет структурные расхождения, включая сложный grouped-header case. Но это post-hoc replay шести ранее запечатанных VLM-ответов после разработки assembly v4.

После заморозки кода проведён отдельный fresh holdout на шести ранее не использованных Broker Reports PDF. Он честно остановился до модели: во второй из трёх заранее выбранных таблиц оказалось 330 parser atoms при заводском лимите 192. Подмены на удобную таблицу не было, reference не открывался, provider generate calls — 0.

После этого результата лимит осознанно изменён отдельной политикой `pdf_visual_topology_policy_v4`: `maximum_atoms` поднят с 192 до 1000. Остальные предохранители не ослаблены: 48 KiB model JSON, 18,000 static input tokens, 20,000 counted input tokens, 8 MiB image и 8,192 output tokens. Исторический fresh holdout остаётся доказательством старой политики v3; открытый `holdout_002` теперь является development regression case.

Локальная регрессия на тех же трёх заранее выбранных таблицах после изменения прошла request construction без provider calls:

| Target | Atoms | Новый cap | Model JSON | Static input estimate | Результат |
|---|---:|---:|---:|---:|---|
| `holdout_001` | 157 | 1000 | 16,327 bytes | 4,735 tokens | package-eligible |
| `holdout_002` | 330 | 1000 | 31,633 bytes | 8,561 tokens | package-eligible |
| `holdout_003` | 72 | 1000 | 8,826 bytes | 2,859 tokens | package-eligible |

Следовательно, production Gate 2 и Gate 2 shadow E2E не включались и пока не готовы. Development replay доказал качество assembly/consensus на допустимых входах, а свежий holdout показал, что автоматический intake пока не покрывает крупные таблицы.

Финальный общий статус:

```text
BROKER_REPORTS_PDF_DUAL_ORACLE_PARTIAL
independent_visual_path_proven_on_three_of_six_required_table_classes
fresh_predeclared_holdout_executed
fresh_holdout_preflight_blocked_by_atom_budget
fresh_holdout_provider_consensus_not_exercised
cross_page_continuation_not_proven
durable_repeat_history_authority_missing
empty_merged_span_binding_representation_partial
```

## Fresh holdout без подбора удобных таблиц

До запуска были зафиксированы:

- шесть уникальных PDF, не встречавшихся в предыдущих `broker_reports_pdf*` и `broker_reports_direct_pdf*` экспериментах;
- порядок документов по полному SHA-256;
- правило: первый документ с минимум тремя parser table candidates;
- внутри него — первые три candidates по `(page_number, parser_ordinal)`;
- два visual attempts на каждую таблицу;
- один model/provider profile и общие budgets;
- отсутствие reference до terminal;
- запрет замены failed/oversized target на следующий удобный candidate.

Первый PDF в SHA-порядке имел 0 table candidates. Следующий имел 12 страниц и 13 table candidates, поэтому был выбран автоматически.

| Target | Page / parser ordinal | Parser atoms | Лимит | Preflight |
|---|---:|---:|---:|---|
| `holdout_001` | `1 / 1` | 157 | 192 | допустим |
| `holdout_002` | `2 / 1` | 330 | 192 | `pdf_visual_topology_atom_budget_exceeded` |
| `holdout_003` | `2 / 2` | 72 | 192 | допустим |

Поскольку `holdout_002` был заранее выбран, система не имела права заменить его четвёртой таблицей. Fresh run завершён typed terminal:

```text
terminal_status:             fresh_holdout_preflight_blocked
automatic request built:     no
provider qualification:      not started
provider generate calls:     0
reference process started:   false
manual target substitution:  false
```

Это не ошибка арбитража двух ответов: ответы оракулов вообще не были получены. Узкое место находилось раньше — политика v3 не разрешала представить таблицу с 330 анонимными атомами в одном bounded package. Политика v4 снимает именно этот локальный блокер, но не является provider-consensus proof.

## Что изменено

| Компонент | Новая ответственность | Что запрещено |
|---|---|---|
| Raw parser observation | точные word atoms, values, refs, checksums, bboxes, source order | готовая таблица, headers, предпочтительная сетка |
| Parser geometry observation | нормализованные vector lines; rect edges только как диагностика | values, candidate groups, row/column count, reference |
| Visual topology | crop, анонимные атомы, rows/columns, headers, spans, alternatives | source values, refs, parser grid, authority |
| Deterministic assembly | калибровка boundaries, проверка spans, exactly-once binding | value repair, nearest-cell fallback, provider call |
| Consensus | constraints, uniqueness, explanation, terminal | score, voting, oracle preference, reference |
| Replay/scoring | sealed input → solver terminal → отдельный reference score process | reference до завершения solver process |
| Fresh holdout | SHA-ordered corpus → predeclared scopes → frozen source → run/typed preflight terminal | reference input, per-target prompt/model override, удобная замена target |

Factory entrypoints обязательны. Прямое создание runtime блокируется. Production Pipe, Gate 2 handoff и OpenWebUI bundle этот код не импортируют.

Технический контракт: `docs/stage2/contracts/BROKER_REPORTS_PDF_STRUCTURAL_REPAIR_CONSENSUS.v2.md`.

## Как теперь собирается таблица

### 1. Независимый visual input

VLM получает один bounded crop и массив:

```text
a0001 + normalized bbox + order
a0002 + normalized bbox + order
...
```

В model-facing package нет raw values, source refs, parser cells, row/column count или header depth. Приватная карта `atom id → candidate id` применяется только после ответа модели и проверяется на exactly-once ownership.

### 2. Геометрия parser без семантики таблицы

`PdfParserGeometryFactory` читает сырые vector lines и rectangle bounds. Для решения используются только vector lines:

- ожидается ровно `N + 1` сильных boundary clusters;
- минимальное покрытие линии — `0.35` ширины или высоты таблицы;
- rectangle edges не могут подтвердить или опровергнуть span;
- bbox на границе или пересечение сертифицированного separator блокирует hypothesis.

Сохранённые geometry v1 наблюдения канонизированы в v2 с проверкой исходного checksum. Семантические поля не изменились; нового parser run не было.

### 3. Детерминированная проверка spans

Внутри каждого model span assembler измеряет покрытие separator:

- `>= 0.80` — реальный separator;
- `<= 0.10` — подтверждённый gap;
- между ними — `regional_retry_required`, без догадки.

Span, который залез за сильную линию, обрезается до ближайшего подтверждённого gap. Если после этого остаётся одна ячейка, span удаляется как no-op. Каждая операция записывается в adjustment journal с `source_value_change_allowed=false`.

Именно этот общий геометрический закон исправил `4:2`: ложные вертикальные spans были отброшены, а переextended horizontal spans обрезаны до parser separator. Ни значения, ни reference для этого не использовались.

### 4. Строгий terminal

Assembler создаёт binding hypotheses, а существующий bounded solver проверяет accounting, rectangularity, order, empties, headers, spans, provenance и uniqueness.

Возможны только terminals:

- `accepted_unique_consensus`;
- `ambiguous_multiple_consensus`;
- `parser_vlm_conflict`;
- `no_valid_consensus`;
- `human_review_required`;
- `unsupported`.

Numeric score, majority vote, “best-looking response”, parser preference и VLM preference отсутствуют.

## Результаты по таблицам

Для каждой таблицы использованы два ранее запечатанных visual attempts.

| Table | Класс | Расхождение oracle | Альтернативы после assembly | Terminal | Reference cells |
|---|---|---|---:|---|---:|
| `1:2` | deterministic-simple control | visual boundaries немного расходились с vector lines | 2 hypotheses → 1 canonical grid `10 x 3` | `accepted_unique_consensus` | `30/30` |
| `4:2` | grouped/merged header | первый старый assembly падал на overlapping spans; второй имел переextended spans | 2 hypotheses → 1 canonical grid `7 x 11` | `accepted_unique_consensus` | `77/77` |
| `5:3` | tax/summary | visual boundaries калиброваны parser geometry | 2 hypotheses → 1 canonical grid `5 x 8` | `accepted_unique_consensus` | `40/40` |

Для `4:2` в исходном live5 journal сохранены старые статусы `failed, assembled`. Финальный assembler v4 воспроизводимо даёт `assembled, assembled`; история не переписана и видна в safe evidence.

`valid_distinct_grid_count=1`, `solver_search_complete=true` и `uniqueness_proven=true` для всех трёх таблиц. Ambiguous и blocked terminals в этом трёхтабличном replay отсутствуют.

## До и после

Сравнение ниже ограничено тремя таблицами нового independent-visual slice. Parser-only и legacy VLM candidate-bound — диагностические baselines, не authority.

| Reconstruction | Exact shape | Exact cells | Numeric-like exact | Empty positions exact | Header-row count |
|---|---:|---:|---:|---:|---:|
| Current parser-only | `3/3` | `137/147` (93.20%) | `39/43` (90.70%) | `53/58` (91.38%) | `3/3` |
| Legacy VLM candidate-bound | `3/3` | `145/147` (98.64%) | `43/43` (100%) | `57/58` (98.28%) | `3/3` |
| New structural consensus | `3/3` | `147/147` (100%) | `43/43` (100%) | `58/58` (100%) | `3/3` |

Поскольку все 147 cells совпали, numeric-like и empty subsets также совпали полностью. При этом provisional reference отдельно не кодирует весь merged/header relation graph. Поэтому отчёт доказывает точную форму, cells и header-row count, а физическую допустимость spans — через vector-separator constraints; отдельную метрику «100% merged semantics» не заявляет.

Continuation correctness для этого slice — `not_evaluated`: пары `3:2 + 4:1` здесь нет.

## Исследованные solver-подходы

| Подход | Вывод |
|---|---|
| Exact cover / Algorithm X | хорошо выражает exactly-once, но неудобен для ordered geometry, empties, hierarchy и continuation |
| CP-SAT | подходит для finite-domain constraints, но добавляет optimizer/dependency без пользы при шести явных hypotheses |
| SMT / Z3 | выразителен и может давать unsat cores, но усложняет runtime и evidence boundary |
| Bounded deterministic enumeration | выбран: каждый явный hypothesis проходит одинаковые constraints, valid grids дедуплицируются по canonical checksum |

Выбранный solver не делает LLM call. Для текущего опыта он проверил 6 hypotheses, 178 atoms и 147 grid positions. Сложность ограничена числом явных hypotheses и размером их grid; скрытого поиска по свободным значениям нет.

## Context budget

Каждый исторический visual call имел pre-call `countTokens`, один crop, узкую JSON schema и caps: 20,000 input tokens, 8 MiB image, 8,192 output tokens. Counted и actual input совпали.

| Table | Atoms | Image bytes/call | Два calls: input counted=actual | Output tokens total | Max output/call | Input tokens / atom за два attempts |
|---|---:|---:|---:|---:|---:|---:|
| `1:2` | 49 | 16,662 | 9,878 | 714 | 361 | 201.59 |
| `4:2` | 60 | 28,655 | 11,326 | 1,779 | 1,024 | 188.77 |
| `5:3` | 69 | 27,225 | 12,516 | 772 | 386 | 181.39 |
| **Всего** | **178** | — | **33,720** | **3,265** | **1,024** | **189.44** |

Все limits соблюдены. Silent truncation, column splitting, hidden retry и provider failover: 0. Whole PDF, forensic payload, business prompts, OCR и Knowledge/RAG/vector модели не передавались.

Исторических provider generate calls — 6. Во время финального replay — 0. Provider qualification в evidence историческая и после рефакторинга не обновлялась.

В историческом fresh holdout сетевые budgets не проверялись: request construction остановился локально на `330 > 192` atoms. После перехода на policy v4 локальная сборка показала для открытой таблицы 31,633 bytes model JSON и 8,561 static input tokens, то есть текущие локальные caps соблюдены. Перед provider generate всё равно обязателен реальный `countTokens`; если он превысит 20,000, выполнение должно завершиться typed terminal без сетевой генерации. Повышение cap до 1000 не означает, что пакет любого размера до 1000 будет отправлен: независимые byte/token guards остаются fail-closed.

## Reference isolation и repeatability

Replay разделён на три процесса:

1. `prepare` строго проверил live5 private/safe evidence и создал whitelist-only input без reference, старых terminal results и private paths;
2. `solve` не имел аргумента reference, не импортировал provider transport и записал terminal artifact;
3. после выхода solver отдельный `score` process проверил terminal seal и только затем прочитал provisional reference.

Seal включает replay-input SHA, accepted-binding SHA, hypothesis-set SHA, repeatability SHA, обе assembly SHAs, parser/geometry SHAs, materialization SHA и consensus result checksum для каждой таблицы. После scoring terminal file перечитан; его SHA и содержимое не изменились.

Repeatability `3/3` означает одинаковый canonical grid после deterministic assembly для двух attempts каждой таблицы. Это не означает, что сырые VLM JSON были побайтно одинаковы. Durable append-only history authority пока нет, поэтому формальный общий статус `BROKER_REPORTS_PDF_CONSENSUS_REPEATABILITY_READY` не заявляется.

## Provenance и explainability

Для принятых таблиц:

- каждый из 178 atoms использован ровно один раз;
- каждый non-empty cell разрешается только в exact parser values;
- invented values: 0;
- omitted candidates: 0;
- nearest-cell fallback: false;
- value mutation: false;
- raw response, package, dictionary и terminal checksums проверены;
- reference answer used by solver: false.

Результат объясняет не только terminal, но и structural adjustments. Для `4:2` сохранены операции:

- `drop_span_reduced_to_single_cell_by_parser_separator`;
- `trim_span_to_parser_separator`;
- `project_geometry_certified_empty_span_to_explicit_empty_cells`;
- `replace_visual_boundary_with_parser_geometry`.

Последняя из специальных операций указывает на ограничение: существующий binding schema не умеет представить пустой merged span без non-empty anchor. Сейчас такой region детерминированно проецируется в explicit empty cells и журналируется.

## Evidence и проверки

Controlled PDF SHA-256:

`79af73d5be78df446f768f516ed6eaebd5a9d4bfc6f98c98a4a53a5b5131f37d`

Финальный safe evidence:

`local/stage2/broker_reports_pdf_structural_repair_2026-07-14-replay2/evidence.safe.json`

Safe evidence SHA-256:

`2dc162e6e1d1aa7f71e821faa6f7112a05adca531d615b8714d1bd1a3bfbd618`

Sanitized replay input SHA-256:

`28ec52c3e9ec0030c0e7cef123c88dcd1cd6978f2e4e0d64968a16c5a53ab938`

Source live5 private evidence SHA-256:

`12612a444d7c96e31794103125dc59c33606658ae67b84e581a13678e3df6a0a`

Terminal private file SHA-256:

`a21632f1bf3c0a111c15b199afb0928842763dd8d48a5e76ce8a3902a0fe7419`

Terminal seal:

`e529cff3235eff675e55d7be8e1ca5ce52bf0bf6a7d01b4ad87a3f7ff2715934`

Fresh holdout safe preflight terminal:

`local/stage2/broker_reports_pdf_structural_holdout_2026-07-14-preflight1/holdout.preflight.safe.json`

Fresh holdout safe SHA-256:

`38bd9b78dc76a67cabf5deeada6c57cdb034ec7a6db076bed64d25b7371c6318`

Fresh holdout private preflight SHA-256:

`899239998185b731608a4d00d158ffb8213be1a661591e8117cb9e99bd534b0d`

Fresh holdout safe atom-count diagnostic:

`local/stage2/broker_reports_pdf_structural_holdout_2026-07-14-preflight1/holdout.preflight.diagnostic.safe.json`

Diagnostic file SHA-256:

`3cb536a7882b21b0daffa499d47761bfebba04dacbb734ef3248d5f6977d8ef7`

Fresh holdout source inventory checksum:

`c035d8c19d4634a0d1248a4716649b026e3fd72363e26c1ddda45d1b4df876d2`

Проверка fresh artifact: contract errors `[]`; frozen source совпадает с текущими runtime/runner/scorer bytes; provider calls `0`; reference process `false`.

Проверки:

- focused holdout contract/routing tests: `14 passed`;
- полный service suite: `418 passed, 5 warnings`;
- `py_compile` новых runtime и runner modules: успешно;
- warnings — существующие SWIG `DeprecationWarning`, test failures отсутствуют.

Safe evidence не содержит raw values, crops, provider responses, candidate/source identifiers или private paths.

## Readiness

Доказаны:

```text
BROKER_REPORTS_PDF_PARSER_OBSERVATION_CONTRACT_READY
BROKER_REPORTS_PDF_VLM_TOPOLOGY_HYPOTHESIS_CONTRACT_READY
BROKER_REPORTS_PDF_DUAL_ORACLE_CONSENSUS_CONTRACT_READY
BROKER_REPORTS_PDF_CONSENSUS_SOLVER_PROTOTYPE_READY
BROKER_REPORTS_PDF_CONSENSUS_EXPLAINABILITY_READY
```

Context guards прошли в development replay. Глобальный status не повышен: fresh holdout был запущен, но остановился до модели на atom budget.

Не доказаны:

```text
BROKER_REPORTS_PDF_CONSENSUS_CONTINUATION_READY
BROKER_REPORTS_PDF_CONSENSUS_REPEATABILITY_READY
BROKER_REPORTS_PDF_DUAL_ORACLE_REAL_TABLE_PROOF_COMPLETED
BROKER_REPORTS_PDF_DUAL_ORACLE_READY_FOR_GATE2_SHADOW_E2E
```

Причины: независимый visual path пока проверен только на трёх development-таблицах; fresh predeclared holdout не прошёл request construction; нет cross-page continuation proof и durable history authority.

Следующий минимальный slice — выполнить реальный `countTokens` и два factory-routed oracle attempts на открытом development regression case, не называя его новым fresh holdout. Если модель не вернёт корректную структуру либо counted input превысит лимит, следующим решением станет bounded segmentation: детерминированные visual regions, полное ownership всех atoms, global row/column/span stitching и тот же fail-closed consensus.

После реализации и локального доказательства на этом regression case алгоритм надо снова заморозить и проверить на другом, ранее не открывавшемся holdout corpus по тому же SHA-порядку и без ручной замены targets. До этих доказательств production Gate 2 selection менять не следует.
