# Broker Reports Cross-Gate Domain Ownership v1

Status: `CURRENT SUPPORTING CONTRACT`

Updated: 2026-08-21 (ordinary-trade production-route conformance)

## Active ordinary-trade route override

For `ordinary_trade_exact_fingerprint_v1`, the source-semantic step is not the
historical Gate 3 model runtime. Its one-way ownership is:

| Domain | Sole owner | Input | Output | Must not own |
| --- | --- | --- | --- | --- |
| qualified schema/enum/amount-currency meaning | `OrdinaryTradeQualifiedMappingAuthorityFactory.create` | immutable package mapping and receipt registry | exact mapping v3 with receipt-covered amount-column to currency-column pairs | row values, broker profiles, fuzzy routing, unqualified or proximity binding, tax |
| source observation/runtime compilation | `OrdinaryTradeSemanticCompilerFactory.create` | active Canonical + exact mappings | Source Observations + deterministic runtime records | tax, relations, adjacency binding, inferred continuation, Canonical repair |
| current projection | `OrdinaryTradeProjectionFactory.create` | validated compiler output + trusted case context | one immutable current projection per active Canonical | meaning, latest-wins, stale reuse |
| Fact v2 admission | `Gate4OrdinaryTradeCandidateRuntimeFactory.create` | current ordinary projection | exact `Gate4FinancialCaseFactV2` list | Canonical read, classification, SQL, tax |
| deterministic tax consumption | unchanged Gate 5 deterministic source-fact runtime | Fact v2 + trusted methodology/context | assessment, calculations or typed blocker | Source Observation/Canonical/model reads or source-semantic repair |

The Gate 3/Gate 4 SQL rows below remain the exact deployment-rollback path for
ordinary trades and may remain active for separately contracted scopes. They
are not a fallback. `gate3_binding` in Fact v2 is a historical compatibility
field; on the active route it binds the ordinary projection artifact.

Goal: `G5.42`

Date: 2026-08-13

G5.50 authority refinement: the current
[Pipeline Architecture v1](./BROKER_REPORTS_PIPELINE_GATES.v1.md) is the sole
cross-domain navigation and ownership authority. This G5.42 document remains
supporting historical detail for the audited implementation and debt map; it
cannot define an alternative pipeline.

G5.43 addendum: the previously missing input-methodology publication is now
owned by [Gate 5 Evidence to Tax Methodology Bridge v1](./BROKER_REPORTS_GATE5_EVIDENCE_TAX_METHODOLOGY_BRIDGE.v1.md).
The G5.43 contract owns the evidence/method input details and exact remaining
legal gaps.

## Outcome boundary

This contract makes the current Gate 1-5 ownership and call direction explicit.
It does not renumber gates, replace a versioned DTO contract, publish tax law or
activate a product path. Pipeline Gates v1 remains the sole gate-placement
authority.

The audited core terminal is:

```text
CROSS_GATE_CORE_ARCHITECTURE_PROVEN
COMPATIBILITY_DEBT_REMAINS=[gate2_candidate_relation_compatibility,
published_income_source_and_residency_methodology]
```

The stronger `CROSS_GATE_CONTRACT_ARCHITECTURE_PROVEN` terminal is reserved
until the compatibility relation surface is retired and the missing legal
methodology is published through its existing trusted authority path.

## Non-negotiable semantic laws

- Source facts are observations; they are not tax facts.
- Normalization changes representation; it does not add legal interpretation.
- Source granularity is a ceiling. A consumer may aggregate explicit facts but
  may not invent a more detailed event or split an aggregate.
- Missing evidence remains missing. It is never converted into a relation,
  residence, income-source jurisdiction, expense allowability or a negative
  taxpayer-scope claim.
- LLM output is a proposal at a language, visual-document, external-law or
  human-dialog boundary. It never owns arithmetic, scope, persistence or final
  tax meaning.
- Projection validates and represents an already resolved semantic input. It
  does not calculate tax or decide applicability.
