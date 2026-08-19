# Broker Reports Gate 5 — Capability Basis / Expressiveness Audit (G5.17)

Date: `2026-08-10`

Status: `G5.17_CLOSED`

Outcome: `FIVE_PRIMITIVE_FAMILIES_ARE_SUFFICIENT`

Product status: `RESEARCH_ONLY_NO_RUNTIME_CHANGE`

## Verdict

Для уже доказанных declaration-driven задач не нужен шестой base primitive.
Минимальный semantic basis остаётся равным пяти устойчивым типам действий:

1. разрешить закрытый набор требуемых значений;
2. получить у человека ровно один отсутствующий typed fact;
3. исполнить точный опубликованный deterministic behavior;
4. агрегировать exact complete scope;
5. спроецировать complete semantics через validated projection.

Текущие пять G5.15 capabilities правильно выделяют эти action families, но не
все текущие `v0` contracts одинаково выразительны. Перед повторным clean-context
Declaration Definition trial нужно доказать одно минимальное несовместимое
обобщение:

```text
execute_published_calculation_behavior_v0
        ↓ versioned replacement, not silent widening
execute_published_typed_behavior_v1
```

Новый primitive не добавляется. Новый contract должен разрешать только
hash-pinned behavior/result pairs из закрытого runtime registry и возвращать
typed result envelope. Первым обязательным conformance case должен стать уже
существующий G5.14 operation Tax Model behavior. Это устраняет искусственный
разрыв `execute -> aggregate`, обнаруженный G5.16.

Group-level tax base после такого изменения остаётся новым reviewed behavior и
новым methodology artifact, а не capability. Non-money human inputs требуют
расширения закрытого набора value kinds у существующих resolve/acquisition
families, но такое расширение пока не доказано case-time implementation и не
должно блокировать первый contract proof. Generic external research не должен
попадать в case-time contract. Completeness не следует отделять от aggregation
до появления concrete composition, которой действительно нужен отдельный
переиспользуемый completeness result.

G5.15 contract, runtime code и capability registry в G5.17 не изменялись.
Blind-authoring trial не повторялся.

## Scope и evidence

Audit опирается на repository evidence, а не на желаемую архитектуру:

| Evidence | Использованный результат |
| --- | --- |
| [G5.10 declaration-backwards analysis](../2026-08-09/BROKER_REPORTS_GATE5_DECLARATION_BACKWARDS_TAX_MODEL_G5_10.report.md) | минимальный Tax Model, missing context/value kinds, различие source facts, methodology и projection |
| [G5.11 external evidence routing](../2026-08-09/BROKER_REPORTS_GATE5_EXTERNAL_EVIDENCE_ROUTING_G5_11.report.md) | bounded authoritative reference proof и разделение external evidence от Financial Case |
| [G5.12 declaration projection](../2026-08-09/BROKER_REPORTS_GATE5_DECLARATION_PROJECTION_G5_12.report.md) | deterministic projection как stable mechanic с versioned projection artifact |
| [G5.13 operation Tax Model](../2026-08-09/BROKER_REPORTS_GATE5_DECLARATION_DRIVEN_TAX_MODEL_G5_13.report.md) | reviewed classification/expense behavior и complete single-operation model |
| [G5.14 category aggregation](../2026-08-09/BROKER_REPORTS_GATE5_TAX_PERIOD_CATEGORY_AGGREGATION_G5_14.report.md) | aggregation complete operation models, exact member binding и fail-closed completeness |
| [G5.15 Runtime Capability Contract](BROKER_REPORTS_GATE5_RUNTIME_CAPABILITY_CONTRACT_G5_15.report.md) | пять реально доказанных public capabilities и их exact `v0` boundaries |
| [G5.16 Declaration Definition authoring](BROKER_REPORTS_GATE5_DECLARATION_DEFINITION_AUTHORING_G5_16.report.md) | несовместимый operation-model producer и отсутствующий group-tax-base behavior |

Scope stop: это architecture audit. Он не публикует новый contract, behavior,
methodology, reference snapshot или authoring framework и не активирует продукт.

