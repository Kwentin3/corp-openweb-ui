# OpenWebUI Broker Reports: архитектура структурного консенсуса

Дата: 2026-07-14
Режим: research and architecture only
Production runtime: не изменялся в рамках этого исследования
Итоговый статус: архитектурное направление готово; production accuracy и Gate 2 authority не заявлены

Поддержанные исследовательские статусы:

- `BROKER_REPORTS_MULTI_ORACLE_OBSERVATION_MODEL_READY`
- `BROKER_REPORTS_STRUCTURAL_CONSENSUS_ARCHITECTURE_READY`
- `BROKER_REPORTS_OBSERVATION_CONTRACTS_REFINED`
- `BROKER_REPORTS_CONSENSUS_SOLVER_DIRECTION_READY`
- `BROKER_REPORTS_CONTEXT_SAFE_CONSENSUS_MODEL_READY`
- `BROKER_REPORTS_NEXT_IMPLEMENTATION_DIRECTION_READY`

Эти статусы означают готовность архитектуры и следующего исследовательского шага. Они не означают, что автоматическое восстановление таблиц уже прошло независимый accuracy gate.

## Короткий вывод

Проекту не нужно добавлять «третий оракул» к parser и VLM. Само понятие оракула здесь слишком крупное: один инструмент одновременно сообщает текст, координаты, линии и предполагаемую структуру, а затем неясно, какие из этих сведений действительно независимы.

Целевая модель должна состоять из небольших наблюдений, каждое из которых отвечает ровно на один вопрос. Наблюдения не голосуют и не получают общий confidence score. Они образуют конечную систему фактов, альтернатив и ограничений.

Рекомендуемый consensus core — bounded finite-domain satisfiability solver:

1. построить полный конечный домен допустимых границ, ячеек, spans, headers и placements;
2. найти первое допустимое каноническое решение;
3. запретить именно это решение и выполнить второй полный поиск;
4. если второй поиск `UNSAT`, структура уникальна;
5. если найдено второе решение, структура неоднозначна;
6. если первый поиск `UNSAT`, допустимой структуры нет;
7. если домен неполон или бюджет поиска исчерпан, доказательства нет и результат блокируется типизированно.

Никакой optimizer, majority vote, average confidence или «лучший визуальный ответ» для принятия таблицы не нужен.

## Границы исследования

В scope входят только:

- наблюдения одной PDF-таблицы и её page fragments;
- построение конечного структурного домена;
- deterministic consensus;
- proof/explanation artifacts;
- bounded context;
- рекомендации для следующего prototype slice.

Вне scope остаются:

- Gate 2 и business extraction;
- candidate binding бизнес-фактов;
- ArtifactStore redesign;
- новый OCR;
- новый PDF parser;
- новый provider selection;
- новый prompt-engineering цикл;
- новый serialization format;
- изменение production authority или OpenWebUI core.

Текущие checksummed JSON contracts и artifact refs достаточны. Требуется уточнить смысл контрактов, а не вводить другой формат данных.

## Что уже есть в репозитории

Текущий prototype уже содержит большую часть правильных строительных блоков:

- topology-neutral raw-word ledger и exact candidate ownership;
- отдельное наблюдение PDF vector geometry;
- anonymous visual-topology package без видимых значений;
- deterministic topology assembly;
- finite alternative evaluation;
- typed outcomes: unique, multiple, conflict, no valid solution;
- exact materialization из source refs;
- repeatability ledger;
- bounded row windows и atom cap;
- parser/geometry-only continuation discovery;
- fail-closed validators.

Основные локальные опорные файлы:

- `docs/stage2/contracts/BROKER_REPORTS_PDF_DUAL_ORACLE_CONSENSUS.v1.md`;
- `docs/stage2/contracts/BROKER_REPORTS_PDF_STRUCTURAL_REPAIR_CONSENSUS.v2.md`;
- `broker_reports_gate1/pdf_dual_oracle_contracts.py`;
- `broker_reports_gate1/pdf_parser_geometry.py`;
- `broker_reports_gate1/pdf_visual_topology.py`;
- `broker_reports_gate1/pdf_topology_assembly.py`;
- `broker_reports_gate1/pdf_dual_oracle_consensus.py`;
- `broker_reports_gate1/pdf_continuation_discovery.py`.

