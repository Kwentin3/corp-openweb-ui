# G5.22 — Stable Income-Group Tax Base Report

Date: 2026-08-10

Status: `G5.22_CLOSED`

Outcome: `PROVEN_WITH_REPLAY_COMPILER_LIMITATION`

Product status: `INACTIVE PROOF`

## Итог

Первый declaration-driven gap `section2_calculation_behavior_missing` закрыт
минимальным способом:

```text
existing EXECUTE capability
+ one immutable methodology version
+ one static registered deterministic behavior
+ existing G5.8/G5.14/G5.18 owners
```

Новая primitive family не появилась. Пять семейств
`RESOLVE/ACQUIRE/EXECUTE/AGGREGATE/PROJECT` и frozen Capability Contract v1 не
изменились. Новых DB/store/ACL/workflow/service/GUI owners нет.

## Что реализовано

Published identity:

```text
ru-ndfl-securities-tax-model-proof
2026.2-experimental
securities_income_group_tax_base_v0
```

Вход принимает complete G5.14 category model, explicit taxpayer status, четыре
обязательных whole-group money facts и exact hash-bound completeness. Даже
нулевые значения должны быть переданы явно. Выход — stable tax semantic:

```text
total_income
taxable_income
accepted_expenses
tax_base
```

Форма, Section 2 line IDs, codes 02/003, XML/XSD/PDF и tax rate в runtime/output
не входят.

## Requirement evidence

Backward analysis выполнен по официальному приказу ФНС
`ЕД-7-11/913@` и приложению с порядком заполнения. Пункты 37-46 требуют отдельный
расчёт по группе доходов и определяют total/non-taxable/taxable income,
deductions, accepted expenses и tax base. Источник проверен 2026-08-10:

- [страница приказа ФНС](https://www.nalog.gov.ru/rn77/about_fts/docs/16589324/);
- [официальный DOCX порядка](https://www.nalog.gov.ru/html/sites/www.new.nalog.ru/files/about_fts/docs/16589324_2.docx), SHA-256 `7bc11cad8d0465c03c834c50c7832fb2edc7291d9b4b161ef5b2c6cabdcb0fdc`.

## Runtime proof

Representative path использует реальные public owners:

```text
Gate 4-backed inputs
-> two typed G5.13 operation models
-> complete G5.14 category aggregation
-> typed G5.22 behavior
```

Результат:

```text
total income       160.00 RUB
taxable income     155.00 RUB
accepted expenses  104.00 RUB
tax base             48.00 RUB
```

Provenance содержит `financial_case`, `supplemental_fact`,
`user_provided_supplemental`, `proof_assumption`, `user_verified_fact` и
`methodology_derived`.

Fail-closed доказаны для missing/stale completeness, missing group fact,
unsupported taxpayer status, incompatible domain values, reductions above
taxable income, exact contract mismatch, output tamper и resource hash drift.
Package-copy proof подтверждает Closed World.

Final verification:

```text
focused G5.22/G5.21/G5.18/G5.14       51 passed
all Gate 5 plus KT1 architecture      153 passed, 1 pre-existing warning
architecture/hash-authority suites     81 passed, 2 skipped
ruff focused changed Python             passed
Markdown/JSON/links/UTF-8 validation    passed
git diff --check                         passed
```

## Independent replay

Заморожен отдельный history-free G5.22 payload; G5.21 payload не менялся:

```text
payload bytes   26614
payload sha256  cd186b746aabbe699820e4ec58bd08a8cfd1e7041de373af0d4d2ee971267736
bias audit      passed, zero disallowed hits
provider calls  1
retry/followup  0/0
manual repairs  0
```

Candidate сохранён без изменений:

```text
candidate bytes   17613
candidate sha256  dee9cec002449e31ae7536a36e1a897fe2df1c7355f65ec999c7723cf5d70bf2
JSON parse        passed
closed schema     passed
```

Модель естественно использовала новый behavior. Старый
`section2_calculation_behavior_missing` отсутствует. Первым blocker она назвала:

```text
gap.singleton_category_aggregation
```

Аудит подтвердил, что это реальная более ранняя граница: G5.14 сейчас требует
минимум две операции и не принимает exact-complete category из одной операции.
В рамках G5.22 это не исправлялось.

Ограничение replay сохранено явно: deterministic compiler отклонил неизменный
candidate позже, на `requirements[6].compositions[1]`, потому что модель указала
PROJECT composition без artifact для unsupported projection requirement. Это
не было исправлено, не ретраилось и не использовалось для выбора другого
candidate. Поэтому replay доказывает исчезновение старого gap и независимое
обнаружение следующего, но не даёт нового compilation-pass доказательства
языка G5.21.

## Evidence files

- `BROKER_REPORTS_GATE5_SECTION2_CALCULATION_SEMANTICS_G5_22.plan.safe.json` — frozen pre-inference record;
- `BROKER_REPORTS_GATE5_SECTION2_CALCULATION_SEMANTICS_G5_22.candidate.json` — exact model output;
- `BROKER_REPORTS_GATE5_SECTION2_CALCULATION_SEMANTICS_G5_22.compilation.safe.json` — unchanged-candidate compiler audit;
- `BROKER_REPORTS_GATE5_SECTION2_CALCULATION_SEMANTICS_G5_22.trial.safe.json` — safe invocation/audit receipt.

## KISS check

Добавлены одна methodology version, один небольшой behavior owner, одна static
binding и аддитивный inventory replay. G5.14 получил только public downstream
validator на том же factory-created runtime. Formula DSL, dynamic loader,
generic Tax Engine и declaration-specific orchestration не создавались.

## Stop

Не реализованы:

- singleton-category aggregation;
- Section 2 classification/projection artifact;
- full electronic declaration composition;
- XML/PDF, rate/tax, runner, case execution или product activation.

Следующий declaration-discovered blocker — `gap.singleton_category_aggregation`.
Продвижение к нему этим отчётом не авторизовано.
