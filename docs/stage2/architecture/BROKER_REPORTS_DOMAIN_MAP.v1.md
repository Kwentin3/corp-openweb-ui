# Broker Reports Domain Map v1

Status: `HISTORICAL_DOMAIN_MAP_WITH_CURRENT_PDF_BOUNDARY`

Effective date: 2026-09-03

Scope: Broker Reports / NDFL, Gate 1 through Gate 4

This map is a preserved pre-Gate-3 owner snapshot. Its case-assembly Gate 3
assignment and “normative” wording are historical. Current gate meaning is
owned only by
[Pipeline Gates v1](../contracts/BROKER_REPORTS_PIPELINE_GATES.v1.md); current
implementation ownership is in
[Architecture Authorities](../contracts/BROKER_REPORTS_ARCHITECTURE_AUTHORITIES.md).

## Precedence and reading rule

This map names domain boundaries and their maintained owners. Versioned
contracts remain authoritative for payload shape and validation. The global
gate architecture remains authoritative for gate placement. The sole-owner
matrix remains authoritative when two documents appear to name competing
write paths.

Owner modules, symbols, responsibilities, exclusions, consumers, runtime
status, adjacent historical routes, and change gates are maintained in
`docs/stage2/architecture/BROKER_REPORTS_OWNER_CONTEXT.v1.json`. Production
Python comments are not an architecture authority and are not required for
owner discovery.

The current PDF information flow is:

`authenticated bytes -> source custody / safe preflight -> PdfDocumentExtractor -> PdfDocumentExtraction -> existing Full Source / Canonical downstream`

Until an adapter is separately integrated and qualified,
`PdfDocumentExtractorFactory` selects the unconfigured implementation and
returns `PDF_DOCUMENT_AI_NOT_CONFIGURED`. This source-normalization owner is
not a second Canonical or financial-semantic owner. No engine fallback exists.

The current non-PDF information flow is:

`document bytes -> deterministic normalization -> Gate 2 package -> source facts -> financial decision -> canonical materialization -> ArtifactStore -> AnswerContext / Gate 3 manifest -> future Gate 4`

Provider output is always a proposal. It never becomes canonical authority by
transport success alone.

## 1. Document intake and detection

- **Purpose:** admit supported document bytes and identify bounded source units
  and table candidates without applying financial meaning.
- **Business meaning:** a document and its recoverable regions exist; nothing
  has yet been classified as an income, trade, fee, or tax fact.
- **Inputs:** immutable file bytes, declared file metadata, access context.
- **Outputs:** source artifacts, passports, source units and supported non-PDF
  table projections.
- **Current sole owner:** `Gate1Normalizer` and format-specific factories;
  `PdfDocumentExtractor` for PDF understanding after shared custody/preflight.
- **Allowed consumers:** source provenance and declared downstream contracts.
- **Forbidden knowledge:** financial type choice, NDFL calculation, declaration
  fields, Gate 2 canonical facts.
- **Runtime status:** `ACTIVE_PRODUCT`.
- **Evidence:** terminal Gate 1 outcomes, source/candidate manifests, safe
  receipts, ArtifactStore references.
- **Open debt:** none for live bundle parity; KT1.5 closed exact parity.
- **Adjacent domains:** PDF Document AI, OpenWebUI Pipe boundary, ArtifactStore.
- **Completion criterion:** every admitted byte range has a terminal,
  reproducible source outcome or an explicit fail-closed reason.

## 2. PDF Document AI boundary

- **Purpose:** isolate all PDF understanding behind one replaceable port.
- **Inputs:** authenticated PDF bytes and shared source context after custody
  and safe preflight.
- **Output:** immutable provider-neutral `PdfDocumentExtraction`, or a typed
  fail-closed outcome.
- **Current sole owner:** `PdfDocumentExtractor`; selection belongs only to
  `PdfDocumentExtractorFactory`.
- **Allowed consumers:** existing Full Source / Canonical downstream through
  the provider-neutral envelope.
- **Forbidden knowledge outside adapter/composition:** provider schema/model,
  OCR options, bbox/crop/DPI, raw response, table reconstruction, retry or
  fallback.
