# Broker Reports Gate 5 Declaration Scope Resolution Research — G5.27

Date: 2026-08-10

Status: `G5.27_CLOSED`

Outcome: `DOMAIN_LEVEL_AUTOMATIC_FIRST_HUMAN_RESIDUAL`

Architecture decision: `KEEP_FIVE_PRIMITIVES`

Next contract status: `G5.28_CONTRACT_CONFIRMED`

Next allowed GOAL: `G5.28_TRUSTED_FULL_DECLARATION_DEFINITION_AUTHORING_PROOF`

Product status: `INACTIVE RESEARCH`

Implementation status: `NOT_STARTED`

## Verdict

Самая простая устойчивая scope boundary — одна applicability decision на
**stable semantic domain / typed component family**, а не на XML field, не на
каждый внутренний component value и не на декларацию целиком.

```text
exact trusted Declaration Definition
        ↓
closed top-level semantic-domain manifest
        ↓
automatic deterministic evidence pass
  1. Definition-owned always requirements
  2. existing validated typed components
  3. official Financial Case / existing case facts
  4. exact published typed applicability behavior, only where necessary
        ↓
conflict check
        ↓
one bounded human residual at a time, only where policy permits
        ↓
Scope Resolution Receipt
```

Scope states:

```text
APPLICABLE
NOT_APPLICABLE
UNRESOLVED
CONFLICT
```

`SCOPE_RESOLVED` означает, что каждый top-level domain exact Definition имеет
`APPLICABLE` или evidence-bound `NOT_APPLICABLE`. Это ещё не
`DECLARATION_COMPLETE`: у applicable domain может отсутствовать требуемый typed
component. На следующей package boundary это станет `REQUIRED_MISSING`.

Scope Resolution остаётся разновидностью RESOLVE. Новый `DECIDE` primitive,
universal rules engine или questionnaire engine не доказан. ACQUIRE нужен
только для остаточного evidence; EXECUTE — только для exact reviewed typed
classification, которую нельзя честно свести к presence/attestation.

G5.27 подтверждает предпосылку G5.28: полный root scope выражается маленьким
semantic manifest. G5.28 и case-time G5.29 в этом GOAL не выполнялись.

## Current evidence baseline

### What is already reusable

- `Gate4FinancialCaseRuntimeFactory.create` остаётся official financial read
  boundary. Его SQL — rebuildable cache; scope resolver не должен читать schema
  таблиц или строить произвольные SQL queries.
- `resolve_required_values_v0` уже проверяет closed requirements сначала через
  current Financial Case, затем через same-run supplemental facts, и не
  изобретает missing values.
- `execute_published_typed_behavior_v1` уже способен исполнить exact static
  implementation over exact typed contracts с methodology/provenance binding.
- `aggregate_complete_category_scope_v0` и current income-group behavior дают
  сильное positive evidence для bounded securities domain.
- Existing OpenWebUI/client path и `obtain_one_missing_money_input_v0` доказали
  безопасный pattern: один missing input, strict model proposal, deterministic
  validation, trusted persistence, recheck.
- Existing source adaptation содержит candidate taxpayer/period facts, а
  `ArtifactAccessContext` даёт ACL/case identity. Ни одно из них само по себе не
  является declaration taxpayer/signing authority.

### What cannot be promoted

- `CASE_COMPLETE_FOR_CURRENT_INPUT_SET` доказывает только technical readiness
  current visible input set, не отсутствие иных доходов/документов.
- complete securities category доказывает exact category member set, не весь
  declaration scope.
- complete income group доказывает exact group inputs, не отсутствие foreign,
  business, property или deduction domains.
- отсутствие fact/component в Financial Case не означает `NOT_APPLICABLE`.
- current human-loop capability принимает только money. Он является reusable
  interaction pattern, но не готовым boolean applicability resolver.
- LLM proposal, broad user statement и current Definition candidates не
  являются case-time decision authority.

## Competing hypotheses

