# Broker Reports PDF Table Intake Filter Audit

Дата: 2026-07-15

Режим: research / forensic audit only

Корпус: frozen public v5, 7 PDF, 27 сохранённых parser candidates

Изменения production runtime: отсутствуют

## Executive verdict

Текущий входной фильтр действительно **пережёсткий**, но его нельзя просто ослабить.

Он смешивает три разных вопроса в одном `eligible=true/false`:

1. область вообще похожа на таблицу;
2. текущий bounded pipeline технически может её обработать;
3. область подходит как контролируемая цель accuracy-holdout.

На 27 кандидатах это дало следующий результат:

- 3 полноценные настоящие таблицы;
- 1 настоящий фрагмент таблицы;
- 1 оглавление;
- 22 ложных широких кандидата из обычного текста или макета страницы;
- среди этих 22 ложных широких кандидатов 7 содержат внутри меньшие настоящие таблицы, но сами таблицами не являются;
- не менее 10 таблиц Moomoo не получили отдельного bounded-кандидата.

Фильтр отклонил все 27 областей. Поэтому его candidate-level confusion matrix для финансовых таблиц: `TP=0, FP=0, FN=4, TN=23`.

Это одновременно доказывает две вещи:

- ложные отказы реальных таблиц есть;
- blanket relaxation небезопасен: 23 из 27 отклонений были правильными для целого исходного прямоугольника.

Все 27 областей укладываются в уже существующие downstream-пределы: максимум 55 parser rows, 10 columns и 615 word atoms при потолках 64, 24 и 1 000. Большие области могут идти через не более 16 вертикальных atom windows. Следовательно, текущие отказы в основном описывают правдоподобие и выбор holdout, а не техническую невозможность обработки.

Три PDF с нулём кандидатов остановились ещё раньше:

- оба IBKR превысили общий document inventory cap `75 000`; затем parser вернул terminal с `pages=[]` и стёр уже найденные постраничные кандидаты;
- Wealthfront был остановлен только по `is_encrypted=True`, хотя открывается пустым паролем, разрешает text extraction и имеет читаемый text layer.

Ни один из трёх zero-candidate случаев не доказывает отсутствие таблиц, image-only layout или необходимость VLM/OCR.

Рекомендация — ровно один следующий slice: **E = C + одна узкая A-коррекция**. Сначала разделить detection, processability и holdout selection contracts; в том же малом slice перестать превращать document-inventory overflow в пустой результат и сохранить уже полученный bounded page prefix как честный partial result. Лимит `75 000` не повышать. VLM challenge и empty-password support оставить отдельными последующими решениями.

## Evidence boundary and method

Аудит выполнен после frozen run и поэтому не меняет его результат. Использованы:

- неизменённые bytes семи PDF из `local/stage2/broker_reports_pdf_structural_holdout_public_v5_2026-07-15/corpus`;
- production normalizer и production v5 eligibility factory;
- сохранённые parser geometry, cell/word ownership и reason codes;
- read-only page-local parser diagnostics для объяснения нулевых результатов;
- page text и визуальная проверка исходного bbox каждого из 27 кандидатов;
- существующие downstream budget contracts.

Provider/VLM не вызывался. Reference answers, бизнес-промпты и будущие holdout labels не использовались при frozen selection. Ground truth ниже — post-run forensic adjudication; после этой проверки все семь PDF являются development evidence и больше не являются unseen holdout.

## Separation of detection, processability and holdout eligibility

| Решение | Правильный вопрос | Допустимые исходы | Пример из корпуса |
|---|---|---|---|
| Detection assessment | Область правдоподобно является таблицей? | `plausible`, `implausible`, `uncertain`, `absent_due_to_upstream_failure` | Betterment p4: plausible; Moomoo annual p9: целый bbox implausible/compound |
| Processability decision | Можно ли безопасно обработать область в текущих hard budgets? | `processable`, `unsupported` + точный hard reason | Все 27: processable; invalid transform: unsupported |
| Holdout selection decision | Полезна ли область как заранее контролируемая accuracy target? | `selected`, `not_selected`, `not_evaluated` | DriveWealth p11: processable fragment, но не standalone holdout target |