- An authenticated user may supply facts and elections. A user answer cannot
  become a tax conclusion.

## One-way ownership map

| Layer/domain | Single owner | Consumes | May produce | Must not own |
| --- | --- | --- | --- | --- |
| Gate 1 authenticated intake and custody | existing intake factories, `ArtifactStoreFactory` and `ArtifactResolver` | authenticated upload and access context | private source artifacts, format/routing evidence | canonical meaning, financial labels, tax facts |
| Gate 1 external document variability | production visual-provider factories and the Document Passport boundary | bounded page/crop/document projections | provider proposals plus terminal execution evidence | canonical promotion, calculations, hidden retries |
| Gate 2 canonical preservation | `FullSourceArtifactFactory`, `CanonicalNormalizerFactory.create`, `CanonicalArtifactStoreFactory.create`, `CanonicalReaderFactory.create` | Gate 1 source artifacts | immutable `CanonicalArtifactV1`, completeness/provenance evidence | financial or tax interpretation |
| Gate 3 financial label meaning (rollback/other explicit scopes) | published Financial Label Dictionary and Role Pack through the maintained Gate 3 factories | exact canonical projections | separately persisted, canonical-bound financial annotations | canonical mutation, tax methodology, calculation or fallback into active ordinary trade |
| Gate 3 metadata source facts | `Gate3MetadataSourceFactRuntimeFactory.create` | active canonical artifacts through `CanonicalReaderFactory.create` | explicitly labelled party, broker, account, period and identifier observations with provenance | Gate 4 reads, unlabelled role inference, income-source or residency meaning |
| Gate 4 normalized financial source facts | Gate 4 materialization factories | validated Gate 3 annotations and canonical bindings | independent atomic or aggregate `normalized_source_fact` observations | tax facts, event relations, reconciliation |
| Gate 4 case query | `Gate4FinancialCaseRuntimeFactory.create` | Gate 4 facts through the owned cache/repository boundary | immutable supplied-case fact views and counts | direct source/provider reads, tax decisions |
| Gate 5 Definition authority | `Gate5TrustedFullDeclarationDefinitionAuthorityFactory.create` | reviewed immutable definition resources | exact 25-obligation/domain/applicability catalog and hash binding | supplied-case applicability resolution, projection |
| Gate 5 evidence intake | `Gate5EvidenceIntakeRuntimeFactory.create` | strict Gate 3 metadata contract plus official Gate 4 case API | lossless contract composition and independent counts | source parsing, reclassification, relations, persistence |
| Gate 5 deterministic source consumption | `Gate5DeterministicSourceFactConsumptionRuntimeFactory.create` | exact independent Gate 4 observations plus published methodology and explicit scope-coverage evidence | available-evidence calculations, one-representation commission selection, acquisition-basis coverage and explicit insufficiency | proximity matching, persisted event pairs, reconciliation, aggregate splitting, tax eligibility |
| Gate 5 residency evidence interpretation | `Gate5ResidencyEvidenceRuntimeFactory.create` | authenticated typed presence/absence intervals and exception evidence | methodology-bound resident/non-resident classification or insufficiency | direct user tax-status authority, LLM classification, missing-day assumptions |
| Gate 5 tax methodology and Tax Models | trusted methodology authority plus the existing bounded Tax Model factories | declared methodology inputs and sufficient source facts | versioned deterministic Tax Models | LLM arithmetic, filing layout, unknown-law defaults |
| Gate 5 declaration scope | `gate5_declaration_scope_resolution.py`, exposing both `Gate5DeclarationScopeResolutionRuntimeFactory.create` and `Gate5DeclarationScopeActivationRuntimeFactory.create` | trusted Full Definition, exact assertions, typed components, supplied intent/evidence | one final/activation decision domain with explicit unresolved states | copied domain catalog, missing-as-not-applicable, universal questionnaire |
| Gate 5 human/document closure | `Gate5HumanGapClosureRuntimeFactory.create` | formal findings, active demands, trusted `ArtifactAccessContext`, externally owned taxpayer scope and tax period | owner-published request content/current-publication chain plus private publication-bound v1 facts; owner-visible conflict rejection and same-case cross-run validation | minting/authenticating taxpayer identity, case-derived taxpayer hash, timestamp/ref/list-order authority, raw-transaction dialog, user-authored tax conclusions, source/external facts or blocker closure by LLM |
| Gate 5 Evidence Demand | `Gate5EvidenceDemandRuntimeFactory.create` | active methodology/client requirements plus current Gate 4 facts | request meaning, roles, scope, cardinality and named consumers | Canonical/source reads, chunk/table strategy, provider calls, source proposal validation, Gate 4 projection |
| Gate 3 Evidence Demand public port | `Gate3EvidenceDemandPortFactory.create` | Gate 5 source-fact requests plus published Dictionary/Role Pack | accept an existing label/role contract or fail closed; bind accepted labels to the existing batch owner | source reads, provider calls, new labels/roles, Gate 4/Gate 5 logic |
| Gate 5 case preparation | `Gate5DeclarationPreparationRuntimeFactory.create` | evidence intake, review, scope and closure owners | readiness, proven target-independent values and exact remaining gaps | second scope/rule engine, target release while blocked |
| Declaration semantic input | `Gate5DeclarationSemanticInputRuntimeFactory.create` | fully resolved and sealed declaration components | target-independent released semantic input | calculation or target layout |
| XML/projection | existing declaration and full-target projection factories | released semantic input plus immutable projection definition | representational fragment/XML and mapping/XSD proof | Gate 4/source/provider reads, tax arithmetic, applicability |
| Product composition | existing OpenWebUI product factory and pipe/action entrypoints | only maintained factories above | authenticated request/result orchestration | duplicate parsers, readers, rules, persistence or hidden product activation |

