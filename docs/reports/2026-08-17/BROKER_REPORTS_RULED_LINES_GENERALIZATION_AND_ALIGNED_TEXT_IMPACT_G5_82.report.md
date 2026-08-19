# G5.82 — Ruled-lines generalization и consumer impact `aligned_text_v0`

Дата: 2026-08-17
Статус: завершён; Gate 2 исправлен только для доказанной `ruled_lines_v0` regression

## Результат

В `NormalizedTableProjectionFactory` добавлено одно общее admission-условие для `ruled_lines_v0`:

> Внутри candidate bbox на той же странице должно существовать семейство хотя бы из двух различимых параллельных осевых vector lines.

Прямоугольники не считаются линиями разлиновки. Одна изолированная линия тоже не доказывает повторяемую границу таблицы. Правило не использует broker, номер страницы, текст, координаты конкретного документа или финансовую семантику.

Full factory replay дал требуемую точную дельту:

| Проверка | До | После |
|---|---:|---:|
| Все candidates | 90 | 90 |
| `READY` | 89 | 87 |
| `blocked` | 1 | 3 |
| Визуально истинные promoted tables | 77/77 | 77/77 |
| Два новых rectangle-prose false positive | 0/2 blocked | 2/2 blocked |
| Необъяснённые изменения | — | 0 |

Из 90 candidate refs изменились только:

- `pdftablecand_e42ae0b0bfb9f80e98b4a447`, page 64;
- `pdftablecand_893c6e585e6889497afe4395`, page 65.

Оба теперь получают `pdf_table_geometry_parallel_ruling_family_missing` и возвращаются в fallback line-cluster representation. Lost и duplicate refs в regression test равны нулю; validator принимает закрытый fallback.

## Почему это не magic threshold

Число `2` означает не подгонку к страницам 64–65, а минимальное количество различных параллельных границ, при котором вообще возникает повторяемая ruled-структура. Дубли одной линии схлопываются по геометрической позиции. Линии другой страницы не учитываются.

На замороженной популяции:

- все 77 настоящих promoted tables имеют такое семейство;
- минимальное наблюдаемое семейство у настоящей таблицы — 3 горизонтальные линии;
- false page 64 имеет `0 vertical / 0 horizontal` настоящих линий;
- false page 65 имеет `0 vertical / 1 horizontal`;
- rectangles у false cases: 43 и 18 соответственно.

## Расширенный positive corpus

Проверены 77 реальные promoted tables и 10 positive controls: 9 реальных и один явно обозначенный `SYNTHETIC_CALIBRATION` grid 4Ч3.

В корпусе присутствуют:

- полная сетка;
- горизонтальная разлиновка без вертикальной;
- border-light table;
- merged title rows;
- continuation rows;
- subtotal rows;
- пустая табличная форма.

Реальной таблицы только с вертикальными линиями в доступном корпусе не найдено; отсутствие такого layout не маскируется синтетическим заявлением. Правило симметрично и допускает семейство в любой одной ориентации.

Synthetic control после fix: `READY`, validator `passed`, lost refs = 0, duplicate refs = 0.

Шесть ранее repaired pages `16, 19, 24, 25, 26, 27` остаются structured.

## Negative corpus

Две новые `ruled_lines_v0` false positives устранены. Девять прочих visual non-table controls по-прежнему отклоняются до candidate acceptance.

Старый `aligned_text_v0` false positive на holdout page 6 остаётся `READY`. Его detector не менялся.

## Consumer impact `aligned_text_v0`

Для текущего активного case прослежен существующий factory-backed путь до Gate 4.

Важно: current-code rebuild с ложным `aligned_text_v0` candidate не persisted и не activated. Активный Canonical хранит ту же страницу как обычный `TEXT` node из line cluster.

| Слой текущего active case | Результат |
|---|---:|
| Canonical nodes страницы 6 | 1 TEXT node |
| Gate 3 annotations всего | 264 |
| Gate 3 annotations, направленных на страницу 6 | 0 |
| Gate 4 facts всего | 264 |
| Gate 4 facts с provenance страницы 6 | 0 |

Контрфактическое исключение этого node не меняет ни одного financial fact. Совпали:

- полный fact hash;
- `financial_type`;
- значения и роли;
- semantic binding;
- Gate 3 provenance binding.

Следовательно, для **текущего активного consumer case** impact равен `ZERO`; defect классифицирован как `TECH_DEBT_NOT_CURRENT_CRITICAL_PATH` и не исправлялся.

Ограничение: это не доказывает безвредность будущей активации нового Canonical, где page 6 уже представлен ложной таблицей. Перед такой активацией `aligned_text_v0` требует отдельной qualification.

## Проверки

```text
Full real-PDF replay: 4 documents / 103 pages / 90 candidates
Frozen 79: 77 true READY / 2 false blocked / 0 ambiguous
All-candidate unexplained status changes: 0
Focused pytest: 46 passed
Ruff: PASS
py_compile: PASS
FACTORY_REQUIRED / FORBIDDEN anchor test: PASS
Holdout A: 39/39 admitted
Holdout B: 129/129 admitted
```

39/129 проверены через frozen annotation admission seam; полный rebuild этих expired fixtures не заявляется.

Тесты создают новые factory artifacts и используют отдельные deep-copied payloads для каждого варианта. Unit under test не mock-ится. Необратимая граница — принятие или fail-closed отклонение projection до публикации Canonical; assertions проверяют `READY/blocked`, reason code, validator и coverage.

## Scope

- Gate 3 code, prompts, model, retry и validation granularity не менялись.
- Decimal normalization, methodology, metadata и VLM paths не менялись.
- Provider calls = 0; manual facts = 0.
- Product visual dependency = 0.
- Broker-specific rules = 0; page-specific rules = 0.
- Новых imports, dependencies, env или runtime path hacks нет.
- Существующее пользовательское dirty tree сохранено; stage/reset/cleanup не выполнялись.

## Terminal

```text
RULED_LINES_TABLE_ADMISSION_GENERALIZATION_PROVEN
PROMOTED_TRUE_TABLES_PRESERVED
NEW_RULE_FALSE_POSITIVES_ZERO
BROKER_SPECIFIC_TABLE_FITTING_ZERO
PAGE_SPECIFIC_TABLE_FITTING_ZERO
PRODUCTION_VISUAL_DEPENDENCY_ZERO
ALIGNED_TEXT_FALSE_POSITIVE_CONSUMER_IMPACT_ZERO_CURRENT_ACTIVE_CASE
ALIGNED_TEXT_FALSE_POSITIVE_DEFERRED_AS_TECH_DEBT
CANONICAL_TRUST_BOUNDARY_SUFFICIENT_FOR_CURRENT_CASE
READY_FOR_GATE3_MINIMAL_FAIL_CLOSED_GRANULARITY_AUDIT
```
