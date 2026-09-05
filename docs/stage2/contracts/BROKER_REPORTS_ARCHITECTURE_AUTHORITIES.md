# Broker Reports Architecture Authorities

Status: `CURRENT`

Updated: 2026-09-05

Issue #374 updates the Issue #372 PDF boundary without restoring any retired
engine assignment. The configured Mistral adapter is reached only through the
ordinary authenticated Pipe route.
The sole PDF-understanding owner is `PdfDocumentExtractor`; the sole stable
result is provider-neutral `PdfDocumentExtraction`; and the sole selection
point is `PdfDocumentExtractorFactory`. An absent or unselected engine returns
`PDF_DOCUMENT_AI_NOT_CONFIGURED`. With native Mistral configuration, one
accepted PDF causes exactly one provider call. There is no admin qualification,
custom intake/action, retry, repair or automatic fallback. All
PDFPlumber, Camelot, Docling, PyMuPDF, VLM/bbox, hybrid, dual-engine and repair
routes are forbidden. See
[the current ADR](../adr/BROKER_REPORTS_PDF_DOCUMENT_AI_BOUNDARY.v1.md).

Classification: `CURRENT SUPPORTING DOC`; this file maps maintained owners and
does not define gate numbering or gate status.

Composition precedence is strict:

```text
Pipeline Gates current architecture map
> exact current domain contract
> maintained factory/public API
> operating guide
> dated report, receipt or research history
```

This index cannot promote a consumer-local requirement into a global blocker.
Every blocking claim must resolve through Pipeline Gates to a named consumer,
earliest required stage and minimal dependent unit.

`ARCHITECTURE_POLICY_VERSION` is the semantic snapshot identity of the
machine-readable policy, not only the shape of its Python dictionaries. It must
change when an active route, owner, contract, allowed behavior or forbidden
behavior changes. Comments, formatting and behavior-preserving refactors do
not require a bump. Therefore the same version must not name two different
architectural routes across commits; consumers may compare it for exact policy
meaning, while reading the named fields for the policy data itself.

## Active ordinary-trade architecture

This is the implementation-owner map for the currently activated
`ordinary_trade_automatic_semantic_mapping_v1` route. It is subordinate to Pipeline
Gates for numbering, but it is the current answer to **WHO PRODUCES / WHO
CONSUMES** for ordinary security trades.

```text
PDF
-> native OpenWebUI file ID
-> Files exact-owner check -> Storage exact-byte read
-> source custody / safe preflight
-> PdfDocumentExtractorFactory
-> absent or unselected engine: PDF_DOCUMENT_AI_NOT_CONFIGURED and STOP
-> selected configured Mistral -> exactly one call per accepted PDF
-> provider-neutral Markdown/images
-> atomic private graph in the sole ArtifactStore
-> owner-scoped full-source.zip projection through native Files/Storage
-> immutable CanonicalArtifactV1
-> frozen exact mapping fast path OR strict case-scoped semantic mapping
-> append-only clarification/confirmation case + qualification receipt
-> Source Observations
-> deterministic runtime records
-> Gate4FinancialCaseFactV2 compatibility port
-> deterministic Gate 5 source-fact consumption
```

For OpenWebUI 0.9.6 only, the frontend compatibility seam sets `process=false`
on native PDF upload when the exact selected model ID is
`broker_reports_gate1_pipe`. It owns no file mapping or server contract and must
be removed when upstream gains an equivalent per-model processing policy. A
core fork, global bypass and DOM-derived file binding are not authorities.

| Domain | Owns | Input contract | Output contract | Forbidden | Consumer |
| --- | --- | --- | --- | --- | --- |
| Source intake and normalization | source custody/preflight plus provider-neutral `PdfDocumentExtraction` through the sole PDF port; surviving format-normalization outputs | authenticated upload and shared source context | persisted Gate 1 artifacts and validated Canonical candidate | provider-specific knowledge outside the adapter, financial labels or tax meaning | Canonical lifecycle |
| Canonical lifecycle | immutable document/page/table/row/cell representation, exact source refs, activation and current-version selection | validated normalized source plus trusted `ArtifactAccessContext` | active `CanonicalArtifactV1` via `CanonicalReaderFactory.create` | source mutation, financial naming, consumer-specific repair | ordinary-trade projection |
| Case semantic mapping | strict source-semantic proposal for every Canonical table not covered by the frozen exact-schema fast path plus bounded clarification options carrying validator-checked machine decisions | bounded Canonical value sample for exact unknown table nodes with opaque table refs through `OrdinaryTradeSemanticMappingFactory.create` | strict mapping response or one clarification; internal Canonical/case IDs and hashes stay code-only | remapping a frozen table, Canonical mutation, broker/year/filename routing, fuzzy admission, retry, repair, partial publication or unconfirmed table exclusion | append-only mapping case |
| Mapping case | exact user/case/chat/workspace and Canonical binding, same-case resume, stale-answer rejection and native explicit confirmation | validated proposal or interpreted answer | `broker_reports_ordinary_trade_mapping_case_v2`; code renders public options/confirmation from the validated decision; only `COMPLETE` exposes case-qualified material after confirmed-decision checks, full side-literal coverage and a zero-unmapped deterministic dry-run | implicit confirmation, model-authored public decision wording, label-only confirmation, sample-only completeness, overwrite, cross-tenant reuse, global registry promotion | qualified mapping authority |
| Qualified mapping authority | meaning of one exact table schema, literal side enum and amount-column to currency-column bindings; frozen receipt v2 remains the global zero-call schema fast path and case receipt v1 is executable only at its exact authenticated `table_node_id` | package registry or confirmed mapping case | mapping v3 plus `broker_reports_ordinary_trade_mapping_qualification_v2` or `broker_reports_ordinary_trade_case_mapping_qualification_v1` | row/value authorship, broker/year/filename profile keys, fuzzy matching, unconfirmed admission or reuse of a case mapping outside its exact table node | semantic compiler through the projection owner only |
| Ordinary-trade semantic compiler | exact schema match per independent table node, exact execution of case-scoped mappings, explicit display-only no-consumer retention, named-financial-value blocking, qualified amount/currency bindings, deterministic date/decimal transforms and runtime-record lineage | active Canonical plus global frozen mappings and separately scoped case mappings | `broker_reports_ordinary_trade_runtime_projection_v5`: Source Observations, qualified authority lineage, mapping-case ref and runtime records | registry/case overlap on one node, tax, proximity/adjacency binding, relations, inferred continuation, value deduplication, Canonical mutation | projection store and Gate 4 adapter |
| Projection store/current view | immutable projection persistence, exact active-Canonical selection and mandatory composition of the qualified mapping authority with the compiler | active Canonical plus private case context | one current projection per document through `OrdinaryTradeProjectionFactory.create` | caller-supplied mappings, overwrite, stale/latest-wins selection, new meaning | Gate 4 ordinary adapter |
| Gate 4 ordinary adapter | admission into the existing Fact v2 shape, deterministic fact identity and exact active security-position source-contract availability | current validated ordinary projection | `Gate4FinancialCaseFactV2` plus `broker_reports_gate4_ordinary_trade_current_fact_set_v1` through `Gate4OrdinaryTradeCandidateRuntimeFactory.create`; when current projections have no prior `RELEVANT_UNMAPPED` observation but yield no security Fact, the owner returns typed `gate4_ordinary_trade_security_position_source_contract_missing`; current qualified mappings do not emit the optional v4 `position_effect` role | Canonical reads, model calls, classification, tax, SQL cache, historical Gate 4 fallback or invented position state | deterministic Gate 5 and production composition |
| Gate 5 deterministic consumer | reviewed methodology, exact operation-period observation, separate position/source/tax states, FIFO calculation and explicit blockers | Fact v2 only plus trusted context and methodology ref | independent group calculations, `broker_reports_gate5_security_position_scope_v0`, observed dates/years and source blockers; assessment retains an exact source-produced `position_effect` when its Fact port supplies one, but this is not an active-mapping production claim | PDF/Canonical/model output reads, document-period inference, short inference, source-semantic repair, default zero, hidden relations | product composition and later declaration domains only for exact closed calculations |
| Human Fact owner | selected tax period, unsupported-profile mode and established personal/filing facts | current owner publication plus authenticated answer | request-bound immutable facts under stable user/case taxpayer slot and explicit period scope; a mode publication binds the exact current selected-period fact revision, so period changes stale it across year round-trips | Pipe/free-text selection, caller-selected dependency/parallel identity, tax/source/legal conclusion | declaration case inputs |
| Public dialogue presentation | plain-language wording of owner-produced public state and a non-authoritative free-answer proposal | `broker_reports_ordinary_trade_public_dialogue_context_v3` plus the current user's natural reply; mapping clarification enters only through the bounded `MAPPING_CLARIFICATION` action with an opaque current question binding, code-validated safe option descriptions and source literals explicitly tagged as runtime-only quoted data | validated `broker_reports_ordinary_trade_public_dialogue_message_v5`, bound `broker_reports_ordinary_trade_public_mapping_verification_v1` or `broker_reports_ordinary_trade_public_interpretation_v1`; for mapping clarification the dialogue LLM writes one natural question from the safe brief, then a separate strict presentation verifier sees the same safe brief and draft but no raw source and returns exact-turn `ACCEPT/REJECT`; runtime shows the draft only after exact binding and `ACCEPT`, otherwise it falls back; runtime separately attaches source titles as quotations; neither presentation call has business authority, uses lexical semantic rules, or creates a Fact before native confirmation; mapping confirmation remains exact and code-owned; Pipe transport uses only the administrator-pinned HTTPS OpenWebUI origin, denies redirects and bounds response bytes | model-supplied contract identity, foreign/missing question or option binding, raw source text in either presentation prompt, an additional action/data request/financial meaning, model-authored confirmation, request/base-URL-derived destinations, cross-origin token forwarding, raw mapping state, internal role codes, Fact contract names, raw refs/status/reason/source rows, business decisions, request identity, direct Human Fact publication, silent interpretation or more than two presentation calls for a mapping question | OpenWebUI Pipe, explicit user confirmation, then the existing Human Fact or mapping case owner |
| Exact profile composition | `Gate5TrustedMethodologyAuthorityFactory.create` owns tax product rules and insufficient-input classification; `Gate5FullTargetXmlProjectionDefinitionAuthorityFactory.create` owns immutable profile ID/version and form/KND/order/format/XSD target identity | selected non-sentinel Human Fact year plus exact source assertions | profile absence only when the selected year is absent from the Definition-owned available set; source-assertion gaps retain the pinned rule's `REAL_SOURCE_EVIDENCE_MISSING`, while malformed/missing methodology keeps its methodology blocker | silent year substitution, closest-profile fallback, copied form/XSD constants, masking authority failure as profile absence | declaration adapter |
| Product composition | route selection, exact Canonical activation, orchestration, system identity and terminal result | release valves, Canonical refs and trusted context | `broker_reports_ordinary_trade_production_run_v1` through `OrdinaryTradeProductionRuntimeFactory.create`; it preserves the Gate 4 fact-set blocker across status, terminal, Gate 5 accounting, gap closure and final note; the Pipe composes the presentation adapter without transferring meaning and publishes verified idempotent private XML through native Files/Storage; native logical file identity is exact authenticated user + case scope + XML bytes, while the first valid execution receipt remains immutable provenance rather than identity | semantic/legacy fallback, unclassified or domain provider call, broker/year/filename profile routing, caller-selected Human refs/fact keys or hidden declaration action, caller-derived presentation origin, surrogate field invention, reclassification of an owner blocker, receipt-selected duplicate Files identity or alternate XML | OpenWebUI pipe/product response |

### Active authorities

- Pipeline status and route direction: Pipeline Gates v1.
- Canonical meaning: Canonical Artifact v1 and Canonical Reader v1.
- Qualified schema/enum mapping and admission law:
  [Ordinary Trade Qualified Mapping v1](./BROKER_REPORTS_ORDINARY_TRADE_QUALIFIED_MAPPING.v1.md)
  through `ordinary_trade_qualified_mappings.py`.
- Unknown-schema dialogue and case qualification:
  [Ordinary Trade Automatic Semantic Mapping v1](./BROKER_REPORTS_ORDINARY_TRADE_AUTOMATIC_SEMANTIC_MAPPING.v1.md).
- Source Observation/runtime projection: `ordinary_trade_semantic_compiler.py`.
- Fact boundary: Gate 4 Financial Case Fact v2.
- Tax-methodology behavior: the existing trusted Gate 5 methodology authority.

### Historical / evidence only

- `FinancialAnnotationsV2`, Gate 3 type/role passes and the Gate 3-backed SQL
  case runtime are retained deployment-rollback compatibility for this scope.
  They are not read or called by the active ordinary route.
- Dated reports/receipts prove only their exact revision and run. They cannot
  activate a module, redefine a contract or override this map.
- The release report is evidence that the current route was deployed; it is
  not the specification of the route.

### Supported boundaries

- only exact qualified `SECURITY_TRADES` table schemas and exact side literals;
- ordinary purchase/disposal rows with the required source fields;
- non-zero broker/exchange commissions as separate `TRANSACTION_CHARGE` facts;
- every emitted gross amount or charge uses the currency column explicitly bound
  to its amount column by mapping v3 and covered by qualification receipt v2;
  column adjacency has no authority;
- supported and unknown tables in one Canonical: frozen tables stay on the
  zero-call path while only exact unknown table nodes enter the mapping case;
  repeated exact structures execute independently per table node; titles and
  headers remain in Canonical and mapping evidence.
- a mapped row may be retained as display-only only when every non-empty mapped
  field has no standalone transaction/monetary consumer. Any non-empty date,
  side, quantity, price, currency, amount, commission, accrued-interest or
  settlement field remains `RELEVANT_UNMAPPED` until the row contract is complete.

### Unsupported boundaries

- unknown or changed schema, competing mapping authorities for one table node,
  unknown side, incomplete/invalid financial row and inferred table continuation;
- coupons, withheld tax and any financial class not explicitly admitted by an
  exact qualified mapping;
- REPO documents for which Gate 1 does not produce an active Canonical;
- cross-table/mixed-journal structural lineage and financial-event relations;
- declaration release when Gate 5 evidence or methodology is insufficient.
- document reporting period/evidence-horizon completeness when it is not
  explicitly source-bound by the current Fact contract;
- filing XML for a selected year without the exact methodology/form/XSD
  profile; analysis-only and surrogate outputs remain explicitly non-filing.

Unsupported content is retained as Canonical/`RELEVANT_UNMAPPED` or stops with
a typed blocker. It never enters Gate 5 and never invokes Gate 3 or legacy as a
fallback.

### Known compatibility debt

- Fact v2 still names its upstream provenance envelope `gate3_binding` and
  requires the historical `broker_reports_financial_annotations_v2`
  discriminator. On the active route the field binds the ordinary projection
  artifact and Canonical identity; it does **not** prove Gate 3 execution.
- `ordinary_trade_candidate_runtime.py`, the pipe method
  `_maybe_run_ndfl_gate3` and the response key `ndfl_gate3` retain pre-activation
  names. Their names are compatibility debt, not runtime ownership.
- `architecture_policy.GATE_OWNERSHIP` retains generic gate responsibilities;
  its separate closed `ACTIVE_PRODUCT_ROUTES` map identifies the active ordinary
  source-semantic factories and marks Gate 3 runtime as rollback-only.

### Forbidden cross-domain dependencies

- normalization/Canonical must not assign financial or tax meaning;
- the mapping/compiler must not infer tax, relations, missing source values or
  amount/currency binding from proximity or column adjacency;
- Gate 4 must not repair source semantics or calculate tax;
- Gate 5 must not read PDF, Canonical, Source Observations or model output;
- Projection must not calculate or decide release;
- no source layer may use broker/year/filename routing or silently fall back to
  the historical Gate 3 path.

Start at [Pipeline Gates v1](./BROKER_REPORTS_PIPELINE_GATES.v1.md). For the
active ordinary-trade path, read the map above and the exact Fact v2 contract.
For historical Gate 5 context, read the short
[Gate 4 -> Gate 5 handoff](./BROKER_REPORTS_GATE4_HANDOFF.v1.md), then the
[Gate 5 Methodology Selection v0](./BROKER_REPORTS_GATE5_METHODOLOGY_SELECTION.v0.md)
when working on the inactive G5.2 proof seam or the
[Gate 5 Supplemental Fact Persistence v0](./BROKER_REPORTS_GATE5_SUPPLEMENTAL_FACT_PERSISTENCE.v0.md)
when working on the inactive G5.3 proof seam or the
[Gate 5 Combined Requirement Check v0](./BROKER_REPORTS_GATE5_COMBINED_REQUIREMENT_CHECK.v0.md)
when working on the inactive G5.4 proof seam or the
[Gate 5 Supplemental Fact Discovery v0](./BROKER_REPORTS_GATE5_SUPPLEMENTAL_FACT_DISCOVERY.v0.md)
when working on the inactive G5.5 proof seam or the
[Gate 5 Single-Input Human Loop v0](./BROKER_REPORTS_GATE5_SINGLE_INPUT_HUMAN_LOOP.v0.md)
when working on the inactive G5.6 proof seam or the
[Gate 5 Methodology Calculation v0](./BROKER_REPORTS_GATE5_METHODOLOGY_CALCULATION.v0.md)
when working on the inactive G5.7 proof seam or the
[Gate 5 Trusted Methodology Authority v0](./BROKER_REPORTS_GATE5_TRUSTED_METHODOLOGY_AUTHORITY.v0.md)
when working on the inactive G5.8 proof seam or the
[Gate 5 External Evidence Routing v0](./BROKER_REPORTS_GATE5_EXTERNAL_EVIDENCE_ROUTING.v0.md)
when working on the inactive G5.11 proof seam or the
[Gate 5 Declaration Projection v1](./BROKER_REPORTS_GATE5_DECLARATION_PROJECTION.v1.md)
when working on the current inactive G5.24 PROJECT boundary, or previous
[v0](./BROKER_REPORTS_GATE5_DECLARATION_PROJECTION.v0.md) when replaying G5.12, or the
[Gate 5 Declaration-Driven Tax Model v0](./BROKER_REPORTS_GATE5_DECLARATION_DRIVEN_TAX_MODEL.v0.md)
when working on the inactive G5.13 proof seam or the
[Gate 5 Tax-Period Category Aggregation v0](./BROKER_REPORTS_GATE5_TAX_PERIOD_CATEGORY_AGGREGATION.v0.md)
when working on the inactive G5.14 proof seam or the
[Gate 5 Stable Income-Group Tax Base v0](./BROKER_REPORTS_GATE5_SECTION2_CALCULATION_SEMANTICS.v0.md)
when working on the inactive G5.22 semantic behavior or the
[Gate 5 Runtime Capability Contract v3](./BROKER_REPORTS_GATE5_RUNTIME_CAPABILITY_CONTRACT.v3.md)
when working on the current G5.24 PROJECT surface, or previous
[v2](./BROKER_REPORTS_GATE5_RUNTIME_CAPABILITY_CONTRACT.v2.md),
[v1](./BROKER_REPORTS_GATE5_RUNTIME_CAPABILITY_CONTRACT.v1.md) and
[v0](./BROKER_REPORTS_GATE5_RUNTIME_CAPABILITY_CONTRACT.v0.md) for exact replay, or the
[Gate 5 Declaration Authoring Language v2](./BROKER_REPORTS_GATE5_DECLARATION_AUTHORING_LANGUAGE.v2.md)
when replaying the G5.21 semantic authoring/compiler boundary or the previous
[Gate 5 Independent Declaration Authoring v1](./BROKER_REPORTS_GATE5_INDEPENDENT_DECLARATION_AUTHORING.v1.md)
when replaying the G5.20 plain-JSON independent authoring result, or the previous
[Gate 5 Clean-Context Declaration Authoring v0](./BROKER_REPORTS_GATE5_CLEAN_CONTEXT_DECLARATION_AUTHORING.v0.md)
when replaying the G5.19 pre-inference strict-schema result, or the
[Gate 5 Full Declaration Definition Authoring v1](./BROKER_REPORTS_GATE5_FULL_DECLARATION_DEFINITION.v1.md)
when resolving the trusted G5.28B full-root Definition, the
[Gate 5 Declaration Semantic Input v0](./BROKER_REPORTS_GATE5_DECLARATION_SEMANTIC_INPUT.v0.md)
for the inactive G5.33 target-independent consumer boundary, the
[Gate 5 Full-target XML Projection v0](./BROKER_REPORTS_GATE5_FULL_TARGET_XML_PROJECTION.v0.md)
for the inactive G5.34 complete 3-NDFL XML projection proof, the
[Gate 5 End-to-End Full-target XML v0](./BROKER_REPORTS_GATE5_END_TO_END_FULL_TARGET_XML.v0.md)
for the inactive G5.35 supplied-source-to-XSD proof, the
[Gate 5 Real OpenWebUI Product Path v0](./BROKER_REPORTS_GATE5_REAL_OPENWEBUI_PRODUCT_PATH.v0.md)
for the current proof-only and post-proof-inactive G5.36 product boundary, the
  historical [Gate 5 First Real Economic Coverage v0](./BROKER_REPORTS_GATE5_FIRST_REAL_ECONOMIC_COVERAGE.v0.md)
for the rejected G5.38 related-event boundary, the current
[Source-Fact Domain Boundaries v1](./BROKER_REPORTS_SOURCE_FACT_DOMAIN_BOUNDARIES.v1.md)
for the G5.40C semantic ceiling and relation-removal decision, the
[Gate 5 Deterministic Source-Fact Consumption v0](./BROKER_REPORTS_GATE5_DETERMINISTIC_SOURCE_FACT_CONSUMPTION.v0.md)
for the G5.40D/G5.40F deterministic consumer boundary, the
[Gate 5 Real Tax Case Assembly v0](./BROKER_REPORTS_GATE5_REAL_TAX_CASE_ASSEMBLY.v0.md)
for the G5.40F demand-first supplied-case boundary, the
[Gate 5 Declaration Preparation v0](./BROKER_REPORTS_GATE5_DECLARATION_PREPARATION.v0.md)
for the historical G5.41 intake/review/scope/human-replay/readiness composition,
the current
[Gate 5 Human Fact Scope v1](./BROKER_REPORTS_GATE5_HUMAN_FACT_SCOPE.v1.md)
for exact authenticated user/case/taxpayer/period/request-bound Human Adapter
publication and same-case cross-run replay, the
[Cross-Gate Domain Ownership v1](./BROKER_REPORTS_CROSS_GATE_DOMAIN_OWNERSHIP.v1.md)
for the G5.42 one-owner map, LLM/relations audit and compatibility-debt boundary, the
[Gate 5 Evidence to Tax Methodology Bridge v1](./BROKER_REPORTS_GATE5_EVIDENCE_TAX_METHODOLOGY_BRIDGE.v1.md)
for the G5.43 source-evidence, reviewed-methodology and deterministic-input bridge, the
[Gate 5 Evidence Interpretation Contracts v1](./BROKER_REPORTS_GATE5_EVIDENCE_INTERPRETATION_CONTRACTS.v1.md)
for the G5.44 residency, commission-selection, acquisition-coverage and
direct-charge interpretation boundaries, the
[Gate 5 Declaration Model Assembly v1](./BROKER_REPORTS_GATE5_DECLARATION_MODEL_ASSEMBLY.v1.md)
for the G5.45 consumer-first inventory, released-value trace and controlled
end-to-end declaration assembly proof, the
[Gate 5 Existing Pipeline Reconnection v1](./BROKER_REPORTS_GATE5_EXISTING_PIPELINE_RECONNECTION.v1.md)
for the current G5.48 demand-as-request boundary and exact Gate 3 owner binding,
the
[Gate 5 Supplied-case Completeness v1](./BROKER_REPORTS_GATE5_SUPPLIED_CASE_COMPLETENESS.v1.md)
for the corrected G5.32 scope/package boundary, the historical
[Gate 5 Declaration Scope Resolution v0](./BROKER_REPORTS_GATE5_DECLARATION_SCOPE_RESOLUTION.v0.md)
and [Resolved Declaration Package v0](./BROKER_REPORTS_GATE5_RESOLVED_DECLARATION_PACKAGE.v0.md)
when replaying G5.29-G5.31, or previous
[v0](./BROKER_REPORTS_GATE5_FULL_DECLARATION_DEFINITION.v0.md) when replaying
the rejected G5.28 candidate. Use the
[Gate 3 handoff](./BROKER_REPORTS_GATE3_HANDOFF.v1.md) only for an upstream
role/binding audit. Use the
[Gate 2 implementation map](../architecture/BROKER_REPORTS_GATE2_IMPLEMENTATION_MAP.v1.md)
and [safe-change guide](../operations/BROKER_REPORTS_GATE2_SAFE_CHANGE_GUIDE.v1.md)
only when the task reaches those implementation surfaces.

