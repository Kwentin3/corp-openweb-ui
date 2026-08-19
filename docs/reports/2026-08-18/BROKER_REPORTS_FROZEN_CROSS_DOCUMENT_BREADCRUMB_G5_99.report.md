# Broker Reports G5.99 — Frozen Cross-Document Breadcrumb Qualification

Дата: 2026-08-18

Статус: qualification-only, Gate 2

Terminals:

```text
FALSE_LOCALIZATION_PROVEN
BREADCRUMB_CONTRACT_NOT_GENERAL
```

## Вывод

Frozen G5.98 не перенёсся на новый cross-document corpus.

VLM визуально предложила ровно `9` таблиц на страницах, где visual referee подтвердил `9` таблиц, и не предложила ни одной таблицы на `5` negative pages. Но addressability bridge провалился: из `7` schema-valid table contracts resolver вернул `4 RESOLVED`, и все четыре source regions были неправильными. Ещё `3` завершились `NOT_FOUND`. Одна positive page с двумя таблицами целиком отклонена как contract-invalid.

Итог:

```text
REAL VISUAL TABLES                  9
CORRECT UNIQUE RESOLUTION          0
AMBIGUOUS                          0
NOT_FOUND                          3
CONTRACT_NOT_VERIFIED PAGES        1
FALSE LOCALIZATION                 4
FALSE TABLE ADMITTED               0
MISSED VISUAL TABLE                9
```

Это отрицательный результат, а не safe partial: ключевой инвариант `FALSE_LOCALIZATION = 0` нарушен. При этом visual detection и negative control precision были хорошими; сломался именно переход `visual breadcrumb → exact source region`.

`BREADCRUMB_CONTRACT_NOT_GENERAL` относится только к неизменённым semantics G5.98 на этом frozen corpus. G5.99 не доказывает, что любой будущий addressability contract невозможен, и не разрешает автоматически расширять текущий.

## Scope и frozen invariants

G5.99 не добавил implementation code и не менял G5.98:

- implementation SHA-256: `be83b01d7d32965c34d0f30029bee73bce1ec68f4965c2c7473c6e348cdffeaf`;
- prompt SHA-256: `a7030b9a6b07c094a2271ca71dc81b71f7ab0a5bd09d18b377cbc440688b39e4`;
- response schema SHA-256: `b5234742ef277c2707ec4fa13c0b7321a843f7d1abfabf1b459590c51060a406`;
- model: frozen `models/gemini-3.5-flash`;
- fields: `before_anchor`, `header_token_groups`, `after_anchor`, `table_ordinal_in_scope`, `continuation_from_previous_page`;
- normalization, matching, ordinal semantics и resolver code unchanged;
- bbox, body values, financial meaning, vendor settings и fuzzy ranking по-прежнему отсутствуют.

Qualification reuse выполнялся существующим G5.98 one-shot harness. Новый receipt только связал новый corpus manifest с прежними frozen hashes; он не создал вторую schema/resolver authority.

## Corpus freeze

Manifest SHA-256: `b7c2ebb8104c05b37031e6d2d06ba2a5dd741eb4b72220ddf036638260de4eaa`.

Corpus выбран до render review, provider execution, predictions и visual truth. Selection inputs были ограничены:

- PDF hash/bytes/page count;
- current `PdfTextLayerParserFactory.create` line/word/table-candidate counts;
- никаких page text literals, image content, provider output или resolver output.

Page PNG сгенерированы существующим `PdfTableRasterFactory.create` при `150 dpi`, но не открывались до завершения frozen execution.

| Measure | Value |
|---|---:|
| New document hashes | 4 |
| Frozen pages | 9 |
| Parser-positive candidate pages selected | 6 |
| Parser-zero-candidate controls selected | 3 |
| Old G5.98 development/holdout pages reused | 0 |
| G5.97 p029 reused | no |

После visual adjudication две parser-positive страницы оказались prose/list negatives. Они не были удалены: corpus остался неизменным. Поэтому фактический состав — `4` positive pages и `5` negative pages.

Visual truth содержит три независимые positive layout families:

1. две отдельные fair-value financial-statement grids;
2. legacy activity-statement continuation/multi-section ruled grids;
3. две таблицы внутри embedded statement examples на explanatory page.

## Execution discipline

```text
pages                         9
provider calls                9
provider responses            9
attempts per page              1
retry                          false
best-of-N                      false
model change                   false
manual breadcrumb repair       false
post-result tuning             false
observed provider duration     50.342 s
total tokens                   14,623
```

Все девять responses были HTTP-success и parsed JSON objects. Transport/provider failures — `0`. Один parsed object не прошёл frozen semantic validation.

## Truth protocol

Порядок был соблюдён буквально:

```text
preselection receipt
→ render hashes
→ frozen manifest
→ one-shot provider execution
→ execution receipt
→ original render visual review
→ parser-line truth mapping
→ adjudication receipt
→ first read of predictions/resolver outputs
```

Original PDF/render использовался только как referee после execution. Predictions не читались до фиксации adjudication. Для семи visual tables удалось определить exact contiguous parser-line regions. Для двух embedded screenshot tables current line inventory перемешивает statement text с соседней explanatory колонкой; чистого единственного contiguous source region для них нет.

## Results by layout family

| Layout family | Real tables | Correct unique | False localization | Not found | Other | Result |
|---|---:|---:|---:|---:|---:|---|
| Financial-statement fair-value grid | 2 | 0 | 1 | 1 | 0 | failed with false localization |
| Legacy activity-statement ruled grid | 5 | 0 | 2 | 1 | 2 missed under one invalid page contract | failed with false localization |
| Embedded statement examples | 2 | 0 | 1 | 1 | source region not cleanly contiguous | failed with false localization |

Positive layout families tested: `3`. Successfully resolved families: `0`.

Negative controls:

- cover pages: `3/3` correctly empty;
- prose/list pages: `2/2` correctly empty;
- false table admitted: `0`.

## First-divergence classification

### 1. Sibling-table boundary collapse

На странице с двумя adjacent fair-value grids первая breadcrumb использовала следующий section anchor как конец области. Resolver детерминированно объединил обе таблицы и следующий prose block в один `RESOLVED` region. Это false localization. Вторая breadcrumb затем использовала ordinal, несовместимый с уже суженным local scope, и завершилась `NOT_FOUND`.

### 2. Frozen contract validation failure

На headerless continuation page VLM увидела обе visual table sections, но для второй вернула только одну header token group. Frozen validator требует более сильный fingerprint и отклонил весь page contract с `g598_header_groups_invalid`. Это `CONTRACT_NOT_VERIFIED`, не provider failure и не повод ослаблять validator после результата.

### 3. Page-start и section-anchor boundary semantics

На другой continuation page:

- `page_start` включил page header перед таблицей: resolved `[1..9]` вместо truth `[2..9]`;
- `first_table_after` исключил visual section band: `[11..50]` вместо `[10..50]`;
- header-only continuation section завершилась `NOT_FOUND`.

Первые два результата — false localization даже при разнице в одну строку: GOAL требует exact source region, tolerance/ranking отсутствуют.

### 4. Embedded screenshot/source expressibility

На explanatory page VLM корректно увидела две таблицы внутри embedded statement examples. Но parser reading order перемешивает строки screenshot и соседней explanatory колонки. Resolver выдал одну широкую область, содержащую table, graph и prose, а вторую не нашёл. Это одновременно false localization и доказанная граница текущего contiguous-line region representation.

## Что именно доказано

- Visual detection на этом corpus: правильное число tables per page и `0` proposals на negatives.
- Frozen schema/resolver portability: **не доказана**.
- Exact source-region generalization: **опровергнута текущим corpus**.
- False-localization safety: **нарушена четырежды**.
- Provider reliability: transport не был причиной провала.
- Ошибки не требуют broker vocabulary для объяснения; проблема находится в generic boundary/ordinal/contiguity semantics.

G5.99 ничего не исправляет. Не добавлены field, normalization rule, special ordinal behavior, fuzzy matching, document literal или geometry hint.

## Domain isolation

