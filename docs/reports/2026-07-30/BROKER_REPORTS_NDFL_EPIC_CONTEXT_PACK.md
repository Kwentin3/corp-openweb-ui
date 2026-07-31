# Broker Reports / НДФЛ — самостоятельный context pack

Дата: `2026-07-30`

Проверенный repository snapshot: `main@9a4cc2c9f3dce4b4d4c55bff667d12089e62b614`

Этот документ предназначен для нового чата без предыдущей истории. Он кратко, но целиком описывает пользовательскую задачу, текущую архитектуру, доказанные результаты, ограничения, решения GOAL 12–16 и реальную точку продолжения.

## 1. Короткий вердикт

Broker Reports / НДФЛ задуман как контролируемый рабочий сценарий: специалист загружает брокерские документы, система сохраняет их содержание и структуру, извлекает source-local финансовые факты, объединяет их по кейсу, применяет утверждённую налоговую методологию и формирует XLS/XLSX draft для ручной проверки.

До такого результата проект ещё не дошёл.

Что реально есть:

- выполненный bounded Gate 1: intake, нейтральная нормализация, document memory, lineage, restrictions, ArtifactStore и безопасный handoff;
- техническое actual-corpus evidence Gate 1: `104` source identities, `80` logical documents, `26 complete`, `78 review_required`, zero silent loss;
- узкий детерминированный FNS 2-НДФЛ XML adapter, на historical implementation commit `29827e6312eede62802d45d84e86f5fb6df62933` давший `24` typed outputs и `351` source-local facts без LLM;
- bounded legacy Gate 2 paths и общие validators/materializers;
- отдельный V6/Context V2.1 local-proof и qualification контур;
- восемь реальных model calls GOAL 12, показавших technical pass, но semantic failure Nano и Haiku;
- нормативное решение Variant B: model выбирает только plausible financial types, code выводит reason и fail-closed восстанавливает ровно одну exact option.

Чего нет:

- current admitted financial model route: Financial Evidence valve default false, а code-owned production allowlists пусты;
- единого product E2E через Semantic Pack → Candidate Compiler → V6 Packet/Context → Expansion → ArtifactStore;
- runtime implementation Variant B;
- model qualification или accepted-corpus qualification Variant B;
- Gate 3 business reconciliation, case ledger и tax calculations;
- Gate 4 declaration model, specialist acceptance и XLS/XLSX export runtime;
- доказанной current HEAD ↔ live deployment parity;
- customer acceptance.

Поэтому название «НДФЛ» правильно как направление, но шире текущей capability. Фактически построен контролируемый Broker Reports evidence/source-local semantic layer с узким 2-НДФЛ extraction. Собственно расчёт НДФЛ и подготовка декларации остаются будущими Gate.

## 2. Пользовательская задача и безопасная граница

Целевой пользователь — специалист, а не человек, ожидающий автоматическую налоговую консультацию. Предполагаемый процесс:

1. Специалист выбирает curated OpenWebUI scenario.
2. В целевом продукте загружает брокерские PDF, CSV, XLS/XLSX, TXT/HTML, XML/FNS 2-НДФЛ и архивы. Это target list: current maintained document-memory profile ограничен `csv`, `html_text`, `pdf`, `xml`, `zip`; TXT/XLS/XLSX пока относятся к отдельным profiler/target paths, а не к принятому общему профилю.
3. Gate 1 определяет формат и readability, сохраняет текст, порядок, страницы, нейтральные таблицы, archive lineage, completeness и restrictions.
4. Gate 2 получает только bounded resolver-authorized source unit. Он назначает source-local financial meaning либо честно возвращает unclassified.
5. Будущий Gate 3 объединяет факты по документам, разрешает дубли и конфликты, связывает события и строит воспроизводимые ledgers/calculation traces.
6. Будущий Gate 4 применяет утверждённую методологию, формирует declaration-oriented draft, review state и контролируемый XLS/XLSX output.
7. Специалист проверяет draft; система не обещает final tax correctness и не подаёт декларацию.