Главный оставшийся архитектурный недостаток: solver пока в значительной мере проверяет набор альтернатив, который предложил VLM. Уникальность внутри неполного набора VLM-ответов ещё не равна уникальности структуры в полном конечном домене.

## Наблюдение, гипотеза и инвариант — разные вещи

Это разделение принципиально.

Наблюдение — неизменяемое описание того, что конкретный измерительный канал действительно увидел.

Гипотеза — одна допустимая структурная интерпретация наблюдений.

Инвариант — правило, которое обязано выполняться для любой принятой структуры.

Примеры:

| Сущность | Тип | Почему |
|---|---|---|
| token `a17` существует в source bytes | observation | это факт извлечения |
| bbox token `a17` равен `[x1,y1,x2,y2]` | observation | это факт координатного канала |
| между `x=0.41` и `x=0.42` виден vertical separator | observation | это измерение линии |
| token `a17` находится в row 3, column 2 | hypothesis | row/column ещё надо доказать |
| каждая candidate identity используется ровно один раз | invariant | это обязательное правило |
| cell `(3,2)` пустая | derived solution relation | пустота следует из grid и ownership, а не наблюдается напрямую |
| две страницы продолжают одну таблицу | relational hypothesis | это связь между fragment observations |

Ownership, completeness, rectangularity и empty-cell placement не должны называться новыми оракулами. Это solver invariants или свойства решения.

## Независимость: не число оракулов, а граф происхождения

Два сообщения независимы не потому, что пришли из двух функций. Для каждого наблюдения нужен lineage:

- document SHA и page/crop scope;
- producer identity, version и configuration hash;
- input artifact refs и checksums;
- `derivation_kind`: `direct_measurement`, `deterministic_projection`, `model_proposal`, `derived_relation`;
- `depends_on_observation_refs`;
- completeness state;
- canonical checksum.

Тогда зависимости становятся явными:

| Пара наблюдений | Реальная связь |
|---|---|
| extracted text и bbox того же word parser | общий producer; не независимы статистически |
| word geometry и raw PDF vector lines | разные measurement channels; частично независимы |
| VLM topology и atom bbox | VLM получает bbox; по placement они зависимы |
| VLM topology и raster separators | один raster input; коррелированы |
| две попытки одной модели на одном crop | не два oracle domains; только repeatability samples |
| continuation relation и fragment geometry | relation детерминированно производна от geometry |
| repeated-header decision и fragment rows | производная cross-fragment проверка |
| legacy parser cells и parser row/column grid | одно является производным от другого; нельзя считать двумя голосами |

Solver не должен считать количество «подтверждений». Он должен проверять совместимость именованных claims и не удваивать один факт через производные представления.

## Минимальная полная observation architecture

### 1. Table scope envelope

Вопрос: «Какой точный фрагмент документа сейчас рассматривается?»

Содержит:

- document/page/crop identity;
- coordinate spaces и точные transforms;
- table bbox;
- source and crop checksums;
- scope limits.

Не содержит rows, columns, headers, cells или preferred grid.

Это не oracle. Это общий sealed scope для всех наблюдений.

### 2. Text identity observation

Вопрос: «Что именно существует в source?»

Содержит:

- opaque atom/candidate ids;
- exact source refs и text checksums;
- exact visible values в private projection;
- source order;
- duplicate-value groups.

Не содержит:

- row/column placement;
- cell grouping;
- header role;
- spans;
- готовую grid.

Структурному model context нужны ids, но не значения. Exact text требуется materializer и repeated-header checker, а не visual topology model.

### 3. Atom geometry observation

Вопрос: «Где точно находится каждый atom?»

Содержит:

- atom id;
- bbox в table-normalized coordinates;
- baseline/center intervals, если они непосредственно измерены;
- coordinate transform refs;
- geometry completeness.

Не содержит text, rows, columns или cell assignment.

Практически это может быть validated projection существующего parser observation. Новый parser для этого не нужен. Lineage обязан показывать общую зависимость с text extraction.

### 4. Separator field observation

