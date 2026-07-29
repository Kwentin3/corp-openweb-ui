# Broker Reports Architecture Authorities

Status: `ARCHITECTURE_MEMORY_REFINED_WITH_EXPLICIT_DEBT`

This is the compact orientation index for maintained Broker Reports
implementation authorities. It supplements, and does not replace, the
[global gate architecture](../blueprints/BROKER_REPORTS_GATE_ARCHITECTURE.md)
or the versioned data contracts linked below.

Use this order when sources appear to disagree:

1. the global gate architecture owns gate placement and product boundaries;
2. a versioned contract owns DTO meaning and invariants;
3. the maintained source factory owns object construction or execution;
4. a compatibility entrypoint may only adapt and delegate;
5. generated bundles project maintained source;
6. dated reports and receipts are historical evidence only.

## Minimal domain responsibility map

| Domain | Owns | Does not own | Public entrypoint | Normative contracts | Allowed consumers | Forbidden duplicate |
| --- | --- | --- | --- | --- | --- | --- |
| Gate 1 Evidence | neutral source representation, source refs, provenance and private resolution | financial type/role meaning | `Gate1BoundedGraphFactory.create`, `ArtifactResolver` | Gate 1 document memory and normalized payload | Technical Preparation | direct Gate 2 store/source reads |
| Technical Preparation | deterministic financial scope, technical preclose and sealed Evidence Bundle | financial classification or provider choice | `Gate2DeterministicFinancialScopeFromGate1V2Factory.create`, `Gate2FinancialEvidenceBundleFactory.create` | Evidence Bundle | Candidate Compiler, Qualification | a second source/provenance projection |
| Financial Semantic Pack | type/role meaning, ambiguity rules and lifecycle | source binding, provider transport or materialization | `Gate2FinancialSemanticContractFactory.create` | Financial Semantic Pack | projection, compiler, validation, materialization, Financial Domain | type-specific Python or a second registry |
| Candidate Compiler | complete code-owned Typed Options from Pack plus technical evidence | semantic selection or invented bindings | `Gate2FinancialCandidateCompilerFactory.create` | Candidate Compiler and Typed Option | Semantic Matcher, replay | financial regex, known type IDs or provider-built records |
| Semantic Matcher | current four-block packet, versioned model-visible context boundary and field-eligibility policy, semantic instruction, complete-request lint, provider-neutral minimal choice and deterministic choice expansion | source refs/provenance ownership, Pack/Reason meaning, canonical acceptance or persistence | V6 packet/Prompt/Choice factories, `Gate2FinancialSemanticV6ContextLinterFactory.create` and `Gate2FinancialSemanticV6DecisionExpansionFactory.create` | V6 Packet, LLM Semantic Context, [Minimal Model Surface](./BROKER_REPORTS_GATE2_MINIMAL_MODEL_SURFACE.v1.md), Choice and Expansion | Qualification, Validation, Evidence | model-generated records, copied semantic wording, second packet builder or alternative choice schema |
| Provider Integration | canonical request construction, provider-specific projection, transport response parsing and usage normalization | financial semantics, budget policy or product validation | `Gate2StructuredModelClientFactory.create` using request builder and adapter factories | provider-neutral request/choice plus execution metadata contracts | maintained runtime and qualification | direct provider request/response parsing outside builder/adapters |
| Budget | pre-transport admission and post-response usage/cost accounting | request shape, provider parsing or semantic verdict | `Gate2EconomyBudgetSessionFactory.create` | economy budget v1 code contract | structured model client | token/cost policy in callers |
| Validation | canonical decision parsing, Pack/Registry/source authority checks and accepted-decision validation | provider adaptation, ID minting or persistence | `Gate2FinancialEvidenceValidatedDecisionFactory.create`, `validate_financial_evidence_inputs` | Generic Financial Materialization | Materialization, Qualification | local validators that weaken the canonical contract |
| Materialization | canonical IDs, bindings, ownership, provenance, retention and terminal coverage | type semantics, provider choice or storage | `Gate2FinancialEvidenceMaterializerFactory.create().materialize` | Generic Financial Materialization | Financial Domain and explicit compatibility projections | materialization in qualification/evidence/consumer code |
| Financial Domain | immutable snapshot, bounded query semantics and serialization envelope | raw source/provider reads or Gate 3 reconciliation | catalog, query and persistence factories | Managed Financial Domain and Query API | Gate 3 Consumer and future storage adapter | direct record catalogs, query facades or snapshot minting |
| Gate 3 Consumer | checked consumption of the Financial Domain query API | Gate 1/Gate 2 storage, source parsing or domain snapshot mutation | `Gate3FinancialDomainContextFactory.create` | Query API and global gate architecture | Gate 3 successor logic | ArtifactStore/source-reader access |
| Qualification | frozen fixture/preflight, terminal classification, metrics and product-gate evaluation | product contracts, provider-specific parsing or production admission | V6 qualification fixture/preflight factories and `qualify_financial_semantic_v6` | V6 qualification harness and execution identity | qualification CLIs and Evidence | a parallel qualification framework |
| Evidence | exact private execution evidence, safe receipts, integrity and offline replay | product decisions, retries or canonical request construction | `Gate2FinancialSemanticV6DecisionEvidenceFactory.create`, replay entrypoint | V6 Exact Evidence | Qualification and offline audit | evidence-driven product mutation or raw private Git evidence |
| Compatibility | version-pinned read dispatch and explicit legacy validation | silent rewrite, new writes, semantic policy or current product logic | financial-evidence and successor compatibility factories | pinned legacy/successor schemas | migration/local-proof tooling | reimplemented current authorities behind a legacy facade |