LLM в этой архитектуре — ограниченный semantic proposer. Он не владеет:

- source bytes и storage refs;
- provenance и retention;
- exact backend records;
- tax arithmetic;
- cross-document canonical truth;
- completeness всего кейса;
- final declaration или filing.

Код строит допустимые записи, проверяет bindings и authority, materializes результат, считает usage/cost и сохраняет evidence. Для tax arithmetic и export validation модель вообще не должна быть конечной authority.

Текущий MVP не является:

- налоговой платформой;
- универсальным parser всех брокеров;
- автономной 3-НДФЛ;
- FNS integration;
- гарантией налоговой корректности;
- Knowledge/RAG pipeline для raw customer files.

Product PRD описывает результат как рабочий XLS/XLSX draft для manual review, но этот output ещё не реализован. См. `docs/stage2/prd/BROKER_REPORTS_XLS_NDFL_NATIVE_WORKFLOW_PRD.md`.

## 3. Четыре класса состояния

Для правильного чтения репозитория нужно строго разделять:

| Класс | Смысл | Пример |
| --- | --- | --- |
| A — реально работает | Maintained path выполнялся и имеет evidence в заявленной границе | Gate 1 normalization, ArtifactStore, actual-corpus technical acceptance |
| B — реализовано, но не активно | Код есть, но profile/product admission отсутствует | Context V2.1, V6 qualification chain, current financial production runtime |
| C — contract/simulation | Есть schema, report, offline builder или mechanical matrix, но нет product implementation | Variant B GOAL 16, Gate 3/4 business contracts |
| D — гипотеза | Ожидаемое качество или будущая generalization без evidence | Model accuracy Variant B на реальных brokers |

Важно: inactive path мог реально выполняться в qualification. Тогда evidence class будет `executed`, но product state останется B.

## 4. Gate architecture

### Gate 1 — Source Intake and Representation Normalization

Gate 1 отвечает: что находится в документе, в каком порядке и насколько полно это сохранено.

Основные owners:

- OpenWebUI `broker_reports_gate1_pipe.Pipe`;
- `Gate1Normalizer`;
- `Gate1BoundedGraphFactory`;
- document memory factories;
- `ArtifactStoreFactory`;
- `ArtifactResolver`;
- DCP/handoff factories.

Gate 1 создаёт private normalized payloads/source units/tables и safe refs/issues/eligibility. Он не имеет права назначать typed financial facts, налоговую роль или declaration fields.

Фактический actual-corpus result:

- 63 registered files;
- 56 required top-level inputs;
- 24 archive containers;
- 48 promoted archive members;
- 104 source identities;
- 80 logical documents;
- 26 complete;
- 78 review required;
- 104/104 technical operator review;
- 0 partial/blocked/unsupported/unreadable;
- human customer acceptance `not_performed`.

Это разные оси учёта: `63 registered = 56 required top-level + 5 excluded derived PDF + 2 excluded XLSX`; `104 source identities = 26 complete + 78 review_required`. `80 logical documents` — отдельная ось после archive promotion.

Safe receipt: `docs/reports/2026-07-18/BROKER_REPORTS_GATE1_ACTUAL_CUSTOMER_CORPUS_ACCEPTANCE.v1.safe.json`.

Это не universal support. Sber neutral-table profile, например, реализован на actual corpus, но остаётся inactive без previously unseen positive same-family holdout. OCR/image-only и другие format profiles также не закрыты универсально.

### Gate 2 — Source-Local Semantic Interpretation

Gate 2 отвечает: что означает один bounded normalized source unit. Его output — validated source facts или explicit unclassified/unsupported result.

В репозитории существуют два поколения Gate 2:

1. Legacy product route, условно интегрированный в OpenWebUI domain Pipe.
2. V6/Context V2.1 route, используемый local proofs и qualification.