Один объект может быть:

- правдоподобной таблицей и processable, но не подходить для holdout;
- ложным широким кандидатом, который технически processable;
- хорошим holdout target, который текущий selection policy не может выбрать;
- `absent` не потому, что таблицы нет, а потому, что upstream parser завершился partial/blocked.

Текущий runner сначала удаляет всё, где общий `eligible` не равен `true`, и только потом применяет v5 selection (`local_pdf_structural_repair_holdout.py:404-435`). v5 selector дополнительно требует три цели из одного документа и присутствие both aligned and ruled strategies (`:886-968`). Это preference для состава holdout, а не safety property.

## Current filter confusion matrix

| View | TP | FP | FN | TN | Что это показывает |
|---|---:|---:|---:|---:|---|
| Financial table / fragment plausibility | 0 | 0 | 4 | 23 | Три реальные таблицы и один фрагмент потеряны |
| Standalone holdout suitability до раскрытия корпуса | 0 | 0 | 3 | 24 | Betterment p4, DriveWealth p7 и p9 были usable targets; теперь они development-only |
| Technical processability | 0 | 0 | 27 | 0 | Общий `eligible=false` ошибочно выглядит как technical block, хотя все 27 внутри hard bounds |

Последняя строка не говорит, что все 27 надо отправить модели. Она говорит только, что resource/safety contract сам по себе их не запрещает.

## Per-rule false-positive and false-negative effects

Числа ниже пересекаются и не суммируются. `True` означает полноценную таблицу или настоящий фрагмент; `false candidate` — TOC, ordinary text или page-layout compound как целая область.

| Current check | Всего отклоняет | True отклонено | False candidates удалено | Фактическая роль | Дублирование / основание |
|---|---:|---:|---:|---|---|
| Candidate state, page/ref identity | 0 | 0 | 0 | Hard integrity | Не дублируется; обязательная адресуемость доказана контрактом |
| Allowed strategy | 0 | 0 | 0 | Routing capability | Не является safety of region |
| Geometry confidence: aligned `0.8`, ruled minimum `0.9` | 0 | 0 | 0 | Routing label | Parser присваивает фиксированные `0.8` и `0.95`; это не калиброванная вероятность |
| Rows `2..20` / `row_extent` | 23 | 2 | 21 | Holdout preference / routing | Сильно пересекается с height/area; `20` не является downstream hard limit |
| Columns `2..16` | 0 | 0 | 0 | Holdout preference / routing | Downstream уже допускает 24; точность `16` не доказана |
| Width `0.10..0.98` | 0 | 0 | 0 | Geometry annotation / routing | Crop safety обеспечивается отдельными pixel/byte limits |
| Height `0.02..0.55` | 22 | 1 | 21 | Routing signal | На корпусе почти повторяет rows и полностью повторяет area |
| Area `<=0.55` | 22 | 1 | 21 | Redundant routing signal | Логически избыточен: `width<=0.98` и `height<=0.55` уже дают `area<=0.539` |
| Cell-count consistency | 0 | 0 | 0 | Hard integrity | Оставить как consistency check, если grid заявлен |
| Minimum 4 populated cells | 1 | 1 fragment | 0 | Holdout preference | Удаляет только настоящий DriveWealth p11 fragment |
| Fill ratio `>=0.5` | 5 | 3 | 2 | Weak routing signal | На этом корпусе сильнее бьёт по true tables, чем по false candidates |
| Combined `structural_signal_sparse` | 6 | все 4 | 2 | Weak routing signal | Объединяет два разных условия и скрывает причину |
| Every row and column populated | 27 | все 4 | все 23 | Annotation / normalization hint | Нулевая дискриминация; это и есть current `multi_region_coverage` check |
| Exact word ownership once | 0 | 0 | 0 | Hard safety/integrity | Сохраняет immutable atom provenance; оставить hard |
| Minimum ruling evidence | 0 | 0 | 0 | Strategy routing | Для claimed ruled route evidence нужно, но numeric threshold `4` не калиброван |
| Source/reference values forbidden during selection | N/A | N/A | N/A | Hard holdout purity | Это не candidate plausibility rule |

