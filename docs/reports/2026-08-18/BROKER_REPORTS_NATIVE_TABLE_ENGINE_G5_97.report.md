# Broker Reports G5.97 — Layout Contract → Native Table Engine

Дата: 2026-08-18

Статус: research-only, Gate 2

Terminal: `NATIVE_ENGINE_ASSISTED_SIMPLIFICATION_PROVEN`

Qualification: `FROZEN_UNSEEN_HOLDOUT_FAILED_CLOSED`

## Вывод

Native engine помогает **частично**. Уже используемый `pdfplumber 0.11.10` может принять resolved source region и VLM-derived visual column axis, после чего штатно построить row/cell geometry. На development corpus он дал те же 6 source-bound таблиц, что G5.96: 5/5 ошибочных column relations исправлены, known-good сохранена, `1 671 / 1 671` source words/refs перенесены, invented literals и engine strings used — ноль.

Полной замены G5.96 materializer не доказано. Custom core уменьшился только с `407 строк / 10 функций` до `343 / 8`, а число явных core failure classes выросло с `22` до `24` из-за native-engine failures. Breadcrumb/region resolution, visual axis и exact source/ref binding остались нашим кодом.

После development implementation был заморожен. Единственный заранее выбранный unseen holdout p029 корректно остановился на `g597_breadcrumb_line_ambiguous` до вызова native engine. Post-open tuning, retry, repair и второй output отсутствуют. Поэтому `NATIVE_TABLE_ENGINE_ADAPTER_PROVEN` не заявляется и production candidate не создан.

## Architecture bootstrap

- Домен: только Gate 2 physical PDF structure и deterministic source materialization.
- Authorities: `BROKER_REPORTS_ARCHITECTURE_AUTHORITIES`, `BROKER_REPORTS_PIPELINE_GATES.v1`, `BROKER_REPORTS_CANONICAL_ARTIFACT.v1`, `BROKER_REPORTS_NORMALIZED_TABLE_PROJECTION.v0`, Gate 2 implementation map.
- Production owners не изменены: `FullSourceArtifactFactory.create`, `NormalizedTableProjectionFactory.create`, `CanonicalNormalizerFactory.create`.
- G5.97 добавил только research manifest, local harness, behavioral tests, private evidence и safe reports.
- Gate 3+, financial semantics, tax methodology, routing, fallback и activation не затронуты.

## Current stack и выбор кандидата

`requirements-ci.txt` уже pin-ит `pypdf==6.7.5`, `pdfplumber==0.11.10`, `pdfminer.six==20260107` и `PyMuPDF==1.26.5`. В текущем Gate 2 `PdfPlumberLayoutAdapter` открывает PDF через `pdfplumber`, а table candidate discovery уже вызывает `page.find_tables(...)` со штатными `lines` и `text` strategies.

