# Broker Reports GOAL G3.0 — Gate 3 Financial Domain Foundation

Status: `COMPLETED`

Date: 2026-08-06

Repository baseline: `main == origin/main == 288f7a8439baba558ebe2d70e1fb0699f8f163b7`

Scope: read-only architecture audit and implementation-program definition.
Code, runtime, product flags, stage and provider routes were not changed;
provider calls were not made.

## 1. Terminal decision

```text
GOAL_G3_0 = COMPLETED
GATE3_INPUT_AUTHORITY = CONFIRMED
GATE3_OUTPUT_AUTHORITY = VERSIONED_SUCCESSOR_REQUIRED
CANONICAL_TO_FINANCIAL_BRIDGE = VERSIONED_BRIDGE_REQUIRED
EXISTING_FINANCIAL_PIPELINE_REUSE = HIGH
FINANCIAL_TAXONOMY_COVERAGE = PARTIAL_WITH_GAPS
FINANCIAL_SCOPE_TOTALITY = DEFINED
MODEL_ROLE = BOUNDED_SEMANTIC_CHOICE
MODEL_QUALIFICATION = NOT_REQUIRED_FOR_INITIAL_IMPLEMENTATION
MANAGED_FINANCIAL_DOMAIN = CREATE_V2
NDFL_METHODOLOGY_IN_GATE3 = ZERO
GATE3_IMPLEMENTATION_PROGRAM = READY
```

`MODEL_QUALIFICATION = NOT_REQUIRED_FOR_INITIAL_IMPLEMENTATION` означает только,
что контракт, canonical bridge, детерминированный учёт, сохранение
`unclassified` и Managed Financial Domain v2 можно реализовать без модели и без
provider calls. До публикации model-dependent typed records или любой
активации потребуется отдельная новая квалификация модели.

## 2. Ответ простыми словами

1. Gate 3 получает только активную, валидированную версию
   `CanonicalArtifactV1` через публичный `CanonicalReaderFactory.create`.
2. Gate 3 выдаёт версионированный финансовый домен: typed и unclassified
   records, unsupported/no-input outcomes, provenance и доказательство полного
   учёта документа. Это не налоговый расчёт.
3. Сейчас отсутствует нормативный переход от reader-visible canonical nodes и
   tables к финансовым occurrences/scopes и Financial Evidence.
4. Сохраняются Pack, Evidence Bundle, Candidate Compiler, Typed Options,
   Semantic Choice, Expansion, validator/materializer, persistence и query
   механизмы. Историческое имя `Gate2*` само по себе не делает компонент
   непригодным.
5. Нужны версионированный canonical bridge, Financial Evidence Source Package
   v2 и Managed Financial Domain v2; несколько соседних контрактов требуют
   минимальной адаптации.
6. Текущий словарь недостаточен для полного брокерского отчёта: доказаны лишь
   узкие balance/printed-total основы, остальные семейства имеют явные gaps.
7. Financial Domain v1 даёт хорошую основу, но не выражает требуемую
   пятиисходную totality и не закрепляет snapshot за точной canonical version;
   нужен v2.
8. Языковая модель нужна только там, где после детерминированной подготовки
   остаётся выбор между заранее созданными code-owned options. Она не создаёт
   факты, значения, IDs, refs или полноту.
9. Неопределённые данные становятся first-class `unclassified` records;
   неподдержанные и нефинансовые scopes остаются видимыми coverage outcomes.
10. На реальном авторизованном корпусе нужно отдельно исследовать сделки,
    доходы, дивиденды, купоны, комиссии, удержанные налоги, cash movements, FX,
    client positions, instruments и corporate actions.
11. Налоговое резидентство, FIFO, cost basis, tax FX, netting, перенос убытков,
    ставки, льготы и declaration mapping относятся к следующему этапу НДФЛ.
12. Следующие GOAL идут от контрактов и bridge к taxonomy, evidence/options,
    bounded choice, MFD v2, totality, actual-corpus proof, новой model
    qualification, shadow и только затем controlled cutover.

## 3. Нормативная база и метод аудита

Текущую authority задают, в порядке приоритета:

- [Pipeline Gates v1](../../stage2/contracts/BROKER_REPORTS_PIPELINE_GATES.v1.md);
- [Architecture Authorities](../../stage2/contracts/BROKER_REPORTS_ARCHITECTURE_AUTHORITIES.md);
- [Canonical Artifact v1](../../stage2/contracts/BROKER_REPORTS_CANONICAL_ARTIFACT.v1.md)
  и его schema;
- [Gate 3 Handoff v1](../../stage2/contracts/BROKER_REPORTS_GATE3_HANDOFF.v1.md);
- текущий maintained code и focused tests;
- versioned финансовые контракты и только затем historical reports/receipts.

Исторические документы использованы как evidence, а не как право изменить
текущую нумерацию gate или current code. Аудит проверил contracts, factories,
code dependencies, Semantic Pack, source/evidence/choice/materialization chain,
Managed Financial Domain, actual-corpus inventory, KT2/KT2.1 и terminal model
qualification evidence.

## 4. Нормативный вход Gate 3

Решение: `GATE3_INPUT_AUTHORITY = CONFIRMED`.

```text
CanonicalReaderFactory.create
→ read_active_envelope
→ active validated CanonicalArtifactV1
→ Gate 3
```

