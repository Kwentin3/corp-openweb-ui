# G5.80 — Atomic Source Facts & Development Visual Qualification

Дата: 2026-08-16
Статус: `PARTIAL — DOWNSTREAM_REPLAY_INCOMPLETE`

## Итог

Структурная причина шести инцидентных страниц локализована и устранена одним
broker-neutral условием в существующем table projection owner. Atomic Gate 4
boundary закреплён: coarse region без однозначной source assertion больше не
может стать transaction fact. Все 12 прежних broad annotations блокируются;
exact incomplete G579-08 остаётся допустимым по контракту.

Обычный двухфазный Gate 3 replay завершился terminal результатом, но весь
документ не прошёл fail-closed validation: `135/140` chunks validated, `5`
отклонены на role-binding стадии. Все шесть исправленных страниц validated;
rejections относятся к другим страницам. Поскольку result incomplete,
`FinancialAnnotationsV2` не опубликован и Gate 4 не перестроен. Поэтому
`CURRENT_CASE_SOURCE_FACTS_REQUALIFIED` честно не заявляется.

## Development visual qualification

Правило встроено в текущий короткий architecture authority: исходный PDF можно
открывать глазами только как development/test oracle для поиска первого
расхождения. Визуальное наблюдение нельзя копировать в production facts;
после исправления owner требуется обычный machine replay.

Production visual dependency: `0`.

## Шесть страниц и первая дивергенция

Все страницы проверены по исходным full-page images и crops. Визуальная
структура — таблицы с отдельными records и с одной или несколькими
одноклеточными структурными строками (title/continuation/subtotal).

| Страница | Визуальная структура | Старый Canonical | Canonical после общего fix |
| ---: | --- | --- | --- |
| 16 | title + 40 record rows | coarse `TEXT` | `TABLE`, 42 rows |
| 19 | merged continuation/title + 44 record rows | coarse `TEXT` | `TABLE`, 45 rows |
| 24 | title + 33 record rows | coarse `TEXT` | `TABLE`, 34 rows |
| 25 | 36 record/subtotal rows | coarse `TEXT` | `TABLE`, 36 rows |
| 26 | title + 35 record rows | coarse `TEXT` | `TABLE`, 36 rows |
| 27 | primary 28 rows + second 8-row table | coarse `TEXT` | two `TABLE` nodes: 28 + 8 rows |

`FIRST DIVERGENCE` одинаков для всех шести страниц:

```text
NormalizedTableProjectionFactory.create
-> pdf_table_geometry_column_structure_insufficient
-> rejected_to_line_cluster
-> coarse TEXT in Canonical
```

Candidate inventory уже содержал multi-column rows, но прежняя проверка
требовала минимум две cells **в каждой** строке. Одна merged/title row с одной
cell отбрасывала всю таблицу. Минимальный общий критерий проверяет, что хотя бы
одна строка multi-column (`min(row_cell_counts)` ->
`max(row_cell_counts)`). Это structure-only fix: названий брокера, страниц,
координат, финансовых labels и нового framework нет.

После re-normalization шесть страниц получили отдельные table rows; полный
Canonical имеет `16,538` cells и `2,456` rows, lost/duplicate source refs =
`0/0`. Visual observations не входили в Canonical или facts.

## Presence не является atomic fact

Минимальный admission guard использует только существующую Canonical
структуру:

- `table_row`, `table_cell`, `list_item` — атомарно адресуемы;
- однострочный `node` — атомарно адресуем;
- многострочный `node` допускается только для assertion с bound `exact_text`,
  который встречается в разрешённом Canonical target ровно один раз;
- repeated или отсутствующий literal anchor оставляет annotation в статусе
  `non_atomic_region_presence_only`.

Это уточнение важно: target kind сам по себе не доказывает и не опровергает
atomicity. Legacy facts с единственным точным literal anchor сохраняются, а
многооперационная page projection без уникального anchor — нет.

Квалификация frozen G5.79 incidents:

| Показатель | Результат |
| --- | ---: |
| broad annotations | 12 |
| `SECURITY_PURCHASE` | 6 |
| `SECURITY_DISPOSAL` | 6 |
| страниц | 6 |
| annotations на страницу | 2 |
| structurally atomic | 0 |
| materializable новым guard | 0 |

На frozen baseline из `391` Gate 4 facts новый общий критерий квалифицирует
`333` как materializable (`286` structural targets + `47` unique literal
anchors) и `58` как non-atomic presence-only. В эти `58` входят все 12 broad
G5.79 incidents. Это admission-аудит старого evidence set, а не новый current
Gate 4 result.