Legacy product route строит Registry-driven package, code-local prompt и canonical response schema. Модель возвращает disposition/type/bindings; code валидирует, materializes и пишет private artifacts. Вызов условный: `financial_evidence_enabled` по умолчанию `false`; также нужны non-qualification mode, completed upstream result и package refs. Даже при включённом valve current Economy workload policy имеет пустые `production_admissions` для всех routes. Поэтому current model execution fail-closed до provider selection.

V6 route сначала строит Evidence Bundle и complete code-owned Typed Options, затем Packet/Context/Choice, request, provider response, Expansion, validation/materialization и Decision Evidence/replay. Он технически гораздо лучше разделяет authorities, но не подключён к product Pipe.

Узкий FNS 2-НДФЛ adapter — отдельный хороший deterministic case. На historical actual corpus он дал 24 typed outputs/351 facts без provider calls. Это доказывает source-local extraction, но не налоговый расчёт.

### Gate 3 — Case Assembly and Reconciliation

Gate 3 должен:

- собрать facts по units/documents;
- выявить overlaps и дубли;
- разрешить или явно оставить конфликты;
- связать lots/events;
- построить ledgers и deterministic calculation traces.

Реализованы Gate 3 input manifest и financial domain context consumer. Они проверяют ready scope и query boundary. Business runtime Gate 3 не начат. Наличие manifest не означает выполненное reconciliation.

### Gate 4 — Tax and Declaration Preparation

Gate 4 должен:

- применить versioned official requirements и customer methodology;
- посчитать tax base/rates/rounding deterministically;
- подготовить declaration-oriented model;
- провести specialist review;
- сформировать контролируемый XLS/XLSX/export.

Сейчас это contracts/proposals. Runtime отсутствует.

Normative gate map: `docs/stage2/blueprints/BROKER_REPORTS_GATE_ARCHITECTURE.md`.

## 5. Текущая Gate 2 архитектура и расхождение с product route

Целевая V6 последовательность:

```text
normalized source
→ Gate2InputReadinessFactory / model source projection
→ Financial Evidence Source Package
→ Semantic Pack/type-card projection
→ Evidence Bundle
→ Candidate Compiler / exact Typed Options
→ V6 Packet / Context V2.1 + private mapping receipt
→ Prompt + Choice response schema
→ Context Linter / sealed request
→ canonical request builder
→ provider adapter/client
→ response parser
→ Expansion
→ validated decision
→ materializer
→ persistence/evidence/replay
```

Sole owners:

- source readiness/projection: `Gate2InputReadinessFactory`;
- semantic meaning: `Gate2FinancialSemanticContractFactory` и managed Pack;
- type cards: `Gate2FinancialSemanticV5ProjectionFactory`;
- options: `Gate2FinancialCandidateCompilerFactory`;
- Packet/Context: `Gate2FinancialSemanticV6PacketFactory`;
- response contract/parser: `Gate2FinancialSemanticV6ChoiceContractFactory`;
- linter: `Gate2FinancialSemanticV6ContextLinterFactory`;
- request: `Gate2OpenWebUIRequestBuilder`;
- provider: `Gate2ProviderAdapterFactory` и structured model client;
- Expansion: `Gate2FinancialSemanticV6DecisionExpansionFactory`;
- validation/materialization: Financial Evidence factories;
- evidence/replay: `Gate2FinancialSemanticV6DecisionEvidenceFactory`;
- accounting: `Gate2EconomyBudgetSessionFactory`.

Но product Pipe имеет отдельную условную интеграцию:

```text
[financial_evidence_enabled=true
+ non-qualification mode
+ completed upstream result
+ package refs]
→
Gate2FinancialEvidenceProductionRuntimeFactory
→ Registry-driven source package
→ production prompt/model package
→ canonical decision
→ shared validation/materializer
→ ArtifactStore
```

Этот legacy path обходит minimal Pack projection, Evidence Bundle, Candidate Compiler, V6 Packet/Context, V6 Choice и Expansion. Valve по умолчанию выключен, а provider selection admission-blocked. Это главное architectural debt. GOAL 8–16 улучшали inactive/qualification route, а не active product route.

В действующих legacy/V6 responses reason ещё выбирает модель и проверяет code. В Variant B reason должен выводить code по cardinality, но такого runtime behavior пока нет.

