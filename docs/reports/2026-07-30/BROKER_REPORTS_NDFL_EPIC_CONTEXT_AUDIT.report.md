# Broker Reports / НДФЛ — аудит контекста эпика

Дата аудита: `2026-07-30`

Репозиторий: `corp-openweb-ui`

Ветка и исходный HEAD: `main@9a4cc2c9f3dce4b4d4c55bff667d12089e62b614`

Режим: read-only анализ кода и evidence; единственные разрешённые изменения — три новых файла этого аудита. Provider calls: `0`.

## 1. Executive summary

Главный вывод: название «Broker Reports / НДФЛ» описывает конечное продуктовое намерение, но не текущий технический результат.

- **[proven | executed]** Gate 1 действительно принимает ограниченный набор брокерских документов, сохраняет нейтральное представление, provenance, completeness/restrictions и resolver-linked handoff. Историческое actual-corpus evidence содержит `104` source identities и `80` logical documents; технический оператор просмотрел `104/104`, но customer acceptance не проводился. Источник: `docs/reports/2026-07-18/BROKER_REPORTS_GATE1_ACTUAL_CUSTOMER_CORPUS_ACCEPTANCE.v1.safe.json:2-22,40-49,4380-4411`.
- **[proven | executed, historical]** Узкий детерминированный FNS 2-НДФЛ XML-контур на historical implementation commit `29827e6312eede62802d45d84e86f5fb6df62933` получил `24` typed outputs и `351` typed facts без provider calls. Это source-local extraction, а не расчёт налоговой базы, 3-НДФЛ или XLSX. Источник: `docs/reports/2026-07-21/BROKER_REPORTS_GOAL5_INTEGRATED_ACTUAL_CORPUS_REPROOF.v1.safe.json:2-36,50-66,83-91`.
- **[proven | implemented_inactive]** V6 Semantic Pack projection, Candidate Compiler, Packet/Context V2.1, Choice, linter, request builder profile, provider adapters, Expansion, validation, materialization, evidence и replay существуют и были собраны в qualification/local-proof контурах. Они не образуют текущий product E2E.
- **[proven | implemented_inactive]** OpenWebUI domain Pipe условно интегрирует более старый Registry-driven `Gate2FinancialEvidenceProductionRuntime`: valve `financial_evidence_enabled` по умолчанию `false`, а вызов дополнительно требует non-qualification mode, completed upstream result и package refs. Даже при включённом valve текущая Economy policy оставляет `production_admissions=()` для всех workload, поэтому модельный route fail-closed до provider selection. Источники: `services/broker-reports-gate1-proof/openwebui_actions/broker_reports_gate2_domain_source_fact_pipe.py:111,245-265,432-515`; `services/broker-reports-gate1-proof/broker_reports_gate1/gate2_financial_evidence_production_runtime.py:125-278,545-578,950-1003`; `services/broker-reports-gate1-proof/broker_reports_gate1/gate2_economy_workload_policy.py:235-283`.
- **[proven | executed]** GOAL 12 сделал восемь реальных provider submissions: четыре Nano и четыре Haiku. Обе модели прошли technical smoke, но провалили semantic smoke; Google остановлен до transport. Production admissions остались пустыми. Источник: `docs/reports/2026-07-29/BROKER_REPORTS_GATE2_CONTEXT_V2_1_BUDGET_MODEL_SMOKE_GOAL12.receipt.safe.json:2-10,27-73`.
- **[proven | contract_only]** GOAL 16 не реализовал Variant B. Он создал нормативный inactive contract, offline validator, negative fixtures и tests. В machine contract прямо указаны `runtime_implementation_performed=false`, `provider_qualification_performed=false`, `model_quality_proven=false`. Источник: `docs/stage2/contracts/BROKER_REPORTS_GATE2_TYPE_FIRST_FAIL_CLOSED.v1.json:405-446,965-1009`.
- **[proven | contract_only]** Gate 3 business reconciliation и Gate 4 tax/declaration/XLSX runtime не реализованы. Имеющиеся Gate 3 manifest/context owners проверяют вход и query boundary, но не выполняют case assembly, налоговый расчёт или подготовку декларации. Источник: `docs/stage2/blueprints/BROKER_REPORTS_GATE_ARCHITECTURE.md:205-248`.

Практический итог: сейчас продукт ближе к **контролируемому Broker Reports evidence и source-local semantic layer**, чем к готовому НДФЛ-решению. Дополнительный аналитический GOAL уже имеет низкую отдачу. Следующий оправданный шаг — один ограниченный **inactive implementation slice Variant B** внутри существующих owners, с локальным Packet-to-materialization/replay E2E и adversarial false-singleton accounting, но без runtime activation и provider calls. После него нужны sealed-request proof, model qualification и accepted-corpus qualification; только затем можно обсуждать admission.

### Шкала состояния

| Код | Значение |
| --- | --- |
| A | Реально выполненный maintained path с фактическим evidence в заявленной границе |
| B | Код существует, но профиль или модельный product route не активирован |
| C | Только contract, proposal, offline simulation или доказательный артефакт |
| D | Гипотеза или ожидаемое свойство без достаточного evidence |

Evidence class (`executed`, `implemented_inactive`, `contract_only`, `simulation_only`, `historical`, `hypothesis`) указывается отдельно: например, inactive qualification path мог реально исполняться, но от этого он не становится active product capability.

## 2. Пользовательская задача

### 2.1 Что должен делать целевой продукт

Простыми словами предполагаемый процесс таков:

1. Специалист выбирает подготовленный сценарий Broker Reports.
2. В целевом продукте загружает брокерские PDF, CSV, XLS/XLSX, TXT/HTML, XML/FNS 2-НДФЛ и архивы. Это target format list, не current acceptance claim: maintained document-memory profile сейчас ограничен `csv`, `html_text`, `pdf`, `xml`, `zip`; TXT/XLS/XLSX существуют в отдельных profiler/target paths.
3. Gate 1 сохраняет содержание и структуру без назначения финансового смысла: страницы, строки, таблицы, порядок, lineage, полноту и ограничения.
4. Gate 2 интерпретирует один ограниченный source unit: определяет source-local финансовый тип/роль и создаёт валидированные typed source facts либо честно оставляет вход unclassified.
5. Будущий Gate 3 должен объединить факты по документам, разрешить дубли и конфликты и построить воспроизводимые ledgers/calculation traces.
6. Будущий Gate 4 должен применить утверждённую методологию, подготовить declaration-oriented model и контролируемый XLS/XLSX draft для ручной проверки специалистом.

Продуктовый PRD формулирует результат как структурированный черновик с явными пробелами и XLS/XLSX draft для manual review, а не как автономную декларацию: `docs/stage2/prd/BROKER_REPORTS_XLS_NDFL_NATIVE_WORKFLOW_PRD.md:9-17,80-95,406-435`.

### 2.2 Где заканчивается автоматическая обработка

В целевой архитектуре:

- код обязан владеть source bytes, refs, lineage, exact records, validation, materialization, persistence, арифметикой и export validation;
- LLM получает только ограниченный model-visible контекст и предлагает semantic decision;
- LLM не является authority для налоговой арифметики, правовой трактовки, completeness всего кейса, записи raw provider payload или подачи декларации;
- специалист остаётся конечной контрольной точкой для draft.

В текущем product состоянии автоматическая обработка фактически заканчивается раньше: Gate 1 и некоторые bounded Gate 2 paths работают, но current financial model route admission-blocked, а Gate 3/4 отсутствуют.

### 2.3 Что делает LLM сейчас и что планирует Variant B

Существуют три разных поколения ответственности:

