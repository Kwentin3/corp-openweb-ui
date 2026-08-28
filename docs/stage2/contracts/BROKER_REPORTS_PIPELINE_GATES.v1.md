# Broker Reports Pipeline Architecture v1

Status: `CURRENT`

Classification: `CURRENT AUTHORITY`

Updated: 2026-08-28 (independently reviewed automatic semantic mapping)

```text
CURRENT_PIPELINE_AUTHORITY = ONE
CanonicalArtifactV1 = OUTPUT OF GATE 2
GATE1_STATUS = CLOSED
GATE2_STATUS = CLOSED
GATE3_STATUS = CLOSED
GATE3_PRODUCT_STATUS = RETAINED_DEPLOYMENT_ROLLBACK_ONLY
GATE3_TERMINAL_PROOF = G3.C5_CLOSED
GATE4_STATUS = CLOSED
G4.1_CLOSED = CONTRACT_PROVEN
G4.6_CLOSED = NO_NEW_READ_LAYER_REQUIRED
GATE5_PRODUCT_STATUS = CURRENT_FAIL_CLOSED
ACTIVE_ORDINARY_TRADE_ROUTE = ordinary_trade_automatic_semantic_mapping_v1
GATE3_EXECUTION_IN_ACTIVE_ORDINARY_TRADE_ROUTE = DISABLED
LEGACY_SEMANTIC_FALLBACK = FORBIDDEN
GATE3_BINDING_FIELD = COMPATIBILITY_FIELD_ONLY
```

This is the one short navigation authority for Broker Reports ownership and
gate direction. Start here. Versioned contracts own exact DTO meaning; the
[Architecture Authorities index](./BROKER_REPORTS_ARCHITECTURE_AUTHORITIES.md)
maps maintained factories; dated reports are evidence only.

The current ordinary-security-trade product composition is exactly:

```text
broker_reports_gate1_pipe
  -> PdfTableIntakeRuntimeFactory.create_for_openwebui
  -> Gate1Normalizer / persist_gate1_result
  -> immutable active CanonicalArtifactV1
  -> OrdinaryTradeProductionRuntimeFactory.create
  -> exact qualified mapping fast path OR OrdinaryTradeSemanticMappingFactory.create
  -> same-Canonical independent semantic review for every risky mapper terminal
  -> OrdinaryTradeMappingCaseFactory.create; user confirmation only for a
     reviewer-certified irreducible ambiguity
  -> OrdinaryTradeQualifiedMappingAuthorityFactory.create
  -> OrdinaryTradeSemanticCompilerFactory.create
  -> immutable Source Observations + deterministic runtime records
  -> Gate4OrdinaryTradeCandidateRuntimeFactory.create
  -> Gate4FinancialCaseFactV2 compatibility port
  -> unchanged deterministic Gate 5 source-fact consumer
```

`NdflWorkflowFactory.create().run_product_path`, `FinancialAnnotationsV2`, the
Gate 3 type/role model passes and `Gate4FinancialCaseRuntimeFactory.create`
remain readable deployment-rollback compatibility. They are not called when
`ordinary_trade_candidate_enabled=true`; production release additionally pins
`ndfl_gate3_enabled=false`. They are not a fallback for an unknown schema,
missing Canonical, incomplete row or downstream evidence blocker.

The retired dual-VLM, semantic-migration, structural-repair, hybrid-shadow and
synthetic end-to-end XML runtimes are absent from the product bundle and are
not fallbacks. A real case may terminate before release with an exact evidence
or methodology blocker.

## Stage-aware composition law

**Source world.** Gate 1 owns source identity and custody. Gate 2 produces a
faithful Canonical and may change form, not meaning. In the active ordinary-
trade route, one frozen exact-schema mapping plus its qualification receipt, or
one mapper proposal plus one same-Canonical independent semantic review, and one
deterministic compiler assign only qualified source meaning and preserve
every literal and cell reference. The historical Gate 3 model path performs the analogous source-
semantic responsibility only when explicitly selected as deployment rollback.
Gate 4 publishes only contract-valid normalized source facts. Visual metadata
follows the separate supporting route
`visual region -> VLM -> faithful neutral Markdown -> best-effort metadata`.
Metadata is never financial or tax authority and cannot admit, reject, group or
delete financial facts. Source content without a named consumer remains in the
faithful Canonical/Markdown representation; it is not coerced into the nearest
ontology meaning.

**Development visual qualification.** When a downstream result is implausible
or source presence is unclear, inspect the original document visually, compare
it with Canonical and the downstream representations, and locate the first
divergence before changing a parser, prompt, normalizer or consumer. This is a
development/test oracle only: a visual human/agent inspection is never a
production dependency or runtime authority, and its observations must never be
copied into production facts. Fix the first wrong production owner and replay
the ordinary machine path.