| Кандидат | Что умеет | Current Gate 2 | Решение |
|---|---|---|---|
| `pypdf 6.7.5` | page/content-stream text и lossless slicing; PDF не содержит semantic table layer | page-text baseline | Не table engine. Официальная документация отдельно отмечает неопределённость table structure и отсутствие semantic layer: [pypdf 6.7.5 text extraction](https://pypdf.readthedocs.io/en/6.7.5/user/extract-text.html). |
| `pdfminer.six 20260107` | layout foundation для `pdfplumber` | underlying layout engine | Самостоятельного native table API в используемом пути нет. |
| `pdfplumber 0.11.10` | crop, explicit/text/lines strategies, `find_tables`, row/column/cell bboxes | уже основной PDF layout/table candidate engine | **Выбран**: ноль новых dependencies и минимальная смена execution path. Его алгоритм строит edges → intersections → cells → tables; `Table` публикует `.rows`, `.columns`, `.cells`, `.bbox`: [официальный v0.11.10 README](https://github.com/jsvine/pdfplumber/blob/v0.11.10/README.md?plain=1#L415-L499). |
| `PyMuPDF 1.26.5` | `Page.find_tables`, clip, fixed/derived row and column lines, cell bboxes | уже есть для visual rendering, но не является текущим layout owner | Не выбран: это второй table engine, а PyMuPDF FAQ указывает, что table extraction ported from pdfplumber; до проверки текущего engine KISS-выгоды нет: [PyMuPDF table API](https://pymupdf.readthedocs.io/en/latest/page.html#Page.find_tables), [FAQ](https://pymupdf.readthedocs.io/en/latest/faq/index.html#table-extraction). |
| Camelot / Tabula | специализированные table engines | dependencies отсутствуют | Не добавлялись: существующий stack уже имеет требуемый native API. |

В `pdfplumber 0.11.10` explicit vertical lines являются штатным входом, `horizontal_strategy=lines` использует реальные source vector lines, а crop ограничивает поиск resolved region. Vendor defaults для snap/join/intersection остаются version-pinned defaults; G5.97 не добавляет numeric overrides. См. [settings и strategies](https://github.com/jsvine/pdfplumber/blob/v0.11.10/README.md?plain=1#L455-L514) и [TableFinder source](https://github.com/jsvine/pdfplumber/blob/v0.11.10/pdfplumber/table.py#L573-L681).

## Contract boundaries

| Артефакт | WHO PRODUCES? | WHO CONSUMES? | WHO OWNS MEANING? |
|---|---|---|---|
| Table Layout Contract | VLM visual pass | engine-neutral resolver | VLM owns only visible layout facts; body values, bbox, vendor knobs и Canonical IDs forbidden |
| Resolved Source Region | deterministic breadcrumb/axis resolver | extractor adapter | resolver owns exact localization against parser lines/candidates; fail closed at 0/2+ matches |
| Native Engine Configuration | `PdfplumberTableExtractorAdapter` | только `pdfplumber.find_tables` | adapter owns vendor translation; configuration не возвращается в VLM contract |
| Extracted Source Table | native cell geometry + deterministic source binder | только private research comparison | native engine owns structure proposal; maintained parser words/refs alone own literals/provenance |
| Canonical Table | существующие Gate 2 factories | existing Canonical consumers | production `NormalizedTableProjectionFactory` / `CanonicalNormalizerFactory`; G5.97 ничего не публикует |

VLM contract не содержит `vertical_strategy`, `horizontal_strategy`, explicit lines, tolerances, bbox, rows, cells или body values. Замена engine требует изменить только adapter, пока `Resolved Source Region` остаётся стабильным. Canonical domain не знает ни о `pdfplumber`, ни о G5.97.

## Native adapter

Engine-neutral inputs:

```text
resolved source bbox
+
resolved visual column boundaries
+
expected visual column count
```

Adapter-only translation:

```text
page.crop(source_region)
vertical_strategy = explicit
explicit_vertical_lines = visual column boundaries
horizontal_strategy = lines
find_tables()
```

Native engine выполняет:

- row-boundary detection по source vector lines;
- cell rectangle construction;
- contiguous row/cell grid assembly.

Наш код сохраняет:

- breadcrumb и source-region resolution;
- header-derived или inherited visual axis;
- binding каждого native cell обратно к exact maintained-parser words;
- frozen literal/ref verification и fail-closed coverage checks.

`table.extract()` и другие engine strings не используются. Каждое слово сначала совпадает по parser ordinal, literal, `source_word_ref` и `source_value_ref`; затем должно попасть ровно в одну native cell. Неполная/двойная binding закрывает case.

## Development comparison

| Page | Control | G5.96 parser → result | Native result | Rows | Source words/refs | Mapping vs G5.96 |
|---:|---|---:|---:|---:|---:|---:|
| 23 | wrong relation | 13 → 11 | 13 → 11 | 4 | 21 / 21 | exact |
| 24 | continuation/subtotal | 13 → 11 | 13 → 11 | 34 | 353 / 353 | exact |
| 25 | continuation/subtotal | 13 → 11 | 13 → 11 | 36 | 357 / 357 | exact |
| 26 | continuation/subtotal | 13 → 11 | 13 → 11 | 36 | 357 / 357 | exact |
| 27 | continuation/subtotal | 13 → 11 | 13 → 11 | 28 | 271 / 271 | exact |
| 28 | known-good | 5 → 5 | 5 → 5 | 48 | 312 / 312 | exact |
| 64 | prose negative | fail closed | fail closed | — | 0 / 0 | n/a |

Aggregate:

- correct problem tables: `5/5`;
- known-good preserved: `1/1`;
- prose fail closed: `1/1`;
- source refs: `1 671/1 671` (`100%`);
- invented literals: `0`;
- VLM body values: `0`;
- engine strings used: `0`;
- native-to-G5.96 source-word cell mapping: `6/6 exact`;
- development provider calls: `0`;
- research replay: `6.629 s` versus примерно `4.5 s` у финального G5.96 replay; speedup не доказан.

## Complexity / TCO

| Measure | G5.96 custom | Native-engine path |
|---|---:|---:|
| Custom core LOC | 407 | 343 |
| Custom core functions | 10 | 8 |
| Engine-specific adapter LOC/functions | n/a | 44 / 1 |
| Custom top-level numeric tolerances | 3 | 3 |
| Vendor numeric overrides | n/a | 0 |
| Core failure classes | 22 | 24 |
| Document/page-specific branches | 0 | 0 |
| Body/financial heuristics | 0 | 0 |
| New dependencies | 0 | 0 |

LOC снизился на `64` строки (`15.7%`), functions — на `2` (`20%`). Это реальное, но небольшое упрощение. Native engine удалил наиболее механическую часть grid construction, однако не уменьшил localization/source-authority burden. Failure surface даже вырос на native `not_found`, `ambiguous` и `grid_incompatible` outcomes.

Понимать и заменять engine стало проще благодаря одному adapter boundary. Тестировать end-to-end не стало радикально проще: exact ref coverage и retained resolver по-прежнему требуют тех же строгих fixtures. Upgrade `pdfplumber` обязан replay-ить frozen corpus, потому что adapter сознательно полагается на version-pinned native defaults.

## Frozen unseen holdout

Holdout был записан в manifest до открытия страницы и provider execution: `document_04:p029`, один attempt, без retry/best-of-N/post-open tuning.

- provider/model: `google / models/gemini-3.5-flash`;
- HTTP `200`, valid structured object, `10.209 s`;
- provider calls: `1`;
- VLM предложила две визуальные таблицы: `5` и `8` колонок;
- post-result visual adjudication исходной страницы подтвердил две отдельные таблицы и эти column counts;
- первый contract не локализовался однозначно: выбранный textual breadcrumb встречается и как section anchor, и внутри table header;
- terminal: `g597_breadcrumb_line_ambiguous` до native engine;
- materialized source words/refs: `0/0`, invented literals `0`;
- code/manifest hash после freeze не менялся.

Это полезный отрицательный результат: native engine хорошо исполняет уже resolved contract, но не решает addressability. Holdout не даёт права чинить breadcrumb rule или расширять contract после просмотра. Значит abstraction пока не прошла unseen qualification.

## Finish Contract

1. Current Gate 2 architecture восстановлена из authorities — PASS.
2. Existing dependencies инвентаризированы — PASS.
3. Native APIs проверены по primary sources — PASS.
4. Один кандидат выбран — `pdfplumber 0.11.10`.
5. Layout Contract engine-neutral — PASS.
6. Vendor API изолирован adapter'ом — PASS.
7. VLM body values — `0`.
8. Literals только source/parser-derived — PASS.
9. Ref binding на development не ухудшена — `1 671/1 671`, exact mappings `6/6`.
10. G5.96 controls сравнены — PASS.
11. Broker/page-specific rules — `0`.
12. Known-good preserved — `1/1`.
13. Non-table fail closed — `1/1`.
14. Frozen unseen holdout выполнен — FAIL CLOSED, без тюнинга.
15. LOC/functions/thresholds/failures сравнены — PASS.
16. Contract boundaries описаны — PASS.
17. Domain leakage — не обнаружен.
18. Gate 3+ — untouched by G5.97.
19. Production activation — `0`.
20. KISS verdict — **partial simplification only**.

## Проверки

```text
113 passed, 5 existing SWIG deprecation warnings in 36.17s
Ruff: PASS
py_compile: PASS
frozen implementation SHA-256 unchanged: PASS
pdfplumber dependency declared/resolved exactly 0.11.10: PASS
```

Тесты покрывают G5.97, G5.96, frozen G5.94/G5.95, PDF layout owner, normalized table projection owner и Gate architecture. Test shell: PowerShell, `PYTHONPATH=.` задан синтаксисом PowerShell. Tests реально executed; assertion failures отсутствуют.

Рабочее дерево до G5.97 уже содержало многочисленные user-owned изменения, включая production owners и Gate 3+ документы. Они сохранены; G5.97 их не чистил, не reset-ил, не stage-ил и не изменял.

## Evidence

- [Frozen G5.97 manifest](../../../services/broker-reports-gate1-proof/benchmarks/table_layout_native_engine_g597/manifest.json)
- [Research harness](../../../services/broker-reports-gate1-proof/scripts/local_native_table_engine_g597.py)
- [Behavioral tests](../../../services/broker-reports-gate1-proof/tests/test_broker_reports_native_table_engine_g597.py)
- [Development safe evidence](BROKER_REPORTS_NATIVE_TABLE_ENGINE_G5_97.development.safe.json)
- [Holdout contract safe evidence](BROKER_REPORTS_NATIVE_TABLE_ENGINE_G5_97.holdout.contract.safe.json)
- [Holdout materialization safe evidence](BROKER_REPORTS_NATIVE_TABLE_ENGINE_G5_97.holdout.materialization.safe.json)

Private page bytes, provider response, breadcrumbs, coordinates, literals и cells остаются вне Git.

## Stop

G5.97 не разрешает production integration. Практический итог: native `pdfplumber` стоит рассматривать только как implementation detail для row/cell geometry **после** доказанного engine-neutral region/axis resolution. Следующий отдельный research GOAL, если будет явно разрешён, должен проверять addressable breadcrumb/localization contract на новом frozen corpus; нельзя ремонтировать уже открытый p029 внутри G5.97.
