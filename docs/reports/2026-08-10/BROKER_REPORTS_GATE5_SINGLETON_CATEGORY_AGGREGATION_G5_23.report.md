# Broker Reports Gate 5 Singleton Category Aggregation — G5.23

Date: 2026-08-10

Status: `G5.23_CLOSED`

Outcome: `RESEARCH_SCAR_REMOVED`

Product status: `INACTIVE PROOF`

## Ответ

Ограничение `member_count >= 2` не было налоговым или safety invariant. Оно
возникло в G5.14 как условие representative proof A+B, нужное для демонстрации
сложения двух операций, и затем было дословно перенесено в runtime, supporting
contract и model-visible Capability Contract.

Текущая корректная cardinality:

```text
complete category member set = 1..N
```

Singleton проходит тот же `AGGREGATE COMPLETE SCOPE` owner. Отдельная
completeness остаётся обязательной; одна известная операция сама по себе не
становится complete category.

## Attribution до реализации

Проверены code, первоначальный commit `02659a9`, G5.14 report/contract, tests,
G5.15 capability publication, G5.17 audit, G5.20/G5.22 candidates и architecture
map.

| Проверка | Результат |
| --- | --- |
| runtime admission | единственный отказ — `len(value) < 2` в member validator |
| downstream Category Tax Model validator | повторял тот же `len(value) < 2` |
| exact scope binding | canonical hash уже принимает обычный sorted list; зависимости от двух members нет |
| known-value aggregation | один общий цикл суммирования; identity case естественно работает для одного member |
| completeness | exact scope/member SHA-256; cardinality два не используется |
| duplicates | проверяются refs и model hashes независимо от minimum cardinality |
| consensus | period/category/currency/loss/methodology проверяются относительно scope и members; minimum два не является условием scope agreement |
| history | G5.14 contract вводит minimum одновременно с representative A+B proof |
| причина A+B | доказать сложение, ordering, разные expense meanings и stale A+B против A+B+C |
| domain evidence | причины запрещать exact category из одной операции не найдено |

Наблюдаемое несоответствие до fix:

```text
expected: non-empty exact compatible member set reaches ordinary aggregation
actual:   one valid member fails gate5_tax_period_members_invalid before safety checks
```

Это классический переход:

```text
proof fixture assumption
        -> runtime invariant
        -> public machine contract
        -> LLM correctly reports the artificial gap
```

## Official-source cross-check

Проверено 2026-08-10. Приказ ФНС № ЕД-7-11/913@ утверждает форму, порядок и
электронный формат для налогового периода 2025. Опубликованная XSD описывает
повторяемый category occurrence `ДохОперЦБ` и aggregate value `ДохСовОпер`, но
не задаёт minimum две исходные операции.

Это supporting negative evidence. XSD не является owner внутренней
operation-member completeness.

## Минимальная реализация

В прежнем
`Gate5TaxPeriodCategoryAggregationRuntimeFactory.create` обе проверки заменены
на non-empty list validation:

```text
not a list OR empty -> gate5_tax_period_members_invalid
otherwise           -> unchanged validation and aggregation path
```

Не добавлены:

- singleton branch;
- новый capability или behavior;
- новый Tax Model или result schema;
- новый service/completeness owner;
- declaration-specific constants;
- DSL, DB, workflow или product route.

## Safety regression

Реальный operation model строится прежним G5.13 factory path. Для exact set из
одной операции доказано:

- `describe_scope` возвращает binding с одним exact model hash;
- без completeness evidence возвращается `incomplete_scope`, known values и
  отсутствуют Category Tax Model/declaration fragment;
- с exact `user_verified_fact` возвращается complete Category Tax Model и
  существующий Appendix 8 projection;
- gross/related/allowable values совпадают с вкладом единственного member;
- downstream G5.22 category validator принимает тот же model;
- изменение единственного `operation_ref` делает старый completeness binding
  stale и fail-closed;
- zero members остаются invalid.

Существующие negative proofs продолжают закрывать wrong period/category,
mixed currency, incompatible loss/methodology, incomplete/unknown model,
duplicate operation ref, duplicate model content и ambiguous identity.

## Contract/versioning decision

Runtime fix backward compatible: все прежние valid `2..N` requests имеют те же
ID, inputs, outputs и результат. Поэтому capability ID и aggregation result
schemas не менялись.

