# Broker Reports Gate 5 — Runtime Capability Contract (G5.15)

Date: 2026-08-10

Goal status: `G5.15_CLOSED`

Proof outcome: `PROVEN`

Product status: `INACTIVE`

## Ответ

Да. Реально доказанные возможности текущего Gate 5 удалось представить как
маленький closed machine-readable contract из пяти семантических capabilities:

```text
future LLM author
        |
        v
[ Runtime Capability Contract ]
        |
     stable IDs
        |
        v
[ Runtime Resolver ]
        |
        v
[ Existing Proven Owners ]
```

Contract не экспортирует Python API, не содержит tax/declaration rules и не
создаёт workflow DSL. Unknown capability fail closed. Contract-only и
binding-only drift детектируются при загрузке и тестами.

Последующая цепочка остаётся гипотезой следующего GOAL:

```text
Official Requirements
        -> future Declaration Definition
        -> references capabilities
        -> Runtime
```

G5.15 не проектировал Definition Package и не выполнял LLM compilation.

## Определение capability

Runtime capability — это устойчивое семантическое действие, для которого
одновременно существуют:

- stable capability ID;
- закрытые input/output contracts;
- явные preconditions и failure conditions;
- различимые provenance classes;
- доказанный executable owner;
- точный code binding без догадок и fallback.

Наличие функции, factory или отдельного G5.x proof само по себе capability не
создаёт. Scenario-specific behavior может оставаться обычным reviewed code,
не становясь универсальным primitive.

## Capability Inventory

| Existing mechanism | Semantic capability candidate | Public to LLM? | Why / why not | Proven owner | Preconditions |
| --- | --- | --- | --- | --- | --- |
| G5.2 methodology-driven selection | часть `resolve_required_values_v0` | не отдельно | raw selection по `financial_type` — внутренняя стадия sufficiency, а не самостоятельная декларационная операция | `Gate5MethodologySelectionRuntimeFactory.create` | current Gate 4 case; closed non-empty requirements |
| G5.3 Supplemental persistence/read | часть `obtain_one_missing_money_input_v0` | не отдельно | public raw write позволил бы author управлять artifact refs/binding; persistence должна остаться под G5.6 deterministic binding | `Gate5SupplementalFactRuntimeFactory.create` | trusted case/run/workspace context; validated money; write before recheck |
| G5.4 combined sufficiency check | часть `resolve_required_values_v0` | не отдельно | decision seam уже корректно скрыт за automatic G5.5 discovery | `Gate5CombinedRequirementCheckRuntimeFactory.create` | one tagged Financial Case or Supplemental source; ambiguity rejected |
| G5.5 same-run discovery + check | `resolve_required_values_v0` | да | устойчивый смысл: разрешить требуемые значения без caller artifact refs | `Gate5SupplementalFactDiscoveryRuntimeFactory.create` | trusted current case; same-run Supplemental only; G5.4 closed decision |
| G5.6 single-input human loop | `obtain_one_missing_money_input_v0` | да | устойчивый bounded input-acquisition seam; не generic interview | `Gate5SingleInputHumanLoopRuntimeFactory.create` | exactly one missing money input; strict structured model path; deterministic answer match |
| G5.7 methodology calculation | часть `execute_published_calculation_behavior_v0` | только через G5.8 | caller-supplied methodology bytes не должны быть authority; прямой G5.7 seam остаётся implementation detail | `Gate5MethodologyCalculationRuntimeFactory.create` | supported calculation schema/behavior; satisfied values; one currency |
| G5.8 trusted methodology | `execute_published_calculation_behavior_v0` | да, как composed operation | stable operation — выполнить reviewed behavior из exact published methodology, а не отдельно «прочитать JSON» | `Gate5TrustedMethodologyCalculationRuntimeFactory.create` | registered identity/version; resource hash/schema valid; G5.7 behavior supported |
| G5.9 managed publication research | managed publication | нет | `NOT_JUSTIFIED_YET`; executable owner не создан, repository authority остаётся дешевле | отсутствует | отсутствует immutable managed publication contract |
| G5.10 declaration-backwards research | author declaration semantics | нет | research finding, не runtime behavior | отсутствует | отдельный future authoring contract не доказан |
| G5.11 external evidence routing | `research_authoritative_fact` | нет | runtime не выполняет research/provider/browser flow и принимает только один fixed 2025 rate-schedule requirement; generic capability была бы overclaim | `Gate5ExternalEvidenceRuntimeFactory.create` для bounded prepare/accept | exact fixed requirement/entity/source/effective/hash evidence only |
| G5.12 declaration projection | `project_validated_declaration_fragment_v0` | да, case-time only | mechanical projection — устойчивый смысл; candidate validation для одного evidence family остаётся internal authoring support | `Gate5DeclarationProjectionRuntimeFactory.create` | repository spec/evidence valid; all five compatible concepts present |
| G5.13 securities Tax Model | universal `build_tax_model` | нет | `securities_disposal_operation_tax_model_v0` — reviewed scenario-specific behavior, не универсальный primitive | `Gate5SecuritiesDisposalTaxModelRuntimeFactory.create` | exact published securities methodology and closed scenario prerequisites |
| G5.14 category aggregation | `aggregate_complete_category_scope_v0` | да | устойчивый смысл: агрегировать complete compatible member set, не raw facts | `Gate5TaxPeriodCategoryAggregationRuntimeFactory.create` | at least two complete members; period/category/currency/loss consensus; exact completeness binding |

