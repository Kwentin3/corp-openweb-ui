# Broker Reports: Real Table CSV vs JSON Hybrid Experiment

Дата: 2026-07-13

Режим: controlled private research, без production Gate 2 changes
Итог: CSV не доказан как замена current candidate-bound JSON; free CSV полезен как non-authoritative challenge path

## Вердикт

Ни один CSV-arm не улучшил одновременно format reliability, placement, empties, continuation и provenance по сравнению с current JSON control.

- Current JSON: 2/6 `accepted_shadow`, 0/12 malformed primary packages, 270/270 numeric-like reference cells.
- Free CSV: 3/6 byte-complete diagnostic grids, но нет source binding и 3/6 malformed primary outputs.
- Candidate-id CSV: 2/6 `accepted_shadow`, 9/12 strict-valid primary packages, но 3/12 malformed packages и те же structural blocks на continuation.
- Candidate-id CSV + topology: 0/6 complete table artifacts, 4/12 strict-valid primary packages; sidecar добавил ошибки, а не надёжность.

Candidate CSV действительно сократил provider output: на 80.10% по tokens и на 91.45% по visible bytes. Но candidate input остался тот же, prompt вырос на 1.25%, а accepted-table count не изменился. Это output compression, а не reliability improvement.

Рекомендация: оставить current candidate-bound JSON как основной hybrid output contract. Free CSV сохранить только как challenge/auditor path без authority. Production-refactor на CSV не обоснован. Ещё один узкий research-only тест допустим только для candidate CSV без sidecar, если output cost станет отдельным приоритетом.

## CSV dialect и fail-closed parser

Введён `broker_reports_real_table_csv_dialect_v1`:

- UTF-8 without BOM;
- delimiter `,`;
- quote `"`, escape `""`;
- только LF; literal line break только в quoted field;
- zero-byte field означает explicit empty cell;
- fixed row width и exact expected row count;
- в candidate mode поле содержит один lowercase base36 id или ids через `+` в source order;
- terminal: provider `STOP` плюс byte-complete strict parse;
- Markdown fences, BOM, CRLF, blank extra row, trailing commentary и silent repair запрещены.

Parser fail-closed проверяет malformed quoting, wrong delimiter через fixed-width mismatch, row/column mismatch, unknown ids, duplicate ownership, incomplete ownership, duplicate ids inside one cell, source-order violations и incomplete output. Он не подбирает delimiter и не пересобирает строки.

Candidate resolver пропускает CSV через тот же current binding contract. Каждый id обратимо связан с exact private value, `source_value_ref[]`, `word_ref[]`, bbox и checksum; free financial values в candidate arms не допускаются.

## Compact topology sidecar

Version: `broker_reports_real_table_csv_topology_sidecar_v1`.

Envelope:

```text
CSV/1
<raw CSV>
SIDECAR/1
<one-line compact JSON>
END/1
```

Ключи sidecar: version, decision, rows, columns, header count, merged ranges, header relations, continuation identity, optional normalized row/column boundaries и uncertainty codes. Maximum size: 4,096 bytes. Full grid, candidate dictionary, source values, refs и repeated candidates запрещены рекурсивно.

Sidecar проходит независимую shape/range/hierarchy/boundary/continuation validation. Даже valid sidecar не доказывает placement: current coordinate validator отдельно сверяет candidate positions.

В live-run принятые sidecars заняли 167–168 bytes, 670 bytes всего на четырёх strict-valid primary windows. Однако ни одна таблица не собрала полный valid package set.

## Real-table corpus

Один одобренный six-page PDF, SHA-256 `79af73d5be78df446f768f516ed6eaebd5a9d4bfc6f98c98a4a53a5b5131f37d`.

Reference остаётся provisional: `agent_visual_reviewed_pending_human_signoff`. Все accuracy ниже — controlled diagnostic, а не authoritative customer truth.

| Table | Case | Parser shape | Reference shape | Candidates | Windows |
|---|---|---:|---:|---:|---:|
| 1:2 | deterministic simple control | 10x3 | 10x3 | 30 | 1 |
| 1:3 | wide multi-row header | 20x18 | 8x18 | 241 | 2 |
| 3:2 | wide multiline header, continuation fragment 1 | 48x16 | 12x16 | 708 | 4 |
| 4:1 | cross-page continuation fragment 2 | 25x16 | 10x16 | 343 | 3 |
| 4:2 | grouped/merged header | 7x11 | 7x11 | 35 | 1 |
| 5:3 | tax/summary | 5x8 | 5x8 | 24 | 1 |

Для A/C/D использованы одинаковые 12 window crops, 688,319 bytes, 150 DPI, width 422–1,899 px, height 146–310 px. Free CSV получил шесть full-table crops, 682,877 bytes, 150 DPI, width 422–1,899 px, height 146–1,193 px.