## Baseline G5.15

| Current capability | Что реально доказано | Наблюдаемая граница |
| --- | --- | --- |
| `resolve_required_values_v0` | Financial Case first, затем same-run supplemental fact; satisfied либо missing; один tagged source | только `financial_case_role_value` и `money` |
| `obtain_one_missing_money_input_v0` | один missing money fact, bounded human answer, deterministic verification, persistence before recheck | не boolean/enum/date/status/identifier |
| `execute_published_calculation_behavior_v0` | exact hash-pinned methodology, reviewed calculation, source-tagged money, deterministic decimal result | единственный output contract — `broker_reports_gate5_trusted_calculation_result_v0`; operation Tax Model не возвращается |
| `project_validated_declaration_fragment_v0` | complete stable semantics через repository-pinned evidence-validated projection | declaration fragment, не полный XML и не tax reasoning |
| `aggregate_complete_category_scope_v0` | compatible operation models + exact completeness binding; projection только при complete scope | один taxpayer/category/period contract; минимум два members |

G5.13 `run_operation` и G5.14 aggregation доказывают, что runtime уже умеет
создать и использовать operation model внутри trusted implementation. G5.16
доказывает более узкий факт: public capability surface не позволяет получить
этот member, потому что current execute capability закреплена за старым
calculation-result contract. Это contract-surface mismatch, а не отсутствие
самого действия runtime.

## Рабочие определения

**Capability** — стабильный deterministic тип действия runtime с закрытыми
preconditions, input/output boundary и fail-closed failures. Ее смысл не должен
меняться вместе с конкретной формулой, кодом дохода или версией декларации.

**Behavior** — reviewed domain semantics, которую capability исполняет по
точному identity/version/hash. Например, правила classification и expense
allowability для securities disposal являются behavior, а не capability.

**Artifact** — immutable versioned content, нужный для исполнения: methodology,
behavior declaration, reference snapshot, projection spec или evidence pack.
Capability отвечает «что runtime умеет сделать», artifact — «с каким точным
опубликованным содержимым он это делает».

**Value kind** — детерминированный тип значения и его validation/evidence rules.
Появление `boolean`, `enum`, `date`, `identifier` или `status` само по себе не
создаёт новый action type.

**Internal operation** — реализационный механизм owner-а. Factory call, lookup,
hashing, persistence, adapter или schema validation не становятся public
capability, если LLM не должна выбирать их для выражения business intent.

Эти определения выдерживают текущий код: G5.8 исполняет опубликованную
methodology, G5.13 содержит concrete behavior/adapter, G5.14 владеет exact-scope
admission, а G5.12 отделяет projection engine от projection spec.

## Gap Classification Matrix

Обозначения: `A` — new primitive; `B` — existing primitive + behavior; `C` —
different parameters/contract; `D` — value kind; `E` — artifact; `F` —
authoring-time; `G` — not a capability.