| Artifact | Producer | Consumer | Meaning owner | G5.99 |
|---|---|---|---|---|
| Visual Breadcrumb Contract | VLM | Source Resolver | Visual domain | unchanged |
| Resolved Source Region | Resolver | Table Engine Adapter | Source localization | qualification failed |
| Engine Configuration | Adapter | `pdfplumber` | Vendor adapter | untouched |
| Extracted Structure | `pdfplumber` + binder | Canonical materializer | Physical structure | not executed/researched |
| Literals / refs | source parser | Canonical | Source authority | unchanged |

Canonical по-прежнему не знает о breadcrumbs/VLM/`pdfplumber`. Gate 3+, tax methodology, production routing, fallback policy и activation не затронуты.

## Finish Contract

1. Frozen G5.98 hashes проверены — PASS.
2. Prompt/schema/resolver/normalization не изменены — PASS.
3. Новый corpus выбран до execution — PASS.
4. Старые G5.98 pages не использованы — PASS.
5. Несколько документов — `4`.
6. Positive layout families — `3`.
7. Non-table negatives — `5` pages.
8. Один attempt на страницу — PASS.
9. Best-of-N — `0`.
10. Post-result tuning — `0`.
11. Original PDF/render использован как referee — PASS.
12. Correct unique localization измерена — `0/9`.
13. Ambiguous/not-found измерены — `0 / 3`.
14. False localization измерен отдельно — `4`.
15. False table admission измерен отдельно — `0`.
16. Results разбиты по families/documents — PASS.
17. Failures классифицированы и не исправлены — PASS.
18. Domain boundaries изменены — no.
19. Gate 3+ touched — no.
20. Production activation/routing — `0`.
21. Verdict относится к cross-document generalization — PASS, negative.

## Проверки

```text
73 passed, 5 existing SWIG deprecation warnings in 34.13s
Ruff: PASS
py_compile: PASS
manifest/freeze/execution/adjudication/evaluation hash chain: PASS
render hashes: 9/9
attempt_number = 1: 9/9
safe JSON: 3/3 valid
private JSON: 7/7 valid
safe privacy marker groups with hits: 0
Markdown relative links missing: 0
report UTF-8 BOM / Cyrillic: PASS
private evidence gitignored: PASS
```

Regression selection включает frozen G5.98, G5.97, G5.96, current PDF layout owner и Gate architecture. Test runner действительно выполнил assertions; abort/config failures отсутствуют. PowerShell использовался как единый shell, `PYTHONPATH` задан PowerShell-синтаксисом.

## Evidence

- [Frozen G5.99 corpus manifest](../../../services/broker-reports-gate1-proof/benchmarks/frozen_cross_document_breadcrumb_g599/manifest.json)
- [Qualification freeze safe receipt](BROKER_REPORTS_FROZEN_CROSS_DOCUMENT_BREADCRUMB_G5_99.freeze.safe.json)
- [One-shot execution safe receipt](BROKER_REPORTS_FROZEN_CROSS_DOCUMENT_BREADCRUMB_G5_99.execution.safe.json)
- [Final safe evaluation](BROKER_REPORTS_FROZEN_CROSS_DOCUMENT_BREADCRUMB_G5_99.final.safe.json)
- [Frozen G5.98 harness](../../../services/broker-reports-gate1-proof/scripts/local_addressable_visual_breadcrumb_g598.py)
- [Frozen G5.98 behavioural tests](../../../services/broker-reports-gate1-proof/tests/test_broker_reports_addressable_visual_breadcrumb_g598.py)

Private source paths, PDFs, renders, provider payloads, breadcrumb literals, source coordinates, adjudication и per-case diagnosis остаются вне Git.

## Stop

G5.99 завершён на отрицательном terminal. Никакой production Gate 2 design/activation из этого результата не разрешён.

Следующий GOAL нельзя автоматически формулировать как «добавить ещё одно поле». Сначала требуется отдельное решение: либо принять узкую supported-layout envelope для G5.98 и доказать fail-closed admission до resolver, либо открыть новую гипотезу region representation для multi-table boundaries и non-contiguous source layouts. Это новая авторизация, не продолжение G5.99.