G5.50 refinement: Pipeline Gates v1 is now the complete Gate 1 -> Projection
navigation map and owns all domain placement/`MUST NOT` boundaries. This long
file is an implementation index only; it must never be used as a second
pipeline narrative.

This is the compact orientation index for maintained Broker Reports
implementation authorities. Current gate numbering is owned by
[Pipeline Gates v1](./BROKER_REPORTS_PIPELINE_GATES.v1.md). The older
[global gate architecture](../blueprints/BROKER_REPORTS_GATE_ARCHITECTURE.md)
is `SUPERSEDED` for numbering and remains migration context only.

Use this order when sources appear to disagree:

1. Pipeline Gates v1 owns gate placement and product boundaries;
2. a versioned contract owns DTO meaning and invariants;
3. the maintained source factory owns object construction or execution;
4. a compatibility entrypoint may only adapt and delegate;
5. generated bundles project maintained source;
6. dated reports and receipts are historical evidence only.

## Documentation authority audit

The repository contains 595 Broker Reports Markdown files that mention the
audited gate, canonical, annotation, NDFL or financial-label terms. They are
classified by ownership and document family; they are not 594 independent
authorities.

| Classification | Documents or family | Rule |
| --- | --- | --- |
| `CURRENT AUTHORITY` | [Pipeline Gates v1](./BROKER_REPORTS_PIPELINE_GATES.v1.md) | the one current Gate 1-through-Projection navigation, ownership and status map |
| `CURRENT SUPPORTING DOC` | this map, [Source-Fact Domain Boundaries v1](./BROKER_REPORTS_SOURCE_FACT_DOMAIN_BOUNDARIES.v1.md), [Gate 4 -> Gate 5 Handoff v1](./BROKER_REPORTS_GATE4_HANDOFF.v1.md), [Gate 4 Financial Case Fact v2](./BROKER_REPORTS_GATE4_FINANCIAL_CASE_FACT.v2.md), and current Gate 5 methodology/declaration contracts listed below | explain direct boundaries or own exact DTO/factory meaning; cannot renumber gates |
| `DEPLOYMENT ROLLBACK COMPATIBILITY` | Gate 3 handoff/contracts, `FinancialAnnotationsV2`, Gate 3-backed Gate 4 SQL/assembly contracts | exact historical path only; not active ordinary-trade authority and never fallback |
| `CURRENT SUPPORTING DOC` | [Gate 5 Supplied-case Completeness v1](./BROKER_REPORTS_GATE5_SUPPLIED_CASE_COMPLETENESS.v1.md) | owns the corrected inactive G5.32 scope and sealed supplied-case completeness boundary |
| `CURRENT SUPPORTING DOC` | [Gate 5 Declaration Semantic Input v0](./BROKER_REPORTS_GATE5_DECLARATION_SEMANTIC_INPUT.v0.md) | owns the inactive G5.33 target-independent semantic consumer boundary and H2 verdict |
| `CURRENT SUPPORTING DOC` | [Gate 5 Full-target XML Projection v0](./BROKER_REPORTS_GATE5_FULL_TARGET_XML_PROJECTION.v0.md) | owns the inactive G5.34 definition-driven full-target XML, mapping-proof, XSD-conformance and terminal-receipt boundary |
| `CURRENT SUPPORTING DOC` | [Gate 5 End-to-End Full-target XML v0](./BROKER_REPORTS_GATE5_END_TO_END_FULL_TARGET_XML.v0.md) | owns the inactive G5.35 authenticated supplied-source through official-XSD composition proof and source-to-target hash-chain boundary |
| `CURRENT SUPPORTING DOC` | [Gate 5 Real OpenWebUI Product Path v0](./BROKER_REPORTS_GATE5_REAL_OPENWEBUI_PRODUCT_PATH.v0.md) | owns the controlled-staging G5.36 native auth/upload/chat/human-residual/private-download proof; the product valve is off after proof |
| `CURRENT SUPPORTING DOC` | [Source-Fact Domain Boundaries v1](./BROKER_REPORTS_SOURCE_FACT_DOMAIN_BOUNDARIES.v1.md), [Gate 5 Deterministic Source-Fact Consumption v0](./BROKER_REPORTS_GATE5_DETERMINISTIC_SOURCE_FACT_CONSUMPTION.v0.md), [Gate 5 Real Tax Case Assembly v0](./BROKER_REPORTS_GATE5_REAL_TAX_CASE_ASSEMBLY.v0.md) and [Gate 5 Declaration Preparation v0](./BROKER_REPORTS_GATE5_DECLARATION_PREPARATION.v0.md) | own the source semantic ceiling, independent available-evidence calculation, demand accounting and G5.41 client-ready preparation composition; none creates relation meaning |
| `CURRENT SUPPORTING DOC` | [Cross-Gate Domain Ownership v1](./BROKER_REPORTS_CROSS_GATE_DOMAIN_OWNERSHIP.v1.md) | owns the G5.42 cross-gate owner/call-direction, LLM classification, relations boundary and explicit compatibility-debt map; cannot renumber gates or publish legal methodology |
| `CURRENT SUPPORTING DOC` | [Gate 5 Evidence to Tax Methodology Bridge v1](./BROKER_REPORTS_GATE5_EVIDENCE_TAX_METHODOLOGY_BRIDGE.v1.md) | owns the G5.43 audited source-fact, tax-methodology and deterministic-input bridge for the active 2025 broker/securities scope; cannot activate filing, projection or advisory processing |
| `CURRENT SUPPORTING DOC` | [Gate 5 Evidence Interpretation Contracts v1](./BROKER_REPORTS_GATE5_EVIDENCE_INTERPRETATION_CONTRACTS.v1.md) | owns the G5.44 residency-evidence, commission-selection, acquisition-basis-coverage and direct-charge interpretation boundaries; cannot close the four external legal-methodology gaps or activate filing/projection |
| `CURRENT SUPPORTING DOC` | [Gate 5 Declaration Model Assembly v1](./BROKER_REPORTS_GATE5_DECLARATION_MODEL_ASSEMBLY.v1.md) | owns the G5.45 bounded consumer inventory, released semantic-value traceability and controlled end-to-end assembly proof; cannot claim real-case completeness, activate filing or replace the product authority |
| `CURRENT SUPPORTING DOC` | [Gate 5 Existing Pipeline Reconnection v1](./BROKER_REPORTS_GATE5_EXISTING_PIPELINE_RECONNECTION.v1.md) | owns the G5.48 demand-as-request contract, exact Gate 3 owner binding, removal of the Gate 5 Canonical reader/provider and transient Gate 4 projector, and fail-closed one-gap live boundary |
| `CURRENT SUPPORTING DOC` | [Gate 3 Demand-Scoped Recovery v1](./BROKER_REPORTS_GATE3_DEMAND_SCOPED_RECOVERY.v1.md) | owns the G5.55 FULL versus DEMAND_SCOPED publication distinction, exact-target supersession, the G5.56 narrow same-table-row cell-to-row refinement rule and zero omission-driven deletion under the existing Gate 3 persistence owner |
| `REJECTED HISTORICAL EVIDENCE` | [Gate 5 Methodology-Driven Evidence Demand v1](./BROKER_REPORTS_GATE5_METHODOLOGY_DRIVEN_EVIDENCE_DEMAND.v1.md), [Gate 5 Real Canonical Semantic Recovery v1](./BROKER_REPORTS_GATE5_REAL_CANONICAL_SEMANTIC_RECOVERY.v1.md) | retain the useful consumer-demand and 32-to-10 consolidation evidence; their Gate 5 Canonical recovery authority and G5.47 preservation conclusion are superseded by G5.48 |
| `REJECTED INACTIVE EXPERIMENT` | [Gate 3 Predeclared Atomic Assertions v0](./BROKER_REPORTS_GATE3_PREDECLARED_ATOMIC_ASSERTIONS.v0.md) | preserves the G5.92 exact-target batch-classification candidate and negative semantic result; it does not replace current pass 1, activate Dictionary 2.1.0, or authorize a second Gate 3 owner |
| `SUPERSEDED SUPPORTING EVIDENCE` | [Gate 5 First Real Economic Coverage v0](./BROKER_REPORTS_GATE5_FIRST_REAL_ECONOMIC_COVERAGE.v0.md) | retains the rejected G5.38 relation experiment and routes current work to the G5.40C boundary |
| `SUPERSEDED SUPPORTING EVIDENCE` | [Gate 5 Declaration Scope Resolution v0](./BROKER_REPORTS_GATE5_DECLARATION_SCOPE_RESOLUTION.v0.md), [Gate 5 Resolved Declaration Package v0](./BROKER_REPORTS_GATE5_RESOLVED_DECLARATION_PACKAGE.v0.md) | retain the historical G5.29-G5.31 interpretation and route current work to Supplied-case Completeness v1 |
| `EVIDENCE` | dated reports/receipts, including corrected G3.7C and G3.C5 product-path proof | prove one revision and scope; never a current contract |
| `HISTORICAL` | dated research, proof plans, old current-state snapshots and evidence indexes | retained for audit or investigation only |
| `SUPERSEDED` | `BROKER_REPORTS_GATE_ARCHITECTURE.md`, `BROKER_REPORTS_3NDFL.blueprint.md`, the pre-Gate-3 Domain Map, Contract Flow Mapping and Data Contract Family | old gate meaning is preserved but cannot override Pipeline Gates v1 |
| `STALE / CONFLICTING` | any unqualified claim that the active ordinary-trade route executes Gate 3, reads `FinancialAnnotationsV2`, requires old Gate 4 SQL, or may use legacy/semantic fallback | must be treated as historical text and routed to Pipeline Gates v1 before use |

### G5.50 contradiction classification

| Surface | Finding before refinement | G5.50 classification / action |
| --- | --- | --- |
| Pipeline Gates v1 | stopped its primary sequence at Gate 4 and still pointed to Gate 5 design | `AMBIGUOUS_DOC -> CURRENT`; replaced by the complete short navigation map and domain cards |
| this implementation index | its length and many proof seams could be mistaken for architecture precedence | `AMBIGUOUS_DOC -> CURRENT SUPPORTING DOC`; explicitly subordinate to Pipeline Gates v1 |
| Cross-Gate Domain Ownership v1 | correct one-way map, but named the Evidence Demand boundary an adapter and retained the pre-G5.50 entry-point role | `CURRENT`; routed to the new map and renamed the boundary to the published Gate 3 port |
| G5.46 Methodology-Driven Evidence Demand v1 | formerly described Gate 5 Canonical/provider recovery | `HISTORICAL_ONLY`; rejected runtime authority and current-route pointer remain explicit |
| G5.47 Real Canonical Semantic Recovery v1 | described the removed parallel reader/projector | `HISTORICAL_ONLY`; retained only as rejected research evidence |
| Managed Financial Domain v1 | pre-renumbering text assigned financial classification and “Gate 3 tax methodology” to old owners | `COMPATIBILITY_ONLY`; cannot define current Gate 2/3/5 meaning |
| old global Gate Architecture blueprint | pre-current numbering | `HISTORICAL_ONLY / SUPERSEDED`; visual-table legacy evidence only |
| inactive versioned Gate 5 proof contracts | exact replay evidence can resemble current product architecture | `COMPATIBILITY_ONLY` or `HISTORICAL_ONLY` according to each heading; never overrides the map |

Research, proposals, drafts, Skills/Prompts and generated assets are not
architecture authority merely because they contain the same terms. Dated Gate
3 reports remain evidence even when their outcome is terminal. The earlier
G3.7 `NOT_READY` conclusion is superseded by corrected G3.7C evidence.

## Minimal domain responsibility map

For ordinary security trades, the active rows are the active architecture table
above. Gate 3 and Gate 3-backed Gate 4 rows below describe retained deployment-
rollback compatibility or exact historical proof surfaces; their word
`current` is scoped to those versioned contracts, not to release activation.

