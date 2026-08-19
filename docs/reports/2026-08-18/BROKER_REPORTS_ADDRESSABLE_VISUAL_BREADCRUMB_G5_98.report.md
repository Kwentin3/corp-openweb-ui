# Broker Reports G5.98 — Addressable Visual Breadcrumb Contract

Дата: 2026-08-18

Статус: research-only, Gate 2

Terminal: `ADDRESSABILITY_CONTRACT_PROMISING_BUT_INCOMPLETE`

Secondary terminal: `FALSE_LOCALIZATION_ZERO`

## Вывод

Узкий мост `VLM visual object → ровно один source region` технически сработал без bbox, body values, fuzzy ranking и document-specific правил.

На development наборе resolver дал `14/14` correct unique localizations. После freeze schema, prompt и implementation unseen holdout был вызван один раз: `3/3` реальных таблиц разрешены точно, prose control не породил таблицу, `4/4` страниц совпали с независимой adjudication, false localization и false table admitted равны нулю.

Сильные terminals сознательно не заявлены. Все три положительные holdout-таблицы принадлежат одной layout family; второй holdout-документ оказался корректным negative control. Frozen критерий strong-proof требовал минимум две успешно разрешённые unseen-positive families. Поэтому доказана корректность на текущем holdout, но не достаточная переносимость между положительными layout families.

Минимальный контракт оказался меньше исходной гипотезы: visual column count и header row count не понадобились. Достаточны code-owned page identity и пять table-level полей: `before_anchor`, `header_token_groups`, `after_anchor`, `table_ordinal_in_scope`, `continuation_from_previous_page`.

## Architecture bootstrap и scope

- Домен: только Gate 2 physical source localization.
- Current owners сохранены. Parser вызывается только через `PdfTextLayerParserFactory.create(PdfParserCapabilityRequest(capability="table_candidates"))`.
- G5.97 native table extraction не переисследовался: G5.98 останавливается на `Resolved Source Region`.
- Production Canonical, routing, activation, financial semantics, Gate 3, Gate 4, Gate 5 и tax methodology не изменены.
- G5.97 p029 оставлен historical evidence причины ambiguity и явно исключён из development/holdout G5.98.

## Research first: доступные primitives

Текущий stack уже даёт необходимые source primitives, поэтому новая dependency и отдельный localization framework не потребовались:

- maintained parser публикует page-local `line_inventory`, `word_inventory`, source bboxes, reading order и diagnostic table candidates;
- `pdfplumber Page.search(...)` возвращает все textual matches вместе с bbox/chars, а `extract_words(...)` — слова с координатами;
- `crop(...)` / `within_bbox(...)` создают ограниченную derived page;
- `find_tables(...)` возвращает все найденные table objects, а table finder строит `edges → intersections → cells → tables`.