Для canonical Financial Evidence decision write owner — legacy production runtime через ArtifactStore; source/domain runtimes отдельно пишут свои owned artifacts. V6 persistence currently означает proof snapshot serialization/restore, а не production storage owner.

## 6. GOAL 12–14: что именно произошло

### GOAL 12

GOAL 12 запланировал четыре synthetic cases на три providers:

- `unique_cash`;
- `no_registry_type`;
- `multiple_compatible`;
- `detail_vs_subtotal`.

Фактическое выполнение:

| Model | Calls | Exact results | Verdict |
| --- | ---: | ---: | --- |
| `gpt-5.4-nano-2026-03-17` | 4 | 2/4 | technical pass, semantic fail |
| `claude-haiku-4-5-20251001` | 4 | 3/4 | technical pass, semantic fail |
| `models/gemini-3.1-flash-lite` | 0 | 0/4 | stop before transport: immutable dated identity not proven |

Итого 8 submissions/responses. Retry, fallback, repair и semantic repair равны нулю. Unsafe typed и wrong typed type не возникли. Production admissions остались пустыми.

Receipt: `docs/reports/2026-07-29/BROKER_REPORTS_GATE2_CONTEXT_V2_1_BUDGET_MODEL_SMOKE_GOAL12.receipt.safe.json`.

Три ошибки:

1. True plausible count `2+`; Nano reason означал `1`.
2. True count `1`, но safe complete record отсутствовал; Nano reason означал `0`.
3. True count `0`; Haiku reason означал `2+`.

Все финальные dispositions остались unclassified. Это безопасно, но не значит, что модели правильно поняли источники.

### GOAL 13

GOAL 13 независимо перепроверил expected answers:

- expected-answer defect не поддержан;
- все 3 cardinality mismatches подтверждены;
- safe unclassified 3;
- unsafe typed 0;
- proven causal root layers 0.

Доказан error locus, но не root cause. Choices presentation как contributor — supported. Конкретная вина Prompt, flat projection, glossary или model capability остаётся hypothesis.

Receipt: `docs/reports/2026-07-30/BROKER_REPORTS_GATE2_CONTEXT_V2_1_POST_SMOKE_FORENSIC_AUDIT_GOAL13.receipt.safe.json`.

### GOAL 14

GOAL 14 сравнил exact evidence Nano и Haiku:

- 15/15 source values имеют table/JSON parity;
- system message, semantic context и canonical schema для одной case совпадают;
- на каждой ошибочной case вторая модель давала правильный reason;
- в `no_registry_type` code мог построить две complete options, хотя audited plausible set был пуст.

Отсюда следует доказанный architecture fact:

> Constructible option не является доказательством plausible financial type.

Candidate Compiler сознательно строит records из bindings/cardinality и не должен делать semantic match. Показ choices модели может влиять на type judgment, но causality не доказана.

## 7. GOAL 15: варианты A, B, C

### Variant A — one call, choices and plausible types

Модель видит source, type cards и complete options. Возвращает plausible type set и selected choice. Code проверяет singleton/type membership и exact option.

Плюс: может выбрать record среди нескольких same-type options за один call.

Минус: constructible choices остаются внутри type judgment и могут anchor решение.

### Variant B — one call, type first, fail closed

Модель видит только source и type cards. Возвращает ordered plausible type keys. Code:

- count 0 → `no_registry_type`;
- count 2+ → `ambiguous_registry_type`;
- count 1 → filters complete options этого типа;
- ровно одна matching option → typed;
- zero/multiple options → unclassified.

Плюсы: минимальный surface, one call, clear responsibility split, choices не влияют на type judgment.

Минусы: false singleton и intentional under-typing при multiple same-type options.

### Variant C — type first, then record

Stage 1 как B. Если после singleton type осталось несколько same-type options, Stage 2 выбирает record или null.

Плюс: потенциально лучше completeness.

Минусы: 1–2 calls, новая record-level semantic error surface, сложнее economy, replay и failure accounting.

