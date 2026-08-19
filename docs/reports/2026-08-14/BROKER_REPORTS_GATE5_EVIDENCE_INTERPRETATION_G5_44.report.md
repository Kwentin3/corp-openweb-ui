# Broker Reports G5.44 — Evidence Interpretation Contracts

Дата: `2026-08-14`

Статус: `CONTRACTS PROVEN WITH EXTERNAL LEGAL GAPS`

```text
EVIDENCE_INTERPRETATION_CONTRACTS_PROVEN
COMMISSION_SELECTION_CONTRACT_PROVEN
ACQUISITION_BASIS_COVERAGE_CONTRACT_PROVEN
RESIDENCY_EVIDENCE_BOUNDARY_PROVEN
CROSS_DOMAIN_REFACTOR_CONSISTENCY_PROVEN
```

## Результат

G5.44 закрыл четыре runtime-контракта, не расширяя юридическую методологию.
Резидентство теперь выводит только hash-pinned methodology из typed evidence;
detail/aggregate комиссии выбираются по доказанному coverage без сравнения и
double count; нехватка базы приобретения выражается отдельным количественным
`ACQUISITION_BASIS_COVERAGE_GAP`; same-row charge остаётся source context и не
становится вычетом без независимых Tax Model evidence flags.

Прямой ответ пользователя «я резидент» не является authoritative input.
LLM/adapter может предложить только интервалы и причины, которые затем
буквально сверяются с authenticated answer. Tax Model, Tax-Period Aggregation
и Income Group Base принимают residency только с provenance
`methodology_derived_result`.

## A-I black-box proof

| Case | Наблюдаемый результат |
| --- | --- |
| A | естественный русский ответ → typed intervals → 183 дня → `RESIDENT`; прямой status без intervals → insufficiency |
| B | только detail-комиссии → выбран detail |
| C | только matching aggregate → выбран aggregate |
| D | details и aggregate сохранены; выбрано ровно одно представление |
| E | detail 25 и aggregate 40 не чинятся и не сравниваются; при доказанном detail coverage выбран detail |
| F | detail coverage не доказан: matching aggregate выбирается, без него — `FAIL_CLOSED` |
| G | покупка 70 / продажа 100 → supported 70, gap 30; relation и zero-cost не создаются |
| H | один lot 100 / десять продаж по 10 → 10 transient FIFO calculations, 0 stored pairs |
| I | same-row charge с недоказанным `documented` → `not_allowed_unproven`; allowable expenses не включают charge |

## Producer → Contract → Consumer

| Meaning | Producer | Contract owner | Consumer |
| --- | --- | --- | --- |
| residency evidence | authenticated human boundary | `Gate5ResidencyEvidenceRuntimeFactory.create` | Tax Model / aggregation / Income Group Base через methodology-derived binding |
| commission representations | Gate 4 independent assertions | deterministic source consumer + methodology `2026.6-interpretation-contract` | ровно одна selected representation; tax eligibility отдельно |
| acquisition coverage | Gate 4 purchase/disposal observations | deterministic source consumer | client review и отдельное methodology blocking decision |
| transaction charge | exact same canonical row | deterministic source consumer | Tax Model с отдельными incurred/documented/related flags |

Projection остаётся representation-only и не содержит второго residency,
commission-selection, acquisition-gap или deductibility owner.

## Не закрыто

Четыре внешних gap из G5.43 сохранены без переименования и без fallback:

```text
ambiguous_security_disposal_source_classification
partial_acquisition_commission_allocation
non_rub_intermediate_precision_and_rounding
treaty_specific_foreign_tax_credit_limit
```

Поэтому G5.44 не означает полную налоговую готовность клиента, filing
activation или разрешение на выпуск декларации.

## Verification

Проверено:

- A-I, preparation и contract-focused slice: `32 passed`;
- все 39 Gate 5 modules: `449 passed`;
- все 15 Gate 3/4 modules: `150 passed`;
- rebuilt bundle + isolated/control XML vertical: `17 passed`, 5 только
  сторонних SWIG deprecation warnings;
- `python -m compileall`: `PASS`;
- `git diff --check`: `PASS`; выведены только существующие LF → CRLF warnings.

Read-only replay frozen real corpus: 4 документа, 186 финансовых source facts,
15 metadata facts, 9 активных demands. Результат ожидаемо
`PREPARATION_INCOMPLETE`: residency evidence отсутствует, поэтому
classification = `INSUFFICIENT_EVIDENCE`; 12 required actions (8 additional
documents, 4 user facts), 0 calculations, 0 invented facts/relations. Provider
calls — 0, frozen store до/после идентичен.

Первый inline replay не открыл store из-за искажения кириллического абсолютного
пути в stdin (`???????`). Повторный запуск через cwd-relative path прошёл; это
transport/path failure, не assertion failure и не изменение evidence.

## KISS и scope stop

Добавлен один узкий residency owner, одна append-only source methodology и три
малых typed result contracts. Новых DB, relation graph, generic rule engine,
parallel reader или projection logic нет. Existing factories переиспользованы.

Private corpus bytes/values не помещались в Git. Product activation, real-case
XML/PDF emission, commit, push и PR не выполнялись. Следующая допустимая цель —
только отдельно авторизованное закрытие конкретного внешнего legal-methodology
gap; G5.45 автоматически не начинается.