- **Runtime status:** `ACTIVE_FAIL_CLOSED`; no live adapter is configured.
- **Completion criterion:** `PDF_DOCUMENT_AI_NOT_CONFIGURED` before network, or
  one qualified adapter returns a contract-valid envelope.

## 3. Gate 2 table package

- **Purpose:** project accepted Gate 1 tables into the bounded input contract
  consumed by Gate 2 extraction.
- **Business meaning:** a table is ready for source-fact analysis; it has not
  itself become a financial fact.
- **Inputs:** validated supported non-PDF table projection plus source lineage.
- **Outputs:** `broker_reports_gate2_table_package_v1` packages.
- **Current sole owner:** `Gate2TablePackageFactory.create`.
- **Allowed consumers:** Gate 2 input-readiness, segmentation, routing,
  source-fact runtimes.
- **Forbidden knowledge:** final fact acceptance, financial semantic choice,
  AnswerContext selection, tax calculation.
- **Runtime status:** `ACTIVE_PRODUCT`.
- **Evidence:** package validation, source accounting, ArtifactStore refs.
- **Open debt:** none created by KT1.
- **Adjacent domains:** source normalization, source-fact extraction,
  ArtifactStore.
- **Completion criterion:** each package validates and points to one
  reproducible source projection.

## 4. Source-fact extraction

- **Purpose:** extract source-local candidate facts, validate them against
  visible evidence, and stitch accepted facts.
- **Business meaning:** facts remain grounded in source units; semantic
  uncertainty is explicit and code-owned validation is final.
- **Inputs:** Gate 2 packages, routed/segmented source units, managed prompt
  identity, structured model proposal where applicable.
- **Outputs:** canonical source facts, validation outcomes, stitch result,
  terminal Gate 2 run.
- **Current sole owner:** `Gate2DomainSourceFactRuntimeFactory.create` for the
  product route; `Gate2SourceFactValidatorFactory.create` and
  `Gate2SourceFactStitcherFactory.create` retain their validation and stitching
  responsibilities.
- **Allowed consumers:** financial decision preparation, ArtifactStore,
  AnswerContext, Gate 3 manifest.
- **Forbidden knowledge:** crop bytes, visual transcription, provider-specific
  transport fields, NDFL calculation or declaration generation.
- **Runtime status:** `ACTIVE_PRODUCT`.
- **Evidence:** domain package, model execution metadata, validation records,
  stitch artifact, terminal run record.
- **Open debt:** reconcile future financial semantic convergence without
  activating a second extraction route.
- **Adjacent domains:** Gate 2 package, financial decision, AnswerContext.
- **Completion criterion:** every package is accounted for by an accepted,
  unclassified, unsupported, no-fact, or failed terminal disposition.

## 5. Financial semantic decision

- **Purpose:** select or reject a bounded financial interpretation from
  code-owned candidates.
- **Business meaning:** the model may choose only among allowed plausible
  interpretations; it cannot mint facts, lineage, or records.
- **Inputs:** canonical source evidence, registry/type-card snapshot, bounded
  code-owned options.
- **Outputs:** exact semantic choice and deterministic expanded decision.
- **Current sole owner:** `Gate2FinancialSemanticV6ChoiceContractFactory.create`
  for choice parsing and
  `Gate2FinancialSemanticV6DecisionExpansionFactory.create` for expansion.
- **Allowed consumers:** canonical financial validation/materialization and
  evidence/replay.
- **Forbidden knowledge:** PDF/crop bytes, source parsing, storage IDs,
  retention, Gate 4 calculation.
- **Runtime status:** the established V6 authorities exist; the GOAL 17
  Type-First proposal is `CONTRACT_ONLY` on main and must not be product
  reachable.
- **Evidence:** packet/choice/expansion receipts and zero-call or qualification
  evidence explicitly allowed by their contracts.
- **Open debt:** converge only through a future same-source contract and proof;
  no KT1 activation.
- **Adjacent domains:** source facts, canonical materialization, provider
  boundary, replay.