| Requirement / Gap | Current capability | Primitive gap? | Behavior gap? | Artifact gap? | Value-kind gap? | Authoring-time? | Verdict |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| operation Tax Model production | `execute_published_calculation_behavior_v0` related; internal G5.13 producer exists | no | no: `2026.1` behavior exists | no | no | no | `C`: versioned typed-output generalization of execute; do not add `build_tax_model` |
| group-level tax base | current execute is related but too narrow | no | yes | yes: methodology/behavior publication | no | authoring publishes it | `B+C+E`: after typed execute, add reviewed behavior/artifact only |
| residency acquisition | resolve + human acquisition families | no | no | possible input schema/evidence policy | yes: status/enum | artifact design at authoring time | `D`: do not add `obtain_residency` |
| IIS status | resolve + human acquisition families | no | no | possible input schema/evidence policy | yes: boolean/status/enum | artifact design at authoring time | `D`: one closed typed-fact family, not declaration command |
| loss treatment | resolve/acquire input, then execute behavior | no | likely yes for tax treatment | methodology may be needed | yes for fact/status | behavior publication is authoring-time | `B+D+E`: separate user fact from derived tax treatment |
| missing acquisition cost | `resolve_required_values_v0` + `obtain_one_missing_money_input_v0` | no | no | no | no: money already proven | no | current basis expresses the case |
| tax period input | resolve/acquisition families | no | no | input schema/evidence policy | yes: year/date | schema publication is authoring-time | `D`: no `obtain_tax_period` primitive |
| operation classification and expense allowability | typed execute family; G5.13 internal behavior | no | yes per tax rule/version | yes when newly published | no | publication/review is authoring-time | `B+E`: domain semantics stays outside primitive |
| external authoritative rate lookup | none public; bounded G5.11 acceptance seam | not yet proven | possibly consumer behavior | yes: reference snapshot | no | yes for research/publication | `F+E`: authoring research -> reviewed snapshot; no `research_any_fact` |
| case-time authoritative external fact acquisition | no public capability | evidence insufficient to decide | no | source policy/snapshot may be needed | source-specific | no | no addition now; prove recurring live case need and trust boundary first |
| category aggregation | `aggregate_complete_category_scope_v0` | no | no | existing operation methodology/projection required | no | no | current atomic capability is proven |
| completeness admission | inside `aggregate_complete_category_scope_v0` | no | no | evidence instance, not new artifact type | no | no | `G`: safety precondition/output admission; do not publish separate verifier yet |
| declaration projection | `project_validated_declaration_fragment_v0` | no | no | yes per form/version | no | projection authoring/review is authoring-time | current capability + new projection artifact |
| new XML/form version | projection capability | no | no | yes: projection/evidence pack | maybe new stable enum/code | yes for authoring | `E+F`: never `project_3ndfl_2026` |
| member sorting, SHA-256 and binding comparison | aggregation owner | no | no | no | no | no | `G`: internal safety mechanics |

Матрица не содержит подтверждённого `A`. У operation-model gap есть реальный
public-surface defect, но stable action уже совпадает с «исполнить exact
published behavior». Добавление `build_tax_model` повторило бы shape одного
Tax Model и сделало basis декларационно-зависимым.

## Обязательные gap verdicts

### 1. Operation Tax Model

Рассмотренные варианты:

- новый `build_tax_model` отклонён: model shape и tax semantics меняются с
  methodology, а G5.13 уже выполняется deterministic reviewed code;
- отдельный `classify_or_transform` отклонён: у него нет отличимой runtime
  admission/execution semantics по сравнению с исполнением published behavior;
- публикация internal `run_operation` отклонена: это owner-specific entrypoint,
  а не stable LLM language;
- выбран `C`: versioned generalization существующего execute primitive.

Минимальный `v1` не должен быть generic plugin runner. Допустимы только заранее
зарегистрированные пары:

```text
(behavior_id, behavior_version, input_contract_id, output_contract_id,
 implementation_binding, artifact_hashes)
```

Runtime валидирует exact pair, source/provenance, typed input и typed output.
Unknown contract, arbitrary schema, dynamic code и free-form case-time reasoning
fail closed.

### 2. Group-level tax base

Действие остаётся тем же: применить reviewed deterministic tax behavior к
complete, validated group inputs. Меняются formula, methodology artifact,
input/output schema и behavior binding. Поэтому это `B+E`, а не new primitive.
Current `v0` добавляет `C`, потому что умеет возвращать только старый money
calculation result. Typed execute `v1` снимает именно эту механическую помеху.

### 3. Human input

Разные value kinds не оправдывают набор `obtain_money`, `obtain_boolean`,
`obtain_enum`, ... . Устойчивое действие одно: запросить ровно один current
missing fact, принять bounded evidence, детерминированно проверить, записать в
trusted case scope и повторно разрешить requirement.

Однако только money path доказан G5.6/G5.15. Поэтому:

- current public capability остаётся `obtain_one_missing_money_input_v0`;
- target family может получить versioned semantic name
  `obtain_one_missing_typed_user_fact_v1` только после отдельного proof;
