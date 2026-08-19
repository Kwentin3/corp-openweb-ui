# Broker Reports Gate 5 Minimal Complete Declaration Model Research — G5.26

Date: 2026-08-10

Status: `G5.26_CLOSED`

Outcome: `TYPED_COMPONENT_PACKAGE_WITH_DEFINITION_BOUND_COMPLETENESS`

First blocker: `COMPLETE_DECLARATION_SCOPE_RESOLUTION_MISSING`

Product status: `INACTIVE RESEARCH`

Implementation status: `NOT_STARTED`

## Verdict

Минимальный complete Declaration Model — не большой form-specific DTO и не
generic concept bag. Это один versioned, target-independent resolved package:

```text
exact trusted Declaration Definition binding
+ exact declaration case scope
+ closed typed semantic component snapshots
+ requirement-resolution manifest
+ hash-bound completeness receipt
```

Его непосредственный runtime input перед final PROJECT должен быть замкнутым:
PROJECT получает все resolved component snapshots внутри package и не читает
Financial Case, ArtifactStore, Tax Models или методологии повторно. При этом
Declaration Model не расплющивает и не копирует значения Tax Models в новый
набор полей: он композиционно включает их immutable typed snapshots и связывает
их contract/content hashes с requirement IDs.

```text
typed Tax Models ───────────────┐
taxpayer identity ──────────────┤
declaration/filing context ─────┤
signer context ─────────────────┤
typed settlement semantics ─────┤
applicability decisions ─────────┤
                                 ↓
                      RESOLVED DECLARATION PACKAGE
                      + completeness receipt
                                 ↓
                  one exact Projection Definition
                                 ↓
                              PROJECT
```

`DECLARATION_COMPLETE` означает: для exact trusted Definition, taxpayer/case
scope, tax period и declaration instance каждый её semantic requirement имеет
ровно одно terminal resolution — validated `RESOLVED` либо evidence-bound
`NOT_APPLICABLE`; нет `UNRESOLVED`, `REQUIRED_MISSING`, conflict, stale binding
или unaccounted component.

Это completeness конкретной декларации относительно exact Definition и
доказанного scope. Это не абстрактное утверждение о полноте всей налоговой
истории налогоплательщика и не гарантия будущего принятия ФНС.

## Competing hypotheses

| Hypothesis | Support | Counter-evidence / discriminating test | Verdict |
| --- | --- | --- | --- |
| H1: один `ThreeNdfl2025DeclarationModel` с полем на каждый form/XSD field | высокая локальная type safety; простой serializer | смена XML layout меняет semantic runtime; `НалБаза`, XML order и field codes проникают upstream; PDF требует другой shape | `FALSIFIED`: это копия target schema |
| H2: typed semantic components + declaration manifest/receipt | current Gate 5 уже выдаёт typed operation/category/income-group models с provenance; компоненты можно валидировать отдельно; Definition задаёт exact coverage | требовалось доказать, что optional/zero/stale states валидируются без generic rules engine; disposable state-algebra test это подтвердил | `SURVIVES` |
| H3: `concept_id -> Any`, целиком governed Definition | легко расширять и удобно LLM-authoring | identity alternatives, money, collections, settlement invariants и provenance потребуют вложенных schemas, magic paths и dynamic validation; получится второй schema language | `FALSIFIED AS PRIMARY MODEL`; stable IDs допустимы только в manifest над typed contracts |
| H4: generic graph/ontology/rules engine | способен выражать provenance и произвольные связи | нет evidence, что declaration composition требует graph traversal; усложняет execution authority и переносит calculation/applicability в DSL | `FALSIFIED` |
| H5: package содержит только refs на Tax Models | нет дублирования persisted bytes | final PROJECT вынужден читать store, выбирать версии и заново решать ACL/availability; boundary не замкнута | `FALSIFIED AS DIRECT INPUT`; normalized storage refs допустимы до sealing, но PROJECT получает resolved snapshots |

### Design pressure matrix