`maximum row count` и `row extent` — одно правило и один reason code. `every row/column populated` и `multi-region coverage` — также одна реализация, а не независимые сигналы.

### First rejecting rule in source evaluation order

Reason codes хранятся sorted, поэтому «первый» здесь восстановлен по порядку проверок в `_candidate_eligibility_reason_codes`:

| First rule | Candidates | True | False |
|---|---:|---:|---:|
| `row_extent_unsupported` | 23 | 2 | 21 |
| `structural_signal_sparse` | 2 | 2 | 0 |
| `multi_region_coverage_rejected` | 2 | 0 | 2 |

Ослабление только coverage не спасёт ни одной из четырёх true regions: они раньше падают на rows или sparse.

### Rule overlap patterns

- 19 candidates: coverage + rows + height + area;
- 3: coverage + rows + height + area + sparse;
- 2: coverage only;
- 2: coverage + sparse;
- 1: coverage + rows + sparse.

Rows, height и area удаляют один и тот же набор из 21 false candidates. Rows дополнительно ошибочно удаляет Betterment p4. Area не даёт самостоятельной защиты. Sparse ошибочно удаляет все четыре true regions и только два false candidates. Эти метрики годятся как risk/routing metadata, но не как самостоятельные hard pre-VLM blocks.

## Candidate-level classification

Обозначения: `A` = `aligned_text_v0`, `R` = `ruled_lines_v0`; `ROW`, `SPARSE`, `COVER` — первый reason по фактическому порядку проверок. `Created` относится к frozen run. `Justified` оценивает отклонение целого bbox как intake table region; для fragment отдельно указано отличие holdout decision.