| Domain | Owns | Does not own | Public entrypoint | Normative contracts | Allowed consumers | Forbidden duplicate |
| --- | --- | --- | --- | --- | --- | --- |
| Gate 1 Intake | authenticated upload custody, access, format detection, original storage and routing | canonical normalization, financial meaning or product cutover | existing intake/ArtifactStore factories and `ArtifactResolver` | [Pipeline Gates v1](./BROKER_REPORTS_PIPELINE_GATES.v1.md) | Gate 2 canonical extraction | native document processing, Knowledge/RAG/vectorization or caller tenant authority |
| PDF Document AI | provider-neutral extraction of exact Markdown/pages/opaque image refs and provenance; the Mistral adapter preserves `page_number + markdown_target -> local_ref + sha256` in order | custody/preflight, Canonical, financial meaning, provider fallback or content repair | `PdfDocumentExtractor` selected only by `PdfDocumentExtractorFactory`; existing ArtifactStore owns the atomic private Markdown/image lifecycle | [PDF Document AI boundary ADR](../adr/BROKER_REPORTS_PDF_DOCUMENT_AI_BOUNDARY.v1.md) | ordinary authenticated Pipe; native owner-checked file IDs enter one configured Mistral call per PDF, then owner-scoped Full Source delivery | provider/model/response knowledge outside adapter/composition, positional reconstruction, alternate parsers, second store, custom intake/action, retry or automatic fallback |
| Gate 2 Canonical | format extraction, deterministic non-financial `CanonicalArtifactV1`, provenance/issues, immutable versions, shared completeness and shadow comparison | product/task-specific LLM projection, financial type/role meaning or product cutover | `FullSourceArtifactFactory`, `CanonicalNormalizerFactory.create`, `CanonicalArtifactStoreFactory.create`, `CanonicalReaderFactory.create` | [Canonical Artifact v1](./BROKER_REPORTS_CANONICAL_ARTIFACT.v1.md), Storage, Reader and [Gate 2 Exit Contract v1](./BROKER_REPORTS_GATE2_EXIT_CONTRACT.v1.md) | shadow/read-only proof and the explicitly authorized NDFL Gate 3 exact-manifest route | a second schema/parser/store/reader, direct component access or canonical product reads outside an authorized route |
| Gate 2 Consumer Compatibility | consumer-specific, versioned structural projection over an active canonical version; aggregate safe read telemetry; one non-active format-neutral proof renderer | global read enable, legacy fallback, private evidence, financial semantics or consumer selection | four explicit factories plus `render_neutral_canonical_projection` in `canonical_consumer_migration.py`, all consuming `CanonicalReaderFactory.create` output | [Canonical Reader v1](./BROKER_REPORTS_CANONICAL_READER.v1.md), [Gate 2 Exit Contract v1](./BROKER_REPORTS_GATE2_EXIT_CONTRACT.v1.md), [Migration Strategy](./BROKER_REPORTS_GATE2_MIGRATION_STRATEGY.v1.md), [Consumer Matrix](./BROKER_REPORTS_GATE2_CONSUMER_MIGRATION_MATRIX.v1.md) | isolated Wave 0 tests, retained-cohort proof and shadow-only Wave 2 | format-branch consumer API, direct ArtifactStore/SQLite/payload access, global flag or silent fallback |
| Technical Preparation | deterministic financial scope, technical preclose and sealed Evidence Bundle | financial classification or provider choice | `Gate2DeterministicFinancialScopeFromGate1V2Factory.create`, `Gate2FinancialEvidenceBundleFactory.create` | Evidence Bundle | Candidate Compiler, Qualification | a second source/provenance projection |
| Financial Semantic Pack | type/role meaning, ambiguity rules and lifecycle | source binding, provider transport or materialization | `Gate2FinancialSemanticContractFactory.create` | Financial Semantic Pack | projection, compiler, validation, materialization, Financial Domain | type-specific Python or a second registry |
| Candidate Compiler | complete code-owned Typed Options from Pack plus technical evidence | semantic selection or invented bindings | `Gate2FinancialCandidateCompilerFactory.create` | Candidate Compiler and Typed Option | Semantic Matcher, replay | financial regex, known type IDs or provider-built records |
| Semantic Matcher | current four-block packet, versioned model-visible context boundary and field-eligibility policy, semantic instruction, complete-request lint, provider-neutral minimal choice and deterministic choice expansion | source refs/provenance ownership, Pack/Reason meaning, canonical acceptance or persistence | V6 packet/Prompt/Choice factories, `Gate2FinancialSemanticV6ContextLinterFactory.create` plus additive `create_context_v2_1`, and `Gate2FinancialSemanticV6DecisionExpansionFactory.create` | V6 Packet, LLM Semantic Context, [Minimal Model Surface](./BROKER_REPORTS_GATE2_MINIMAL_MODEL_SURFACE.v1.md), Choice and Expansion | Qualification, Validation, Evidence | model-generated records, copied semantic wording, second packet builder or alternative choice schema |
| Provider Integration | canonical request construction, provider-specific projection, transport response parsing and usage normalization | financial semantics, budget policy or product validation | `Gate2StructuredModelClientFactory.create` using request builder and adapter factories; additive Context V2.1 one-attempt seam remains under that factory | provider-neutral request/choice plus execution metadata contracts and [Context V2.1 Budget Model Smoke v1](./BROKER_REPORTS_GATE2_CONTEXT_V2_1_BUDGET_MODEL_SMOKE.v1.md) | maintained runtime and qualification | direct provider request/response parsing outside builder/adapters |
| Budget | pre-transport admission and post-response usage/cost accounting | request shape, provider parsing or semantic verdict | `Gate2EconomyBudgetSessionFactory.create` | economy budget v1 code contract | structured model client | token/cost policy in callers |
| Validation | canonical decision parsing, Pack/Registry/source authority checks and accepted-decision validation | provider adaptation, ID minting or persistence | `Gate2FinancialEvidenceValidatedDecisionFactory.create`, `validate_financial_evidence_inputs` | Generic Financial Materialization | Materialization, Qualification | local validators that weaken the canonical contract |
| Materialization | canonical IDs, bindings, ownership, provenance, retention and terminal coverage | type semantics, provider choice or storage | `Gate2FinancialEvidenceMaterializerFactory.create().materialize` | Generic Financial Materialization | Financial Domain and explicit compatibility projections | materialization in qualification/evidence/consumer code |
| Financial Domain | immutable historical snapshot, bounded query semantics and serialization envelope | current Gate 3 or Gate 4 fact meaning, raw source/provider reads or workflow state | catalog, query and persistence factories | Managed Financial Domain and Query API | historical compatibility only; any later adapter requires its own explicit Gate 4 Goal | direct record catalogs, query facades or snapshot minting presented as current Gate 4 |
| Gate 3 Minimal Labeling Contract | DTO meaning for one canonical-bound projection, sparse label proposal, role proposal and validated annotation sidecar; exact traversal/alias rule and bare-alias model-facing schema projection | dictionary/Role Pack meaning, provider execution, persistence, workflow or activation | [Minimal Labeling v1](./BROKER_REPORTS_GATE3_MINIMAL_LABELING.v1.md), [Role Labeling v1](./BROKER_REPORTS_GATE3_ROLE_LABELING.v1.md) and their closed schemas | current Gate 3 contracts | projection, type pass, role pass, persistence and NDFL workflow | a second target grammar, alias parser/normalizer, rewritten canonical artifact or Financial Domain on the current Gate 3 route |
| Gate 3 Projection | deterministic Markdown and backend-only reversible aliases over the exact active canonical version | source parsing, financial meaning, model execution, storage, workflow or activation | [`Gate3ProjectionFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate3_projection.py) via `CanonicalReaderFactory.create().read_active_envelope` | [Minimal Labeling v1](./BROKER_REPORTS_GATE3_MINIMAL_LABELING.v1.md), [Gate 3 Handoff v1](./BROKER_REPORTS_GATE3_HANDOFF.v1.md) and [Canonical Reader v1](./BROKER_REPORTS_CANONICAL_READER.v1.md) | NDFL product workflow plus retained proofs | raw artifact input, source-format branch, second renderer, projection persistence or model-visible canonical IDs |
| Gate 3 Structural Chunking | ordered bounded model contexts, structural context repetition and exactly-once projection of existing G3.2 targets | financial/keyword selection, model execution, batching, annotation merge, persistence, overlap or product activation | [`Gate3StructuralChunkFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate3_structural_chunking.py) over the exact package-internal render plan owned by `Gate3ProjectionFactory` | [Structural Chunking v1](./BROKER_REPORTS_GATE3_STRUCTURAL_CHUNKING.v1.md), [Structural Chunk Set schema](./BROKER_REPORTS_GATE3_STRUCTURAL_CHUNK_SET.v1.schema.json) and [Minimal Labeling v1](./BROKER_REPORTS_GATE3_MINIMAL_LABELING.v1.md) | NDFL product workflow plus retained proofs | second renderer or alias issuer, financial labels/dictionary, arbitrary token windows, row overlap, provider call, ArtifactStore registration or workflow |
| Gate 3 Financial Label Dictionary | exact published label IDs and meanings, immutable version identity, draft/diff/approval/publish-preparation lifecycle and deterministic full model view | source/canonical reads, target selection, provider execution, annotations, workflow or activation | [`Gate3FinancialLabelDictionaryFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate3_financial_label_dictionary.py) loading the exact-file-hash-pinned package resource; generated OpenWebUI Skill/Tool are inspection/delivery projections only | [Financial Label Dictionary v1](./BROKER_REPORTS_GATE3_FINANCIAL_LABEL_DICTIONARY.v1.md) | G3.C1 managed OpenWebUI binding and G3.4 composition | independently authored meaning in Prompt/Skill/Tool/Knowledge/renderer, RAG/lazy retrieval, mutable published version, registry, database or second publisher system |
| Gate 3 Bounded Labeling | pass-1 exact three-part model context, one sparse financial-type proposal, closed response validation and backend-only alias restoration | role binding, deterministic semantic classification, alias normalization, retry/repair/fallback, persistence, workflow or activation | [`Gate3BoundedLabelingFactory.create/create_from_chunk`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate3_bounded_labeling.py) using the existing `Gate2StructuredModelClientFactory.create` provider path | [Minimal Labeling v1](./BROKER_REPORTS_GATE3_MINIMAL_LABELING.v1.md), [Financial Label Dictionary v1](./BROKER_REPORTS_GATE3_FINANCIAL_LABEL_DICTIONARY.v1.md) and [Gate 3 Handoff v1](./BROKER_REPORTS_GATE3_HANDOFF.v1.md) | Gate 3 role pass through the batch owner | second prompt/dictionary/projection/validator/alias grammar, model-provided canonical refs, code-owned financial classifier or annotation storage |
| Gate 3 Financial Role Pack | exact role IDs/meanings, per-label required/optional profiles, literal source-value policy and maximum-one cardinality | financial labels, source reads, model execution, persistence or relations | [`Gate3FinancialRolePackFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate3_financial_role_pack.py) loading the exact hash-pinned package resource | [Role Labeling v1](./BROKER_REPORTS_GATE3_ROLE_LABELING.v1.md) and [Role Pack schema](./BROKER_REPORTS_GATE3_FINANCIAL_ROLE_PACK.v1.schema.json) | Gate 3 role pass and persistence validation | role/profile copies in Python, prompt, Skill, adapter, RAG, database or broker-specific mapping |
| Gate 3 Role Labeling | one pass-2 proposal for all validated pass-1 facts in a non-empty chunk, exact-alias restoration in pass-1 order, fact/label equality, allowed-role/cardinality checks, target restoration, literal `exact_text` validation, role-local source-binding rejection as explicit `missing`, exact known duplicated-alias fact rejection as all roles `missing`, and mechanical source-value resolution | relabeling, normalized/computed values, one call per fact, retry/repair/fallback, persistence, relations or Gate 4 | [`Gate3RoleLabelingFactory.create_from_chunk`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate3_role_labeling.py) plus `Gate3RoleValueResolverFactory.create/create_from_active_canonical` in the same module, reusing `Gate2StructuredModelClientFactory.create` and `CanonicalReaderFactory.create` | [Role Labeling v1](./BROKER_REPORTS_GATE3_ROLE_LABELING.v1.md), Role Pack and role-response schemas | batch owner, persistence and deterministic downstream code | selection among duplicated responses, missing/unknown-alias recovery, fuzzy/positional reconciliation, whole-chunk suppression for one source-invalid role, second projection/chunker/provider adapter, broker-column rules, normalized values, relation ontology or parallel sidecar |
| Gate 3 Chunk Batch Labeling | sequential pass 1 then pass 2 per selected chunk, pass-2 skip for empty pass 1, deterministic in-memory V2 merge, and separate chunk-execution versus source-fact completeness accounting | chunk boundaries, label/role meaning, provider adaptation, retry/repair, per-fact calls, persistence or activation | [`Gate3ChunkBatchLabelingFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate3_chunk_batch_labeling.py) calling the structural, bounded-label and role-label factories | [Chunk Batch Labeling v1](./BROKER_REPORTS_GATE3_CHUNK_BATCH_LABELING.v1.md), [Role Labeling v1](./BROKER_REPORTS_GATE3_ROLE_LABELING.v1.md) and [Structural Chunking v1](./BROKER_REPORTS_GATE3_STRUCTURAL_CHUNKING.v1.md) | NDFL product workflow plus retained proofs | second provider/validator/classifier, semantic deduplication, concurrency/retry infrastructure, persistence or product route |
| Gate 3 FinancialAnnotations Persistence | admission of a contract-valid machine-scoped result, including explicit role-incomplete facts; FULL save or non-destructive DEMAND_SCOPED recovery against one explicit current base; exact active canonical/dictionary/Role Pack/instruction/model/provider binding, repeated target/profile/literal and completeness-accounting checks, and immutable private full-current-view V2 sidecar save/read | labeling, canonical mutation, physical storage, retention/purge policy, generic merge/conflict framework, economic identity, workflow or activation | [`Gate3FinancialAnnotationsPersistenceFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate3_financial_annotations_persistence.py) delegating to `ArtifactStore` and `ArtifactResolver` | [Role Labeling v1](./BROKER_REPORTS_GATE3_ROLE_LABELING.v1.md), [Demand-Scoped Recovery v1](./BROKER_REPORTS_GATE3_DEMAND_SCOPED_RECOVERY.v1.md), [`FinancialAnnotationsV2`](./BROKER_REPORTS_FINANCIAL_ANNOTATIONS.v2.schema.json) and the existing Artifact Lifecycle contract | NDFL product workflow, Evidence Demand recovery and artifact-derived G3.6 readiness | demand delta masquerading as FULL, omission-as-delete, publication with rejected/provider-failed chunks, parallel V1/V2 current writes, second database/store/resolver, mutable overwrite, copied financial meaning, Gate 2 mutation or workflow state |
| Gate 3 NDFL Case Readiness | deterministic per-document/case readiness and fixed follow-up permissions derived from existing artifacts | Gate 3 semantic-system acceptance, persisted workflow state, labeling, financial meaning, tax decisions or Gate 4 execution | [`Gate3NdflCaseReadinessFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate3_ndfl_case_readiness.py) through `ArtifactResolver`, active canonical pointers and G3.5 reads | [NDFL Case Readiness v1](./BROKER_REPORTS_GATE3_NDFL_CASE_READINESS.v1.md) | inactive G3.6 downstream proof and corrected G3.7C case-status audit | caller tenant/case ids, cross-document labeling, phantom completion, second workflow owner/database or LLM-owned state |
| NDFL Gate 2 to Gate 3 Workflow | exact validated-manifest selection, compare-and-swap activation, full-document Gate 3 coordination and exact sidecar publication | canonical construction, projection/chunk/label meaning, provider adaptation, persistence mechanics, case-readiness meaning or Gate 4 | [`NdflWorkflowFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate3_ndfl_workflow.py), delegating every stage operation to its existing factory | [Gate 3 Handoff v1](./BROKER_REPORTS_GATE3_HANDOFF.v1.md), [Minimal Labeling v1](./BROKER_REPORTS_GATE3_MINIMAL_LABELING.v1.md) and exact-version sidecar contracts | stable-ID NDFL product route | Gate 2 calling Gate 3, copied canonical/text handoff, Pipe-to-Pipe chat, display-name routing, direct store read/write, retry/repair or second stage owner |
| Gate 4 Financial Case Fact Contract | one minimal immutable normalized-source-fact shape: deterministic identity, trusted case/chat binding, exact Gate 3/canonical/semantic-authority binding, typed role values with source literals, explicit missing and role completeness status | financial type/role meaning, source parsing, persistence, SQL, multi-document assembly, reconciliation, relations, tax logic, API or activation | [Gate 4 Financial Case Fact v2](./BROKER_REPORTS_GATE4_FINANCIAL_CASE_FACT.v2.md) and its closed schema | [Gate 4 Financial Case Fact v2](./BROKER_REPORTS_GATE4_FINANCIAL_CASE_FACT.v2.md) and [Source-Fact Domain Boundaries v1](./BROKER_REPORTS_SOURCE_FACT_DOMAIN_BOUNDARIES.v1.md) | current Gate 4 materializer/runtime and Gate 5 consumers through the official runtime | a second fact/locator/role schema, stripped semantic authority, historical Financial Domain activation, caller-owned case registry, new ACL/store, broker adapter or type/profile copy |
| Gate 4 Deterministic Materialization and SQL Cache | mechanical V2-sidecar-to-Fact-V2 projection, typed normalization, exact fact identity, same-ArtifactStore SQL projection, explicit scoped reads, rebuild and freshness/lifecycle enforcement | financial type/role meaning, source-format parsing, separate storage/ACL/case lifecycle, detail-total reconciliation, relations, tax logic, API or product activation | [`Gate4FinancialCaseMaterializerFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate4_financial_case_materialization.py) plus composed [`Gate4FinancialCaseRuntimeFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate4_financial_case_cache.py), reusing Gate 3 resolver/readiness and the existing ArtifactStore adapter | [Gate 4 SQL Materialization v1](./BROKER_REPORTS_GATE4_SQL_MATERIALIZATION.v1.md) and [Gate 4 Financial Case Fact v2](./BROKER_REPORTS_GATE4_FINANCIAL_CASE_FACT.v2.md) | ordinary deterministic Gate 4 code and Gate 5 consumers through the official runtime | second DB/store/resolver, caller tenant/case IDs, SQL-owned meaning, raw broker reads, provider/LLM calls, generic query language, reconciliation, relations or tax logic |
| Gate 4 Multi-Document Case Assembly | one deterministic current source set, whole-case rebuild/read, derived technical completeness and exact-generation freshness over all current Gate 3 V2 sidecars | financial interpretation, deduplication, reconciliation, relations, tax logic, persisted workflow state, separate storage/ACL/case lifecycle, API or product activation | [`Gate4FinancialCaseRuntimeFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate4_financial_case_cache.py), reusing Gate 3 readiness, the G4.2 materializer/cache and the existing ArtifactStore adapter | [Gate 4 Case Assembly v1](./BROKER_REPORTS_GATE4_CASE_ASSEMBLY.v1.md), [Gate 4 SQL Materialization v1](./BROKER_REPORTS_GATE4_SQL_MATERIALIZATION.v1.md) and [Gate 4 Financial Case Fact v2](./BROKER_REPORTS_GATE4_FINANCIAL_CASE_FACT.v2.md) | ordinary deterministic Gate 4 code and Gate 5 consumers through the official runtime | second source-set registry, new table/index/database, partial case generation, caller tenant/case IDs, content-based deduplication, reconciliation, LLM/provider calls, relations or tax logic |
| Gate 5 Methodology-Driven Selection | validate one external closed requirement list, select current Gate 4 facts by financial type and project requested roles with found/partial/missing accounting | tax calculation, Tax Model, methodology lifecycle/storage, supplemental facts, scenario policy, generic query language, relations or product activation | [`Gate5MethodologySelectionRuntimeFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate5_methodology_selection.py), composing `Gate4FinancialCaseRuntimeFactory.create` | [Gate 5 Methodology Selection v0](./BROKER_REPORTS_GATE5_METHODOLOGY_SELECTION.v0.md) | closed inactive G5.2 representative proof only | tax-specific control flow, copied Gate 4 facts/roles, direct source/canonical/Gate 3/SQL reads, second Repository/DB or generic rules/query framework |
| Gate 5 Supplemental Fact Persistence | validate one closed structured money input, bind it only to trusted `ArtifactAccessContext`, persist one private artifact and return found/missing through access-checked resolution | free-text extraction, question flow, tax calculation, Tax Case/Model, methodology lifecycle, merge/query semantics, relations or product activation | [`Gate5SupplementalFactRuntimeFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate5_supplemental_fact.py), using an `ArtifactStoreFactory.create` store and `ArtifactResolver.resolve` | [Gate 5 Supplemental Fact Persistence v0](./BROKER_REPORTS_GATE5_SUPPLEMENTAL_FACT_PERSISTENCE.v0.md) | inactive G5.3 representative persistence proof only | caller-owned scope identity, direct SQL/store implementation construction, Gate 4/Gate 3/canonical mutation, chat/Knowledge/LLM persistence, new DB/Repository/registry or generic fact/query engine |
| Gate 5 Combined Requirement Check | compose one closed external requirement through G5.2 Financial Case presence and G5.3 access-checked supplemental refs, then return satisfied/missing with exactly one tagged source | tax calculation, Tax Case/Model, methodology or supplemental lifecycle, discovery/rebinding, generic join/query, conflict resolution, relations or product activation | [`Gate5CombinedRequirementCheckRuntimeFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate5_combined_requirement_check.py), composing only the G5.2 and G5.3 factories | [Gate 5 Combined Requirement Check v0](./BROKER_REPORTS_GATE5_COMBINED_REQUIREMENT_CHECK.v0.md) | inactive G5.4 representative sufficiency proof only | direct Gate 4/store/SQL/source reads, caller scope identity, untagged value merge, new DB/table/Repository/registry, Tax Case or generic input/query engine |
| Gate 5 Supplemental Fact Discovery | derive eligible same-run supplemental refs from the trusted case catalog and delegate the unchanged combined requirement decision | supplemental write, cross-run rebinding/migration, tax calculation, Tax Case/Model, generic discovery/query, conflict resolution, relations or product activation | [`Gate5SupplementalFactDiscoveryRuntimeFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate5_supplemental_fact_discovery.py), composing `ArtifactResolver.catalog_case` and the G5.4 factory | [Gate 5 Supplemental Fact Discovery v0](./BROKER_REPORTS_GATE5_SUPPLEMENTAL_FACT_DISCOVERY.v0.md) | inactive G5.5 representative reopen/discovery proof only | caller artifact refs or scope identity, direct store/SQL/payload reads, new registry/index/table/DB, cross-run use, Tax Case or generic filter/query engine |
| Gate 5 Single-Input Human Loop | turn exactly one current G5.5 missing money requirement into a strict structured question/proposal, validate it deterministically, then delegate persistence and recheck to unchanged G5.3/G5.5 owners | scope/fact binding by the model, free-form output acceptance, multi-input interview, workflow state, tax calculation, Tax Case/Model, provider stack or product activation | [`Gate5SingleInputHumanLoopRuntimeFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate5_single_input_human_loop.py), using the existing `Gate2StructuredModelClientFactory.create` path and composing G5.3/G5.5 factories | [Gate 5 Single-Input Human Loop v0](./BROKER_REPORTS_GATE5_SINGLE_INPUT_HUMAN_LOOP.v0.md) | inactive G5.6 representative acquisition-cost proof only | model-visible trusted identities/artifact refs/full case, direct provider/store/Gate 4 access, retry/fallback/repair, new DB/registry/workflow/Tax Case or generic interview engine |
| Gate 5 Methodology-Selected Calculation | validate one experimental methodology projection, resolve its source-tagged inputs only through G5.5, dispatch one known behavior and return a hash/rule/provenance-bound deterministic result | methodology lifecycle/publication, tax-context selection, executable formulas, rates, payable tax, Tax Case, generic rule engine or product activation | [`Gate5MethodologyCalculationRuntimeFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate5_methodology_calculation.py), composing only `Gate5SupplementalFactDiscoveryRuntimeFactory.create` | [Gate 5 Methodology Calculation v0](./BROKER_REPORTS_GATE5_METHODOLOGY_CALCULATION.v0.md) | inactive G5.7 representative disposal net-result proof only | implicit scenario selection, unknown-behavior fallback, direct Gate 4/store/SQL/provider reads, LLM arithmetic, executable methodology, DSL/plugin/registry/DB/workflow/Tax Case |
| Gate 5 Trusted Methodology Authority | bind each closed published methodology identity/version to one exact repository package resource/hash/schema and resolve it without caller content; current authorities are `ru-3ndfl-2025-declaration-input-contract@2026.3-current-authority` and `ru-ndfl-securities-source-fact-consumption-proof@2026.7-current-authority`; older resources are historical references, never current selection or fallback | methodology CRUD/approval/lifecycle, effective-date/residency/tax-period selection, calculation behavior, case state, mutable OpenWebUI authoring or product activation | [`Gate5TrustedMethodologyAuthorityFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate5_trusted_methodology.py) and composed [`Gate5TrustedMethodologyCalculationRuntimeFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate5_trusted_methodology.py) | [Gate 5 Trusted Methodology Authority v0](./BROKER_REPORTS_GATE5_TRUSTED_METHODOLOGY_AUTHORITY.v0.md); behavior remains owned by the consuming G5.7, G5.13/G5.14 or G5.22 boundary | inactive G5.8 replay plus additive immutable G5.13/G5.14/G5.22 Tax Model versions only | caller-supplied methodology/hash/path, mutable same-version content, implicit default, direct Gate 4/supplemental/store/SQL/OpenWebUI/provider reads, new registry/DB/workflow/platform |
| Gate 5 Deterministic Source-Fact Consumption | consume complete normalized purchase/disposal facts, apply bounded date-ordered FIFO without stored event identity, select exact-target disposal charges, and preserve detail/aggregate assertions independently | source parsing, currency inference/conversion, partial acquisition commission, reconciliation, relation persistence, tax completeness or activation | [`Gate5DeterministicSourceFactConsumptionRuntimeFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate5_deterministic_source_fact_consumption.py) composes the historical Gate 4 runtime; active ordinary composition injects `Gate4OrdinaryTradeCandidateRuntimeFactory.create` into the same validated runtime through `OrdinaryTradeCandidateRuntimeFactory.create`; both use the trusted methodology authority | [Gate 5 Deterministic Source-Fact Consumption v0](./BROKER_REPORTS_GATE5_DETERMINISTIC_SOURCE_FACT_CONSUMPTION.v0.md) and [Source-Fact Domain Boundaries v1](./BROKER_REPORTS_SOURCE_FACT_DOMAIN_BOUNDARIES.v1.md) | active ordinary-trade source-fact assessment/consumption plus historical deterministic proof/Tax Model consumers | direct source/Canonical/Gate 3/Source Observation/SQL/provider reads, inferred currency/event/relation, aggregate allocation, reconciliation or second methodology/calculator/store |
| Gate 5 Real Tax Case Assembly | enumerate reviewed declaration demands, retain explicit A-E knowledge origins, attach only available normalized facts and deterministic calculations, and emit exact supplied-case blockers | source extraction, user/filer evidence acquisition, global reconciliation, event identity, taxpayer completeness, declaration release/XML or product activation | [`Gate5RealTaxCaseAssemblyRuntimeFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate5_real_tax_case_assembly.py), composing the deterministic source-fact consumer and existing declaration Definition/obligation-package factories | [Gate 5 Real Tax Case Assembly v0](./BROKER_REPORTS_GATE5_REAL_TAX_CASE_ASSEMBLY.v0.md), Deterministic Source-Fact Consumption v0 and Full Declaration Definition v1 | inactive G5.40F real-evidence assembly and exact-gap proof only | direct upstream/storage/provider reads, synthetic supplement in real mode, handwritten replacement obligation package, reconciliation, graph/relation persistence, new TaxCase database/workflow or activation |
| Gate 3 Metadata Source Adapter | retain exact explicitly labelled non-tax client/broker/account/period/tax-identifier observations from active canonical artifacts | Gate 4 reads, tax-case assembly, unlabelled entity-role inference, income-source/residency meaning or persistence | [`Gate3MetadataSourceFactRuntimeFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate3_metadata_source_facts.py), composing only `ArtifactResolver.catalog_case` and `CanonicalReaderFactory.create` | [Gate 5 Declaration Preparation v0](./BROKER_REPORTS_GATE5_DECLARATION_PREPARATION.v0.md) and [Source-Fact Domain Boundaries v1](./BROKER_REPORTS_SOURCE_FACT_DOMAIN_BOUNDARIES.v1.md) | Gate 5 evidence intake only | Gate 4 aggregation, generic metadata ontology, unlabeled broker/party guesses or tax meaning |
| Gate 5 Declaration Scope | resolve final supplied-case scope and activate the minimal intent/evidence demand subset as one decision domain over the trusted Full Definition | obligation/domain inventory, legal methodology, user dialog, projection or missing-as-not-applicable | [`Gate5DeclarationScopeResolutionRuntimeFactory.create` and `Gate5DeclarationScopeActivationRuntimeFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate5_declaration_scope_resolution.py) | [Cross-Gate Domain Ownership v1](./BROKER_REPORTS_CROSS_GATE_DOMAIN_OWNERSHIP.v1.md), Full Declaration Definition v1 and Supplied-case Completeness v1 | declaration preparation and sealed-package composition only | a second scope module, copied domain catalog, universal questionnaire or taxpayer-completeness claim |
| Gate 5 Human Fact Scope | build exact scope-bound Human requests, own immutable current-request publication and same-lane correction successors, normalize authenticated answers, validate calendar date and 12-digit INN before persistence, reject owner-visible conflicts and validate exact owner origin across runs in one case | authentication, authenticated taxpayer identity, tax/legal/source/external meaning, browser rendering, workflow state, declaration assembly or generic evidence | [`Gate5HumanGapClosureRuntimeFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate5_human_gap_closure.py), reusing `ArtifactResolver.resolve_case`; Issue #304 product composition supplies one owner-minted user+case+period workflow slot which is explicitly not taxpayer identity; the separate presentation adapter may propose wording but cannot publish, and only a later direct authenticated answer reaches this owner | [Gate 5 Human Fact Scope v1](./BROKER_REPORTS_GATE5_HUMAN_FACT_SCOPE.v1.md) | current Issue #304/#310 bounded interactive preparation and prior inactive publication/validation proofs | case hash as taxpayer, `user_id` or operation subject as taxpayer, caller-published/current-selected requests, browser-selected ref/fact key, timestamp/ref authority, conflict omission, free-text external authority, invalid date/INN persistence, v0 downgrade, presentation candidate publication, domain provider/LLM calls or new registry/workflow/receipt engine |
| Gate 5 Declaration Preparation | combine strict metadata and Gate 4 evidence contracts, review evidence coverage, consume the single scope owner, produce exact human/document actions, replay deterministically and expose readiness/proven target-independent values | source parsing, LLM tax decisions, raw-transaction dialog, universal questionnaire, new tax/projection/workflow/persistence owner, taxpayer completeness or XML/PDF release while blocked | [`Gate5EvidenceIntakeRuntimeFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate5_evidence_intake.py) and [`Gate5DeclarationPreparationRuntimeFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate5_declaration_preparation.py); the stable Pipe composes them only on the historical Gate 3 route | [Pipeline Gates v1](./BROKER_REPORTS_PIPELINE_GATES.v1.md), [Gate 5 Declaration Preparation v0](./BROKER_REPORTS_GATE5_DECLARATION_PREPARATION.v0.md), [Cross-Gate Domain Ownership v1](./BROKER_REPORTS_CROSS_GATE_DOMAIN_OWNERSHIP.v1.md) | retained fail-closed Gate 4 -> Gate 5 compatibility continuation; not the active ordinary-trade composition | direct SQL/source/provider reads, inferred source/residency/basis, stale LLM authority, manual target construction, reconciliation, transaction graph, generic engine, new TaxCase DB or synthetic product fallback |
| Gate 5 Declaration Model Assembly | audit the supported official consumer backward, release the exact minimal declaration-value set, project it without interpretation, and emit a value-by-value target-to-fact trace for one controlled profile | product activation, real-case completeness, legacy authority replacement, foreign/treaty completeness, new tax engine or projection framework | [`Gate5EndToEndFullTargetXmlRuntimeFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate5_end_to_end_full_target_xml.py) retains the historical G5.45 replay; [`ActiveCategoryDeclarationAssemblyRuntimeFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/active_category_declaration_assembly.py) is the additive inactive current-Fact composition and delegates every meaning to the existing owners | [Gate 5 Declaration Model Assembly v1](./BROKER_REPORTS_GATE5_DECLARATION_MODEL_ASSEMBLY.v1.md), [Active Category Declaration Assembly v0](./BROKER_REPORTS_ACTIVE_CATEGORY_DECLARATION_ASSEMBLY.v0.md), Declaration Semantic Input v0, Full-target XML Projection v0 and Evidence Interpretation Contracts v1 | inactive G5.45 and Issue #295 controlled proofs and safe audit evidence only | raw semantic bypass, projector calculation/default/inference, duplicate meaning owner, audit metadata as target input, real-case XML release or activation |
| Gate 5 External Evidence Routing | prove one declaration-required tax reference input is absent from Financial Case meaning, project a minimal research request and accept only an exact request/entity/effective/source-bound structured proposal over supplied authoritative bytes | web/browser/provider orchestration, semantic legal re-research, persistence, Tax Context/Model, methodology application, human fallback, generic source/reference platform or product activation | [`Gate5ExternalEvidenceRuntimeFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate5_external_evidence.py), composing only `Gate4FinancialCaseRuntimeFactory.create` for the read-only source audit | [Gate 5 External Evidence Routing v0](./BROKER_REPORTS_GATE5_EXTERNAL_EVIDENCE_ROUTING.v0.md) | inactive G5.11 representative 2025 group-02 rate-schedule proof only | document-semantic expansion, model-memory/snippet authority, direct broker/canonical/Gate 3/SQL reads, Supplemental Fact reuse, evidence-to-tax conclusion shortcut, new DB/registry/cache/workflow or generic research agent |
| Gate 5 Declaration Projection | resolve one exact published projection definition, consume values/traces validated by Declaration Semantics and mechanically emit a bounded declaration-shaped fragment with source/rule/evidence/target provenance | Tax Model/Methodology meaning, calculation, official-source research at case time, full XML/PDF, persistence, managed publication, generic form/XSD engine, GUI or product activation | current [`Gate5DeclarationProjectionRuntimeV1Factory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate5_declaration_projection.py), delegating semantic-input validation to `DeclarationSemanticsIncomeGroupRuntimeFactory.create`; historical v0 factory remains exact | [Gate 5 Declaration Projection v1](./BROKER_REPORTS_GATE5_DECLARATION_PROJECTION.v1.md), historical [v0](./BROKER_REPORTS_GATE5_DECLARATION_PROJECTION.v0.md), G5.22 Tax Model contract and SHA-pinned official evidence packs | inactive G5.24 proof: Appendix 8 remains executable and real G5.22 semantics project to one two-node Section 2 fragment | Tax Model imports, caller evidence/schema/path/code, calculation in PROJECT, dynamic import/registry, condition/expression/loop DSL, LLM/XSD/network/DB/Gate 4 use, best effort, full declaration or generic mapping framework |
| Gate 5 Declaration-Driven Tax Model | combine one trusted methodology with either G5.5-resolved case money or the factory-owned current source-fact result and a closed source-tagged prerequisite/context input, then produce one stable securities-disposal Tax Model; declaration adaptation remains a separate compatible method | annual aggregation, tax base/rate/tax, Tax Case/Model persistence, production evidence acquisition, full Tax Context, declaration codes/paths, XML/PDF, generic engine/DSL or product activation | [`Gate5SecuritiesDisposalTaxModelRuntimeFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate5_securities_disposal_tax_model.py) for the historical/full composition; additive `create_current_source_fact_operation` injects the factory-built active ordinary Fact v2 consumer without G5.5 discovery or G5.12 projection | [Gate 5 Declaration-Driven Tax Model v0](./BROKER_REPORTS_GATE5_DECLARATION_DRIVEN_TAX_MODEL.v0.md), [Deterministic Source-Fact Consumption v0](./BROKER_REPORTS_GATE5_DETERMINISTIC_SOURCE_FACT_CONSUMPTION.v0.md), G5.8, G5.5 and G5.12 | inactive G5.13/G5.14, G5.40D and Issue #293 proof seams only | caller-supplied consumption payload, direct Gate 4/supplemental/store/SQL/source/provider reads, hidden defaults, related-to-allowable shortcut, float/LLM arithmetic, declaration representation in Tax Model, new DB/repository/workflow/Tax Engine |
| Gate 5 Tax-Period Category Aggregation | validate one explicit taxpayer/category/period scope and a non-empty set of complete operation models, bind a user-verified completeness assertion to their exact deterministic member hashes, and aggregate stable semantics; projection is optional and owned separately | operation input discovery, category classification, expense allowability, tax base/rate/tax, persistence, cross-run rebinding, generic aggregation/query, full declaration or product activation | [`Gate5TaxPeriodCategoryAggregationRuntimeFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate5_tax_period_category_aggregation.py), composing G5.8 methodology authority and G5.12 projector; `run_tax_model` stops before projection and the compatible `run` delegates then projects only a complete scope | [Gate 5 Tax-Period Category Aggregation v1](./BROKER_REPORTS_GATE5_TAX_PERIOD_CATEGORY_AGGREGATION.v1.md), historical [v0](./BROKER_REPORTS_GATE5_TAX_PERIOD_CATEGORY_AGGREGATION.v0.md), G5.13 and G5.12 | inactive G5.23 and Issue #293 one-or-more-member proofs; one member still requires exact completeness evidence | treating one known operation as completeness, Gate 4 technical completeness as tax completeness, raw-fact aggregation, stale completeness after member change, mixed category/period/currency/loss, direct upstream/storage reads, LLM, DB, Tax Case or generic engine |
| Active Fact v2 to Category Tax Model bridge | compose the active ordinary Fact v2 consumer, existing operation Tax Model owner and existing category aggregation owner; bind member source scope to the returned case and independently bind operation subject plus category taxpayer scope through one explicit user-verified proof input; preserve exact results and expose typed bounded blockers/demands | source mapping, Fact v2 admission, FIFO, tax applicability/calculation, taxpayer inference, category aggregation, completeness authority, declaration projection or activation | [`OrdinaryTradeTaxModelBridgeRuntimeFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/ordinary_trade_tax_model_bridge.py), injecting `OrdinaryTradeCandidateRuntimeFactory.create` through the Tax Model factory seam and calling `run_tax_model`; acquisition-commission presence is queried from the source-fact owner for the exact selected disposal and its recognized acquisition source rows; the typed operation/taxpayer binding validator is owned by `Gate5TaxPeriodCategoryAggregationRuntimeFactory.create`, with the bridge retaining only a compatibility entrypoint | Gate 4 Fact v2, Deterministic Source-Fact Consumption v0, Declaration-Driven Tax Model v0 and Tax-Period Category Aggregation v1 | inactive/shadow Issue #293 bounded 2025 control only | equating operation subject with taxpayer identity, missing/foreign/misbound proof binding, foreign case rebinding, Canonical/Source Observation/Gate 3/historical SQL Gate 4/provider reads downstream, caller-built consumption results, copied calculation/aggregation, default zero, inferred event relations, declaration/XML or second authority |
| Active Category Tax Model to controlled declaration assembly | coordinate the Issue #293 current Fact v2 bridge with one shared right-side assembly owner and the existing Full Definition, Scope, Package, release, consumer projection and official-XSD owners; retain every upstream blocker or demand before release; prove one execution chain by comparing the Category member Operation hash, Tax Base Category-input hash, Package Scope snapshot and Package component snapshots before release | any source, tax, completeness, declaration-value or target meaning; real-case evidence; filing/download activation | [`ActiveCategoryDeclarationAssemblyRuntimeFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/active_category_declaration_assembly.py), constructing the ordinary Gate 4 runtime only at this composition boundary, injecting it into the additive Scope entrypoint, injecting Scope into Package, delegating right-side assembly to `Gate5DeclarationRightSideAssemblyRuntimeFactory.create` shared with G5.35, and checking only adjacency fields produced by the existing owners | [Active Category Declaration Assembly v0](./BROKER_REPORTS_ACTIVE_CATEGORY_DECLARATION_ASSEMBLY.v0.md), Gate 5 Declaration Model Assembly v1 and Supplied-case Completeness v1 | inactive/shadow Issue #295 synthetic 2025 RUB control only | prebuilt Tax Models/package/semantic input, caller raw visual data, direct taxpayer status, hidden demands, operation/taxpayer identity collapse, stale completeness, self-consistent receipt-only tamper, mix-and-match of individually valid artifacts from unrelated runs, direct category-to-XML bypass, Gate 3/historical SQL Gate 4/provider reads, projector interpretation, persistence, download or activation |
| Gate 5 Stable Income-Group Tax Base | validate one complete G5.14/G5.23 category Tax Model plus explicit user-verified whole-group income/reduction facts and exact input-bound completeness, then calculate a provenance-retaining stable income-group tax base through one published typed behavior | declaration group/code/line mapping, projection, rate or tax, case discovery/acquisition, persistence, XML/PDF, dynamic formulas, generic rules engine or product activation | [`Gate5IncomeGroupTaxBaseRuntimeFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate5_income_group_tax_base.py), composed only by the existing [`Gate5PublishedTypedBehaviorRuntimeFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate5_published_typed_behavior.py) and reusing G5.8 and category-aggregation validation owners | [Gate 5 Stable Income-Group Tax Base v0](./BROKER_REPORTS_GATE5_SECTION2_CALCULATION_SEMANTICS.v0.md), G5.8, [Category Aggregation v1](./BROKER_REPORTS_GATE5_TAX_PERIOD_CATEGORY_AGGREGATION.v1.md) and Runtime Capability Contract v2 | inactive G5.22 representative proof only; G5.23 changes accepted upstream cardinality, not this behavior | implicit zero/residency/completeness, stale input binding, declaration line/code/path in runtime/output, caller formula/schema/code, LLM arithmetic, direct upstream/store/SQL/provider reads, new capability/DB/workflow/Tax Engine |
| Gate 5 Runtime Capability Contract | publish five semantic case-time action families with inputs, preconditions, outputs, failures and provenance; v3 preserves four v2 members and version-replaces only PROJECT v0 with registered-input PROJECT v1 | Tax Methodology, Declaration Definition, authoring/compiler flow, tax/declaration rules, owner implementation details, dynamic behavior/schema/code loading, generic workflow/DSL or product activation | current v3 through [`Gate5RuntimeCapabilityContractV3Factory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate5_runtime_capabilities.py); exact v0/v1/v2 replay through their versioned factories; the PROJECT resolver delegates only to `Gate5DeclarationProjectionRuntimeV1Factory.create` | [Gate 5 Runtime Capability Contract v3](./BROKER_REPORTS_GATE5_RUNTIME_CAPABILITY_CONTRACT.v3.md), previous [v2](./BROKER_REPORTS_GATE5_RUNTIME_CAPABILITY_CONTRACT.v2.md), [v1](./BROKER_REPORTS_GATE5_RUNTIME_CAPABILITY_CONTRACT.v1.md) and [v0](./BROKER_REPORTS_GATE5_RUNTIME_CAPABILITY_CONTRACT.v0.md) with exact package resources | inactive unchanged five-family proof; Section 2 uses PROJECT v1 without a sixth capability and all previous bytes remain replayable | exporting every function/G5.x as a capability, exposing Python names to the model, declaration-specific new primitive, unregistered projection/behavior execution, caller schema/code/callable, unknown-ID guessing, contract/runtime drift, formulas/codes/paths, service registry, plugin platform or next-slice implementation |
| Gate 5 Declaration Definition Authoring | expose one exact six-section authoring payload, validate a bounded agent-authored securities Definition candidate against official evidence, G5.15 capabilities and published artifacts, and produce a static compilation report with typed gaps | blind model-evaluation claim, case-time execution/research, new capability/behavior, tax calculation, XML/PDF, publication, generic workflow/DSL, GUI or activation | [`Gate5DeclarationDefinitionAuthoringFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate5_declaration_definition.py), reusing the G5.15 contract/resolver, G5.8 methodology authority and G5.12 projection owner | [Gate 5 Declaration Definition Authoring v0](./BROKER_REPORTS_GATE5_DECLARATION_DEFINITION_AUTHORING.v0.md) and two exact package resources | inactive G5.16 structural authoring/validation proof; blind anti-bias trial not proven | free-form action/steps/formula/code/tool fields, unknown capability fallback, artifact guessing, declaration composition in Python, dynamic runner, generated methodology/capability or product route |
| Gate 5 Declaration Authoring Language | freeze and bias-audit exact history-free six-section v2 payloads; let the model author only official semantics and existing capability/behavior/artifact identities; derive exact wrapper/behavior contracts, aggregate status and no-case-evidence assessment in ordinary code | case-time execution, production model path, new runtime semantics, model-authored implementation contracts, expected-gap validation, candidate repair/selection, publication, GUI or activation | [`Gate5DeclarationAuthoringLanguageV2Factory`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate5_declaration_authoring_language.py) preserves G5.21 and additive `create_g522_replay`, `create_g523_replay`, `create_g524_replay` snapshots; all reuse the same evidence/schema/compiler owners | [Gate 5 Declaration Authoring Language v2](./BROKER_REPORTS_GATE5_DECLARATION_AUTHORING_LANGUAGE.v2.md), [Runtime Capability Contract v3](./BROKER_REPORTS_GATE5_RUNTIME_CAPABILITY_CONTRACT.v3.md), [Declaration Projection v1](./BROKER_REPORTS_GATE5_DECLARATION_PROJECTION.v1.md), previous authoring contracts and dated G5.19-G5.24 records | inactive G5.24 one-inference proof: both old Section 2 projection gaps are absent; exact candidate passes parser/schema/compiler with no repair and identifies complete electronic declaration assembly first; recorded candidate/cardinality semantics remain non-authoritative limitations | changing any frozen payload after inference, hiding pre-provider evidence, repair/cherry-picking/retry, direct application transport, expected requirement/gap IDs, manual candidate construction, promoting candidate prose to authority, new capability/DB/runner or implementation of the discovered dependent slice |
| Historical Financial Domain Consumer | checked consumption of the historical Financial Domain query API | current Gate 3 type/role route, current Gate 4 facts, Gate 1/Gate 2 storage, source parsing or domain snapshot mutation | `Gate3FinancialDomainContextFactory.create` | Query API and superseded global gate architecture | compatibility/history only | treating the historical consumer as current Gate 3 or Gate 4 authority |
| Qualification | frozen fixture/preflight and slot plan, terminal classification, metrics and product-gate evaluation | product contracts, provider-specific parsing or production admission | V6 qualification fixture/preflight factories, `qualify_financial_semantic_v6`, and additive `Gate2FinancialSemanticV6ContextV21BudgetSmokePlanFactory` / thin coordinator | V6 qualification harness, execution identity and [Context V2.1 Budget Model Smoke v1](./BROKER_REPORTS_GATE2_CONTEXT_V2_1_BUDGET_MODEL_SMOKE.v1.md) | qualification CLIs and Evidence | a parallel qualification framework |
| Evidence | exact private execution evidence, safe receipts, integrity and offline replay | product decisions, retries or canonical request construction | `Gate2FinancialSemanticV6DecisionEvidenceFactory.create`, additive Context V2.1 local/live success/failure methods, and their versioned restore/replay entrypoints | V6 Exact Evidence and [Context V2.1 Budget Model Smoke v1](./BROKER_REPORTS_GATE2_CONTEXT_V2_1_BUDGET_MODEL_SMOKE.v1.md) | Qualification and offline audit | evidence-driven product mutation or raw private Git evidence |
| Compatibility | version-pinned read dispatch and explicit legacy validation | silent rewrite, new writes, semantic policy or current product logic | financial-evidence and successor compatibility factories | pinned legacy/successor schemas | migration/local-proof tooling | reimplemented current authorities behind a legacy facade |