Итоговая гранулярность не повторяет G5 numbering. G5.2–G5.5 схлопнуты в одну
public operation; G5.7 публикуется только через trusted G5.8 wrapper; G5.11 и
G5.13 честно оставлены за public boundary.

## Минимальный contract

Package resource:

```text
gate5_runtime_capability_contract.v0.json
```

Exact raw size: `9,861` bytes.

Exact SHA-256:

```text
61fc352ae0e77e92cc1f06fb71fbbf5c2c79e6123bc40b8c930140ead774c8e8
```

`.gitattributes` pins this raw resource to LF for cross-checkout hash parity.

Published IDs:

```text
resolve_required_values_v0
obtain_one_missing_money_input_v0
execute_published_calculation_behavior_v0
project_validated_declaration_fragment_v0
aggregate_complete_category_scope_v0
```

Все пять имеют `implementation_status = proven` и `execution_phase =
case_time`. Универсальной authoring-time capability текущий contour не доказал.

## Model-visible proof

`Gate5RuntimeCapabilityContract.model_projection()` удаляет только internal
`conformance` block и оставляет semantic IDs, meaning, inputs, preconditions,
outputs, failures, value kinds, provenance и implementation status.

Exact canonical UTF-8 payload: `6,775` bytes.

Из него тестом исключены:

```text
binding_id
owner_contract
Gate5 class names
RuntimeFactory names
.py paths
```

Payload не содержит methodology bytes, formulas, rates, XML paths/codes,
case values, SQL или artifact identifiers. Один payload остаётся обозримым;
отдельная model-contract subsystem не создана.

## Runtime binding и conformance

Maintained owner:

```text
Gate5RuntimeCapabilityContractFactory.create
        -> SHA-pinned package resource
        -> closed shape validation
        -> exact contract/binding parity

Gate5RuntimeCapabilityResolverFactory.create
        -> closed capability ref
        -> static code-owned binding
        -> existing reviewed factory
```

Binding table обычная статическая Python-таблица. Она не использует dynamic
imports, import-by-string, plugin loading или model-visible constructor args.

| Proof | Observable result |
| --- | --- |
| known capability | все 5 IDs resolve в exact binding/factory/operations |
| unknown capability | `calculate_3ndfl_2025` -> `gate5_runtime_capability_unsupported` |
| malformed capability ref | missing/extra/wrong schema -> `gate5_runtime_capability_ref_invalid` |
| invalid internal dependencies | extra `candidate_spec` rejected before G5.12 factory construction |
| missing owner precondition | resolved G5.12 runtime сохраняет `gate5_declaration_projection_input_invalid`; fragment не создаётся |
| contract/resource tamper | exact raw SHA mismatch blocks loading |
| contract/runtime drift | ID-set, binding ID, factory `create` и runtime operations проверяются при factory construction; mismatch -> `gate5_runtime_capability_contract_drift` |
| actual execution | resolved G5.12 owner реально создаёт deterministic projected fragment with bounded validation claim |

Code function не становится public автоматически: capability появляется
только при одновременном explicit resource entry и explicit binding. Поэтому
implementation может существовать внутри runtime без утечки в LLM language.

## Provenance boundary

Contract различает:

```text
financial_case_evidence
user_case_evidence
user_verified_completeness
methodology_derived_result
declaration_projection
```

G5.11 external authoritative evidence не переименована в user evidence и не
опубликована как якобы generic research capability. Эти источники не считаются
взаимозаменяемыми.

## Authoring-time vs case-time

Audit нашёл authoring support, но не universal authoring runtime language:

- G5.10 — research report;
- G5.11 не выполняет external research;
- G5.12 factory валидирует candidate только против одного pinned evidence
  family;
- managed publication G5.9 не имеет executable owner.

