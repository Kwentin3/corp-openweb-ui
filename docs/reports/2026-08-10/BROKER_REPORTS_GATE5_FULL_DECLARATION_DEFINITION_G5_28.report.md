# Broker Reports Gate 5 Trusted Full Declaration Definition Authoring Proof — G5.28

Date: `2026-08-10`

Status: `G5.28_PARTIALLY_PROVEN`

Trusted publication: `REJECTED`

G5.29: `NOT_STARTED / NOT_ALLOWED`

Product/runtime activation: `NOT_STARTED`

## Verdict

Independent clean-context LLM смогла с первого фактического inference создать
маленький target-independent root manifest: 12 semantic domains, закрытые
applicability/evidence policies, exact official-evidence binding и честные
typed-component gaps. Candidate не зеркалирует форму/XSD, не содержит formula,
predicate, workflow, case-time resolver, XML или PDF и проходит весь закрытый
структурный validator.

Но итоговый ответ на финальный вопрос пока **нет**: candidate нельзя публиковать
как trusted Declaration Definition. Один официальный surface был accounted по
ID, но не по всем независимым semantic obligations. Приложение 3 одновременно
охватывает:

- factual/legal occurrence предпринимательской, адвокатской и частной практики;
- elective professional deductions по гражданско-правовым и авторским доходам.

Candidate объединил всё в
`independent_professional_activity_income` с одной
`typed_legal_classification` policy и сузил meaning до private-practice family.
Разные applicability/evidence owners потеряны. Это локальный дефект authoring
evidence atomization/semantic validator, а не необходимость нового runtime
primitive или rules engine.

```text
LLM candidate                     PASS
closed structural validation      PASS
14 official surface IDs mapped    PASS
semantic obligation coverage      FAIL: one localized mixed surface
trusted publication               FAIL CLOSED
```

Verdict: `PARTIALLY_PROVEN`.

## Delivered artifacts

- authoring/publication contract:
  [`BROKER_REPORTS_GATE5_FULL_DECLARATION_DEFINITION.v0.md`](../../stage2/contracts/BROKER_REPORTS_GATE5_FULL_DECLARATION_DEFINITION.v0.md);
- maintained factory/validator:
  [`gate5_full_declaration_definition.py`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate5_full_declaration_definition.py);
- frozen clean payload:
  [`gate5_full_declaration_definition_authoring.primary.v0.payload.json`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate5_full_declaration_definition_authoring.primary.v0.payload.json);
- exact unedited model candidate:
  [`gate5_full_declaration_definition_candidate.g528.json`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate5_full_declaration_definition_candidate.g528.json);
- hash-pinned review decision:
  [`gate5_full_declaration_definition_review.g528.json`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate5_full_declaration_definition_review.g528.json);
- pre-inference plan:
  [`BROKER_REPORTS_GATE5_FULL_DECLARATION_DEFINITION_G5_28.plan.safe.json`](./BROKER_REPORTS_GATE5_FULL_DECLARATION_DEFINITION_G5_28.plan.safe.json);
- exact safe trial record:
  [`BROKER_REPORTS_GATE5_FULL_DECLARATION_DEFINITION_G5_28.trial.safe.json`](./BROKER_REPORTS_GATE5_FULL_DECLARATION_DEFINITION_G5_28.trial.safe.json);
- deterministic validation audit:
  [`BROKER_REPORTS_GATE5_FULL_DECLARATION_DEFINITION_G5_28.validation.safe.json`](./BROKER_REPORTS_GATE5_FULL_DECLARATION_DEFINITION_G5_28.validation.safe.json);
- terminal tests:
  [`test_broker_reports_gate5_full_declaration_definition.py`](../../../services/broker-reports-gate1-proof/tests/test_broker_reports_gate5_full_declaration_definition.py).

## Exact clean trial record

### Frozen input

```text
payload bytes   21,536
payload SHA-256 e37001463b156034bee6c0843d30f9068b66d1dbdda96dd8265159bd81d5cf90
bias audit      passed, 0/20 forbidden prior-partition terms
preflight       passed, synthetic 14-surface terminal validation
```

The model did not see G5.27 domain IDs, candidate, roadmap, next gap or expected
validator errors. It saw official surface evidence, general granularity and
evidence-policy principles, Runtime Capability Contract v3 and exact current
bounded component inventory.