1. Старый production runtime просит модель вернуть полный canonical disposition/type/bindings; код валидирует и materializes.
2. V6 qualification path заранее строит exact Typed Options; модель выбирает exact option либо unclassified reason.
3. Будущий Variant B должен показывать модели только source и type cards; модель возвращает ordered plausible type keys, а код выводит reason и допускает typed output только при ровно одной complete matching option.

Третий вариант пока контракт, а не поведение.

### 2.4 Что не входит в текущий MVP

Не доказаны и не должны обещаться:

- автономный расчёт НДФЛ или готовая 3-НДФЛ;
- налоговая консультация или гарантия налоговой корректности;
- подача в ФНС;
- универсальный parser всех брокеров и форматов;
- автоматическое устранение cross-document дублей/конфликтов;
- production-ready XLS/XLSX generation;
- использование raw customer uploads как Knowledge/RAG/vector corpus;
- production admission любой из проверенных в GOAL 12 моделей.

### 2.5 Насколько корректно название «НДФЛ»

**[proven]** Название корректно как направление эпика: репозиторий содержит domain docs, FNS 2-НДФЛ adapter и будущие Gate 3/4 contracts.

**[proven]** Как описание текущего capability название завышено: tax treatment, case reconciliation, declaration generation и XLSX runtime не реализованы.

**[supported]** На текущем этапе разумнее говорить: «Broker Reports evidence/source-local semantic layer с узким 2-НДФЛ extraction и будущим НДФЛ output».

## 3. Текущее состояние эпика

### 3.1 Проверенный Git snapshot

- Исходная ветка: `main`.
- Исходный `HEAD == origin/main`: `9a4cc2c9f3dce4b4d4c55bff667d12089e62b614`.
- До создания трёх audit outputs working tree был clean.
- Worktree один.
- После аудита ожидаются только три untracked файла в `docs/reports/2026-07-30/`; commit не создаётся.

Последовательность текущей программы:

| GOAL | Content commit | Merge/current relation |
| --- | --- | --- |
| 12 | `4156174010276f07ba8642ad782678dabfae0ba1` | Прямой commit на истории main |
| 13 | `adf60cb3a0ecec059a4a4763715ad6c1bc166c7e` | Прямой commit на истории main |
| 14 | `737682f7dacdd0ff6b1d68c06e51d64c86a4283c` | PR #229 content |
| 15 | `d2d7ec6e2e8016629f40b0fe63590a1bf7bd066f` | Merge `7ef38c2bba12e6773f2ded8542c256d603ca5aff` |
| 16 | `d3d9bbd4d7657f26222aa9dc137c8a31ff33c120` | Merge/HEAD `9a4cc2c9f3dce4b4d4c55bff667d12089e62b614` |

### 3.2 Состояние по слоям

| Слой | Статус | Честная формулировка |
| --- | --- | --- |
| OpenWebUI curated Workspace Model | C | Есть proposal/UX/config docs; blueprint scenario contract содержит `workspace_model_id: null`, current curated model не доказан |
| Gate 1 Pipe/normalization/ArtifactStore | A | Реализовано и выполнялось; current HEAD ↔ live exact parity не подтверждён |
| Accepted private corpus | A в Gate 1 | Technical operator acceptance есть; customer acceptance нет |
| Узкий FNS 2-НДФЛ adapter | A, bounded/historical | Source-local deterministic extraction; не tax calculation |
| Legacy Gate 2 product runtime | B current / A historical | Интегрирован с Pipe, но current production admissions пусты |
| V6/Context V2.1 qualification path | B | Реализован, выполнялся в smoke, но inactive и не product route |
| Type-first Variant B | C | Только normative contract/offline validator |
| Gate 3 business assembly | C | Manifest/input boundary есть; reconciliation runtime нет |
| Gate 4 tax/declaration/XLSX | C | Contracts/proposals, runtime отсутствует |

### 3.3 Текущая пользовательская observable capability

Пользователь может получить Gate 1 safe summary: учёт файлов, форматы, coverage, blockers, readiness и дальнейшие действия. Исторические bounded Gate 2 paths также выдавали source-local results. Но пользователь сейчас не получает из current admitted semantic route:

- собранный инвестиционный кейс;
- налоговую базу;
- готовую 3-НДФЛ;
- XLS/XLSX draft;
- подтверждение специалистом.

## 4. Карта Gate

| Gate | Назначение | Вход | Выход | Статус | Доказано | Не доказано / blocker | Observable result |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Gate 1 | Source intake и нейтральная нормализация | OpenWebUI file refs/private bytes | normalized payloads/units/tables, document memory, issues, eligibility, DCP refs | A, частично закрыт по профилям | Actual corpus, lineage, zero silent loss, resolver boundary, supported formats | Универсальные форматы/OCR; Sber unseen positive holdout; current live parity | Safe document inventory, coverage, blockers, ready/reduced/blocked handoff |
| Gate 2 | Source-local semantic interpretation | DCP + resolver-authorized bounded descendants | validated source facts, issues, terminal run, Gate 3 context manifest | Смешанный: bounded A historical; legacy product B current; V6 B; Variant B C | Bounded source/domain paths, 2-НДФЛ adapter, V6 local/qualification mechanics, GOAL 12 smoke | Current production admission; single canonical E2E; type-first model/corpus quality; whole-corpus semantic coverage | Сейчас нет нового admitted financial semantic result |
| Gate 3 | Cross-unit/cross-document assembly, reconciliation, ledgers | Ready Gate 2 manifest/facts | reconciled events, conflicts, ledgers, calculation traces | C для business runtime; manifest/context boundary implemented | Input manifest integrity/query boundaries | Deduplication, conflict resolution, lot/event linking, deterministic calculations | Нет |
| Gate 4 | Tax methodology, declaration model, specialist review, export | Accepted Gate 3 case root + methodology | declaration-oriented draft, review state, controlled XLSX/export | C | Только docs/contracts/proposals | Methodology authority, tax calculations, review workflow, export runtime | Нет |

Normative gate placement: `docs/stage2/blueprints/BROKER_REPORTS_GATE_ARCHITECTURE.md:81-119,143-160,186-248`.

### 4.1 Почему Gate 1 и Gate 2 нельзя объединять

Gate 1 отвечает на вопрос «что находится в источнике и как оно структурировано». Он может определять format/readability и нейтральные structural labels, но не финансовый смысл. Gate 2 отвечает «что означает один bounded source unit» и создаёт source-local facts. Если Gate 1 начнёт назначать financial types, исчезнет независимая source representation и станет невозможно отличить parsing error от semantic error.

### 4.2 Boundary к декларации

Gate 2 не имеет права выбирать canonical fact между документами, объединять события, считать налог или заполнять declaration fields. Эти обязанности начинаются в Gate 3/4. Реализованные `Gate3ContextManifestFactory` и `Gate3FinancialDomainContextFactory` — входная/consumer boundary, не бизнес-реализация Gate 3. В manifest кодом запрещены tax/declaration permissions: `services/broker-reports-gate1-proof/broker_reports_gate1/gate3_context_manifest.py:86-136`.

## 5. Архитектура end-to-end

### 5.1 Целевая последовательность и sole owners

```text
исходный документ
→ Gate 1 normalized source / document memory
→ Gate 2 source projection
→ Semantic Pack / type cards
→ Evidence Bundle + Candidate Compiler
→ V6 Packet / model-visible Context
→ Prompt + Choice schema + Context Linter
→ canonical request builder
→ provider adapter/client
→ response normalization
→ Expansion
→ canonical validation
→ materialization
→ product persistence / Decision Evidence / replay
```