**Formal world.** After Gate 4, deterministic consumers receive only Gate 4
facts, factual USER/CASE facts, authoritative EXTERNAL facts and versioned
methodology. Every missing input belongs to a named consumer, becomes required
at one earliest stage and blocks only the smallest unit that actually depends
on it. Declaration Semantics owns what is declared; Release owns permission to
release a complete declaration; Projection only represents released meaning.

```text
REQUIREMENT_NOT_GLOBAL_BLOCKER = FROZEN
CLOSURE_ORDER_NOT_DEPENDENCY_ORDER = FROZEN
BLOCKER_SCOPE_REQUIRED = NAMED_CONSUMER + EARLIEST_STAGE + MINIMAL_UNIT
```

An obligation required for a complete declaration is not automatically an
input to earlier calculation. The ordering of `USER_FACT`,
`ADDITIONAL_DOCUMENT` and `METHODOLOGY_RESEARCH` actions is workflow/display
ordering, not a dependency graph. Use `BLOCKER` only with an explicit scope;
otherwise use `EVIDENCE_GAP`.

### Stage / consumer map

| Input or gap | Named consumer | Earliest required stage | Minimal blocking scope | Route when missing |
| --- | --- | --- | --- | --- |
| acquisition basis | `Gate5DeterministicSourceFactConsumptionRuntimeFactory.create` | Gate 5 calculation | dependent exact `(asset, currency)` group and unresolved disposal suffix | evidence-horizon review; request authoritative acquisition evidence only after distinguishing absence from upstream loss |
| residency evidence | `Gate5ResidencyEvidenceRuntimeFactory.create.classify` and methodology that consumes period status | Gate 5 methodology | residency-dependent tax classification and its downstream semantics | Human Adapter factual intervals -> reviewed deterministic methodology; never accept a user/LLM tax conclusion |
| `taxpayer_identity_confirmed` | `Gate5DeclarationPreparationRuntimeFactory.create` for `obl_taxpayer_identity_and_period_status`, then the filing/party component | Declaration Preparation / declaration identity | taxpayer-period identity demand and later release | authenticated USER/CASE fact; does not block Gate 4 or source-level FIFO |
| `signer_and_representation` | filing/party identity component and Release | Declaration Semantics / Release | signer obligation and filing release | authenticated USER/CASE fact; never a financial-calculation input without a new named contract |
| `filing_instance_identity` | filing/party identity component, Release and target context | Declaration Semantics / Release | filing-instance obligation, release and projection context | authenticated USER/CASE fact; never a financial-calculation input |
| supporting account/contract/broker/period metadata | evidence review, scope or UI only where explicitly named | supporting path | supporting consumer only | warning/review; never filter or mutate financial facts |
| source fact exists, required role missing | Gate 3 -> Gate 4 source-fact production owners | source-fact production | one source fact | `EXISTING_EVIDENCE` upstream owner review; do not ask the user or request another document until source presence is classified |
| source value exists, decimal normalization fails | `Gate4FinancialCaseMaterializerFactory.create` | source-fact production | one source value/fact | normalization-owner review; never ask the user to restate the value |
| non-RUB declaration field has a sub-kopeck result | `Gate5TrustedMethodologyAuthorityFactory.create` | Gate 5 methodology | only the dependent declaration field | exact Decimal and no intermediate rounding; stop at `LEGAL_INTERPRETATION_REQUIRED` until the non-tax tie rule is officially resolved |
| unmapped source content | no machine consumer yet | none | none | retain faithfully in Canonical/neutral Markdown; add no runtime type without a consumer |

### Consumer-first source-meaning admission

```text
SOURCE_MEANING_ADMISSION = NAMED_DOWNSTREAM_CONSUMER + REQUIRED_FACTUAL_DISTINCTION
TAX_CRITICAL_SOURCE_MEANING_ADMISSION = SOURCE_MEANING_ADMISSION + VERSIONED_METHODOLOGY_INPUT
NO_NAMED_CONSUMER = SAME_CANONICAL_PROOF_OF_SAFE_NON_FINANCIAL_AUXILIARY
```

`NO_NAMED_CONSUMER` is not inferred from the absence of a complete supported
trade mapping. Unknown income, expense, tax, cash movement, unsupported
operation, incomplete transaction or damaged financial row remains relevant
and blocks atomic fact publication.

Before adding a source type, field or state, name its current owner and
contract, the exact downstream consumer, why that consumer needs the factual
distinction, what reviewed methodology derives from it and why faithful
unmapped retention is insufficient. A report label such as `US Tax credit`
proves neither a tax reversal nor credit/refund treatment. Gate 3 may preserve
the broker-stated observation, but it must not publish a tax conclusion; Gate 4
may normalize only an admitted source meaning; Gate 5 may derive a declaration
consequence only from an explicit versioned methodology input. For a
tax-critical distinction, without that input contract stop at
`METHODOLOGY_INPUT_CONTRACT_GAP_PROVEN`; do not infer a
new source ontology from wording or proximity. G5.x reports remain evidence of
the observed gap, never authority for admission.