- каждый supported kind должен иметь closed schema, parser/validator, evidence
  policy и matching rule;
- derived decision или disputed legal classification нельзя маскировать под
  «human fact»;
- generic interview engine, multi-question workflow и free-form fallback не
  входят в basis.

То же value-kind proof должно расширять `resolve_required_values`, иначе acquired
typed fact не сможет войти в общий resolution contract.

### 4. External research

G5.11 доказал один bounded reference-data route и deterministic acceptance над
конкретным evidence, но не доказал generic live research, source selection,
publication, freshness lifecycle или persistence как case-time capability.

Граница должна остаться двухплоскостной:

```text
AUTHORING: research -> cite -> review -> publish immutable reference snapshot
CASE TIME: resolve published snapshot -> execute reviewed behavior
```

Если когда-нибудь появится реальная recurring потребность получать
case-specific external fact во время расчёта, ей нужен отдельный goal с exact
source authority, identity, freshness, consent, caching и fail-closed proof.
Она не следует автоматически из G5.11.

### 5. Scope, completeness и aggregation

G5.14 показывает concrete safe composition: aggregate принимает exact scope,
exact member models и optional user-verified assertion, связанную с canonical
scope/member hashes. Без exact binding runtime может вернуть known totals, но не
complete Category Tax Model и не projection.

Разделение на `verify_scope -> aggregate` сейчас ухудшило бы boundary:

- caller мог бы попытаться переиспользовать admission после смены member set;
- потребовался бы новый durable token contract и новый stale-token protocol;
- ни один G5.10–G5.16 scenario не использует verified scope отдельно от exact
  aggregate result;
- отдельная public capability увеличила бы orchestration без новой выразимости.

Поэтому completeness остаётся атомарной admission semantics aggregation.
Смысл family — `aggregate_complete_scope`; current category-specific `v0`
следует сохранять до второго concrete scope proof, а не обобщать по воображению.

## Primitive basis test

| Candidate action family | Вне 3-НДФЛ | При смене закона | Deterministic без LLM | Stable I/O | Убирает hardcode | Result |
| --- | --- | --- | --- | --- | --- | --- |
| resolve closed requirements | да | primitive не меняется; schemas/kinds могут versionироваться | да | да, closed requirements -> satisfied/missing | да, один owner для source precedence | `KEEP` |
| obtain one missing typed fact | да | primitive не меняется; evidence policy может versionироваться | да только для closed kind validators | да после kind-specific proof | да, не плодит type-named commands | `GENERALIZE_LATER`, current money proof retained |
| execute published typed behavior | да | меняются behavior/methodology artifacts | да при closed registry | да: typed envelope + registered contracts | да, tax functions не становятся capabilities | `GENERALIZE_FIRST` |
| aggregate exact complete scope | да как mechanic, но current category shape доказан только один раз | aggregation admission не меняется; scope schema/behavior могут versionироваться | да | да для exact scope/member binding | да, completeness не размазывается по orchestrator | `KEEP_CURRENT`, generalize only after second proof |
| project validated fragment | да | меняется projection artifact | да | да, complete semantics -> validated fragment | да, form/version не входит в capability ID | `KEEP` |

Каждая family имеет устойчивый deterministic action. Ни одна новая
scenario-specific команда этот тест не проходит лучше существующей composition.

## Candidate Runtime Basis

### 1. `resolve_required_values_v0` — KEEP

- **Meaning:** разрешить каждый closed semantic requirement сначала из current
  Financial Case, затем из eligible same-run user facts, не смешивая sources.
- **Inputs:** closed requirements; trusted case context.
- **Preconditions:** current Financial Case; complete access context; closed
  non-empty requirements; same-run supplemental scope.
- **Output:** satisfied/missing result; у satisfied ровно один tagged source.
- **Failure boundary:** stale case, invalid/foreign fact, ambiguous match,
  unsupported value kind.
- **Почему primitive:** source precedence и missing admission нужны независимо от
  декларации и formula.
- **Почему не behavior/artifact:** он не определяет tax meaning; schemas и kinds
  являются versioned content контракта.
