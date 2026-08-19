# Broker Reports Gate 5 Tax-Period Category Aggregation — G5.14

Date: 2026-08-09

Status: `G5.14_CLOSED`

Outcome: `PROVEN_WITH_USER_VERIFIED_COMPLETENESS`

Product status: `INACTIVE PROOF`

## Ответ

Да. Gate 5 может перейти от корректного Tax Model одной операции к
агрегированному результату одной категории за заданный налоговый scope, не
выдавая «все известные операции» за «все операции налогоплательщика».

Минимальный найденный seam:

```text
G5.13 complete operation models
        +
taxpayer/category/period scope
        +
user-verified completeness assertion
bound to exact scope/member-model SHA-256
        ↓
known values всегда
complete Category Tax Model только при exact binding
        ↓
existing G5.12 projector
```

## Что исследовано до реализации

Repository truth подтверждает:

- Gate 4 `CASE_COMPLETE_FOR_CURRENT_INPUT_SET` описывает только техническую
  полноту текущего известного document set;
- Gate 4 не доказывает, что загружены все отчёты, отсутствует другой брокер или
  не пропущены операции;
- текущий G5.13 `2026.0-experimental` одновременно моделировал одну операцию и
  использовал proof-only `complete_for_category_in_proof`;
- такой результат нельзя честно использовать как operation member годового
  aggregate.

Поэтому G5.14 не использует Gate 4 completeness и не агрегирует raw facts.

## Минимальная реализация

### 1. Operation-only seam в существующем G5.13 owner

В
[`Gate5SecuritiesDisposalTaxModelRuntimeFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate5_securities_disposal_tax_model.py)
добавлен совместимый `run_operation`.

Он:

- получает Financial Case и Supplemental значения через прежний G5.5 path;
- применяет прежнюю G5.13 classification/expense semantics;
- возвращает `single_operation_only` Tax Model;
- не содержит category completeness;
- не вызывает G5.12 projector.

Для него опубликована отдельная immutable methodology version:

```text
methodology_id      = ru-ndfl-securities-tax-model-proof
methodology_version = 2026.1-experimental
behavior_id         = securities_disposal_operation_tax_model_v0
resource_sha256     = 253f6f644eb88c963639833bcef8b169a51e4b8790ab2dcfa22c091b58e30bed
```

Старая G5.13 methodology version и `run` не изменены.

### 2. Один scope/aggregation runtime

Новая единственная boundary:

[`Gate5TaxPeriodCategoryAggregationRuntimeFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate5_tax_period_category_aggregation.py)

Она принимает только:

- explicit `scope_ref`, `taxpayer_scope_ref`, `tax_period`, stable category;
- минимум две complete G5.13 operation models;
- optional structured completeness evidence.

Runtime проверяет methodology каждого member через G5.8, сортирует операции,
считает canonical SHA-256 каждой модели и создаёт один closed scope binding.

### 3. Exact completeness binding

Completeness assertion содержит:

```text
source_kind = user_verified_fact
coverage_kind = all_operations_in_taxpayer_category_period_scope
scope_binding_sha256 = hash(scope + exact sorted member set)
```

Member set включает:

```text
operation_ref
source_scope_ref
operation_model_sha256
```

Это не generic signing framework. Это минимальная защита от повторного
использования старого assertion после изменения набора.

## Representative proof

Через реальный G5.13 `run_operation` созданы две operation models:

```text
Operation A
gross income        100.00 RUB
related expenses     72.00 RUB
allowable expenses   72.00 RUB

Operation B
gross income         50.00 RUB
related expenses     30.00 RUB
allowable expenses   28.00 RUB
```

У Operation B комиссия `2.00 RUB` связана с операцией, но не подтверждена как
documented. Поэтому она остаётся related, но не allowable. Это специально
доказывает раздельную aggregation двух expense meanings.

При exact completeness:

```text
category gross income        150.00 RUB
category related expenses    102.00 RUB
category allowable expenses  100.00 RUB
loss treatment               none
```

G5.12 создал один Appendix 8 fragment:

```text
ВидОпер        = 01
ДохСовОпер     = 150.00
РасхРеалЦБ     = 102.00
РасхУмДохОпер  = 100.00
ПризУчетУбыт   = 0
```

G5.14 не содержит этих declaration-owned names или codes.

## Negative proofs

Доказано fail closed:

- без completeness evidence возвращаются `known_values`, но
  `status = incomplete_scope`, Category Tax Model и declaration output равны
  `null`;
