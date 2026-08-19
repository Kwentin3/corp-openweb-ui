# Broker Reports — G5.95 Whole-Document Canonical Coverage Audit

Дата: 2026-08-18

Статус: `CLOSED`

Контур: только `SOURCE PDF -> Gate 2 representation`

## Короткий вывод

`Markdown -> Canonical-compatible` подтверждён как тонкий механический adapter: headings, text и только явно размеченные Markdown-таблицы переносятся без PDF, Variant A, финансовой семантики или ожидаемой taxonomy.

Whole-document результат не подтверждает общий structural advantage B из выборки G5.94. У B есть локально более верные отношения колонок, но две недоступные страницы снижают полноту всего 65-страничного отчёта. A остаётся полнее, буквальная верность A выше, а coordinate provenance есть только у A. Основания проектировать hybrid в G5.95 нет.

## Frozen selection и метод

- До сравнительного review выбран `document_04`: максимальное объявленное число страниц, затем `document_id` по возрастанию.
- PDF: 65 страниц; frozen SHA-256 `7cfd297786cc91cbccbe0c2ae5bce905a2a11ac6b35e5b0a795cf9c6d41bd015`.
- A: неизменённый G5.93/G5.94 output; parser fixes = 0.
- B: только G5.94 primary `run1`; retries, best-of-N, смена prompt/model = 0.
- Все страницы `p001..p065` просмотрены по original PDF без sampling.
- Истина для score — original PDF. Сравнение A и B использовалось только как средство поиска расхождений.

`Body row` здесь означает визуально существующую строку ниже основного заголовка таблицы; secondary header, category, subtotal и continuation row считаются, если они видимы. Logical table coverage ограничена числом визуальных table regions: лишний split не увеличивает полноту. Literal change — визуально различимое изменение token occurrence; неразличимые на рендере Unicode-homoglyph различия не оценивались.

## Whole report

| Whole report | Canonical A | Canonical B |
| --- | ---: | ---: |
| Pages represented | 65/65 | 63/65 |
| Visual tables represented | 72/74 | 72/74 |
| Visual body rows represented | 2281/2295 | 2239/2295 |
| Headers preserved | 77/77 | 75/77 |
| Literal changes | 10 | 17 |
| Lost text segments | 1 | 6 |
| Invented text segments | 0 | 0 |
| Wrong row structure | 0 | 1 |
| Wrong column relations | 5 | 0 |
| Broken order | 0 | 0 |
| Unavailable pages | 0 | 2 |

Категории ошибок не складываются в accuracy score: completeness, literal fidelity и structural fidelity показаны отдельно.

## Характерные случаи

- `p001`: A представляет 2 из 4 визуальных table regions; B — 4 из 4. При этом B разделяет одну составную область на две Markdown-таблицы, поэтому у B зафиксирована одна ошибка row structure.
- `p023..p027`: у A пять случаев неверной связи колонок в широкой таблице; B сохраняет визуальное число колонок. Это подтверждает локальный column-relation advantage B.
- `p033` и `p042`: frozen primary B недоступен; retry не выполнялся. В сумме B не представляет 2 таблицы, 56 body rows и 2 headers, которые A представляет.
- У B визуально различимые literal substitutions найдены на 12 страницах; у A — на 4 страницах. Значения в safe evidence не публикуются.
- На двух представленных B-страницах отсутствуют по два footer segments; недоступные страницы учитываются ещё как два page-level literal losses. У A найден один потерянный видимый text region.
- Ни в A, ни в B не найдено invented text или нарушения общего reading order.

## Adapter и capabilities

Adapter поддерживает общий минимальный слой:

```text
page -> ordered HEADING | TEXT | TABLE -> ROW -> CELL -> literal
```

Неоднозначная или ragged Markdown-разметка сохраняется как `TEXT`; adapter не достраивает таблицу. Недоступная primary page даёт пустую страницу со статусом `unavailable`.

| Capability | A frozen | B adapter |
| --- | ---: | ---: |
| Page identity and order | yes | yes |
| Source coordinates | yes | no |
| PDF cell path | yes | no |
| Glyph/word refs | yes | no |
| Markdown line identity | n/a | yes |

Итог adapter: `MECHANICAL`. Новый heuristic parser не требуется. Это research-only projection, не новый production owner Canonical.

## Стоимость, runtime, maintenance

- Новых VLM calls: 0; incremental provider cost G5.95: 0.
- Projection и scoring локальные, детерминированные; внешнего inference runtime нет.
- Maintenance surface: один manifest, один локальный CLI и один focused test module; новых dependencies нет.

## Scope и terminals

- Gate 3+ changes: 0.
- Financial reasoning/labels: 0.
- Hybrid design/reconciliation/routing: 0.
- Production activation: 0.
- Customer text в safe artifacts: 0.

Terminals:

```text
WHOLE_DOCUMENT_CANONICAL_AUDIT_PROVEN
MARKDOWN_TO_CANONICAL_THIN_ADAPTER_PROVEN
VARIANT_A_WHOLE_DOCUMENT_COVERAGE_MEASURED
VARIANT_B_WHOLE_DOCUMENT_COVERAGE_MEASURED
G594_SAMPLE_CONCLUSION_NOT_CONFIRMED_WHOLE_DOCUMENT
COLUMN_RELATION_ADVANTAGE_B_CONFIRMED
LITERAL_AUTHORITY_ADVANTAGE_A_CONFIRMED
```

Простое архитектурное заключение: B можно без новой сложности привести к общей машинной форме, но frozen B не является whole-document replacement для A. Локальная структурная польза B доказана, hybrid остаётся отдельной, неавторизованной гипотезой.

## Evidence

- Safe machine result: `BROKER_REPORTS_WHOLE_DOCUMENT_CANONICAL_AUDIT_G5_95.machine.safe.json`
- Private projection: `external_private_evidence`
- Private page-by-page review: `external_private_evidence`
- Safe SHA-256: `eb508f11d630101c9bed5a7e7bab812d8ab41828dd99ae390c9657a4e6f9fec9`

Следующий GOAL не выполнялся.