Вопрос: «Где физически есть separator или подтверждённый gap?»

Содержит:

- horizontal/vertical segments;
- origin: PDF vector line, rectangle edge, raster line;
- normalized position and coverage interval;
- measured coverage;
- evidence quality and exclusion reason.

Не содержит values, header meaning или cell assignment.

Vector segments и raster segments должны оставаться разными origins. Их нельзя заранее усреднять в одну confidence number. Rectangle edges могут оставаться diagnostic-only, как сейчас.

### 5. Visual relation observation

Вопрос: «Какие структурные отношения визуально предложены?»

Содержит ограниченный набор альтернатив:

- row/column boundary proposals;
- header depth;
- span relations;
- header hierarchy relations;
- explicit `unsupported` и uncertainty codes;
- package and attempt identity.

В model input остаются только crop, anonymous atom ids, normalized bboxes и source order. Видимые values, parser grid и reference запрещены.

Это model proposal, не authority. Две одинаковые попытки доказывают repeatability ответа, но не независимость наблюдения.

### 6. Fragment relation observation

Вопрос: «Как связаны два table fragments?»

Содержит:

- ordered fragment refs;
- page adjacency;
- edge proximity;
- horizontal overlap;
- column-signature compatibility;
- repeated-header relation refs;
- subtotal/duplicate policy refs;
- complete fragment-set accounting.

Не содержит новую grid и не скрывает локальный failure. Это first-class relational contract, но он детерминированно зависит от fragment observations.

Для single-page table этот контракт не нужен. Поэтому минимальная single-table модель состоит из scope, text identity, atom geometry, separator field и visual relations; fragment relation добавляется только для continuation.

## Что не должно становиться отдельным observation contract

| Кандидат | Решение |
|---|---|
| ownership observation | Нет. Exact-once ownership — solver invariant |
| empty-cell observation | Нет. Empty cell — следствие grid, spans и отсутствия допустимого atom placement |
| confidence observation | Нет. Confidence допустим для routing, но не для consensus |
| repeated model attempt | Нет. Это repeatability event в том же observation domain |
| parser-ready grid | Нет. Это преждевременная hypothesis, которая снова делает parser авторитетом |
| combined parser/VLM score | Нет. Он скрывает конфликт и зависимость источников |
| repeated header | Не raw observation. Это derived relation с собственным проверяемым contract |

## Нейтральное представление структуры

Graph model полезен как промежуточное представление и explanation surface:

- atom nodes;
- boundary nodes;
- row-band and column-band nodes;
- cell nodes;
- span nodes;
- fragment nodes;
- `contains`, `precedes`, `separated_by`, `aligned_with`, `covers`, `continues` edges.