- assertion для A+B не принимается для A+B+C;
- period mismatch отклоняется;
- category mismatch отклоняется до aggregation;
- mixed currency отклоняется;
- duplicate operation ref и duplicate model content отклоняются;
- пустая/неоднозначная operation identity отклоняется;
- incompatible loss treatment отклоняется;
- incomplete operation model отклоняется;
- unknown methodology version отклоняется через trusted authority;
- перестановка A/B даёт structure-equivalent результат.

## Provenance

Каждый aggregate содержит sorted contributions:

```text
aggregate value
  -> operation_ref
  -> operation_model_sha256
  -> exact operation value
  -> original Financial Case / Supplemental source evidence
```

Gross income сохранил `financial_case` provenance. Acquisition cost и fee
сохранили `supplemental_fact` provenance. Graph/relations/новая persistence не
понадобились.

## Completeness Audit

### Что именно считается полным?

Все операции категории
`organized_market_securities_outside_iis` для `taxpayer-proof-1` за 2025 год
в exact member set текущего scope binding.

### Кто это утверждает?

Пользователь/case boundary через structured `user_verified_fact`.

Не Gate 4, не aggregator и не LLM.

### На чём основано утверждение?

На отдельном structured assertion, который ссылается на SHA-256 конкретного
taxpayer/category/period/member scope. Документального доказательства полной
налоговой истории этот proof не заявляет.

### Что произойдёт при появлении нового документа или операции?

Появится новая operation model, изменится member set и его binding hash.
Старое completeness evidence станет несовместимым и runtime остановится.

### Можно ли считать старый aggregate complete?

Нет. Для нового exact set требуется новое completeness assertion.

## normalization_run_id и multiple sources

Representative proof строит каждую operation model через G5.13 в её текущем
trusted source scope и агрегирует уже разрешённые модели. Поэтому G5.3/G5.5
same-run binding не блокирует этот post-resolution slice.

G5.14 не делает cross-run Supplemental discovery, rebinding или migration.
Эта lifecycle-задача остаётся за пределами GOAL.

## Gate 4 immutability

До и после aggregation тест сравнивает официальные Gate 4 facts для обеих
операций: они идентичны. Новый runtime не импортирует Gate 4, ArtifactStore,
Supplemental boundary, SQL или source readers.

## Architecture/test integrity

Первый расширенный architecture replay дал один assertion failure:

```text
expected: every added package module belongs to the exact declared set
actual: stacked Gate 5 modules, включая новый G5.14 module, отсутствовали
        в historical package-module allowlist test
```

Authority map уже объявлял эти modules самостоятельными inactive contract
authorities. Исправлен exact allowlist; условие не ослаблено. Повторный exact
test прошёл.

Test isolation: каждый proof использует temporary SQLite/payload root,
отдельные case/run IDs; `monkeypatch` восстанавливает synthetic Gate 4 fixture
maps после теста. Необратимой boundary в aggregation нет: runtime ничего не
пишет, а observable result и неизменность Gate 4 проверяются напрямую.

## Verification

Terminal checks из service cwd
`services/broker-reports-gate1-proof`:

```text
focused G5.14:
5 passed in 2.09s

all Gate 5 tests:
51 passed, 2978 deselected in 14.35s

architecture/current-boundary replay after exact allowlist repair:
113 passed, 1 skipped in 49.09s

successor-hash and comparative evidence checks:
24 passed, 2 skipped in 2.02s

ruff check/format for changed G5 runtime/authority/focused-test files:
passed

closed-world package import/resource read and forbidden-path scan:
passed
```

Full service suite was attempted with a 600-second command limit. The process
remained alive for 603 seconds and produced no pytest summary before external
timeout; teardown then reported stdout flush `OSError 22`. Therefore:

```text
FULL_SUITE_TERMINAL_VERDICT = NOT_OBTAINED_TIMEOUT
```

Это не записано ни как pass, ни как assertion failure.

## KISS

Добавлены:

- один additive operation-only method в существующем G5.13 owner;
- одна отдельно hash-pinned methodology version;
- один scope/aggregation runtime;
- один focused test module;
- один supporting contract и этот report.

Не созданы Tax Case, TaxPortfolio, TaxLedger, DB/table, workflow, relation
graph, generic aggregation/query engine, LLM flow, tax base/rate/tax или новый
declaration owner.

## Stop

G5.14 закрыт. Следующий Gate 5 slice не начат.