## Context, tokens и serialization

Primary attempts only. Sidecar/schema bytes для D — только independently accepted sidecars; malformed sidecars не считаются valid metadata.

| Arm | Prompt B | Candidate B | Schema/sidecar B | Visible output B | Input tokens | Output tokens | Amplification | Max CSV row B |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| A JSON | 82,505 | 69,018 | 25,527 | 49,689 | 75,010 | 18,830 | 19.495510x | n/a |
| B free CSV | 3,744 | 0 | 0 | 15,471 | 7,235 | 9,303 | 0.884688x | 351 |
| C candidate CSV | 83,539 | 69,018 | 0 | 4,248 | 73,230 | 3,747 | 19.739839x | 48 |
| D candidate CSV + topology | 89,220 | 69,018 | 670 | 7,332 | 75,313 | 5,214 | 21.082231x | 46 |

Относительно JSON:

- B: prompt -95.46%, input tokens -90.35%, output tokens -50.59%, output bytes -68.86%; ценой потери provenance и 3/6 malformed outputs.
- C: prompt +1.25%, input tokens -2.37%, output tokens -80.10%, output bytes -91.45%; input complexity не исчезла.
- D: prompt +8.14%, input tokens +0.40%, output tokens -72.31%, output bytes -85.24%; sidecar перенёс сложность в prompt и validation.

Таким образом, candidate CSV компактнее только на output leg. Он не уменьшает candidate context и не снижает amplification.

## Aggregate accuracy against provisional reference

Знаменатели различаютс, потому что shape mismatch расширяет position-sensitive comparison. Проценты нельзя читать без exact counts.

| Arm | Accepted/parsed tables | Exact cells | Numeric-like | Exact empties | Exact structures | Headers exact | Malformed primary outputs |
|---|---:|---:|---:|---:|---:|---:|---:|
| A JSON | 2/6 | 813/1,675 | 270/270 | 293/1,154 | 3/6 | 6/6 | 0/12 |
| B free CSV | 3/6 diagnostic | 387/1,219 | 107/270 | 158/698 | 2/6 vs reference | 2/6 | 3/6 |
| C candidate CSV | 2/6 | 577/1,459 | 175/270 | 205/938 | 2/6 | 4/6 | 3/12 |
| D CSV + topology | 0/6 | 122/643 | 0/270 | 122/122 | 0/6 | 0/6 | 8/12 |

## Per-table result

Формат score: `exact cells; numeric-like; empties` against provisional reference. `H` означает exact header projection.

| Table | A JSON | B free CSV | C candidate CSV | D CSV + topology |
|---|---|---|---|---|
| 1:2 | accepted; `30/30; 11/11; 0/0`; H | parsed; `30/30; 11/11; 0/0`; H | accepted; `30/30; 11/11; 0/0`; H | fail: candidate-cell grammar; `0/30; 0/11; 0/0` |
| 1:3 | structural block; `233/360; 78/78; 119/246`; H | fail: width; `30/144; 0/78; 30/30` | fail: width; `30/144; 0/78; 30/30` | fail: width/range; `30/144; 0/78; 30/30` |
| 3:2 | structural/continuation block; `228/768; 79/79; 60/600`; H | parsed diagnostic; `225/768; 79/79; 60/600` | structural block; `228/768; 79/79; 60/600`; H | fail: width/range; `24/192; 0/79; 24/24` |
| 4:1 | structural block; `207/400; 70/70; 57/250`; H | fail: width; `10/160; 0/70; 10/10` | structural block; `207/400; 70/70; 57/250`; H | fail: range; `10/160; 0/70; 10/10` |
| 4:2 | structural/merged block; `75/77; 17/17; 41/42`; H | parsed diagnostic; `76/77; 17/17; 42/42`; H | fail: width; `42/77; 0/17; 42/42` | fail: width; `42/77; 0/17; 42/42` |
| 5:3 | accepted; `40/40; 15/15; 16/16`; H | fail: width; `16/40; 0/15; 16/16` | accepted; `40/40; 15/15; 16/16`; H | fail: width; `16/40; 0/15; 16/16` |

## Independent parser comparison

Free CSV дал два сильных и один частичный challenge signal:

- 1:2: 30/30 parser cells, 11/11 numeric, exact shape;
- 3:2: 765/768 parser cells, 331/331 numeric, 60/60 empties, exact parser shape 48x16; повтор дал тот же parsed grid hash;
- 4:2: 66/77 parser cells, 13/17 numeric, 37/42 empties, но 76/77 against visual reference. Пять видимых reference values не совпали с text-layer placement.

Это здравое зерно гипотезы: free visual CSV может независимо подтвердить parser geometry или выявить text-layer gap. Но он нестабилен на wide/tax formats и не имеет source refs.