- **Examples:** gross proceeds; acquisition cost; позже — residency/status после
  отдельного kind proof.

### 2. `obtain_one_missing_money_input_v0` — KEEP NOW; GENERALIZE LATER

Proposed family name: `obtain_one_missing_typed_user_fact_v1`.

- **Meaning:** получить ровно один missing fact поддерживаемого closed kind,
  проверить against bounded human evidence, сохранить и recheck.
- **Inputs:** one missing requirement; trusted case context; optional bounded
  human answer; kind contract.
- **Preconditions:** exactly one missing requirement; kind has registered
  deterministic validator; trusted persistence and recheck path.
- **Output:** structured question либо accepted persisted typed fact + recheck.
- **Failure boundary:** zero/multiple missing, unsupported kind, ambiguity,
  proposal/evidence mismatch, persistence/recheck failure.
- **Почему primitive:** evidence acquisition — отдельное действие с human trust
  boundary, одинаковое для разных деклараций.
- **Почему не behavior/artifact:** tax interpretation не выполняется; конкретный
  kind schema/validator является contract extension.
- **Examples:** current acquisition cost; future residency enum, IIS status or
  tax period only after their exact schemas/evidence policies are proven.

### 3. `execute_published_typed_behavior_v1` — GENERALIZE FIRST

Replaces, but does not silently mutate,
`execute_published_calculation_behavior_v0`.

- **Meaning:** разрешить exact published behavior и исполнить его registered
  deterministic implementation над validated source-tagged typed input.
- **Inputs:** published behavior reference; validated typed semantic input or
  trusted case context adapter declared by the registered binding.
- **Preconditions:** identity/version/hash pinned; input/output contract pair is
  in a closed registry; implementation reviewed; required values satisfied;
  behavior-specific invariants hold.
- **Output:** typed result envelope containing behavior/artifact identity,
  `output_contract_id`, validated payload and retained provenance.
- **Failure boundary:** unknown behavior/contract pair, hash drift, input/output
  mismatch, missing/ambiguous value, implementation/schema validation failure.
- **Почему primitive:** deterministic application of reviewed rules is stable
  across declarations and laws.
- **Почему не behavior/artifact:** formulas, classifications, rates and result
  schemas live in the published binding/artifacts, not in capability meaning.
- **Examples:** old securities net result; G5.13 operation Tax Model; future
  group-level tax base after its behavior is separately published.

### 4. `aggregate_complete_category_scope_v0` — KEEP

Semantic family: `aggregate_complete_scope`; no rename/generalization yet.

- **Meaning:** aggregate compatible complete member models for exact scope and
  admit complete result only against exact scope/member completeness binding.
- **Inputs:** scope; typed member set; optional completeness evidence.
- **Preconditions:** compatible complete members; published bindings; exact
  identity/period/category/currency/loss agreement; exact completeness hash for
  complete output.
- **Output:** deterministic known aggregates; complete model/projection only
  when exact admission succeeds.
- **Failure boundary:** duplicate/invalid member, stale methodology, scope or
  currency mismatch, stale/invalid completeness binding.
- **Почему primitive:** aggregation plus exact completeness admission is a stable
  safety action not owned by one tax formula.
- **Почему не behavior/artifact:** concrete member semantics and projection are
  published content; member sorting/hash comparison are internal mechanisms.
- **Examples:** G5.14 Appendix 8 category; a future second scope must prove any
  broader contract before the public ID changes.

### 5. `project_validated_declaration_fragment_v0` — KEEP

- **Meaning:** project complete stable semantics through exact validated
  repository-pinned projection.
- **Inputs:** complete declaration semantics matching the projection contract.
- **Preconditions:** valid projection spec/evidence hash; all concepts present;
  value kinds compatible.
- **Output:** deterministic declaration-shaped fragment with mapping provenance.
- **Failure boundary:** invalid spec/evidence, unknown/missing concept,
  unsupported target/code, incomplete input.
- **Почему primitive:** mapping stable semantics into a declared representation
  is reusable across form versions and declarations.