| Property | H1 giant DTO | H2 typed package | H3 generic bag | H4 graph |
| --- | --- | --- | --- | --- |
| type safety | high | high at component boundaries | low/dynamic | dynamic |
| form-layout coupling | high | low | low | low |
| deterministic completeness | possible but hardcoded | direct manifest validation | requires schema/rule interpreter | requires graph/rule interpreter |
| provenance preservation | copied or bespoke | component hash binding | ad hoc per value | expressive but excessive |
| LLM authoring compatibility | low | high for semantic requirement manifest | superficially high | low |
| projection independence | low | high | medium | high |
| complexity | high per form | lowest sufficient | hidden in generic validator | highest |

H2 is the only design that keeps both a closed type system and a
Definition-driven declaration inventory without introducing a new language.

## Official requirement audit, used backwards

Проверены exact official bytes, ранее зафиксированные в G5.25 с
[страницы приказа ФНС](https://www.nalog.gov.ru/rn77/about_fts/docs/16589324/):

```text
procedure DOCX  7bc11cad8d0465c03c834c50c7832fb2edc7291d9b4b161ef5b2c6cabdcb0fdc
format DOCX     f5215c237a8af73dd7a251cee94a2e09aacd8540173fcde2904b4c311129e3c2
XSD 5.20.01     083128322833dbafb29be0bf919e33b7b362956244b422d34dd554c99a1e4484
```

[Official XSD 5.20.01](https://www.nalog.gov.ru/html/sites/www.new.nalog.ru/files/about_fts/docs/xsd/NO_NDFL3_1_033_00_05_20_01.xsd)
требует один full document с taxpayer, signer и declaration body. В body
обязательны document-level tax disposition и один или более income-group tax
calculations; каждая такая группа содержит и tax base calculation, и tax
payment/refund calculation. Многочисленные income, deduction, property,
business, foreign-income и refund branches условны.

XSD использован как backward discovery evidence: наличие target field
заставляет найти upstream meaning и authority. Его tag names, hierarchy и
order не превращались в Declaration Model fields.

Ключевые границы:

| Official target observation | Stable pre-projection meaning | Boundary result |
| --- | --- | --- |
| `СвНП` required | resolved taxpayer filing identity | Declaration Model component |
| `Подписант` required, representative conditional | signer role, identity and authority | Declaration Model component |
| document date, period, authority, correction | declaration instance and filing context | Declaration Model component |
| `НалБаза/РасчНалБаза` | typed income-group tax-base semantics | Tax Model component |
| `НалБаза/РасчНалПУ` | calculated, withheld, credited, payable/refundable tax semantics for the group | missing Tax/settlement component |
| `СумНалПу` | declaration-level settlement/disposition by applicable budget/territory identity | missing declaration settlement component |
| optional target branch | evidence-backed applicability decision plus optional typed component | manifest state, never omission inference |
| `ЗаявРаспДС` and bank account | refund request/destination only when applicable | conditional filing/payment component |
| XML element/attribute names and order | none | Projection Definition only |

`НалБаза`, `СумДох`, `РасчНалПУ` и `СумНалПу` — target names. Их meanings
разделяются: income totals/tax base, tax calculation/withholding/credits и
document-level payable/refund disposition являются semantic concepts; сами
имена containers/attributes — нет.

Аналогично, stable income-group meaning принадлежит Tax Model/Definition, а
form code вроде `02` является mapping exact Projection Definition, если только
его code system не объявлен отдельным authoritative semantic identifier.
Значения КБК/ОКТМО могут быть settlement identifiers; их XML attribute names,
formatting и placement остаются projection-only.

## Minimal declaration semantic inventory

| Requirement | Stable semantic concept | Owner / source class | Current availability | Missing dependency | Projection-only? |
| --- | --- | --- | --- | --- | --- |
| exact declaration contract | Definition id/version/hash and semantic requirement set | published Declaration Definition authority | bounded inactive candidates exist | complete trusted full-declaration Definition absent | no |
| declaration instance | taxpayer scope, case binding, tax period, declaration instance identity | user/case facts + Definition | tax period and bounded scope refs exist | one full-declaration scope binding absent | no |
| filing metadata | correction context, filing destination, declaration date/type | `declaration_filing_context` semantic owner; acquired through existing case/user infrastructure | not found as a Gate 5 owner | typed acquisition/resolution absent | no |
| taxpayer identity | FIO plus authoritative taxpayer identifier/identity alternative | authenticated source/user facts, resolved by identity owner | FNS 2-NDFL adapter has recipient identity candidates; access context has only app user/case IDs | declaration taxpayer identity resolution and authority binding absent | no |
| taxpayer tax status | residency/status applicable to exact period | user/case fact, validated against methodology requirements | bounded user-verified status exists for current income-group proof | declaration-wide consistency binding absent | no |
| signer/representative | signer role, identity, representative authority when applicable | `declaration_filing_context`, user/case/source evidence | absent | typed signer resolution absent | no |
| domain applicability | whether each stable declaration domain applies | Definition expectation + case/domain evidence | only bounded securities/group applicability exists | full domain resolution set absent | no |
| securities operation/category semantics | operation facts, complete category aggregates, loss treatment | typed Gate 5 Tax Models + trusted methodology | available for exact bounded category with exact member-hash completeness | no gap inside that bounded category | no |
| income-group tax base | income, non-taxable amount, deductions, accepted expenses, tax base | typed income-group Tax Model | available for current bounded group 02 proof | no other groups or declaration-wide applicability proof | no |
| group tax settlement | rate-basis result, calculated/withheld/credit amounts, payable/refundable result | trusted methodology-derived Tax Model / settlement owner | a reference rate fact exists but explicitly derives no tax conclusion | reviewed typed tax settlement behavior absent | no |
| document tax disposition | payable/refundable allocation and stable budget/territory identities | declaration settlement composition over complete group settlements + filing facts | absent | typed document-level settlement semantics absent | no |
| other income/deduction domains | foreign/business/property/deduction and other applicable typed results | their respective Tax Model owners | not established in current bounded scenario | applicability and, when applicable, typed models absent | no |
| refund destination | refund request, bank destination and amount | user/case filing/payment facts | absent | needed only after evidence-backed applicability | no |
| requirement accounting | resolution state for every Definition requirement | Declaration Model assembler/validator | absent | exact requirement-resolution manifest absent | no |
| provenance/completeness | component authorities, hashes, case/period binding and overall receipt | each component owner + Declaration Model validator | component-local provenance exists | declaration-wide sealed receipt absent | no |
| XML/PDF layout | tags, paths, order, namespace, encoding, file name, PDF coordinates | exact Projection Definition + target adapter | bounded projection evidence exists | full-target package absent, but not a Declaration Model gap | yes |

### What current repository truth proves

- `ArtifactAccessContext` contains application user, normalization, case, chat,
  workspace and source-file access coordinates. Они достаточны для ACL/case
  routing, но не являются taxpayer identity или signer authority.
- Source-level FNS 2-NDFL adaptation extracts `tax_agent_identity`,
  `recipient_identity` and `report_period`. Это candidate identity evidence,
  а не resolved declaration taxpayer identity.
- Operation Tax Model owns subject, period, residency, exemption, category,
  gross income, expenses, loss treatment, methodology and provenance; it does
  not own rate or tax payable.
- Category completeness is explicitly limited to
  `all_operations_in_taxpayer_category_period_scope` and exact sorted member
  hashes.
- Income-group completeness is limited to
  `all_income_and_reductions_in_stable_income_group`; the model produces income,
  accepted expenses and tax base, not calculated tax.
- Current external rate evidence has `derived_tax_conclusion = false`; it cannot
  be promoted directly to a settlement result.
- Current Declaration Definition artifacts are inactive/bounded authoring
  evidence. They do not publish a complete 3-NDFL semantic requirement and
  applicability authority.

Поэтому current category/group `complete` statuses должны сохраняться внутри
компонентов, но не могут поднимать весь package до `DECLARATION_COMPLETE`.

## Ownership and provenance matrix

| Concept class | Semantic owner | Evidence/authority | Declaration Model binding | New infrastructure? |
| --- | --- | --- | --- | --- |
| source financial facts | existing source/canonical owners | authenticated source refs | retained inside Tax Model snapshot/hash | no |
| external/reference facts | existing external-evidence authority | source URL/hash/effective period | retained by consuming typed component | no |
| user/case facts | existing authenticated case/user flow | user-verified fact + case binding | exact fact/component hash | no |
| methodology-derived tax facts | typed Tax Model factory + trusted methodology | methodology id/version/hash + input refs | immutable Tax Model snapshot/hash | no |
| declaration/filing context | one new semantic component owner | case/user/source evidence plus filing validation | typed context snapshot/hash | no new DB/service; reuse auth, ACL, ArtifactStore and case context |
| requirement applicability | Declaration Definition expectation + typed case-time decision owner | exact evidence refs and decision contract | per-requirement state/evidence hash | no rules engine |
| definition requirements | published Declaration Definition authority | exact definition bytes/hash | top-level definition binding | no registry service required |
| target structure | Projection Definition and target validator | official target package hashes | not part of Declaration Model | no change to five primitives |

Отдельный semantic owner `declaration_filing_context` доказан полезным:
correction number, filing authority, declaration date/type и signer role имеют
declaration lifecycle/integrity rules и не являются financial, external или
methodology-derived tax facts. Это не требует нового raw provenance channel:
их acquisition provenance остаётся existing user/case/source evidence.

## Completeness contract

### Requirement states

| State | Meaning | Terminal for completeness? |
| --- | --- | --- |
| `RESOLVED` | requirement applicable; exact typed validated component/value bound with required provenance | yes |
| `NOT_APPLICABLE` | requirement conditionally allowed to be absent and exact case evidence proves non-applicability | yes |
| `UNRESOLVED` | applicability or required meaning cannot yet be determined | no |
| `REQUIRED_MISSING` | applicability is true, but required typed value/component is absent | no |
| `CONFLICT` | two authorities/components disagree or bind to incompatible scopes | no |

`optional` не является runtime state. Definition может объявить requirement как
`always_applicable` или `case_decision_required`; concrete model всё равно
содержит resolution row. Молчаливое отсутствие row означает `UNRESOLVED`, а не
`NOT_APPLICABLE`.

### Overall rule

`DECLARATION_COMPLETE` iff:

1. Definition binding resolves to exact trusted published bytes/hash.
2. Scope binds one taxpayer/case, tax period and declaration instance.
3. Every Definition requirement occurs exactly once in the resolution manifest.
4. Every row is `RESOLVED` or evidence-bound `NOT_APPLICABLE`.
5. `RESOLVED` rows bind a closed allowed typed contract and validated immutable
   component content hash.
6. `NOT_APPLICABLE` is allowed for that requirement and binds exact
   applicability evidence/decision authority.
7. All component scopes, periods, currencies/identities and authority hashes
   are compatible; no stale, conflict, orphan or unaccounted component exists.
8. Definition, scope, component-set and resolution-manifest hashes match the
   completeness receipt.

Otherwise status is `DECLARATION_INCOMPLETE` and final PROJECT must return no
publishable target representation.

`0` is an ordinary resolved numeric value with type, authority and provenance.
It is neither absence nor non-applicability. Serializer-required placeholder
zero without semantic authority must be rejected as `REQUIRED_MISSING` or
`UNRESOLVED` upstream.

### Non-authoritative machine-contract sketch

```json
{
  "schema_version": "resolved_declaration_package_v0_research",
  "definition_binding": {
    "definition_id": "stable-id",
    "definition_version": "exact-version",
    "definition_sha256": "sha256"
  },
  "scope": {
    "case_ref": "opaque-ref",
    "taxpayer_scope_ref": "opaque-ref",
    "tax_period": "YYYY",
    "declaration_instance_ref": "opaque-ref"
  },
  "components": [
    {
      "component_ref": "local-stable-ref",
      "contract_id": "closed-typed-contract",
      "contract_version": "exact-version",
      "owner_class": "tax_model|filing_context|identity|settlement",
      "content_sha256": "sha256",
      "snapshot": "<validated typed value with its native provenance>"
    }
  ],
  "requirement_resolutions": [
    {
      "requirement_id": "definition-owned-stable-id",
      "state": "resolved|not_applicable|unresolved|required_missing|conflict",
      "component_ref": "local-stable-ref|null",
      "applicability_evidence_refs": [],
      "resolution_sha256": "sha256"
    }
  ],
  "completeness_receipt": {
    "status": "declaration_complete|declaration_incomplete",
    "definition_sha256": "sha256",
    "scope_sha256": "sha256",
    "component_set_sha256": "sha256",
    "resolution_manifest_sha256": "sha256"
  }
}
```

Это shape для проверки boundary, не production schema. `snapshot` — typed
contract payload, не `Any` in runtime. Persisted storage может дедуплицировать
его через content-addressed ref, но sealed PROJECT input должен уже содержать
resolved bytes/value и не выполнять store reads.

### Declaration Definition boundary

Definition должна владеть:

- stable semantic requirement IDs;
- expected typed contract id/version для `RESOLVED`;
- applicability mode: always или exact case decision required;
- допустимыми authority/provenance classes и completeness expectation;
- Definition version/hash and compatibility policy.

Definition не должна содержать formulas, Python, XPath, XML order, loops,
workflow graph, source search или arbitrary condition expressions. Она может
потребовать typed applicability decision, но это decision produces separate
evidence-bound result через reviewed owner; Definition не становится executable
rules DSL.

## Disposable falsification experiment

Вне repository выполнен in-memory validator для восьми synthetic requirements.
Он проверял только state algebra и hash bindings; customer values, tax
calculation и production files не использовались.

| Case | Result | Discriminated claim |
| --- | --- | --- |
| только current bounded tax-base + securities components | `DECLARATION_INCOMPLETE`; filing, taxpayer, signer, settlement, summary and other-domain applicability unresolved | category/group completeness cannot become declaration completeness |
| conditional requirement simply omitted | `DECLARATION_INCOMPLETE: unresolved` | optional omission is unsafe |
| same requirement explicitly `NOT_APPLICABLE` with evidence hash | synthetic `DECLARATION_COMPLETE` | legitimate absence can be terminal without a value |
| settlement value explicitly resolved as numeric zero | synthetic `DECLARATION_COMPLETE` | zero and absence are distinct |
| `NOT_APPLICABLE` without evidence | `DECLARATION_INCOMPLETE: unsupported_absence` | serializer/caller cannot silently suppress a section |
| all resolutions terminal but Definition hash stale | `DECLARATION_INCOMPLETE: definition_hash_mismatch` | completeness is version-bound |

Synthetic `COMPLETE` outcomes доказывают только непротиворечивость minimal
state contract. Они не являются налоговой декларацией и не доказывают, что
какое-либо real requirement не применимо.

## Surviving Declaration Model boundary

### Included

- exact Definition and exact case/tax-period/declaration-instance binding;
- resolved taxpayer and signer semantic components;
- declaration/filing context;
- immutable validated typed Tax Model snapshots without flattening;
- required typed declaration settlement components;
- explicit requirement-resolution manifest, including legitimate absence;
- component-native provenance plus minimal content/contract/owner hash binding;
- deterministic completeness receipt.

### Excluded

- raw source documents, Financial Case traversal and fact search;
- methods, formulas, rates-as-rules or legal decisions still to be made;
- user questions, clarification workflow and acquisition plans;
- XML/PDF names, paths, order, field numbers, namespaces and encodings;
- target fragments, target tree, serialized bytes and conformance receipt;
- inferred zero/default values;
- generic `dict[str, Any]`, open extension values or LLM-authored runtime logic;
- duplicate flattened copies of component values/provenance trees.

### Final PROJECT pressure test

For a `DECLARATION_COMPLETE` package, final PROJECT can:

1. validate package/Definition/Projection bindings;
2. read typed semantic components already present;
3. map them through one exact Projection Definition;
4. construct the full target tree/representation;
5. invoke target serializer and conformance validator.

It must not search facts, read case/store data, calculate tax, decide
applicability, ask a user or reconcile conflicting authorities. Если любое из
этих действий необходимо, package был не complete.

### Multi-target and version pressure

```text
same complete Declaration Model
  ├─ exact XML Projection -> XML tree/bytes -> XML conformance
  └─ exact PDF/Form Projection -> form values/rendering -> target validation
```

| Change | Correct owner |
| --- | --- |
| XML/XSD layout, tag or ordering change | Projection Definition / target adapter |
| PDF layout change | PDF/Form Projection |
| tax rule change | trusted methodology + affected typed Tax Model |
| stable declaration semantic requirement changes | Declaration Definition and, only if necessary, component/model contract version |
| filing acquisition channel changes | existing case/user integration around filing-context owner |

No target-specific field is needed in the surviving package to support either
projection.

## First real missing semantic dependency

Selected blocker:

```text
COMPLETE_DECLARATION_SCOPE_RESOLUTION_MISSING
```

Current system has no exact full-declaration requirement/applicability set and
no case-time evidence receipt that accounts for every stable domain for this
taxpayer/period as either applicable or legitimately not applicable.

Это состоит из двух неразделимых частей:

1. authority prerequisite — publish a target-independent Declaration
   Definition manifest naming the complete stable requirement set, typed
   contracts and applicability expectations;
2. case semantic prerequisite — resolve that manifest for the exact
   taxpayer/case/period with evidence-bound applicability/coverage states.

Без них невозможно определить, какие Tax Models и filing components вообще
обязаны присутствовать. Поэтому немедленно реализовать `РасчНалПУ`, tax payable
или document summary недостаточно: даже с ними неизвестно, потеряны ли foreign,
business, property, deduction или other-income domains.

После scope resolution downstream blockers уже видимы и сохраняются:

- declaration taxpayer identity authority binding;
- filing and signer context;
- typed group tax settlement (`РасчНалПУ` meanings);
- document-level payable/refund disposition (`СумНалПу` meanings).

Первый отдельно авторизуемый declaration-driven slice должен доказать bounded
Definition-governed declaration-scope applicability/completeness contract и
receipt. Он не должен вычислять tax payable или строить full PROJECT.

## KISS decision

Surviving model adds no capability family, DSL, ontology, graph, workflow, DB
or registry service. Минимальные stable owners:

```text
existing typed semantic component owners
+ one declaration/filing-context component owner
+ one Declaration Model assembler/validator
+ one Definition-bound completeness receipt
```

Manifest содержит IDs и bindings, но не переносит component schemas или
business logic. Это сохраняет one owner per meaning и позволяет менять форму
без переписывания tax runtime.

## Limitations and scope stop

- Audit establishes a semantic boundary, not complete legal interpretation of
  every official field.
- Official XSD/format were used for requirement discovery; XSD/Schematron
  execution and final conformance were outside G5.26.
- No real taxpayer declaration-scope applicability was asserted.
- No taxpayer identity, signer, filing context, settlement or bank details were
  acquired.
- No Declaration Model runtime/schema, Definition publication, tax payable,
  `РасчНалПУ`, `СумНалПу`, full PROJECT, XML/PDF, serializer, filing, GUI, DB,
  registry, workflow or new capability was implemented.
- The disposable validator was not added to repository and is not production
  evidence.

G5.26 is research-only and closed at the named boundary. No dependent GOAL was
started.