Но immutable model-visible v0/v1 resources нельзя переписать после G5.18-G5.22.
Опубликован additive Runtime Capability Contract v2:

```text
same five capability IDs
aggregate precondition: at_least_one_complete_operation_model
explicit failure: empty_operation_member_set
resource SHA-256: f35ca4cb5ef8a218b3eab0e287c76b69aeb687ad1741d6196ff6889d547209cc
```

v1 SHA-256 остался
`e5134005e3715e70249f14dd1918ce4d110e70bb6eba1304ccbd9204c1531e8f`.
G5.14 v0 contract сохранён как historical A+B evidence; current aggregation
contract — v1.

## History-free replay

Новый payload построен из неизменённых G5.22 official evidence, inventory,
output schema и research policy. Изменены только:

- current Runtime Capability Contract v2 projection;
- одно generic language clarification: executable composition должна содержать
  все подходящие required published artifacts, иначе unsupported semantic
  остаётся только typed gap.

Clarification не содержит singleton, старого candidate/compiler error,
ожидаемого requirement/gap или roadmap.

Pre-inference:

```text
trial_id          g5.23-history-free-replay-2026-08-10-001
payload bytes     26898
payload SHA-256   62fde21f4bc75d32deebf3ac9c650b4506d5f269d3392c6ba97c3af3695a7a9d
history           none
workspace items   0
provider schema   none
retry/follow-up   0/0
bias audit        passed
```

Ровно один `gpt-5.6-sol` inference завершился terminally. Exact final-message
candidate:

```text
bytes             11146
SHA-256           1b681477ee6f3d09cf69ca533f42d53cebb26397912f57ccbf362c5decce7b4b
plain JSON parse  passed
closed schema     passed
compiler          passed
manual repair     0
```

Старый `gap.singleton_category_aggregation` отсутствует. Модель независимо
выделила:

```text
first blocker: section2_validated_projection_artifact_missing
related gap:   section2_projection_contract_incompatible
```

Candidate использует существующий calculation behavior как supported
sub-semantic, но не придумывает пустую PROJECT composition. Итог compiler:
`partially_compilable`, 3 requirements, 2 supported, 1 unsupported, 2 gaps,
7 resolved compositions.

Evidence сохранено в exact candidate, safe trial record и deterministic
compilation record рядом с этим отчётом.

## Verification

Из `services/broker-reports-gate1-proof`:

```text
focused G5.23 owners plus closed-world package copy:
52 passed in 13.88s

all Gate 5 tests plus KT1 architecture:
158 passed, 1 warning in 46.43s

authority successor hash pin:
1 passed in 1.38s

ruff for changed G5 runtime/test modules:
passed

UTF-8, JSON parse, local Markdown links, frozen hashes, authority LF hash pin,
secret-like/absolute-path scan and git diff check:
passed
```

Первый расширенный pytest command передал literal wildcard и остановился до
collection с `no tests ran`; это invocation error, не assertion failure. Тот же
набор был повторён с explicit PowerShell path list и дал terminal result выше.

Полный service suite не запускался; G5.23 закрыт scoped Gate 5/architecture
replay, а не неподтверждённым full-suite claim.

## KISS / scar audit

Исправлены только два одинаковых minimum checks у одного owner, опубликована
одна честная versioned contract projection и добавлены focused regressions.

Рядом обнаружен тот же research-scar class в historical G5.14/G5.15/G5.17
documents and frozen payloads. Они сохранены как dated evidence и явно routed
к current v1/v2 contracts; unrelated runtime scars не исправлялись.

## Scope stop

G5.23 закрыт. Не начаты:

- Section 2 validated projection artifact;
- Section 2 declaration projection contract;
- classification/projection/electronic XML;
- rate/tax or new inputs;
- новая capability;
- product activation.

Следующая обнаруженная boundary —
`section2_validated_projection_artifact_missing`. Её реализация требует
отдельного разрешённого GOAL.

## Official sources

- [FNS order ED-7-11/913@](https://www.nalog.gov.ru/rn77/about_fts/docs/16589324/)
- [FNS XSD 5.20.01](https://www.nalog.gov.ru/html/sites/www.new.nalog.ru/files/about_fts/docs/xsd/NO_NDFL3_1_033_00_05_20_01.xsd),
  downloaded SHA-256
  `083128322833dbafb29be0bf919e33b7b362956244b422d34dd554c99a1e4484`