### Current Gate 5 authority

| Meaning | Single current authority | Current decision |
| --- | --- | --- |
| source-fact consumption and FIFO | `ru-ndfl-securities-source-fact-consumption-proof@2026.7-current-authority` through `Gate5TrustedMethodologyAuthorityFactory.create` | exact Decimal; FIFO by acquisition date; no inferred relations; no rounding before the declaration-field boundary |
| 2025 declaration inputs | `ru-3ndfl-2025-declaration-input-contract@2026.3-current-authority` through the same authority factory | official date/rate rules, field scale, declarant-category classification, foreign-tax evidence conditions and explicit legal stops |
| current case assembly | `Gate5RealTaxCaseAssemblyRuntimeFactory.create` | all 25 Definition demands; each active unresolved demand has one exact gap-owner class |
| human or document action | `Gate5HumanGapClosureRuntimeFactory.create` | only real source evidence and user/case facts may become user-facing requests |

The five and only five unresolved-owner classes are
`REAL_SOURCE_EVIDENCE_MISSING`, `USER_CASE_FACT_MISSING`,
`EXTERNAL_AUTHORITATIVE_FACT_MISSING`, `METHODOLOGY_RULE_MISSING` and
`INTERNAL_CONTRACT_OR_PIPELINE_DEFECT`. An internal defect is never a user
request. Historical methodology resources are not selected by current code
and are not fallbacks.

The current legal stops are deliberately narrow:

- Articles 214.1(10), 214.1(12) and 214.1(13) prove eligible documented direct
  commissions, category-level allocation of non-direct expenses and FIFO.
  They do not prove how one acquisition commission is allocated when only part
  of that acquired lot is disposed: `LEGAL_INTERPRETATION_REQUIRED`.
- Article 210(5) proves the CBR-rate date. The 2025 3-NDFL order fixes monetary
  field scale and final whole-ruble tax rounding. It does not state the
  sub-kopeck tie rule for a non-tax monetary field:
  `LEGAL_INTERPRETATION_REQUIRED` at that exact output boundary.
- Under Article 232, a broker report always proves only its literal source
  assertion. For a foreign-tax credit it is sufficient by itself only when its
  issuer is the income payment source and it contains the required monthly
  income/tax details, with the required copy and notarized translation.

### Evidence horizon and calculation granularity

A disposal inside the supplied period with acquisition history outside the
supplied document window is
`EVIDENCE_HORIZON_ACQUISITION_BASIS_GAP`. It is not by itself a broken
transaction, parser defect or source defect. The system must not invent a
purchase-sale relation, zero-cost basis or symmetric short-position history.

The current securities calculation unit is the exact methodology group
`(asset, currency)`. FIFO is independent inside each group. An incomplete group
cannot erase a successfully calculated independent group. A whole declaration
domain may remain incomplete for Release while already proven group
calculations remain present in the partial target-independent draft.

Fact readiness and group readiness are different counts. For example,
`80 ready / 16 incomplete / 0 calculations` does not prove global suppression:
zero calculations is correct when none of the ready facts compose one complete
disposal group under the current methodology.

### Source-has-it routing

Gate 5 must not read Canonical to settle source presence. The source owner
performs that review through the existing public port. Until it does, a
role-incomplete fact routes to `EXISTING_EVIDENCE` owner review, not directly to
`USER_FACT` or `ADDITIONAL_DOCUMENT`. A decimal-invalid fact already contains a
source value and therefore routes directly to the normalization owner. Only a
proven source/evidence-horizon absence may become an additional-document
request.

The normative route names reserved for the bounded remediation are
`UPSTREAM_SOURCE_FACT_PRODUCTION_REVIEW` and
`NORMALIZATION_OWNER_REVIEW`; both have
`user_or_additional_document_allowed=false`.
G5.78 carries these routes through the existing finding/action contracts and
separates them from user-facing actions. Unknown ownership fails closed as
`OWNER_UNRESOLVED`; it never defaults to the user. G5.78 does not implement the
13 role repairs or 3 decimal repairs observed in the G5.76 evidence set.

### Cold-agent composition exam

1. Missing signer: identify the filing/release consumer; do not block financial calculation.
2. First action is `USER_FACT`: it is not automatically the first dependency.
3. Disposal is in 2025 and acquisition may predate supplied reports: classify an evidence-horizon gap, not a parser defect.
4. Literal exists but a role did not reach Gate 4: route upstream; do not request a new document.
5. Decimal literal exists but normalization rejects it: route to the normalization owner; do not ask the user for the number.
6. Account metadata is wrong: retain financial facts; record supporting review evidence.
7. Signer is missing: FIFO may run when its contract does not consume signer.
8. Residency is not an XML-only field: it is factual evidence plus deterministic methodology where tax meaning depends on status.
9. Some security facts are incomplete: block the whole domain only when a documented dependency requires it; preserve independent calculations.
10. Projector lacks a value: it must not calculate; return to the semantic owner.