| Звено | Sole owner | Ответственность | Фактический current status |
| --- | --- | --- | --- |
| Source normalization | `Gate1Normalizer` / `Gate1BoundedGraphFactory` | Neutral content, order, structure, completeness, lineage | A |
| Artifact persistence/access | `ArtifactStoreFactory`, `ArtifactResolver` | Private records, lifecycle и exact access context | A |
| Gate 2 readiness/projection | `Gate2InputReadinessFactory`; `_build_model_source_projection` | Resolver-backed bounded source projection | A deterministic |
| Financial source package | `Gate2FinancialEvidenceSourcePackageFactory` | Bounded source-local package | B for V6 |
| Semantic type authority | `Gate2FinancialSemanticContractFactory`; managed Pack | Type meanings/rules; canonical validation primitive | Shared primitive; current minimal managed projection inactive |
| Type-card projection | `Gate2FinancialSemanticV5ProjectionFactory` | Full/minimal model-visible type cards | B |
| Candidate construction | `Gate2FinancialEvidenceBundleFactory`, `Gate2FinancialCandidateCompilerFactory`, `Gate2FinancialTypedOptionFactory` | Deterministically construct complete code-owned options | B |
| Packet/Context | `Gate2FinancialSemanticV6PacketFactory` | Packet and V2.1 candidate/private mapping receipt | B |
| Prompt | `financial_semantic_v6_prompt` | Exact semantic instruction | B qualification |
| Choice/parser | `Gate2FinancialSemanticV6ChoiceContractFactory` | Response schema, local-key parsing/restoration | B; Variant B profile absent |
| Linter/sealed request | `Gate2FinancialSemanticV6ContextLinterFactory` | Totality, surface budget, sealed inactive request | B |
| Request | `Gate2OpenWebUIRequestBuilder` | Canonical logical request → provider-neutral request | A generic; Type-first profile absent |
| Provider | `Gate2ProviderAdapterFactory`, `Gate2StructuredModelClientFactory` | Provider projection, extraction, usage/error handling | A generic/qualification |
| Expansion | `Gate2FinancialSemanticV6DecisionExpansionFactory` | Local choice → exact canonical decision | B |
| Validation | `Gate2FinancialEvidenceValidatedDecisionFactory` | Registry/source/binding/decision invariants | A shared |
| Materialization | `Gate2FinancialEvidenceMaterializerFactory` | Exact typed/unclassified product artifact | A shared |
| Financial Evidence canonical write | `Gate2FinancialEvidenceProductionRuntime._put_private` | Записывает canonical Financial Evidence decision artifacts; source/domain runtimes отдельно пишут свои owned artifacts | B current, A historical |
| V6 evidence/replay | `Gate2FinancialSemanticV6DecisionEvidenceFactory` + replay functions | Private evidence, safe receipts, exact offline replay | A qualification/offline; B product |
| Economy | `Gate2EconomyBudgetSessionFactory`, workload policy/provider selection | Calls, usage, cost, allowlist/admission | A; current admission empty |

Лучшие code anchors:

- `services/broker-reports-gate1-proof/broker_reports_gate1/gate2_input_readiness.py:52-57,111-147,1791-1935`
- `services/broker-reports-gate1-proof/broker_reports_gate1/gate2_financial_semantic_v6_packet.py:218-337,4400-4440,4842-4862`
- `services/broker-reports-gate1-proof/broker_reports_gate1/gate2_financial_semantic_v6_choice.py:249-430,531-590`
- `services/broker-reports-gate1-proof/broker_reports_gate1/gate2_financial_semantic_v6_context_linter.py:596-880`
- `services/broker-reports-gate1-proof/broker_reports_gate1/gate2_financial_semantic_v6_expansion.py:120-339`
- `services/broker-reports-gate1-proof/broker_reports_gate1/gate2_financial_evidence_materialization.py:89-183,200-432`
- `services/broker-reports-gate1-proof/broker_reports_gate1/gate2_financial_semantic_v6_evidence.py:450-737,1064-1153,1260-1432`

### 5.2 Фактический product route отличается от целевой цепочки

Это главное архитектурное расхождение.

```text
OpenWebUI domain Pipe
→ [financial_evidence_enabled=true
   + non-qualification mode
   + completed upstream result
   + package refs]
→ Gate2FinancialEvidenceProductionRuntimeFactory
→ Registry-driven scope/source package
→ code-local production Prompt
→ direct canonical decision schema
→ provider
→ validated decision
→ materializer
→ ArtifactStore
```

Этот условно интегрированный legacy runtime не вызывает V5 minimal projection, Evidence Bundle, Candidate Compiler, V6 Packet, Context V2.1, V6 Choice или Expansion. Valve по умолчанию выключен, а model selection дополнительно admission-blocked. Поэтому нельзя говорить, что GOAL 8–16 «улучшили активный production decision path»: они создали параллельный inactive/qualification контур.

### 5.3 Где принимаются решения

- В legacy product route модель выбирает canonical disposition/type/bindings; code проверяет.
- В current V6 qualification route модель выбирает exact option id или unclassified reason; code восстанавливает option.
- В Context V2.1 модель возвращает локальный `choice_N` и reason; `normalize_financial_semantic_v6_context_v2_1_choice` восстанавливает exact backend option по private receipt.
- В Variant B model должна выбирать только plausible type set; code должен выводить reason. Это contract-only.

### 5.4 Кто определяет reason и кто имеет право писать

В реально существующих legacy/V6 routes reason возвращает модель и валидирует код. Code-derived reason по cardinality существует только в GOAL 16 offline contract logic. Для canonical Financial Evidence decision write owner — legacy production runtime через `_put_private` → `ArtifactStore.put_record`; Gate 2 source/domain runtimes отдельно записывают собственные artifact types. Qualification/local proof может materialize snapshots и evidence, но не является product write authority.

### 5.5 Fail-closed, evidence и replay

В maintained legacy/V2.1 owners реально реализованы и/или выполнялись:

- пустой production allowlist до provider call;
- exact profile/schema/request binding;
- terminal provider response и byte budget;
- duplicate JSON-key rejection, unknown scalar choice-alias rejection и exact choice restoration для существующих Choice profiles;
- Pack/Registry/source/binding validation;
- unclassified retention;
- deterministic evidence serialization и offline replay.

Точные проверки Variant B `unknown_type_key`, `duplicate_type_key` и `out_of_order_type_keys` пока существуют только в GOAL 16 offline builder/test. Runtime parser ordered plausible-type set отсутствует.

Replay не повторяет provider call. Он восстанавливает pinned request/response authorities и повторяет Expansion/validation/materialization, затем сравнивает canonical result.

### 5.6 Есть ли конкурирующие owners

Номинально authority map старается сохранить sole owners, но фактически существуют два поколения orchestration:

1. legacy product `Gate2FinancialEvidenceProductionRuntime`;
2. V6/Context V2.1 qualification/local-proof chain.

Это не два класса с одинаковым именем, но два разных semantic decision routes. Дополнительные точки drift:

- V5-named projection остаётся owner для V6;
- legacy scope factory и V6 Evidence Bundle/Compiler строят разные input surfaces;
- product writes напрямую в ArtifactStore, а V6 `Gate2FinancialDomainPersistenceFactory` только serializes/restores proof snapshots;
- frozen Context V2.1 summary ещё содержит `response_profile_status="not_implemented"`, хотя отдельный inactive Choice profile уже появился.

## 6. Что реально работает

### 6.1 Gate 1

**[proven | executed]**