| # | PDF / page | Candidate | Post-run class | Created | First reject | Justified | Processable | VLM useful | Minimal correction | Remaining risk |
|---:|---|---|---|---|---|---|---|---|---|---|
| 1 | Betterment p2 | A 5x4 | Table of contents | yes | COVER | yes | yes | no | TOC должен быть holdout exclusion, не technical failure | TOC геометрически похож на schedule |
| 2 | Betterment p4 | R 21x5 | Real table | yes | ROW | no | yes | yes | Rows/density/empty currency columns сделать metadata; считать normalized core | Section headers, symbol columns, spans |
| 3 | Betterment p5 | A 54x9 | Page layout / ordinary prose | yes | ROW | yes | yes | no | Suppress page-wide paragraph alignment | Не подавить настоящую full-page borderless table |
| 4 | Betterment p6 | A 54x8 | Page layout / ordinary prose | yes | ROW | yes | yes | no | То же | То же |
| 5 | Betterment p7 | A 50x8 | Page layout / ordinary prose | yes | ROW | yes | yes | no | То же | То же |
| 6 | Betterment p8 | A 55x9 | Page layout / ordinary prose | yes | ROW | yes | yes | no | То же | То же |
| 7 | Betterment p9 | A 16x6 | Ordinary text | yes | COVER | yes | yes | no | Для aligned proposal требовать повторяемые axes/gutters, не только общий left edge | Numeric prose |
| 8 | DriveWealth p5 | A 43x10 | Page layout / auditor letter | yes | ROW | yes | yes | no | Suppress letterhead + paragraph compound | Page furniture |
| 9 | DriveWealth p7 | A 33x6 | Real table plus blank bands/footer | yes | ROW | no | yes | yes | Normalized core может убрать только доказанный outer noise, сохранив original bbox | Footer leakage, separator rows |
| 10 | DriveWealth p9 | R 4x6 | Real table | yes | SPARSE | no | yes | yes | Sparse and empty symbol columns сделать metadata | Нет явного column header, indents |
| 11 | DriveWealth p11 | R 2x4 | Table fragment: wrapped first row of 4-row schedule | yes | SPARSE | no for intake; yes for holdout-as-is | yes | yes | Детерминированно проверить adjacent rows/merge, затем заново оценить | Over-merge соседних schedules |
| 12 | Moomoo annual p7 | A 48x7 | Page layout / ordinary prose | yes | ROW | yes | yes | no | Suppress broad prose candidate | Full-page borderless false suppression |
| 13 | Moomoo annual p8 | A 47x7 | Page layout / ordinary prose | yes | ROW | yes | yes | no | То же | То же |
| 14 | Moomoo annual p9 | A 46x10 | Compound page region containing one smaller table | yes | ROW | yes for whole bbox | yes | yes | Bounded subregion proposal; whole bbox не принимать | Crop/atom ownership loss |
| 15 | Moomoo annual p10 | A 42x10 | Ordinary text; real table lies below candidate bbox | yes | ROW | yes | yes | yes, page-level only | Page-level bounded region proposal | Candidate crop не видит пропущенную таблицу |
| 16 | Moomoo annual p11 | A 32x8 | Compound page region containing fixed-assets table | yes | ROW | yes for whole bbox | yes | yes | Bounded subregion proposal | Table/prose conflation |
| 17 | Moomoo annual p13 | A 42x9 | Page layout / ordinary prose | yes | ROW | yes | yes | no | Suppress broad prose candidate | Borderless false suppression |
| 18 | Moomoo annual p14 | A 32x9 | Compound page region containing two tables | yes | ROW | yes for whole bbox | yes | yes | Return two bounded proposals, не один merged crop | Cropping totals / merging tables |
| 19 | Moomoo annual p15 | A 41x9 | Page layout / ordinary prose | yes | ROW | yes | yes | no | Suppress broad prose candidate | Borderless false suppression |
| 20 | Moomoo midyear p4 | A 47x8 | Page layout / ordinary prose | yes | ROW | yes | yes | no | Suppress broad prose candidate | То же |
| 21 | Moomoo midyear p5 | A 50x9 | Page layout / ordinary prose | yes | ROW | yes | yes | no | То же | То же |
| 22 | Moomoo midyear p6 | A 45x8 | Compound page region containing allowance table | yes | ROW | yes for whole bbox | yes | yes | Bounded subregion proposal | Crop/atom ownership loss |
| 23 | Moomoo midyear p7 | A 41x8 | Compound page region containing fair-value table | yes | ROW | yes for whole bbox | yes | yes | Bounded subregion proposal | Table touches candidate edge |
| 24 | Moomoo midyear p8 | A 33x8 | Compound page region containing fixed-assets table | yes | ROW | yes for whole bbox | yes | yes | Bounded subregion proposal | Table/prose conflation |
| 25 | Moomoo midyear p9 | A 50x8 | Page layout / ordinary prose | yes | ROW | yes | yes | no | Suppress broad prose candidate | Borderless false suppression |
| 26 | Moomoo midyear p10 | A 38x9 | Compound page region containing two tables | yes | ROW | yes for whole bbox | yes | yes | Return two bounded proposals | Cropping totals / merging tables |
| 27 | Moomoo midyear p11 | A 45x7 | Page layout / ordinary prose | yes | ROW | yes | yes | no | Suppress broad prose candidate | Borderless false suppression |

### Candidate conclusions

- False rejections: Betterment p4, DriveWealth p7, p9 and p11.
- Correct whole-bbox rejections: remaining 23.
- False parser candidates: 22 broad page-layout/prose regions plus one structurally tabular TOC that is invalid only for financial-table holdout use.
- Standalone tables missed inside/near broad candidates: at least 10 across Moomoo annual p9, p10, p11, p14 (two) and midyear p6, p7, p8, p10 (two).
- VLM challenge would have forensic value for 12 candidate/pages: 4 true regions/fragments and 8 Moomoo pages with contained or adjacent missed tables. It is not justified for the 15 obvious whole-page prose/TOC negatives.

`Processable=yes` означает только прохождение declared hard resource ceilings. Это не означает table presence, корректную reconstruction или разрешение на provider call.

## Zero-candidate PDF analysis