Candidate CSV прошёл exact candidate ownership на 1:2, 3:2, 4:1 и 5:3. Сравнение с parser:

- 1:2: 30/30 cells;
- 3:2: 624/768 cells, 247/331 numeric, 48/60 empties; 132 existing values попали не в ту position;
- 4:1: 384/400 cells, 154/162 numeric, 49/57 empties; 8 existing values попали не в ту position;
- 5:3: 40/40 cells.

Совпадение числа в другой ячейке не засчитывалось. В 3:2 и 4:1 были 465 и 221 duplicate-value ambiguity positions; comparison остался position-sensitive.

## Provenance, empties и invented values

- A остаётся control: all current packages прошли schema parsing, candidate/source binding не ослаблялся.
- B имеет provenance coverage 0 по определению. Его values не могут стать source facts.
- C даёт complete reversible Level 4 binding, когда все packages таблицы parse-valid. Это доказано для 4/6 tables, но structural acceptance получили только 2/6.
- D не собрал complete binding ни для одной таблицы.

Accepted candidate-bound artifacts содержат zero invented values. Ошибки C в 3:2 и 4:1 — это wrong-cell placement existing candidates, а не generated financial values. Current validators их заблокировали по `candidate_column_incompatible`, `candidate_column_mismatch` и `empty_cell_position_mismatch`.

CSV не улучшил corpus-wide preservation empties: A 293/1,154, C 205/938, D не дошёл до non-empty grid comparison. Free CSV был exact по parser empties на 3:2, но не выдержал rectangular width на трёх других tables.

## Continuation и merged headers

Continuation 3:2 + 4:1 проверялась как два separate fragments и как одна ordered logical group с 16 columns.

- A: 1,051/1,051 candidates и 1,213/1,213 unique word refs, но group blocked на fragment placement.
- B: fragment 3:2 exact parser shape и repeatable; 4:1 malformed по width, поэтому logical join fail-closed.
- C: 1,051/1,051 candidates, 73 source rows, complete ordered coverage; both fragments blocked independent placement validator.
- D: incomplete package coverage, 0 candidates допущено до logical join.

Grouped/merged 4:2 не дал accepted merged-header topology ни в одном arm. Free CSV был ближе всех к visual reference (76/77), но CSV не выражает merge semantics. C и D не прошли width; A остался blocked на structural merged relation. Merged-header acceptance: 0/1.

## Repeatability

Два identical attempts выполнены для simple 1:2, wide 1:3, continuation fragments 3:2/4:1 и grouped 4:2. Хеши записаны раздельно.

| Arm | Parsed/materialized pairs that matched | Unassessed because one/both outputs failed | Raw hashes |
|---|---|---|---|
| A JSON | 1:2, 3:2 placement | 1:3, 4:1, 4:2 не имели complete repeat proof в control evidence | not used as equality substitute |
| B free CSV | 1:2, 3:2, 4:2 grid | 1:3, 4:1 | differed for every pair |
| C candidate CSV | 1:2 and blocked 4:1 grid/placement | 1:3, 3:2, 4:2 | differed for every pair |
| D CSV + topology | none at whole-table level | all five repeated tables | differed for every pair |

Different raw hashes при identical parsed hashes показывают, что stable parsed result не сводится к байтовому совпадению provider response. На wide/topology corpus repeatability не доказана: malformed pair не засчитывается как stable.

Monotonic conflict contract проверен отдельно: после sequence `a,b,a` состояние остаётся `ever_conflicted`; позднее совпадение не снимает конфликт. В final valid pairs real conflict не наблюдался; failed pairs остались unassessed.

## Safe structural failure examples

Без customer values и raw crops:

- free 1:3: 20 rows, row widths 18/19/20 -> `pdf_csv_column_count_mismatch`;
- free 4:1: 25 rows, row widths 16/17/18 -> `pdf_csv_column_count_mismatch`;
- free 5:3: five rows, widths 8/9 -> `pdf_csv_column_count_mismatch`;
- candidate 1:3: package widths 18/20 и 19/22 -> `pdf_csv_column_count_mismatch`;
- topology 1:2 -> `pdf_csv_candidate_cell_grammar_invalid`;
- topology wide/continuation windows -> `pdf_csv_topology_merged_range_out_of_bounds`;
- candidate continuation after complete binding -> `pdf_hybrid_structure_candidate_column_incompatible`, `pdf_hybrid_structure_candidate_column_mismatch`, `pdf_hybrid_structure_empty_cell_position_mismatch`;
- logical continuation -> `pdf_hybrid_continuation_fragment_placement_blocked`.

Все 57 CSV provider attempts завершились HTTP/transport success и `STOP`. CountTokens и actual input совпали во всех 57 attempts, maximum error 0.0%. Поэтому malformed terminals — это format/structure failures, а не transport noise.

## Implementation complexity