Primary sources: [pdfplumber v0.11.10 README](https://github.com/jsvine/pdfplumber/blob/v0.11.10/README.md), [Page implementation](https://github.com/jsvine/pdfplumber/blob/v0.11.10/pdfplumber/page.py), [TableFinder implementation](https://github.com/jsvine/pdfplumber/blob/v0.11.10/pdfplumber/table.py).

Вывод исследования: primitives достаточно скомпозировать. `find_tables` не используется как probabilistic winner: native candidates остаются только диагностикой. Authority локализации — exact parser lines/words/order, а не «самая большая» или «ближайшая» таблица engine-а.

## Новый frozen corpus

Manifest был записан до визуального просмотра выбранных страниц и имеет SHA-256 `121a00be74cd4360982f4278f7868b0187bd56b8deadc0b85e725c8e2b390d0f`.

| Split | Cases | Documents | Назначение |
|---|---:|---:|---|
| Development | 10 | 3 | normal header, continuation, multiple tables, repeated header words, overlapping section/header wording, headerless continuation, prose/list, known-good и другая family |
| Unseen holdout | 4 | 2 | три positive tables одной family и один prose negative другой family |

Полный corpus включает разные документы/layout families и non-table controls. Но strong holdout qualification недобрала именно второй unseen-positive layout family; общая diversity development не заменяет unseen evidence.

## Минимальный Visual Breadcrumb Contract

Page identity (`case_id`, document identity, page number, source hash) принадлежит code envelope и не генерируется VLM.

Для каждой визуальной таблицы VLM возвращает только:

```text
before_anchor:
  relation = page_start | immediately_after | first_table_after
  tokens[]

header_token_groups[][]

after_anchor:
  boundary = next_anchor | page_footer | page_end
  tokens[]

table_ordinal_in_scope
continuation_from_previous_page
```

Удалены как не добавившие необходимой addressability:

- `visual_column_count`;
- `header_row_count`;
- subtotal/footer-presence flags;
- local geometry hints.

Запрещены и фактически отсутствуют:

- body rows/values;
- exact VLM bbox/coordinates;
- source refs и Canonical IDs;
- financial types/semantics;
- `pdfplumber` settings и другие vendor knobs.

Header/section literals — только короткие locator proposals. Они не становятся source truth и обязаны подтвердиться на реальных parser lines/words.

## Deterministic resolver

Resolver концептуально выполняет пять шагов:

```text
resolve exact before-anchor scope
→ verify exact header fingerprint in bounded source-line windows
→ resolve exact after-anchor/end scope
→ intersect scopes and apply local ordinal
→ require exactly one source region
```

Особенности:

- NFKC + casefold + punctuation collapse используются только для literal matching;
- numeric footnote suffix нормализуется, потому что Unicode footnote после NFKC становится digit suffix;
- header fingerprint проверяется как exact normalized token multiset в окне максимум шесть source lines: visual column order может отличаться от parser reading order;
- `next_anchor` означает первый exact anchor после before-anchor;
- итоговый bbox вычисляется только из source line/word coordinates;
- overlapping parser table candidates публикуются только как diagnostics и не выбирают победителя;
- confidence score, fuzzy similarity, ranking, broker vocabulary и page-number branches отсутствуют.

Terminal semantics:

| Source evidence | Terminal |
|---|---|
| ровно один composed region | `RESOLVED` |
| ни одного region/anchor | `NOT_FOUND` |
| больше одного region | `AMBIGUOUS` |
| обязательная часть source contract не подтверждаема | `CONTRACT_NOT_VERIFIED` |

## Development refinement

Development был bounded research, а не скрытым best-of-N. Каждый schema/prompt revision прогонялся один раз на всех 10 development pages; output предыдущего revision не выбирался как кандидат для финального результата.

| Revision | Provider calls | Valid page contracts | Invalid | Proposed tables |
|---|---:|---:|---:|---:|
| v0 | 10 | 4 | 6 | 5 |
| v1 | 10 | 6 | 4 | 7 |
| v2 | 10 | 8 | 2 | 9 |
| v3 final | 10 | 10 | 0 | 14 |

Итого: `40` development calls, по одному attempt на page/revision, без retry, failover и best-of-N. Refinement убрал из контракта недоказанные поля, ограничил locator tokens и уточнил exact source semantics. Финальная evaluation v7 использует ровно один набор v3 contracts; между evaluation revisions менялся только development resolver/metric semantics, provider повторно не вызывался.

Финальные development metrics:

| Metric | Value |
|---|---:|
| Cases exact | 10/10 |
| Expected regions | 14 |
| Correct unique localization | 14 |
| Ambiguous | 0 |
| Not found | 0 |
| Contract not verified | 0 |
| Missed expected | 0 |
| False localization | 0 |
| False table admitted | 0 |

## Freeze и unseen holdout

Перед holdout заморожены:

- implementation SHA-256: `be83b01d7d32965c34d0f30029bee73bce1ec68f4965c2c7473c6e348cdffeaf`;
- response schema SHA-256: `b5234742ef277c2707ec4fa13c0b7321a843f7d1abfabf1b459590c51060a406`;
- prompt SHA-256: `a7030b9a6b07c094a2271ca71dc81b71f7ab0a5bd09d18b377cbc440688b39e4`.

Holdout execution: `4` provider calls, ровно один attempt на страницу, retry `false`, best-of-N `false`, post-holdout tuning `false`. Implementation hash после holdout совпал с freeze.

Ground truth был зафиксирован после frozen execution, но до чтения predictions: сначала human visual review оригинальных renders, затем ordinal mapping через current parser factory, после этого — единственная финализация.

| Metric | Value |
|---|---:|
| Cases exact | 4/4 |
| Expected positive regions | 3 |
| Proposed tables | 3 |
| Correct unique localization | 3 |
| Negative prose cases correctly empty | 1/1 |
| Ambiguous | 0 |
| Not found | 0 |
| Contract not verified | 0 |
| Missed expected | 0 |
| False localization | 0 |
| False table admitted | 0 |
| Resolved unseen-positive layout families | 1 |

`FALSE_LOCALIZATION_ZERO` доказан на этом holdout. `ADDRESSABLE_VISUAL_BREADCRUMB_CONTRACT_PROVEN`, `UNIQUE_SOURCE_REGION_RESOLUTION_PROVEN` и `ENGINE_NEUTRAL_ADDRESSABILITY_PROVEN` не заявляются, потому что frozen strong criterion требует две positive families.

Execution accounting отделён от accuracy: development — `40` provider calls, суммарно `206.257 s` observed provider duration и `70,835` tokens; holdout — `4` calls, `20.498 s` и `6,533` tokens. Денежная стоимость не вычислялась, поскольку в receipts нет стабильной authority цены. Сам deterministic resolver внешних provider calls не делает.

## Complexity / KISS

Метрика рассчитана одинаковым AST-скриптом: сумма source spans выбранных resolver functions и число `If/For/While/Try/BoolOp/Match/comprehension` nodes. Это не semantic complexity score, а воспроизводимый относительный proxy.

| Measure | G5.97 old breadcrumb resolver | G5.98 addressable resolver | Delta |
|---|---:|---:|---:|
| Resolver core LOC | 188 | 176 | -12 (-6.4%) |
| AST control nodes | 69 | 65 | -4 (-5.8%) |
| Resolver helper functions | 6 | 9 | +3 |
| Whole research harness LOC | 1,584 | 1,370 | -214 |
| Fuzzy scoring/ranking rules | 0 | 0 | 0 |
| Confidence thresholds | 0 | 0 | 0 |
| Document/page-specific rules | 0 | 0 | 0 |
| New dependencies | 0 | 0 | 0 |

Core немного меньше, но разбит на большее число маленьких composable helpers. Это KISS-плюс, не радикальное упрощение. Whole harness всё ещё велик из-за provider receipts, privacy projection, freeze и one-shot enforcement; его LOC нельзя выдавать за production resolver cost.

## Contract boundaries

| Artifact | Producer | Consumer | Meaning owner |
|---|---|---|---|
| Visual Breadcrumb Contract | VLM | Source Resolver | Visual domain |
| Resolved Source Region | deterministic resolver | Table Engine Adapter | Source localization |
| Engine Configuration | adapter | `pdfplumber` | Vendor adapter |
| Extracted Structure | `pdfplumber` + source binder | Canonical materializer | Physical structure |
| Literals / refs | maintained source parser | Canonical | Source authority |

Ответы на boundary checks:

- поменять `pdfplumber`, не меняя VLM contract — **да**;
- поменять VLM provider, не меняя resolver semantics — **да**, если provider соблюдает тот же schema;
- Canonical может не знать, что breadcrumbs существовали — **да**;
- VLM literals могут стать source authority — **нет**;
- resolver может выбрать best-looking candidate — **нет**.

## Finish Contract

1. Current architecture authorities восстановлены — PASS.
2. p029 только historical evidence и исключён из corpus — PASS.
3. Новый corpus frozen заранее — PASS.
4. Current source-localization primitives изучены — PASS.
5. Минимальный engine-neutral contract сформулирован — PASS.
6. VLM body values — `0`.
7. VLM exact bbox — `0`.
8. Vendor-specific visual fields — `0`.
9. Resolver использует deterministic source evidence — PASS.
10. Correct unique resolutions измерены — PASS.
11. Ambiguous/not-found измерены — PASS.
12. False localization измерен отдельно — `0`.
13. Non-table controls включены — PASS.
14. Different layout families включены в полный corpus — PASS; unseen-positive coverage только одна family.
15. Broker/page-specific logic — `0`.
16. Complexity delta измерена — PASS.
17. Domain boundaries описаны — PASS.
18. Contract/resolver frozen до holdout — PASS.
19. Holdout не тюнился после открытия — PASS.
20. Production routing/activation — `0`.
21. Gate 3+ — untouched by G5.98.
22. Verdict отвечает только на addressability — PASS, partial.

## Проверки

```text
43 passed, 5 existing SWIG deprecation warnings in 2.25s
Ruff: PASS
py_compile: PASS
14 safe/manifest JSON files parsed: PASS
safe privacy marker groups with hits: 0
Markdown relative links missing: 0
report UTF-8 BOM / Cyrillic / whitespace: PASS
private evidence gitignored: PASS
frozen implementation SHA-256 unchanged: PASS
```

Regression selection включает G5.98 behavioural tests, G5.97 native-engine path, G5.96 visual-layout contract и current PDF layout owner. Tests реально executed; assertion failures отсутствуют.

## Evidence

- [Frozen corpus manifest](../../../services/broker-reports-gate1-proof/benchmarks/addressable_visual_breadcrumb_g598/manifest.json)
- [Research harness](../../../services/broker-reports-gate1-proof/scripts/local_addressable_visual_breadcrumb_g598.py)
- [Behavioral tests](../../../services/broker-reports-gate1-proof/tests/test_broker_reports_addressable_visual_breadcrumb_g598.py)
- [Final safe summary](BROKER_REPORTS_ADDRESSABLE_VISUAL_BREADCRUMB_G5_98.final.safe.json)
- [Development v3 provider receipt](BROKER_REPORTS_ADDRESSABLE_VISUAL_BREADCRUMB_G5_98.development.contracts.v3.safe.json)
- [Development final evaluation](BROKER_REPORTS_ADDRESSABLE_VISUAL_BREADCRUMB_G5_98.development.evaluation.v7.safe.json)
- [Freeze receipt](BROKER_REPORTS_ADDRESSABLE_VISUAL_BREADCRUMB_G5_98.freeze.safe.json)
- [Holdout execution receipt](BROKER_REPORTS_ADDRESSABLE_VISUAL_BREADCRUMB_G5_98.holdout.execution.safe.json)
- [Holdout final evaluation](BROKER_REPORTS_ADDRESSABLE_VISUAL_BREADCRUMB_G5_98.holdout.final.safe.json)

Private PDFs, renders, source paths, customer literals, VLM payloads, source coordinates и adjudication остаются вне Git.

## Stop

G5.98 завершён на partial terminal. Он не разрешает production integration, activation или зависимый Gate 3+ GOAL.

Следующий допустимый отдельный research GOAL, только после явного разрешения: не менять frozen schema/resolver, а квалифицировать их на новом заранее замороженном unseen-positive corpus минимум ещё одной независимой layout family. Уже открытые G5.98 pages нельзя использовать как новый unseen proof.
