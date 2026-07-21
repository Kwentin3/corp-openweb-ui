# OpenWebUI Broker Reports: forensic-аудит структурных отказов fresh holdout

Дата: 2026-07-14

Режим: research and forensic audit only

Исследуемый прогон: sealed fresh holdout v4

Production runtime: в рамках аудита не изменялся

## Итоговый статус

- `BROKER_REPORTS_FRESH_HOLDOUT_FAILURE_AUDIT_PARTIAL`
- `BROKER_REPORTS_CORRECT_TOPOLOGY_STAGE_OF_LOSS_PROVEN`
- `BROKER_REPORTS_VISUAL_HYPOTHESIS_COMPLETENESS_ASSESSED`
- `BROKER_REPORTS_CONSTRAINT_REJECTION_AUDITED`
- `BROKER_REPORTS_MINIMAL_NEXT_CORRECTION_READY`

Не заявлены:

- `BROKER_REPORTS_FRESH_HOLDOUT_FAILURE_AUDIT_READY`;
- `BROKER_REPORTS_STRUCTURAL_DOMAIN_COMPLETENESS_ASSESSED`;
- `BROKER_REPORTS_GENUINE_AMBIGUITY_ASSESSED`.

Причина `PARTIAL`: sealed terminal не содержит самостоятельного finite-domain artifact, compiled-constraint trace, blocking search или альтернативных solver witnesses. Текущий consensus runtime проверяет только уже собранные VLM-гипотезы. Поэтому по сохранённым данным можно доказать, почему получено `0/3`, но нельзя доказать полноту отсутствующего домена или формальную уникальность/неоднозначность каждой reference-структуры.

## Executive verdict

`0/3` вызвано не слабостью языка программирования solver и не недостатком числа оракулов.

- `holdout_001`: правильная структура впервые исчезла в visual generation. Обе попытки вернули `unsupported` без гипотез. Дополнительно protocol validation отвергла оба ответа из-за несортированных uncertainty codes.
- `holdout_002`: правильная структура впервые исчезла в visual generation. Обе попытки валидно вернули `unsupported` без гипотез.
- `holdout_003`: VLM дважды вернула правильные `3 x 6`, header depth, геометрию пяти spans и header hierarchy. Exact reference всё же не присутствовал: четыре вертикальных header spans были названы `merged`, тогда как reference использует `spanning_header`. Затем assembler дополнительно и необоснованно отверг правильную row/column geometry из-за неполного набора vector lines и отбросил spans из-за неприменимых global source-order/band-overlap требований.

Главный архитектурный вывод: текущий путь не строит полный конечный структурный домен. Он принимает от VLM готовые topology candidates, assembler либо превращает их в bindings, либо отбрасывает, после чего consensus перебирает только оставшиеся bindings.

## Ровно одно следующее направление

Выбрано **C. Correct specific structural constraints**.

Первый implementation slice должен исправить только доказанные ошибки assembler:

1. неполный или неприменимый набор vector-line boundaries должен означать `no geometry override`, а не `boundary_count_conflict`;
2. global parser source-order contiguity нельзя требовать от атомов многострочного merged/header span;
3. общий узкий x/y overlap всех слов нельзя использовать как обязательное доказательство многострочного span;
4. `header_relation_span_uncertified` должен исчезать как каскадный отказ, когда span не был ошибочно отброшен предыдущими двумя проверками.

Это направление выбрано раньше A, потому что текущие constraints всё равно заблокируют borderless topology после улучшения visual generation. Исправление C устраняет доказанный ложный отказ уже существующей VLM-гипотезы и не требует нового parser, provider, формата или solver framework.

## Scope и запреты

Аудит использует только уже запечатанные v4 artifacts и post-terminal human reference. Новых provider calls, повторной генерации гипотез и runtime-изменений нет.

Reference использован только для post-terminal сравнения. Он не передавался в:

- visual generation;
- assembler replay, имитирующий runtime;
- consensus acceptance;
- runtime materialization.

Counterfactual reference injection не выполнялся и доказательством не считается.

## Evidence boundary

Исследованы четыре неизменяемых набора:

- preregistration, terminal, post-terminal reference and score: retained in the
  ignored private evidence root; paths withheld.

Проверенные SHA-256 файлов:

| Artifact | SHA-256 |
|---|---|
| preregistration private | `48f3f31d32091bebec37e4a0b6f1c78fd1f488e99b3c7e97a51981c4f583e491` |
| terminal private | `2a9eaed161cd3fcc390dbade29aac9b130bcc9b1dfef634b2a910aa30e0c82e9` |
| reference private | `3deddc54a6ad92c978907d2be467fa84cd77d182e6d3ef58c0ccb1ca04204a9e` |
| score private | `13e87baf4b0e7c5a221aebf8203802f81594ff14704c01706ccfe187716b04d7` |

Terminal seal во всех связанных artifacts совпадает:

`a5a87738dea7cd17ce310471732cd9fce2e5d1bd83fbd4e79b753000ba1a99ed`

Также подтверждено:

- reference отсутствовал при preregistration;
- `reference_material_accessed=false` до запуска;
- `reference_process_started=false` в terminal;
- scorer зафиксировал `terminal_unchanged_during_scoring=true`;
- выполнено ровно `6/6 countTokens` и `6/6 generate`;
- hidden retries и failover отсутствовали.

## Что в текущей реализации называется solver

В текущем runtime нет domain builder, который комбинирует boundary, span, header и placement alternatives.

`pdf_dual_oracle_consensus.py`:

1. получает `vlm_hypothesis_set.hypotheses`;
2. вызывает `_evaluate_hypothesis` для каждой готовой гипотезы;
3. оставляет элементы с `accepted_by_constraints=true`;
4. группирует их по `canonical_grid_checksum`;
5. объявляет один, несколько или ни одного результата внутри supplied evidence.

Это видно в `pdf_dual_oracle_consensus.py:370-457`. В sealed terminal отсутствуют ключи или artifacts `finite_domain`, `domain_builder`, `compiled_constraints`, `blocking_clause`, `solver_witness`, `constraint_trace` и `rejection_trace`.

Следствие: термин `solver_search_complete` в текущем prototype не доказывает полноту всех физически допустимых структур. Он относится только к переданному набору VLM bindings.

## Общая survivability chain

```text
post-terminal human reference
  -> parser atoms and geometry: сохранены для 3/3
  -> two VLM attempts: 0 hypotheses / 0 hypotheses / 1 near-reference hypothesis
  -> assembler: no call / unsupported / two rejected bindings
  -> finite structural domain: отсутствует как самостоятельная стадия
  -> compiled constraints: только inline gates готовой гипотезы
  -> solver witnesses: отсутствуют для 3/3
  -> terminal: no_valid_consensus / unsupported / no_valid_consensus
```

## Root-cause matrix

| Проверка | `holdout_001` | `holdout_002` | `holdout_003` |
|---|---|---|---|
| Human reference | `3 x 3`, без headers/spans | `2 x 3`, без headers/spans | `3 x 6`, headers `1,2`, 5 header spans |
| Correct exact topology в VLM | Нет | Нет | Нет: geometry совпала, но 4 span relation labels отличаются |
| Correct row/column topology в VLM | Нет | Нет | Да, в обеих попытках |
| Представима текущим schema | Да | Да | Да |
| Собираема из фактически возвращённых relations | Нет: relations отсутствуют | Нет: relations отсутствуют | Нет exact; spatial topology была собираема до ошибочных constraints |
| Correct topology в finite domain | Нет: domain не строится | Нет: domain не строится | Нет: binding отброшен до consensus |
| Первый отказ | VLM `unsupported`; затем protocol error | VLM `unsupported` | `pdf_topology_assembly_parser_geometry_boundary_count_conflict` по row axis |
| Отказ оправдан source evidence | Нет для отсутствия topology; protocol order check формально соответствует контракту | Нет: crop и atoms содержат достаточное alignment evidence | Нет |
| Альтернативный valid witness | Не доказан; `2-column` визуально правдоподобен | Не доказан; `2-column` визуально правдоподобен | Не доказан |
| Context/evidence loss | Да, вторичный protocol loss из-за порядка codes; crop/atoms не потеряны | Нет | Нет |
| Минимальная общая коррекция класса | Разрешить whitespace/alignment column evidence в visual contract | Та же | Исправить polarity geometry evidence и span membership constraints |
| Оставшийся риск | `2 vs 3 columns` может остаться genuinely ambiguous | `2 vs 3 columns` может остаться genuinely ambiguous | relation semantics и отсутствие formal alternative domain |

## `holdout_001`: stage-of-loss

### Reference