The expected result is `COLD_AGENT_ANTI_DRIFT_10_OF_10`. No dated G5.x report
is needed to answer these questions.

## Pipeline map

Gate numbers describe responsibility boundaries, not a mandatory sequence of
module names. The active ordinary-trade route satisfies the source-semantic
responsibility without executing the historically named Gate 3 runtime:

```text
ACTIVE ORDINARY SECURITY TRADES

PDF -> normalization -> immutable Canonical
    -> exact mapping + matching qualification receipt
    -> Source Observations
    -> deterministic runtime records
    -> Gate 4 Fact v2 compatibility adapter
    -> deterministic Gate 5

UNKNOWN / INCOMPLETE

Canonical row -> RELEVANT_UNMAPPED -> STOP
missing Canonical -> ordinary_trade_canonical_evidence_missing -> STOP
```

The broader responsibility vocabulary remains:

```text
SOURCE DOCUMENT
  -> Gate 1: source custody / identity
  -> Gate 2: faithful machine-readable Canonical
  -> Adaptive Context: whole or structurally bounded source context
  -> Gate 3: LLM source-semantic labeling
  -> Gate 4: validated normalized source facts
  ================================================================
                         DETERMINISTIC BOUNDARY
  ================================================================
  -> Gate 5: versioned tax methodology + deterministic calculation
  -> Declaration Semantics: target-independent declaration meaning
  -> Release: evidence/completeness permission
  -> Projection: representation-only target mapping
  -> XML / PDF
```

### Source-route quick map

```text
ORDINARY SECURITY TRADES — ACTIVE PRODUCT/NORMATIVE
PDF -> Gate 1 -> CanonicalArtifactV1
    -> OrdinaryTradeProductionRuntimeFactory.create
    -> exact qualified Source Observations / runtime records
    -> Gate4OrdinaryTradeCandidateRuntimeFactory.create
    -> deterministic Gate 5

HISTORICAL GATE 3 ROUTE — DEPLOYMENT ROLLBACK ONLY
CanonicalArtifactV1 -> Adaptive Context
    -> Gate3ChunkBatchLabelingFactory.create
    -> Gate4FinancialCaseRuntimeFactory.create
    -> Gate 5

VISUAL METADATA — SINGLE SUPPORTING CANDIDATE, NOT PRODUCT-ACTIVE
broker-neutral visual region
    -> existing VLM provider owner
    -> faithful neutral Markdown
    -> Gate3LlmMetadataAdapterFactory.create
    -> best-effort supporting metadata
```

Markdown is the contract seam between the visual and semantic domains. The
transcriber may change form but must preserve source words, labels, values,
table/line relationships and value boundaries. It must not emit G5.60 role
names, tax meaning or broker-specific normalization. The semantic metadata
adapter may propose supporting facts only; it is not financial admission,
calculation or tax-scope authority.

The candidate metadata route is not product-active because the maintained
region detector is table-only and explicitly excludes document identity
headers. No broker-neutral automatic metadata-region selector exists yet.
Manual crops remain research evidence, not a runtime default. Do not add
broker/page/percentage rules: stop with
`METADATA_REGION_SELECTION_GENERALIZATION_GAP_LOCALIZED`.

PDF data-table normalization has one separate source-bound route. The VLM
locates each visible table with a native normalized `box_2d`; deterministic
code projects the box to PDF points; pdfplumber reconstructs structure and
reads every literal from the original PDF; the existing normalizer validates
and publishes. The model does not transcribe values, invent structure, choose
parser settings or publish canonical data. A missing or ambiguous region fails
closed with `pdf_table_normalization_incomplete`; there is no semantic-VLM
transcription fallback. Exact rules are in
[PDF Source-Bound Table Normalization v1](./BROKER_REPORTS_PDF_SOURCE_BOUND_TABLE_NORMALIZATION.v1.md).