### Invocation

```text
provider/client     openai / codex-cli 0.147.0-alpha.6.5
model/profile       gpt-5.6-sol / high
sandbox             read-only
cwd                 new empty temporary directory
session             ephemeral
user config/rules   ignored / ignored
history             0 messages
provider retry      0
follow-up           0
repair              0
actual inferences   1
exit                0
duration            133.294 seconds
```

Two local command-shell launches failed before inference and are disclosed in
the safe trial record: the first omitted `exec` and closed stdin before payload
delivery; the second wrapper did not bind its arguments and never started
Codex. Neither accepted input, created a candidate or contacted a model. The
third process performed the one actual inference over the original frozen
bytes. This is transport history, not a provider retry.

### Frozen output

```text
candidate bytes   7,472
candidate SHA-256 3a5cf39a0a70b308c72e8f8688c6785618746a4634d2c41360d6ee5f871db639
strict JSON       one UTF-8 object
manual edits      0
reported tokens   13,605
```

The package candidate bytes are byte-for-byte equal to the CLI
`output-last-message` file.

## Official evidence

Live bytes were fetched again on `2026-08-10`; all four hashes matched the
frozen package:

| Official FNS source | Bytes | SHA-256 |
| --- | ---: | --- |
| [form PDF](https://www.nalog.gov.ru/html/sites/www.new.nalog.ru/files/about_fts/docs/16589324_1.pdf) | 438,785 | `d751043f63af1f0095a14228a65a3831acf47fcd82c397e2eb38b0f9f8dc9565` |
| [filling procedure DOCX](https://www.nalog.gov.ru/html/sites/www.new.nalog.ru/files/about_fts/docs/16589324_2.docx) | 106,008 | `7bc11cad8d0465c03c834c50c7832fb2edc7291d9b4b161ef5b2c6cabdcb0fdc` |
| [electronic format DOCX](https://www.nalog.gov.ru/html/sites/www.new.nalog.ru/files/about_fts/docs/16589324_3.docx) | 148,677 | `f5215c237a8af73dd7a251cee94a2e09aacd8540173fcde2904b4c311129e3c2` |
| [XSD 5.20.01](https://www.nalog.gov.ru/html/sites/www.new.nalog.ru/files/about_fts/docs/xsd/NO_NDFL3_1_033_00_05_20_01.xsd) | 178,427 | `083128322833dbafb29be0bf919e33b7b362956244b422d34dd554c99a1e4484` |

Exact combined evidence-package binding:

```text
package_id      fns-ru-3ndfl-2025-root-surfaces
package_version 2026-08-10.0
package_sha256  af3b42a5cf9e543275e6913b7e8645d3d4548efa786f9136cecd0f9a1039c62d
```

Target-specific locators occur only inside official evidence. Candidate
semantic IDs/meanings contain no target layout identity.

## Minimal schema / KISS result

The candidate repeats only information that cannot be reconstructed from the
trusted binding:

```text
Definition identity/version
official evidence package binding
root domains:
  stable ID
  semantic meaning
  ALWAYS|conditional
  one closed evidence policy
  expected typed component family + exact bounded contracts or missing
  allowed authority classes
  official evidence refs
```

Removed from the manifest:

- model/trial/review status;
- gap narrative and roadmap;
- XSD/PDF/form mappings;
- formulas, conditions, queries, fact paths and workflows;
- component schemas and copied capability descriptions;
- publication metadata.

Those meanings are either deterministic context, audit output or separate
repository review state. Removing more would lose identity, surface accounting,
human-assertion safety or typed-component completeness.

## Semantic Coverage Audit

Closed validation maps all 14 official surface records to a candidate domain:

| Official surface | Candidate owner | Audit |
| --- | --- | --- |
| filing/taxpayer/signer identity | `filing_instance_and_authorization` | structurally mapped; acceptable one ALWAYS root aggregate, package may retain separate subcomponents |
| declaration-level tax disposition | `declaration_budget_settlement` | complete root meaning |
| refund election/destination | `refundable_amount_disposal_election` | complete elective meaning |
| income-group base and settlement | `income_group_tax_base_and_settlement` | complete root meaning; current contract honestly bounded |
| Russian-source taxable income | `russian_source_taxable_income` | complete occurrence meaning |
| foreign-source taxable income/foreign tax | `foreign_source_taxable_income` | complete occurrence meaning; legal classification remains component concern |
| activity income plus professional deductions | `independent_professional_activity_income` | **semantic fail**: civil-contract/author professional deduction claim meaning omitted/misclassified |
| exempt income and limits | `tax_exempt_income` | complete typed-classification meaning |
| standard/social/investment/savings deductions | `standard_social_investment_and_savings_deduction_claims` | complete elective meaning |
| property/rights/vehicle/gift dispositions | `property_rights_vehicle_and_gift_dispositions` | complete, conservatively typed meaning |
| acquisition/construction/interest deductions | `property_acquisition_and_interest_deduction_claim` | complete elective meaning |
| financial instruments/digital/partnership | `financial_instruments_digital_assets_and_partnership_results` | complete root family; three current contracts honestly bounded |
| object-level property disposition calculation | `property_rights_vehicle_and_gift_dispositions` | stable semantic owner, not separate target domain |
| detailed social/investment calculation | `standard_social_investment_and_savings_deduction_claims` | stable semantic owner, not separate target domain |

```text
surface IDs mapped          14 / 14
surface IDs unmapped         0
semantic obligations lost    1 localized mixed-surface obligation
layout-only domains           0
```

This falsifies the validator assumption `surface ref present == all meanings
covered`. Official surfaces need semantic obligation atoms while still hiding
the expected domain partition.

## Domain Granularity Audit

| Candidate domain | Applicability / component coherence | Result |
| --- | --- | --- |
| `filing_instance_and_authorization` | all meanings are ALWAYS and can activate one filing-authority aggregate; identity/filing/signer may remain typed subcomponents | acceptable merge |
| `declaration_budget_settlement` | one ALWAYS declaration-settlement owner | pass |
| `refundable_amount_disposal_election` | one filing election, one payment/destination component family | pass |
| `income_group_tax_base_and_settlement` | one ALWAYS non-empty group-set aggregate | pass |
| `russian_source_taxable_income` | one occurrence question, one source-income family | pass |
| `foreign_source_taxable_income` | one occurrence boundary; jurisdiction/credit legality remains typed inside | pass |
| `independent_professional_activity_income` | combines activity classification and unrelated elective deduction claims | **too coarse / fail** |
| `tax_exempt_income` | one typed exemption-classification family | pass |
| `standard_social_investment_and_savings_deduction_claims` | one elective deduction aggregate with compatible policy | pass |
| `property_rights_vehicle_and_gift_dispositions` | one disposition family; target calculation is internal component semantics | pass |
| `property_acquisition_and_interest_deduction_claim` | one elective property-deduction family | pass |
| `financial_instruments_digital_assets_and_partnership_results` | one reviewed financial-operation result family; nested categories stay inside domain Definition | pass |

Candidate has 12 domains, not a giant taxonomy and not a 14-part form mirror.
The sole rejected domain is localized.

## Evidence-policy Audit

| Policy use | Candidate domains | Review |
| --- | --- | --- |
| `definition_mandatory` | filing/authorization, document settlement, income-group settlement | negative forbidden; pass |
| `factual_occurrence` | Russian and foreign source income | declarant attestation explicitly allowlisted but policy requires exact period/domain scope and no conflict; pass at Definition level |
| `typed_legal_classification` | activity, exemptions, property disposition, financial instruments | human denial is not authority; conservative and safe; activity domain fails for mixing an elective meaning |
| `elective_claim` | refund, deduction aggregate, property acquisition deduction | authenticated filing choice owns applicability; eligibility/value remains missing typed component; pass |
| `exhaustive_coverage` | none | absence is not falsely inferred; no requirement that every policy be used |

No conditional domain receives a default `user says no -> NOT_APPLICABLE` rule.
`user_case_evidence` appears only for factual inputs or filing elections;
published typed classification remains required for the legal-classification
domains.

## Typed component audit

Ten component families are honestly `missing`. Two cite existing bounded
contracts without promoting them to full-root coverage:

- `income_group_tax_base_and_settlement` cites
  `broker_reports_gate5_income_group_tax_base_model_v0` as
  `published_bounded`;
- `financial_instruments_digital_assets_and_partnership_results` cites the
  securities disposal, operation and tax-period category models as
  `published_bounded`.

No `Any`, invented contract or `published_exact` overclaim appears.

## Post-hoc G5.27 comparison

The clean model did not see the G5.27 inventory. Comparison happened only after
freezing the exact bytes.

| G5.27 result | G5.28 independent partition | Assessment |
| --- | --- | --- |
| filing + taxpayer + signer as three ALWAYS domains | one `filing_instance_and_authorization` domain | acceptable KISS merge at root scope; package components may remain separate |
| income-group settlement | same meaning | match |
| document tax disposition | same meaning | match |
| domestic/foreign income | two same meanings | match |
| business/private-practice occurrence | `independent_professional_activity_income` | partial match |
| other professional deductions as elective | absorbed into activity/classification domain | **material missed split** |
| exemptions | same typed meaning | match |
| broad elective deductions | same aggregate | match |
| property disposition | same family | match; G5.28 uses safer typed classification instead of negative attestation |
| property acquisition deduction | same elective family | match |
| securities/digital/partnership | same family | match; G5.28 uses safer typed classification |
| refund request | same elective family | match |

The inventories agree on the overall domain-level boundary. Exact equality was
not a criterion; official semantic coverage exposed the one unacceptable merge.

## Trusted-publication audit

The lifecycle is observable and fail-closed:

```text
candidate SHA-256
3a5cf39a0a70b308c72e8f8688c6785618746a4634d2c41360d6ee5f871db639
        ↓
deterministic status: eligible_for_review
        ↓
repository review: review_rejected
finding: official_surface_07_mixed_applicability_semantics_unaccounted
        ↓
Gate5TrustedFullDeclarationDefinitionAuthorityFactory.create
        ↓
gate5_full_declaration_definition_not_published
```

This proves that repository publication is sufficient as the cheap boundary
and that an LLM candidate cannot become authority merely by passing structural
validation. No Definition Service, DB or registry was created.

Trusted-publication verdict: **cannot be used as G5.29 authority**.

## Verification

### Passed

```text
ruff check gate5_full_declaration_definition.py test_broker_reports_gate5_full_declaration_definition.py
All checks passed

pytest full-definition + G5.16 + G5.21 + architecture
77 passed in 35.60s

isolated closed-world package-copy replay
candidate bytes 7472; domains 12; review rejected fail-closed

official live-byte re-download
4/4 exact SHA-256 matches
```

The tests exercise terminal outcomes without mocks: exact resource replay,
bias audit, one-object parse, identity/evidence tampering, duplicate domains,
unmapped surfaces, ALWAYS/conditional policy failure, contract overclaim,
target/executable rejection, historical G5.16 replay and rejected publication.

### Full-suite limitation

```text
python -m pytest -q
external runner timeout: exit 124 after 904 seconds
terminal pytest summary: absent
assertion failure: not observed
```

This is not reported as a green full suite and not reported as a test failure.
The related/architecture suite is terminal and green.

## No-drift and scope stops

- Runtime Capability Contract v3 and all prior resources are unchanged.
- The five primitive families are unchanged.
- Existing G5.16/G5.21 owners remain replayable; the new owner is only the
  distinct full-root authoring/review boundary.
- No provider client was added; Codex CLI remained an outer research harness.
- No case-time facts, resolver, questionnaire, filing context, Tax Model,
  Declaration Model, tax payable, full PROJECT, XML/PDF, DB, GUI or activation
  was implemented.
- Private/provider transcripts and temporary paths were not committed; only
  safe aggregate trial metadata and the allowed semantic candidate are stored.

## First blocker / next allowed boundary

The first blocker is not case-time resolution. It is an authoring-only revision
that:

1. decomposes each official surface into opaque semantic obligation atoms when
   the official text contains different applicability/evidence owners;
2. validates atom-to-domain bidirectional coverage, not only surface-ref
   presence;
3. still withholds the expected domain list;
4. runs a new independent single-inference/no-repair trial.

That work is outside G5.28 and was not implemented.

`G5.29` remains not allowed because there is no exact trusted full Declaration
Definition for it to consume.