- rows: `3`;
- columns: `3`;
- header rows: `[]`;
- spans: `[]`;
- review: `human_verified`.

### Parser atoms and geometry

- `14/14` word atoms сохранены;
- `3` parser lines;
- candidate ids и word refs уникальны;
- exactly-once ownership подтверждён;
- semantic grid parser не заявлял;
- whole-table mode, одно окно, continuation отсутствует.

Parser evidence не потерян. Три row bands видны и в atom y-ranges, и в фоновых/линейных horizontal signals. По x физические rectangles дают две крупные области, тогда как reference отдельно считает currency marker и amount, то есть использует alignment/whitespace как третью колонку.

### VLM attempts

Обе попытки вернули:

- `decision=unsupported`;
- `hypotheses=[]`;
- `alternatives_complete=true`;
- uncertainty: `no_visible_vertical_separators`, `no_visible_horizontal_separators`.

Правильной `3 x 3` topology нет ни в одной попытке.

Это согласуется не только с поведением модели, но и с текущим prompt contract. `pdf_visual_topology.py:164-189` требует считать row bands только по видимым borders, а `pdf_visual_topology.py:175-179` прямо запрещает boundary, поддержанный только whitespace. Model-facing flags повторяют требования `row_boundary_requires_visible_horizontal_separator=true` и `column_boundary_requires_visible_vertical_separator_in_unmerged_regions=true`.

Следовательно, reference currency split не просто не угадан: текущий visual contract подталкивает модель отказать в borderless/alignment-based структуре.

### Protocol loss

Обе VLM-попытки вернули uncertainty codes не в лексикографическом порядке. `_codes()` требует `value == sorted(set(value))` (`pdf_visual_topology.py:1503-1512`), поэтому обе реакции получили:

`pdf_visual_topology_uncertainty_codes_invalid`

Это реальный protocol loss, но не первичная причина отсутствия correct topology: даже нормализованный ответ всё равно содержал бы `unsupported` и ноль гипотез.

### Assembly, domain, constraints, solver

- assemblies: `0`;
- assembled hypotheses: `0`;
- finite domain: отсутствует;
- compiled constraints: не запускались;
- witnesses: `0`;
- terminal: `no_valid_consensus`;
- terminal reasons: `pdf_dual_oracle_all_vlm_evidence_invalid`, `pdf_visual_topology_uncertainty_codes_invalid`.

### Root cause

- primary: **1. Visual hypothesis missing**;
- secondary: **5. Evidence or protocol loss**;
- structural domain completeness и genuine ambiguity: не доказаны.

### Smallest general correction

Не добавлять новый provider. Уточнить narrow topology contract: повторяющиеся whitespace gutters и устойчивое выравнивание anonymous atom bands являются допустимым visual boundary evidence даже без нарисованной вертикальной линии. Модельный payload не увеличивается.

## `holdout_002`: stage-of-loss

### Reference

- rows: `2`;
- columns: `3`;
- header rows: `[]`;
- spans: `[]`;
- review: `human_verified`.

### Parser atoms and geometry

- `14/14` word atoms сохранены;
- `2` parser lines;
- unique candidate/word identity;
- exactly-once ownership подтверждён;
- whole-table mode, одно окно, continuation отсутствует.

Две row bands подтверждены horizontal geometry. Физические rectangle edges образуют две крупные области, но reference снова отделяет currency marker от amount по устойчивому выравниванию.

### VLM attempts

Обе попытки валидно вернули:

- `decision=unsupported`;
- `hypotheses=[]`;
- `alternatives_complete=true`;
- uncertainty: `no_visible_borders`.

В отличие от 001, protocol parser принял ответы. Assembler получил `unsupported`, но bindings не создал.

### Assembly, domain, constraints, solver

- assemblies: `2`, оба `reconstruction_status=unsupported`;
- received alternatives: `0`;
- bindings: `0`;
- finite domain: отсутствует;
- compiled constraints: не запускались;
- witnesses: `0`;
- terminal: `unsupported`;
- reason: `pdf_dual_oracle_vlm_hypothesis_unavailable`.

### Root cause

- primary: **1. Visual hypothesis missing**;
- evidence/context loss: не обнаружен;
- structural domain completeness и genuine ambiguity: не доказаны.

### Smallest general correction

Та же, что для 001: разрешить topology hypothesis на основе повторяющегося alignment/whitespace, не требуя нарисованной полной grid border. Это общий borderless-table rule, не Edward-Jones hardcode.

