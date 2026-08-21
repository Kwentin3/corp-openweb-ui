# Broker Reports — Ordinary Trade Production Candidate

## Вердикт

`ORDINARY_TRADE_SEMANTIC_COMPILER_PRODUCTION_CANDIDATE_READY`

Квалифицированный ordinary security-trade path доведён до отдельного рабочего
production candidate. В production он не включён. Старый маршрут не удалён и не
изменён.

## Фактический маршрут

```text
проверенный source PDF
→ active immutable Canonical
→ exact-fingerprint schema mapping
→ Source Observations
→ deterministic runtime records
→ existing Gate 4 fact v2 shape
→ unchanged deterministic Gate 5 consumer
```

Реальные владельцы маршрута:

- `CanonicalReaderFactory` читает активный Canonical и остаётся source authority;
- `OrdinaryTradeSemanticCompilerFactory` сопоставляет только точный structural
  fingerprint, создаёт observation для каждой непустой table row и копирует
  значения из Canonical;
- `OrdinaryTradeProjectionFactory` сохраняет один immutable private sidecar с
  детерминированным artifact id;
- `Gate4OrdinaryTradeCandidateRuntimeFactory` механически переводит runtime
  records в существующий Gate 4 fact v2 contract;
- `OrdinaryTradeCandidateRuntimeFactory` подаёт эти факты в неизменённую
  `Gate5DeterministicSourceFactConsumptionRuntime`.

Current Gate 3 free discovery, FinancialAnnotationsV2, separate role pass и
current Gate 4 SQL cache в candidate route не вызываются. Они сохранены только
для старого production route.

Candidate composition вынесен в отдельный неактивный module; production Gate 5
source и его runtime bundle не менялись. Compatibility facts дополнительно
проверены опубликованной JSON Schema Gate 4 Fact v2.

## Что решает модель и что решает код

Для одного нового exact schema модель принимает два ограниченных решения:

1. тип таблицы и значения колонок;
2. смысл source literals покупки и продажи.

В повторном документе с тем же exact fingerprint model call не нужен. При
изменённом fingerprint reuse запрещён.

Код владеет таблицами, строками, cardinality, source refs, всеми финансовыми
значениями, нормализацией дат и чисел, созданием фактов и provenance. Значений,
созданных моделью: **0**.

Числовая запись определяется только по однозначной лексической форме той же
таблицы. Например, наличие `comma-grouped + dot-decimal` формы разрешает коду
прочитать grouped integer с запятыми. Финансовые равенства и broker rules для
этого не используются.

## Real-document E2E

Проверены три полных настоящих PDF. Для каждого SHA-256 фактических PDF bytes
совпал с source SHA-256 активного Canonical.

| Case | Canonical tables | Supported trades | Gate 4/Gate 5 trade facts | Other rows preserved | Result |
|---|---:|---:|---:|---:|---|
| Sber 2024 | 14 | 45 | 45/45 ready | 152 `RELEVANT_UNMAPPED` | pass |
| VTB 2024 | 24 | 15 | 15/15 ready | 514 `RELEVANT_UNMAPPED` | pass |
| BKS 2025 REPO negative | 10 | 0 | 0 | 173 `RELEVANT_UNMAPPED` | fail-closed pass |

В supported rows дополнительно созданы 102 отдельных transaction-charge facts.
Итого Gate 5 увидел 162 candidate source facts: 60 security trades и 102 charges.

В Sber и VTB Gate 5 корректно сообщил
`gate5_source_fact_acquisition_quantity_insufficient`: в этих годовых отчётах
нет достаточной исторической acquisition basis для части продаж. Это не дефект
compiler и не пропавшее значение: все 60 security facts прошли входную проверку
Gate 5, после чего существующая налоговая методология остановила расчёт по
реально отсутствующему source evidence. Declaration calculation для этих
продаж поэтому честно не создавался.

## Главные цифры

| Metric | Result |
|---|---:|
| Source records accounted | **899/899 = 100%** |
| Emitted runtime values traced | **768/768 = 100%** |
| Gate 5 required facts supplied | **60/60 = 100%** |
| Broker/year special profiles | **0** |
| Exact projection repeatability | **true** |
| Exact Gate 4 fact repeatability | **true** |

Каждый emitted value связан цепочкой:

```text
Gate 5 fact
→ candidate projection artifact
→ runtime record role
→ Source Observation field
→ Canonical node/row/column + source_coordinate + provenance_refs
→ Canonical source binding
→ verified source PDF SHA-256
```

Одинаковые значения разных строк не объединяются. Повторная компиляция создаёт
тот же projection hash и тот же artifact id; повторное чтение даёт те же fact
ids. Отдельного SQL cache у candidate нет, поэтому SQL duplicates не возникают.

## Поддерживаемая граница

Поддержано: independently readable ordinary security-trade table с exact
qualified structural fingerprint и полными обязательными source fields.

Fail closed:

- РЕПО;
- mixed-operation journals;
- неизвестная operation semantics;
- изменённая или неизвестная схема;
- physical continuation без доказанного structural lineage;
- строка внутри matched table, не проходящая literal/runtime contract.

Неподдерживаемые строки остаются Source Observations и не блокируют независимые
supported rows того же полного документа. Semantic compiler не строит relation
между физическими таблицами; structural lineage остаётся обязанностью
Canonical-side structural layer.

## KISS и остаточный долг

Новых broker profiles, ontology, dialect framework, второго SQL store и
fallback на legacy не создано. Добавлены четыре узких владельца: compiler,
immutable projection, Gate 4 compatibility adapter и отдельная Gate 5 candidate
factory.

Единственный намеренно сохранённый технический долг: существующий Gate 4 fact
v2 называет compatibility envelope `gate3_binding` и фиксирует исторический v2
discriminator. Candidate использует эту опубликованную форму, указывает в ней
id immutable projection artifact, а свою semantic authority — в разрешённых
`dictionary`/`role_pack` identities. Факт целиком проходит существующую JSON
Schema v2; старый Gate 3 при этом не вызывается. Переименование потребовало бы
новой версии общего Gate 4/5 контракта и изменения опубликованной методики Gate
5, что не нужно для этой кандидатной квалификации.

## Состояние

- production activation: **нет**;
- legacy fallback: **нет**;
- current production route: **не сломан и не удалён**;
- private raw projections/facts/model bindings: вне Git;
- safe receipt: `BROKER_REPORTS_ORDINARY_TRADE_PRODUCTION_CANDIDATE.receipt.json`.

Проверки: 63/63 целевых теста прошли; Ruff и проверка parity поддерживаемого
source внутри bundle прошли. Полный service suite дал 3835 passed и 5 skipped.
После точечного исправления найденных candidate-интеграций остались только
baseline failures, не принадлежащие этой поставке: stale authority pin для
неизменённого `gate2_provider_adapters.py`, ранее не зарегистрированный
`pdf_table_locator_provider.py` и byte-exact rebuild на Windows из-за CRLF/LF.