| Hypothesis | Support | Counter-evidence / cheap test | Verdict |
| --- | --- | --- | --- |
| H1: applicability requirement на каждый XML field | exact coverage target fields; простая связь с XSD | official target has dozens of optional/repeated nodes; field omission often depends on already-resolved component value; form changes would rewrite scope runtime | `FALSIFIED`: target schema mirror |
| H2: одна assertion «это вся декларация» | минимальный UX; один user answer | mixed state `securities=applicable`, `foreign=unresolved`, `refund=not_applicable` невозможно представить или проверить | `FALSIFIED`: hides first blocker |
| H3: decision на каждый semantic value/component subfield | precise missing inventory | повторяет internal Tax Model validation, создаёт сотни prompts и смешивает applicability с component completeness | `FALSIFIED AT ROOT`; допустимо внутри separately activated domain Definition |
| H4: domain-level manifest + automatic first + bounded human residual | совпадает с typed owner boundaries; позволяет progressive domain Definitions; не зависит от target layout | требовалось проверить official surface accounting, absence/negative evidence и conflict behavior | `SURVIVES` |
| H5: case-time LLM решает applicable/not applicable | гибкость natural language | превращает LLM в tax engine; decision невозможно replay по exact typed authority; prompt drift меняет legal scope | `FALSIFIED` |
| H6: generic rules/questionnaire engine | может выразить все conditional branches | требует conditions DSL, workflow state, registry и universal interview ontology до первого case proof | `FALSIFIED` |
| H7: form-specific handwritten resolver with nested `if` for every section | deterministic and type-checkable | переносит authoring output в code deploy, смешивает Definition change с runtime release | `FALSIFIED AS DEFAULT`; exact typed behavior разрешён только для реально сложной классификации |

H4 выдерживает type safety, authoring, version change и human-loop pressure без
шестого primitive family.

## Granularity rule

Top-level semantic domain создаётся, только если одновременно выполнены четыре
условия:

1. domain имеет одно понятное applicability question для exact case/period;
2. applicable state активирует coherent typed component family/owner;
3. domain имеет одну совместимую evidence policy;
4. он может эволюционировать независимо от XML/PDF layout.

Если два meanings имеют разные applicability/evidence owners, их надо разделить.
Если optionality является внутренним tagged union или value-level invariant
одного typed component, новый top-level domain не нужен.

Примеры:

- signer всегда required; self/representative — tagged union внутри signer
  component, а не два глобальных domains;
- property disposition и property-acquisition deduction имеют разные event vs
  elective-claim policies, поэтому это разные domains;
- Section 2 field names не domains: stable owner — income-group base/settlement;
- отдельные social deduction kinds могут раскрыться внутри activated deduction
  Domain Definition, не раздувая root manifest.

## Official semantic-domain inventory

Official evidence live-link availability повторно проверена 2026-08-10:

- [страница приказа ФНС](https://www.nalog.gov.ru/rn77/about_fts/docs/16589324/)
  — HTTP 200;
- [official XSD 5.20.01](https://www.nalog.gov.ru/html/sites/www.new.nalog.ru/files/about_fts/docs/xsd/NO_NDFL3_1_033_00_05_20_01.xsd)
  — HTTP 200.

Exact cached official bytes, использованные для backward audit:

```text
procedure DOCX  7bc11cad8d0465c03c834c50c7832fb2edc7291d9b4b161ef5b2c6cabdcb0fdc
format DOCX     f5215c237a8af73dd7a251cee94a2e09aacd8540173fcde2904b4c311129e3c2
XSD 5.20.01     083128322833dbafb29be0bf919e33b7b362956244b422d34dd554c99a1e4484
```

Пункт 15 official procedure говорит, что title, Section 1 и Section 2
обязательны, а application to Section 1, Appendices 1–8 и calculations to
Appendices 1/5 заполняются при необходимости. Пункты 16–23 и последующие
sections дают stable business meanings условных частей: domestic/foreign
income, business/private practice, exemptions, deductions, property and
securities/investment operations.

Это даёт следующий target-independent candidate inventory. Он является
research result G5.27, но ещё не trusted Definition G5.28.

| Domain ID | Stable meaning | Root applicability |
| --- | --- | --- |
| `declaration_filing` | declaration instance, period, correction, destination, date/type | `ALWAYS` |
| `taxpayer_identity_status` | filing taxpayer identity and period-bound status | `ALWAYS` |
| `signer_representation` | signer role/identity and representative authority union | `ALWAYS` |
| `income_group_base_settlement` | non-empty collection of applicable income-group bases and tax settlements | `ALWAYS` |
| `document_tax_disposition` | declaration-level payable/refundable allocation | `ALWAYS` |
| `domestic_taxable_income` | taxable income from Russian sources | conditional |
| `foreign_taxable_income` | taxable income from sources outside Russia and related foreign-tax credit context | conditional |
| `business_private_practice` | entrepreneurial, advocate and private-practice income/advances | conditional |
| `other_professional_deductions` | professional deductions outside the business/private-practice occurrence family | conditional/elective |
| `non_taxable_exempt_adjustments` | income amounts legally excluded from taxation or excess-limit adjustments | conditional |
| `standard_social_investment_longterm_deductions` | claimed standard/social/investment/long-term-saving deductions | conditional/elective |
| `property_disposition` | property/vehicle/rights disposal or gift income and related disposition deductions/calculations | conditional |
| `property_acquisition_interest_deductions` | claimed acquisition/construction/interest property deductions | conditional/elective |
| `securities_derivatives_digital_partnership` | securities, derivatives, digital assets/rights, investment partnership, relevant loss/deduction semantics | conditional |
| `refund_request_destination` | elective refund request and bank destination | conditional/elective |

### Surface-accounting falsification

Disposable accounting mapped 14 official form surfaces — title, Sections 1/2,
refund application, Appendices 1–8 and two calculations — to the 15 candidate
semantic domains:

```text
official_surfaces        = 14
stable_semantic_domains  = 15
unmapped_surfaces        = 0
one_to_one_mirror        = false
```

Many-to-many cases are material:

- title maps to filing, taxpayer and signer owners;
- Appendix 1 may consume both domestic-income and property-disposition
  semantics;
- property disposition contributes to multiple target surfaces;
- deduction domain contributes to Appendix 5 and its calculation.

Поэтому inventory accounts for official surface without being a one-to-one
copy of form structure. Exact partition remains subject to independent G5.28
authoring/validation; an alternative is acceptable only if it preserves full
surface accounting and the granularity rule above.

## Minimal Scope Resolution Model

Scope Resolution Model содержит только concrete applicability decisions и
their evidence bindings. Tax values, component snapshots and projection data в
него не входят.

### Non-authoritative machine sketch

```json
{
  "schema_version": "declaration_scope_resolution_v0_research",
  "definition_binding": {
    "definition_id": "stable-id",
    "definition_version": "exact-version",
    "definition_sha256": "sha256"
  },
  "scope_binding": {
    "case_ref": "opaque-ref",
    "taxpayer_scope_ref": "opaque-ref",
    "tax_period": "YYYY",
    "declaration_instance_ref": "opaque-ref",
    "scope_sha256": "sha256"
  },
  "domain_decisions": [
    {
      "domain_id": "definition-owned-stable-id",
      "definition_requirement_sha256": "sha256",
      "state": "applicable|not_applicable|unresolved|conflict",
      "resolution_route": "definition|resolve|execute|acquire|null",
      "evidence_bindings": [
        {
          "authority_class": "closed-enum",
          "owner_contract": "exact-owner-id",
          "evidence_sha256": "sha256",
          "polarity": "applicable|not_applicable"
        }
      ],
      "decision_sha256": "sha256"
    }
  ],
  "receipt": {
    "status": "scope_resolved|scope_incomplete",
    "definition_sha256": "sha256",
    "scope_sha256": "sha256",
    "decision_set_sha256": "sha256",
    "unresolved_domain_ids": [],
    "conflict_domain_ids": []
  }
}
```

Это conceptual contract, не production schema. Definition, а не case receipt,
владеет `applicability_policy`, allowed evidence classes и expected component
family. Receipt связывает exact Definition requirement hash вместо копирования
её rule metadata.

### State algebra

| Scope state | Meaning | Terminal for scope? | Later package meaning |
| --- | --- | --- | --- |
| `APPLICABLE` | exact allowed evidence proves domain is in this case/period scope | yes | component must resolve; otherwise `REQUIRED_MISSING` |
| `NOT_APPLICABLE` | exact policy allows absence and evidence proves domain out of scope | yes | terminal legitimate absence |
| `UNRESOLVED` | no allowed evidence determines applicability | no | declaration remains incomplete |
| `CONFLICT` | allowed authorities/evidence imply incompatible polarities/scopes | no | adjudication required; no priority overwrite |

`APPLICABLE` не означает, что tax semantics рассчитаны. `NOT_APPLICABLE` не
означает numeric zero. `REQUIRED_MISSING` не нужен в scope model: это состояние
component completeness после applicable decision.

Research prototype различал пять closed policy profiles:

| Policy profile | Allowed decision basis |
| --- | --- |
| `ALWAYS` | Definition itself makes the domain applicable; negative forbidden |
| `ATTESTABLE_OCCURRENCE` | validated component/positive facts or exact policy-authorized declarant occurrence assertion; exhaustive coverage may prove absence |
| `TYPED_DECISION_OR_COVERAGE` | exact published typed behavior decides polarity, or true exhaustive coverage proves absence |
| `COMPONENT_OR_ATTESTATION` | validated component proves positive; exact occurrence attestation may resolve the no-event branch |
| `ELECTIVE` | explicit claim/request proves positive; authenticated non-election proves negative |

These are finite contract profiles, not boolean expressions. G5.28 may rename or
split a profile only with official evidence; it must not let the author combine
arbitrary predicates or source paths.

`SCOPE_RESOLVED` iff every exact Definition domain occurs once, every decision
is `APPLICABLE` or evidence-bound `NOT_APPLICABLE`, hashes match, and no orphan,
stale or conflicting evidence exists. Otherwise result is `SCOPE_INCOMPLETE`.

## Ownership and primitive routing

| Concern | Owner | Primitive / reuse |
| --- | --- | --- |
| domain inventory, applicability mode and allowed evidence classes | exact trusted Declaration Definition | authoring/publication plane; no case-time primitive |
| official financial evidence lookup | `Gate4FinancialCaseRuntimeFactory.create` through existing RESOLVE owner | `RESOLVE`; no direct SQL |
| existing validated Tax Model/component evidence | component factory/validator that produced it | `RESOLVE` consumes its exact receipt/hash; does not recalculate |
| legal/derived applicability classification | exact registered typed behavior + trusted methodology | `EXECUTE` only when presence/attestation is insufficient |
| one missing factual/elective assertion | existing OpenWebUI interaction path + trusted case fact persistence pattern | `ACQUIRE`; current money-only capability is not silently generalized |
| decision accounting/conflict/completeness | small deterministic Scope Resolution assembler/validator | root `RESOLVE` orchestration, ordinary code |
| target section presence | final Projection Definition after scope/components resolve | `PROJECT`, outside G5.27 |

No separate DB, registry, workflow or rules service is required. Scope
assertions, if later implemented, may reuse existing ArtifactStore lifecycle,
ACL and case binding. SQL remains a replaceable Gate 4 query projection.

### Deterministic resolution order

1. Validate exact Definition and case/taxpayer/period binding.
2. Materialize one decision row for every Definition domain.
3. Mark Definition-owned `ALWAYS` domains `APPLICABLE`; missing values are not
   scope questions.
4. Bind already validated same-scope typed components as positive evidence.
5. Use closed RESOLVE requirements against official Financial Case and eligible
   existing user/case facts. Current-input absence remains non-evidence.
6. Invoke only exact published typed EXECUTE behaviors for classification the
   Definition says requires them.
7. If allowed evidence has opposite polarities, return `CONFLICT`; never apply
   last-write-wins or generic source priority.
8. For remaining `UNRESOLVED` domains, acquire at most one exact factual or
   elective assertion where Definition policy explicitly allows it, persist
   through trusted case scope and rerun the same resolver.
9. Seal the decision/evidence hash receipt. Do not create Tax Models or PROJECT
   output in this action.

This is a bounded deterministic coordinator over existing owners, not a
declarative execution graph.

## Applicability evidence matrix

| Semantic domain | Positive / `APPLICABLE` proof | Legitimate `NOT_APPLICABLE` proof | Allowed evidence/owner class | Human boundary |
| --- | --- | --- | --- | --- |
| declaration filing | Definition `ALWAYS` | forbidden | Definition + typed filing context later | human may supply missing values, never decide applicability |
| taxpayer identity/status | Definition `ALWAYS` | forbidden | identity/status components; source/user facts; typed behavior for legal status | identity facts may be acquired; status classification is not a bare yes/no |
| signer/representation | Definition `ALWAYS`; exact self/representative union value | forbidden for signer; representative branch absent only when self-signing role resolved | filing context, authenticated user assertion, representative document | human may choose role; representative authority requires its evidence |
| income-group base/settlement | Definition `ALWAYS`; non-empty group set derived from applicable income domains | forbidden | typed Tax Models + trusted methodology | no scope question; missing calculation becomes downstream gap |
| document tax disposition | Definition `ALWAYS` | forbidden | typed composition over complete group settlements + filing identifiers | no applicability question |
| domestic taxable income | matching validated source-income/Tax Model evidence | exact period/domain negative attestation allowed by Definition, or true exhaustive-domain coverage | Financial Case positive facts, typed component, authenticated declarant assertion | ask only after automatic pass; current-input absence is insufficient |
| foreign taxable income | matching income evidence plus typed source-jurisdiction classification where needed | exact negative attestation only if Definition permits and no candidate facts; or exhaustive-domain coverage | Financial Case/source facts, EXECUTE classification, authenticated assertion | user may attest no occurrence; cannot legally classify a known payment by assertion alone |
| business/private practice | matching activity/income facts or component | exact period activity-negative attestation with no conflict, or exhaustive coverage | Financial Case, source/case facts, typed domain owner | one exact factual question may suffice |
| other professional deductions | explicit claim plus eligible income/evidence | authenticated decision not to claim for this filing | user/case claim, source support, typed deduction owner | explicit decline is sufficient for elective claim; eligibility is not |
| non-taxable/exempt adjustments | source facts + reviewed typed exemption behavior/component | exhaustive evidence or exact policy-approved negative assertion with no candidate fact | Financial Case, reference facts, EXECUTE, Tax Model | user cannot override known candidate income/exemption conflict |
| standard/social/investment/long-term deductions | explicit claim and domain evidence | authenticated decision not to claim in this filing | user/case claim, supporting source facts, typed deduction owner | decline may close scope; claimed eligibility/amount remains downstream |
| property disposition | matching disposal/gift/rights event evidence | exact period event-negative attestation or exhaustive event coverage | Financial Case/source facts, user/case evidence, property Tax Model | factual event question allowed; taxability/exemption needs typed owner |
| property acquisition/interest deductions | explicit deduction claim and object/expense evidence | authenticated decision not to claim | user/case claim, supporting documents, typed property-deduction owner | decline is sufficient for filing scope, not an eligibility ruling |
| securities/derivatives/digital/partnership | current validated operation/category component or matching source facts | exact period/domain negative attestation allowed by Definition or exhaustive coverage | current Gate 5 Tax Models, Financial Case, user/case evidence | current complete securities model is strong positive evidence; absence is not negative |
| refund request/destination | refundable settlement plus explicit request | authenticated decision not to request refund in this declaration | settlement component + user filing election | explicit decline is sufficient; bank data asked only when applicable |

### Absence law

```text
no matching current Financial Case fact
!=
NOT_APPLICABLE
```

Negative resolution needs one of:

- exact trusted domain-coverage receipt proving absence;
- exact typed behavior result `NOT_APPLICABLE`;
- exact authenticated declarant assertion, but only for a Definition policy
  that permits that evidence class;
- explicit non-election for an elective claim/request.

The current Gate 4 completeness status is not a domain-coverage receipt and
must not be used as one.

## Human residual boundary

Human involvement is justified only after deterministic evidence routes leave
one exact domain unresolved. A future bounded adapter should reuse the proven
G5.6 pattern, not the exact money contract:

```text
one unresolved domain
-> exact period/domain question
-> bounded yes/no/enum assertion proposal
-> deterministic answer validation
-> Definition evidence-policy check
-> trusted case-bound persistence
-> full scope recheck
```

The LLM may phrase a question or propose an interpretation. It must not choose
the requirement ID, scope, evidence sufficiency, legal classification or final
state.

`USER SAYS NO` is sufficient only when all are true:

1. exact Definition policy permits authenticated declarant negative assertion;
2. question names one stable domain and exact tax period/scope;
3. answer is unambiguous and deterministically bound;
4. no positive or conflicting case/component evidence exists;
5. receipt retains assertion and policy hashes.

Otherwise the domain stays `UNRESOLVED` or becomes `CONFLICT`. Broad statements
such as «это все документы» or one whole-declaration checkbox cannot close
multiple domains.

## Disposable state-algebra experiment

In-memory prototype использовал 11 representative domain rows и пять closed
policy shapes. Он не читал customer data, не рассчитывал tax и не создавал
repository fixture/runtime.

Observed outcomes:

```text
bounded_mixed_scope:
  SCOPE_INCOMPLETE; unresolved=['foreign_income']

foreign_user_no_not_authorized:
  foreign_income=UNRESOLVED

business_source_vs_user_conflict:
  business_private_practice=CONFLICT

absence_without_coverage:
  domestic_income=UNRESOLVED

absence_with_exhaustive_coverage:
  domestic_income=NOT_APPLICABLE
```

The mixed synthetic case automatically marked mandatory domains applicable,
accepted current securities component as positive evidence, accepted explicit
non-election where permitted, but did not hide the foreign-income blocker.

The test discriminates the architecture:

- one whole-declaration assertion loses the exact unresolved domain;
- Financial Case absence alone produces a false negative;
- source evidence plus user denial must not resolve by priority;
- evidence-bound negative coverage can safely terminate a domain;
- a small finite state contract is sufficient; arbitrary conditions language
  is not required.

Synthetic states are architecture evidence only. They make no claim about a
real taxpayer or whether foreign/business/property domains are absent.

## Why the five primitives remain sufficient

| Action | Existing primitive |
| --- | --- |
| resolve `ALWAYS`, existing component and case-fact evidence | RESOLVE |
| ask for one permitted missing factual/elective assertion | ACQUIRE |
| derive a legal applicability classification from exact typed inputs | EXECUTE |
| later combine complete operation/domain models | AGGREGATE |
| later map complete semantics to target | PROJECT |

The receipt assembler validates accounting; it does not introduce independent
business behavior. Calling it `DECIDE`, `INTERVIEW` or `SCOPE` as a sixth base
primitive would rename composition of RESOLVE/ACQUIRE/EXECUTE without new
semantics.

## Minimal proof plan for G5.28

G5.27 confirms that a small root semantic manifest is viable. The next
authorized GOAL should test authoring/publication only.

### Input

- exact official procedure/format/XSD evidence and hashes;
- G5.27 granularity rule, candidate inventory and evidence-policy boundary;
- proven G5.21+ independent LLM authoring transport/validator pattern;
- Runtime Capability Contract v3 and current published artifact inventory;
- G5.26 Definition-bound completeness boundary.

### Candidate contract

Independent LLM should author one target-independent root manifest with:

```text
definition identity/version;
unique stable domain IDs;
ALWAYS or conditional applicability expectation;
one small closed evidence-policy kind per domain;
expected typed component family/contract where known;
allowed authority/provenance classes;
official evidence refs;
honest missing-domain-definition/component gaps.
```

It must not contain XML names/order/paths, target field cardinality, Python,
formulas, XPath, arbitrary boolean expressions, question flow or runtime
execution graph.

### Deterministic checks

1. Closed schema, unique Definition/domain identities and exact evidence hashes.
2. Every official mandatory/conditional surface is accounted to at least one
   stable semantic domain; no domain exists only because of target layout.
3. `ALWAYS` requirements cannot allow `NOT_APPLICABLE`.
4. Conditional domain has exactly one approved policy kind and allowed evidence
   classes; no free-form condition string.
5. Every applicable-output expectation names one closed typed component family
   or an explicit missing contract, not `Any`.
6. Policy/evidence combinations are consistent: elective decline, factual
   occurrence, exhaustive coverage and typed legal classification are not
   interchangeable.
7. Neutral validator receives immutable independent candidate; no silent repair
   or expected-answer injection.
8. Trusted publication remains separate and reviewable; candidate alone is not
   execution authority.

### Acceptance / stop

Success is:

```text
independent authoring candidate
-> deterministic semantic + surface-accounting validation
-> reviewed trusted root Declaration Definition
```

Stop before case-time applicability, human questions, Scope Resolution receipt,
Declaration Model, tax payable or projection. Only a successful G5.28 may
authorize bounded G5.29.

## Rejected overengineered approaches

### XML/XSD-derived requirement list

Rejected: target optionality/order is not semantic applicability and changes
with representation version.

### Universal applicability rules DSL

Rejected: expressions, fact paths and conditions would create a second tax
language. Complex classification belongs in one published typed EXECUTE owner.

### Questionnaire engine / stored workflow

Rejected: automatic evidence should resolve most positive domains first; only
current residual needs one bounded interaction. No interview graph/state DB is
required.

### Generic ontology / knowledge graph

Rejected: closed domain IDs, typed components and content-hash evidence already
support deterministic accounting and provenance.

### One negative taxpayer declaration for all unseen domains

Rejected: scope and evidence sufficiency differ by factual occurrence,
elective claim and legal classification. It would convert convenience into a
false completeness claim.

### Per-form hardcoded resolver

Rejected as normal path: Definition changes should not require editing runtime.
Small static typed behaviors remain allowed only when a real domain decision
cannot be made by existing closed evidence.

### Current-input absence as negative evidence

Rejected: Gate 4 readiness proves current input technical completeness, not
taxpayer/domain coverage.

## Risks and validation requirements for future slices

- Domain partition may omit an official conditional surface; G5.28 needs exact
  bidirectional surface-accounting evidence.
- Too-permissive user-negative policy can erase legal obligations; every policy
  choice needs official evidence and review.
- Positive fact presence can be a candidate rather than legal applicability;
  use typed behavior where classification matters.
- Overlapping domains can double-count values later; scope receipt only selects
  owners, while typed Tax Model/component contracts must own value accounting.
- Domain Definition expansion must not mutate the trusted root decision set or
  introduce a workflow graph.
- Definition version/evidence/policy hash drift must invalidate old receipts.
- No conflict may be resolved by source priority or user overwrite without a
  separately owned adjudication contract.

Future acceptance should include exact hash mutation tests, wrong-period and
wrong-case rejection, user-negative-vs-positive conflict, absence-without-
coverage failure, Definition version mismatch and privacy-safe evidence output.

## KISS decision

The surviving research boundary needs:

```text
one small Definition-owned domain manifest
+ existing typed evidence owners
+ existing RESOLVE / ACQUIRE / EXECUTE routes
+ one deterministic decision accountant
+ one hash-bound receipt
```

No Tax DSL, rule engine, questionnaire platform, graph, workflow, new DB,
registry service or sixth primitive is justified.

`architecture-blueprint-guardrails` kept decisions aligned to component owners
and rejected abstractions with no current pressure. `pb-docs-output-routing`
routed this research result to the dated report boundary; no contract authority
was edited.

## Scope stop

G5.27 is research-only and closed.

Not implemented:

- Scope Resolution runtime/schema/validator;
- applicability behavior or policy registry;
- yes/no human-loop capability or questionnaire;
- trusted full Declaration Definition;
- case-time applicability receipt;
- filing/taxpayer/signer acquisition;
- tax payable, settlement, Declaration Model/package;
- PROJECT, XML/PDF, serialization, conformance, GUI, DB or new capability.

No case was declared scope-complete. No real `NOT_APPLICABLE` assertion was
made. G5.28 is the only next allowed GOAL; no later strategic GOAL was started.