`G579-08` остаётся negative control: exact `table_cell`, row `5`, column `4`.
Он допускается как atomic source assertion, а отсутствующие `amount/currency`
остаются `missing`; соседние строки и блоки не используются.

## Gate 2 proof

- active repaired Canonical:
  `canver_lvs64r6lTXf56n30XPIfbV0FRxwVW1lE`;
- normalization run: `normrun_1f4f2d9e30c1a076`;
- six coarse pages before -> six structured pages after;
- provider calls `0`, manual financial facts `0`, broker rules `0`;
- proof выполнен на изолированной копии store; product capacity defaults не
  менялись.

Safe receipt:
[Gate 2 addressability](./BROKER_REPORTS_ATOMIC_SOURCE_FACTS_G5_80.gate2.safe.json).

## Downstream replay

Frozen shape: `140` chunks, `19,060` exact targets, lost/duplicate targets
`0/0`. Использован существующий
`Gate3ChunkBatchLabelingFactory -> Gate3FinancialAnnotationsPersistenceFactory
-> Gate4FinancialCaseRuntimeFactory` path.

После двух pre-result диагностических запусков без batch output выполнен один
полный frozen replay. Первые два результата не использовались и не участвовали
в выборе ответа. Полный запуск вернул:

- `188/188` provider submissions returned при ceiling `280`;
- `retry/repair/fallback/manual facts = 0/0/0/0`;
- `140` chunks: `135` validated, `5` rejected, provider failed `0`;
- `1,316` annotations validated внутри batch;
- terminal: `DOWNSTREAM_REPLAY_INCOMPLETE`.

Все исправленные страницы прошли обе стадии:

| Страница | Chunk ordinals | Validated annotations | Статус |
| ---: | --- | ---: | --- |
| 16 | 34, 35 | 40 | validated |
| 19 | 40, 41 | 43 | validated |
| 24 | 52, 53 | 22 | validated |
| 25 | 54, 55 | 19 | validated |
| 26 | 56, 57 | 38 | validated |
| 27 | 58, 59, 60 | 28 | validated |

Пять fail-closed rejections находятся вне исправленных страниц:

| Chunk | Страница | Phase | Validator code |
| ---: | ---: | --- | --- |
| 10 | 4 | role labeling | `gate3_role_target_outside_fact_context` |
| 12 | 5 | role labeling | `gate3_role_exact_text_not_literal_substring` |
| 42 | 20 | role labeling | `gate3_role_exact_text_not_literal_substring` |
| 44 | 21 | role labeling | `gate3_role_exact_text_not_literal_substring` |
| 76 | 35 | role labeling | `gate3_role_target_text_ambiguous` |

Exact-output audit подтвердил, что все пять отказов правильны:

- chunk 10: роль сослалась на alias другой строки;
- chunk 12: `currency` сослалась на date-cell;
- chunks 42 и 44: `amount` сослался на description-cell;
- chunk 76: `date` сослалась на многозначную table row без exact literal.

Это новый downstream bottleneck: single-shot role-binding reliability на уже
адресуемом Canonical. Gate 2 defect и validator defect для этих пяти случаев
исключены. Обход, частичная sidecar publication, prompt fitting и повторный
replay не выполнялись. Без complete sidecar нельзя честно посчитать новую Gate
4 fact delta или runtime-проверить G579-08 и три decimal controls на current
version.

Safe receipts:
[terminal replay](./BROKER_REPORTS_ATOMIC_SOURCE_FACTS_G5_80.replay.attempt3.safe.json),
[rejection diagnostic](./BROKER_REPORTS_ATOMIC_SOURCE_FACTS_G5_80.replay_diagnostic.safe.json).

## Holdouts

Изменённый admission seam проверен на exact frozen sidecars:

- Holdout A: `39/39` annotations допускаются, blocked `0`;
- Holdout B: `129/129` annotations допускаются, blocked `0`;
- source stores byte-identical.

Полный свежий rebuild этих двух frozen fixtures не заявлен: их artifact TTL
истёк, и current lifecycle owner корректно возвращает stale/incomplete. Проверен
ровно изменённый pure admission seam; frozen fact hashes не переобъявлялись как
новый runtime result.

Safe receipt:
[holdout admission canary](./BROKER_REPORTS_ATOMIC_SOURCE_FACTS_G5_80.holdouts.safe.json).

## Guards и проверки