- OpenWebUI Pipe принимает file refs, вызывает normalizer, сохраняет private artifacts и возвращает safe report: `services/broker-reports-gate1-proof/openwebui_actions/broker_reports_gate1_pipe.py:135-136,241-251,500-741`.
- Normalizer создаёт inventory, profiles, source units/tables, provenance, eligibility, blockers и DCP, не назначая financial meaning: `services/broker-reports-gate1-proof/broker_reports_gate1/normalizer.py:62-145,147-438,479-574`.
- Document memory поддерживает bounded CSV/HTML-text/PDF/XML/ZIP profiles с explicit restrictions: `services/broker-reports-gate1-proof/broker_reports_gate1/document_memory.py:13-40,57-166,260-620,715-1034`.
- `ArtifactStoreFactory` — единственный production store entrypoint; resolver проверяет user, run, case/chat, optional Workspace и lifecycle: `artifact_store.py:29-56,56-237,829-949`; `artifact_resolver.py:18-30,60-117`.
- DCP/handoff содержит refs, а не private payload copy: `gate2_handoff.py:54-90,145-175,208-245,1035-1085,1160-1193`.

Actual-corpus result:

| Показатель | Значение |
| --- | ---: |
| Registered source files | 63 |
| Required top-level inputs | 56 |
| Archive containers | 24 |
| Promoted members | 48 |
| Source identities | 104 |
| Logical documents | 80 |
| Complete | 26 |
| Review required | 78 |
| Operator reviewed | 104 |
| Human customer acceptance | not performed |
| Partial/blocked/unsupported/unreadable | 0 |

Счётчики относятся к разным осям и не должны складываться между собой: `63 registered = 56 required top-level + 5 excluded derived PDF + 2 excluded XLSX`; `104 source identities = 26 complete + 78 review_required`. `80 logical documents` — отдельная после archive-promotion ось.

Это доказывает technical handling в зафиксированном профиле. Оно не доказывает universal parser или customer approval.

### 6.2 Узкий FNS 2-НДФЛ path

`Gate2Fns2NdflAdapter` детерминированно интерпретирует заявленный XML contract и не требует LLM. Historical actual-corpus reproof на `29827e6312eede62802d45d84e86f5fb6df62933` показал 24 outputs/351 facts. Owners: `services/broker-reports-gate1-proof/broker_reports_gate1/gate2_fns_2ndfl_contracts.py:10-115`; `gate2_fns_2ndfl_adapter.py:167-230,430-465`.

Это важное здравое зерно: эпик не является только документами и схемами. Но данный path не решает foreign broker reports, cross-document reconciliation или tax calculation.

### 6.3 Shared Gate 2 primitives

Canonical validation/materialization, request builder, provider adapters, Economy accounting, ArtifactStore и replay factories выполняются тестами и историческими proof paths. В текущем аудите без provider calls выполнено:

```text
python scripts/build_type_first_fail_closed_contract.py --check
python -m pytest -q \
  tests/test_build_type_first_fail_closed_contract.py \
  tests/test_broker_reports_gate1_artifact_store.py \
  tests/test_broker_reports_gate1_pipe_bundle.py \
  tests/test_broker_reports_gate_architecture.py \
  -p no:cacheprovider
```

Результат: builder check `passed`; `75 passed, 1 skipped`. Skip — merged-feature diff guard, а не functional failure. Эти тесты доказывают текущие factories и boundaries, но не current live deployment, provider quality или customer acceptance.

### 6.4 GOAL 12 provider evidence

GOAL 12 — единственный из GOAL 12–16, где были новые provider calls:

| Exact model | Submitted/responded | Exact semantic cases | Technical | Semantic |
| --- | ---: | ---: | --- | --- |
| `gpt-5.4-nano-2026-03-17` | 4/4 | 2/4 | passed | failed: 2 wrong reasons |
| `claude-haiku-4-5-20251001` | 4/4 | 3/4 | passed | failed: 1 wrong reason |
| `models/gemini-3.1-flash-lite` | 0/0 | 0/4 | pre-transport stop | failed |

Итого: `8` submissions/responses; retry/repair/fallback/semantic repair `0`; unsafe typed `0`; production admissions `[]`. Google имеет четыре infrastructure/pre-transport failures, но это не четыре provider calls.

## 7. Что реализовано, но не активно

### 7.1 Minimal managed semantic surface

Current managed semantic Pack объявляет `authority_status="target_normative_not_live"` и `runtime_activation=false`; в minimal snapshot ровно два типа:

1. `cash_balance_snapshot_v1`;
2. `printed_financial_metric_v1`.

Источник: `services/broker-reports-gate1-proof/semantic_packs/broker_reports_financial_semantic_pack.v1.json:7-14,39-291`.

### 7.2 V6 / Context V2.1 chain

Реализованы, но не product-active:

- minimal type-card projection;
- Evidence Bundle и Candidate Compiler;
- V6 Packet and Context V2.1 candidate/private mapping receipt;
- V6 Prompt;
- inactive V2.1 Choice schema/parser;
- Context Linter and sealed inactive request;
- V6-specific request profile;
- provider-neutral/provider-specific projection;
- Expansion, validation/materialization composition;
- private evidence, safe receipt и offline replay;
- GOAL 12 qualification coordinator.

Контур был выполнен в GOAL 11/12, но `active=false`, `transport_eligible=false` вне строго отдельной qualification authorization и не импортируется product Actions.

### 7.3 Legacy production runtime

Код production runtime существует и условно подключён к OpenWebUI Pipe. Сейчас есть два независимых stop: `financial_evidence_enabled=false` по умолчанию и пустые `production_admissions`. Поэтому статус текущего model-dependent route — B, а не A. Historical live evidence относится к более ранним revisions; current exact live readback отсутствует.

### 7.4 Sber neutral-table profile

Профиль реализован на actual corpus, но release valve default false и отсутствует genuine unseen positive same-family holdout. Источник: `docs/contracts/BROKER_REPORTS_CUSTOMER_TEST_DEBT.v1.md:21-65`. Это B, а не generalization closure.

## 8. Что существует только как контракт или симуляция

### 8.1 Workspace Model

Curated `Broker Reports / XLS NDFL Draft Scenario` описан в config/UX blueprint, но config прямо является proposal, а product blueprint содержит `workspace_model_id: null`: `docs/stage2/config/BROKER_REPORTS_OPENWEBUI_WORKSPACE_CONFIGURATION.v0_PROPOSAL.md:5-19`; `docs/stage2/blueprints/BROKER_REPORTS_OPENWEBUI_WORKSPACE_PRODUCT_MODEL.blueprint.md:81-82`.

Pipes существуют, но их наличие не доказывает существование current curated Workspace Model.

### 8.2 Gate 3 и Gate 4

Gate 3 case ledger/reconciliation и Gate 4 tax/declaration/export описаны архитектурно. Это C. Реализованный manifest не делает их A или B.

### 8.3 GOAL 15 variants

Variants A/B/C оценивались offline. Builder подставлял frozen audited plausible set, а не вызывал модель. Его `10/10` — deterministic consequence при oracle input, то есть `simulation_only`.

### 8.4 GOAL 16 type-first contract

Новые canonical outputs GOAL 16:

1. `docs/stage2/contracts/BROKER_REPORTS_GATE2_TYPE_FIRST_FAIL_CLOSED.v1.md`;
2. `docs/stage2/contracts/BROKER_REPORTS_GATE2_TYPE_FIRST_FAIL_CLOSED.v1.json`;
3. report;
4. safe receipt;
5. offline builder;
6. builder test.

Product code changes: `0`. Runtime changes: `0`. Provider calls: `0`. Type-first Packet method, inactive implementation profile, private mapping receipt, response parser, linter profile, request profile, Expansion behavior, evidence/replay profile и type-first coordinator profile отсутствуют. Existing GOAL 12 coordinator реализован, но type-first profile в него не добавлен.