Allowed direction is strictly:

```text
source -> canonical -> financial/metadata labels -> normalized source facts
       -> deterministic methodology/Tax Models -> declaration semantics
       -> representation-only projection
```

Human and external evidence re-enter at a typed boundary. They do not bypass
the preceding owner.

## LLM call-point audit

| Call point | Status and input | Output | Deterministic validator/owner | Why LLM is still justified |
| --- | --- | --- | --- | --- |
| `openwebui_actions/broker_reports_gate1_pipe.py` Document Passport completion | maintained product boundary; bounded document package and managed prompt | passport proposal | strict passport schema/validation; Document Passport remains owner | heterogeneous document language |
| `pdf_table_intake_runtime.py` | maintained bounded page image | table-region proposal only | coordinate/schema/completeness checks; table-intake owner | visual page geometry varies externally |
| `pdf_table_locator_provider.py` | maintained current page images | table boxes only | one provider factory plus coordinate contract; no cells or meanings | visual location varies externally |
| `pdf_dual_vlm_runtime.py`, `pdf_structural_repair_runtime.py` | research only; absent from the product bundle | historical proposals | standalone research validators only | retained for reproducibility, never fallback |
| `pdf_hybrid_shadow.py`, `pdf_hybrid_reliability_shadow.py`, experiment providers and view/repair shadows | research/compatibility only; absent from the product bundle | historical candidates and evidence | research validators; no product admission authority | comparative provider research only |
| `gate2_domain_runtime.py`, `gate2_source_fact_runtime.py` | maintained/compatibility source packets with sealed schemas | source-value/source-fact proposals | canonical request builder, provider adapters, source-fact validators and materializers | external broker vocabulary and table language |
| Gate 2 financial checksum/evidence/successor and V5/V6 qualification/diagnostic runners | qualification, shadow or bounded historical routes | semantic choices/evidence | published Semantic Pack, Choice, expansion, validation and materialization owners | model-quality evaluation over ambiguous source language |
| `gate3_bounded_labeling.py` | active exact canonical target projections plus published label view | sparse label proposal | dictionary-pinned schema and deterministic validation | financial wording classification |
| `gate3_role_labeling.py` | active labelled candidates plus published Role Pack | sparse role proposal | Role Pack/schema validator and annotation persistence owner | source wording does not deterministically expose roles |
| `gate5_single_input_human_loop.py` | inactive bounded one-question factual money interaction | question text or one factual money proposal | strict answer/value validation and supplemental-fact owner | natural-language human interaction only |
| Gate 5 authoring trials | frozen evidence; no live case-time call in current source | reviewed candidate payload | trusted repository publication and hash-pinned authority | historical definition/language research, not runtime tax authority |