These domains are code responsibilities, not new product gates or packages.
One domain may coordinate several distinct operation authorities listed below;
that does not permit a second owner for any operation.

Rows using historical `Gate2*` or Gate 3 financial-semantic class/module names
below are legacy code-identity maps, not current release activation. Under
Pipeline Gates v1, LLM-friendly projection, sparse financial-type labeling and
source-bound role labeling belong to the retained Gate 3 responsibility
contour. They run only when that deployment-rollback path is explicitly
selected; `ordinary_trade_automatic_semantic_mapping_v1` does not call them. DOC33's
neutral reader-only renderer remains completeness proof
tooling, not a product or persisted stage output.
DOC27 likewise creates no Gate 3 projection and switches no background or
primary product consumer.

## Operation authority map

| Concern | Sole authority | Contract | Consumers | Compatibility | Forbidden duplicate |
| --- | --- | --- | --- | --- | --- |
| Gate 2 whole-document canonical construction | [`CanonicalNormalizerFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/canonical_artifact.py) consuming only Gate 1-authorized refs, FullSource outputs and validated table projections | [Pipeline Gates v1](./BROKER_REPORTS_PIPELINE_GATES.v1.md), [Canonical Artifact v1](./BROKER_REPORTS_CANONICAL_ARTIFACT.v1.md), [schema](./BROKER_REPORTS_CANONICAL_ARTIFACT.v1.schema.json) and [Gate 2 Exit Contract v1](./BROKER_REPORTS_GATE2_EXIT_CONTRACT.v1.md) | controlled Gate 2 shadow write and compare | `gate2_handoff_v0` remains product compatibility authority; DOC23/DOC24 are regression evidence, not runtime owners | a second schema/parser, financial fields, provider output as canonical authority or direct consumer construction |
| Gate 2 canonical version lifecycle and private read | [`CanonicalArtifactStoreFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/canonical_store.py) delegating to the ArtifactStore-created adapter; [`CanonicalReaderFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/canonical_store.py) stays disabled by default and is enabled only for explicit consumers | [Canonical Storage Lifecycle v1](./BROKER_REPORTS_CANONICAL_STORAGE_LIFECYCLE.v1.md), [Canonical Reader v1](./BROKER_REPORTS_CANONICAL_READER.v1.md) and [Gate 2 Exit Contract v1](./BROKER_REPORTS_GATE2_EXIT_CONTRACT.v1.md) | controlled shadow/storage proof and stable NDFL exact-manifest product route | immutable cross-run versions, chunks, CAS activation/rollback and receipts are additive; source and legacy handoff remain resolvable | direct SQLite/file access, caller tenant identity, overwrite, implicit promotion or reads outside an authorized consumer |
| Consumer-specific canonical compatibility read | [`Gate1ArtifactStoreCanonicalAdapterFactory`, `PdfCompactCanonicalAdapterFactory`, `LocalPdfCompactResearchCanonicalAdapterFactory` and `render_neutral_canonical_projection`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/canonical_consumer_migration.py), all consuming `CanonicalReaderFactory.create` output | [Canonical Reader v1](./BROKER_REPORTS_CANONICAL_READER.v1.md), [Gate 2 Exit Contract v1](./BROKER_REPORTS_GATE2_EXIT_CONTRACT.v1.md) and [Consumer Migration Matrix v1](./BROKER_REPORTS_GATE2_CONSUMER_MIGRATION_MATRIX.v1.md) | isolated Wave 0 tests, retained-cohort proof and six Wave 2 shadows | each mapping has one flag/output version; the neutral renderer is non-active proof-only; flag-off rollback restores external legacy authority without changing active pointer | direct store/component reads, format-branch consumer API, one global flag, private evidence, silent fallback or primary product use |
| Gate 3 current DTO meaning | [Minimal Labeling v1](./BROKER_REPORTS_GATE3_MINIMAL_LABELING.v1.md) plus [Role Labeling v1](./BROKER_REPORTS_GATE3_ROLE_LABELING.v1.md), shared target/projection, both response schemas and [`FinancialAnnotationsV2`](./BROKER_REPORTS_FINANCIAL_ANNOTATIONS.v2.schema.json) | [Pipeline Gates v1](./BROKER_REPORTS_PIPELINE_GATES.v1.md) and [Gate 3 Handoff v1](./BROKER_REPORTS_GATE3_HANDOFF.v1.md) | projection, type pass, role pass, persistence and NDFL workflow | V1 label-only payload remains historical and immutable; current writes use V2 | a second locator grammar, model-provided canonical refs, rewritten canonical source, parallel sidecar or Financial Domain on the current route |
| Gate 3 projection construction | [`Gate3ProjectionFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate3_projection.py) calling [`CanonicalReaderFactory.create().read_active_envelope`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/canonical_store.py) | [Minimal Labeling v1](./BROKER_REPORTS_GATE3_MINIMAL_LABELING.v1.md), [Gate 3 Handoff v1](./BROKER_REPORTS_GATE3_HANDOFF.v1.md) and [Canonical Reader v1](./BROKER_REPORTS_CANONICAL_READER.v1.md) | NDFL product workflow plus retained G3.2/G3.4 proofs | DOC33 neutral renderer remains independent proof tooling; no source-format or storage-layout branch | direct artifact input, a second alias issuer/renderer, raw/private reads, projection persistence, provider call or another product route |
| Gate 3 structural chunk construction | [`Gate3StructuralChunkFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate3_structural_chunking.py) reusing the exact package-internal structural plan of `Gate3ProjectionFactory` | [Structural Chunking v1](./BROKER_REPORTS_GATE3_STRUCTURAL_CHUNKING.v1.md), [Structural Chunk Set schema](./BROKER_REPORTS_GATE3_STRUCTURAL_CHUNK_SET.v1.schema.json) and [Gate 3 Handoff v1](./BROKER_REPORTS_GATE3_HANDOFF.v1.md) | NDFL product workflow plus retained G3.4B proofs | exact 60,000-character default bound, whole natural units first, contiguous whole-row groups only, zero data-row overlap and exactly-once existing target mappings | semantic/keyword filtering, second renderer/alias authority, tokenizer infrastructure, provider/batching/merge/persistence or another product route |
| Gate 3 financial-label dictionary lifecycle, rendering and managed binding | [`Gate3FinancialLabelDictionaryFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate3_financial_label_dictionary.py) loading [`gate3_financial_label_dictionary.v1.json`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate3_financial_label_dictionary.v1.json) through package resources and one exact file-hash pin; the deterministic managed-assets builder and stable-ID publisher project it to OpenWebUI | [Financial Label Dictionary v1](./BROKER_REPORTS_GATE3_FINANCIAL_LABEL_DICTIONARY.v1.md) and [Minimal Labeling v1](./BROKER_REPORTS_GATE3_MINIMAL_LABELING.v1.md) | G3.C1 operator inspection through Skill `broker-reports-financial-labels`, exact byte delivery through Tool `broker_reports_financial_label_dictionary`, and runtime context construction through the same factory | Skill is generated from the exact model view, Tool embeds the exact verified resource bytes, no Prompt carries definitions and Knowledge/RAG is absent | second meaning owner, name-based lookup, workspace path import, RAG/lazy load, unreviewed activation, overwrite, provider call or annotation persistence |
| Gate 3 bounded semantic-label proposal and validation | [`Gate3BoundedLabelingFactory.create/create_from_chunk`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate3_bounded_labeling.py) composing the exact projection/chunk, published dictionary, versioned minimal instruction and response schema, then calling the existing `Gate2StructuredModelClientFactory.create` seam | [Minimal Labeling v1](./BROKER_REPORTS_GATE3_MINIMAL_LABELING.v1.md), [Financial Label Dictionary v1](./BROKER_REPORTS_GATE3_FINANCIAL_LABEL_DICTIONARY.v1.md) and [Gate 3 Handoff v1](./BROKER_REPORTS_GATE3_HANDOFF.v1.md) | NDFL product workflow plus retained G3.4 proofs and human review | schema description and instruction project the sole G3.1/G3.2 alias grammar; empty annotations are valid; omissions remain non-claims; only exact validated aliases are restored | regex/keyword classifier, alias repair/extraction, copied dictionary meaning, hidden history/metadata, retry/repair/fallback, canonical refs from the model, persistence outside its owner or another product route |
| Gate 3 financial Role Pack | [`Gate3FinancialRolePackFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate3_financial_role_pack.py) over one hash-pinned package resource | [Role Labeling v1](./BROKER_REPORTS_GATE3_ROLE_LABELING.v1.md) and [Role Pack schema](./BROKER_REPORTS_GATE3_FINANCIAL_ROLE_PACK.v1.schema.json) | role pass and persistence | exact dictionary-label coverage is validated; model view is generated from the pack | role/profile definitions in Python, prompt, Skill, adapter, RAG or database |
| Gate 3 source-bound role proposal and validation | [`Gate3RoleLabelingFactory.create_from_chunk`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate3_role_labeling.py) and mechanical `Gate3RoleValueResolverFactory.create/create_from_active_canonical` in the same module | [Role Labeling v1](./BROKER_REPORTS_GATE3_ROLE_LABELING.v1.md), role response schema and FinancialAnnotationsV2 | batch, persistence and downstream deterministic code | uses the existing three-message request builder/adapter path and same chunk aliases; empty pass 1 skips provider; response order is non-authoritative; a known duplicated alias is discarded in full and its exact pass-1 fact retains only explicit missing roles | relabeling, normalized/computed values, duplicated-response selection, missing/unknown-alias recovery, fuzzy/positional reconciliation, broker-column rules, per-fact calls, retry/repair/fallback or Gate 4 logic |
| Gate 3 chunk batch labeling and merge | [`Gate3ChunkBatchLabelingFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate3_chunk_batch_labeling.py) over exact chunks, pass-1 bounded labeling and pass-2 role labeling | [Chunk Batch Labeling v1](./BROKER_REPORTS_GATE3_CHUNK_BATCH_LABELING.v1.md), [Role Labeling v1](./BROKER_REPORTS_GATE3_ROLE_LABELING.v1.md) and [Structural Chunking v1](./BROKER_REPORTS_GATE3_STRUCTURAL_CHUNKING.v1.md) | NDFL product workflow plus retained proofs | a selected subset is never complete; any pass rejection/failure makes the result incomplete; empty pass 1 skips pass 2; V2 merge preserves deterministic order | changed chunk/dictionary/Role Pack baseline, direct provider call, per-fact call, retry/repair/fallback, semantic dedup, concurrency, persistence outside its owner or another route |
| Gate 3 FinancialAnnotations sidecar save/read/recovery | [`Gate3FinancialAnnotationsPersistenceFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate3_financial_annotations_persistence.py), delegating record writes to the injected ArtifactStore, reads/access to `ArtifactResolver` and active canonical value checks to `Gate3RoleValueResolverFactory.create_from_active_canonical` | [Role Labeling v1](./BROKER_REPORTS_GATE3_ROLE_LABELING.v1.md), [Demand-Scoped Recovery v1](./BROKER_REPORTS_GATE3_DEMAND_SCOPED_RECOVERY.v1.md), [`FinancialAnnotationsV2`](./BROKER_REPORTS_FINANCIAL_ANNOTATIONS.v2.schema.json) and [Artifact Lifecycle](./BROKER_REPORTS_ARTIFACT_LIFECYCLE_CONTRACT.v0.md) | NDFL workflow, Evidence Demand recovery and artifact-derived readiness | FULL admits complete all-chunk V2; DEMAND_SCOPED requires an explicit current base and emits a new full current view with zero omission-driven deletes; historical V1 remains readable; fact and role targets, profiles and exact text are rechecked | direct SQLite/files, parallel V1 current write, new DB, partial/delta sidecar exposed to Gate 4, stale base, active-version mismatch, alias persistence, semantic repair or activation outside NDFL |
| Gate 3 NDFL case-readiness derivation | [`Gate3NdflCaseReadinessFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate3_ndfl_case_readiness.py), reading case metadata through `ArtifactResolver` and sidecars through the G3.5 owner | [NDFL Case Readiness v1](./BROKER_REPORTS_GATE3_NDFL_CASE_READINESS.v1.md), [Pipeline Gates v1](./BROKER_REPORTS_PIPELINE_GATES.v1.md) and ArtifactStore access scope | inactive G3.6 downstream proof and corrected G3.7C case-status audit | state is recomputed; only an exact current-canonical sidecar is ready; stale/incomplete records are explicit; declaration preparation is a fail-closed permission only; current-case completion is not Gate 3 system acceptance | direct SQL/files, caller-provided tenant/case identity, persisted state, event sourcing, cross-document labeling, provider call or Gate 4 execution |
| NDFL Gate 2 to Gate 3 handoff and execution | [`NdflWorkflowFactory.create().run_product_path`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate3_ndfl_workflow.py) resolving one exact manifest through `CanonicalReaderFactory.read_envelope`, compare-and-swap activating it when needed, calling `Gate3ChunkBatchLabelingFactory.create`, then `Gate3FinancialAnnotationsPersistenceFactory.create` | [Gate 3 Handoff v1](./BROKER_REPORTS_GATE3_HANDOFF.v1.md), [Minimal Labeling v1](./BROKER_REPORTS_GATE3_MINIMAL_LABELING.v1.md) and [NDFL Case Readiness v1](./BROKER_REPORTS_GATE3_NDFL_CASE_READINESS.v1.md) | single stable-ID NDFL product route plus exact-version tests | the exact manifest ref selects the Gate 2 result; only `document_id` plus authenticated `ArtifactAccessContext` enters downstream Gate 3; post-label version/root/payload equality is required | Gate 2 import/call, document payload transfer, direct ArtifactStore access, name lookup, Pipe-to-Pipe chat, incomplete persistence, retry/repair/fallback, another product route or Gate 4 |
| Gate 4 deterministic fact materialization | [`Gate4FinancialCaseMaterializerFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate4_financial_case_materialization.py), reading V2 through its persistence owner, resolving values through `Gate3RoleValueResolverFactory.create_from_active_canonical` and profiles through the exact Role Pack factory | [Gate 4 Financial Case Fact v2](./BROKER_REPORTS_GATE4_FINANCIAL_CASE_FACT.v2.md), [Gate 4 SQL Materialization v1](./BROKER_REPORTS_GATE4_SQL_MATERIALIZATION.v1.md) and [`FinancialAnnotationsV2`](./BROKER_REPORTS_FINANCIAL_ANNOTATIONS.v2.schema.json) | composed G4.2 runtime and direct ordinary-code materialization | exact semantic authority, ISO/DMY date and ungrouped dot/comma decimal grammars only; source literal remains exact; missing is preserved | source-format/broker adapters, label/role choice, guessed locale/grouping, copied profiles, LLM, reconciliation, relations or tax meaning |
| Gate 4 SQL cache rebuild and explicit reads | [`Gate4FinancialCaseRuntimeFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate4_financial_case_cache.py), composing the materializer and `Gate4FinancialCaseSqlCacheFactory.create` over the existing `SqliteArtifactStoreAdapter` | [Gate 4 SQL Materialization v1](./BROKER_REPORTS_GATE4_SQL_MATERIALIZATION.v1.md), [Gate 4 Financial Case Fact v2](./BROKER_REPORTS_GATE4_FINANCIAL_CASE_FACT.v2.md) and Artifact Lifecycle | ordinary code queries by case, fact ID, financial type, asset and period | exact current selection comes from `Gate3NdflCaseReadinessFactory`; cached generations fail closed; upstream lifecycle triggers delete projections; cache can be removed/rebuilt | second database, direct global DB handle, caller tenant/case scope, cache as source of truth, ORM/event store, generic query API, product route, reconciliation, relations or tax logic |
| Gate 4 whole-case assembly and read | [`Gate4FinancialCaseRuntimeFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate4_financial_case_cache.py), deriving the source set through `Gate3NdflCaseReadinessFactory`, materializing each exact ready binding through the G4.2 owner and replacing the case in one tenant-scoped transaction | [Gate 4 Case Assembly v1](./BROKER_REPORTS_GATE4_CASE_ASSEMBLY.v1.md), [Gate 4 SQL Materialization v1](./BROKER_REPORTS_GATE4_SQL_MATERIALIZATION.v1.md) and Artifact Lifecycle | ordinary code requiring the complete current technical case projection | source order is deterministic; a cache generation must equal the complete current ready binding tuple; incomplete/stale input fails closed; duplicate-looking facts retain distinct identities and provenance | new registry/table/index, partial replace, direct global DB handle, caller tenant/case scope, deduplication, reconciliation, relations, tax logic, provider/LLM calls or product route |
| Gate 5 methodology-driven Financial Case selection | [`Gate5MethodologySelectionRuntimeFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate5_methodology_selection.py), composing only `Gate4FinancialCaseRuntimeFactory.create` and iterating external requirements through `list_by_financial_type` | [Gate 5 Methodology Selection v0](./BROKER_REPORTS_GATE5_METHODOLOGY_SELECTION.v0.md) and [Gate 4 -> Gate 5 Handoff v1](./BROKER_REPORTS_GATE4_HANDOFF.v1.md) | closed inactive G5.2 representative disposal proof | requirement order is preserved; requested roles are projected from complete Gate 4 facts; zero facts are `missing`; absent roles are explicit; no methodology or result persistence | direct broker/canonical/Gate 3/SQL reads, financial-type branches, tax calculation, generic selector/query/relations, new store or product route |
| Gate 5 supplemental fact write/read | [`Gate5SupplementalFactRuntimeFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate5_supplemental_fact.py), accepting an existing `ArtifactStoreFactory.create` store, composing `ArtifactResolver`, and deriving storage scope only from `ArtifactAccessContext` | [Gate 5 Supplemental Fact Persistence v0](./BROKER_REPORTS_GATE5_SUPPLEMENTAL_FACT_PERSISTENCE.v0.md) and existing Artifact Lifecycle | inactive G5.3 acquisition-cost persistence proof | exact structured money input is stored as a private ArtifactStore payload; provenance is boundary-owned; reopen uses a new store/runtime instance; missing remains null and foreign scope is denied | caller scope fields, Gate 4 mutation, direct SQL or adapter construction, chat/LLM/Knowledge state, new store/table/registry, tax calculation or merged query engine |
| Gate 5 combined Financial Case + Supplemental Fact sufficiency check | [`Gate5CombinedRequirementCheckRuntimeFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate5_combined_requirement_check.py), composing `Gate5MethodologySelectionRuntimeFactory.create` and `Gate5SupplementalFactRuntimeFactory.create` under the same trusted context | [Gate 5 Combined Requirement Check v0](./BROKER_REPORTS_GATE5_COMBINED_REQUIREMENT_CHECK.v0.md), [Gate 5 Methodology Selection v0](./BROKER_REPORTS_GATE5_METHODOLOGY_SELECTION.v0.md) and [Gate 5 Supplemental Fact Persistence v0](./BROKER_REPORTS_GATE5_SUPPLEMENTAL_FACT_PERSISTENCE.v0.md) | inactive G5.4 acquisition-cost sufficiency proof | G5.2 `found` wins as tagged Financial Case source; otherwise exactly matching persistent supplemental fact may satisfy; missing remains explicit; cross-run rebinding is absent | direct upstream/storage reads, caller scope, value-origin erasure, conflict resolution, discovery/list API, generic join/query, Tax Case, write path or product route |
| Gate 5 trusted-case supplemental discovery before sufficiency check | [`Gate5SupplementalFactDiscoveryRuntimeFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate5_supplemental_fact_discovery.py), reading metadata through `ArtifactResolver.catalog_case`, filtering the trusted current run and delegating to G5.4 | [Gate 5 Supplemental Fact Discovery v0](./BROKER_REPORTS_GATE5_SUPPLEMENTAL_FACT_DISCOVERY.v0.md), [Gate 5 Combined Requirement Check v0](./BROKER_REPORTS_GATE5_COMBINED_REQUIREMENT_CHECK.v0.md) and Artifact Lifecycle | inactive G5.5 acquisition-cost reopen proof | caller supplies only methodology and trusted context; catalog metadata carries no payload; G5.3 re-resolves every selected ref; foreign scope and other runs cannot satisfy; provenance is unchanged | caller refs/scope fields, direct store/SQL/payload reads, registry/index/DB, cross-run rebinding, generic discovery/query, conflict resolution, Tax Case, write path or product route |
| Gate 5 one-missing-input structured human interaction | [`Gate5SingleInputHumanLoopRuntimeFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate5_single_input_human_loop.py), rerunning G5.5, calling the existing strict model client twice, validating answer evidence, delegating one write to G5.3 and rerunning G5.5 | [Gate 5 Single-Input Human Loop v0](./BROKER_REPORTS_GATE5_SINGLE_INPUT_HUMAN_LOOP.v0.md), G5.3 and G5.5 contracts | inactive G5.6 acquisition-cost proof | model sees only phase, financial type, value key/kind, currency requirement and the human answer; requirement/subject/scope/provenance remain deterministic; ambiguous input writes nothing | free-form model result, LLM-owned authority/persistence, trusted IDs in model context, direct provider/ArtifactStore/Gate 4 use, retry/fallback, interview workflow, Tax Case or multi-input engine |
| Gate 5 methodology-to-deterministic-calculation boundary | [`Gate5MethodologyCalculationRuntimeFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate5_methodology_calculation.py), validating a rule/behavior/input-binding projection, calling G5.5 once, resolving exactly one money value per semantic slot and executing one reviewed Decimal behavior | [Gate 5 Methodology Calculation v0](./BROKER_REPORTS_GATE5_METHODOLOGY_CALCULATION.v0.md), [G5.1 research](../../reports/2026-08-08/BROKER_REPORTS_GATE5_TAX_METHODOLOGY_BOUNDARY_G5_1.report.md) and G5.5 | inactive G5.7 disposal calculation proof | exact methodology hash plus rule/behavior identity and source-tagged inputs make replay explainable; new behavior requires explicit code and unknown behavior fails closed | formulas/code in methodology, implicit behavior, direct upstream/storage/provider access, float/LLM arithmetic, fallback, aggregation/allocation, generic DSL/engine/plugin/registry, Tax Case or write path |
| Gate 5 trusted-methodology resolution and calculation | [`Gate5TrustedMethodologyCalculationRuntimeFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate5_trusted_methodology.py), resolving a closed id/version reference through `Gate5TrustedMethodologyAuthorityFactory.create`, verifying exact raw resource SHA-256, delegating to unchanged G5.7 and checking the returned canonical projection binding | [Gate 5 Trusted Methodology Authority v0](./BROKER_REPORTS_GATE5_TRUSTED_METHODOLOGY_AUTHORITY.v0.md) and G5.7 | inactive G5.8 trusted replay proof | one id/version maps to one system-owned package resource/hash; caller controls only reference and existing trusted case context | caller methodology bytes/hash/path, same-version overwrite, implicit selection, direct source/storage/OpenWebUI/provider access, Methodology CRUD/lifecycle/DB/registry/platform |
| Gate 5 one-input external evidence routing and deterministic acceptance | [`Gate5ExternalEvidenceRuntimeFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate5_external_evidence.py), reading current facts only through `Gate4FinancialCaseRuntimeFactory.create`, emitting a scope-free research projection and binding a strict proposal to actual evidence-byte hashes | [Gate 5 External Evidence Routing v0](./BROKER_REPORTS_GATE5_EXTERNAL_EVIDENCE_ROUTING.v0.md) and [G5.10 declaration-backwards research](../../reports/2026-08-09/BROKER_REPORTS_GATE5_DECLARATION_BACKWARDS_TAX_MODEL_G5_10.report.md) | inactive G5.11 group-02 reference proof | one closed 2025 resident-securities rate requirement routes externally; official FNS page/procedure bytes produce a separate external fact; non-authoritative/conflicting/unresolved proposals produce no fact; persistence remains absent | web/provider execution, source content inferred from model memory, full-case model context, Gate 4 enrichment, Supplemental persistence, tax application, generic evidence/reference/query framework or product route |
| Gate 5 validated declaration-fragment projection | current [`Gate5DeclarationProjectionRuntimeV1Factory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate5_declaration_projection.py), resolving one static published definition and its exact SHA-pinned evidence before revalidating a registered semantic input and applying only closed data mappings; historical v0 remains replayable | [Gate 5 Declaration Projection v1](./BROKER_REPORTS_GATE5_DECLARATION_PROJECTION.v1.md), historical [v0](./BROKER_REPORTS_GATE5_DECLARATION_PROJECTION.v0.md) and G5.22 Tax Model contract | inactive G5.24 Appendix 8 plus Section 2 proof | real G5.22 values deterministically emit group `02` and six money fields; one source/rule/evidence/target trace per mapping; unknown ref, hash drift, missing/ambiguous mapping, classification mismatch or invalid upstream model fails closed; output is partial, not full XML | case-time LLM/research/XSD parse, target literals in executor, calculation, caller code/schema/path, full XML/PDF, persistence/publication, generic form engine, GUI or product route |
| Gate 5 first declaration-driven Tax Model slice | [`Gate5SecuritiesDisposalTaxModelRuntimeFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate5_securities_disposal_tax_model.py), resolving the additive G5.13 identity through G5.8, reading case values through G5.5, applying one reviewed Decimal behavior and sending a five-concept semantic projection to G5.12 | [Gate 5 Declaration-Driven Tax Model v0](./BROKER_REPORTS_GATE5_DECLARATION_DRIVEN_TAX_MODEL.v0.md), G5.8, G5.5 and G5.12 | inactive G5.13 one-disposal proof | stable category, complete-scope gross income, related/allowable separation, component decisions, explicit loss and provenance/assumption audit; identical input/methodology replays exactly; G5.12 emits the same fragment | annual aggregation, tax base/rate/tax, implicit market/IIS/loss/scope facts, direct upstream/storage reads, declaration identifiers in model, persistence, generic Tax Engine/DSL/context/reference framework |
| Gate 5 tax-period/category scope and aggregation | [`Gate5TaxPeriodCategoryAggregationRuntimeFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate5_tax_period_category_aggregation.py), validating a non-empty operation-model set through existing owners and delegating complete category semantics to the projection boundary; G5.13 `run_operation` creates each member without category-completeness meaning | [Gate 5 Tax-Period Category Aggregation v1](./BROKER_REPORTS_GATE5_TAX_PERIOD_CATEGORY_AGGREGATION.v1.md), historical [v0](./BROKER_REPORTS_GATE5_TAX_PERIOD_CATEGORY_AGGREGATION.v0.md), G5.13 and Declaration Projection v1 | inactive G5.23 one-or-more-operation proof | exact scope and sorted member-model hashes produce a deterministic binding; absent evidence returns known totals with `incomplete_scope`; an exact user-verified assertion admits one category model and projection; singleton follows the same path | raw Gate 4 aggregation, technical-to-tax completeness promotion, category/allowability/loss decisions in aggregator, stale assertion reuse, cross-run Supplemental rebinding, persistence, generic aggregation framework or product route |
| Gate 5 semantic capability publication and exact resolution | versioned resolver factories load exact SHA-pinned v0-v3 resources; v3 preserves the five-family basis, resolves typed execution through [`Gate5PublishedTypedBehaviorRuntimeFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate5_published_typed_behavior.py) and PROJECT v1 only through `Gate5DeclarationProjectionRuntimeV1Factory.create` | [Gate 5 Runtime Capability Contract v3](./BROKER_REPORTS_GATE5_RUNTIME_CAPABILITY_CONTRACT.v3.md), previous [v2](./BROKER_REPORTS_GATE5_RUNTIME_CAPABILITY_CONTRACT.v2.md), [v1](./BROKER_REPORTS_GATE5_RUNTIME_CAPABILITY_CONTRACT.v1.md) and [v0](./BROKER_REPORTS_GATE5_RUNTIME_CAPABILITY_CONTRACT.v0.md) | inactive G5.24 current capability proof; all prior resources replay exactly | four v2 members are structurally unchanged; PROJECT v1 accepts one registered projection ref/input and returns the v1 partial-fragment envelope; unknown/mismatched contracts, stale refs, malformed output, absent provenance and artifact hash drift fail closed | Python API export, runtime introspection, alias/fallback guessing, dynamic import/registration, caller schema or implementation, sixth declaration primitive, full-document runner, LLM compilation, workflow/rules DSL/platform or product route |
| Gate 5 Declaration Definition static validation | [`Gate5DeclarationDefinitionAuthoringFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate5_declaration_definition.py), loading hash-pinned context/candidate resources, injecting the unchanged G5.15 model projection, resolving artifact identities through existing owners and validating one-capability compilation units | [Gate 5 Declaration Definition Authoring v0](./BROKER_REPORTS_GATE5_DECLARATION_DEFINITION_AUTHORING.v0.md), G5.15, G5.8 and G5.12 | inactive G5.16 candidate/compilation proof only | target/evidence equality, proven case-time IDs, exact input/output compatibility, artifact-role resolution and gap consistency fail closed; payload is measured; candidate discloses non-blind trial boundary | workflow execution, composition ordering, case reads, model/provider call, generated capability/behavior/formula, Section 2 implementation, persistence/publication, GUI or product route |
| Gate 5 full root Declaration Definition authoring and trusted publication | [`Gate5FullDeclarationDefinitionAuthoringFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate5_full_declaration_definition.py) replays the hash-pinned reviewed obligation package and one frozen clean payload, derives policy/evidence audit from exact obligation refs and validates the immutable candidate; `Gate5FullDeclarationDefinitionCandidateFactory.create` exposes untrusted evidence; `Gate5TrustedFullDeclarationDefinitionAuthorityFactory.create` is the sole publication/resolution gate | current [Gate 5 Full Declaration Definition Authoring v1](./BROKER_REPORTS_GATE5_FULL_DECLARATION_DEFINITION.v1.md), historical rejected [v0](./BROKER_REPORTS_GATE5_FULL_DECLARATION_DEFINITION.v0.md) and current bounded component contracts | inactive G5.28B `PROVEN`; exact Definition is repository-published and resolvable by ID/version/hash; G5.29 consumes it through the additive trusted `resolve_for_scope` read | all 25 reviewed obligations occur exactly once; no expected partition exists; one policy per domain, component scope/coverage, target/runtime rejection and package/candidate/validation/review hashes fail closed; bounded review accepts coherent aggregates that retain member variants | case-time decision ownership, expected-domain prompt, provider retry/repair/best-of, XML/PDF/layout, formula/predicate/workflow, missing filing/component implementation, DB/service/registry or product activation |
| Gate 5 Definition-driven Declaration scope resolution | [`Gate5DeclarationScopeResolutionRuntimeFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate5_declaration_scope_resolution.py) retains the historical Gate 4 reader; additive `create_current_source_fact_scope` accepts an injected validated current-Fact runtime/source boundary and uses the category-owner typed taxpayer binding while keeping operation subject distinct from taxpayer scope; the module imports no ordinary bridge or Gate 4 ordinary factory | current [Supplied-case Completeness v1](./BROKER_REPORTS_GATE5_SUPPLIED_CASE_COMPLETENESS.v1.md), historical [Scope Resolution v0](./BROKER_REPORTS_GATE5_DECLARATION_SCOPE_RESOLUTION.v0.md), Active Category Declaration Assembly v0, G5.28B and Gate 4 Fact v2 | inactive G5.32-corrected and Issue #295 current-Fact scope receipts | mandatory and positive evidence activate; an exact current fact binds typed evidence; empty conditional evidence becomes `NOT_ACTIVATED_FOR_SUPPLIED_CASE`; no real-world absence is asserted; every decision, source and identity binding is hash-bound | ordinary-domain construction/imports, copied domain/policy list, operation-subject/taxpayer equality, universal questionnaire, caller missing-source flag, current-input absence as taxpayer-period absence, direct SQL/Gate 3/canonical reads, LLM authority, new DB/rules engine, Declaration Model, PROJECT or product route |
| Gate 5 Definition-bound resolved Declaration package completeness | [`Gate5ResolvedDeclarationPackageRuntimeFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate5_resolved_declaration_package.py) retains historical assembly; additive `create_current_source_fact_package` accepts the injected current-Fact Scope owner and validates identity through the category authority; `create_validation_only` exposes the sealed-byte validator without upstream reads; the module imports no ordinary bridge or Gate 4 ordinary factory | current [Supplied-case Completeness v1](./BROKER_REPORTS_GATE5_SUPPLIED_CASE_COMPLETENESS.v1.md), historical [Resolved Declaration Package v0](./BROKER_REPORTS_GATE5_RESOLVED_DECLARATION_PACKAGE.v0.md), Active Category Declaration Assembly v0, G5.28B and typed-component contracts | inactive G5.32 and Issue #295 supplied-case package proofs | all 11 Definition domains are accounted once; current receipts retain the separate operation/taxpayer binding; exact and bounded coverage remain distinct; completeness explicitly disclaims real-world taxpayer completeness | ordinary-domain construction/imports, applicability recalculation, operation-subject/taxpayer equality, Gate 4/SQL/Gate 3/canonical/ArtifactStore value reads, bounded-to-exact promotion, orphan/ambiguous components, new DB/registry/graph/primitive, Declaration Model flattening, PROJECT or product route |
| Gate 5 autonomous Definition-driven blocker closure | unchanged G5.28B Definition plus the corrected scope/package chain and repository-owned exact component validators | historical [G5.31 blocker-loop report](../../reports/2026-08-11/BROKER_REPORTS_GATE5_AUTONOMOUS_BLOCKER_CLOSURE_G5_31.report.md) and current [Supplied-case Completeness v1](./BROKER_REPORTS_GATE5_SUPPLIED_CASE_COMPLETENESS.v1.md) | G5.31 `STRATEGIC_STOP` retained as research-scar evidence; superseded by G5.32 result | G5.31 usefully exposed four missing exact owners but incorrectly promoted empty conditional evidence into universal unresolved questions; G5.32 corrects that interpretation without changing the Definition | treating the historical stop as current authority, declarant denial under typed-legal policy, real-world absence claims, generic classifier/questionnaire/workflow, Definition rewrite or activation |
| Gate 5 supplied-case financial-investment exact component | [`Gate5DeclarationFinancialInvestmentResultsRuntimeFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate5_declaration_financial_investment_results.py), validating each native category through `Gate5TaxPeriodCategoryAggregationRuntimeFactory.create` and exposing exact obligation accounting to the existing package owner | [Supplied-case Completeness v1](./BROKER_REPORTS_GATE5_SUPPLIED_CASE_COMPLETENESS.v1.md) and [G5.32 correction report](../../reports/2026-08-11/BROKER_REPORTS_GATE5_SUPPLIED_CASE_COMPLETENESS_G5_32.report.md) | inactive G5.32 exact-root synthetic proof; representative status `DECLARATION_COMPLETE_FOR_SUPPLIED_CASE` | supplied securities evidence resolves its obligation; digital-asset/right and partnership obligations remain explicitly not activated for the supplied case; manifest, scope, category hashes and false real-world-absence flag are validated | raw operation reimplementation, hidden source reads, global absence/tax-completeness claim, bounded-model promotion, new primitive/DB/registry/rules engine, PROJECT/XML/PDF or activation |
| Gate 5 target-independent Declaration semantic input | [`Gate5DeclarationSemanticInputRuntimeFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate5_declaration_semantic_input.py), validating only a sealed complete Package through `Gate5ResolvedDeclarationPackageRuntimeFactory.create_validation_only` and selecting semantic result fields from its native exact-root components | [Declaration Semantic Input v0](./BROKER_REPORTS_GATE5_DECLARATION_SEMANTIC_INPUT.v0.md), [Supplied-case Completeness v1](./BROKER_REPORTS_GATE5_SUPPLIED_CASE_COMPLETENESS.v1.md) and G5.32 package/component contracts | inactive G5.33 H2 proof; terminal status `DECLARATION_SEMANTIC_INPUT_READY` | all 11 domains and 25 obligations remain accounted; five resolved result payloads and six explicit not-activated meanings are exposed without input snapshots, methodology, provenance, receipt, owner, diagnostic or target-locator mechanics; supplied-case disclaimer and Package/component hash links remain sealed | tax calculation/applicability/source/component decisions, Gate 4/SQL/ArtifactStore/document/provider reads, bounded promotion, flattened Form DTO, target locators, new Declaration Model authority/framework, PROJECT/XML/PDF or activation |
| Gate 5 full-target 3-NDFL XML projection | [`Gate5FullTargetXmlProjectionRuntimeFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate5_full_target_xml_projection.py), resolving one exact hash-pinned full-target Definition, validating the G5.33 semantic input through its factory, constructing the XML tree generically, serializing representation-only and validating serialized bytes against the packaged official XSD | [Full-target XML Projection v0](./BROKER_REPORTS_GATE5_FULL_TARGET_XML_PROJECTION.v0.md), G5.33 and the official FNS order/procedure/format/XSD evidence | inactive G5.34 supplied-case proof; terminal status `FULL_TARGET_XML_VALID` | 25/25 obligation outcomes are accounted, 49 mappings are definition-owned, the XML is byte-deterministic for identical input/Definition/serializer, mapping and XSD proofs pass independently, and the final receipt binds XML to Projection Definition, semantic input, Full Declaration Definition and package hashes | target literals or tax decisions in Python, fragment composition, case-time Gate 4/ArtifactStore/document/provider/LLM/network reads, manual repair/defaults, PDF, filing, product activation, new registry/framework or dependent Gate goal |
| Gate 5 authenticated supplied source to full-target XML composition proof | [`Gate5EndToEndFullTargetXmlRuntimeFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate5_end_to_end_full_target_xml.py), composing the existing Gate 1 normalizer/persistence, Gate 2 reader, Gate 3 labeling/persistence, Gate 4 Financial Case and trusted Gate 5 factories, using the shared `Gate5DeclarationRightSideAssemblyRuntimeFactory.create` for right-side tax-base/component assembly, then delegating the target boundary unchanged to G5.34 | [End-to-End Full-target XML v0](./BROKER_REPORTS_GATE5_END_TO_END_FULL_TARGET_XML.v0.md), G5.34 and the safe [G5.35 receipt](../../reports/2026-08-11/BROKER_REPORTS_GATE5_END_TO_END_FULL_TARGET_XML_G5_35.receipt.safe.json) | inactive G5.35 synthetic supplied-case proof; terminal status `END_TO_END_FULL_TARGET_XML_VALID` | replay begins with authenticated hash-bound source bytes; genuine filing facts enter through a separate synthetic case boundary; direct income-group/filing taxpayer status is rejected; a 16-stage chain binds source through official XSD; same bound semantic inputs produce byte-identical XML; missing source, missing case fact and sealed-stage tamper fail closed | duplicated right-side assembly, prebuilt Gate 4/Tax Model/Scope/Package/Semantic Input fixtures, SQL as API, target literals or manual XML in the orchestrator, case-time LLM tax authority, universal questionnaire, second pipeline, PDF, filing or product activation |
| Historical Gate 5 OpenWebUI synthetic product proof | [`Gate5OpenWebUIProductRuntimeFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate5_openwebui_product.py) and `Gate5EndToEndFullTargetXmlRuntimeFactory.create` | [Real OpenWebUI Product Path v0](./BROKER_REPORTS_GATE5_REAL_OPENWEBUI_PRODUCT_PATH.v0.md), G5.35, and the safe [G5.36 receipt](../../reports/2026-08-11/BROKER_REPORTS_GATE5_REAL_OPENWEBUI_PRODUCT_PATH_G5_36.receipt.safe.json) | historical controlled-staging proof; inactive, absent from the product bundle and not a fallback | preserves exact historical evidence only | re-entry from the current Pipe, hidden supplied-case facts, synthetic-as-real release or use as a fallback |
| Gate 5 broker-report coverage expansion loop | the existing `Gate1Normalizer` / `persist_gate1_result` / `NdflWorkflowFactory.run_product_path` route plus [`Gate5OpenWebUIProductRuntimeFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate5_openwebui_product.py); G5.35 owns the exact-one UTF-8-or-canonical-base64 source envelope | [Coverage Expansion Loop v0](./BROKER_REPORTS_GATE5_COVERAGE_EXPANSION_LOOP.v0.md), versioned [`g537_coverage_corpus.v0.json`](../../../services/broker-reports-gate1-proof/tests/fixtures/g537_coverage_corpus.v0.json), and safe [G5.37 receipt](../../reports/2026-08-11/BROKER_REPORTS_GATE5_COVERAGE_EXPANSION_G5_37.receipt.safe.json) | G5.37 first wave proven; terminal `COVERAGE_EXPANSION_LOOP_PROVEN`; inactive after proof | CSV/HTML/XLSX disposal representations converge to equivalent Gate 4/declaration semantics; XLSX passes live product XML/XSD; official public PDF reaches Gate 3 then stops on honest incomplete purchase roles; G5.36 baseline remains valid | broker adapters, broker/source vocabulary below Gate 4, a second parser/product/tax/XML path, validator weakening, defaulted missing values, synthetic-as-real claims, speculative purchase Tax Model/Declaration changes, production activation or all-brokers claim |
| Historical Gate 5 related-event experiment | no current runtime owner; `Gate5RelatedSecuritiesEventsRuntime` was removed by G5.40C | historical [First Real Economic Coverage v0](./BROKER_REPORTS_GATE5_FIRST_REAL_ECONOMIC_COVERAGE.v0.md), G5.39/G5.39R evidence and current [Source-Fact Domain Boundaries v1](./BROKER_REPORTS_SOURCE_FACT_DOMAIN_BOUNDARIES.v1.md) | `OVERINTERPRETATION_REMOVED`; historical evidence only | structural proximity and matching date/asset/quantity are not financial-event identity; the supported declaration replay consumes explicit supplemental inputs and fails closed when absent | reintroducing inferred relations, FIFO, partial allocation, first-match selection, arbitrary charge eligibility, repair, retry/best-of-N, private cross-case copying or production activation |
| Prompt ownership | [`financial_semantic_v6_prompt`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate2_financial_semantic_v6_prompt.py) | [V6 Choice](./BROKER_REPORTS_GATE2_FINANCIAL_SEMANTIC_CHOICE_V6.md) | request builder, qualification | version-pinned older prompts only | semantic instruction in request, adapter or runner |
| Managed model-facing asset-family identity and composition | additive [`broker_reports_financial_domain_assets.v3.manifest.json`](../../../services/broker-reports-gate1-proof/managed_assets/broker_reports_financial_domain_assets.v3.manifest.json), immutable v1/v2 predecessors, their one deterministic builder and single closed-world `load_gate2_financial_semantic_model_assets` entrypoint | [OpenWebUI Financial Domain Asset Family v3](./BROKER_REPORTS_OPENWEBUI_FINANCIAL_DOMAIN_ASSET_FAMILY.v3.md), historical [family v2](./BROKER_REPORTS_OPENWEBUI_FINANCIAL_DOMAIN_ASSET_FAMILY.v2.md) and [Outcome Taxonomy v1](./BROKER_REPORTS_GATE2_OUTCOME_TAXONOMY.v1.md) | active v1 consumers, historical non-active Context V2.0 assets and the non-active GOAL 7 minimal managed profile | family v1/v2 and Context V2.0 remain immutable; family v3 packages catalog v2 and identifies one transport-ineligible profile without changing full Pack/catalog bytes | parallel asset-family/manifest authority, in-place historical manifest rewrite, second catalog loader, financial-semantic registry, custom asset GUI or adapter-owned semantic text |
| Human decision-reason meaning | immutable historical [`broker_reports_gate2_financial_decision_reason_catalog.v1.json`](../../../services/broker-reports-gate1-proof/managed_assets/decision_reasons/broker_reports_gate2_financial_decision_reason_catalog.v1.json) plus additive inactive [`broker_reports_gate2_financial_decision_reason_catalog.v2.json`](../../../services/broker-reports-gate1-proof/managed_assets/decision_reasons/broker_reports_gate2_financial_decision_reason_catalog.v2.json), each under the same catalog ID and versioned validator boundary | [Financial Decision Reason Catalog v1](./BROKER_REPORTS_GATE2_FINANCIAL_DECISION_REASON_CATALOG.v1.md), [Outcome Taxonomy v1](./BROKER_REPORTS_GATE2_OUTCOME_TAXONOMY.v1.md) and [family v3](./BROKER_REPORTS_OPENWEBUI_FINANCIAL_DOMAIN_ASSET_FAMILY.v3.md) | v1 remains the historical non-active [Context V2.0 candidate](./BROKER_REPORTS_GATE2_LLM_SEMANTIC_CONTEXT.v2.md); family v3 packages v2 for the inactive minimal projection and Choice-owned V2.1 profile | active V6 decision/Choice still accepts only two reasons; the inactive [Local Choice V2.1](./BROKER_REPORTS_GATE2_FINANCIAL_SEMANTIC_LOCAL_CHOICE.v2.1.md) accepts all three without activation | human wording in Python, Prompt, Packet, adapter, report projector, Pack, an in-place catalog edit or a second active catalog/loader |
| Model-visible semantic context | [`Gate2FinancialSemanticV6PacketFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate2_financial_semantic_v6_packet.py); managed Pack/reason subprojection remains [`Gate2FinancialSemanticV5ProjectionFactory`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate2_financial_semantic_v5_projection.py) | implemented historical [LLM Semantic Context v1](./BROKER_REPORTS_GATE2_LLM_SEMANTIC_CONTEXT.v1.md), historical non-active [Context V2.0](./BROKER_REPORTS_GATE2_LLM_SEMANTIC_CONTEXT.v2.md), current non-active [Context V2.1](./BROKER_REPORTS_GATE2_LLM_SEMANTIC_CONTEXT.v2.1.md), [Minimal Model Surface](./BROKER_REPORTS_GATE2_MINIMAL_MODEL_SURFACE.v1.md), and [current V6 Packet](./BROKER_REPORTS_GATE2_FINANCIAL_SEMANTIC_PACKET_V6.md) | the historical active request-builder path consumes only active `packet.payload`; the current Packet path builds one V2.1 candidate plus private exact receipt from the GOAL 7 projection; inactive Choice/Linter paths and the additive zero-call request-builder proof path consume exact V2.1 artifacts | V2.1 candidate, Choice profile, sealed provider-neutral request and local provider projections are all `active=false` and transport-ineligible; current four-block V6 packet stays exact | second Packet/context/projection builder, per-request historical V2.0 construction, unallowlisted model-visible field or provider-side semantic context rewrite |
| Complete model-visible request lint | [`Gate2FinancialSemanticV6ContextLinterFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate2_financial_semantic_v6_context_linter.py) for historical Slim plus additive [`create_context_v2_1`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate2_financial_semantic_v6_context_linter.py) under the same authority | implemented [LLM Semantic Context v1](./BROKER_REPORTS_GATE2_LLM_SEMANTIC_CONTEXT.v1.md)/[Local Choice v1](./BROKER_REPORTS_GATE2_FINANCIAL_SEMANTIC_LOCAL_CHOICE.v1.md) and current non-active [Context V2.1](./BROKER_REPORTS_GATE2_LLM_SEMANTIC_CONTEXT.v2.1.md) constrained by the [Minimal Model Surface](./BROKER_REPORTS_GATE2_MINIMAL_MODEL_SURFACE.v1.md) and [Local Choice V2.1](./BROKER_REPORTS_GATE2_FINANCIAL_SEMANTIC_LOCAL_CHOICE.v2.1.md) | exact version-pinned provider-neutral request before provider projection/transport | historical `create` unchanged; `create_context_v2_1` consumes exact Prompt, candidate, private mapping receipt and Choice-owned schema, then emits a private sealed-request receipt without inventing schema | direct candidate transport, a second packet/Choice/linter authority, context repair, an unsealed request, a linter that cements V2.0, or linter-built/invented Choice schema |
| Provider transport-request construction | [`Gate2OpenWebUIRequestBuilder.build`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate2_model_requests.py) plus additive `build_from_sealed_context_v2_1` under the same owner | provider/model request profiles consuming an already linted logical request | structured model client; GOAL 11 zero-call proof; GOAL 12 immutable plan/client | historical profiles validate then delegate; local proof remains transport-ineligible; the GOAL 12 profile attaches only its frozen exact model ID and `stream=false` before budget/adapter controls | direct `form_data` assembly in evidence or qualification, or provider fields added by the Context Linter |
| Provider response-format projection | [`Gate2ProviderAdapterFactory.create`, adapter `prepare_form_data`, and `Gate2PreparedProviderRequest.validate_schema_binding`/`canonical_schema_is_bound` plus versioned Context V2.1 binding methods](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate2_provider_adapters.py) | canonical choice schema projected to the provider-supported subset | structured model client; GOAL 11 zero-call proof; GOAL 12 immutable plan/evidence replay | provider profile selects one adapter; each Context V2.1 binding rebuilds the complete request through the canonical builder, budget where applicable and exact repository adapter/profile, then requires whole-object equality across messages, model, top-level shape, metadata, complete schema projection, wrapper/name/strictness, transform count and hashes | provider-layout parsing or schema rewrites in request, qualification, evidence, report or build code |
| Provider response parsing | [`Gate2ProviderAdapterFactory.create`, legacy adapter `extract_content` / `provider_error_code`, and versioned Context V2.1 prepared-content methods](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate2_provider_adapters.py) | [`Gate2StructuredModelResult`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate2_model_contracts.py) or exact Context V2.1 candidate content | structured model client; GOAL 11 zero-call proof; GOAL 12 live evidence path | legacy active extraction is unchanged; candidate extraction first proves exact prepared-request binding and requires one terminal envelope: `finish_reason=stop` for OpenAI/Google or `stop_reason=end_turn` for Anthropic | provider payload parsing in qualification or product code, or candidate extraction from an unbound/non-terminal/multiple-result envelope |
| Provider usage normalization | [adapter `execution_metadata`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate2_provider_adapters.py) | [`Gate2ProviderExecutionMetadata`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate2_model_contracts.py) | model client, budget, evidence | adapter normalizes provider variants | provider token-field reads outside adapters |
| Budget admission/accounting | [`Gate2EconomyBudgetSessionFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate2_economy_budget.py) | economy budget v1 code contract | structured model client | none | token or cost policy in callers/adapters |
| Semantic Pack meaning | [`Gate2FinancialSemanticContractFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate2_financial_semantic_contract.py) | [Financial Semantic Pack](./BROKER_REPORTS_FINANCIAL_SEMANTIC_PACK.v1.md) | projection, compiler, validator, materializer, Financial Domain | V5-named projection is shared by V6 | financial type IDs, roles or ambiguity rules in Python |
| Evidence Bundle | [`Gate2FinancialEvidenceBundleFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate2_financial_semantic_v6_bundle.py) | [Evidence Bundle](./BROKER_REPORTS_GATE2_FINANCIAL_EVIDENCE_BUNDLE.v1.md) | compiler, packet, expansion, replay | none | second sealed source/provenance projection |
| Typed Option compilation | [`Gate2FinancialCandidateCompilerFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate2_financial_semantic_v6_candidate_compiler.py) using [`Gate2FinancialTypedOptionFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate2_financial_semantic_v6_typed_option.py) | [Candidate Compiler](./BROKER_REPORTS_GATE2_FINANCIAL_CANDIDATE_COMPILER.v1.md), [Typed Option](./BROKER_REPORTS_GATE2_FINANCIAL_TYPED_OPTION.v1.md) | packet, qualification, replay | none | financial regex, known type IDs or provider-built options |
| Semantic choice | [`Gate2FinancialSemanticV6ChoiceContractFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate2_financial_semantic_v6_choice.py) | active [V6 Choice](./BROKER_REPORTS_GATE2_FINANCIAL_SEMANTIC_CHOICE_V6.md), historical [Local Choice v1](./BROKER_REPORTS_GATE2_FINANCIAL_SEMANTIC_LOCAL_CHOICE.v1.md), inactive [Local Choice V2.1](./BROKER_REPORTS_GATE2_FINANCIAL_SEMANTIC_LOCAL_CHOICE.v2.1.md) | active request builder/expansion/evidence; inactive V2.1 linter and GOAL 11 local adapter proof | active exact-ID bytes and historical Local v1 remain pinned; V2.1 restores only through its private receipt and public validation pins exact model-order schema bytes | alternative Choice factory/schema authority, index-derived restoration or model-generated records/bindings |
| Canonical decision expansion | [`Gate2FinancialSemanticV6DecisionExpansionFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate2_financial_semantic_v6_expansion.py) plus additive `create_from_context_v2_1_candidate` under the same owner | [V6 Expansion](./BROKER_REPORTS_GATE2_FINANCIAL_DECISION_EXPANSION_V6.md) and inactive [Local Choice V2.1](./BROKER_REPORTS_GATE2_FINANCIAL_SEMANTIC_LOCAL_CHOICE.v2.1.md) | materializer, qualification, replay, GOAL 11 local proof | active path remains byte/hash exact; candidate path alone accepts the third V2.1 reason and still delegates to the canonical validator | choice-to-record expansion in runner/evidence code |
| Validator | [`Gate2FinancialEvidenceValidatedDecisionFactory.create` and `validate_financial_evidence_inputs`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate2_financial_evidence_materialization.py) | [Generic Materialization](./BROKER_REPORTS_GATE2_GENERIC_FINANCIAL_MATERIALIZATION.v1.md) | materializer, qualification, local proofs | legacy validators remain version-pinned | weaker local acceptance or provider output as authority |
| Materializer | [`Gate2FinancialEvidenceMaterializerFactory.create().materialize`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate2_financial_evidence_materialization.py) | [Generic Materialization](./BROKER_REPORTS_GATE2_GENERIC_FINANCIAL_MATERIALIZATION.v1.md) | Financial Domain, explicit compatibility projections | projections read canonical output | ID, binding, provenance or retention minting elsewhere |
| Persistence | [`Gate2FinancialDomainPersistenceFactory.serialize/restore`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate2_financial_domain_persistence.py) | [Managed Financial Domain](./BROKER_REPORTS_MANAGED_FINANCIAL_DOMAIN.v1.md) | local proof, future storage adapter | restore validates the current envelope | a storage adapter reimplementing serialization or minting snapshots |
| Financial Domain snapshot | [`Gate2FinancialDomainCatalogFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate2_financial_domain_catalog.py) | [Managed Financial Domain](./BROKER_REPORTS_MANAGED_FINANCIAL_DOMAIN.v1.md) | query and persistence factories | explicit legacy/successor readers only | direct record catalogs or mutable snapshots |
| Historical Financial Domain Query API | [`Gate2FinancialDomainQueryFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate2_financial_domain_query.py) | [Query API](./BROKER_REPORTS_GATE2_FINANCIAL_DOMAIN_QUERY_API.v1.md) | historical Financial Domain consumer | none | treating query results as current Gate 3 labeling input or adding facades over raw records/sources |
| Historical Financial Domain consumer | [`Gate3FinancialDomainContextFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate3_financial_domain_context.py) | [Query API](./BROKER_REPORTS_GATE2_FINANCIAL_DOMAIN_QUERY_API.v1.md) and superseded global gate architecture | compatibility/history only | legacy context manifest remains separate | current Gate 3 authority, ArtifactStore, Gate 1 reader or provider access |
| Qualification result | [`qualify_financial_semantic_v6`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate2_financial_semantic_v6_qualification_run.py) plus additive [`Gate2FinancialSemanticV6ContextV21BudgetSmokePlanFactory` and thin coordinator](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate2_financial_semantic_v6_context_v2_1_budget_smoke.py) | [V6 Qualification Harness](./BROKER_REPORTS_GATE2_FINANCIAL_SEMANTIC_V6_QUALIFICATION_HARNESS.md) and [Context V2.1 Budget Model Smoke v1](./BROKER_REPORTS_GATE2_CONTEXT_V2_1_BUDGET_MODEL_SMOKE.v1.md) | qualification CLI, safe receipt and transparent synthetic report | older runners are replay-only; GOAL 12 cannot admit production | parallel result classifier or production admission |
| Evidence storage and local replay | [`Gate2FinancialSemanticV6DecisionEvidenceFactory` Context V2.1 local/live methods and the versioned private-evidence serialize/restore/replay entrypoints](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate2_financial_semantic_v6_evidence.py); additive zero-call composition [`Gate2FinancialSemanticV6ContextV21ProviderProofFactory.create_case` and canonical proof validator](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate2_financial_semantic_v6_context_v2_1_provider_proof.py); atomic external private checkpointing in the [GOAL 12 CLI](../../../services/broker-reports-gate1-proof/scripts/live_gate2_financial_semantic_v6_context_v2_1_three_provider_smoke.py); public synthetic projection/aggregate and privately issued case evidence under [`Gate2FinancialSemanticV6TransparentSmokeReportFactory`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate2_financial_semantic_v6_smoke_report.py) | [V6 Exact Evidence](./BROKER_REPORTS_GATE2_FINANCIAL_SEMANTIC_V6_EXACT_EVIDENCE.md) and [Context V2.1 Budget Model Smoke v1](./BROKER_REPORTS_GATE2_CONTEXT_V2_1_BUDGET_MODEL_SMOKE.v1.md) | qualification, offline audit, synthetic smoke/provider report | replay restores serialized private evidence and checks the validated sealed request, trusted plan/profile, projection policy, exact rebuilt prepared request and schema before reconstruction; private actual evidence stays outside Git; safe reports contain only approved synthetic evidence, hashes, verdicts and metrics | raw private evidence in Git, public case projection treated as issued evidence, raw or resealed proof dictionaries as report authority, actual-corpus transparent projection, evidence-driven product mutation, retry or production admission |

## Duplicate, compatibility and history findings

- No proven active duplicate owns the same maintained product operation.
- `financial_semantic_v6_canonical_request` validates V6 inputs and delegates to
  `Gate2OpenWebUIRequestBuilder.build`; it is a wrapper, not a second builder.
  It is marked `COMPATIBILITY_WRAPPER_DELEGATES_ONLY` and has a delegation test.
- `Gate2FinancialSemanticV5ProjectionFactory` is intentionally consumed by V6.
  Renaming or replacing it would create migration risk; document the
  cross-version ownership instead of creating a V6 copy. Keep it as the one
  shared maintained projection authority.
- `gate2_financial_evidence_compatibility.py`,
  `gate2_financial_evidence_legacy_validation.py` and
  `gate2_successor_compatibility.py` are active compatibility readers. Their
  readers are marked `COMPATIBILITY_WRAPPER_DELEGATES_ONLY` and delegate to
  canonical or pinned validators. The pinned legacy validator is explicitly a
  `HISTORICAL_VERSION_PINNED_AUTHORITY`; it is read-only and cannot define
  current meaning or writes.
- `gate3_context_manifest.py` is the legacy bounded Gate 2 handoff root;
  `gate3_financial_domain_context.py` is the historical Financial Domain
  successor consumer. Neither is the current Gate 3 type-and-role authority. The
  historical consumer remains forbidden from importing the legacy manifest or
  Gate 1 readers.
- `openwebui_actions/*_bundled.py` are generated closed-world projections.
  `scripts/build_openwebui_pipe_bundle.py` and maintained package/action
  sources own their content; bundle files must not be edited as authorities.
- Files under `docs/reports/**`, benchmark sealed results and committed safe
  receipts are immutable historical evidence. They may identify a past
  revision but never override maintained code or contracts.
- V5 and earlier qualification runners remain readable for historical replay
  and version-pinned tests. New V6 work must not extend them as current
  qualification authority.

## Managed Semantic Decision Context GOAL 0 authority audit

The existing
[OpenWebUI Financial Domain Asset Family](./BROKER_REPORTS_OPENWEBUI_FINANCIAL_DOMAIN_ASSET_FAMILY.v1.md)
is the sole reusable managed-asset mechanism for the next context program.
It already pins one Skill, one Prompt, one exact Semantic Pack Tool, the Pack
dependency and their composition in one manifest. The program must extend this
family; it must not create another registry, packet builder, parallel
asset-family/manifest authority or GUI framework. New immutable version
manifests inside the selected family remain allowed and required.

Concern ownership is fixed as follows:

| Concern | Owner and required placement |
| --- | --- |
| financial type semantics | the existing Financial Semantic Pack; no Prompt, adapter or runner copy |
| decision reason semantics | the closed code set remains in Choice/decision contracts; human meanings live in one versioned catalog dependency inside the same managed asset family, not a second registry or Pack |
| model-visible presentation | the managed Skill/Prompt plus the existing V6 packet owner's versioned context projection |
| exact refs, provenance, aliases, bindings, retention and materialization | existing backend authorities; never managed semantic content |
| future asset-version lifecycle and active pointer | a planned extension of the selected asset-family version manifest and release receipt will select one immutable active version; no family active pointer exists today |

The repository and pinned OpenWebUI `v0.9.6` provide only a partial lifecycle
today:

- the asset-family manifest provides semantic versions, exact Git-blob hashes,
  deterministic composition and inactive target status;
- native OpenWebUI Prompt records provide history entries, a production-version
  pointer, active toggling and restoration of a selected history version, but
  every update overwrites the current Prompt row content even when
  `is_production=false`; this is not an isolated runtime-safe draft;
- native Skill records expose content and active state plus API update/toggle
  operations, but no version history or restore endpoint;
- native Tool records expose content plus an overwrite update operation, but no
  version history or active-version selector;
- the repository atomic stage release snapshots every Function/Prompt field it
  mutates and proves exact snapshot restoration during rollback rehearsal, but
  candidate readback is only a contracted projection and automatic failure
  restoration has a known pre-`modified` loader window; it does not publish or
  restore the Skill/Tool/Pack family, and direct Prompt-row updates do not
  create native Prompt history.

Primary upstream evidence for the pinned distribution:

- [Prompt version/history/production fields](https://github.com/open-webui/open-webui/blob/v0.9.6/backend/open_webui/models/prompts.py#L23-L93),
  [current-row update with conditional history creation](https://github.com/open-webui/open-webui/blob/v0.9.6/backend/open_webui/models/prompts.py#L481-L554)
  and [selected-version restoration](https://github.com/open-webui/open-webui/blob/v0.9.6/backend/open_webui/models/prompts.py#L585-L622);
- Prompt [version-selection](https://github.com/open-webui/open-webui/blob/v0.9.6/backend/open_webui/routers/prompts.py#L360-L397),
  [active-toggle](https://github.com/open-webui/open-webui/blob/v0.9.6/backend/open_webui/routers/prompts.py#L454-L492)
  and [history-read endpoints](https://github.com/open-webui/open-webui/blob/v0.9.6/backend/open_webui/routers/prompts.py#L533-L616);
- [Skill fields](https://github.com/open-webui/open-webui/blob/v0.9.6/backend/open_webui/models/skills.py#L20-L52),
  [Skill API update](https://github.com/open-webui/open-webui/blob/v0.9.6/backend/open_webui/routers/skills.py#L253-L320)
  and [toggle endpoint](https://github.com/open-webui/open-webui/blob/v0.9.6/backend/open_webui/routers/skills.py#L376-L410);
- [Tool fields without version or activation state](https://github.com/open-webui/open-webui/blob/v0.9.6/backend/open_webui/models/tools.py#L20-L52)
  and [Tool overwrite update](https://github.com/open-webui/open-webui/blob/v0.9.6/backend/open_webui/models/tools.py#L291-L304).

Therefore isolated draft storage, hardened full candidate readback/rollback
and a complete family-level `draft → validated → active → retired → rollback`
publisher are explicit implementation gaps, not a second authority to invent
in GOAL 0. Later work must extend the existing manifest/release contour and may
reuse the existing OpenWebUI Workspace GUI/API only as an
authoring/inspection surface behind that guarded lifecycle. Until exact
readback and rollback exist for the full family, the managed assets remain
non-active and the current V6 route remains unchanged.

## Managed Semantic Decision Context GOAL 1 catalog status

GOAL 1 adds one immutable same-family draft:

- family v2 keeps `family_id=broker_reports_gate2_financial_domain_assets`,
  advances only the family semantic version to `1.1.0`, and remains
  `runtime_activation=false`;
- all v1 Skill, Prompt, Tool and Pack assets remain byte-exact; GOAL 4 later
  changes only the generated container bytes additively to package the inactive
  snapshot, while the default active semantic/default loader payload remains
  exact;
- the decision contract remains the sole reason-code owner;
- the
  [Financial Decision Reason Catalog v1](./BROKER_REPORTS_GATE2_FINANCIAL_DECISION_REASON_CATALOG.v1.md)
  becomes the sole human-meaning owner;
- its build-time factory derives the code set from the maintained decision
  source, generates the strict schema and checks meaning-field completeness,
  reciprocal contrasts, non-overlapping boundaries and canonical integrity;
- draft rollback discards v2 without runtime mutation; the exact immutable v1
  manifest is pinned as the prior baseline.

This establishes a GUI-ready repository asset, not live GUI publication.
Full-family publishing/readback/rollback remains the lifecycle gap above.
The catalog is not visible on the active model route. Managed Semantic
Decision Context GOAL 4 projects it only into the non-active Context V2.0 packet
sidecar; this does not claim compatibility with frozen V6 expected answers,
especially for cases whose current active packet exposes no type cards.

## Managed Semantic Decision Context GOAL 2 alias audit

The
[alias necessity and readability audit](../../reports/2026-07-28/BROKER_REPORTS_GATE2_MANAGED_SEMANTIC_CONTEXT_GOAL2_ALIAS_NECESSITY_AND_READABILITY_AUDIT.report.md)
changes no operation authority. It refines only the requirements for a future
versioned projection inside the existing packet and Choice owners:

- a local value or structural reference is visible only when another
  model-visible field consumes it;
- exact refs and the complete binding table remain Evidence Bundle, Candidate
  Compiler and Typed Option authority;
- deterministic local keys are paired with readable evidence-owned labels;
- readable type and choice labels come from the existing Financial Semantic
  Pack title; Context V2.0 uses no choice-label qualifier because relationships
  already carry the evidence distinction;
- Context V2.0 versioned/extended the existing type-card projection to carry
  Pack title; packet code may not read the asset through a bypass;
- positional `A/B` and numeric `TN` are not future semantic label
  authorities, though unique local response/cross-reference keys remain
  required;
- semantically indistinguishable choices remain distinct by key;
  `unclassified` is truthful for two or more plausible distinct types, while
  same-type indistinguishability hits the explicit count-one compatibility
  stop; only mapping/integrity defects are technical failures;
- provider adapters perform no naming, binding filtering or semantic repair.

The 10-case frozen census records 45 value aliases, 20 structural aliases, 12
type aliases, 12 choice aliases and 59 visible bindings. Twenty-two value
aliases and 14 structural aliases have no inbound reference. Only five
`source_label` relations and six printed-label-evidence predicates distinguish
options. Factoring common eligibility relationships yields 35 readable
relations and removes 24 duplicate occurrences; all 59 exact bindings remain
backend-owned and reconstructable.

The GOAL 2 census above was documentation-only. Managed Semantic Decision
Context GOAL 4 now implements its factoring and mapping rules as a non-active
packet sidecar. The active V6 payload, Choice and request/provider route remain
unchanged; V2.0 runtime activation and provider calls are zero, and the four
zero-option expected-answer concerns remain an explicit compatibility stop.

## Managed Semantic Decision Context GOAL 3 contract

The versioned
[LLM Semantic Context V2.0](./BROKER_REPORTS_GATE2_LLM_SEMANTIC_CONTEXT.v2.md)
closed the historical completeness-candidate model-visible boundary in GOAL 3:

- the current system Prompt, generic task, option order, Pack wording and
  reason wording are unchanged;
- the available type set comes from active Pack/Registry contracts compatible
  with the Evidence Bundle source family; Compiler Typed Options and blocked
  bindings are only a private parity signal, so a zero-choice semantic case no
  longer implies zero type meanings in the V2.0 completeness view;
- type titles/definitions/distinctions come only through a versioned extension
  of the existing Pack projection;
- complete human-readable reason cards come only from the managed catalog;
- repeated option bindings become factored readable relationships with an
  explicit local-choice subset when they are not global, while the exact
  complete binding table remains private;
- `value_N`, `type_N` and `choice_N` keys are request-local and separate from
  readable labels; structural keys appear only for necessary cross-reference;
- the packet-owned private mapping receipt binds every visible
  key/relationship and every hidden exact binding to existing Registry,
  Evidence Bundle, Compilation and Typed Option authorities without importing
  Prompt or Choice; the historical V2.0 design assigned separate complete
  Prompt + Context + response-format sealing to the existing Context Linter,
  but that extension was not implemented.

## Managed Semantic Decision Context GOAL 4 non-active implementation

Managed Semantic Decision Context GOAL 4 consumes that contract only inside
the existing packet authority. The single managed-assets loader packages an
inactive candidate snapshot; the existing projection owner produces
Pack/reason projections; and the packet factory returns the deterministic V2.0
candidate plus private mapping receipt. The V2.0 Choice profile,
complete-request linter, request route, provider compatibility,
persistence/replay and benchmark compatibility remain unimplemented or
unproven. Count `1` remains outside the two reason boundaries. Provider calls
and runtime activation remain zero.

Repository-safe implementation evidence:

- [analytical report](../../reports/2026-07-28/BROKER_REPORTS_GATE2_MANAGED_SEMANTIC_CONTEXT_GOAL4_NON_ACTIVE_CONTEXT_V2.report.md);
- [safe receipt](../../reports/2026-07-28/BROKER_REPORTS_GATE2_MANAGED_SEMANTIC_CONTEXT_GOAL4_NON_ACTIVE_CONTEXT_V2.receipt.safe.json).

## Minimal Semantic Model Surface GOAL 5 contract

The
[Minimal Model Surface v1](./BROKER_REPORTS_GATE2_MINIMAL_MODEL_SURFACE.v1.md)
supersedes Context V2.0 as the field-eligibility policy for the current
non-active
[Context V2.1](./BROKER_REPORTS_GATE2_LLM_SEMANTIC_CONTEXT.v2.1.md).
Context V2.0 remains exact, implemented, non-active, version-pinned
completeness evidence; GOAL 8 does not rewrite its bytes or historical
receipts.

GOAL 5 is documentation-only. It changes no Prompt, Pack, reason catalog,
managed asset, projection, Packet, Choice, linter, request/provider route,
expected answer or runtime byte. The ordered successor program is:

1. GOAL 5 defines the minimal field allowlist, default-forbidden fields,
   field-by-field necessity and exact managed-string selection rules;
2. GOAL 6 audits outcome taxonomy, the count-one stop and frozen benchmark
   expectations;
3. GOAL 7 implements the exact versioned minimal managed projection through
   the existing Pack/reason projection and loader authorities;
4. GOAL 8 builds only one non-active Context V2.1 candidate plus private
   mapping receipt in the existing Packet factory;
5. the later governing program separately authorizes GOAL 9 to add one
   versioned inactive V2.1 response profile/parser in the existing Choice
   authority;
6. GOAL 10 adds only the V2.1 linter/budget guard and provider-neutral sealed
   request through additive `create_context_v2_1`, consuming the P01-P18
   Prompt, Packet candidate, mapping receipt and Choice-owned schema;
7. GOAL 11 proves OpenAI, Anthropic and Google projection plus extraction,
   materialization, persistence/restore and exact replay on four synthetic
   fixtures with zero provider calls;
8. GOAL 12 froze one budget candidate per provider and at most 12 live
   qualification slots under the existing owners, using exact direct-provider
   transport resolved from the enabled OpenWebUI connection, a committed
   pre-call plan, exact open-PR/Actions provenance and one-shot external
   execution claims; the run completed with `8` submissions, OpenAI and
   Anthropic semantic failures, and four Google pretransport failures;
9. **STOP before GOAL 13:** GOAL 12 produced no eligible provider/model.
   Further attempts require a separate explicit candidate or policy decision.

The minimal contract selects existing semantic wording; it does not author it.
`positive_signal` is exact Pack `examples[0]`, `negative_signal` is exact
`counterexamples[0]`, and nearest distinction is the unique direct rule
against the only other current visible type. Reason `use_when` is the exact
first sentence of catalog `meaning` under the closed sentence rule. GOAL 7
only implements those mappings and may not embed replacement wording.

GOAL 8 is implemented at that exact boundary. The current Packet factory calls
the GOAL 7 minimal projection, constructs one five-block V2.1 candidate and
one exact private receipt, and leaves historical V2.0 off the current
per-request path. Frozen proof preserves all ten active packet hashes, all 45
semantic literal occurrences and all 59 compiled bindings. Aggregate V2.1
payload is 26,211 UTF-8 bytes versus historical V2.0 at 78,621 bytes. Runtime
activation, provider calls and full-benchmark runs are zero.

The former post-GOAL-8 STOP was cleared by the later explicit program. GOAL 9
now implements the inactive profile through the existing Choice owner. It
leaves active V6 bytes, Context candidate/receipt, Expansion, linter, request
builder, adapters and provider routes unchanged.

## Context V2.1 Local Choice response profile GOAL 9

The existing `Gate2FinancialSemanticV6ChoiceContractFactory.create` adds one
inactive response profile pinned to the Context V2.1 candidate, its private
mapping receipt and the unchanged active Choice hash. Its parser restores
`choice_N` only through the exact receipt row and preserves any of the three
allowed V2.1 reasons without repair.

The profile has two inactive consumers:
`Gate2FinancialSemanticV6ContextLinterFactory.create_context_v2_1` and the
GOAL 11 local proof coordinator. The third reason remains outside active V6
Expansion/materialization and is accepted only by the additive candidate path.
Provider calls, managed-asset changes, benchmark runs and runtime activation
are zero.

## Context V2.1 three-provider local proof GOAL 11

`Gate2FinancialSemanticV6ContextV21ProviderProofFactory.create_case` is a
bounded coordinator, not a new semantic authority. It delegates request
sealing, provider projection/extraction, Choice restoration, candidate
Expansion, canonical materialization, Financial Domain snapshot/persistence
and transparent reporting to the owners listed above. For each synthetic path
it serializes one exact private-evidence document, restores that document,
replays from its preserved adapter output, validates the sealed request, exact
repository profile and whole prepared-request rebuild, and reconstructs the
Financial Domain snapshot. Candidate-only extraction first requires one
terminal provider envelope.

The public report method `create_context_v2_1_provider_case` returns only the
raw closed projection and cannot mint evidence. ProviderProofFactory first
creates an unissued full proof, independently recomputes the same unissued proof
from governed inputs and requires exact equality. Only then does its private
report-module authority issue the opaque immutable case-evidence token.
Independent canonical full-proof validation follows. The aggregate accepts only
that issued token and revalidates its closed projection when read; raw or
resealed proof dictionaries are not report evidence and fail closed.

The proof covers three profiles by four semantic fixtures, including
`single_registry_type_no_safe_record`. The candidate decision contract extends
the unclassified reason enum only through the existing decision/Expansion
factories; the active Choice schema/hash remains unchanged during the proof.
The non-active
`broker_reports_gate2_context_v2_1_local_schema_projection_v1` identity binds
OpenAI/Anthropic/Google projection behavior and preserves the `choice` and
`reason` enums, including Gemini, while canonical adapter versions stay
unchanged. No transport function is called.

## Outcome Taxonomy and Benchmark Audit GOAL 6

The
[Outcome Taxonomy v1](./BROKER_REPORTS_GATE2_OUTCOME_TAXONOMY.v1.md)
closes the count-one vocabulary gap additively:

- semantic truth is evaluated by plausible distinct type count plus uniquely
  safe complete-choice count, never by raw Compiler option/block counts;
- the semantic rows are typed `1/1`, no type `0/0`, ambiguous type `2+/0`,
  and single type without a safe record `1/0`;
- the count-one row uses the new inactive managed candidate reason
  `single_registry_type_no_safe_record`;
- insufficient source context and technical failure remain non-semantic
  preclose/fail-closed rows and never force a semantic reason;
- the four frozen zero-choice audits have plausible-type counts `2,1,1,1`;
  three historical `ambiguous_registry_type` expectations are proven errors;
  and
- the corrections live in a new frozen outcome-audit identity. Historical
  successor/V6 manifests, local proof, reports and receipts remain unchanged.

Catalog v2 is an additive successor under the existing catalog ID. It remains
inactive and is not accepted by the active V6 Choice. GOAL 7 packages it in
inactive family v3 and implements only its exact managed minimal projection
through the existing loader/projection owner. The current non-active V2.1
Packet construction, Choice-owned response profile, provider-neutral Context
Linter, GOAL 11 zero-call local proof and the terminal GOAL 12 qualification
plan/evidence path are its only consumers. None is product runtime. GOAL 12
completed with `8` submissions, no benchmark-eligible provider/model and no
activation.
Current non-active V2.1 uses the Minimal Model Surface instruction, not the historical
V2.0 complete-prebound task.

## Documentation drift and explicit debt

1. `architecture_policy.py` now points its general runtime authority to this
   current Pipeline Gates contract. The superseded global blueprint is retained
   only as the narrow historical authority for its visual-table contract.
2. Generated bundles are deterministically rebuilt and tested, but their file
   headers do not make generated-only status obvious.
3. Financial Domain persistence owns an envelope, not a storage backend. A
   future storage adapter must delegate serialization and may not mint snapshot
   authority.
4. The OpenAI root-object projection is implemented locally in the existing
   adapter. GOAL 12 passed its separately enforced pre-call Actions gate and
   completed without admitting a provider/model; its terminal final head still
   requires its own green Actions check and fresh review before merge.
5. `FULL_REPROCESSING_RICH_CANONICAL_COST`: full semantic republication of a
   rich document may require many bounded contexts and high provider cost.
   Current mitigation is indexed demand-driven bounded recovery. Revisit only
   under measured product latency/cost pressure or an explicit full-document
   republication requirement; G5.55 does not optimize it.

## Historical LLM Semantic Context v1 candidate boundary

The
[LLM Semantic Context v1](./BROKER_REPORTS_GATE2_LLM_SEMANTIC_CONTEXT.v1.md)
was the closed target for the historical Slim candidate profile. It requires
readable evidence-derived hierarchy, exactly one rendered occurrence per
authoritative semantic source value, omitted nulls, local request-bound aliases
and zero opaque global IDs across messages and response schema. The
[LLM Semantic Context V2.0](./BROKER_REPORTS_GATE2_LLM_SEMANTIC_CONTEXT.v2.md)
is the additive historical successor. Its packet-owned candidate and private
mapping receipt are implemented but non-active; its complete Prompt + Context
+ response-format request was not implemented. The future field-eligibility
target is the
[Minimal Model Surface v1](./BROKER_REPORTS_GATE2_MINIMAL_MODEL_SURFACE.v1.md),
not completion of the V2.0 surface.

The current active V6 four-block packet and V6 Choice do not claim this
conformance: they expose exact source/option identities by their historical
contracts. The historical staged GOAL 0 defined the v1 boundary; its GOAL 1/2
implemented a non-active local projection, and its GOAL 3 enforces that profile
at the candidate request boundary.
Slim construction remains inside
`Gate2FinancialSemanticV6PacketFactory.create`, and the separate
[Local Choice v1](./BROKER_REPORTS_GATE2_FINANCIAL_SEMANTIC_LOCAL_CHOICE.v1.md)
remains inside the current Choice authority. No provider adapter may remove
IDs or repair semantic meaning to simulate conformance.

```text
CONTEXT_CONTRACT: DEFINED
CURRENT_PACKET_CHANGED: NO
CURRENT_CHOICE_CHANGED: NO
RUNTIME_ROUTE_CHANGED: NO
SECOND_PACKET_BUILDER: ZERO
CONTEXT_LINTER: IMPLEMENTED_FOR_CANDIDATE_PROFILE
PROVIDER_CALLS: ZERO
STAGE_MUTATIONS: ZERO
```

### GOAL 1 non-active Slim View implementation

`Gate2FinancialSemanticV6PacketFactory.create` now constructs the inactive
Slim View and private alias receipt alongside the unchanged active four-block
packet. No second module, packet factory, Candidate Compiler, semantic
projection or Choice schema was introduced.

The maintained request builder, qualification and evidence paths continue to
consume only `packet.payload`. Candidate renderers are local-proof surfaces;
they do not create a provider route. Exact source/type identities, lineage,
bindings and deterministic-reference values stay in the private receipt and
existing authorities.

Executable architecture and packet tests prove:

- all 10 frozen active packet hashes and UTF-8 byte counts are exact;
- each semantic value has one local alias and one rendered occurrence;
- structure and non-null metadata are retained;
- every displayed binding resolves through the receipt to its exact compiled
  option binding;
- candidate/receipt tampering fails closed;
- the candidate is always inactive and provider-call accounting is zero;
- no `gate2_financial_semantic_v6*slim*.py` module or Slim factory exists.

```text
SLIM_VIEW_OWNER: EXISTING_V6_PACKET_FACTORY
ACTIVE_PACKET_HASH_PARITY: 10_OF_10_EXACT
SLIM_VIEW_ACTIVE: FALSE
PRIVATE_ALIAS_RECEIPT: INTEGRITY_BOUND
CURRENT_REQUEST_ROUTE_CHANGED: NO
CURRENT_CHOICE_CHANGED: NO
SECOND_PACKET_BUILDER: ZERO
PROVIDER_CALLS: ZERO
STAGE_MUTATIONS: ZERO
```

### GOAL 2 non-active Local Choice implementation

`Gate2FinancialSemanticV6ChoiceContractFactory.create` now returns the
unchanged active exact-ID Choice plus one inactive versioned local candidate.
Slim View v2 removes canonical `return_id`; the packet private receipt retains
the exact A/B-to-option mapping.

`Gate2FinancialSemanticV6DecisionExpansionFactory.create_from_local_candidate`
normalizes the local closed answer and delegates to the same canonical
expansion used by `create`. It is not called by the request builder,
qualification run or evidence runtime.

Executable tests prove:

- all 10 active Choice schema hashes remain exact;
- exact messages plus local response schema contain zero opaque IDs;
- option permutation moves the visible record and private mapping together
  while active packet payload/hash remain exact;
- every local typed and unclassified answer expands and materializes
  identically to the current path;
- unclassified retention remains the complete Evidence Bundle retention set;
- unknown/extra/duplicate/tampered choices fail closed;
- no second Choice factory or local-choice module exists;
- provider calls, fallback, repair, retry and runtime-route changes are zero.

```text
LOCAL_CHOICE_OWNER: EXISTING_V6_CHOICE_FACTORY
LOCAL_EXPANSION_OWNER: EXISTING_V6_DECISION_EXPANSION_FACTORY
ACTIVE_CHOICE_SCHEMA_HASH_PARITY: 10_OF_10_EXACT
FULL_MODEL_VISIBLE_OPAQUE_IDS: ZERO
CANONICAL_EXPANSION_MATERIALIZATION_PARITY: EXACT
LOCAL_CHOICE_ACTIVE: FALSE
CURRENT_REQUEST_ROUTE_CHANGED: NO
SECOND_CHOICE_FACTORY: ZERO
PROVIDER_CALLS: ZERO
STAGE_MUTATIONS: ZERO
```

### GOAL 3 pre-transport Context Linter and local totality

`Gate2FinancialSemanticV6ContextLinterFactory.create` validates the complete
Prompt + Slim View + Local Choice projection after the existing packet and
Choice authorities have constructed their parts. This downstream position is
intentional: the packet owner cannot inspect Prompt or Choice without becoming
a second authority for them.

The linter verifies zero opaque IDs, duplicate literal occurrences, nulls,
unmapped aliases, orphan aliases and alias collisions; it also proves complete
literal coverage, valid evidence-derived hierarchy, exact option coverage and
the full private alias-receipt integrity. It records exact model-visible UTF-8
bytes plus the repository estimator result and seals one request-bound
receipt.

The existing `Gate2OpenWebUIRequestBuilder.build` remains the sole provider
request constructor. Its non-active
`financial_semantic_v6_slim_linted_v1` profile checks the sealed receipt before
returning `form_data`. It imports no qualification-only V6 module, is rebuilt
inside all generated bundles and fails closed there when a receipt is absent.

Executable proof over all 10 frozen semantic cases records:

```text
SEMANTIC_LITERAL_COVERAGE: 100_PERCENT
DUPLICATE_LITERALS: ZERO
NULL_FIELDS: ZERO
OPAQUE_IDS: ZERO
UNMAPPED_ALIASES: ZERO
ORPHAN_ALIASES: ZERO
ALIAS_COLLISIONS: ZERO
STRUCTURAL_HIERARCHY: VALID
EXACT_OPTION_COVERAGE: COMPLETE
ALIAS_RECEIPT_INTEGRITY: VALID
EXACT_REPLAY: 10_OF_10
LOCAL_TOTAL_MATERIALIZATION: 32_OF_32
MODEL_VISIBLE_UTF8_BYTES_TOTAL: 26404
REPOSITORY_ESTIMATED_INPUT_TOKENS_TOTAL: 7247
CURRENT_RUNTIME_ROUTE_CHANGED: NO
PROVIDER_CALLS: ZERO
```

This adds one validation operation authority, not another context
construction authority. It performs no provider call, fallback, repair,
semantic rewrite, production admission or stage mutation.

### Historical Slim-program GOAL 4 bounded model diagnostic

`Gate2FinancialSemanticV6SlimDiagnosticFactory.create` is the
qualification-only orchestration owner for the exact six-cell experiment:
Nano canonical order, Haiku canonical order and Nano reversed order, each on
the frozen typed and unclassified smoke cases. It reuses the existing packet,
Local Choice, Context Linter, structured model client, expansion and total
materialization authorities. The reversed cells ask the existing
`Gate2FinancialSemanticV6PacketFactory` for a permutation; the active packet
payload/hash and canonical Choice schema remain exact.

The one authorized execution is terminal and must not be rerun:

```text
PROVIDER_SUBMISSIONS: SIX
PROVIDER_RESPONSES: SIX
TECHNICAL_PIPELINE: PASSED
HAIKU_TYPED: PASSED
HAIKU_UNCLASSIFIED: FAILED_WITH_EXACT_EVIDENCE
NANO_SLIM_TYPED: FAILED_WITH_EXACT_EVIDENCE
NANO_SLIM_UNCLASSIFIED: FAILED_WITH_EXACT_EVIDENCE
NANO_REVERSED_TYPED: FAILED_WITH_EXACT_EVIDENCE
NANO_REVERSED_UNCLASSIFIED: PASSED
FALLBACK_REPAIR_HIDDEN_RETRY: ZERO
FULL_BENCHMARK: NOT_RUN
RUNTIME_ROUTE_CHANGED: NO
```

The exact safe receipt and evidence-first
[report](../../reports/2026-07-28/BROKER_REPORTS_GATE2_LLM_CONTEXT_GOAL4_SLIM_MODEL_DIAGNOSTIC.report.md)
are the result authority. The report's post-execution layer audit localizes
the shared unclassified miss to the readable reason-code boundary:
`ambiguous_registry_type` and `no_registry_type` were exposed as bare labels
without an explicit distinction. This evidence owner records facts and
diagnosis only; it does not become a packet, Choice, provider or admission
authority.

## OpenAI projection decision and local completion

- `Gate2FinancialSemanticV6ChoiceContractFactory.create` owns the canonical
  minimal choice schema. Its top-level `anyOf` remains product-neutral contract
  meaning and is not a provider projection.
- `Gate2OpenAIResponseFormatAdapter.prepare_form_data` owns the OpenAI schema
  projection; `extract_content` owns inverse normalization and
  `provider_error_code` owns parsing provider rejection. Adapter version
  `1.1.0` wraps canonical root `anyOf` under one required provider-only root
  object property and removes that envelope before canonical parsing.
- The [safe two-case smoke](../../reports/2026-07-27/BROKER_REPORTS_V6_QUALIFICATION_GOAL5_TWO_CASE_SMOKE.report.md)
  records two provider responses rejected before any semantic decision.
  OpenAI's [Structured Outputs schema rules](https://developers.openai.com/api/docs/guides/structured-outputs#root-objects-must-not-be-anyof-and-must-be-an-object)
  require a root object rather than root `anyOf`. Both V6 smoke shapes have
  root `anyOf`, no root `type`, equal canonical/adapted hashes and transform
  count zero. Therefore the actionable root-cause layer is the existing
  provider projection, not Prompt, Pack, Choice meaning or qualification.
- OpenAI permits
  [nested `anyOf` schemas](https://developers.openai.com/api/docs/guides/structured-outputs#for-anyof-the-nested-schemas-must-each-be-a-valid-json-schema-per-this-subset)
  when every variant follows the supported subset. The provider-only envelope
  therefore preserves both closed V6 variants instead of flattening or
  weakening their semantic constraints.
- The corrective slice is now implemented inside
  `Gate2OpenAIResponseFormatAdapter`. Tests prove exact typed and unclassified
  choice parity, unchanged canonical input, a distinct adapted schema hash and
  exactly one recorded schema transform before transport.
- No product contract change or new qualification framework is required. The
  existing two-case smoke path can be used only after the local adapter seam
  passes and a new explicit authorization is granted; consumed submissions
  must not be retried or reused.

## V6 completion Goal 0 acceptance

```text
OPENAI_ROOT_OBJECT_PROJECTION: PASSED
TYPED_SEMANTIC_PARITY: EXACT
UNCLASSIFIED_SEMANTIC_PARITY: EXACT
CANONICAL_CHOICE_CHANGED: NO
SECOND_AUTHORITY_CREATED: NO
ADAPTER_VERSION: 1.1.0
PROVIDER_CALLS: ZERO
STAGE_MUTATIONS: ZERO
DOCUMENTATION_IMPACT: AUTHORITY_MAP_UPDATED
DOCUMENTATION: CURRENT
```

## V6 completion Goal 1 local response seam

`Gate2FinancialSemanticV6LocalProofFactory.create` now routes every frozen
semantic benchmark choice through the existing canonical request builder,
`Gate2ProviderAdapterFactory.create`, OpenAI root-object projection, simulated
provider-shaped JSON content and adapter inverse normalization before invoking
the existing V6 expansion, validator and total materializer.

The local proof receipt/policy revision is `v2`. It separately accounts for
ten simulated provider-shaped responses while preserving zero provider
submissions and zero provider responses. Four typed and six unclassified
semantic cases traverse the seam; the two technical-preclose cases never enter
the provider branch.

```text
TYPED_LOCAL_SEAM: PASSED
UNCLASSIFIED_LOCAL_SEAM: PASSED
OPENAI_ROOT_OBJECT_PROJECTION: PASSED
EXPANSION: PASSED
VALIDATION: PASSED
MATERIALIZATION: PASSED
PROVIDER_CALLS: ZERO
PROVIDER_RESPONSES: ZERO
SECOND_AUTHORITY_CREATED: NO
DOCUMENTATION_IMPACT: AUTHORITY_MAP_UPDATED
DOCUMENTATION: CURRENT
```

## V6 completion Goal 2 provider smoke

The bounded smoke reuses `smoke_financial_semantic_v6` in the existing
qualification runner and `Gate2StructuredModelClientFactory.create`. It owns
no request builder, provider adapter, validator or materializer. The only
selected cases are the frozen unambiguous typed case
`syn_successor_v2_unique_cash` and frozen unambiguous unclassified case
`syn_successor_v2_no_registry_type`.

The exact Nano smoke consumed two provider submissions and received two
responses. Both responses first stopped at
`Gate2FinancialSemanticV6ExecutionIdentityFactory.create` because that owner
still expected pre-projection metadata (`canonical == adapted`, transform
count zero). Adapter `1.1.0` correctly supplied distinct canonical/adapted
hashes and transform count one.

The execution-identity owner now derives its exact expected hashes and
transform count through `Gate2ProviderAdapterFactory.create`; the synthetic
preflight and tests use the same factory route. Exact offline processing of
both preserved responses then passed schema identity, parsing, normalization,
usage normalization, validation/materialization and evidence replay without a
provider call. The typed response selected the wrong exact option and the
unclassified response did not select the required unclassified disposition,
so both semantic smoke cases remain failed.

The canonical live receipt and supplemental offline diagnostic are
[repository-safe evidence](../../reports/2026-07-27/BROKER_REPORTS_GATE2_V6_COMPLETION_GOAL2_TWO_CASE_PROVIDER_SMOKE.report.md).
No precision, recall or model-safety verdict is published. Goal 2 is not
accepted and Goal 3 must not run.

```text
PROVIDER_SUBMISSIONS: TWO
PROVIDER_RESPONSES: TWO
TECHNICAL_PIPELINE_AFTER_IDENTITY_CORRECTION: PASSED
TYPED_SMOKE: FAILED
UNCLASSIFIED_SMOKE: FAILED
USAGE_NORMALIZATION_AFTER_IDENTITY_CORRECTION: PASSED
OFFLINE_REPLAY_AFTER_IDENTITY_CORRECTION: EXACT
FALLBACK_REPAIR_RETRY: ZERO
MODEL_QUALIFICATION_PERFORMED: FALSE
MODEL_SAFETY_VERDICT: NONE
SECOND_AUTHORITY_CREATED: NO
GOAL3: BLOCKED
DOCUMENTATION_IMPACT: RUNTIME_EVIDENCE_UPDATED
DOCUMENTATION: CURRENT
```

## Zero-context orientation proof

Status: `HISTORICAL_EVIDENCE` for the legacy pre-Pipeline-Gates-v1 naming below.

A fresh read-only agent with no conversation history, Codex memory, report
archaeology or internet access followed service `AGENTS.md` to this map,
versioned contracts and maintained code. It correctly identified:

- the current Gate 1 → technical preparation → Typed Options → minimal semantic
  choice → deterministic expansion → validation/materialization → Financial
  Domain → Query API → Gate 3 consumer path;
- the sole request, provider projection/parsing, budget, financial semantics,
  source-binding, materialization and query authorities;
- the provider-projection blocker and
  `Gate2OpenAIResponseFormatAdapter` as the only next corrective component;
- Prompt, Pack, canonical Choice, request builder, budget, qualification,
  materialization, domain/query contracts and generated bundles as forbidden
  direct corrective targets.

No second authority or qualification framework was proposed. The only
orientation drift found was the stale resolved-debt text removed above.

## Goal 0 acceptance

```text
DOMAINS: FULLY_INVENTORIED
AUTHORITIES: IDENTIFIED_OR_EXPLICITLY_AMBIGUOUS
DUPLICATES: IDENTIFIED
DOCUMENTATION_DRIFT: IDENTIFIED
PROVIDER_CALLS: ZERO
STAGE_MUTATIONS: ZERO
```

## Goal 2 acceptance

```text
AUTHORITY_MAP: COMPACT_AND_ACTIONABLE
EXACT_CODE_REFERENCES: PRESENT
FULL_CONTRACT_DUPLICATION: ZERO
PROVIDER_CALLS: ZERO
STAGE_MUTATIONS: ZERO
```

## Goal 5 acceptance

```text
ACTIVE_DUPLICATE_AUTHORITIES: ZERO
COMPATIBILITY_REIMPLEMENTATION: ZERO
PRODUCT_BEHAVIOR_CHANGE: ZERO
PROVIDER_CALLS: ZERO
STAGE_MUTATIONS: ZERO
```

## Historical architecture-map program Goal 8 acceptance

```text
RESPONSE_FORMAT_OWNER: IDENTIFIED
ROOT_CAUSE_LAYER: IDENTIFIED
ROOT_CAUSE: PROVIDER_PROJECTION
NEXT_CORRECTIVE_SLICE: ONE_EXISTING_AUTHORITY
CORRECTIVE_AUTHORITY: GATE2_OPENAI_RESPONSE_FORMAT_ADAPTER
PRODUCT_CONTRACT_CHANGE: ZERO
NEW_QUALIFICATION_FRAMEWORK: ZERO
PROVIDER_CALLS: ZERO
STAGE_MUTATIONS: ZERO
```

## Historical architecture-map program Goal 9 acceptance

```text
ZERO_CONTEXT_AGENT_ORIENTATION: PASSED
AUTHORITIES_FOUND_WITHOUT_REPORT_ARCHAEOLOGY: YES
WRONG_SECOND_PATH_PROPOSED: ZERO
DOCUMENTATION_DRIFT_FOUND: ONE_STALE_RESOLVED_DEBT_BLOCK
DOCUMENTATION_DRIFT_CORRECTED: YES
PROVIDER_CALLS: ZERO
STAGE_MUTATIONS: ZERO
FINAL_STATUS: ARCHITECTURE_MEMORY_REFINED_WITH_EXPLICIT_DEBT
```

## DOC28 durable deployment authority status

No new owner was introduced. `ArtifactStoreFactory` remains the metadata and
payload owner, `CanonicalArtifactStoreFactory` remains the version/lifecycle
facade, and `CanonicalReaderFactory` remains the sole read boundary. The
existing `openwebui_data` mount is only a deployment candidate until an
authorized runtime proves restart, backup/restore, capacity and retention.
DOC28 created no durable store, active pointer, Wave 2 adapter or product read.

DOC29 retained these owners and introduced no engine. It identified the live
`openwebui_data` mount, reused the Broker namespace, and added only a bounded
job plus factory-routed Wave 2 shadow contracts. STT's named-volume and factory
patterns are reusable; its schema, nullable tenant field, inline payload model,
missing rotation worker and backup omission are not canonical authority.
Target ownership remains unadmitted until host recovery and post-job
durability/restore accounting. Global and primary canonical reads remain off.

At the DOC30 checkpoint, DOC30 made no authority change. It recovered the target, accounted the DOC29
OOM and selected `RETAIN` after current Broker/STT integrity and zero-write
proof. Its closed-world resource-bounded entrypoint routes normalization,
publish/activate and readback through the existing factories, one document per
checkpoint. Two canaries and 8 target versions passed; an XLSX then reached
the frozen memory cgroup and triggered the mandatory stop with zero partial
persisted state. `ArtifactStoreFactory`, `CanonicalArtifactStoreFactory` and
`CanonicalReaderFactory` remained the only storage/lifecycle/read owners. Wave 2
and primary reads were off, target durability/restore were unconfirmed, and
Gate 3 was then unstarted. This is historical checkpoint state, not the current
Gate 3 status.

DOC32 also creates no second authority. `CanonicalNormalizerFactory` remains
the sole logical builder, `CanonicalArtifactStoreFactory` the lifecycle facade,
and `CanonicalReaderFactory` the sole consumer query boundary. The PDF adapter
now accounts every source atom and emits a counts-only completeness receipt;
the store refuses non-empty zero-node PDF candidates. The research projector is
inside the existing consumer adapter and accepts only a reader envelope. The
bounded republisher, backup/restore command and Wave 2 shadow orchestrate these
owners; they do not become new parsing, storage, reader or product authorities.

At the DOC33 checkpoint, DOC33 confirmed those same owners across PDF, HTML,
CSV and XLSX. It refined the
existing validator with one format-neutral completeness rule, generalizes the
existing research renderer over common container/node semantics, and removes
source format from Wave 2 shadow output. `canonical_artifact_v1` remains the
only schema, `CanonicalReaderFactory.create` remains the only reader, and the
[Gate 2 Exit Contract v1](./BROKER_REPORTS_GATE2_EXIT_CONTRACT.v1.md) summarizes
the boundary without creating another DTO or execution authority. Product
cutover and Gate 3 were then unstarted; current status is owned by Pipeline
Gates v1.