- **Completion criterion:** exactly one allowed terminal disposition is
  deterministically expanded and independently reproducible.

## 6. Canonical financial materialization

- **Purpose:** validate a financial decision against authoritative source
  values and create canonical financial evidence.
- **Business meaning:** only code promotes evidence into durable financial
  structures.
- **Inputs:** expanded decision, authoritative source package, registry and
  contract snapshots, execution metadata.
- **Outputs:** validated decision and canonical financial evidence inputs.
- **Current sole owner:** `Gate2FinancialEvidenceValidatedDecisionFactory.create`
  and `Gate2FinancialEvidenceMaterializerFactory.create().materialize`.
- **Allowed consumers:** financial-domain persistence, replay, Gate 3 query
  boundary.
- **Forbidden knowledge:** crop bytes, provider-native payloads, alternate
  materializers, tax calculation.
- **Runtime status:** `ACTIVE_PRODUCT` authority; candidate callers remain
  governed by their own activation status.
- **Evidence:** validation and materialization hashes, totality checks, persisted
  snapshot refs.
- **Open debt:** no second materializer may be introduced by convergence.
- **Adjacent domains:** financial decision, ArtifactStore, replay, Gate 3.
- **Completion criterion:** all accepted decisions materialize through this
  authority or fail closed without partial canonical output.

## 7. Artifact persistence

- **Purpose:** persist immutable artifacts and resolve them under access and
  retention policy.
- **Business meaning:** durable evidence is append-only, scoped, and
  reference-based.
- **Inputs:** validated domain artifacts, access context, lifecycle metadata,
  retention policy.
- **Outputs:** immutable records, references, resolution results.
- **Current sole owner:** `ArtifactStoreFactory` and `ArtifactResolver`.
- **Allowed consumers:** all gate services through declared ports and
  references.
- **Forbidden knowledge:** business classification, provider repair, implicit
  filesystem reads, mutable overwrite semantics.
- **Runtime status:** `ACTIVE_PRODUCT`.
- **Evidence:** append-only record lineage, hashes, lifecycle and access
  receipts.
- **Open debt:** none created by KT1.
- **Adjacent domains:** every producing domain, AnswerContext, Gate 3.
- **Completion criterion:** persisted artifacts are independently resolvable and
  hash-verifiable under the same access context.

## 8. Replay and comparators

- **Purpose:** reconstruct prior decisions and compare the exact governed
  authorities without calling providers.
- **Business meaning:** replay proves determinism and detects drift; it does not
  create a new decision policy.
- **Inputs:** private evidence bundle, safe receipt, contract and registry
  snapshots.
- **Outputs:** replay result, exact comparator outcome, safe integrity status.
- **Current sole owner:** `Gate2FinancialSemanticV6DecisionEvidenceFactory` and
  `replay_financial_semantic_v6_decision`.
- **Allowed consumers:** tests, qualification evidence checks, audit reports.
- **Forbidden knowledge:** retries, repair, fallback, new semantic decisions,
  activation.
- **Runtime status:** `PROOF_ONLY` unless explicitly consumed by an established
  read path.
- **Evidence:** serialized/restored evidence hash and exact replay comparison.
- **Open debt:** future Type-First evidence, if authorized, must reuse this
  boundary instead of minting a parallel replay framework.
- **Adjacent domains:** financial decision, canonical materialization,
  release verification.
- **Completion criterion:** reconstructed outputs and all governed request,
  choice, validation, and materialization identities compare exactly.

## 9. AnswerContext

- **Purpose:** select the bounded evidence view presented after a completed
  Gate 2 run.
- **Business meaning:** it is a downstream presentation context, not an input
  to financial classification.
- **Inputs:** completed terminal Gate 2 run, stitch result, allowed table
  provenance and ArtifactStore refs.
- **Outputs:** answer context and selection receipt.
- **Current sole owner:** `AnswerContextSelectionFactory.create`.
- **Allowed consumers:** final answer/report projection.
- **Forbidden knowledge:** raw sources, crop bytes, provider output, incomplete
  Gate 2 runs, financial choice input.