| PDF | Real table | Candidate created in frozen run | First blocking rule | Rejection justified | Processable under current downstream limits | VLM challenge useful for immediate cause | Minimal correction | Remaining risk |
|---|---|---|---|---|---|---|---|---|
| IBKR audited 2025 | yes | no | `pdf_layout_document_inventory_budget_exceeded` | no | yes, bounded regions | no | Preserve bounded parsed prefix as explicit partial instead of returning `pages=[]`; later design page/chunk-local accounting | Prefix remains incomplete; true tables also exist after p22 |
| IBKR midyear 2025 | yes | no | `pdf_layout_document_inventory_budget_exceeded` | no | yes, bounded regions | no | Same | Prefix remains incomplete; related-party table is on p21 |
| Wealthfront 2026 | yes | no | `pdf_encrypted_without_key` on any `is_encrypted=True` | no | yes, readable empty-password document | no | In a later isolated slice, try exactly empty password and verify extraction permission before blocking | Never admit password-required or extraction-forbidden PDF |

### IBKR: document cap erases valid page work

`PdfLayoutParserConfig.max_inventory_objects_per_document` is `75 000`. Parser accumulates chars, words, lines, blocks, vectors, rects and candidates. When cumulative count becomes larger than the cap, `_terminal_result` returns `pages=[]`, zero diagnostics and `table_candidate_status=blocked`.

Read-only page-local replay with the same per-page policies established:

| PDF | Full page-local inventory | First cap crossing | Latent page candidates | Frozen output candidates |
|---|---:|---|---:|---:|
| IBKR audited | 97,327 | p22, cumulative 78,687 | 29 | 0 |
| IBKR midyear | 80,418 | p20, cumulative 77,639 | 22 | 0 |

The audited statement page p6 and midyear statement page p3 already produced three ruled fragments each before the cap. Therefore zero candidates is caused by terminal semantics, not by absent tables or absent geometry.

Merely preserving the prefix is a deliberately small recovery, not complete detection. Audited p25-p29 and midyear p21 contain later real schedules. A later page/chunk-local design would be needed to reach every page without accumulating an unbounded document inventory. Blindly raising `75 000` is not supported by this evidence.

### Wealthfront: readable empty-password encryption is classified as corrupt/unsupported

The PDF reports `is_encrypted=True`, but `decrypt("")` succeeds, all 12 pages are readable, and permissions include `EXTRACT` and `EXTRACT_TEXT_AND_GRAPHICS`. Current adapter blocks immediately on the flag and never attempts the empty password. Consequently layout never runs.

The file contains at least the Statement of Financial Condition on p6 and a fair-value table on p10. A read-only pdfplumber diagnostic produced 14 page candidates, including broad aligned regions; this confirms extractability but does not validate those 14 as tables.

The correct deterministic rule is not “accept encrypted PDF”. It is: try only the empty user password, verify allowed extraction and source checksum, otherwise remain fail-closed. This is proven but intentionally deferred from the one recommended next slice.

### Other real tables not proposed as bounded candidates

- Moomoo: at least 10 small tables listed in the candidate section were embedded in broad prose candidates or lay outside their bbox.
- IBKR audited: the frozen projection lost the statement p6 and later note/supplemental tables on p11-p21 and p25-p29.
- IBKR midyear: the frozen projection lost the statement p3 and note tables on p8, p11-p17 and p21.
- Wealthfront: the frozen projection lost p6 and p10 before layout detection began.

These are detection failures. They must not be “repaired” by declaring the broad page candidates to be tables.

## Proposed minimal intake contract

This section is a contract proposal only; no new runtime or serialization was added by the audit.

### 1. Detection assessment

Required observations:

- original document/page identity and immutable original bbox;
- `plausible | implausible | uncertain | absent_due_to_upstream_failure`;
- proposed strategy and deterministic evidence: rulings, repeated column anchors/gutters, connected regions;
- raw rows/columns, raw fill, empty bands, page extent and candidate atoms;
- optional normalized-core descriptor with an exact original-to-core mapping;
- reason codes that describe evidence, not processability.

Detection has no authority to relax resource, provenance or ownership limits.

### 2. Processability decision

`unsupported` is allowed only for an exact demonstrated technical failure:

- invalid, empty, non-finite or out-of-page region;
- broken or unreconcilable source-to-crop coordinate transform;
- no usable text atoms and no usable raster evidence;
- source bytes/hash/provenance cannot be preserved;
- unsafe crop or crop identity/checksum failure;
- hard image byte/pixel, atom, model JSON or counted-token budget exceeded;
- impossible ownership accounting: duplicate, missing or out-of-region atoms;
- contract/schema/checksum failure.

Otherwise the result is `processable`, even if the area is likely prose. Processable regions can still be routed to `implausible`, `challenge` or `not_selected` without a provider call.

### 3. Holdout selection decision

Selection has a separate policy checksum and may prefer:

- full tables over unresolved fragments;
- representative ruled, borderless, sparse, multi-row-header and continuation cases;
- diversity across the frozen corpus;
- no TOC, decorative/page-layout compounds or unresolved multiple-table regions;
- targets whose exact source/reference values remained sealed.

Requirements such as “three targets from one document” or “both parser strategies in the selected document” belong only here. They cannot be reused as intake safety.

## Exact checks that must remain hard and checks that should become routing metadata

| Keep hard | Move to routing/description |
|---|---|
| Source hash, document/page identity, immutable provenance | Raw row and column counts before downstream reconstruction |
| Finite non-empty bbox and valid coordinate transform | Page width/height/area ratios |
| Usable text or raster evidence | Fill ratio / sparse classification |
| Crop checksum, dimensions, pixel/byte budgets and proven value masking before any intake VLM call | Empty separator rows/columns and currency-symbol columns |
| Atom, model JSON, counted-token and response budgets | Missing grid lines / borderless label |
| Exact atom ownership once, no missing/duplicates | Header depth, indentation and merged-region likelihood |
| Parser/schema/checksum consistency | Parser strategy and fixed geometry confidence |
| Reference/source-value isolation during holdout selection | Page furniture, component count, continuation likelihood |

If a region claims `ruled_lines_v0` without sufficient rulings, that route may be rejected or downgraded. The region itself should not become technically unsupported solely for lacking lines.

## Useful table core hypothesis

Гипотеза подтверждается как безопасный способ **измерения и маршрутизации**, но не как способ подогнать кандидата под threshold.

Core may exclude only deterministically proven layout noise:

- fully empty outer margins;
- fully empty separator bands, while retaining their positions in the mapping;
- repeated page furniture outside the table;
- footer outside the connected table body.

Required invariants:

1. Preserve `original_bbox`, original candidate identity and all source atoms.
2. Record `core_bbox`, each excluded band/region and its deterministic reason.
3. Preserve an exact original-to-core coordinate mapping.
4. Never exclude a populated atom, label, total, footnote or span merely to improve density.
5. Compute raw and core metrics side by side; never overwrite raw evidence.
6. If normalization produces multiple populated cores, mark the input `compound/uncertain`; do not silently merge or choose the convenient one.

Betterment p4 demonstrates the issue: empty symbol/separator columns make the raw ruled grid fail coverage and density even though the table is real. DriveWealth p7 demonstrates empty outer bands/footer. Moomoo demonstrates the opposite risk: a large prose bbox may contain one or two true subregions, so trimming cannot justify accepting the entire page.

## VLM intake role

VLM полезен не как новый фильтр с правом решения, а как bounded visual challenge между deterministic proposal и strict reconstruction:

1. deterministic detector предлагает bounded region или честно сообщает, что region отсутствует;
2. VLM описывает visual structure и при необходимости предлагает ограниченную корректировку bbox;
3. parser заново выбирает exact immutable atoms по координатам;
4. downstream validators проверяют ownership, topology, budgets и provenance;
5. `uncertain` не превращается автоматически в `eligible`.

VLM не может:

- выбирать row/density/area thresholds;
- отключать hard validators;
- придумывать source values или исправлять числа;
- принимать whole-page compound как таблицу без bounded proposal;
- выбирать accuracy target после просмотра reference answer.

### Bounded output vocabulary

- `table_presence`: `present | absent | uncertain`;
- `structure`: `ruled | borderless | mixed | uncertain`;
- `density`: `sparse | dense | uncertain`;
- `header`: `simple | multi_row | absent | uncertain`;
- `merged_regions`: `yes | no | uncertain`;
- `continuation`: `none | possible | likely | uncertain`;
- bounded visual reason codes;
- normalized bbox proposals only, never values or reconstructed cells.