Поэтому вводить authoring-time capability taxonomy или фиктивные operations
не потребовалось. Future model author может читать current case-time contract,
но authoring/compiler execution остаётся следующим отдельным вопросом.

## Hardcode Boundary

```text
DECLARATION-SPECIFIC COMPOSITION
        должна уйти из orchestration Python
                    |
                    v
       Runtime Capability Contract
             stable semantic IDs
                    |
                    v
STABLE EXECUTION MECHANICS
        ordinary reviewed code
```

Hardcode, который желательно убрать позже:

- порядок шагов конкретной версии декларации;
- выбор последовательности data acquisition / calculation / aggregation /
  projection для конкретного Declaration Definition;
- декларационно-специфичную orchestration ветку.

Полезный hardcode, который остаётся code-owned:

- G5.7 reviewed Decimal arithmetic и unknown-behavior rejection;
- G5.8 repository identity/resource/hash pins;
- G5.3/G5.5 access, lifecycle, trusted scope и same-run checks;
- G5.6 deterministic evidence-versus-proposal validation;
- G5.12 closed candidate/input/target/evidence validation;
- G5.14 member consensus, canonical hash и completeness binding;
- статическое сопоставление пяти capability IDs с proven factories.

Это не `zero hardcode`: declaration composition должна стать data/config,
тогда как стабильная execution semantics остаётся reviewed code.

## Test integrity и verification

Shell context: Windows PowerShell, service cwd
`services/broker-reports-gate1-proof`, Python 3.11. ENV для тестов не требовался.
Runner реально выполнял tests; completed runs дали terminal summaries.

```text
new G5.15 focused:
9 passed in 0.72s

all Gate 5 tests:
60 passed in 12.77s

G5.15 + architecture:
38 passed in 27.54s

extended ArtifactStore/lifecycle/architecture/Gate3/Gate4/
Gate5/bundles/privacy replay:
189 passed, 5 warnings in 61.00s

ruff check + format check for new Python files:
passed

closed-world staged package import/resource/hash/model-size proof:
passed
```

Новые tests не mock'ят unit/core owner. Они загружают реальный package
resource, разрешают реальные factory classes и выполняют реальный G5.12
runtime. Observable output и exact owner error проверяются напрямую.

Необратимой boundary у нового contract/resolver нет: он ничего не пишет. Для
использованного G5.12 owner также нет write boundary. Invalid dependency и
missing input прекращают control flow до результата.

Первый focused run имел один assertion failure: test ошибочно запрещал
разрешённый package-resource import `from importlib import resources` вместе с
dynamic import. Assertion был сужен только до `importlib.util`,
`importlib.machinery`, `import_module` и `__import__`; runtime contract не
ослаблялся. Повторный run прошёл.

Первый all-Gate5 command не выполнил collection из-за literal PowerShell
wildcard. Он был повторён с явным PowerShell array. Это shell attribution, не
test failure.

Full service suite (`3,038` tests collected in `2.81s`) был запущен с лимитом
`900s`, оставался активным `904s` и завершён внешним timeout без pytest summary
или assertion diff:

```text
FULL_SUITE_TERMINAL_VERDICT = NOT_OBTAINED_TIMEOUT
```

Это не записано ни как pass, ни как assertion failure. Расширенный
189-test boundary replay завершён и является финальным локальным proof для
G5.15.

## Factory/closed-world proof

Canonical routes:

```text
Gate5RuntimeCapabilityResolverFactory.create
  -> Gate5RuntimeCapabilityContractFactory.create
  -> exact static binding
  -> existing Gate5*RuntimeFactory.create
```

`FACTORY_REQUIRED` и `FORBIDDEN` anchors присутствуют и test-covered. UI,
control-check и smoke path для G5.15 отсутствуют: product status `INACTIVE`,
поэтому parity не симулировалась через новый route. Existing product bundles
прошли parity tests и не получили G5.15 consumer.

Closed-world proof скопировал только Python package в отдельный staged root и
подтвердил, что imported module и JSON resource разрешены из этого artifact,
resource SHA exact, capabilities `5`, model bytes `6,775`. Workspace-only
imports, filesystem path hacks, new dependencies и ENV contracts не добавлены.

## KISS

Добавлены:

- один JSON contract resource;
- один LF rule для byte-stable resource hash;
- один contract/resolver module со статическими bindings;
- один focused conformance test file;
- один supporting contract;
- одна authority-map запись;
- этот dated report.

Не созданы Capability Platform, plugin system, workflow/rules DSL, dynamic
loading, registry/service/DB/table, Tax Case, new Tax Model, Declaration
Definition, LLM compiler, GUI, provider call или product activation.

## Stop

`G5.15_CLOSED`. Следующий slice не начат и этим отчётом не авторизован.