| Entrypoint / artifact | Status | Authority boundary |
| --- | --- | --- |
| `OrdinaryTradeProductionRuntimeFactory.create` | `PRODUCT/NORMATIVE` | sole active ordinary-trade and bounded declaration-product composition root; current Canonical/source owner + current Human Facts + pinned methodology -> `INPUT_REQUIRED | DRAFT_READY | DECLARATION_XML_READY`; deterministic Gate 5 and private XML delivery, zero FNS transport |
| `OrdinaryTradeQualifiedMappingAuthorityFactory.create` | `PRODUCT/NORMATIVE` | frozen exact schema/enum meaning plus explicit amount-column to currency-column bindings; no row values, broker/year/filename routing or fuzzy reuse |
| `OrdinaryTradeSemanticCompilerFactory.create` | `PRODUCT/NORMATIVE` | Canonical-bound Source Observations and deterministic runtime records; executes qualified bindings and never derives them from adjacency; unknown content remains unmapped |
| `Gate4OrdinaryTradeCandidateRuntimeFactory.create` | `PRODUCT/NORMATIVE` | validates candidate projection into the existing Fact v2 boundary without SQL or Gate 3 execution |
| `NdflWorkflowFactory.create().run_product_path` | `DEPLOYMENT ROLLBACK ONLY` | historical Gate 2 -> Gate 3 financial execution; never semantic fallback |
| `Gate3ChunkBatchLabelingFactory.create` | `DEPLOYMENT ROLLBACK ONLY` | historical model-based financial semantic extraction |
| `Gate4FinancialCaseRuntimeFactory.create` | `DEPLOYMENT ROLLBACK ONLY FOR ORDINARY TRADE` | historical Gate 3-backed normalized facts and case reads |
| `PdfTableIntakeRuntimeFactory.create_for_openwebui` | `PRODUCT/NORMATIVE` | one full-page call; table boxes only; no source literals or structure |
| `PdfTableLocatorProjectionFactory.create` | `PRODUCT/NORMATIVE` | the only native `box_2d` to PDF-point projection owner |
| `PdfDualVlmRuntimeFactory.create_for_openwebui` | `HISTORICAL/INACTIVE` | old value-transcription route; no new writes or fallback |
| `PdfGridExperimentProviderFactory.create_for_openwebui` | `LEGACY COMPATIBILITY` | historically named provider transport behind maintained owners; never a public semantic owner |
| `Gate3LlmMetadataAdapterFactory.create` | `SUPPORTING` | best-effort metadata proposal, no tax/financial authority |
| `Gate3MetadataSourceFactRuntimeFactory.create` | `SUPPORTING` | current supporting metadata publication/read boundary |
| Gate 1 document passport stage | `LEGACY COMPATIBILITY` | optional pre-Gate2 document review; not G5.60 or tax authority |
| G5.61–G5.73 live/qualification scripts | `PROOF/RESEARCH ONLY` | retained evidence; never imported or selected by normative runtime |

Executable laws:

1. Low-criticality metadata cannot control financial fact admission.
2. Metadata adapters cannot become tax authority.
3. Gate 4 cannot depend on metadata-classifier output.
4. Product modules cannot import G5.61–G5.73 live/benchmark harnesses.
5. Visual Markdown transcription cannot assign machine metadata roles.

Cold-agent navigation answers are intentionally literal:

- Ordinary security-trade fact from broker PDF: `Canonical -> exact qualified mapping -> Source Observation/runtime record -> Gate 4 Fact v2 adapter`. Current Gate 3 is not executed.
- Visual document header: `visual region -> existing VLM -> faithful Markdown -> metadata adapter`; if a general region is unavailable, stop rather than add a broker rule.
- Metadata account mismatch: `NO`; retain financial facts and record supporting evidence/review uncertainty.

If a new document exposes a defect, locate the existing owner first. Do not
create a parallel reader. G5.75 does not authorize further ingestion research;
the next allowed goal after this bounded consolidation is a full current-case
end-to-end replay.

The short questions are normative:

| Boundary | One question |
| --- | --- |
| Gate 1 | What did we receive? |
| Gate 2 | How do we represent the source faithfully? |
| Adaptive Context | What is the smallest sufficient source context? |
| Gate 3 | What did the source say? |
| Gate 4 | What standardized facts can we prove? |
| Gate 5 | What follows from those facts under tax rules? |
| Declaration Semantics | What exactly will we declare? |
| Release | Are we allowed to release it? |
| Projection | How do we write it into the target format? |

Normalization changes form, not meaning. Source granularity is a semantic
ceiling. After Gate 4 the source-world question ends and deterministic
rule/tax reasoning begins.

## Domain contract cards

### Gate 1 — Source custody

- **PURPOSE:** establish what was supplied and who may access it.
- **INPUT:** authenticated source bytes and access context.
- **OWNS / MAY ASSERT:** source/document identity, custody, hashes, provenance
  root, storage and routing facts.
- **MUST NOT ASSERT:** financial labels, tax or declaration meaning.
- **OUTPUT:** trusted source identity plus access/routing receipt.
- **PUBLIC PORT:** existing intake and `ArtifactStoreFactory.create` /
  `ArtifactResolver` boundaries.
- **PREVIOUS / NEXT:** external source -> Gate 2.
- **FAILURE MODE:** deny access or fail closed without inventing source state.

### Gate 2 — Canonical source representation

- **PURPOSE:** faithfully represent the source for machine consumption.
- **INPUT:** exact Gate 1 source identity plus trusted access context.
- **OWNS / MAY ASSERT:** document/page/section/table/row/cell/text structure,
  source refs, layout and immutable Canonical identity.
- **MUST NOT ASSERT:** deductible expense, income-source jurisdiction,
  financial-event relations or any tax conclusion.
- **OUTPUT:** validated immutable `CanonicalArtifactV1`.
- **PUBLIC PORT:** `CanonicalReaderFactory.create`; storage and parser internals
  are not consumer ports.