Offline tests cross-check current source projection/type cards/option counts и четыре typed-option identities through current factories. Они не запускают Variant B Packet → request → response → Expansion → materialization, потому что такого path нет.

Прямой ответ: **GOAL 16 — формализация будущей реализации, не implementation goal.**

## 9. История GOAL 12–16

### 9.1 Причинно-следственная цепочка

1. GOAL 12 выполнил bounded Context V2.1 model smoke.
2. Nano и Haiku технически ответили, но ошиблись в diagnostic reason/cardinality на трёх cases; typed errors не возникли.
3. GOAL 13 независимо перепроверил expected answers и локализовал error locus: модель неверно оценивала число plausible financial types. Ни один causal root layer не был доказан.
4. GOAL 14 сравнил одинаковые source/context/schema между моделями и доказал важное различие: **constructible record option не равен plausible financial type**. Choices presentation — supported risk, но не доказанная единственная причина.
5. GOAL 15 сравнил три будущих type-first архитектуры и рекомендовал B.
6. GOAL 16 закрепил B в contract и mechanical validator, но не реализовал его в runtime.

### 9.2 Три проблемных кейса

| Source summary | Правильное число plausible types | Фактический ответ модели | Почему final disposition остался безопасным | Обнаруженный риск |
| --- | ---: | --- | --- | --- |
| Possible cash + possible total | `2+` | Nano вернул unclassified reason, означающий `1` | В этом schema typed branch/choices отсутствовали | `2+ → 1`: прямой precursor false singleton |
| Detail `25` и subtotal `125` | `1` — printed metric, но safe complete record нет | Nano вернул reason, означающий `0` | Unclassified был единственным допустимым disposition | Модель спутала отсутствие constructible record с отсутствием plausible type |
| Broker fee detail, CHF | `0` | Haiku вернул reason, означающий `2+` | Модель всё же выбрала unclassified, typed records не записаны | Две constructible choices могли повлиять на type judgment |

Machine evidence: `docs/reports/2026-07-30/BROKER_REPORTS_GATE2_CONTEXT_V2_1_POST_SMOKE_FORENSIC_AUDIT_GOAL13.receipt.safe.json:4-10,15-87`.

### 9.3 Что доказал GOAL 13

**[proven]**

- `3/3` expected answers независимо revalidated;
- `3/3` final dispositions safe unclassified;
- wrong diagnostic reasons `3`;
- unsafe typed `0`;
- cardinality errors: `2+→1`, `1→0`, `0→2+`;
- proven causal root layers `0`.

**[supported]** Choices presentation мог быть contributor.

**[hypothesis]** Конкретная причинность Prompt, projection, glossary или model capability.

### 9.4 Что доказал GOAL 14

**[proven]**

- `15/15` source values имеют exact table/JSON parity;
- system/context/schema для одной case были одинаковы между Nano и Haiku;
- на каждой ошибочной case другая модель давала правильный reason;
- `no_registry_type` имел две constructible options при истинном plausible set `[]`.

Candidate Compiler по контракту не имеет права читать literals/labels и выполнять semantic match; он строит records из bindings/cardinality: `services/broker-reports-gate1-proof/broker_reports_gate1/gate2_financial_semantic_v6_candidate_compiler.py:42-50,130-155`.

### 9.5 Change/artifact ledger

| GOAL | Product-code change | Provider calls | Новый contract | Report/receipt/transparent artifacts | User-visible capability | Снятый риск | Оставшийся риск |
| --- | ---: | ---: | ---: | ---: | --- | --- | --- |
| 12 | 8 maintained modules + 3 generated bundles + 2 qualification scripts; active product change `0` | 8 | 1 | 5 | Нет | Получено реальное technical/semantic provider evidence | Все admissions empty; semantic errors |
| 13 | 0 | 0 | 0 | 2 | Нет | Expected-answer defect не поддержан; error locus локализован | Root cause не доказан |
| 14 | 0 | 0 | 0 | 3 | Нет | Сведены exact comparative evidence; constructibility отделена от plausibility | Causality/model generalization |
| 15 | 0 | 0 | 0 | 3 + offline builder/test | Нет | Выбран минимальный кандидат B; C отложен | Только simulation, two-type synthetic corpus |
| 16 | 0 | 0 | 1 logical contract, MD+JSON | 2 + offline builder/test | Нет | Зафиксирована total fail-closed policy и future counters | Нет implementation, request, model/corpus evidence |

## 10. Анализ Variant B

### 10.1 Варианты простыми словами

| Вариант | Что видит/возвращает модель | Что решает код | Calls | Преимущество | Основной риск | Models / accepted corpus |
| --- | --- | --- | ---: | --- | --- | --- |
| A — choices + types | Source, type cards и complete options; возвращает plausible types + selected choice | Проверяет singleton/type membership и exact option | 1 | Может выбрать record среди same-type options | Constructible choices остаются внутри type judgment | Не проверен / не проверен |
| B — type first, fail closed | Только source + type cards; возвращает plausible type keys | Выводит reason; typed только при singleton type + ровно одной matching option | 1 | Самый маленький surface; отделяет plausibility от construction | False singleton; under-typing при multiple same-type options | Не проверен / не проверен |
| C — type then record | Stage 1 как B; Stage 2 видит options одного уже выбранного типа | Вызывает Stage 2 только при 2+ same-type options | 1–2 | Возвращает completeness в сложном same-type state | Двухвызовные failure/replay/economy и record-level model error | Не проверен / не проверен |

Anchors: `docs/reports/2026-07-30/BROKER_REPORTS_GATE2_TYPE_FIRST_SEMANTIC_DECISION_ARCHITECTURE_AUDIT_GOAL15.report.md:25-40,182-195,319-333,580-590`.

### 10.2 Независимая оценка решения

`SELECT_VARIANT_B_AS_MVP_AND_RESERVE_C` обоснован как **следующий inactive implementation candidate**, потому что:

- убирает constructible choices из type judgment;
- сохраняет one-call budget;
- не требует нового authority;
- Stage 2 варианта C не понадобился ни в одной из 10 governed simulations;
- его можно реализовать additive profiles в существующих Packet/Choice/Linter/Expansion/Evidence owners.

Но решение имеет только medium confidence:

- score `142/160` — ручной rubric, не измеренная model quality;
- type-first prompt/schema не отправлялись ни одной модели;
- accepted-corpus false-singleton rate равен «нет данных»;
- ontology содержит два типа;
- 10/10 предполагает правильный oracle plausible set.

Следовательно, B — разумный инженерный MVP, но не доказанная production strategy. Reserve C — разумный complexity stop, а не доказательство, что второй stage никогда не понадобится.

## 11. False singleton risk

### 11.1 Механизм

```text
истинный plausible set = [type_1, type_2]
→ модель возвращает schema-valid [type_1]
→ код находит одну complete option type_1
→ exact restoration и structural validation проходят
→ materialized typed record внутренне согласован, но семантически неверен
```

Риск возникает между model-owned type judgment и code-owned option filtering.

### 11.2 Что проверки ловят — с учётом статуса

Current legacy/V2.1 code умеет закрывать malformed/duplicate JSON, unknown exact-choice aliases, mapping/profile/request drift, exact option restoration и canonical validation. Qualification comparator существующего V2.1 smoke может сравнить result с независимым expected oracle и пометить typed mismatch как `unsafe_typed`.

GOAL 16 **offline contract validator**, но не runtime parser, дополнительно проверяет:

- missing/null/not-array `plausible_types`;
- unknown, duplicate и out-of-order local type keys;
- extra fields и backend type IDs;
- mapping/profile/Pack/evidence/compiler seal drift;
- missing/mismatched exact code-owned option;
- mechanical reported cardinality `0`, `1`, `2+`.

GOAL 16 negative fixtures: 9 response + 5 integrity + 2 restoration = 16. Источники: `services/broker-reports-gate1-proof/scripts/build_type_first_fail_closed_contract.py:248-349,886-979`; receipt `docs/reports/2026-07-30/BROKER_REPORTS_GATE2_TYPE_FIRST_FAIL_CLOSED_CONTRACT_GOAL16.receipt.safe.json:14-25`.

### 11.3 Что не ловится

Product validators не могут определить, что schema-valid singleton семантически ложен, если local key известен и exact matching option существует. Validation после materialization проверяет authority, registry, refs, bindings и exact record, а не независимую semantic truth. Источник: `gate2_financial_evidence_materialization.py:105-142,200-219`.

### 11.4 Adversarial fixtures и метрики

- Executed adversarial type-first model fixture «true 2+, model 1, one matching option» отсутствует.
- GOAL 12 `2+→1` — сильный historical precursor, но старый response был reason-only/unclassified и не мог materialize typed record.
- GOAL 16 определяет counters, включая `false_singleton_total` и `false_singleton_typed_total`, но observed values отсутствуют.
- `provider_qualification_performed=false`; `model_quality_proven=false`.
- Accepted-corpus evidence для false singleton: `0`.

### 11.5 Что требуется для admission

1. Inactive runtime implementation exact contract.
2. Sealed request/linter/replay E2E.
3. Immutable exact-model qualification на type-first schema.
4. Independently adjudicated plausible sets и exact safe options.
5. Adversarial cases для истинных `0`, `1`, `2+`, включая one-constructible-option trap.
6. Измеренные counters; hard gates `unsafe_typed_total=0`, `false_singleton_typed_total=0`, `wrong_singleton_type_total=0`, `invalid_response_total=0`.
7. Representative accepted-corpus broker/type coverage.
8. Human-readable evidence для post-hoc adjudication без raw customer bytes в Git.

## 12. Synthetic versus accepted corpus

### 12.1 Честная статистика

| Corpus/evidence | Размер | Что доказывает | Что не доказывает |
| --- | ---: | --- | --- |
| Gate 1 tracked payload fixtures | 7 payload files | Basic format/duplicate/unsupported mechanics | Customer/broker coverage |
| V6 successor semantic benchmark | 12 synthetic cases | Two-type edge cases, bindings/cardinality | Real broker generalization |
| GOAL 15/16 governed subset | 10 of 12 | Mechanical A/B/C route comparison | Model quality |
| GOAL 12 workload | 4 cases × 3 planned providers; 8 actual calls | Exact technical/semantic smoke on Nano/Haiku | Full benchmark or accepted corpus |
| Semantic-visual actual-corpus benchmark | 9 crops, 6 PDF hashes | Table-plan handling: 8 accepted, 1 unsupported | Type-first financial semantics |
| Gate 1 private acceptance | 104 source identities, 80 logical docs | Normalization/document-memory technical acceptance | Customer acceptance or Variant B quality |
| Historical integrated 2-НДФЛ reproof | 24 typed outputs, 351 facts | Narrow deterministic XML extraction | Tax calculation/declaration |

Нельзя суммировать все benchmark directories как «уникальные fixtures»: manifests переиспользуют и наследуют одни cases. Для текущей type-first дискуссии canonical number — 12 V6 synthetic cases, из которых GOAL 15/16 рассматривают 10.

### 12.2 Broker families

Private safe registry даёт signals, а не нормативную one-to-one classification:

- 38/63 records имеют хотя бы один probable-broker signal;
- distinct labels: BCS, IBKR, Otkritie, Sber, VTB;
- signals могут пересекаться, поэтому нельзя утверждать «пять доказанно поддерживаемых families»;
- Sber generalization не закрыта без positive unseen same-family holdout.

Public semantic-visual manifest имеет candidate IDs Betterment, DriveWealth, IBKR и Moomoo, 9 crops из 6 PDFs. В нём нет authoritative `broker_family` field, и это technical benchmark, а не production support matrix: `services/broker-reports-gate1-proof/benchmarks/semantic_visual_actual_corpus_v1/manifest.json:103-111`.

### 12.3 Финансовые типы

Managed minimal ontology содержит два типа. Type-first semantic decision фактически проверялся только на synthetic representations этих двух типов и unclassified cases. Реальные documents проходили:

- Gate 1 normalization/document memory;
- public Gate 2 handoff validator;
- исторические bounded Gate 2 paths, включая FNS 2-НДФЛ;
- отдельный semantic-visual table benchmark.

Но full Gate 2 package builder в Gate 1 acceptance boundary был `not_run_outside_gate1_acceptance_boundary`: `docs/reports/2026-07-18/BROKER_REPORTS_GATE1_ACTUAL_CUSTOMER_CORPUS_ACCEPTANCE.v1.safe.json:4380-4400`. Variant B не выполнялся ни на одном accepted-corpus document.

### 12.4 Переносимость GOAL 15–16

**[proven]** Механическая decision table переносится на любой input, если plausible set и option counts уже верны.

**[supported]** Разделение plausibility и constructibility остаётся хорошим boundary при расширении типов.

**[hypothesis]** Модель сохранит acceptable type recall/precision на новых brokers, реальных layouts и большой ontology.


Следовательно, GOAL 15–16 хорошо фиксируют responsibility split, но почти ничего не доказывают о реальной model accuracy.

## 13. Масштабирование финансовой онтологии

Current GOAL 16 request с двумя cards измерен как `2052–2210` provider-neutral bytes. Две representative cards занимают около 1.3 KB; рост all-cards surface приблизительно линейный. Ниже — planning estimate при сохранении текущей плотности card, не provider tokenizer и не measured quality:

| Типов | Оценка request bytes | Оценка состояния |
| ---: | ---: | --- |
| 2 | 2.05–2.21 KB measured | Укладывается в future 2.5 KB target |
| 10 | ~7–8 KB | Уже выше 4.5 KB current sealed-request ceiling; all-cards profile неразумен |
| 25 | ~17 KB | Нужен deterministic shortlist; flat discrimination резко сложнее |
| 50 | ~33 KB | Превышает 30 KB Context V2.1 aggregate target; вероятны hierarchy/two-stage needs |
| 100 | ~65 KB | Flat all-types request несовместим с текущим budget/portability intent |

Sources: `docs/stage2/contracts/BROKER_REPORTS_GATE2_TYPE_FIRST_FAIL_CLOSED.v1.json:byte_budget`; `gate2_financial_semantic_v6_context_linter.py:73-81`; `gate2_financial_semantic_v6_packet.py:4373-4374`.

### 13.1 Где текущий профиль перестаёт быть разумным

Порог наступает **до или при переходе к 10 типам**, если модель видит все cards:

- request превышает current sealed budget;
- число pairwise nearest-competitor distinctions растёт;
- вероятность false empty/singleton/superset становится отдельной quality problem;
- разные providers могут по-разному соблюдать длинные enums и ordered-set semantics;
- economy policy придётся requalify по tokens, latency и call budget.

Deterministic shortlist нужен до массового расширения ontology. Иерархическая классификация может понадобиться ближе к 25–50 типам, но это пока гипотеза и не повод проектировать новый framework. Сначала следует измерить shortlist recall и type confusion на accepted corpus.

## 14. Продуктовый прогресс против evidence overhead

### 14.1 Независимая оценка