### Two possible challenge paths

| Path | Trigger | Model image | Model-visible atoms | Maximum proposals | Authority |
|---|---|---|---|---:|---|
| Candidate-crop challenge | Plausible/uncertain bounded candidate with unusual sparse/core evidence | Exactly one value-masked geometry crop | Up to 1,000 anonymous IDs/coordinates, no text values, also constrained by 48 KiB JSON | 1 adjusted bbox inside source crop | Routing only |
| Page-level region proposal | No bounded candidate, candidate misses visible table, or compound contains multiple tables | Exactly one value-masked geometry page | 0; parser atoms are attached only after proposal | 2 non-overlapping bboxes | Routing only |

The page path is necessary for Moomoo annual p10 because the true table lies below the candidate bbox, and for pages with two tables. A candidate-only crop cannot recover content it does not contain.

`Value-masked geometry` означает локально созданное изображение, где все распознанные text/value glyph regions закрыты нейтральными масками, а lines, whitespace, word-box geometry и relative placement сохранены. Raw crop/page с видимыми customer/source values отправлять нельзя. Original crop hash, atom ledger и source-to-masked mapping остаются private. Если exact masking coverage нельзя доказать, provider call запрещён и результат остаётся `unsupported_for_vlm_challenge`.

## Context-budget impact

Each individual VLM intake decision must obey all of the following. These are current hard ceilings reused from existing contracts; they are ceilings, not expected normal consumption.

| Resource | Candidate-crop challenge | Page-level proposal |
|---|---|---|
| PDF scope | One page identity, never PDF bytes | One page identity, never PDF bytes |
| Images | Exactly 1 value-masked crop | Exactly 1 value-masked rendered page |
| Render | 150 DPI only for intake | 150 DPI only for intake |
| Image dimensions | <=4096 x 4096, <=16,000,000 pixels | Same |
| Encoded image | <=8 MiB PNG | Same |
| Source-owned atoms | <=1,000 | 0 before proposal; proposed regions re-enter deterministic atom selection |
| Model JSON | <=48 KiB | <=48 KiB |
| Counted input | <=20,000 tokens | <=20,000 tokens |
| Output | <=8,192 tokens and <=512 KiB JSON | Same |
| Transport response | <=2 MiB | <=2 MiB |
| Provider calls | At most 1 `countTokens` + 1 generate | Same |
| Retry/failover | 0 / forbidden | 0 / forbidden |

The model view may contain only sanitized crop/page identity, coordinate space, anonymous atom IDs/coordinates where applicable, the bounded question, and the output schema. It must not contain:

- whole PDF;
- forensic payload or full normalizer projection;
- raw customer/source values, readable glyphs or reconstructed cells;
- business prompts;
- duplicated source ledgers;
- reference answers.

On this corpus only 12 of 27 candidate/pages merit a challenge: 4 true regions/fragments and 8 Moomoo pages with contained/adjacent missed tables. Fifteen obvious negative candidates should cost zero provider calls. A retrospective upper bound would therefore be 12 count calls plus 12 generate calls, not calls for all 27; no such calls were made in this audit.

VLM is not part of the recommended next slice because the three zero-candidate root causes are deterministic, and broad page candidates first need contract separation.

## One recommended implementation slice

### Decision: E — combine C with one narrowly proven A correction

Implement exactly these two tightly coupled changes:

1. Introduce separate detection assessment, processability decision and holdout selection decision. Keep legacy `eligible` authoritative only during a shadow transition; prove parity and explicit differences before any selection behavior changes.
2. Change only document-inventory overflow semantics: when the cumulative `75 000` cap is crossed, return the already completed bounded page prefix as an explicit partial layout result, with the exact overflow reason and missing-tail accounting, instead of returning terminal `pages=[]`.

Do not in this slice:

- change row, column, density, height, area or confidence thresholds;
- raise `75 000`;
- add VLM/provider/parser/solver;
- add empty-password support;
- claim full-document detection for IBKR;
- auto-select newly visible candidates into a certifying holdout.