- Product-wide canonical reads remain off; only explicitly contracted product
  paths may consume a validated projection.
- **PREVIOUS / NEXT:** Gate 1 -> Adaptive Context.
- **FAILURE MODE:** explicit completeness/validation failure; no zero-node
  activation for a non-empty document.

The global product canonical
read valve remains disabled.

### Adaptive Context Boundary

- **PURPOSE:** transport Canonical structure into a sufficient bounded semantic
  context without creating business meaning.
- **INPUT:** exact active Canonical projection.
- **OWNS / MAY ASSERT:** whole-artifact versus structural partition decision,
  ancestor/header/row/cell/provenance preservation and budget accounting.
- **MUST NOT ASSERT:** a chunk is a financial event or tax object; no new label,
  role or relation meaning.
- **OUTPUT:** one whole context or ordered bounded structural contexts.
- **PUBLIC PORT:** `Gate3StructuralChunkFactory.create`.
- **ACTIVE STATUS:** not traversed by the active exact-qualified ordinary-trade
  route; retained for the historical Gate 3 rollback path and other explicitly
  contracted consumers.
- **PREVIOUS / NEXT:** Gate 2 -> Gate 3 on that compatibility path.
- **FAILURE MODE:** fail closed when sufficient structure cannot fit; do not
  fragment more than necessary or merge more than allowed.

### Gate 3 — Source semantic adapter

- **PURPOSE:** answer only what the source said.
- **INPUT:** whole/bounded source context + published Dictionary + Role Pack +
  optional Evidence Demand hint.
- **OWNS / MAY ASSERT:** source-semantic label proposals and source-bound roles
  over published meaning.
- **MUST NOT ASSERT:** tax, deductibility, residency, income-source
  classification, inferred economic relations or reconciliation.
- **OUTPUT:** validated, Canonical-bound `FinancialAnnotationsV2` proposals and
  immutable current-view sidecars; sparse proposal omission is not an absence
  claim, and demand-scoped recovery cannot delete unrelated validated facts.
- **PUBLIC PORT:** `Gate3ChunkBatchLabelingFactory.create`; consumer demand
  enters only through `Gate3EvidenceDemandPortFactory.create`.
- **ACTIVE STATUS:** not executed by `ordinary_trade_automatic_semantic_mapping_v1`.
  The active route fulfills the source-semantic responsibility through the
  qualified mapping and deterministic compiler above; this is not a second
  model path or fallback.
- **NORMATIVE CONTRACT:**
  [Gate 3 Minimal Labeling v1](./BROKER_REPORTS_GATE3_MINIMAL_LABELING.v1.md).
- **PREVIOUS / NEXT:** Adaptive Context -> Gate 4.
- **FAILURE MODE:** explicit missing/invalid/role-incomplete state; no retry,
  repair, fallback taxonomy or second reader.

### Gate 4 — Normalized source facts

- **PURPOSE:** publish the strict standardized facts that source evidence proves.
- **INPUT:** either validated historical Gate 3 semantics with exact Canonical
  bindings, or validated ordinary-trade runtime records with exact Source
  Observation and Canonical-cell lineage.
- **OWNS / MAY ASSERT:** typed independent `normalized_source_fact`
  observations, roles, provenance and technical completeness state.
- **MUST NOT ASSERT:** tax meaning, relations, reconciliation or calculation;
  no document-semantic LLM authority.
- **OUTPUT:** `Gate4FinancialCaseFactV2` and immutable case views.
- **PUBLIC PORT:** `Gate4OrdinaryTradeCandidateRuntimeFactory.create` on the
  active ordinary route; `Gate4FinancialCaseRuntimeFactory.create` on the
  historical rollback route. Both expose Fact v2; SQL exists only on the
  historical route and remains an internal, rebuildable non-authority.
- **PREVIOUS / NEXT:** qualified source-semantic producer -> Gate 5.
- **FAILURE MODE:** missing/stale/role-incomplete facts remain explicit.

### Gate 5 — Tax methodology and deterministic calculation

- **PURPOSE:** determine what follows from proven facts under reviewed rules.
- **INPUT:** Gate 4 facts + typed user/case facts + typed external reference
  facts + versioned reviewed methodology.
- **OWNS / MAY ASSERT:** evidence requirements, tax classification, SELECT /
  FILTER / GROUP / ORDER / FIFO / SUM / FX / APPLY RULE, tax/declaration values
  and explicit insufficiency.
- **MUST NOT ASSERT:** source text meaning; it must not read PDF/Canonical,
  choose chunks, call a document provider, reconstruct tables or create source
  facts from text.
- **OUTPUT:** methodology-bound deterministic Tax Models/results and Evidence
  Demand requests.