Но graph сам не принимает решение. Он компилируется в конечные variables и constraints. Это важно: современные TSR-системы успешно представляют таблицу через cell graph или через separator prediction и merge, но обычно возвращают наиболее вероятное предсказание. TGRNet моделирует spatial и logical cell location как graph reconstruction; TSRFormer и RobusTabNet разделяют separator prediction и cell merging. Для нашего проекта это хорошие observation generators, но не production consensus authority. См. [TGRNet](https://arxiv.org/abs/2106.10598), [TSRFormer](https://arxiv.org/abs/2208.04921), [RobusTabNet](https://arxiv.org/abs/2203.09056).

PubTables-1M отдельно показывает важность canonicalization и непротиворечивой ground truth для merged/oversegmented tables. Это поддерживает решение дедуплицировать solver witnesses по одной canonical grid, а не сравнивать provider JSON буквально. См. [PubTables-1M](https://www.microsoft.com/en-us/research/publication/pubtables-1m/).

## Finite-domain consensus model

### Variables

Для одной bounded table scope достаточно следующих семейств variables:

- `row_boundary[i]`: выбрана ли candidate horizontal boundary;
- `column_boundary[j]`: выбрана ли candidate vertical boundary;
- `cell_of[atom_id]`: одна допустимая `(row, column)` position;
- `span[k]`: включён ли допустимый merged/spanning region;
- `header_depth`: `0..min(row_count, 8)`;
- `header_parent[child]`: допустимая hierarchy relation или `none`;
- `fragment_link[f1,f2]`: relation state для continuation;
- `repeat_header[row]`: derived removal state, только если relation contract это разрешает.

Domains должны строиться детерминированно из:

- table outer bounds;
- separator clusters;
- atom interval gaps and alignments;
- bounded visual proposals;
- explicit absence/unsupported alternatives.

Критически важно: visual response не может быть единственным источником domain completeness. Если VLM не предложил вторую возможную boundary, solver не имеет права считать её невозможной. Domain builder обязан либо добавить все допустимые candidates по фиксированным правилам, либо вернуть `domain_incomplete` и запретить unique acceptance.

### Hard constraints

Минимальный набор:

1. scope and checksum integrity;
2. finite ordered row/column boundaries with exact outer bounds;
3. rectangular grid;
4. every atom assigned exactly once;
5. no unknown, omitted or duplicated atom;
6. bbox belongs to its selected bands;
7. atom bbox cannot cross a certified separator;
8. span cannot cross a certified internal separator;
9. span requires a supported separator gap;
10. spans do not overlap illegally;
11. covered span positions are empty except the canonical anchor policy;
12. source order remains compatible with selected row/column order;
13. header hierarchy refers only to proved header spans;
14. fragment set is exact and ordered;
15. continuation cannot accept if any required fragment is not uniquely accepted;
16. repeated header removal requires its derived relation proof;
17. materialization may resolve ids to exact values but may not alter assignments.

Thresholds such as separator coverage remain versioned policy. Их вычисление детерминировано, но сам выбор threshold является heuristic policy и должен проверяться на holdout.

### Три доказуемых terminal outcomes

Пусть `C` — полный набор compiled constraints.

```text
validate observations and dependency DAG
build finite domain D
if D is not complete or exceeds hard limits:
    return SEARCH_NOT_CERTIFIABLE

r1 = solve(C, D)
if r1 == UNSAT:
    return NO_VALID_STRUCTURE + conflict certificate
if r1 == UNKNOWN:
    return SEARCH_NOT_CERTIFIABLE

w1 = canonicalize(r1.model)
r2 = solve(C AND canonical_structure != w1, D)
if r2 == UNSAT:
    return UNIQUE_STRUCTURE + w1 + uniqueness certificate
if r2 == UNKNOWN:
    return SEARCH_NOT_CERTIFIABLE

w2 = canonicalize(r2.model)
return MULTIPLE_VALID_STRUCTURES + w1 + w2 + structural diff
```

Для доказательства неоднозначности достаточно двух разных canonical witnesses. Для доказательства уникальности нужен `UNSAT` второго поиска. Для доказательства отсутствия решения нужен `UNSAT` первого поиска.

`timeout`, `budget exceeded`, неполный domain или solver `UNKNOWN` не являются ни «несколько решений», ни «нет решения». Это отдельный fail-closed non-consensus outcome.

Constraint programming естественно подходит для конечных feasibility problems и умеет перечислять решения без objective function; официальный CP-SAT guide прямо разделяет `FEASIBLE`, `INFEASIBLE`, `MODEL_INVALID` и `UNKNOWN` и поддерживает enumeration. См. [Google OR-Tools CP-SAT](https://developers.google.com/optimization/cp/cp_solver).

Z3 полезен как research backend для named constraints, models, proof generation и unsat cores. Официальный guide показывает `sat`/`unsat`/`unknown`, models и tracked unsatisfiable cores. См. [Z3 basic commands](https://microsoft.github.io/z3guide/docs/logic/basiccommands/) и [Z3 unsat cores](https://microsoft.github.io/z3guide/docs/logic/propositional-logic/).

## Оценка альтернативных consensus approaches

| Подход | Польза | Решение для проекта |
|---|---|---|
| deterministic finite-domain constraints | точные hard constraints, полная проверка, typed UNSAT | Основной подход |
| SAT/SMT | uniqueness blocking clause, named constraints, unsat cores | Лучший research direction для proof backend |
| CP-SAT без objective | удобные integer domains и enumeration | Допустимый scalability backend |
| graph reconstruction | естественная модель cells/relations и объяснений | Использовать как IR, не как authority |
| exact cover | хорошо решает exact-once ownership | Возможная внутренняя оптимизация, но недостаточна для spans/geometry сама по себе |
| optimization under constraints | быстро выбирает один best candidate | Запрещено для acceptance; objective скрывает допустимую неоднозначность |
| probabilistic/Bayesian fusion | полезно для offline calibration и routing | Не использовать для доказательства структуры |
| Dempster-Shafer/evidence mass | явно представляет conflict/unknown | Не решает проблему зависимых evidence и не даёт structural proof |
| majority voting | просто | Запрещено: два зависимых представления могут переголосовать один точный факт |
| highest confidence wins | удобно для UX | Запрещено для consensus; confidence не заменяет witness |

Search heuristics разрешены только для порядка перебора. Они не могут отбрасывать допустимые решения, менять canonical result или превращать incomplete search в unique result.

## Explanation model

Каждый compiled constraint получает стабильный id и evidence refs.

Минимальная запись объяснения:

```text
constraint_id
constraint_kind
scope_ref
observation_refs
subject_refs
result: satisfied | violated | unresolved
witness_ref | counterexample_ref
safe_reason_code
private_detail_ref
```

### Почему таблица принята

Safe explanation сообщает:

- первый canonical witness найден;
- exact ownership прошёл;
- separator/span/placement constraints прошли;
- fragment constraints прошли, если применимо;
- второй поиск с blocking clause доказал `UNSAT`;
- domain completeness и search completeness подтверждены.

### Почему таблица неоднозначна

Возвращаются два private canonical witnesses и safe structural diff, например:

- boundary присутствует только в witness A;
- atom `a17` занимает разные columns;
- span существует только в witness B;
- header depth различается.

### Почему допустимой структуры нет

Возвращается deterministic conflict certificate. При SMT backend это может быть unsat core из named constraints. Unsat core не следует автоматически называть минимальным: Z3 этого не гарантирует. Минимизация допустима отдельным bounded deterministic pass.

### Почему candidate размещён здесь

Нужна цепочка:

```text
atom geometry -> selected row/column bands
separator non-crossing -> legal placement
exact ownership -> only one placement retained
canonical witness -> final cell
```

### Почему empty cell действительно пустая

Не потому, что VLM вернул `[]`. Пустота доказана, если:

- row/column boundaries входят в unique witness;
- ни один atom не может законно занимать эту cell;
- cell не является covered non-anchor position другого незаконного span;
- альтернативная структура с другим placement не существует.

### Privacy boundary

Safe explanation содержит ids, counts и reason codes. Exact values, raw provider payloads, paths, crops и detailed counterexamples остаются private artifacts.

## Context-safe architecture

Добавление observation source не должно добавлять его raw payload в prompt.

Правила:

1. VLM получает только тот projection, который нужен для его единственного вопроса.
2. Text values, vector-line ledger, repeat history и solver constraints не дублируются в model context.
3. Новые deterministic observations поступают непосредственно в domain builder/solver.
4. Artifact payloads передаются по checksum refs, а не копируются в каждый package.
5. Full-table package остаётся assembly ledger, не provider input.
6. Wide tables используют full-width vertical atom windows с disjoint ownership.
7. Attempt-local windows не смешиваются между model attempts.
8. Context manifest считает bytes, atoms, static tokens, counted tokens и output budget до generate call.
9. Observation registry хранит dependency refs, поэтому derived claims не пересылают исходный payload.
10. Новый model call разрешён только для реально отсутствующего observation kind, а не для повторного общего «прочитай всю таблицу».

Таким образом, больше наблюдений увеличивает число deterministic constraints, но не линейно увеличивает LLM context.

Текущие hard bounds разумно сохранить как исходную policy boundary:

- `1..192` atoms — whole-table topology call;
- `193..1000` atoms — deterministic vertical windows;
- больше `1000` atoms или unsafe cut — typed block;
- fixed byte/token/output guards на каждое окно;
- ровно две model attempts на observation package;
- continuation join выполняет zero provider calls.

## Как закрываются текущие pain points

### Wide tables

Columns никогда не режутся. Full-width windows сохраняют общий column domain; ownership partitions только по vertical atom ranges. Column disagreement между windows создаёт multiple/no-valid outcome, а не stitch по score.

### Continuation

Fragment relation — отдельный cross-page contract. Каждый fragment сначала получает локальный unique proof. Join не вызывает provider, не меняет values и не скрывает failed sibling.

### Merged headers

Span — variable, а не готовый VLM fact. Он допустим только при совместимости visual relation, separator gaps, atom geometry, header hierarchy и exact ownership.

### Repeated identical values

Solver оперирует atom ids/source refs, а не строками. Две одинаковые строки остаются разными evidence objects и не могут схлопнуться по value.

### Wrong column placement

Placement ограничивается bbox bands, certified separators, source order и exact ownership. Nearest-cell fallback запрещён.

### Wrong empty-cell placement

Empty positions выводятся из unique grid и ownership. Они не принимаются как свободная model догадка.

### Parser/VLM disagreement

Никто не побеждает. Конфликт либо делает `C` unsatisfiable, либо оставляет несколько witnesses. Оба результата объяснимы.

### Repeatability

Повторные model attempts сравниваются как alternative sets в одном domain. Они не считаются независимыми оракулами. Исторический conflict остаётся monotonic blocker.

### Bounded context and deterministic behavior

Model packages остаются локальными и bounded; acceptance определяется canonical constraints и полным поиском, а не порядком JSON, provider wording или confidence.

## Что должно остаться детерминированным навсегда

- source/crop/package identity и checksums;
- coordinate transforms;
- observation lineage DAG;
- exact atom/source ownership;
- domain construction rules;
- hard budgets and limits;
- constraint compilation;
- canonical witness representation;
- structural witness deduplication;
- first/second solve terminal mapping;
- materialization from source refs;
- continuation fragment accounting;
- repeatability history;
- safe/private explanation projection;
- replay and holdout isolation;
- validators at every boundary.

## Что может оставаться heuristic

- initial table region proposal;
- visual topology proposals;
- raster separator proposal;
- separator coverage thresholds как versioned policy;
- header-role proposal;
- continuation candidate proposal;
- search variable ordering;
- решение, какой region отправить на bounded retry/manual review;
- confidence для routing и research diagnostics.

Heuristic может предложить domain member или порядок поиска. Она не может сама принять таблицу, удалить физически допустимую альтернативу без contract rule или изменить exact source value.

## Основные риски

### Ложная независимость

Один факт может прийти в нескольких derived forms. Без dependency DAG система снова начнёт считать дубликаты подтверждением.

### Неполный домен

Это главный риск. Solver может доказать unique только относительно переданного domain. Поэтому `domain_complete=true` должен вычисляться, а не приниматься от caller.

### Search explosion

Boundary presence, placements и spans дают комбинаторный рост. Нужны hard caps на variables, alternatives, spans, windows, solve steps, memory и wall time. Превышение означает `SEARCH_NOT_CERTIFIABLE`.

### Borderless tables

Separator evidence может быть слабым. Если atom alignments и visual relations не дают полного домена, система должна вернуть multiple/incomplete, а не усиливать confidence.

### Correlated VLM attempts

Две одинаковые попытки одной модели могут повторять одну ошибку. Repeatability — необходимая, но недостаточная проверка.

### Unsat core misuse

Core объясняет конфликт constraints, но не всегда минимален и не доказывает, что observation producer был прав. Safe wording должно говорить «эти утверждения несовместимы».

### Solver dependency and closed-world packaging

Добавление Z3/OR-Tools в production bundle создаст runtime/deployment risk. Сначала нужен offline parity prototype. Production dependency нельзя добавлять только ради красивой архитектуры.

### Empirical adequacy

Формальная уникальность не гарантирует правильность observation model. Нужен source-frozen unseen holdout с human reference только после terminal seal.

## Рекомендуемая реализация маленькими срезами

### Slice 1. Observation lineage refinement

Без нового parser и без изменения public output:

- формально определить common observation envelope;
- добавить dependency refs/completeness semantics в research contracts;
- классифицировать current fields как measurement, projection, proposal или derived relation;
- тест: derived observation не может заявить независимость от своего input.

### Slice 2. Topology-neutral projections

- получить text identity и atom geometry как validated projections текущего sealed parser observation;
- не создавать второй extraction path;
- не передавать visible text в VLM;
- тест: projections recombine to the same atom identity/checksum set.

### Slice 3. Finite domain builder

- строить bounded boundary candidates из outer bounds, separators, atom gaps и visual proposals;
- выдавать completeness certificate;
- тесты: wide table, missing separator, extra separator, repeated values, unsafe span, wrong empty-cell alternative.

### Slice 4. Proof-oriented solver prototype

- сохранить текущий factory boundary;
- реализовать reference bounded backtracking/SAT-style solver только в research path;
- first solve + blocking clause + second solve;
- objective function отсутствует;
- deterministic seed/search order;
- typed `UNIQUE`, `MULTIPLE`, `NONE`, `INCOMPLETE`.

Сначала разумно расширить текущий pure-Python enumerator: он уже закрыт в репозитории и прозрачен. Параллельный offline Z3 prototype допустим только для сравнения witness sets и unsat explanations. Production migration имеет смысл лишь при доказанной parity и closed-world packaging.

### Slice 5. Explanation certificates

- stable ids для constraints;
- unique blocking proof;
- two-witness diff;
- conflict certificate/unsat core;
- safe Russian renderer без private values.

### Slice 6. Continuation composition

- local unique proof для каждого fragment;
- first-class fragment relation;
- derived repeated-header proof;
- zero-call deterministic join;
- сначала exact two-page pair; three-page chains остаются deferred.

### Slice 7. Evaluation

1. sealed historical replay без provider calls;
2. synthetic adversarial matrices;
3. development regression;
4. новый source-frozen unseen holdout;
5. post-terminal human reference;
6. live default-disabled canary;
7. production authority остаётся неизменной до accuracy gate.

Каждый slice меняет одну границу и имеет самостоятельную acceptance surface. Gate 2 и ArtifactStore не требуют redesign.

## Acceptance criteria следующего prototype

- observation dependency graph closed and acyclic;
- все persisted observations checksum-valid;
- domain completeness вычислена детерминированно;
- no caller-supplied `passed=true` authority;
- no score, vote or optimizer objective;
- unique требует UNSAT после blocking clause;
- multiple содержит два разных canonical witnesses;
- none содержит conflict certificate;
- incomplete никогда не маскируется под unique/none;
- every atom owned exactly once;
- no value invention or mutation;
- explicit empty cells;
- merged headers проверяются separator constraints;
- identical values различаются по ids/refs;
- exact two-page continuation добавляет zero provider calls;
- model context не растёт от deterministic observation payloads;
- hard budgets проверяются до provider call и до solve;
- safe explanations не содержат customer values/raw payloads;
- replay deterministic;
- fresh holdout reference недоступен solver process.

## Отложенная работа

- three-or-more-page continuation chains;
- curved/distorted table geometry;
- production solver dependency selection;
- probabilistic routing calibration;
- automatic minimal unsat core reduction;
- borderless-table accuracy research;
- production Gate 2 authority.

Это отложено не потому, что неважно, а потому, что не требуется для первого проверяемого structural consensus slice.

## Финальное решение

Целевая архитектура — не dual-oracle и не majority multi-oracle. Это multi-observation, dependency-aware, finite-domain consensus:

```text
sealed document scope
  -> independent and derived observation contracts
  -> dependency-aware finite domain
  -> named hard constraints
  -> first satisfiability search
  -> blocking-clause second search
  -> unique | multiple | none | incomplete
  -> proof/explanation artifact
  -> exact source materialization only after unique proof
```

Здравое зерно текущего dual-oracle prototype сохраняется: anonymous visual topology, exact parser evidence, deterministic assembly, fail-closed validation и typed terminals. Меняется только концептуальная граница: solver должен доказывать структуру из полного набора типизированных наблюдений, а не арбитрировать два крупных ответа.

Следующий правильный шаг — formal observation lineage + finite domain builder + blocking-clause uniqueness prototype в default-disabled research path. Новый parser, новый serialization format и Gate 2 redesign для этого не нужны.