- **Runtime status:** `ACTIVE_PRODUCT`.
- **Evidence:** selection receipt, run identity, selected representation refs.
- **Open debt:** none created by KT1.
- **Adjacent domains:** source facts, ArtifactStore, Gate 3.
- **Completion criterion:** one representation per evidence group is selected
  only after Gate 2 reaches a completed terminal state.

## 10. Gate 3 context manifest

- **Purpose:** seal the declared Gate 2 exit artifacts consumed by future or
  present Gate 3 readers.
- **Business meaning:** it is the context boundary for reconciliation/query,
  not a hidden business runtime.
- **Inputs:** terminal Gate 2 artifacts and refs, access context.
- **Outputs:** validated Gate 3 context manifest and input status.
- **Current sole owner:** `Gate3ContextManifestFactory.create`.
- **Allowed consumers:** declared Gate 3 business/query consumers.
- **Forbidden knowledge:** Gate 1 raw bytes, provider payloads, undeclared
  storage reads, Gate 4 tax policy.
- **Runtime status:** `ACTIVE_PRODUCT` boundary; broader Gate 3 business scope
  remains separately governed.
- **Evidence:** manifest integrity hash and descendant-ref validation.
- **Open debt:** no new Gate 3 capability is authorized by KT1.
- **Adjacent domains:** ArtifactStore, financial domain, Gate 4.
- **Completion criterion:** manifest validation independently proves the
  complete allowed input set and rejects undeclared descendants.

## 11. Gate 4 calculation and declaration

- **Purpose:** calculate and assemble tax/declaration outputs from accepted
  upstream domain facts.
- **Business meaning:** tax treatment and declaration preparation are separate
  from extraction and financial semantic interpretation.
- **Inputs:** future governed Gate 3 outputs and explicit tax policy.
- **Outputs:** future calculation/declaration artifacts and receipts.
- **Current sole owner:** none; no production owner is admitted.
- **Allowed consumers:** none until a separately approved Gate 4 contract and
  runtime exist.
- **Forbidden knowledge:** direct source/crop/provider access and bypass of
  Gate 2/3 manifests.
- **Runtime status:** `CONTRACT_ONLY`.
- **Evidence:** future architecture decision and executable acceptance proof.
- **Open debt:** define Gate 4 contracts and owner in a separate checkpoint.
- **Adjacent domains:** Gate 3, ArtifactStore, final presentation.
- **Completion criterion:** a separate approved contract names one owner,
  inputs, outputs, rollback, and independent verification.

## 12. OpenWebUI adapter and Pipe boundary

- **Purpose:** adapt chat/file requests to maintained Broker Reports factories
  without moving business logic into OpenWebUI.
- **Business meaning:** OpenWebUI is a host and transport boundary, not a source
  of canonical financial policy.
- **Inputs:** user request, files, valves, OpenWebUI request context.
- **Outputs:** calls to maintained factories and bounded chat responses. The
  Issue #310 presentation sub-boundary has exactly two owners: Pipe owns the
  pinned HTTPS/no-redirect/byte-bounded OpenWebUI transport; the declaration
  chat adapter owns the safe public context, strict dialogue validation and
  deterministic literal-answer proposal. Neither owns Human Facts.
- **Current sole owner:** maintained
  `openwebui_actions/broker_reports_*_pipe.py` adapters; generated bundles are
  closed-world outputs only.
- **Allowed consumers:** OpenWebUI Function runtime.
- **Forbidden knowledge:** duplicate validators/materializers, hidden RAG,
  workspace imports, business policy in bundles, caller-derived presentation
  origins, or model interpretation/publication of Human answers.
- **Runtime status:** `ACTIVE_PRODUCT` in repository.
- **Evidence:** bundle parity tests, factory-call tests, closed-world checks.
- **Open debt:** none for live bundle parity.
- **Adjacent domains:** intake, source facts, provider boundary, release.
- **Completion criterion:** every product action routes through a named factory,
  generated bundles match maintained inputs, and no OpenWebUI core fork exists.

## 13. Model and provider boundary

- **Purpose:** project a canonical request to a provider and normalize one
  terminal response.