- GOAL 12 оправдан: дал реальные model/transport facts и не допустил слабые модели.
- GOAL 13 оправдан: не позволил исправлять expected answers или Prompt наугад.
- GOAL 14 полезен: установил separation constructibility/plausibility и обеспечил сравнимость.
- GOAL 15 полезен как decision convergence: выбрал минимальный вариант и остановил преждевременный Variant C.
- GOAL 16 полезен как safety contract, но не добавил пользовательской capability. Он добавил крупный contract/builder/test surface для нулевого runtime change.

### 14.2 Стало ли evidence самоцелью

До GOAL 15 evidence снижал риск неверного corrective change. В GOAL 16 он всё ещё зафиксировал важные hard gates. Но ещё один analysis-only GOAL будет иметь отрицательную отдачу:

- GOAL 13–16 дали `0` provider calls и `0` active product capabilities;
- GOAL 15/16 `10/10` повторяет oracle-driven mechanics, а не проверяет главный риск;
- нерешённые вопросы требуют executable implementation и data, а не новой матрицы.

**[supported]** Проект достиг точки evidence overhead: доказательная дисциплина остаётся необходимой, но следующий результат должен быть кодом inactive slice, а не ещё одним report family.

### 14.3 Какой продуктовый прогресс реально нужен

Сначала закрыть один semantic decision seam и устранить parallel-route ambiguity. После bounded inactive proof выбрать:

- либо допускать Variant B к model/accepted-corpus qualification;
- либо оставить financial semantic output manual/unclassified и двигать узкий deterministic FNS/Gate 3 product slice.

Нельзя одновременно считать Variant B готовым и начинать широкий Gate 4.

## 15. Технический долг и дублирование

1. **Parallel semantic routes.** Legacy production runtime и V6 qualification chain обходят друг друга.
2. **Current activation/admission gap.** Legacy Financial Evidence path интегрирован условно: valve default false; даже после его включения все workload production allowlists пусты.
3. **V5 naming in V6.** Shared projection owner корректен, но имя скрывает current authority.
4. **Different persistence semantics.** Product writes to ArtifactStore; V6 persistence owner делает proof serialization/restore.
5. **Workspace shell gap.** Curated Workspace Model остаётся proposal; Pipes не равны готовому scenario entrypoint.
6. **Live parity drift.** Последний live closure относится к stage revision `60b273694479705848d9b0c4ac8f3392ea9b351d` (`docs/reports/2026-07-22/BROKER_REPORTS_WORKFLOW_FINAL_LIVE_REPROOF_AND_CLOSURE.report.md:12-21`); current Gate 1 bundle изменился. Current HEAD-to-live exact readback не доказан.
7. **Historical receipt heads.** GOAL 12 receipt содержит execution head `ed12ee627282f7954fb494c35f2a7f2b6e75ff7e`, GOAL 15/16 receipts — свои base commits. Это корректная immutable history, но их нельзя выдавать за current execution.
8. **Stale wording.** PRD line 29 заявляет deployed bounded contour и старые model acceptances. Current code-owned admissions empty, поэтому этот historical product statement шире current runtime truth.
9. **Sber acceptance debt.** Actual-corpus implementation есть, positive unseen holdout нет.
10. **Ontology scale debt.** Current full-card profile уже не подходит к 10 типам.

Generated bundles являются build outputs, не owners. Focused bundle/architecture checks в этом аудите прошли; current stale generated artifact не обнаружен. Это не current live parity proof.

## 16. Открытые вопросы

| Вопрос | Текущее состояние |
| --- | --- |
| Какова false-singleton rate у exact type-first prompt? | Нет данных |
| Какова rate на accepted corpus? | Нет данных |
| Сколько реальных broker families имеет adjudicated semantic coverage? | Не зафиксировано authoritative field; signals не равны support |
| Насколько часты multiple same-type options? | Нет accepted-corpus metric; C trigger был 0/10 synthetic |
| Какой deterministic shortlist сохраняет recall? | Не исследовано |
| Нужно ли включать все types при 10+ ontology? | Current budget показывает, что нет |
| Какой current live Pipe/asset hash? | Требуется fresh readback |
| Есть ли customer acceptance Gate 1 output? | Нет |
| Когда можно включить Sber profile? | После unseen positive holdout |
| Какой узкий Gate 3 user slice ценнее всего? | Нужен product choice после Gate 2 seam |
| Кто утверждает tax methodology и XLSX schema? | Не закрыто |

## 17. Рекомендуемая точка продолжения

### 17.1 Следующий bounded goal

Рекомендуется **NON_ACTIVE_TYPE_FIRST_VARIANT_B_IMPLEMENTATION**, без provider calls и без runtime activation.

Минимальный scope:

1. Добавить additive inactive profile в существующий `Gate2FinancialSemanticV6PacketFactory`, не создавая нового owner.
2. Использовать current source projection и managed type cards; private mapping receipt связывает local type keys с backend IDs.
3. Добавить strict response profile/parser в существующий Choice owner.
4. Добавить exact linter/sealed request method в существующий linter и canonical request builder profile.
5. Добавить в существующий Expansion owner additive type-first profile: reason derives from returned cardinality; typed route только при ровно одной valid complete matching option. Existing V6 profile остаётся неизменным.
6. Сохранить existing validation/materializer authorities без bypass.
7. Добавить Decision Evidence/replay profile и Economy accounting; calls remain zero в local proof.
8. Выполнить local simulated-terminal-envelope E2E:

```text
Packet
→ Context/type cards
→ linter/sealed request
→ request builder
→ provider adapter extraction without transport
→ type-first parser
→ expansion
→ validation
→ materialization
→ persistence snapshot
→ evidence/replay
```

9. Добавить adversarial qualification fixtures, включая true `2+` → returned singleton + one matching option. Product path не сможет распознать semantic lie без oracle; zero-call local comparator живёт в existing Decision Evidence owner. Для последующей provider qualification нужно additive type-first profile в существующем `Gate2FinancialSemanticV6ContextV21BudgetSmokeCoordinator`, а не новый coordinator; он обязан посчитать `false_singleton_typed_total` и заблокировать admission.
10. Active Context/Choice/production admissions остаются неизменными.

### 17.2 Что делать после реализации

Только после local E2E:

1. sealed provider request proof;
2. bounded exact-model qualification без retries/repair/fallback;
3. accepted-corpus adjudication по broker/type families;
4. hard-gate review;
5. отдельное решение об activation.

Variant C следует открывать только если accepted corpus покажет материальную частоту singleton-type/multiple-option state и доказанный net gain.

### 17.3 Почему не ещё один анализ

Главные unknowns теперь исполнимые: отсутствует код path и отсутствуют model/corpus measurements. Новый аналитический документ не может заменить ни одно из них.

## 18. Appendix: authority map и evidence

### 18.1 Карта артефактов

Счётчики в safe receipt относятся к component-level состоянию строк, а не к числу доступных product capabilities или live objects: A implementation=`10`, B implementation=`13`, contract-only=`2`, simulation-only=`2`, executed evidence-only=`1`. Всего строк `28`.