- **PUBLIC PORT:** the active ordinary-trade composition injects only
  `Gate4OrdinaryTradeCandidateRuntimeFactory.create` into the unchanged
  deterministic source-fact consumer. The historical route consumes
  `Gate4FinancialCaseRuntimeFactory.create`. Gate 5 receives Fact v2 in both
  cases and must not inspect which upstream producer supplied it. Historical
  Evidence Demand routing through the Gate 3 port is not active on the ordinary
  route.
- **PREVIOUS / NEXT:** Gate 4 + typed side facts/methodology -> Declaration
  Semantics.
- **FAILURE MODE:** fail closed when methodology inputs or evidence are missing.

### Human Adapter

- **PURPOSE:** translate human factual circumstances into typed evidence.
- **INPUT:** one explicit factual requirement and authenticated human answer.
- **OWNS / MAY ASSERT:** typed intervals, presence/absence circumstances,
  identities and elections that the user actually supplied.
- **MUST NOT ASSERT:** resident/non-resident, taxable/non-taxable, deductibility
  or another tax conclusion.
- **OUTPUT:** typed user/case facts for deterministic Gate 5 replay.
- **PUBLIC PORT:** `Gate5HumanGapClosureRuntimeFactory.create`; the older
  `Gate5SingleInputHumanLoopRuntimeFactory.create` remains an inactive bounded
  natural-language adapter, not tax authority.
- **PREVIOUS / NEXT:** human world -> Gate 5.
- **FAILURE MODE:** insufficient/ambiguous factual evidence remains unresolved.

### External Reference Facts

- **PURPOSE:** supply authoritative non-document, non-human reference facts.
- **INPUT:** identified authoritative source bytes, entity, effective scope and
  provenance.
- **OWNS / MAY ASSERT:** typed CBR rates, market-admission/quotation facts and
  other explicit authoritative reference observations.
- **MUST NOT ASSERT:** tax methodology or applicability merely because a
  reference fact exists.
- **OUTPUT:** provenance-bound typed external facts.
- **PUBLIC PORT:** versioned exact evidence contracts; there is no generic live
  connector authority in this pipeline.
- **PREVIOUS / NEXT:** authoritative reference source -> Gate 5.
- **FAILURE MODE:** unresolved/conflicting/non-authoritative evidence produces no
  fact.

### Methodology Adapter

- **PURPOSE:** convert human-oriented law into a reviewable methodology proposal.
- **INPUT:** official text and authority evidence.
- **OWNS / MAY ASSERT:** structured proposal, cited interpretation and review
  package.
- **MUST NOT ASSERT:** runtime authority from an LLM answer alone.
- **OUTPUT:** reviewed, tested, versioned and hash-pinned methodology or no
  publication.
- **PUBLIC PORT:** `Gate5TrustedMethodologyAuthorityFactory.create` publishes
  only reviewed resources; authoring/research routes are not runtime owners.
- **PREVIOUS / NEXT:** official normative world -> Gate 5.
- **FAILURE MODE:** no review/authority/test evidence means no methodology.

### Declaration Semantics

- **PURPOSE:** state target-independently what will be declared.
- **INPUT:** complete deterministic Gate 5 results and exact case identity.
- **OWNS / MAY ASSERT:** taxpayer, period, income groups/sources, investment
  results, tax base, calculated/withheld/payable/refundable meaning.
- **MUST NOT ASSERT:** XML/PDF paths, encoding mechanics or target-specific
  calculation shortcuts.
- **OUTPUT:** sealed target-independent declaration semantic input.
- **PUBLIC PORT:** `Gate5DeclarationSemanticInputRuntimeFactory.create` owns the
  sealed package view; `DeclarationSemanticsIncomeGroupRuntimeFactory.create`
  owns the legacy Tax Model-to-semantic handoff used by PROJECT. Both remain
  inactive until product release is authorized.
- **PREVIOUS / NEXT:** Gate 5 -> Release.
- **FAILURE MODE:** unresolved meaning stays upstream; no partial target model.

### Release / Completeness

- **PURPOSE:** decide whether evidence permits declaration release.
- **INPUT:** declaration semantics plus active demands, terminal states,
  blockers and evidence ownership.
- **OWNS / MAY ASSERT:** release permission/refusal and exact blockers.
- **MUST NOT ASSERT:** new tax values or source meaning; it does not calculate.
- **OUTPUT:** release receipt or fail-closed blocker set.
- **PUBLIC PORT:** the current preparation/package factories provide inactive
  proof evidence; no live product release port is activated.
- **PREVIOUS / NEXT:** Declaration Semantics -> Projection.
- **FAILURE MODE:** any unresolved blocking demand prevents release.

### Projection

- **PURPOSE:** write already released semantics into an official target format.
- **INPUT:** released declaration semantics + immutable target definition.
- **OWNS / MAY ASSERT:** MAP, FORMAT, PLACE, ENCODE, SERIALIZE and target/XSD
  validation.
- **MUST NOT ASSERT:** FIFO, tax calculation, residency, expense selection,
  evidence repair or scope reasoning.
