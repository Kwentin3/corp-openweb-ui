# G5.39AB — Consumer-First Re-Derivation of the 3-NDFL Declaration Contract

Verified on: 2026-08-12

Mode: research only. No runtime, DTO, Gate 4/5, test, product, database,
activation, commit, push or PR change is authorized.

## Terminal

```text
THREE_CONTRACT_BOUNDARY_PROVEN_FOR_SUPPLIED_CASE
SEMANTIC_INPUT_CAN_BE_SMALLER_THAN_RESOLVED_PACKAGE
RESOLVED_PACKAGE_IS_A_SEALED_AUDIT_ENVELOPE_NOT_A_DECLARATION_DTO
STRATEGIC_STOP: UNRESEARCHED_LEGAL_METHODOLOGIES_FOR_INACTIVE_DOMAINS
```

The minimal boundary immediately before Projection Definition is not one rich
Package. It is three independently owned results:

```text
Declaration Semantics
+ Calculation Evidence
+ Completeness Receipt
```

Only Declaration Semantics is projector input. Calculation Evidence proves how
every derived declared value was obtained. Completeness Receipt proves why every
official obligation is terminal for the supplied case. The latter two are
release conditions and audit records, not declaration fields.

This result is complete for the supplied-case obligation profile: all 25
reviewed obligations are accounted, 8 are projected and 17 are terminal
`NOT_ACTIVATED_FOR_SUPPLIED_CASE`. It does not claim that the taxpayer had no
other real-world income, property, gifts, activities, deductions or elections.
It also does not claim universal calculation support for those 17 inactive
obligations.

The full safe machine-readable result is
[the G5.39AB matrix](./BROKER_REPORTS_GATE5_CONSUMER_FIRST_DECLARATION_G5_39AB.matrix.safe.json).

## 1. Official consumer demand

The current authority is FNS Order ED-7-11/913@ of 20 October 2025. The FNS
publication page states that the new form, filling procedure and electronic
format apply to declarations for tax period 2025 from 1 January 2026. The bytes
used by the trusted repository authority were downloaded again in this loop;
the 106,008-byte filling procedure has the same SHA-256
`7bc11cad8d0465c03c834c50c7832fb2edc7291d9b4b161ef5b2c6cabdcb0fdc`.

The official consumer requires meanings, not the current internal object graph:

- filing, taxpayer, signer and conditional representation semantics;
- declaration-level budget disposition;
- one coherent tax-base and settlement result per applicable income group;
- conditional source-income, activity, exemption, deduction, property, gift and
  financial-investment results.

The 16-page official form and its filling procedure establish those surfaces.
Procedure paragraphs 37-55 own the Section 2 result meanings. Paragraphs 97-98
own the Appendix 8 category row: operation kind, aggregate income, related
expenses, allowable expenses and loss treatment. They do not require Package
hashes, domain rows, component IDs, source manifests, event relations or Tax
Model snapshots to appear in the declaration.

Official sources:

- [FNS Order ED-7-11/913@ publication](https://www.nalog.gov.ru/rn77/about_fts/docs/16589324/)
- [Official 3-NDFL form PDF](https://www.nalog.gov.ru/html/sites/www.new.nalog.ru/files/about_fts/docs/16589324_1.pdf)
- [Official filling procedure DOCX](https://www.nalog.gov.ru/html/sites/www.new.nalog.ru/files/about_fts/docs/16589324_2.docx)
- [Official electronic format DOCX](https://www.nalog.gov.ru/html/sites/www.new.nalog.ru/files/about_fts/docs/16589324_3.docx)
- [Official XSD 5.20.01](https://www.nalog.gov.ru/html/sites/www.new.nalog.ru/files/about_fts/docs/xsd/NO_NDFL3_1_033_00_05_20_01.xsd)

The repository's trusted Definition does not conflict with those current
sources. It binds 25 reviewed obligations into 11 target-independent domains.

## 2. Minimal Declaration Semantic Contract

For the supplied case, the smallest target-independent value surface is:

```text
tax_period

filing
  correction_number
  declaration_date
  tax_authority_code

taxpayer
  inn
  name
  period_status
  declarant_category

signer
  identity
  capacity
  representation_authority?  # only when a representative signs

budget_dispositions[]
  kind
  kbk
  oktmo
  amount

income_group_results[]
  income_group
  total_income
  non_taxable_income
  taxable_income
  tax_deductions
  accepted_expenses
  tax_base
  calculated_tax
  settlement_amounts
  tax_payable
  tax_refundable

russian_source_income[]
  income_kind
  source_party
  gross_income
  withheld_tax

financial_investment_results[]
  operation_category
  category_gross_income
  related_expenses
  allowable_expenses
  loss_treatment
```

This is a conceptual contract, not a production DTO proposal. A value remains
in the contract only when removing it breaks a current official meaning for the
supplied case. It may be direct evidence-backed input or a methodology-derived
tax result; origin does not change its status as a declared value.

The following are deliberately absent:

- `definition_id`, component contract IDs and component hashes;
- `scope_ref`, `case_id`, normalization-run identity and scope hashes;
- domain rows, obligation refs and terminal states;
- methodology definitions, input snapshots, provenance and derivation trees;
- XML/PDF locators, KND, format version and order identity;
- electronic file ID and program version.

`declaration_instance_ref` fails the paper-declaration consumer test and is used
only as the XML file identifier in the current projection. It belongs to target
representation. `income_group_code` duplicates the semantic group; the
Projection Definition already owns the code mapping. The current source-entry
`taxable_income` is not read by the supplied-case source-row projection; the
declared taxable result remains at the income-group level.

## 3. Calculation Evidence Contract

Every methodology-derived declared value gets one replayable calculation
record:

```text
calculation_id
declared_value_path
declared_value

methodology_id
methodology_version
methodology_content_sha256
effective_tax_period

rule_or_formula_trace
used_fact_refs[]
used_fact_values[]
source_evidence_refs[]
external_reference_refs[]
dependency_calculation_refs[]

calculation_sha256
```

This contract owns exact intermediate values, methodology bindings, fact
membership and source/external evidence. The private authoritative record must
retain the values needed for replay; a safe report may expose only hashes and
counts. Direct facts such as taxpayer INN or broker-reported withholding retain
evidence bindings but must not acquire fake calculation objects.

Intermediate results do not need to become persistent domain entities. An
income-group subtotal or FIFO lot-consumption trace may live inside a sealed
calculation receipt if it can be replayed and addressed. It becomes a reusable
domain object only after another consumer is proven.

Current Tax Models, category aggregation, income-group base and settlement
results are therefore legitimate. Their mandatory consumer role is calculation
evidence, not projection input structure.

## 4. Completeness Receipt Contract

The separate completeness result contains:

```text
definition id/version/hash
case and tax-period scope binding
one disposition for each of 25 obligations
evidence binding for each disposition
blockers[] and first blocker
real_world_taxpayer_completeness_asserted = false
receipt hash
```

Allowed terminal dispositions are:

```text
RESOLVED
NOT_APPLICABLE
NOT_ACTIVATED_FOR_SUPPLIED_CASE
```

`SCOPE_UNRESOLVED`, `SCOPE_CONFLICT` and `REQUIRED_MISSING` are blockers. A
release gate may hand values to a projector only when all 25 obligations occur
exactly once, every disposition is terminal, and all resolved values have valid
calculation/evidence bindings.

Completeness does not belong inside Declaration Semantics. The projector may
receive a value surface only after a separate gate validates completeness; it
does not need to parse inactive domain rows to serialize active values.

## 5. Declaration Demand Matrix

The domain-level result is:

| Trusted domain | Supplied case | Official consumer | Output owner when active |
| --- | --- | --- | --- |
| filing and party identity | `RESOLVED` | title/signature/electronic header | direct declaration facts |
| declaration budget disposition | `RESOLVED` | Section 1 | settlement-derived declaration result |
| income-group tax results | `RESOLVED` | Section 2 | income-group methodologies |
| refundable amount disposal | not activated | Section 1 appendix | election + refund methodology |
| taxable income by source | Russian resolved; foreign not activated | Appendices 1-2 | source classification result |
| professional activity | not activated | Appendix 3 | activity/deduction methodology |
| deduction claims | not activated | Appendices 3, 5, 7 and calculation | claim-specific methodologies |
| tax-exempt income | not activated | Appendix 4 | exemption methodology |
| property and vehicle dispositions | not activated | Appendix 6 and object calculation | property/vehicle methodologies |
| gift income | not activated | Appendix 6 and object calculation | gift classification methodology |
| financial investment results | securities resolved; DFA/partnership not activated | Appendix 8 | operation/category methodologies |

The exact 25-row matrix records consumer, methodology owner, required input
types, evidence classes, projection consumers, completeness policy, current
owner and recommended owner. No obligation was dropped because it was inactive.
Inactivity changes its supplied-case disposition, not its place in the trusted
Definition inventory.

## 6. Methodology Dependency Matrix

| Declared value family | Methodology | Minimal inputs | Proof class |
| --- | --- | --- | --- |
| filing/taxpayer/signer | none; validation only | authenticated case and filing facts | user/case + reference evidence |
| Russian source row | source jurisdiction and income-kind classification | gross, source party, income nature, withholding | source + external refs |
| Appendix 8 row | operation classification, expense eligibility/allocation, category aggregation | transaction atoms, expense evidence, instrument/account context, complete scope | source + user coverage + official method |
| Section 2 base | income-group aggregation/base method | category results, other income, exempt amounts, deductions, expenses | dependent calculation receipts |
| Section 2 tax/settlement | rate schedule, rounding and credits | base, status, withheld tax, applicable credits | official method + source/external tax evidence |
| Section 1 line | final disposition method | payable/refundable result, KBK, OKTMO | settlement receipt + reference facts |

The current supplied-case methodologies cover this bounded path. G5.39AB does
not derive the legal algorithms for all inactive domains. Their consumer-shaped
input/output demands are recorded, but their calculation contracts remain
`UNKNOWN` until domain-specific official research is performed.

One already known securities gap remains outside the supplied-case value path:
official authority inspected in G5.39AA did not establish an exact partial-lot
allocation rule for one acquisition-ticket commission. That value must fail
closed if a future case needs it.

## 7. Minimal Financial Fact Demand

Gate 4 needs no universal financial ontology. It needs only source-authored
facts demanded by a downstream methodology or direct declaration row:

1. income receipt: amount, currency, receipt date, source party, income nature
   and source evidence;
2. tax withheld/paid: amount, tax kind, withholding party, date/period and
   authority evidence;
3. security acquisition: instrument, sequence/date-time, quantity, purchase
   price, currency, payment/document evidence and relevant account context;
4. security disposal: instrument, sequence/date-time, quantity, proceeds,
   currency, receipt/document evidence and relevant account context;
5. financial expense: amount, currency, actual expense date, source-authored
   description, payment/document evidence and direct scope when the source says
   so;
6. external reference: official code, rate or limit with effective date and
   authority binding;
7. coverage fact: taxpayer, period, category/domain scope and covered source
   set, consumed only by completeness.

Tax eligibility, FIFO consumption, expense allocation, allowable amounts,
category totals, tax bases and tax amounts are methodology outputs. They are not
Gate 4 source facts.

## 8. Current-vs-Minimal Diff

The main disposition is:

| Current entity | Classification | Action |
| --- | --- | --- |
| Trusted Full Declaration Definition | completeness authority | `KEEP` outside value payload |
| Scope Receipt | completeness/audit | `MOVE_TO_COMPLETENESS` |
| Resolved Package | calculation + completeness envelope | `KEEP_AS_SEALED_AUDIT_ENVELOPE` |
| definition/scope/component snapshots | audit/evidence | move to their receipts |
| requirement resolutions and manifest | completeness | `MOVE_TO_COMPLETENESS` |
| current Semantic Input source hashes | audit | `REMOVE_FROM_REQUIRED_CONTRACT` |
| current completeness object and domain states | completeness | `MOVE_TO_COMPLETENESS` |
| typed-component wrappers and component hashes | evidence | `MOVE_TO_CALCULATION_EVIDENCE` |
| selected business payload values | declaration semantics | `KEEP`, reshape by consumer meaning |
| Tax Models and intermediate aggregates | methodology/evidence | keep outside projector input |
| Projection Definition | target representation | `KEEP` |
| XML tree/bytes | target representation | `KEEP` |
| distributed event/reconciled wrapper/relation IDs | research scar | `REMOVE_FROM_REQUIRED_CONTRACT` |

The full diff has 28 explicit rows in the machine-readable matrix.

### Existing Package audit

The Package is a real and useful owner of sealed validation today. It binds the
Definition, scope, exact-root components, requirement resolutions and
completeness receipt. That makes it an audit envelope. It does not make the
Package's object graph the smallest semantic model of what a declaration says.

This interpretation preserves reproducibility: no hashes or snapshots are
deleted from the evidence boundary. They merely stop leaking into the required
consumer contract.

### Existing Semantic Input audit

The current contract already acknowledges that the direct Package DTO is too
rich and excludes methodology, provenance and nested dependencies. G5.39AB
continues that logic one step further.

Current projector reads justify the business values, but not:

- five source-binding hashes;
- case and scope mechanics;
- completeness flags;
- 11 domain wrappers and their obligation states;
- source component IDs and hashes.

Those fields are legitimate validation metadata. They are not official
declaration semantics. Conversely, a field is not removed merely because the
bounded XML does not read it if the official declaration form still consumes
it. Official consumer demand outranks one target implementation.

### Projection Definition audit

The current Projection Definition passes the reverse audit for the supplied
case:

- 49 mapping occurrences are target-owned;
- 8 obligations have non-empty projected target paths;
- 17 obligations have the exact terminal non-activated outcome;
- 0 obligations are unaccounted;
- enum codes, constants, encoding, tree order and target paths stay outside
  semantic input.

The Projection Definition must not decide tax, recover missing semantics or
re-run completeness. A missing semantic source path is an upstream failure.

## 9. End-to-end provenance traces

### Taxpayer INN

```text
XML/PDF taxpayer INN
<- minimal Declaration Semantics taxpayer.inn
<- authenticated taxpayer case fact
<- identity evidence
```

No calculation is invented.

### Russian-source gross income and withholding

```text
Appendix 1 / XML gross income and withheld tax
<- minimal Russian-source income row
<- domestic-source and income-kind classification
<- broker/source gross-income and withholding facts
<- exact source evidence refs
```

### Appendix 8 allowable expense

```text
Appendix 8 allowable_expenses
<- minimal financial-investment category result
<- category aggregation
<- operation expense eligibility/allocation methodology
<- acquisition, disposal and fee atoms
<- payment and source-document evidence refs
```

### Section 2 tax base and tax

```text
Section 2 tax_base / calculated_tax
<- minimal income-group result
<- income-group base then rate/rounding methodology
<- category results, deductions, expenses, status and credits
<- dependent calculation receipts and source/user/external evidence
```

### Section 1 payable amount

```text
Section 1 budget amount
<- minimal budget disposition line
<- declaration-level settlement disposition
<- completed income-group settlements + KBK + OKTMO
<- settlement receipt + official reference + filing context
```

An omitted foreign-source appendix has a different proof: no empty semantic
object is projected; the separate completeness receipt records the
policy-authorized `NOT_ACTIVATED_FOR_SUPPLIED_CASE` disposition.

## 10. Research scars

- **Distributed financial event.** It appeared while trying to recover
  multi-row identity before a consumer was proved. No audited declaration or
  Tax Model requires the stored composite.
- **Generic relation/reconciled operation.** A local cost-allocation question
  was generalized into a reusable entity. The consumer needs source facts and
  a methodology trace, not a universal relation registry.
- **Resolved Package as declaration model.** One sealed object simplified
  replay, but its snapshots and diagnostics serve auditors rather than FNS.
- **Domain/component wrappers in Semantic Input.** They inherited the Package
  construction route. The projector needs their business payload, not the
  wrappers.
- **Duplicated semantic and target codes.** Target pressure copied codes into
  business payloads. The Projection Definition already owns representation
  mappings.

The healthy residue of earlier research is retained: exact source-bound atoms,
methodology-owned derived values, explicit audit evidence and fail-closed
completeness. The speculative mandatory entities are not retained.

## 11. Current Knowledge

### PROVEN

- the current official sources and trusted obligation Definition agree;
- 25/25 obligations are accounted for the bounded supplied-case profile;
- Declaration Semantics, Calculation Evidence and Completeness Receipt have
  different consumers and can be independently sealed;
- the projector's semantic value input can be materially smaller than the
  Resolved Package and current Semantic Input wrapper structure;
- target-independent business values can be separated from XML/PDF mechanics;
- the Resolved Package is best treated as a sealed audit envelope;
- no distributed event or universal relation object is declaration-mandatory.

### FALSIFIED

- Package direct DTO is the minimal declaration consumer contract;
- domain states, component IDs/hashes and scope manifests are declaration
  semantics;
- every Tax Model intermediate belongs in projector input;
- current exact-root component boundaries are themselves official meanings;
- XML/PDF locators belong in a target-independent contract.

### UNKNOWN

- complete legal methodologies for all 17 inactive obligations;
- universal taxpayer identity fallbacks beyond the bounded INN case;
- authoritative partial acquisition-commission allocation;
- which calculation intermediates should be persisted versus regenerated;
- live supplied-case closure in the current dirty checkout. This research did
  not rerun or repair the declaration pipeline.

## 12. Recommended minimal architecture

```text
SOURCE / USER / EXTERNAL FACTS
          |
          v
TRUSTED TAX METHODOLOGIES
          |
          +--> DECLARATION VALUES --------+
          |                               |
          +--> CALCULATION EVIDENCE       | release gate
                                          +--> MINIMAL SEMANTIC INPUT
TRUSTED DEFINITION                        |          |
          |                               |          v
          +--> COMPLETENESS RECEIPT ------+   PROJECTION DEFINITION
                                                     |
                                                     v
                                                 XML / PDF
```

One owner remains for each meaning. Existing methodology, Definition,
completeness and Projection owners are reused. No new ontology, event graph,
relation registry, parallel Declaration Model, SQL authority or implementation
roadmap is justified.

The stopper is intentionally outside the supplied-case result: universal
activation of inactive domains requires separate legal methodology research.
Until each such methodology is proven, the system must retain a terminal
blocker rather than fabricate a value or weaken completeness.

## KISS and stop

- every retained semantic field has an official declaration consumer;
- every derived value has one methodology/evidence owner;
- every inactive meaning lives in the completeness receipt, not an empty DTO;
- every target code or locator stays in the Projection Definition;
- no intermediate entity survives without a named consumer.

G5.39AB stops at conceptual contracts and safe evidence. It does not authorize
implementation, migration, activation, commit, push, PR, G5.40 or a dependent
GOAL.
