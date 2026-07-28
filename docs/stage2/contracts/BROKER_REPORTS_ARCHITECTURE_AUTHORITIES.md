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
| Semantic Matcher | current four-block packet, versioned model-visible context boundary, semantic instruction, complete-request lint, provider-neutral minimal choice and deterministic choice expansion | source refs/provenance ownership, canonical acceptance or persistence | V6 packet/Prompt/Choice factories, `Gate2FinancialSemanticV6ContextLinterFactory.create` and `Gate2FinancialSemanticV6DecisionExpansionFactory.create` | V6 Packet, LLM Semantic Context, Choice and Expansion | Qualification, Validation, Evidence | model-generated records, bindings, second packet builder or alternative choice schema |
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
| Model-visible semantic context | [`Gate2FinancialSemanticV6PacketFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate2_financial_semantic_v6_packet.py) | [LLM Semantic Context v1](./BROKER_REPORTS_GATE2_LLM_SEMANTIC_CONTEXT.v1.md), [current V6 Packet](./BROKER_REPORTS_GATE2_FINANCIAL_SEMANTIC_PACKET_V6.md) | request builder and qualification after an explicit version-pinned route exists | current four-block V6 packet remains active until a separately qualified activation | second packet builder, unallowlisted model-visible field or provider-side semantic context rewrite |
| Complete model-visible request lint | [`Gate2FinancialSemanticV6ContextLinterFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate2_financial_semantic_v6_context_linter.py) | [LLM Semantic Context v1](./BROKER_REPORTS_GATE2_LLM_SEMANTIC_CONTEXT.v1.md), [Local Choice v1](./BROKER_REPORTS_GATE2_FINANCIAL_SEMANTIC_LOCAL_CHOICE.v1.md) | version-pinned candidate request profile before provider projection/transport | current active V6 packet/Choice route remains unchanged; exact replay is local | direct candidate transport, a second packet/Choice builder, context repair or an unsealed request |
| Provider request construction | [`Gate2OpenWebUIRequestBuilder.build`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate2_model_requests.py) | provider-neutral Prompt/package/choice contracts | structured model client; delegating evidence helper | wrappers validate then delegate | direct `form_data` assembly in evidence or qualification |
| Provider response-format projection | [`Gate2ProviderAdapterFactory.create` and adapter `prepare_form_data`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate2_provider_adapters.py) | canonical choice schema projected to the provider-supported subset | structured model client | provider profile selects one adapter | provider-schema rewrites in request, qualification or evidence code |
| Provider response parsing | [`Gate2ProviderAdapterFactory.create` and adapter `extract_content` / `provider_error_code`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate2_provider_adapters.py) | [`Gate2StructuredModelResult`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate2_model_contracts.py) | structured model client | provider profiles select an adapter | provider payload parsing in qualification or product code |
| Provider usage normalization | [adapter `execution_metadata`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate2_provider_adapters.py) | [`Gate2ProviderExecutionMetadata`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate2_model_contracts.py) | model client, budget, evidence | adapter normalizes provider variants | provider token-field reads outside adapters |
| Budget admission/accounting | [`Gate2EconomyBudgetSessionFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate2_economy_budget.py) | economy budget v1 code contract | structured model client | none | token or cost policy in callers/adapters |
| Semantic Pack meaning | [`Gate2FinancialSemanticContractFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate2_financial_semantic_contract.py) | [Financial Semantic Pack](./BROKER_REPORTS_FINANCIAL_SEMANTIC_PACK.v1.md) | projection, compiler, validator, materializer, Financial Domain | V5-named projection is shared by V6 | financial type IDs, roles or ambiguity rules in Python |
| Evidence Bundle | [`Gate2FinancialEvidenceBundleFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate2_financial_semantic_v6_bundle.py) | [Evidence Bundle](./BROKER_REPORTS_GATE2_FINANCIAL_EVIDENCE_BUNDLE.v1.md) | compiler, packet, expansion, replay | none | second sealed source/provenance projection |
| Typed Option compilation | [`Gate2FinancialCandidateCompilerFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate2_financial_semantic_v6_candidate_compiler.py) using [`Gate2FinancialTypedOptionFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate2_financial_semantic_v6_typed_option.py) | [Candidate Compiler](./BROKER_REPORTS_GATE2_FINANCIAL_CANDIDATE_COMPILER.v1.md), [Typed Option](./BROKER_REPORTS_GATE2_FINANCIAL_TYPED_OPTION.v1.md) | packet, qualification, replay | none | financial regex, known type IDs or provider-built options |
| Semantic choice | [`Gate2FinancialSemanticV6ChoiceContractFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate2_financial_semantic_v6_choice.py) | [V6 Choice](./BROKER_REPORTS_GATE2_FINANCIAL_SEMANTIC_CHOICE_V6.md) | request builder, expansion, evidence | version-pinned older choices only | alternative choice schema or model-generated records/bindings |
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

## LLM Semantic Context v1 target boundary

The
[LLM Semantic Context v1](./BROKER_REPORTS_GATE2_LLM_SEMANTIC_CONTEXT.v1.md)
is the closed target contract for the complete future model-visible financial
semantic request. It requires readable evidence-derived hierarchy, exactly one
rendered occurrence per authoritative semantic source value, omitted nulls,
local request-bound aliases and zero opaque global IDs across messages and
response schema.

The current active V6 four-block packet and V6 Choice do not claim this
conformance: they expose exact source/option identities by their historical
contracts. GOAL 0 defined the boundary; GOAL 1/2 implemented a non-active
local projection, and GOAL 3 enforces it at the candidate request boundary.
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

## Goal 8 acceptance

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

## Goal 9 acceptance

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