- **OUTPUT:** XML/PDF plus representational validation proof.
- **PUBLIC PORT:** existing declaration/full-target projection factories.
- **PREVIOUS / NEXT:** Release -> XML/PDF.
- **FAILURE MODE:** target mapping/validation failure; never repair meaning here.

## Evidence Demand loop

Gate 5 owns **WHAT** evidence is required. The source domain owns **HOW** it is
recovered from documents.

```text
Gate5EvidenceDemandRuntimeFactory.create
  -> source_fact_demand_v1
  -> Gate3EvidenceDemandPortFactory.create
  -> Gate3StructuralChunkFactory.create
  -> Gate3ChunkBatchLabelingFactory.create
  -> Gate3FinancialAnnotationsPersistenceFactory.create
     (FULL save or non-destructive DEMAND_SCOPED recovery)
  -> validated full-current-view FinancialAnnotationsV2
  -> Gate4FinancialCaseRuntimeFactory.create
  -> deterministic Gate 5 replay
```

Gate 5 never receives Canonical bytes through this loop. The Gate 3 port only
checks the published Dictionary/Role Pack and binds to the existing owner; it
does not read source or call a provider itself.

The exact publication rules are defined by
[Gate 3 Demand-Scoped Recovery v1](./BROKER_REPORTS_GATE3_DEMAND_SCOPED_RECOVERY.v1.md).
Gate 4 never consumes a narrow recovery delta.

## Provider boundary

Every direct structured-model call site is classified in
`architecture_policy.PROVIDER_CALL_SITE_CLASSIFICATIONS` as exactly one of
`SOURCE_ADAPTER`, `METHODOLOGY_ADAPTER`, `HUMAN_ADAPTER`,
`PRESENTATION_ADAPTER`, or `RESEARCH_ONLY`.
Each entry names the uncertainty removed and strict output contract. Gate 4,
deterministic Gate 5, Declaration Semantics, Release and Projection admit no
source-semantic provider call. `PRESENTATION_ADAPTER` may phrase only a safe
owner-produced public context and may propose `CLARIFY` or one public answer
from a natural reply. The proposal is replayed through the current owner and
cannot create a Human Fact before separate explicit user confirmation. It has
no business authority and may send one authenticated conversation call
only to the administrator-pinned HTTPS OpenWebUI origin, with redirects denied
and response bytes bounded.

## Authority hierarchy

When surfaces disagree, use this order:

1. this current architecture map for domain placement, stage direction and
   `MUST NOT` boundaries;
2. the exact current domain contract/resource for semantic meaning;
3. the maintained factory/public API for construction and execution;
4. an operating guide for procedure only, never for new semantic authority;
5. a compatibility port or generated bundle only when it validates and
   delegates to the owners above;
6. dated reports, receipts and research as historical evidence only.

A downstream report or action ordering cannot promote a local requirement into
a global blocker. Such promotion requires an explicit dependency in items 1-3.

Research status must be explicit: `RESEARCH`, `QUALIFICATION`,
`CONTROLLED PROOF`, or `MAINTAINED`. A passing experiment does not become an
owner. G5.46/G5.47 Canonical recovery is rejected historical evidence; current
Evidence Demand routing is owned by
[Existing Pipeline Reconnection v1](./BROKER_REPORTS_GATE5_EXISTING_PIPELINE_RECONNECTION.v1.md).

## Cold-agent navigation checks

1. Missing `SECURITY_PURCHASE.currency`:
   `Gate 5 Evidence Demand -> Gate 3 public port -> Adaptive Context -> Gate 3
   -> Gate 4 -> Gate 5 replay`. Never read Canonical in Gate 5.
2. Tax residency:
   `methodology requirement -> Human Adapter factual evidence -> typed facts ->
   deterministic Gate 5 methodology`. Never ask an LLM for the tax conclusion.
3. New XML value:
   first ask whether Declaration Semantics owns the meaning. If not, fix the
   upstream semantic owner. Never calculate in Projection.

## Architecture smells — STOP

- Gate 5 starts reading source documents or Canonical.
- Gate 3 starts interpreting tax law.
- Gate 4 starts calculating tax.
- Projection starts deciding business meaning.
- One semantic meaning gets a second owner.
- A new LLM path appears inside deterministic runtime.
- A consumer-specific source fact appears.
- A missing input creates a parallel reader.

Before implementation ask: **WHICH DOMAIN OWNS THIS QUESTION?** Then ask:
**WHAT CONTRACT SHOULD CROSS THE BOUNDARY?** Only then write code.

## Explicit physical boundary debt

`gate5_end_to_end_full_target_xml.py` is an inactive compatibility-only
full-pipeline proof orchestrator whose historical filename places composition
under `gate5_`. It is not a Gate 5 domain owner. Moving it safely requires
replay-consumer and generated-bundle migration, so G5.50 freezes it as the one
exact allowlisted physical debt instead of performing a destructive package
rewrite. New cross-domain imports there or any second exception fail the
architecture tests.