[Pipeline Gates v1](../../stage2/contracts/BROKER_REPORTS_PIPELINE_GATES.v1.md)
определяет validated `CanonicalArtifactV1` как точный output Gate 2, а active
validated canonical version — как input Gate 3. [Gate 3 Handoff
v1](../../stage2/contracts/BROKER_REPORTS_GATE3_HANDOFF.v1.md) закрепляет тот же
путь через `CanonicalReaderFactory.create` и запрещает direct storage/layout
access, format branching, re-normalization и silent legacy fallback.

`CanonicalArtifactV1` достаточен как контрактный источник для bridge, потому
что сохраняет:

- ordered containers, nodes, list items и tables;
- table title/header/notes, ordered rows и cells;
- raw/displayed cell values и structural metadata;
- source refs, compact provenance, issues, conflicts и ambiguities;
- deterministic completeness и immutable canonical version/root identity.

Он намеренно не содержит financial type/role/tax meaning. Это правильная
граница: Gate 3 добавляет финансовую семантику, не переписывая source meaning.
Фактическая достаточность всех полей на расширенном реальном брокерском корпусе
остаётся предметом отдельной qualification, а не blocker для начала bridge.

`gate2_handoff_v0` остаётся временной product compatibility authority при
выключенном global canonical read. Gate 3 не получает право читать этот legacy
handoff в обход canonical reader.

## 5. Нормативный выход Gate 3

Решение: `GATE3_OUTPUT_AUTHORITY = VERSIONED_SUCCESSOR_REQUIRED` и
`MANAGED_FINANCIAL_DOMAIN = CREATE_V2`.

Existing [Managed Financial Domain
v1](../../stage2/contracts/BROKER_REPORTS_MANAGED_FINANCIAL_DOMAIN.v1.md) уже
даёт сильную основу:

- immutable snapshot;
- typed и first-class unclassified records;
- pinned Semantic Pack identity;
- catalog, coverage и provenance;
- persistence, deterministic query и authorization boundary;
- strict completeness/query behavior.

Но v1 недостаточен для текущего Gate 3:

1. Coverage имеет четыре outcomes — `typed`, `unclassified`,
   `no_financial_input`, `unsupported` — и не имеет per-scope
   `blocking_failure`.
2. Snapshot сохраняет historical source-extraction/Gate2 run refs, но не
   закрепляет результат за exact canonical artifact version/root и bridge
   identity.
3. Нужен отдельный occurrence-ownership receipt: scope-level terminal outcome
   сам по себе не доказывает, что все canonical source occurrences учтены
   ровно один раз.
4. Сам v1 требует новую contract version при изменении terminal ownership,
   completeness или provenance meaning.

Поэтому v1 нельзя «тихо расширить». MFD v2 должен сохранить совместимые
механизмы v1, но добавить exact canonical binding, bridge/Pack versions,
пятиисходную scope totality и occurrence ownership.

## 6. Недостающий canonical-to-financial bridge

Решение: `CANONICAL_TO_FINANCIAL_BRIDGE = VERSIONED_BRIDGE_REQUIRED`.