There are no case-time source-semantic model calls anywhere in the active
ordinary-trade route. There are no document-semantic structured-model calls in Gate 4 or deterministic Gate 5
calculation, declaration scope/preparation, semantic-input or projection code.
The exact gate-file call-site inventory is frozen by
`test_broker_reports_cross_gate_contract_architecture.py`.

## Authority hierarchy

For any decision, use this order:

1. Pipeline Gates v1 for placement and gate status;
2. the current versioned contract/resource for semantic meaning;
3. the maintained factory for construction and execution;
4. a compatibility adapter only when it validates then delegates;
5. generated bundles as projections of maintained source;
6. dated research/reports as evidence, never live authority.

The Full Declaration Definition owns domain and obligation inventory. Scope
resolution owns one supplied-case decision over that inventory. Published tax
methodology owns calculation/classification. Projection definitions own target
mapping only.

## Relations and reconciliation

There is no current Gate 4 or Gate 5 financial-event relation owner. The former
Gate 5 related-securities runtime is absent. Gate 4 stores independent
observations, including independent detail and aggregate observations. A Gate
5 consumer can calculate only where exact methodology inputs are independently
sufficient; otherwise it emits an insufficiency terminal.

Gate 2 still contains same-row candidate-relation contracts used by a
default-off compatibility manifest. They cannot enter Gate 4 or Gate 5 and do
not establish purchase/disposal, fee, withholding or cross-document event
identity.

## Research scars and compatibility debt

| Item | Consumer | Risk | Why retained | Removal condition |
| --- | --- | --- | --- | --- |
| Gate 2 candidate relation set and `gate3_context_manifest` | historical Gate 2 domain artifacts/tests; configuration defaults off | names can be mistaken for current financial-event authority | persisted compatibility and replay evidence | prove no retained artifacts/callers require it, migrate readers, then remove in a separately authorized goal |
| V5/V6, successor, checksum and provider experiment runners | qualification/replay suites and historical reports | broad surface and stale naming | reproducibility of accepted/rejected research; no current authority | remove only with an evidence-retention/migration decision |
| older `gate2_*` names around pre-renumbered financial semantics | compatibility imports and generated bundles | naming can imply wrong gate placement | renaming is higher risk than an explicit authority map | versioned consumer migration plus bundle compatibility release |
| declaration-input methodology follow-through | real declaration preparation | source/user inputs and three reviewed legal details remain insufficient even though the rule/input contract is now published | the G5.43 contract is hash-pinned and bound to all active demands; no user conclusion is accepted | close only the exact `SOURCE`, `CONTRACT`, `METHODOLOGY` or `USER/CASE` rows in the G5.43 Gap Register |

## Enforced architecture tests

`tests/test_broker_reports_cross_gate_contract_architecture.py` proves:

- the exact one-owner gate map;
- Gate 3 metadata cannot import/read Gate 4 or Gate 5;
- Gate 5 evidence intake composes the Gate 3 and Gate 4 contracts only;
- declaration scope has one module owner and no copied domain catalog;
- user facts exclude tax conclusions;
- every gate-level structured-model call site is explicit and Gate 4 has none;
- no relation contract reaches Gate 4/Gate 5;
- Decimal use in projection is representation validation only.

## Non-goals

No TaxCase database, generic relation/risk/workflow engine, universal
questionnaire, new persistence platform, speculative legal rule, upstream data
repair, transaction reconciliation, automatic product activation or new target
format is introduced by G5.42.