- focused architecture/runtime suite: `155 passed`;
- Ruff на изменённых owners, harnesses и guards: passed;
- generated Gate 1 bundle пересобран существующим builder;
- cold-agent exam: `PASS/PASS` — сначала original source -> Canonical -> first
  divergence; visual reading никогда не переносится в production facts;
- false user requests `0`;
- manual facts `0`;
- inferred purchase/sale relations `0`;
- decimal normalization, methodology, metadata/VLM product path: не менялись;
- dirty tree сохранён, stage/commit/reset/cleanup не выполнялись.

## Finish Contract audit

| # | Требование | Статус | Evidence / предел |
| ---: | --- | --- | --- |
| 1 | Dev-only visual rule | proven | current pipeline authority |
| 2 | Production visual dependency = 0 | proven | Gate 2/replay receipts |
| 3 | Six pages visually qualified | proven | raw full pages/crops + таблица выше |
| 4 | 12 broad annotations non-atomic | proven | frozen baseline admission audit |
| 5 | Atomic Gate 4 evidence | proven | Gate 3/Gate 4 contracts + guard tests |
| 6 | Presence cannot silently materialize | proven | `non_atomic_region_presence_only` |
| 7 | G579-08 legitimate incomplete | partial | contract/guard proven; current-version runtime replay unavailable without complete sidecar |
| 8 | First divergence localized | proven | common Gate 2 table acceptance decision |
| 9 | Minimal broker-neutral fix | proven | one structure-only acceptance condition |
| 10 | Strategic stop if large fix required | not triggered | local fix was sufficient |
| 11 | Manual operations = 0 | proven | receipts |
| 12 | Canonical visually rechecked | proven | row accounting above |
| 13 | Ordinary Gate 3/Gate 4 path | partial | ordinary Gate 3 ran; Gate 4 correctly did not run on incomplete result |
| 14 | Broker hacks = 0 | proven | source/code audit |
| 15 | Inferred relations = 0 | proven | source/code audit |
| 16 | Fact-count delta fully explained | not proven | no current Gate 4 fact set was legally publishable |
| 17 | No artificial 391 preservation | proven | `333/58` baseline qualification |
| 18 | False user requests = 0 | proven | no user-facing action path changed |
| 19 | Decimal behavior unchanged by G5.80 | proven | changed-owner audit |
| 20 | Methodology unchanged | proven | changed-owner audit |
| 21 | Metadata unchanged | proven | changed-owner audit |
| 22 | Dirty tree preserved | proven | no stage/commit/reset/cleanup |
| 23 | Cold-agent dev-oracle boundary | proven | `PASS/PASS` |
| 24 | Next bottleneck from replay | proven | five exact role-binding rejections |

G5.80 нельзя закрыть по пунктам 7, 13 и 16. Текущие Gate 3 contracts прямо
требуют complete-proposal rejection и запрещают response repair/retry; batch
contract прямо делает весь document result `incomplete` при одном rejected
chunk. Поэтому публикация частичной sidecar была бы нарушением authority, а не
KISS-завершением.

## KISS и terminal

Новый parser, VLM fallback, ontology, relation graph и recovery framework не
создавались. Реализация ограничена одним общим table acceptance condition,
одним structural addressability predicate и одним Gate 4 admission decision.

Доказано:

```text
DEVELOPMENT_VISUAL_QUALIFICATION_PATTERN_FROZEN
ATOMIC_SOURCE_EVIDENCE_BOUNDARY_PROVEN
NON_ATOMIC_PSEUDO_FACT_MATERIALIZATION_BLOCKED
GATE2_ROW_ADDRESSABILITY_REPAIRED
VISUAL_SOURCE_TO_CANONICAL_STRUCTURE_PROVEN
PRODUCTION_VISUAL_DEPENDENCY_ZERO
READY_FOR_DOWNSTREAM_REPLAY
```

Не заявлено из-за пяти корректно отклонённых role-binding outputs:

```text
CURRENT_CASE_SOURCE_FACTS_REQUALIFIED
```

Следующий bottleneck определён фактическим replay:
`GATE3_ROLE_BINDING_SINGLE_SHOT_RELIABILITY`. Exact-output audit уже объяснил
пять rejection как ошибки LLM role bindings. Дальнейший выбор — сохранить
whole-chunk rejection либо перейти к формально определённому per-role
fail-closed outcome — меняет validation contract и требует отдельного узкого
GOAL. Weakening validation, best-of-N, retry и broker-specific rules в G5.80
не допускаются. До этого нельзя считать G5.80 полностью закрытым или
переходить к decimal fix.

Private evidence bundle сохранён вне Git; safe report не публикует его host path.