- **Business meaning:** transport executes an already governed decision task;
  it does not define that task.
- **Inputs:** sealed request, provider profile, budget authorization.
- **Outputs:** normalized terminal model result and execution metadata.
- **Current sole owner:** `Gate2OpenWebUIRequestBuilder`,
  `Gate2ProviderAdapterFactory`, `Gate2StructuredModelClientFactory` for
  semantic mapping. Future PDF transport belongs only inside the separately
  authorized Document AI adapter.
- **Allowed consumers:** explicitly admitted Gate 1/Gate 2 runtimes and bounded
  qualification harnesses.
- **Forbidden knowledge:** canonical promotion, source ownership, financial
  record creation, retry/repair/fallback unless a versioned contract permits
  it.
- **Runtime status:** route-specific; GOAL 17 Type-First provider calls remain
  zero and product unreachable.
- **Evidence:** sealed request hashes, adapter metadata, budget receipt,
  terminal execution outcome.
- **Open debt:** no candidate/provider qualification is authorized by KT1.
- **Adjacent domains:** semantic transcription, financial decision, release.
- **Completion criterion:** one sealed request produces one terminal normalized
  outcome with exact provider identity and no hidden retry.

## 14. Release and parity verification

- **Purpose:** prove repository, generated bundles, staged Function state, and
  readback agree before release claims.
- **Business meaning:** deployment transport success is not acceptance.
- **Inputs:** committed repository state, generated bundles, live read-only
  snapshots where authorized.
- **Outputs:** parity verdict, rollback/readback evidence, release receipt.
- **Current sole owner:** `scripts/live_verify_broker_reports_stage2_delivery.py`
  for read-only repository/live verification; atomic stage scripts remain
  separately governed.
- **Allowed consumers:** release operators, CI, audit reports.
- **Forbidden knowledge:** business semantics, implicit deployment, mutation by
  a read-only verifier.
- **Runtime status:** repository checks are active; live parity is
  `VERIFIED_LIVE` at operational authority
  `db009421b68c8b09df728239d23c217e5482d3a1`.
- **Evidence:** exact bundle hashes, Function/prompt snapshots, terminal
  readback and rollback proof when a release is authorized.
- **Open debt:** none. A later product or generated-bundle change requires a
  fresh release receipt and independent readback.
- **Adjacent domains:** OpenWebUI Pipe, replay, historical routes.
- **Completion criterion:** exact committed head, generated assets, live state,
  rollback and independent readback all pass the governing release contract.

## 15. Historical and compatibility routes

- **Purpose:** preserve reproducibility and narrow compatibility without
  competing with current product owners.
- **Business meaning:** old artifacts remain readable; historical code is not
  evidence of current activation.
- **Inputs:** pinned historical artifacts and version-specific contracts.
- **Outputs:** bounded validation, replay, migration, or compatibility
  delegation.
- **Current sole owner:** each pinned historical validator/wrapper only for its
  exact version; no shared production write authority.
- **Allowed consumers:** historical replay, migration, audit, tests explicitly
  named by version.
- **Forbidden knowledge:** product routing, new writes, silent fallback,
  current-policy decisions.
- **Runtime status:** `HISTORICAL_READ_ONLY` or `COMPATIBILITY_ONLY`.
- **Evidence:** exact version/hash binding and architecture containment tests.
- **Open debt:** retire `source_fact_selection_v3` after preserved evidence no
  longer needs executable compatibility.
- **Adjacent domains:** source facts, replay, release verification.
- **Completion criterion:** every historical path is explicitly contained,
  has no product consumer, and names its allowed archival consumers.

## Cross-domain invariants

1. A responsibility has one maintained write owner.
2. Visual transcription cannot classify finance.
3. Financial semantic models cannot receive crop or document bytes.
4. Canonical financial materialization has one authority.
5. AnswerContext is post-Gate-2 and presentation-only.
6. Historical status never implies activation.
7. Generated bundles are outputs, not owners.
8. Artifact persistence is reference-based and append-only.
9. Gate 4 cannot read around Gate 3.
10. A live claim requires live parity evidence for the exact committed head.