На 10 governed simulations Stage 2 потребовался `0/10` раз.

### Критическая оценка решения

Рекомендация `SELECT_VARIANT_B_AS_MVP_AND_RESERVE_C` разумна как следующий inactive implementation:

- B решает доказанную boundary problem;
- сохраняет one-call budget;
- использует существующие owners;
- C пока не оправдывает сложность.

Но это не measured model result. GOAL 15 builder подставляет frozen audited plausible sets. Его `10/10` означает:

> Если модель вернёт oracle set, deterministic backend даст ожидаемый final route.

Это не semantic accuracy, не provider qualification и не accepted-corpus generalization. Score `142/160` — ручной rubric. Confidence справедливо только medium.

Report: `docs/reports/2026-07-30/BROKER_REPORTS_GATE2_TYPE_FIRST_SEMANTIC_DECISION_ARCHITECTURE_AUDIT_GOAL15.report.md`.

## 8. GOAL 16: contract, а не implementation

GOAL 16 создал:

- normative Markdown contract;
- machine-readable JSON contract;
- report;
- safe receipt;
- stdlib-only offline builder;
- repository test.

Он не изменил product logic, runtime, active Prompt/Context/Choice/Pack, provider adapters или production admissions. Provider calls: 0.

Machine contract явно говорит:

- `active=false`;
- `transport_eligible=false`;
- `runtime_implementation_performed=false`;
- `provider_smoke_allowed=false`;
- `provider_qualification_performed=false`;
- `model_quality_proven=false`.

Offline validator проверяет response shape, local keys, order, duplicates, seal integrity и exact backend restoration. Negative fixtures:

- 9 response;
- 5 contract-integrity;
- 2 restoration;
- total 16.

Repository test запускает current fixture/registry factories и cross-checks source/type cards/option counts/four typed-option IDs. Он не запускает Variant B Packet, linter, request builder, provider adapter, Expansion или materializer, потому что type-first runtime path отсутствует.

GOAL 16 `10/10` — mechanical contract matrix с frozen oracle plausible sets: four mechanically typed и six mechanically unclassified cases. Это не model evidence.

Прямой вывод:

> GOAL 16 формализует будущую реализацию Variant B, но не реализует её.

Files:

- `docs/stage2/contracts/BROKER_REPORTS_GATE2_TYPE_FIRST_FAIL_CLOSED.v1.md`
- `docs/stage2/contracts/BROKER_REPORTS_GATE2_TYPE_FIRST_FAIL_CLOSED.v1.json`
- `docs/reports/2026-07-30/BROKER_REPORTS_GATE2_TYPE_FIRST_FAIL_CLOSED_CONTRACT_GOAL16.report.md`

## 9. Главный риск: false singleton

False singleton выглядит так:

```text
истинный plausible set = [type_1, type_2]
→ модель возвращает валидный [type_1]
→ существует одна complete option type_1
→ code restores exact option
→ structural validation проходит
→ typed record внутренне корректен, но financial type неверен
```

Current legacy/V2.1 checks ловят malformed/duplicate JSON, unknown exact-choice aliases, request/mapping drift, exact option restoration и canonical validation. Existing qualification comparator может сравнить result с oracle.

Только GOAL 16 offline contract validator — не runtime parser — дополнительно ловит:

- missing/null/not-array `plausible_types`;
- unknown/duplicate/out-of-order local type keys;
- backend IDs и extra response fields;
- mapping/profile/Pack/scope drift;
- missing/mismatched exact option;
- mechanical reported count 0/1/2+.

Что они не ловят:

- schema-valid, semantically false singleton;
- known local type key + one exact option, когда true set был 0 или 2+;
- такую ошибку после materialization без независимой semantic truth.

GOAL 16 определяет counters, но не измеряет их:

- `plausible_type_set_exact_total`;
- `false_empty_total`;
- `false_singleton_total`;
- `false_superset_total`;
- `wrong_singleton_type_total`;
- `false_singleton_typed_total`;
- `unsafe_typed_total`;
- `safe_under_typing_total`;
- `invalid_response_total`.