- **Почему не behavior/artifact:** field paths, codes and XML version belong to
  Projection Spec/evidence pack.
- **Examples:** Appendix 8 five concepts; another form/version via another
  validated projection artifact.

## Expressiveness test

### Scenario 1 — Appendix 8

```text
resolve_required_values
-> execute_published_typed_behavior
   [securities_disposal_operation_tax_model]
-> aggregate_complete_category_scope
-> project_validated_declaration_fragment
```

Current G5.15 fails only at the second arrow's output contract. G5.13 behavior
and G5.14 consumer already exist. The proposed typed execute generalization makes
the contracts composable without `build_3ndfl_appendix8`.

### Scenario 2 — missing acquisition cost

```text
resolve_required_values
-> missing money
-> obtain_one_missing_money_input
-> resolve_required_values
-> continue
```

Current basis already expresses this scenario. No general interview primitive or
new value kind is required.

### Scenario 3 — authoritative rate/reference fact

```text
authoring research
-> bounded official evidence
-> human review/publication
-> immutable reference snapshot

case-time execute_published_typed_behavior
-> resolves exact snapshot through trusted artifact owner
```

Research is not a case-time step. A changed rate creates a new snapshot and
usually a new methodology/behavior version, not a capability.

### Scenario 4 — future group-level tax base

```text
complete validated group inputs
-> execute_published_typed_behavior
   [future reviewed group_tax_base behavior]
-> typed group tax-base result
-> later projection/next reviewed behavior
```

The missing item is behavior/artifact. A command named
`calculate_3ndfl_group02` would only relocate declaration hardcode.

### Scenario 5 — residency / IIS / loss facts

```text
resolve_required_values
-> missing supported typed fact
-> obtain_one_missing_typed_user_fact
-> resolve_required_values
-> execute reviewed tax behavior
```

This is a valid future composition, not a current conformance claim. Until exact
kind validators, evidence policy and owner routing are proven, the current
contract must report `unsupported_value_kind` rather than improvise.

No scenario requires a workflow DSL. Arrows describe I/O compatibility only;
loops, branches, variables and expression trees are outside G5.17.

## Authoring plane vs case-time runtime

Verdict: capability surfaces **must remain distinct**.

| Authoring plane | Case-time runtime |
| --- | --- |
| interpret declaration requirements | resolve closed case requirements |
| research and cite official evidence | acquire only supported bounded case facts |
| propose methodology/behavior/reference/projection artifacts | resolve exact reviewed artifacts |
| compare versions and expose gaps | execute deterministic registered behavior |
| run static compatibility validation | aggregate exact complete scope |
| send candidate to human review/publication | project validated semantics |

G5.16 authoring context may name available case-time capabilities, but the LLM's
research/synthesis actions are not evidence that runtime should publish them.
Один combined contract смешал бы proposal authority с execution authority.

## DO NOT PUBLISH

Следующие полезные mechanisms должны оставаться за owner boundaries:

- raw Gate 4/Financial Case querying и storage access;
- `ArtifactStore` reads/writes и supplemental-fact persistence calls;
- G5.2 `financial_type` selection;
- G5.3 raw supplemental store/read/ref operations;
- G5.4 combined checker internals;
- G5.13 `run_operation`, private adapters и конкретные `Factory.create` calls;
- G5.14 `describe_scope`, member sorting, canonical serialization, SHA-256 и
  completeness-binding comparison;
- G5.12 projection candidate validation, evidence-pack loader и mapping lookup;
- methodology/reference resource loading and hash verification;
- Declaration Definition candidate validator internals;
- web search, citation collection and arbitrary external research;
- LLM chain-of-thought, free-form formulas, dynamic Python/code and workflow DSL.

Эти operations необходимы implementation, но их публикация не даёт LLM нового
business meaning и увеличивает возможность bypass trusted factories.

## Architecture Pressure Test