These domains are code responsibilities, not new product gates or packages.
One domain may coordinate several distinct operation authorities listed below;
that does not permit a second owner for any operation.

## Operation authority map

| Concern | Sole authority | Contract | Consumers | Compatibility | Forbidden duplicate |
| --- | --- | --- | --- | --- | --- |
| Prompt ownership | [`financial_semantic_v6_prompt`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate2_financial_semantic_v6_prompt.py) | [V6 Choice](./BROKER_REPORTS_GATE2_FINANCIAL_SEMANTIC_CHOICE_V6.md) | request builder, qualification | version-pinned older prompts only | semantic instruction in request, adapter or runner |
| Managed model-facing asset-family identity and composition | additive [`broker_reports_financial_domain_assets.v3.manifest.json`](../../../services/broker-reports-gate1-proof/managed_assets/broker_reports_financial_domain_assets.v3.manifest.json), immutable v1/v2 predecessors, their one deterministic builder and single closed-world `load_gate2_financial_semantic_model_assets` entrypoint | [OpenWebUI Financial Domain Asset Family v3](./BROKER_REPORTS_OPENWEBUI_FINANCIAL_DOMAIN_ASSET_FAMILY.v3.md), historical [family v2](./BROKER_REPORTS_OPENWEBUI_FINANCIAL_DOMAIN_ASSET_FAMILY.v2.md) and [Outcome Taxonomy v1](./BROKER_REPORTS_GATE2_OUTCOME_TAXONOMY.v1.md) | active v1 consumers, historical non-active Context V2.0 assets and the non-active GOAL 7 minimal managed profile | family v1/v2 and Context V2.0 remain immutable; family v3 packages catalog v2 and identifies one transport-ineligible profile without changing full Pack/catalog bytes | parallel asset-family/manifest authority, in-place historical manifest rewrite, second catalog loader, financial-semantic registry, custom asset GUI or adapter-owned semantic text |
| Human decision-reason meaning | immutable historical [`broker_reports_gate2_financial_decision_reason_catalog.v1.json`](../../../services/broker-reports-gate1-proof/managed_assets/decision_reasons/broker_reports_gate2_financial_decision_reason_catalog.v1.json) plus additive inactive [`broker_reports_gate2_financial_decision_reason_catalog.v2.json`](../../../services/broker-reports-gate1-proof/managed_assets/decision_reasons/broker_reports_gate2_financial_decision_reason_catalog.v2.json), each under the same catalog ID and versioned validator boundary | [Financial Decision Reason Catalog v1](./BROKER_REPORTS_GATE2_FINANCIAL_DECISION_REASON_CATALOG.v1.md), [Outcome Taxonomy v1](./BROKER_REPORTS_GATE2_OUTCOME_TAXONOMY.v1.md) and [family v3](./BROKER_REPORTS_OPENWEBUI_FINANCIAL_DOMAIN_ASSET_FAMILY.v3.md) | v1 remains the historical non-active [Context V2.0 candidate](./BROKER_REPORTS_GATE2_LLM_SEMANTIC_CONTEXT.v2.md); family v3 packages v2 for the inactive minimal projection and Choice-owned V2.1 profile | active V6 decision/Choice still accepts only two reasons; the inactive [Local Choice V2.1](./BROKER_REPORTS_GATE2_FINANCIAL_SEMANTIC_LOCAL_CHOICE.v2.1.md) accepts all three without activation | human wording in Python, Prompt, Packet, adapter, report projector, Pack, an in-place catalog edit or a second active catalog/loader |
| Model-visible semantic context | [`Gate2FinancialSemanticV6PacketFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate2_financial_semantic_v6_packet.py); managed Pack/reason subprojection remains [`Gate2FinancialSemanticV5ProjectionFactory`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate2_financial_semantic_v5_projection.py) | implemented historical [LLM Semantic Context v1](./BROKER_REPORTS_GATE2_LLM_SEMANTIC_CONTEXT.v1.md), historical non-active [Context V2.0](./BROKER_REPORTS_GATE2_LLM_SEMANTIC_CONTEXT.v2.md), current non-active [Context V2.1](./BROKER_REPORTS_GATE2_LLM_SEMANTIC_CONTEXT.v2.1.md), [Minimal Model Surface](./BROKER_REPORTS_GATE2_MINIMAL_MODEL_SURFACE.v1.md), and [current V6 Packet](./BROKER_REPORTS_GATE2_FINANCIAL_SEMANTIC_PACKET_V6.md) | current request builder consumes only the active packet payload; the current Packet path builds one V2.1 candidate plus private exact receipt from the GOAL 7 projection; the existing Choice owner is their only inactive consumer | V2.1 is `active=false`, transport-ineligible and has no request/runtime consumer; its separate Choice profile is also inactive; current four-block V6 packet stays exact | second Packet/context/projection builder, per-request historical V2.0 construction, unallowlisted model-visible field or provider-side semantic context rewrite |
| Complete model-visible request lint | [`Gate2FinancialSemanticV6ContextLinterFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate2_financial_semantic_v6_context_linter.py) | implemented [LLM Semantic Context v1](./BROKER_REPORTS_GATE2_LLM_SEMANTIC_CONTEXT.v1.md)/[Local Choice v1](./BROKER_REPORTS_GATE2_FINANCIAL_SEMANTIC_LOCAL_CHOICE.v1.md); future V2.1 extension constrained by the [Minimal Model Surface](./BROKER_REPORTS_GATE2_MINIMAL_MODEL_SURFACE.v1.md) and [Local Choice V2.1](./BROKER_REPORTS_GATE2_FINANCIAL_SEMANTIC_LOCAL_CHOICE.v2.1.md) | version-pinned candidate request profile before provider projection/transport | **STOP before GOAL 10:** no V2.1 linter/sealed request until reviewed, green GOAL 9 is merged; linter consumes but never invents Choice schema | direct candidate transport, a second packet/Choice builder, context repair, an unsealed request, a linter that cements V2.0, or linter-built/invented Choice schema |
| Provider request construction | [`Gate2OpenWebUIRequestBuilder.build`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate2_model_requests.py) | provider-neutral Prompt/package/choice contracts | structured model client; delegating evidence helper | wrappers validate then delegate | direct `form_data` assembly in evidence or qualification |
| Provider response-format projection | [`Gate2ProviderAdapterFactory.create` and adapter `prepare_form_data`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate2_provider_adapters.py) | canonical choice schema projected to the provider-supported subset | structured model client | provider profile selects one adapter | provider-schema rewrites in request, qualification or evidence code |
| Provider response parsing | [`Gate2ProviderAdapterFactory.create` and adapter `extract_content` / `provider_error_code`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate2_provider_adapters.py) | [`Gate2StructuredModelResult`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate2_model_contracts.py) | structured model client | provider profiles select an adapter | provider payload parsing in qualification or product code |
| Provider usage normalization | [adapter `execution_metadata`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate2_provider_adapters.py) | [`Gate2ProviderExecutionMetadata`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate2_model_contracts.py) | model client, budget, evidence | adapter normalizes provider variants | provider token-field reads outside adapters |
| Budget admission/accounting | [`Gate2EconomyBudgetSessionFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate2_economy_budget.py) | economy budget v1 code contract | structured model client | none | token or cost policy in callers/adapters |
| Semantic Pack meaning | [`Gate2FinancialSemanticContractFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate2_financial_semantic_contract.py) | [Financial Semantic Pack](./BROKER_REPORTS_FINANCIAL_SEMANTIC_PACK.v1.md) | projection, compiler, validator, materializer, Financial Domain | V5-named projection is shared by V6 | financial type IDs, roles or ambiguity rules in Python |
| Evidence Bundle | [`Gate2FinancialEvidenceBundleFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate2_financial_semantic_v6_bundle.py) | [Evidence Bundle](./BROKER_REPORTS_GATE2_FINANCIAL_EVIDENCE_BUNDLE.v1.md) | compiler, packet, expansion, replay | none | second sealed source/provenance projection |
| Typed Option compilation | [`Gate2FinancialCandidateCompilerFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate2_financial_semantic_v6_candidate_compiler.py) using [`Gate2FinancialTypedOptionFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate2_financial_semantic_v6_typed_option.py) | [Candidate Compiler](./BROKER_REPORTS_GATE2_FINANCIAL_CANDIDATE_COMPILER.v1.md), [Typed Option](./BROKER_REPORTS_GATE2_FINANCIAL_TYPED_OPTION.v1.md) | packet, qualification, replay | none | financial regex, known type IDs or provider-built options |
| Semantic choice | [`Gate2FinancialSemanticV6ChoiceContractFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate2_financial_semantic_v6_choice.py) | active [V6 Choice](./BROKER_REPORTS_GATE2_FINANCIAL_SEMANTIC_CHOICE_V6.md), historical [Local Choice v1](./BROKER_REPORTS_GATE2_FINANCIAL_SEMANTIC_LOCAL_CHOICE.v1.md), inactive [Local Choice V2.1](./BROKER_REPORTS_GATE2_FINANCIAL_SEMANTIC_LOCAL_CHOICE.v2.1.md) | active request builder/expansion/evidence; inactive V2.1 parser proof only | active exact-ID bytes and historical Local v1 remain pinned; V2.1 restores only through its private receipt | alternative Choice factory/schema authority, index-derived restoration or model-generated records/bindings |
| Canonical decision expansion | [`Gate2FinancialSemanticV6DecisionExpansionFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate2_financial_semantic_v6_expansion.py) | [V6 Expansion](./BROKER_REPORTS_GATE2_FINANCIAL_DECISION_EXPANSION_V6.md) | materializer, qualification, replay | none | choice-to-record expansion in runner/evidence code |
| Validator | [`Gate2FinancialEvidenceValidatedDecisionFactory.create` and `validate_financial_evidence_inputs`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate2_financial_evidence_materialization.py) | [Generic Materialization](./BROKER_REPORTS_GATE2_GENERIC_FINANCIAL_MATERIALIZATION.v1.md) | materializer, qualification, local proofs | legacy validators remain version-pinned | weaker local acceptance or provider output as authority |
| Materializer | [`Gate2FinancialEvidenceMaterializerFactory.create().materialize`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate2_financial_evidence_materialization.py) | [Generic Materialization](./BROKER_REPORTS_GATE2_GENERIC_FINANCIAL_MATERIALIZATION.v1.md) | Financial Domain, explicit compatibility projections | projections read canonical output | ID, binding, provenance or retention minting elsewhere |
| Persistence | [`Gate2FinancialDomainPersistenceFactory.serialize/restore`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate2_financial_domain_persistence.py) | [Managed Financial Domain](./BROKER_REPORTS_MANAGED_FINANCIAL_DOMAIN.v1.md) | local proof, future storage adapter | restore validates the current envelope | a storage adapter reimplementing serialization or minting snapshots |
| Financial Domain snapshot | [`Gate2FinancialDomainCatalogFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate2_financial_domain_catalog.py) | [Managed Financial Domain](./BROKER_REPORTS_MANAGED_FINANCIAL_DOMAIN.v1.md) | query and persistence factories | explicit legacy/successor readers only | direct record catalogs or mutable snapshots |
| Query API | [`Gate2FinancialDomainQueryFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate2_financial_domain_query.py) | [Query API](./BROKER_REPORTS_GATE2_FINANCIAL_DOMAIN_QUERY_API.v1.md) | Gate 3 consumer | none | query facades over raw records/sources |
| Gate 3 consumer | [`Gate3FinancialDomainContextFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate3_financial_domain_context.py) | [Query API](./BROKER_REPORTS_GATE2_FINANCIAL_DOMAIN_QUERY_API.v1.md) and global gate architecture | Gate 3 successor logic | legacy context manifest remains separate | ArtifactStore, Gate 1 reader or provider access |
| Qualification result | [`qualify_financial_semantic_v6`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate2_financial_semantic_v6_qualification_run.py) | [V6 Qualification Harness](./BROKER_REPORTS_GATE2_FINANCIAL_SEMANTIC_V6_QUALIFICATION_HARNESS.md) | qualification CLI, safe receipt | older runners are replay-only | parallel result classifier or production admission |
| Evidence storage | [`Gate2FinancialSemanticV6DecisionEvidenceFactory.create`, private-evidence restore and replay](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate2_financial_semantic_v6_evidence.py); safe receipt [`write_safe_receipt_atomically`](../../../services/broker-reports-gate1-proof/scripts/live_gate2_financial_semantic_v6_qualification.py); allowlisted synthetic smoke projection [`Gate2FinancialSemanticV6TransparentSmokeReportFactory`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate2_financial_semantic_v6_smoke_report.py) | [V6 Exact Evidence](./BROKER_REPORTS_GATE2_FINANCIAL_SEMANTIC_V6_EXACT_EVIDENCE.md) | qualification, offline audit, synthetic smoke report | private exact evidence stays outside Git; safe receipts are projections; exact readable context is limited to frozen synthetic smoke cases | raw private evidence in Git, actual-corpus transparent projection, evidence-driven product mutation or retry |

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
  `gate3_financial_domain_context.py` is the Financial Domain successor
  consumer. The successor is intentionally forbidden from importing the
  legacy manifest or Gate 1 readers.
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
6. **STOP before GOAL 10:** after reviewed, green GOAL 9 is merged, GOAL 10 may
   add only the V2.1 linter/budget guard and sealed request by consuming the
   P01-P18 Prompt, Packet candidate and Choice-owned schema.

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

The profile has no request/runtime consumer. The third reason is intentionally
not admitted to active V6 Expansion/materialization in this goal. Provider
calls, adapter changes, managed-asset changes, benchmark runs and runtime
activation are zero. GOAL 10 remains blocked until the GOAL 9 PR is
fresh-reviewed, green in real GitHub Actions and merged.

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
Packet construction and Choice-owned GOAL 9 response profile are its only
consumers; neither is a request, transport or runtime consumer. The next
boundary is the GOAL 10 linter/sealed-request STOP.
Current non-active V2.1 uses the Minimal Model Surface instruction, not the historical
V2.0 complete-prebound task.

## Documentation drift and explicit debt

1. The global gate architecture remains normative but does not index the newer
   V6 compiler, choice, expansion, Managed Financial Domain and query owners.
2. Generated bundles are deterministically rebuilt and tested, but their file
   headers do not make generated-only status obvious.
3. Financial Domain persistence owns an envelope, not a storage backend. A
   future storage adapter must delegate serialization and may not mint snapshot
   authority.
4. The OpenAI root-object projection is implemented locally in the existing
   adapter. Provider smoke remains intentionally not run until the V6
   completion program reaches its separately authorized smoke goal.

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