Hard gates требуют нулевых unsafe typed, false-singleton typed, wrong singleton type и invalid response. Observed model values отсутствуют.

GOAL 12 case `2+→1` — сильный precursor, но старый response был unclassified reason, а не type-first set; typed branch там был недоступен. Executed adversarial type-first fixture «true 2+, returned 1, one matching option» отсутствует. Accepted-corpus evidence false singleton — 0.

Для admission нужны:

1. implemented inactive path;
2. exact sealed request/replay;
3. immutable-model qualification;
4. independently adjudicated plausible sets;
5. adversarial 0/1/2+ cases;
6. measured hard-gate counters;
7. representative accepted-corpus brokers/types;
8. reviewable privacy-safe evidence.

## 10. Synthetic и реальные данные

Для type-first текущие числа:

- canonical V6 successor benchmark: 12 synthetic cases;
- GOAL 15/16 governed subset: 10 cases;
- GOAL 12: 4 cases, 8 actual calls;
- managed minimal ontology: 2 types;
- accepted-corpus Variant B cases: 0.

Gate 1 private acceptance имеет 104 source identities/80 logical documents, но full Gate 2 package builder не выполнялся внутри этой acceptance boundary. Это evidence нормализации, а не type-first semantics.

Public semantic-visual actual-corpus benchmark:

- 9 crops;
- 6 unique PDF hashes;
- 8 accepted numeric table plans;
- 1 unsupported layout;
- candidate IDs указывают на Betterment, DriveWealth, IBKR, Moomoo.

Manifest не содержит normative broker-family owner field, поэтому нельзя превращать эти labels в production support matrix.

Private safe registry содержит probable-broker signals BCS, IBKR, Otkritie, Sber и VTB. Signals могут пересекаться. Нельзя утверждать, что доказано ровно пять supported broker families или generalization по каждой.

Managed ontology:

1. `cash_balance_snapshot_v1`;
2. `printed_financial_metric_v1`.

Следовательно, architectural responsibility split GOAL 15–16, вероятно, полезен и дальше; model quality conclusions не переносятся на расширенную ontology без новых данных.

## 11. Масштабирование ontology

GOAL 16 provider-neutral request с двумя cards занимает примерно 2.05–2.21 KB. При сохранении current card density all-cards surface ориентировочно составит:

| Types | Planning bytes | Вывод |
| ---: | ---: | --- |
| 2 | 2.05–2.21 KB measured | Текущий bounded profile |
| 10 | ~7–8 KB | Уже выше 4.5 KB sealed ceiling |
| 25 | ~17 KB | Нужен deterministic shortlist |
| 50 | ~33 KB | Выше 30 KB aggregate target |
| 100 | ~65 KB | Flat all-types surface неприемлем |

Это planning estimate, не tokenizer measurement. Но threshold ясен: all-types profile перестаёт быть разумным уже к 10 типам.

До расширения ontology нужен deterministic shortlist с измеренным recall. Иерархическая classification может понадобиться ближе к 25–50 типам, но проектировать её сейчас преждевременно. Сначала нужны real confusion data, broker-family coverage и economy measurement. Provider portability также должна requalify: длинные enums, ordered-set semantics, latency и token cost могут вести себя по-разному у OpenAI, Anthropic и Google.

## 12. Evidence overhead и продуктовый прогресс

GOAL 12 был необходим: он дал реальные provider facts. GOAL 13 не позволил менять expected answers или Prompt наугад. GOAL 14 доказал separation constructibility/plausibility. GOAL 15 остановил ненужный two-stage Variant C. GOAL 16 зафиксировал safety contract и hard gates.

Но GOAL 13–16 не добавили user-visible capability. GOAL 16 особенно показателен: большой contract/builder/test surface, но product/runtime changes 0 и provider calls 0.

Доказательная дисциплина не была бесполезной — она предотвратила unsafe admission и ложный диагноз. Однако следующий analysis-only GOAL уже не окупается. Главные unknowns нельзя решить отчётом:

- runtime path отсутствует;
- type-first model response не выполнялся;
- false-singleton metrics не измерены;
- accepted-corpus qualification отсутствует.

Следующий deliverable должен быть executable inactive slice, а не ещё один evidence pack.

## 13. Технический долг

Основные долги:

1. Legacy product и V6 qualification — параллельные semantic routes.
2. Legacy Financial Evidence valve default false; current production admissions также пусты.
3. V5-named projection является current V6 projection owner.
4. Product ArtifactStore persistence и V6 proof persistence имеют разные semantics.
5. Curated Workspace Model остаётся proposal; Pipes не равны готовому scenario.
6. Historical live proof не подтверждает current HEAD exact parity.
7. Sber profile ждёт unseen positive holdout.
8. Current ontology scaling заканчивается до 10 all-visible types.
9. Gate 3/4 user outcome отсутствует.
10. Некоторые старые docs шире current truth: PRD упоминает deployed contour/model acceptances, тогда как code-owned admissions сейчас empty.

Generated Action bundles — outputs, не owners. Current focused generated/bundle/architecture checks проходят, но это не live readback.

## 14. Реальная точка продолжения

Рекомендуемый следующий goal:

> Bounded non-active implementation Variant B внутри существующих owners, без provider calls и activation.

Минимальный результат должен включать:

- additive Packet/Context type-first profile;
- exact private local-type mapping receipt;
- strict Choice-owned parser;
- linter-owned sealed request;
- canonical request builder profile;
- code-derived reason по cardinality;
- exactly-one matching complete option rule;
- existing validation/materializer without bypass;
- Decision Evidence/replay profile;
- Economy accounting;
- simulated terminal provider envelope, но no transport;
- полный local E2E Packet → request → parser → Expansion → validation → materialization → persistence snapshot → replay;
- adversarial false-singleton cases и qualification counters.

Expansion получает additive type-first profile; existing V6 profile остаётся неизменным.

Важно: product path сам не может распознать schema-valid false singleton без oracle. Поэтому adversarial fixture должен не «магически fail-closed» внутри materializer, а показать, что zero-call comparator в existing Decision Evidence owner increments `false_singleton_typed_total`. Для последующей provider qualification следует добавить type-first profile в existing `Gate2FinancialSemanticV6ContextV21BudgetSmokeCoordinator`, а не создавать второй coordinator; этот owner блокирует admission.

После local implementation:

1. exact sealed provider request proof;
2. one bounded immutable-model qualification;
3. accepted-corpus adjudication;
4. hard-gate review;
5. отдельное activation decision.

Variant C открывать только при measured frequency multiple same-type options и доказанном net gain.

Параллельно продуктовый владелец должен выбрать следующий observable slice после Gate 2: либо narrow deterministic Gate 3 path на уже доказанном FNS 2-НДФЛ family, либо продолжение broader broker semantic path. Это отдельное продуктовое решение; текущий аудит не разрешает реализацию.

## 15. Key repository files

Architecture and product:

- `docs/stage2/blueprints/BROKER_REPORTS_GATE_ARCHITECTURE.md`
- `docs/stage2/contracts/BROKER_REPORTS_ARCHITECTURE_AUTHORITIES.md`
- `docs/stage2/prd/BROKER_REPORTS_XLS_NDFL_NATIVE_WORKFLOW_PRD.md`
- `docs/stage2/blueprints/BROKER_REPORTS_OPENWEBUI_WORKSPACE_PRODUCT_MODEL.blueprint.md`

Gate 1:

- `services/broker-reports-gate1-proof/openwebui_actions/broker_reports_gate1_pipe.py`
- `services/broker-reports-gate1-proof/broker_reports_gate1/normalizer.py`
- `services/broker-reports-gate1-proof/broker_reports_gate1/document_memory.py`
- `services/broker-reports-gate1-proof/broker_reports_gate1/bounded_graph.py`
- `services/broker-reports-gate1-proof/broker_reports_gate1/artifact_store.py`
- `services/broker-reports-gate1-proof/broker_reports_gate1/artifact_resolver.py`
- `services/broker-reports-gate1-proof/broker_reports_gate1/gate2_handoff.py`