| Изменение | Что меняется | Что не меняется |
| --- | --- | --- |
| другая структурированная налоговая декларация | requirements, schemas, behaviors, reference data, scope/member contracts и projections; broader scope generalization только после proof | пять action families |
| ФНС меняет формулу | methodology/behavior version, reference snapshot и tests | execute primitive |
| ФНС меняет classification/allowability rule | reviewed behavior/artifact and possibly typed result schema | execute primitive |
| ФНС меняет XML/field path/code | Projection Spec, evidence pack и возможно output schema version | projection primitive |
| появляется новый human input type | closed value-kind schema, deterministic validator, evidence/matching policy; versioned support in resolve/acquire | acquisition action family; новая capability не нужна автоматически |
| появляется новый authoritative reference | authoring research evidence, reviewed immutable snapshot, freshness/version and consuming methodology | case-time primitive set |
| появляется новая operation Tax Model shape | registered typed behavior/result pair and consumer compatibility proof | execute action family |
| нужен отдельный reusable completeness decision | сначала concrete second consumer, durable exact token and stale-binding proof | до такого evidence atomic aggregate остаётся unchanged |

Pressure test отделяет stable mechanics от changing domain content. Единственная
немедленная contract problem — current calculation-only output boundary.

## Candidate-basis decision table

| Decision | Capability / mechanism | Reason |
| --- | --- | --- |
| `CURRENT` | пять G5.15 capabilities | exact proven inactive runtime surface |
| `KEEP` | `resolve_required_values_v0` | stable source-resolution primitive |
| `KEEP` | `project_validated_declaration_fragment_v0` | declaration/version specificity уже вынесена в artifact |
| `KEEP` | `aggregate_complete_category_scope_v0` | current atomic safety boundary доказан; split не нужен |
| `GENERALIZE_FIRST` | `execute_published_calculation_behavior_v0` -> `execute_published_typed_behavior_v1` | exact G5.16 operation-member incompatibility; no new action type |
| `GENERALIZE_LATER` | money acquisition/resolve family -> closed typed facts | real known requirements, но non-money case-time path ещё не proven |
| `SPLIT` | none | ни один observed scenario не получает выразимость или safety от split |
| `ADD` | none | все known gaps классифицируются `B`–`G`, не `A` |
| `DO NOT PUBLISH` | research, tax-specific functions, factories, stores, hashes, validators | authoring/internal mechanisms, не stable runtime meaning |

Target basis остаётся маленьким: пять primitive families. Versioned contract
generalization не считается шестым primitive и не даёт arbitrary behavior
execution.

## First capability change to prove

Отдельный implementation goal должен доказать только:

```text
execute_published_typed_behavior_v1
```

Минимальный acceptance boundary:

1. не менять существующий `v0` in place;
2. closed registry допускает exact input/output contract pairs, а не arbitrary
   schemas или code;
3. старый `security_disposal_net_result_v0` проходит parity через `v1`;
4. существующий
   `securities_disposal_operation_tax_model_v0@2026.1-experimental` возвращает
   exact operation-member contract, который принимает G5.14;
5. unknown behavior, wrong output contract, hash drift, malformed typed payload
   и missing provenance fail closed;
6. `execute -> aggregate` compatibility проверяется static contract test и
   real deterministic runtime test;
7. никакой group-tax-base formula, new human value kind, research capability,
   DSL или product activation в этот slice не входит.

После закрытия этого proof отдельный clean-context G5.16-style trial должен
получить обновлённый proven capability contract и тот же declaration authoring
problem. Он обязан независимо найти group-tax-base `missing_published_behavior`
и не получить подсказку о желаемых gaps. До такого causal isolation нельзя
утверждать, что именно LLM независимо вывела Definition.

## KISS check и stop

- primitive count: `5 -> 5`;
- first proposed change: one versioned contract generalization;
- new public primitive: none;
- split capability: none;
- workflow DSL/runner/plugin system: none;
- G5.15 runtime/contract changes: none;
- blind-authoring rerun: none;
- next implementation slice: not started.

G5.17 закрывает только capability-basis research. Следующий допустимый boundary:
отдельный goal на typed execute conformance proof; затем отдельный clean-context
authoring trial.