В maintained code текущий deterministic financial scope factory принимает
`gate1_packages`, а
[`Gate2FinancialEvidenceBundleFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate2_financial_semantic_v6_bundle.py)
принимает historical `source_package` вместе с `gate1_packages`. Финансовый
contour не читает `CanonicalArtifactV1` через `CanonicalReaderFactory`.

Текущий
[`FinancialEvidenceSourceLineage`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate2_financial_evidence_source_package.py)
умеет page/table/row/cell/text-segment lineage, но не имеет общей identity для
container/node/source occurrence всех поддержанных canonical formats. Поэтому
одного compatibility wrapper недостаточно: меняется boundary contract и
provenance identity.

Нужен один `Canonical Financial Bridge v1`:

```text
reader envelope
→ exact canonical version/root validation
→ ordered canonical source occurrences
→ deterministic financial scopes plus bounded structural context
→ Financial Evidence Source Package v2
```

Bridge обязан:

- принимать только reader envelope активной validated canonical version;
- не читать ArtifactStore, PDF pages, XLSX sheets или private engineering
  evidence напрямую;
- не ветвиться по source format для финансовой семантики;
- сохранять literal/raw/displayed values, order, headers, row/table/section
  context, source refs, issues и provenance;
- создавать stable occurrence IDs и scope IDs детерминированно;
- отделять primary ownership от повторно используемых context refs;
- не назначать financial types и не фильтровать «непонятные» данные;
- переносить blocking canonical issues как code-owned blocking outcome;
- выдавать completeness/ownership receipt, проверяемый независимо;
- не становиться вторым parser, normalizer или финансовым pipeline.

## 7. Целевая архитектура

```text
CanonicalReaderFactory.create
→ active validated CanonicalArtifactV1
→ Canonical Financial Bridge v1
→ Financial Evidence Source Package v2
→ Evidence Bundle
→ Candidate Compiler
→ Typed Options
→ bounded Semantic Choice OR code-owned technical terminal
→ Expansion
→ Validation
→ Materialization
→ Managed Financial Domain v2
→ Persistence / Query API
```

`no_financial_input`, `unsupported` и `blocking_failure` определяет код до/вне
model choice. Модель не получает эти outcomes как возможность скрыть источник.

## 8. Переиспользование существующего финансового контура

| Компонент | Решение | Обоснование и требуемое изменение |
| --- | --- | --- |
| Financial Semantic Pack | `MINIMALLY_ADAPT` | Выпустить новую semantic version после actual-corpus taxonomy research; сохранить Pack единственным владельцем type/role/ambiguity meaning. |
| Registry | `MINIMALLY_ADAPT` | Использовать как compiled projection Pack; убрать самостоятельные legacy meanings после миграции, не создавать второй словарь. |
| Financial Evidence Source Package | `VERSIONED_SUCCESSOR_REQUIRED` | v2 должен быть canonical-bound и иметь generic occurrence/container/node lineage. |
| Evidence Bundle | `MINIMALLY_ADAPT` | Сохранить exact values, associations, retention set и provenance; заменить historical source input на Source Package v2. |
| Candidate Compiler | `REUSE_AS_IS` | Уже создаёт complete code-owned options из Pack и technical evidence. |
| Typed Options | `REUSE_AS_IS` | Оpaque/prebound options сохраняют type/value/ref authority в коде. |
| Semantic Choice | `REUSE_AS_IS` | Сохранить bounded choice или safe no-choice; model output не является record. |
| Expansion | `REUSE_AS_IS` | Восстанавливать только заранее sealed bindings и retention. |
| Validation | `MINIMALLY_ADAPT` | Добавить canonical version/bridge/totality bindings и MFD v2 invariants. |
| Materialization | `MINIMALLY_ADAPT` | Сохранить sole code-owned record creation; выдавать MFD v2 terminal outcomes. |
| Managed Financial Domain | `VERSIONED_SUCCESSOR_REQUIRED` | v2 нужен из-за нового terminal ownership/completeness/provenance meaning. |
| Persistence | `MINIMALLY_ADAPT` | Хранить immutable v2 snapshots и новые indexes/receipts без in-place upgrade. |
| Query API | `MINIMALLY_ADAPT` | Сохранить snapshot-bound pagination/filtering; экспонировать новые coverage/receipt поля. |
| Gate 3 Financial Domain Context | `REUSE_AS_IS` | Использовать только как downstream read projection над MFD, не как builder или bridge. |
| KT2/KT2.1 bounded context guard | `MINIMALLY_ADAPT` | Перевести structural context на canonical scopes; сохранить fail-closed typed guard. |

Итог: reuse высокий. Новый код оправдан только на двух реальных boundary gaps —
canonical bridge/source package и MFD v2.

## 9. Финансовая таксономия

Решение: `FINANCIAL_TAXONOMY_COVERAGE = PARTIAL_WITH_GAPS`.

Текущий managed Pack имеет `authority_status=target_normative_not_live`,
`runtime_activation=false` и только два target type:
`cash_balance_snapshot_v1` и `printed_financial_metric_v1`. Остальные десять
financial-statement candidates отложены. Исторические broad router/fact IDs не
становятся нормативными типами автоматически.

[Actual-corpus inventory](../2026-07-23/BROKER_REPORTS_GATE2_CANONICAL_DOMAIN_GOAL1_ACTUAL_CORPUS_CONCEPT_INVENTORY.report.md)
охватывает 6 private документов и 9 bounded crops. Это преимущественно
broker-dealer financial statements/schedules, не client transaction feeds.

| Семейство | Текущий нормативный тип | Реальный evidence/status | Минимально нужные значения и связи | Открытый gap / следующее исследование |
| --- | --- | --- | --- | --- |
| Сделки с ценными бумагами | Нет | Не доказано на текущем actual corpus | trade/settlement dates, side, quantity, price, gross/net, currency, instrument, fee/tax links, correction identity | Авторизованный multi-broker trade corpus; cancellations, partial fills, lots, accrued interest. |
| Доходы | Нет | Не доказано | income kind, accrual/payment date, gross/net, currency, payer/account/instrument refs | Отличить cash receipt, accrual, realized result и printed aggregate. |
| Дивиденды | Нет | Не доказано | instrument/issuer, record/pay dates, gross, withheld, net, currency, country/source refs | ADR, multi-currency, reversals, tax-at-source links. |
| Купоны | Нет | Не доказано | instrument, coupon/accrual period, payment date, gross/withheld/net, currency | Coupon vs accrued interest vs redemption; amortization. |
| Комиссии | Нет | Не доказано | fee kind, date, amount, currency, linked trade/service/cash movement | Included-vs-separate fees, rebates, recurring custody fees. |
| Удержанные налоги | Нет | Не доказано | tax kind, jurisdiction, gross basis, amount, currency, event/income link, source-stated rate | Source-stated withholding only; creditability and Russian tax treatment are outside Gate 3. |
| Движения денежных средств | Нет | Не доказано | date/value date, direction, amount, currency, account, counterparty, purpose, linked event | Transfer vs income vs fee vs FX leg; reversals and internal transfers. |
| Валютные операции | Нет | Не доказано | both currency legs, amounts, rate, dates, fees, account refs, operation identity | Trade vs conversion vs valuation; no tax FX calculation in Gate 3. |
| Позиции | Нет | Current corpus has one security inventory/financing balance candidate, not a proven client position type | instrument/account, quantity, as-of date, price/value basis, currency, long/short, source scope | Separate client positions from broker inventory/financing balances. |
| Финансовые инструменты | Нет самостоятельной entity authority | Не доказано | stable source identity, name, ISIN/ticker/other IDs, asset class, issuer, currency, lifecycle links | Identifier conflicts, aliases, derivatives and instrument master boundaries. |
| Корпоративные действия | Нет | Не доказано | event type/date, instrument before/after, ratios, cash/securities legs, linked positions/income | Splits, mergers, spin-offs, redemptions, rights and broker-specific corrections. |
| Балансовые показатели | `cash_balance_snapshot_v1`; другие statement candidates deferred | Cash snapshot seen in 3 crops; broader line-item/state taxonomy partial | amount, unit/currency, as-of date/period, entity/account/statement scope, concept and sign basis | Prove statement line items, receivables/payables/equity/allowances/lease balances across families. |
| Напечатанные итоги | `printed_financial_metric_v1` | Printed totals seen in 3 crops; target normative, not live | printed amount, unit/currency, period/scope, label/context, exact source refs | Distinguish duplicate subtotal, calculated total, hidden adjustments and repeated occurrences. |

Текущий Pack достаточен только для начала узкого fail-closed Gate 3, где всё
неподтверждённое сохраняется `unclassified`/`unsupported`. Он недостаточен для
полного НДФЛ-потребителя или универсального broker domain.

## 10. Роль модели и квалификация

Решение: `MODEL_ROLE = BOUNDED_SEMANTIC_CHOICE`.

```text
код строит evidence
→ код создаёт допустимые options
→ модель выбирает option или safe no-choice
→ код валидирует sealed decision
→ код expands prebound values/refs
→ код materializes record
```

Полностью детерминированны:

- canonical read/version validation;
- occurrence/scope identity и source accounting;
- extraction of literal values and structural context;
- technical outcome `no_financial_input`, `unsupported`, `blocking_failure`;
- Pack loading, candidate compilation, option IDs и allowed bindings;
- response schema/parsing, expansion, validation, record IDs, provenance;
- completeness, dedup policy, persistence и query behavior.

Модель допустима только для неоднозначного semantic selection между bounded
options. При неуверенности или недостаточном контексте результат — code-owned
`unclassified`, а не fallback, retry, invented type или guessed record.

[KT2](../2026-07-31/BROKER_REPORTS_KT2_SAME_SOURCE_TYPE_FIRST_PROOF.report.md)
доказал inactive type-first mechanical seam. [KT2.1](../2026-07-31/BROKER_REPORTS_KT21_CONTEXT_SUFFICIENCY.report.md)
показал, что amount/date/currency недостаточны: три реальные row-window units
не имели полного document/section/table context и законно завершились
`INSUFFICIENT_SEMANTIC_CONTEXT → unclassified_financial_input`.

Текущей qualified production-модели нет. GOAL12 выполнил 8 submissions без
retry/fallback/repair: OpenAI Nano и Anthropic Haiku прошли technical smoke, но
провалили semantic smoke; Google fail-closed до transport/semantic admission.
`production_admissions=[]`. Новая model qualification нужна позже как
отдельный GOAL, после готовности real canonical scopes и Pack v2.

## 11. Полнота и terminal ownership

Решение: `FINANCIAL_SCOPE_TOTALITY = DEFINED`.

### 11.1 Единицы учёта

- `source occurrence` — один canonical node occurrence, list-item occurrence
  или table-cell occurrence; это атом первичного учёта.
- `financial scope` — одна decision unit: table row либо text/list/note unit с
  явно перечисленным bounded structural context.
- Каждый occurrence имеет ровно одного primary scope owner.
- Header, group label, title, note или соседний row может повторно входить как
  context ref, но это не создаёт второго primary ownership.

### 11.2 Terminal outcomes

Каждый declared financial scope получает ровно один outcome:

```text
typed
unclassified
no_financial_input
unsupported
blocking_failure
```

- `typed`: type и все обязательные roles безопасно доказаны.
- `unclassified`: финансовое содержание присутствует, но safe type/roles не
  доказаны; exact values и refs сохраняются.
- `no_financial_input`: детерминированно доказано отсутствие финансового
  содержания в scope.
- `unsupported`: финансовое содержание есть, но Pack/implementation его пока
  не поддерживает.
- `blocking_failure`: integrity, canonical issue, missing occurrence ownership
  или другая fail-closed ошибка запрещает usable publication.

### 11.3 Правила totality

```text
declared_occurrences
= exactly_once_primary_owned_occurrences

declared_scopes
= typed + unclassified + no_financial_input + unsupported + blocking_failure
```

- Один occurrence не может иметь два primary owners.
- Scope не может иметь два terminal outcomes.
- Повторяющиеся printed totals остаются разными source occurrences; dedup
  допускается только через отдельный explicit identity/dedup receipt, не через
  удаление источника.
- `unclassified` и `unsupported` совместимы с complete domain, если сохранены
  полностью и учтены.
- Любой `blocking_failure`, uncovered occurrence, duplicate ownership или
  conflicting terminal outcome запрещает публикацию usable domain snapshot.

## 12. Граница с НДФЛ

Решение: `NDFL_METHODOLOGY_IN_GATE3 = ZERO`.

Gate 3 владеет только source-stated financial reality:

- source-stated event/state/aggregate type;
- literal amounts, quantities, dates, periods и currencies;
- instrument/account/counterparty identifiers, если они присутствуют;
- source-stated fees и withheld taxes с evidence links;
- ambiguity, unsupported и completeness state.

Следующий этап владеет:

- tax residence и tax treatment;
- FIFO/иной метод списания и cost basis;
- налоговый валютный пересчёт;
- loss carryforward и netting;
- ставки, льготы и creditability удержанного налога;
- declaration field mapping, расчёт и export.

Наличие поля `withheld_tax` в source financial record не означает решение о
зачёте этого налога по НДФЛ.

## 13. Классификация исследований и evidence

| Артефакт/контур | Классификация | Что можно использовать | Что нельзя считать доказанным |
| --- | --- | --- | --- |
| Pipeline Gates v1, Authority Map, Canonical Artifact/Reader, Gate 3 Handoff | `CURRENT_AUTHORITY` | Gate boundaries, sole reader, canonical meaning и prohibitions | Реализацию или activation Gate 3. |
| Existing Pack/evidence/compiler/options/choice/expansion/materializer/MFD code | `REUSABLE_IMPLEMENTATION` | Tested mechanisms и factory boundaries после versioned adaptation | Соответствие новому canonical input без bridge. |
| 2026-07-23 actual-corpus concept inventory | `ACTUAL_CORPUS_EVIDENCE` | Balance/printed-total concepts и explicit corpus gaps | Transaction, tax или universal broker taxonomy. |
| KT2 same-source type-first | `SYNTHETIC_PROOF` с real package structure | Mechanical bounded-option seam и code authority | Real-model quality, product path или sufficient source context. |
| KT2.1 context sufficiency | `ACTUAL_CORPUS_EVIDENCE` + `SYNTHETIC_PROOF` | Real missing-context diagnosis и fail-closed guard behavior | Typed success на реальном full-context corpus. |
| GOAL12 budget model smoke | `TERMINAL_FAILED` qualification evidence | No currently admitted model; exact no-retry/fallback accounting | Production semantic readiness. |
| Older global four-gate numbering | `SUPERSEDED` | Migration/history only | Current Gate ownership или numbering. |
| Historical `gate2_*` financial names | `HISTORICAL_EVIDENCE`/compatibility identity | Existing implementation owner mapping | Что financial semantic logic всё ещё принадлежит current Gate 2. |
| Closed, unmerged PR #232 | `RESEARCH_ONLY` | Только идеи, уже отдельно извлечённые и проверенные в KT2 | Отдельный pipeline, merged authority или production capability. |

## 14. Риски и проверка архитектуры

Основные риски:

- bridge начнёт повторно парсить formats или читать private evidence;
- headers/notes/context будут потеряны или посчитаны дважды;
- старые type names станут новой ontology без actual-corpus proof;
- unclassified исчезнет при materialization;
- MFD v1 будет расширен in place с изменением contract meaning;
- model choice получит право создавать values/refs/records;
- `complete` будет означать только «pipeline завершился», а не exact source
  accounting;
- Gate 3 начнёт выполнять tax methodology.

Обязательная validation ladder будущей реализации:

1. schema/contract validation и executable architecture guards;
2. factory-only dependency tests: reader → bridge → financial contour;
3. deterministic rebuild/equality и tamper tests;
4. per-format canonical fixtures без format branching в semantic layer;
5. occurrence and scope totality/property tests;
6. unclassified/unsupported/blocking fail-closed tests;
7. MFD v2 persistence/query round-trip и authorization tests;
8. privacy scan safe evidence;
9. actual-corpus qualification отдельно от synthetic proof;
10. exact-head CI и rollback proof до activation.

На baseline audit выбранный набор current-head tests охватил gate architecture,
canonical artifact/lifecycle, Pack, bundle/compiler/options/choice/totality,
Managed Financial Domain/query и KT2.1. Итог: `132 passed`.

Первый запуск дал `127 passed, 5 failed`: все пять failures были intentional
fail-closed storage checks, потому что системный TEMP volume имел свободное
место чуть ниже установленного порога 10%. Повтор impacted tests на volume с
достаточным запасом дал `12 passed`, затем полный выбранный набор —
`132 passed`. Это environment-capacity condition, не code regression.

## 15. Программа независимых Gate 3 GOAL

### G3.1 — Versioned Gate 3 contracts

`GOAL_NAME`: `G3.1_GATE3_VERSIONED_CONTRACTS`

`PROBLEM`: текущий input authority установлен, но canonical bridge, Source
Package v2, scope totality и MFD v2 ещё не имеют одной versioned contract set.

`OBJECTIVE`: закрепить boundary DTOs, ownership, five outcomes, canonical
binding, compatibility и migration rules до реализации.

`INPUT_CONTRACT`: Pipeline Gates v1, Canonical Artifact/Reader v1, Gate 3
Handoff v1, Semantic Pack v1, MFD v1.

`OUTPUT_CONTRACT`: Gate 3 Foundation/Bridge v1, Financial Evidence Source
Package v2 и Managed Financial Domain v2 schemas/contracts.

`REUSED_AUTHORITIES`: CanonicalReader, Semantic Pack owner, existing evidence,
materialization, persistence/query owners.

`ACCEPTANCE`: contracts имеют exact versions/schemas; один input и один output;
five outcomes и occurrence ownership формализованы; architecture guards
запрещают duplicate reader/pipeline; no tax/provider/runtime authority.

`EVIDENCE`: contract/schema validation, link checks, architecture tests,
privacy scan и exact contract diff.

`OUT_OF_SCOPE`: bridge code, taxonomy expansion, provider calls, stage,
product flags, cutover, НДФЛ.

`STOP_CONDITIONS`: canonical identity/provenance невозможно выразить без private
storage access; v2 допускает двойную authority; terminal equations нестроги.

`NEXT_ALLOWED_GOAL`: `G3.2_GATE2_CANONICAL_FINANCIAL_BRIDGE`.

### G3.2 — Canonical financial bridge

`GOAL_NAME`: `G3.2_GATE2_CANONICAL_FINANCIAL_BRIDGE`

`PROBLEM`: existing financial scopes consume historical Gate 1 packages, а не
public canonical reader envelope.

`OBJECTIVE`: реализовать один deterministic factory, превращающий validated
canonical occurrences в Source Package v2 без финансовой классификации.

`INPUT_CONTRACT`: G3.1 contracts и `CanonicalReaderFactory.create` envelope.

`OUTPUT_CONTRACT`: Financial Evidence Source Package v2 плюс exact
occurrence/scope ownership receipt.

`REUSED_AUTHORITIES`: CanonicalReader, CanonicalArtifact validator, existing
source-value/evidence value structures и integrity helpers.

`ACCEPTANCE`: PDF/HTML/CSV/XLSX fixtures проходят one public path; zero direct
store/private evidence reads; deterministic equality; every occurrence has one
primary owner; issues/conflicts propagate fail closed.

`EVIDENCE`: focused tests, import/architecture guards, tamper fixtures,
per-format counts-only receipts, zero-provider accounting.

`OUT_OF_SCOPE`: type assignment, Pack v2, model choice, MFD publication,
product activation.

`STOP_CONDITIONS`: необходим reparse/source-format semantic branch; canonical
artifact реально не содержит требуемый literal/context/ref material.

`NEXT_ALLOWED_GOAL`: `G3.3_ACTUAL_BROKER_TAXONOMY_RESEARCH`.

### G3.3 — Actual broker taxonomy research

`GOAL_NAME`: `G3.3_ACTUAL_BROKER_TAXONOMY_RESEARCH`

`PROBLEM`: current corpus proves statement balances/totals, но не transaction
families, необходимые downstream НДФЛ.

`OBJECTIVE`: на авторизованном репрезентативном corpus определить минимальные
financial type families, roles, ambiguity и lifecycle gaps.

`INPUT_CONTRACT`: Source Package v2 outputs, current Pack и research privacy
policy.

`OUTPUT_CONTRACT`: privacy-safe taxonomy decision report и versioned candidate
inventory; candidates не получают production authority.

`REUSED_AUTHORITIES`: bridge, current Pack semantics, actual-corpus evidence
method и source provenance.

`ACCEPTANCE`: каждое из 13 семейств имеет evidence count, counterexamples,
required roles, sign/date/currency/dedup questions и explicit
proven/deferred/rejected status; synthetic и actual evidence разделены.

`EVIDENCE`: aggregate safe receipts, human adjudication protocol, corpus
coverage matrix, private-value scan.

`OUT_OF_SCOPE`: Pack activation, provider/model decision, code materialization,
tax rules, product cutover.

`STOP_CONDITIONS`: корпус нерепрезентативен для заявляемого типа; source values
нельзя безопасно сохранить/исследовать; тип требует налоговой квалификации.

`NEXT_ALLOWED_GOAL`: `G3.4_FINANCIAL_SEMANTIC_PACK_V2`.

### G3.4 — Financial Semantic Pack v2

`GOAL_NAME`: `G3.4_FINANCIAL_SEMANTIC_PACK_V2`

`PROBLEM`: Pack v1 имеет только два target types и не выражает доказанную
расширенную broker taxonomy.

`OBJECTIVE`: выпустить минимальную новую Pack version только из типов,
доказанных G3.3, с явным deferred catalog.

`INPUT_CONTRACT`: G3.3 taxonomy decision и Pack v1 lifecycle/identity rules.

`OUTPUT_CONTRACT`: Semantic Pack v2, generated Registry projection и exact
managed asset identity.

`REUSED_AUTHORITIES`: existing Pack loader, validator, role/type semantics и
generated projections.

`ACCEPTANCE`: immutable IDs; roles/cardinality/ambiguity/dedup lifecycle
валидируются; no duplicate Registry authority; unproven types остаются
deferred; runtime activation false.

`EVIDENCE`: generated parity, Pack hash/identity, schema tests, negative and
counterexample fixtures.

`OUT_OF_SCOPE`: provider choice, bridge changes, model qualification, runtime
activation, tax meaning.

`STOP_CONDITIONS`: один тип смешивает event/state/aggregate; roles опираются на
недоказанные fields; Registry и Pack расходятся.

`NEXT_ALLOWED_GOAL`: `G3.5_CANONICAL_EVIDENCE_AND_OPTIONS`.

### G3.5 — Canonical evidence and typed options

`GOAL_NAME`: `G3.5_CANONICAL_EVIDENCE_AND_OPTIONS`

`PROBLEM`: existing Evidence Bundle принимает historical packages; Pack-backed
compiler ещё не доказан на Source Package v2.

`OBJECTIVE`: адаптировать evidence boundary и доказать exact retention,
associations, candidate compilation и Typed Options на canonical scopes.

`INPUT_CONTRACT`: Source Package v2 и Semantic Pack v2.

`OUTPUT_CONTRACT`: Evidence Bundle successor/compatible version, complete
Typed Options и private mapping receipt.

`REUSED_AUTHORITIES`: Evidence Bundle, Candidate Compiler, Typed Options,
integrity and deterministic rebuild validators.

`ACCEPTANCE`: every authoritative value exactly once; model-visible projection
не содержит global IDs/private refs; complete options rebuild exactly; zero
option scopes имеют code-owned terminal reason.

`EVIDENCE`: round-trip/tamper tests, retention equality, mapping coverage,
privacy scan, zero-provider receipt.

`OUT_OF_SCOPE`: real model calls, materialized domain, cutover, tax.

`STOP_CONDITIONS`: any value disappears; context can reassign ownership;
compiler invents type/value/ref.

`NEXT_ALLOWED_GOAL`: `G3.6_BOUNDED_SEMANTIC_DECISION_SEAM`.

### G3.6 — Bounded semantic decision seam

`GOAL_NAME`: `G3.6_BOUNDED_SEMANTIC_DECISION_SEAM`

`PROBLEM`: нужен current Gate 3 choice contract, отделённый от historical
packet names и не дающий модели record authority.

`OBJECTIVE`: реализовать versioned local choice/parser/guard поверх exact
options и bounded canonical context, сохранив safe no-choice.

`INPUT_CONTRACT`: G3.5 sealed options/context и Pack v2.

`OUTPUT_CONTRACT`: validated semantic decision или code-owned
`unclassified`; exact decision evidence.

`REUSED_AUTHORITIES`: existing Semantic Choice, KT2.1 context guard,
Expansion и response validation.

`ACCEPTANCE`: модель/симулятор может вернуть только allowed option/no-choice;
cannot create values/refs/IDs; insufficient context всегда unclassified;
retry/fallback/repair zero; local zero-call proof complete.

`EVIDENCE`: synthetic seam fixtures, ablation/tamper tests, exact replay,
provider-call count zero.

`OUT_OF_SCOPE`: provider transport, model qualification, production admission,
MFD activation.

`STOP_CONDITIONS`: response schema позволяет free-form facts; guard можно
обойти; no-choice теряет retention.

`NEXT_ALLOWED_GOAL`: `G3.7_MANAGED_FINANCIAL_DOMAIN_V2`.

### G3.7 — Managed Financial Domain v2

`GOAL_NAME`: `G3.7_MANAGED_FINANCIAL_DOMAIN_V2`

`PROBLEM`: MFD v1 не имеет exact canonical/bridge binding и fifth terminal
outcome.

`OBJECTIVE`: реализовать immutable v2 snapshot, records, coverage, provenance,
persistence и query semantics.

`INPUT_CONTRACT`: G3.1 MFD v2 contract, validated expansion/materialization,
Source Package v2 receipts и Pack v2 identity.

`OUTPUT_CONTRACT`: MFD v2 snapshot/query family.

`REUSED_AUTHORITIES`: v1 validator/materializer, catalog, persistence, query,
authorization и `Gate3FinancialDomainContextFactory` read projection.

`ACCEPTANCE`: exact canonical version/root + bridge + Pack pinned; five
outcomes; immutable round-trip; query pagination fingerprint preserved;
blocking snapshot exposes no partial records; v1 remains readable, not mutated.

`EVIDENCE`: schema/contract tests, persistence restore, authorization/token
tests, tamper and version-compatibility checks.

`OUT_OF_SCOPE`: whole-corpus proof, model qualification, product route, tax.

`STOP_CONDITIONS`: v2 requires in-place v1 mutation; blocking data can leak as
usable partial snapshot; provenance leaves authorized scope.

`NEXT_ALLOWED_GOAL`: `G3.8_WHOLE_DOCUMENT_TOTALITY`.

### G3.8 — Whole-document totality

`GOAL_NAME`: `G3.8_WHOLE_DOCUMENT_TOTALITY`

`PROBLEM`: component-level terminality не доказывает exact whole-document
occurrence accounting.

`OBJECTIVE`: доказать primary ownership и one terminal outcome для каждого
scope/occurrence на полном canonical artifact.

`INPUT_CONTRACT`: canonical artifact, bridge receipts и MFD v2 snapshot.

`OUTPUT_CONTRACT`: independently rebuildable whole-document totality receipt.

`REUSED_AUTHORITIES`: canonical completeness, Source Package v2 ownership,
MFD v2 coverage и integrity hashing.

`ACCEPTANCE`: exact equations hold; duplicate/missing ownership fails; repeated
totals preserved; unclassified/unsupported complete; any blocking failure
prevents usable publication.

`EVIDENCE`: property tests, mutation/tamper suite, cross-format fixtures,
independent receipt rebuild.

`OUT_OF_SCOPE`: semantic accuracy benchmark, provider calls, cutover, НДФЛ.

`STOP_CONDITIONS`: totality требует source-format exception или допускает
unaccounted occurrence.

`NEXT_ALLOWED_GOAL`: `G3.9_ACTUAL_CORPUS_QUALIFICATION`.

### G3.9 — Actual-corpus Gate 3 qualification

`GOAL_NAME`: `G3.9_ACTUAL_CORPUS_QUALIFICATION`

`PROBLEM`: synthetic/unit proof не подтверждает bridge/context/totality на
реальных broker reports.

`OBJECTIVE`: прогнать inactive full Gate 3 на авторизованном actual corpus и
измерить completeness, context sufficiency и taxonomy gaps без model calls.

`INPUT_CONTRACT`: G3.2–G3.8 inactive implementation и frozen corpus plan.

`OUTPUT_CONTRACT`: safe actual-corpus qualification receipt/report; no
production admission.

`REUSED_AUTHORITIES`: canonical reader, complete Gate 3 path, private artifact
resolver, privacy-safe evidence projection.

`ACCEPTANCE`: deterministic two-run parity; every document/scope terminally
accounted; no private bytes in Git; typed claims human-adjudicated; gaps remain
unclassified/unsupported; zero provider calls.

`EVIDENCE`: aggregate metrics, hashes, review receipt, per-format/domain
coverage, resource accounting.

`OUT_OF_SCOPE`: provider/model qualification, stage shadow, product activation,
tax calculations.

`STOP_CONDITIONS`: source loss, incomplete ownership, privacy leak, unsafe typed
record или non-deterministic rebuild.

`NEXT_ALLOWED_GOAL`: `G3.10_MODEL_QUALIFICATION`.

### G3.10 — Model qualification

`GOAL_NAME`: `G3.10_MODEL_QUALIFICATION`

`PROBLEM`: current production admissions are empty; previous candidate set
terminally failed.

`OBJECTIVE`: при отдельном разрешении квалифицировать новый exact model/policy
на реальных bounded Gate 3 cases без retry/fallback/repair.

`INPUT_CONTRACT`: frozen G3.9 cases, exact Pack/context/request/choice contracts
и pre-call authorization plan.

`OUTPUT_CONTRACT`: terminal qualification receipt с admissions либо explicit
no-admission.

`REUSED_AUTHORITIES`: existing provider adapters/client, sealed request,
Choice/Expansion/replay/evidence framework.

`ACCEPTANCE`: exact model identity; clean committed pre-call plan; bounded
single-attempt slots; semantic and technical gates; external private payloads;
`production_admissions` derived only from terminal results.

`EVIDENCE`: safe receipt, immutable slot accounting, exact replay, provider
response hashes и privacy scan.

`OUT_OF_SCOPE`: automatic retry, fallback, prompt search, runtime route,
product cutover, tax.

`STOP_CONDITIONS`: no new authorized candidate/policy; exact identity absent;
pre-call CI/ledger guard fails; any slot reaches terminal failure under frozen
policy.

`NEXT_ALLOWED_GOAL`: только при admission — `G3.11_NON_ACTIVE_CANONICAL_SHADOW`;
без admission требуется отдельное model-or-policy decision GOAL.

### G3.11 — Non-active canonical shadow

`GOAL_NAME`: `G3.11_NON_ACTIVE_CANONICAL_SHADOW`

`PROBLEM`: local/actual-corpus qualification не доказывает controlled product
integration, telemetry и rollback.

`OBJECTIVE`: подключить Gate 3 как consumer-specific, non-primary shadow через
public canonical reader и existing product boundaries.

`INPUT_CONTRACT`: admitted Gate 3 stack, exact qualified model/policy при
необходимости, consumer migration contract.

`OUTPUT_CONTRACT`: shadow-only MFD v2 plus safe parity/telemetry receipts;
legacy response остаётся primary.

`REUSED_AUTHORITIES`: consumer-specific flags, canonical reader, existing
observability, persistence и rollback boundaries.

`ACCEPTANCE`: no global canonical read; no user-visible behavior change;
failures cannot alter primary output; bounded cohorts; restart/retention/
capacity and rollback verified; exact-head CI green.

`EVIDENCE`: stage shadow receipts, parity metrics, resource/latency/error
budgets, rollback and cleanup proof.

`OUT_OF_SCOPE`: primary cutover, legacy deletion, tax methodology.

`STOP_CONDITIONS`: shadow affects primary path; capacity/privacy/authorization
fails; rollback not exact; model/Pack identity drifts.

`NEXT_ALLOWED_GOAL`: `G3.12_CONTROLLED_CUTOVER`.

### G3.12 — Controlled cutover

`GOAL_NAME`: `G3.12_CONTROLLED_CUTOVER`

`PROBLEM`: Gate 3 не становится product authority только из-за successful
shadow.

`OBJECTIVE`: отдельным release GOAL перевести разрешённый consumer на MFD v2 с
bounded rollout и exact rollback.

`INPUT_CONTRACT`: approved shadow evidence, admitted identities, release and
rollback plan.

`OUTPUT_CONTRACT`: versioned consumer cutover receipt; MFD v2 становится
primary только для явно объявленного scope.

`REUSED_AUTHORITIES`: consumer-specific migration flags, canonical reader,
MFD persistence/query, CI/deploy/observability controls.

`ACCEPTANCE`: approval and exact-head green CI; canary/bounded wave; no silent
legacy fallback; terminal telemetry; rollback and readback; clean repository
closure; documentation exact.

`EVIDENCE`: PR/review/checks, deployment identity, canary results, rollback
proof, privacy and branch/worktree hygiene receipts.

`OUT_OF_SCOPE`: НДФЛ/declaration logic, global all-consumer cutover, legacy
deletion.

`STOP_CONDITIONS`: any blocking totality outcome, admission drift, stage parity
gap, rollback failure, unexplained test/telemetry regression.

`NEXT_ALLOWED_GOAL`: отдельный post-cutover stabilization/legacy-retirement
GOAL; НДФЛ начинается только по своему versioned contract.

## 16. Следующий разрешённый шаг и stop

Следующий разрешённый GOAL: только `G3.1_GATE3_VERSIONED_CONTRACTS`.

G3.0 не разрешает:

- писать bridge/runtime code;
- менять product flags или global canonical read;
- активировать Gate 3;
- выполнять provider calls;
- продвигать текущий двухтиповый Pack как достаточный;
- смешивать MFD с НДФЛ;
- удалять legacy contour.

На этом G3.0 остановлен, как требует контракт.