| Артефакт | Назначение | Текущий owner | State | Активен | Используется runtime | Evidence class |
| --- | --- | --- | --- | --- | --- | --- |
| Curated Workspace Model | User scenario entrypoint | OpenWebUI config/admin; repo только proposal | C | Нет | Нет | `contract_only` |
| Gate 1 Pipe | Intake/orchestration/safe report | `openwebui_actions.broker_reports_gate1_pipe.Pipe` | A component | Maintained code; current live unverified | Current code yes; live execution historical | `executed`, `historical` |
| Normalization/document memory | Neutral representation/DCP | `Gate1Normalizer`, bounded graph factories | A component | Maintained code; current live unverified | Current code yes; live execution historical | `executed`, `historical` |
| ArtifactStore/Resolver | Private persistence/access/lineage | `ArtifactStoreFactory`, `ArtifactResolver` | A component | Maintained code; current live unverified | Current code yes; live execution historical | `executed`, `historical` |
| Source projection/readiness | Bounded Gate 2 input | `Gate2InputReadinessFactory` | A component | Maintained code | Current code yes; model call admission-blocked | `executed`, `historical` |
| Minimal Semantic Pack | Two-type target meaning | Semantic Contract + managed Pack | B | Нет | Shared validation only | `implemented_inactive` |
| Type-card projection | Model-visible type cards | `Gate2FinancialSemanticV5ProjectionFactory` | B | Нет | Qualification/local proof | `implemented_inactive` |
| Evidence Bundle | Seal source/Pack/bindings | `Gate2FinancialEvidenceBundleFactory` | B | Нет | Qualification/local proof | `implemented_inactive` |
| Candidate Compiler | Complete code-owned options | `Gate2FinancialCandidateCompilerFactory` | B | Нет | Qualification/local proof | `implemented_inactive` |
| V6 Packet/Context V2.1 | Model candidate + mapping receipt | `Gate2FinancialSemanticV6PacketFactory` | B | Нет | Qualification | `implemented_inactive`; executed smoke |
| V6 Prompt | Semantic instruction | `financial_semantic_v6_prompt` | B | Нет | Qualification | `implemented_inactive` |
| Choice V6/V2.1 | Schema/parser/restoration | `Gate2FinancialSemanticV6ChoiceContractFactory` | B | Нет для target | Qualification | `implemented_inactive` |
| Context Linter | Totality/budget/sealed request | `Gate2FinancialSemanticV6ContextLinterFactory` | B | Нет | Qualification | `implemented_inactive` |
| Request builder | Canonical request | `Gate2OpenWebUIRequestBuilder` | A component | Да generic | Да; Type-first absent | `executed` |
| Provider adapters/client | Provider projection/transport/extraction | Adapter/client factories | A component | Да generic | Qualification/historical; current product blocked | `executed`, `historical` |
| V6 Expansion | Local response → canonical decision | `Gate2FinancialSemanticV6DecisionExpansionFactory` | B | Нет | Qualification/local proof | `implemented_inactive` |
| Validated decision | Canonical invariants | `Gate2FinancialEvidenceValidatedDecisionFactory` | A component | Да shared | Legacy conditional route/local proof | `executed`, `historical` |
| Materializer | Typed/unclassified artifacts | `Gate2FinancialEvidenceMaterializerFactory` | A component | Да shared | Legacy conditional route/local proof | `executed`, `historical` |
| Financial Domain persistence | Snapshot serialize/restore | `Gate2FinancialDomainPersistenceFactory` | B | Нет product | Offline proof | `implemented_inactive` |
| Decision Evidence/replay | Exact qualification evidence/replay | V6 Evidence owner | B | Нет product | Qualification/offline | `implemented_inactive`; executed |
| Economy Budget | Call/usage/cost accounting | `Gate2EconomyBudgetSessionFactory` | A component | Да | Qualification/conditional runtime | `executed` |
| Economy admission | Production allowlist | Workload policy/provider selection | A fail-closed component | Да | Да; allowlists empty | `executed` |
| Production runtime | Legacy Registry-driven model route | `Gate2FinancialEvidenceProductionRuntimeFactory` | B current | Valve off + no model admission | Conditional path, currently stopped | `implemented_inactive`; `historical` execution |
| Synthetic fixtures | Frozen semantic cases | Fixture/benchmark factories | C | Нет | Tests/qualification | `simulation_only` |
| Accepted corpus | Gate 1 technical corpus evidence | Private registry + safe receipt | Evidence-only, not implementation | N/A | Gate 1 historical proof | `executed`, `historical`; not Type-first |
| Qualification coordinator | One-shot V6/GOAL 12 run | `Gate2FinancialSemanticV6ContextV21BudgetSmokeCoordinator` | B product / executed qualification | Нет product | Qualification | `implemented_inactive`; executed |
| Type-first contract | Normative Variant B surface | GOAL 16 contract | C | Нет | Нет | `contract_only` |
| GOAL 15 A/B/C simulation | Architecture comparison | Offline builder | C | Нет | Нет | `simulation_only` |

### 18.2 Key evidence files

- Gate architecture: `docs/stage2/blueprints/BROKER_REPORTS_GATE_ARCHITECTURE.md`
- Authority map: `docs/stage2/contracts/BROKER_REPORTS_ARCHITECTURE_AUTHORITIES.md`
- Product PRD: `docs/stage2/prd/BROKER_REPORTS_XLS_NDFL_NATIVE_WORKFLOW_PRD.md`
- Gate 1 actual corpus: `docs/reports/2026-07-18/BROKER_REPORTS_GATE1_ACTUAL_CUSTOMER_CORPUS_ACCEPTANCE.v1.safe.json`
- Integrated actual-corpus reproof: `docs/reports/2026-07-21/BROKER_REPORTS_GOAL5_INTEGRATED_ACTUAL_CORPUS_REPROOF.v1.safe.json`
- GOAL 12 receipt: `docs/reports/2026-07-29/BROKER_REPORTS_GATE2_CONTEXT_V2_1_BUDGET_MODEL_SMOKE_GOAL12.receipt.safe.json`
- GOAL 13 forensic receipt: `docs/reports/2026-07-30/BROKER_REPORTS_GATE2_CONTEXT_V2_1_POST_SMOKE_FORENSIC_AUDIT_GOAL13.receipt.safe.json`
- GOAL 14 comparative report: `docs/reports/2026-07-30/BROKER_REPORTS_GATE2_CONTEXT_V2_1_EVIDENCE_FIRST_COMPARATIVE_REVIEW_GOAL14.report.md`
- GOAL 14 comparative receipt: `docs/reports/2026-07-30/BROKER_REPORTS_GATE2_CONTEXT_V2_1_EVIDENCE_FIRST_COMPARATIVE_REVIEW_GOAL14.receipt.safe.json`
- GOAL 15 architecture report: `docs/reports/2026-07-30/BROKER_REPORTS_GATE2_TYPE_FIRST_SEMANTIC_DECISION_ARCHITECTURE_AUDIT_GOAL15.report.md`
- GOAL 16 Markdown contract: `docs/stage2/contracts/BROKER_REPORTS_GATE2_TYPE_FIRST_FAIL_CLOSED.v1.md`
- GOAL 16 machine contract: `docs/stage2/contracts/BROKER_REPORTS_GATE2_TYPE_FIRST_FAIL_CLOSED.v1.json`
- GOAL 16 receipt: `docs/reports/2026-07-30/BROKER_REPORTS_GATE2_TYPE_FIRST_FAIL_CLOSED_CONTRACT_GOAL16.receipt.safe.json`

### 18.3 Evidence interpretation notes

- GOAL 12 `repository_head=ed12ee627282f7954fb494c35f2a7f2b6e75ff7e` — immutable execution head, не current HEAD.
- GOAL 15/16 base commits — correct generation bases, не current runtime execution.
- Historical live Pipe receipt доказывает более раннюю deployed revision; current HEAD parity требует fresh readback.
- `10/10` GOAL 15/16 — oracle-driven mechanical route, не model accuracy.
- Test counts без path description не являются acceptance; в этом документе они привязаны к конкретным owners.
- Ни один созданный audit file не содержит raw provider payload, customer values, private paths или secrets.