Gate 2 current/product and V6:

- `services/broker-reports-gate1-proof/openwebui_actions/broker_reports_gate2_domain_source_fact_pipe.py`
- `services/broker-reports-gate1-proof/broker_reports_gate1/gate2_financial_evidence_production_runtime.py`
- `services/broker-reports-gate1-proof/broker_reports_gate1/gate2_economy_workload_policy.py`
- `services/broker-reports-gate1-proof/broker_reports_gate1/gate2_input_readiness.py`
- `services/broker-reports-gate1-proof/semantic_packs/broker_reports_financial_semantic_pack.v1.json`
- `services/broker-reports-gate1-proof/broker_reports_gate1/gate2_financial_semantic_v6_candidate_compiler.py`
- `services/broker-reports-gate1-proof/broker_reports_gate1/gate2_financial_semantic_v6_packet.py`
- `services/broker-reports-gate1-proof/broker_reports_gate1/gate2_financial_semantic_v6_choice.py`
- `services/broker-reports-gate1-proof/broker_reports_gate1/gate2_financial_semantic_v6_context_linter.py`
- `services/broker-reports-gate1-proof/broker_reports_gate1/gate2_model_requests.py`
- `services/broker-reports-gate1-proof/broker_reports_gate1/gate2_provider_adapters.py`
- `services/broker-reports-gate1-proof/broker_reports_gate1/gate2_financial_semantic_v6_expansion.py`
- `services/broker-reports-gate1-proof/broker_reports_gate1/gate2_financial_evidence_materialization.py`
- `services/broker-reports-gate1-proof/broker_reports_gate1/gate2_financial_semantic_v6_evidence.py`

Evidence:

- `docs/reports/2026-07-18/BROKER_REPORTS_GATE1_ACTUAL_CUSTOMER_CORPUS_ACCEPTANCE.v1.safe.json`
- `docs/reports/2026-07-21/BROKER_REPORTS_GOAL5_INTEGRATED_ACTUAL_CORPUS_REPROOF.v1.safe.json`
- `docs/reports/2026-07-29/BROKER_REPORTS_GATE2_CONTEXT_V2_1_BUDGET_MODEL_SMOKE_GOAL12.receipt.safe.json`
- `docs/reports/2026-07-30/BROKER_REPORTS_GATE2_CONTEXT_V2_1_POST_SMOKE_FORENSIC_AUDIT_GOAL13.receipt.safe.json`
- `docs/reports/2026-07-30/BROKER_REPORTS_GATE2_CONTEXT_V2_1_EVIDENCE_FIRST_COMPARATIVE_REVIEW_GOAL14.report.md`
- `docs/reports/2026-07-30/BROKER_REPORTS_GATE2_TYPE_FIRST_SEMANTIC_DECISION_ARCHITECTURE_AUDIT_GOAL15.report.md`
- `docs/stage2/contracts/BROKER_REPORTS_GATE2_TYPE_FIRST_FAIL_CLOSED.v1.md`
- `docs/stage2/contracts/BROKER_REPORTS_GATE2_TYPE_FIRST_FAIL_CLOSED.v1.json`

## 16. Bottom line для нового консультанта

1. Не считать Gate 1 acceptance доказательством tax product.
2. Не считать bounded 2-НДФЛ extraction расчётом НДФЛ.
3. Не считать V6 qualification path current product route.
4. Не считать GOAL 15/16 `10/10` model accuracy.
5. Не считать GOAL 16 implementation.
6. Считать false singleton главным admission risk Variant B.
7. Считать accepted-corpus type-first evidence равным нулю.
8. Считать current ontology two-type synthetic.
9. Считать ещё один analysis-only goal низкоценным.
10. Рекомендовать bounded inactive implementation Variant B, затем model/corpus evidence, и только после этого activation или переход к broader Gate 3 product work.