## `holdout_003`: stage-of-loss

### Reference

- rows: `3`;
- columns: `6`;
- header rows: `[1, 2]`;
- spans: `5`;
- header hierarchy: parent `r1/c4` над children `c4-c5`;
- все пять spans размечены как `spanning_header`;
- review: `human_verified`.

### Parser atoms and geometry

- `51/51` word atoms сохранены;
- `12` parser lines;
- unique candidate/word identity;
- exactly-once ownership подтверждён;
- whole-table mode, одно окно, continuation отсутствует;
- `58` horizontal и `26` vertical geometry signals.

Parser geometry содержит rectangle edges, почти совпадающие с VLM boundaries:

| Axis | VLM boundaries | Ближайшие rect-edge boundaries | Максимальная дельта |
|---|---|---|---:|
| rows | `0, .468, .820, 1` | `0, .467682, .814372, 1` | `.005628` |
| columns | `0, .185, .368, .556, .702, .848, 1` | `0, .185333, .366667, .558667, .700000, .846667, 1` | `.002667` |

При этом vertical `vector_line` signals равны `0`; присутствуют только vertical `rect_edge` signals. Horizontal vector lines включают декоративные underlines около нижней строки и не образуют ровно четыре полных row boundaries.

### VLM attempts

Обе попытки идентичны по structural payload и вернули:

- `decision=bound`;
- одну hypothesis;
- row boundaries: `4` edges, то есть `3` rows;
- column boundaries: `7` edges, то есть `6` columns;
- `header_row_count=2`;
- пять spans с теми же координатами, что reference;
- тот же header hierarchy;
- uncertainty: `[]`.

Row/column topology и spatial span geometry правильны.

Exact reference topology всё же отсутствует: VLM назвала четыре вертикальных header spans `merged`, а reference — `spanning_header`. Только horizontal parent span `r1/c4-c5` получил `spanning_header`. Scorer сравнивает `binding.spans == reference.spans` буквально (`local_pdf_structural_repair_holdout_score.py:536-550`), поэтому даже дошедший до scorer binding с исходными labels не был бы topology-exact.

Это не доказывает, что модель не увидела merge geometry. Скорее visual schema недостаточно чётко определяет различие `merged` и `spanning_header`: enum разрешает оба значения, но prompt подробно не задаёт каноническое правило для vertical header cells.

### Первый rejecting constraint

Execution order в `_bind_hypothesis`:

1. row axis canonicalization (`pdf_topology_assembly.py:624-632`);
2. column axis canonicalization (`633-641`);
3. span canonicalization (`671-689`);
4. header hierarchy validation (`691-739`).

Первый фактический blocker:

`pdf_topology_assembly_parser_geometry_boundary_count_conflict`

по row axis.

Терминальный список отсортирован по axis и визуально показывает column раньше row, но это формат сохранения, а не execution order.

### Почему boundary rejection недействителен

`_canonicalize_axis_from_parser_geometry` берёт только `kind == vector_line`. Если число line clusters не равно `expected_segments + 1`, функция возвращает исходные visual boundaries вместе с hard issue `boundary_count_conflict` (`pdf_topology_assembly.py:912-936`). Любой issue запрещает создание binding (`828-868`).

Для 003:

- vertical vector lines отсутствуют, поэтому они не могут опровергать шесть колонок;
- rectangle edges, наоборот, поддерживают семь column boundaries с максимальной дельтой `.002667`;
- лишние horizontal line clusters происходят от декоративных underlines и не опровергают три row bands;
- crop визуально поддерживает `3 x 6`.

Отсутствие полного набора line evidence превращено в отрицательное доказательство. Правильная семантика здесь — abstain from override, не reject hypothesis.

### Почему span rejections недействительны

После boundary issues assembler проверяет каждый span:

- source orders всех atom members должны образовать один глобально непрерывный диапазон;
- atom boxes должны иметь общий x-overlap для vertical span или общий y-overlap для horizontal span с tolerance `.002`.

Это реализовано в `pdf_topology_assembly.py:1055-1111`.

Фактические anonymous order sets:

| Span | Members | Source orders | Результат текущего gate |
|---|---:|---|---|
| `r1-r2/c1` | 5 | `19,20,21,28,29` | non-contiguous, non-overlapping band |
| `r1-r2/c2` | 10 | `6,7,13,14,15,24,30,31,36,37` | non-contiguous, non-overlapping band |
| `r1-r2/c3` | 10 | `8,9,16,17,18,25,32,33,38,39` | non-contiguous, non-overlapping band |
| `r1/c4-c5` | 11 | `0,1,2,3,4,5,10,11,12,22,23` | non-contiguous, non-overlapping band |
| `r1-r2/c6` | 2 | `26,27` | contiguous, non-overlapping band |

Глобальный PDF source order естественно чередует строки и соседние колонки. Многострочные слова внутри одного header cell также не обязаны иметь общий узкий x/y overlap. Поэтому эти два gates не доказывают ошибочность span.

Терминальные rejections:

- четыре `pdf_topology_assembly_span_source_order_not_contiguous`;
- один `pdf_topology_assembly_span_atom_band_incoherent`.

После удаления spans header hierarchy закономерно получает каскадный:

`pdf_topology_assembly_header_relation_span_uncertified`

Он не является независимой первопричиной.

### Assembly, domain, constraints, solver

- assemblies: `2`;
- topology alternatives received: `1 + 1`;
- all `51` candidates были распределены ровно по одному разу в каждой попытке;
- grid positions: `18`;
- explicit empty positions: `1`;
- bindings created: `0`;
- reconstruction: `regional_retry_required`;
- finite domain: отсутствует;
- downstream solver witnesses: `0`;
- terminal: `no_valid_consensus`.

Правильная spatial topology не вошла в consensus supplied evidence: assembler отбросил её раньше.

### Root cause

- **1. Visual hypothesis missing** — только для exact span relation labels;
- **3. Incorrect constraint rejection** — доказано для правильной row/column и span geometry;
- evidence/context loss: не обнаружен;
- genuine ambiguity: не доказана.

### Smallest general correction

Исправить существующие assembler gates, не ослабляя downstream validators:

- geometry может отвергать topology только при положительном противоречащем separator evidence; неполный cluster set должен оставить visual boundaries без override;
- span membership проверять по ownership и отсутствию separator crossing, а не по глобальной непрерывности source order;
- multiline header span не должен требовать общего overlap всех word boxes;
- relation label канонизировать отдельным, явно описанным header-span contract, а не подгонять scorer.

## Domain completeness assessment

### Что доказано

- correct topology отсутствовала в supplied evidence у 001 и 002;
- у 003 near-reference hypothesis была отброшена до consensus;
- consensus не генерирует новые boundaries, spans, header relations или placements;
- поэтому correct exact reference не находилась в фактически проверяемом наборе ни для одной таблицы.

### Что не доказано

- полный ли набор boundary candidates можно было построить из parser gaps/rect edges;
- все ли span/header alternatives были перечислены;
- существовала ли ровно одна удовлетворяющая структура;
- завершился ли полный поиск по всем физически допустимым структурам.

Причина — такой домен не persisted и фактически не строится. Поэтому статус `BROKER_REPORTS_STRUCTURAL_DOMAIN_COMPLETENESS_ASSESSED` не заявлен.

## Ambiguity assessment

Для 001 и 002 визуально правдоподобны минимум две интерпретации:

1. reference: label, currency marker, amount — три колонки;
2. physical rectangle view: label и amount-with-currency — две колонки.

Это полезный counterexample к преждевременному `unique`, но не формальный solver witness: текущий runtime не построил и не проверил обе структуры.

Для 003 alternative valid witness также не сохранён. Две одинаковые model attempts не доказывают уникальность.

Поэтому genuine ambiguity остаётся **не доказанной и не опровергнутой** для 3/3. Typed block до появления полного bounded domain остаётся правильным поведением.

## Context-budget impact

Контекст не был причиной `0/3`.

| Target | Atoms | Model JSON | Counted input tokens | Windowing |
|---|---:|---:|---:|---|
| 001 | 14 | 4,112 bytes | 2,744 | whole table, 1 window |
| 002 | 14 | 4,075 bytes | 2,671 | whole table, 1 window |
| 003 | 51 | 7,312 bytes | 5,070 | whole table, 1 window |

Все значения значительно ниже caps `49,152 bytes`, `20,000 input tokens`, `1,000 atoms`; изображения также ниже `8 MiB`. Continuation и stitching не применялись. Atom ownership до visual stage сохранён.

Предложенные изменения не должны увеличивать prompt payload:

- whitespace/alignment уже видны в crop и anonymous atom boxes;
- deterministic rectangle/line classification должна идти прямо в assembler/domain logic;
- forensic ledger, reference, source values и full PDF в модель не добавляются.

Bounded VLM context остаётся:

- один crop или deterministic window;
- anonymous atom ids;
- компактные coordinates/order;
- narrow topology contract.

## Overengineering assessment

Direction F не обосновано.

Ни одна таблица не дошла до сложного exhaustive search:

- 001: `0` hypotheses;
- 002: `0` hypotheses;
- 003: по одной гипотезе на attempt, обе отброшены assembler.

Нет evidence, что bounded pure-Python enumeration не способен представить или перебрать нужный домен. Добавление SAT, SMT, CP-SAT или нового universal consensus platform сейчас лишь скроет ошибки observation/constraint contracts.

Также не нужен новый parser или VLM provider: 003 уже показывает, что существующая модель способна вернуть правильную spatial topology; 001/002 блокируются узким visual contract, а не отсутствием ещё одного оракула.

## Smallest recommended implementation slice

Scope одного default-disabled research slice:

1. добавить три focused fixtures из sealed v4 без raw values;
2. изменить geometry gate: incomplete line cluster set → abstain, positive conflicting separator set → reject;
3. заменить global span source-order/band-overlap gates на ownership + no-crossing-separator checks;
4. сохранить все текущие candidate ownership, value immutability, crop identity и fail-closed validators;
5. прогнать sealed 003 response без provider calls;
6. потребовать, чтобы две исходные VLM attempts создавали один и тот же binding candidate;
7. не считать это accuracy pass, пока exact span relation semantics и fresh reference score не подтверждены отдельно.

Acceptance evidence:

- никаких reference reads в replay process;
- `51/51` atoms owned exactly once;
- `3 x 6`, five spatial spans, one hierarchy;
- zero invented values;
- deterministic repeat;
- named rejection trace для каждого оставшегося blocker;
- no changes to production Gate 2 authority.

Следующий после него, но не входящий в выбранное направление, slice A может уточнить borderless visual contract для 001/002. Смешивать оба изменения в одном patch не следует: иначе нельзя будет понять, какой contract исправил какой класс отказа.

## Что не следует строить

- SAT/SMT/CP-SAT dependency;
- новый universal solver framework;
- ещё один parser;
- ещё один VLM provider;
- новый serialization format;
- voting, confidence averaging или oracle ranking;
- full-PDF prompt;
- forensic payload в model context;
- source values или business prompts в topology request;
- runtime-доступ к human reference;
- Edward-Jones-specific boundary/span rules;
- ослабление scorer или validators ради прохождения reference;
- автоматическую acceptance на основании двух одинаковых model attempts;
- Gate 2 authority до отдельного accuracy gate.

## Risks и deferred work

### Risks

- `merged` vs `spanning_header` остаётся неоднозначным без чёткой canonical semantics;
- incomplete geometry must abstain, но positive contradictory separator evidence всё ещё должно fail closed;
- 001/002 могут остаться действительно неоднозначными даже после prompt correction;
- текущий `solver_search_complete` легко принять за более сильное доказательство, чем он даёт;
- отсутствие persisted domain/constraint trace затрудняет будущие forensic audits.

### Deferred

- finite-domain builder;
- formal domain completeness certificate;
- blocking-clause uniqueness proof;
- two-witness ambiguity artifact;
- safe named constraint trace;
- borderless visual contract slice A;
- production accuracy and Gate 2 authority.

## Финальное решение

Причина `0/3` изолирована на фактическом runtime path:

```text
001: intact parser evidence
  -> VLM unsupported, no topology
  -> uncertainty-code protocol rejection
  -> no assembly/domain/witness

002: intact parser evidence
  -> VLM unsupported, no topology
  -> no binding/domain/witness

003: intact parser evidence
  -> correct 3 x 6 spatial topology, non-canonical span labels
  -> invalid geometry and span constraints
  -> no binding/domain/witness
```

Следующее направление — **C: исправить конкретные structural constraints** в default-disabled research replay. Это наименьший проверяемый шаг, который устраняет доказанный ложный отказ и не возвращает context explosion.

Полный audit-ready статус пока запрещён отсутствием finite-domain и witness evidence в sealed run. Текущий typed block следует сохранить.