Why this slice is first:

- it repairs the semantic cause shared by two of the three zero-candidate PDFs;
- it makes `partial detector evidence` distinguishable from `no table`;
- it exposes early real IBKR statement candidates without increasing the work budget;
- it is independently testable and leaves later page/chunk completeness as an explicit limitation;
- it prevents future detector fixes from being confused with holdout selection changes.

Required proof for that implementation slice:

- synthetic overflow test preserves only fully completed pre-cap pages, candidates, checksums and provenance;
- tail pages are explicitly `not_processed_budget`, never presented as table-free;
- parser stops at the same cap and performs no provider calls;
- both IBKR PDFs become non-zero development regressions from their early pages;
- Wealthfront remains an explicit upstream encryption result, not `no candidates`;
- no candidate becomes holdout-selected merely because it is processable;
- full existing repository tests pass.

Preserving the prefix is intentionally incomplete: later IBKR tables remain unreachable. Full bounded page/chunk processing and empty-password handling require their own evidence and later slices. This limitation is preferable to hiding missing pages or silently increasing resource use.

## Definition of the next genuinely unseen holdout

The current seven PDFs and every derived crop/classification are permanently development-only.

A next unseen holdout must satisfy all of these before content review or provider execution:

1. Source acquisition rule, date window and public-document class are written first.
2. PDF bytes, SHA-256, size, source URL and acquisition time are frozen before parser/VLM inspection.
3. Every SHA is disjoint from all prior corpora, reports, local experiments and provider runs.
4. Code, detector policy, processability contract, selection policy and model profile are frozen before target discovery.
5. Selection operates across the frozen corpus; it does not require three targets from one document.
6. Required diversity is predeclared as holdout policy, for example ruled, borderless/aligned and sparse/separator structures. If the corpus cannot supply it, the run terminates insufficient; no post-freeze substitution.
7. TOC/prose negatives and zero-candidate documents are scored in detection evaluation, not smuggled into table reconstruction accuracy.
8. Human/reference structure remains sealed until all attempts reach a terminal result.
9. Selection reads no source/reference values and no prior provider output.
10. Accuracy claims require persisted preregistration, attempt journal, exact provider usage and terminal scoring artifacts.

## Code evidence pointers

- Eligibility policy and thresholds: `pdf_structural_repair_holdout_contracts.py:204-247`.
- Raw eligibility observations: `pdf_structural_repair_holdout_contracts.py:691-780`.
- Rule evaluation: `pdf_structural_repair_holdout_contracts.py:2604-2688`.
- Common eligibility filter before selection: `local_pdf_structural_repair_holdout.py:404-435`.
- v5 same-document/strategy selection: `local_pdf_structural_repair_holdout.py:886-968`.
- Fixed parser strategy confidence: `pdf_layout.py:373-463`.
- `75 000` inventory cap and terminal transition: `pdf_layout.py:21-42, 144-165`.
- Terminal erases pages: `pdf_layout.py:498-527`.
- Unconditional encrypted flag block: `pdf_text_layer.py:221-240`.
- Visual hard limits: `pdf_visual_topology.py:125-135`.
- Atom/window limits: `pdf_structural_row_windows.py:94-100, 157-180`.
- Raster hard limits: `pdf_table_raster.py:25-32, 68-99`.
- Runtime token/image/response and retry guards: `pdf_structural_repair_runtime.py:203-212, 317-325`.

## Final status

The separation below is contract-level audit readiness. Production runtime still has the legacy mixed `eligible` path because this task intentionally made no runtime changes.

`BROKER_REPORTS_PDF_INTAKE_FILTER_AUDIT_READY`

`BROKER_REPORTS_PDF_INTAKE_FALSE_REJECTIONS_PROVEN`

`BROKER_REPORTS_PDF_ZERO_CANDIDATE_CAUSES_PROVEN`

`BROKER_REPORTS_PDF_INTAKE_DECISIONS_SEPARATED`

`BROKER_REPORTS_PDF_MINIMAL_INTAKE_CONTRACT_READY`

`BROKER_REPORTS_PDF_NEXT_INTAKE_SLICE_READY`