Research-only footprint:

- strict CSV/topology/comparison core: 743 physical lines;
- isolated provider adapter: 387 physical lines;
- self-contained resumable controlled harness and evidence accounting: 2,137 physical lines;
- contract/provider tests: 309 physical lines, 8 focused test methods.

Эти числа включают research instrumentation и не предлагаются к production merge. Однако они показывают, что CSV не устраняет domain complexity: candidate resolver, provenance ledger, placement, continuation, topology и repeatability всё равно остаются. D добавляет envelope и topology parser поверх CSV parser.

## Ответы на ключевые вопросы

1. CSV материально надёжнее JSON? Нет. C дал тот же 2/6 accepted tables и добавил 3 malformed packages; D снизился до 0/6.
2. Есть ли serialization improvement? Да, на output leg C. Эффект не похож на один lucky response, потому что simple и 4:1 parsed/materialized hashes повторились при разных raw hashes. Corpus-wide reliability при этом не улучшилась.
3. Free CSV полезен против parser? Да, как challenge signal: особенно 3:2 и 4:2. Нет, как authority.
4. Candidate CSV сохраняет Level 4 provenance? Да на complete parse-valid tables; нет на всём corpus и не без structural gate.
5. Sidecar улучшил wide/merged/continuation? Нет. 0/6 full tables, больше prompt, новые range/grammar failures.
6. Что осталось? Reading errors в free 4:2; row/column и empty placement в C; malformed width в B/C/D; topology ranges в D; fragment placement в continuation; merged semantics не доказана.
7. Целевой contract: current JSON only для candidate-bound authority; free CSV только challenge path. CSV-only и CSV+sidecar отвергаются.

## Safety, evidence и regression boundary

- experiment jobs: 59/59 terminal;
- focused CSV/Goal 3 contracts: 18 passed;
- full service suite: 319 passed, 5 external PyMuPDF SWIG deprecation warnings;
- isolated CLI import check: `python -I ... --help` passed;
- CSV provider attempts: 57 unique job keys; B 11, C 23, D 23;
- JSON simple control: 2 explicit attempts;
- hidden retry: 0;
- provider failover: 0;
- final evidence re-summary: `journal_only_no_provider_calls`;
- production PDF pipeline changes: 0;
- production Gate 2 selection changes: 0;
- OCR, whole-PDF provider extraction, Knowledge/RAG/vector, OpenWebUI core patch: 0;
- safe evidence/report contain no customer values, raw responses or raw crops.

Controlled evidence:

- safe summary: `local/stage2/broker_reports_pdf_csv_vs_json_2026-07-13-live1/experiment.safe.json`;
- safe summary SHA-256: `27368196EC21F7E3DFBC784DD9D3F6E8F09FBA3C827E0F2D5CF2F056328C0C86`;
- private journal SHA-256: `89341BABC725E34210A8A603C22415799D02FFFD6A6D7642471E4CA3C09B78E6`;
- JSON control evidence: `local/stage2/broker_reports_pdf_hybrid_reliability_2026-07-13-live3/evidence.safe.json`;
- JSON control evidence SHA-256: `C269AFB65AF764070831157C318D83D5CABA99C765B2B7E7040F09FF670C6F74`;
- Gate 2 source-fact bundle SHA-256: `9E7E3FA0BE71C912FC4DE2B69D1B3447E90012B9FB89894E143C8A5EB8300F81`;
- Gate 2 domain bundle SHA-256: `220BA58A59F33CA2F536D3A61B6959662A5F12E88640236438DEAC5A9523C454`.

Сложные JSON-control tables были взяты из prior controlled live3 с теми же model/config/packages; simple control запущен в этом experiment. Это сохраняет input parity, но не является simultaneous wall-clock A/B test; выводы поэтому консервативны.

## Final statuses

```text
BROKER_REPORTS_REAL_TABLE_CSV_DIALECT_READY
BROKER_REPORTS_REAL_TABLE_CSV_PARSER_READY
BROKER_REPORTS_VLM_FREE_CSV_ARM_COMPLETED
BROKER_REPORTS_VLM_CANDIDATE_CSV_ARM_COMPLETED
BROKER_REPORTS_VLM_CSV_TOPOLOGY_SIDECAR_ARM_COMPLETED
BROKER_REPORTS_CSV_VS_JSON_CONTEXT_COMPARED
BROKER_REPORTS_CSV_VS_JSON_TABLE_ACCURACY_COMPARED
BROKER_REPORTS_CSV_PROVENANCE_ASSESSED
BROKER_REPORTS_CSV_REPEATABILITY_ASSESSED
BROKER_REPORTS_CSV_TARGET_CONTRACT_RECOMMENDATION_READY
```

Эти statuses означают completed research contracts и assessment. Они не означают production readiness CSV и не разрешают Gate 2 integration.
