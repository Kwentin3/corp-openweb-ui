# Broker Reports Global Gate Architecture

Date: 2026-07-21

Status: `VERSIONED_NORMATIVE_ARCHITECTURE_POLICY_V1`

Scope: the global Broker Reports product pipeline. This document does not
number repository-wide Stage 2 governance gates and does not redefine local
format-capability gates.

## 1. Authority and decision

This document is the single architectural authority for Broker Reports gate
placement, runtime policy, domain ownership and terminology.  Versioned runtime
contracts implement this authority; per-gate blueprints elaborate it; dated
reports prove one revision and scope; research reports preserve non-normative
history.  None of those sources may override this document implicitly.

The following policy decisions are normative:

1. Broker Reports is a separate controlled source-processing pipeline.  Its
   source documents never enter native OpenWebUI document processing,
   Knowledge, RAG, embeddings or vectorization.
2. Gate 1 owns source text/order/layout, canonical neutral tables, visual
   evidence, provenance and structural uncertainty.  Gate 2 starts only at
   typed source facts and source-local financial roles.  Gate 3 and Gate 4 are
   outside the current recovery program.
3. Text-layer PDF processing remains deterministic.  Visual recovery is a
   bounded exception accepting exactly one declared page or one bounded table
   crop with source and image lineage; whole-document provider upload is
   forbidden when that smaller scope exists.
4. Production visual-table provider profiles are exactly `google_gemini` and
   `openai_gpt`.  Provider output is a typed proposal.  Confidence, provider
   agreement and raw model output have zero canonical authority.
5. Canonical promotion belongs only to maintained deterministic validators and
   explicit source-to-table accounting.  Ambiguity terminates in review,
   rejection or fail-closed unresolved state.
6. PaddleOCR, PaddleOCR-VL and comparable heavy local OCR frameworks are outside
   production runtime.  Preserved implementations are `proof_only`,
   `offline_only` or `unsupported_runtime`; they are not bundle dependencies or
   capacity assumptions.
7. Private payloads are resolved only through `ArtifactResolver` under trusted
   server context.  Customer documents, values, crops, raw provider responses
   and local paths never enter Git or safe reports.
8. The frozen Sber profile and its unseen positive holdout are governed by
   [Broker Reports Customer Test Debt v1](../../contracts/BROKER_REPORTS_CUSTOMER_TEST_DEBT.v1.md):
   implementation proof is preserved, generalization is external debt and the
   release valve remains default-off.

The global product sequence has four gates:

| Global gate | Canonical name | Ownership boundary |
| --- | --- | --- |
| Gate 1 | Source Intake and Representation Normalization | Preserve what the source contains and how it is structured. |
| Gate 2 | Source-Local Semantic Interpretation | Decide what one normalized source unit means and emit validated typed source facts. |
| Gate 3 | Case Assembly and Deterministic Reconciliation | Combine source facts across units/documents, resolve duplicates/conflicts and build traceable ledgers/calculation results. |
| Gate 4 | Tax and Declaration Output Preparation | Apply approved tax methodology, build the declaration-oriented model, review it and prepare controlled outputs. |

This division follows data ownership, not historical filenames. It keeps
representation-preserving normalization separate from financial meaning,
source-local meaning separate from cross-document conclusions, and financial
reconciliation separate from tax/declaration decisions.

## 2. Plain-language diagram

```text
uploaded source
  |
  v
Global Gate 1: preserve source representation
  output: validated normalized artifacts + Domain Context Packet
  |
  v
Global Gate 2: interpret one bounded source unit
  output: validator-accepted source facts + terminal coverage/stitch
  |
  v
broker_reports_gate3_context_manifest_v0
  Gate 2 exit / Gate 3 input, declared bounded scope only
  |
  v
Global Gate 3: assemble the case
  output: reconciled events, conflicts, ledgers, deterministic traces
  |
  v
Global Gate 4: prepare tax/declaration result
  output: declaration model, review state, controlled export
```

Financial interpretation begins in global Gate 2. Cross-document reasoning
begins in global Gate 3. Tax-domain decisions and declaration/output
preparation belong to global Gate 4.

## 3. Normative gate cards

### 3.1 Global Gate 1 — Source Intake and Representation Normalization

| Field | Normative rule |
| --- | --- |
| Plain-language responsibility | Receive files and preserve their technical and structural content without deciding financial meaning. |
| Normative input | Authorized OpenWebUI file refs/original bytes plus an explicit access and retention context. |
| Normative output | Inventory, technical profiles, source eligibility, normalized text/table/source payloads and units, issue context, safe report and a validated Domain Context Packet. |
| Authoritative root | `normalization_run_v0` is the execution/lifecycle root. `domain_context_packet_v0` with resolver-linked artifacts is the authoritative Gate 1 -> Gate 2 handoff root. |
| Semantic decisions allowed | Container/format detection, readability, document taxonomy/usage classification and non-financial structural labels. |
| Semantic decisions forbidden | Typed financial facts, event consolidation, tax treatment, tax base, declaration fields and output preparation. |
| Deterministic responsibilities | Hashing, byte/profile limits, parsing, source refs, loss/truncation accounting, normalized structures, validation, access and lifecycle metadata. |
| LLM/VLM responsibilities | Bounded metadata classification or clarification; one-page/one-crop Gemini or OpenAI visual-table proposal under a strict contract. Model output never overrides parser/validator authority. |
| Validation/completeness boundary | Completeness is asserted only for the declared normalized source/document scope and its supported format profile. Unsupported, truncated or ambiguous content remains explicit. |
| Storage/access | Private source content uses `private_case` / `project_artifact_payload`. Safe indexes use `safe_internal` / `project_artifact_store`. Chat receives whitelist summaries only. |
| Entry criteria | Authorized source refs, explicit retention policy and a supported or explicitly blocked format path. |
| Exit/acceptance criteria | Valid artifact graph, exact source/ref accounting, privacy checks, explicit blockers/deferred scope and DCP readiness for the requested next stage. |
| Downstream consumer | Global Gate 2. |
| Current status | Implemented. CSV v1 whole-file normalization is stage-proven; the local PDF Table Intake child gate is closed. Global Gate 1 is only partially closed because format-specific acceptance is not universal and OCR/image-only intake remains open. |

Representation-preserving normalization ends here. Mechanically normalized
dates/numbers and structural table labels are allowed only when reproducible
from source values. Assigning a financial fact type is not normalization.

### 3.2 Global Gate 2 — Source-Local Semantic Interpretation

| Field | Normative rule |
| --- | --- |
| Plain-language responsibility | Interpret one bounded normalized source unit and produce source-visible typed financial facts with exact evidence. |
| Normative input | `domain_context_packet_v0` plus resolver-authorized Gate 1 descendants. One model call receives exactly one bounded `broker_reports_source_fact_package_v0` or domain package. |
| Normative output | Candidate/relation artifacts, raw model evidence, validated source-fact sets, issue linkage, terminal validation, stitch/coverage and the Gate 3 context manifest. |
| Authoritative root | A terminal source/domain extraction run is the execution root. `broker_reports_gate3_context_manifest_v0` is the only supported Gate 2 -> Gate 3 handoff root for a declared ready scope. |
| Semantic decisions allowed | Source-local fact type, semantic role, typed value placement, completeness/confidence and restrictions supported by one package's evidence. |
| Semantic decisions forbidden | Cross-document canonical-source choice, duplicate financial-event resolution, ledger creation, legal/tax treatment, declaration mapping and filing/output readiness. |
| Deterministic responsibilities | Package selection, candidate generation, value reproduction, schema/scope/provenance/privacy validation, exact coverage ownership, stitching and readiness recomputation. |
| LLM/VLM responsibilities | Select package-bound candidate ids, allowed roles and relations; propose typed source facts. The model cannot invent values, accept itself or reconstruct the source representation. |
| Validation/completeness boundary | Terminality and coverage apply only to the manifest's declared selected refs. Deferred refs remain outside scope. Whole-document/whole-case coverage requires an explicitly complete declared scope. |
| Storage/access | Raw output and facts are `private_case`. Runs, validations, stitch summaries and the root manifest are `safe_internal`. Resolver access must remain same-context and source-available. |
| Entry criteria | Gate 1 validation passed; DCP source-fact readiness valid; selected normalized refs resolve; issues, retention and Knowledge/RAG guards reconcile. |
| Exit/acceptance criteria | At least one validator-accepted typed fact for a ready scope, terminal package ownership, zero uncovered/conflict/unknown refs inside scope, exact provider/schema identity, and a valid persisted manifest graph. |
| Downstream consumer | Global Gate 3. |
| Current status | Contracts/runtime are implemented. Bounded source-fact paths are unit- and stage-proven, including the bounded CSV v1 vertical. Global Gate 2 is closed only for named bounded scopes; whole-document/full-corpus/all-format semantic coverage remains open. |

### 3.3 Global Gate 3 — Case Assembly and Deterministic Reconciliation

| Field | Normative rule |
| --- | --- |
| Plain-language responsibility | Combine validated source facts into one case-level financial view while preserving conflicts and deterministic traces. |
| Normative input | One ready `broker_reports_gate3_context_manifest_v0` resolved through `Gate3ContextManifestFactory.create()` / ArtifactResolver under the same access context. |
| Normative output | Reconciled event/relation sets, explicit duplicate/conflict decisions, intermediate ledgers, calculation traces and a Gate 3 -> Gate 4 case-assembly root. |
| Authoritative root | The current design target is `broker_reports_intermediate_ledgers_v0_proposal` linked by a case-assembly/case-package root. It is not yet an implemented normative runtime artifact. |
| Semantic decisions allowed | Cross-document identity/relation assembly, duplicate/conflict grouping, canonical-source decisions with evidence and case-level financial categorization. |
| Semantic decisions forbidden | Final tax treatment, declaration code/path acceptance, filing readiness and final export. |
| Deterministic responsibilities | Reconciliation, overlap detection, lot/event linkage, totals, policy-approved currency conversion and financial gain/loss calculations with trace. A model-only number can never be final. |
| LLM/VLM responsibilities | May propose relation, duplicate and ledger-placement candidates or review notes. Deterministic code/validators and explicit review own acceptance. |
| Validation/completeness boundary | Completeness is case-assembly completeness for the manifest-declared input scope, never for deferred Gate 1/Gate 2 material. Conflicts stay visible; last-writer-wins is forbidden. |
| Storage/access | Ledgers and traces remain private-case; safe roots expose refs, counts, status and restrictions only. Access/retention inherit the input graph or fail closed. |
| Entry criteria | Ready manifest, all descendants resolvable, declared scope and restrictions accepted, no inferred expansion beyond the manifest. |
| Exit/acceptance criteria | Every ledger item cites source facts; all duplicates/conflicts are resolved or explicitly open; deterministic traces reproduce; Gate 4 input scope and blockers are explicit. |
| Downstream consumer | Global Gate 4. |
| Current status | Business runtime not started. Intermediate-ledger and case-package contracts are proposals; the implemented Gate 3 context manifest is input readiness only and does not implement this gate. |

Gate ownership is not runtime permission. The current manifest v0 explicitly
sets cross-document reconciliation, duplicate resolution, tax, declaration and
XLS/XLSX permissions to false for its proven bounded CSV contour. A Gate 3
consumer must obey those restrictions. Future multi-document work needs an
explicit compatible input-contract/restriction evolution; it may not reinterpret
the current false flags.

### 3.4 Global Gate 4 — Tax and Declaration Output Preparation

| Field | Normative rule |
| --- | --- |
| Plain-language responsibility | Apply approved tax methodology to the assembled case, prepare declaration-oriented data, route specialist review and create controlled outputs. |
| Normative input | Accepted Gate 3 case-assembly/ledger root, approved official requirement refs and explicit customer methodology/version. |
| Normative output | Declaration-oriented model, review state, specialist-ready package and separately authorized export artifacts. |
| Authoritative root | `broker_reports_ndfl_declaration_model_v0` plus `broker_reports_review_state_v0_proposal`, linked by the case package. These are draft/proposal contracts, not a closed runtime output. |
| Semantic decisions allowed | Tax classification/treatment, declaration paths/codes, methodology application and specialist-review disposition. |
| Semantic decisions forbidden | Reinterpreting raw source rows, silently replacing Gate 3 reconciliation, automatic filing or claiming final tax correctness without the required acceptance authority. |
| Deterministic responsibilities | Tax-base/tax arithmetic, rate/date/rounding policy, declaration totals and export validation after methodology is approved. |
| LLM/VLM responsibilities | May propose mappings, explanations and review questions. It cannot be the final arithmetic, legal/tax or filing authority. |
| Validation/completeness boundary | Declaration completeness is assessed against the accepted Gate 3 scope, official requirements and methodology. Specialist-review readiness is distinct from filing readiness. |
| Storage/access | Tax/declaration artifacts are private-case by default; only explicitly safe review projections may be chat-visible. Export requires a separate authorized retention/delivery contract. |
| Entry criteria | Gate 3 accepted; methodology and official sources versioned; unresolved conflicts/blockers classified. |
| Exit/acceptance criteria | Deterministic calculations reproduce; every declaration candidate cites ledger/source lineage; review blockers are explicit; specialist acceptance and export authorization are recorded. |
| Downstream consumer | Specialist review and, only after separate authorization, export/filing workflows. |
| Current status | Draft/proposal contracts exist; runtime, specialist acceptance and export are not implemented or closed. |

## 4. Artifact and handoff flow

```text
OpenWebUI file refs
  -> [Gate 1 private] source bytes, normalized payloads/units/tables
  -> [Gate 1 safe] domain_context_packet_v0 + issue/eligibility refs
  -> [Gate 2 private] bounded packages + raw model output + source facts
  -> [Gate 2 safe] validations + stitch + terminal run summaries
  -> [Gate 2 safe root / Gate 3 input]
       broker_reports_gate3_context_manifest_v0
  -> [Gate 3 private, future] reconciled events + intermediate ledgers + traces
  -> [Gate 3 safe root, future] case-assembly/case-package refs
  -> [Gate 4 private, future] declaration model + review state
  -> [separately authorized, future] export/output
```

Private descendants are never copied into safe manifests. Cross-gate consumers
use opaque refs and ArtifactResolver. Scope expansion creates a new terminal
run and a new immutable handoff root; it does not mutate an already ready
manifest.

## 5. Component and contract ownership matrix

| Component or artifact family | Single owner | Role | Authority / visibility | Consumer | Current status |
| --- | --- | --- | --- | --- | --- |
| `broker_reports_gate1_pipe` bundle | Gate 1 adapter | OpenWebUI intake/orchestration | Maintained runtime; safe chat projection plus private descendants | Gate 1 factories | Implemented, deployed, parity-proven |
| `broker_reports_gate2_source_fact_pipe` and domain bundle | Gate 2 adapters | OpenWebUI source-fact execution | Maintained runtime; safe summaries/private facts | Gate 2 factories | Implemented, deployed, parity-proven |
| Gate-specific runtime factories | The gate whose artifact/decision they create | Factory-only routing for normalizers, packages, validators, stitchers and manifest creation | Normative runtime entrypoints; cannot bypass the owning gate contract | Same-gate runtime or next-gate handoff | Implemented for Gate 1/Gate 2 and the Gate 3 input manifest |
| Format profilers, `CsvSupportedProfileFactory`, `FullSourceArtifactFactory` | Gate 1 | Format detection and representation preservation | Normative runtime; private source content | DCP/Gate 2 | Implemented; acceptance varies by format |
| Normalized text/table/source payload and unit contracts | Gate 1 | Source representation | Versioned/private; table projection is structural, not financial | Gate 2 | Implemented for supported paths |
| PDF Table Intake Gate 1 | Gate 1 local child capability | PDF page -> private raster candidates | Versioned/private; local gate terminology | Downstream Gate 1 table normalizer | Closed for accepted bounded scope |
| Bounded visual-table VLM adapters | Gate 1 | One declared page/crop -> typed structural proposal | Production Gemini/OpenAI transport; proposal-only, private | Deterministic visual validator | Maintained production policy |
| PDF hybrid, structural-repair, dual-oracle and direct-PDF contours | Gate 1 research/shadow unless promoted | Alternative structural reconstruction evidence | Evidence-only or default-off; not product authority | Research/quality decisions | Research-only, rejected or unclosed by contour |
| `domain_context_packet_v0` | Gate 1 | Safe handoff root and stage readiness | Normative safe-internal refs | Gate 2 | Implemented |
| `gate1_issue_ledger_v0` | Gate 1 | Source/intake issue authority | Normative safe-internal; carried forward by ref | Gates 2-4 | Implemented |
| Candidate sets, relations and binding validation | Gate 2 | Reproducible source-local semantic selection | Versioned; private candidates/safe validation | Source-fact materializer | Implemented |
| Source-fact runs, packages, facts and contracts | Gate 2 | Source-local financial interpretation | Versioned; facts private, runs/summaries safe | Gate 3 | Implemented; bounded scopes proven |
| Source-fact validation and stitching | Gate 2 | Terminal acceptance and coverage ownership | Deterministic normative runtime; safe validation/private fact refs | Gate 3 manifest factory | Implemented |
| `broker_reports_gate3_context_manifest_v0` | Gate 2 exit boundary | Checked index of a declared Gate 2 scope | Normative safe-internal root; no copied values | Gate 3 | Implemented and CSV-bounded stage-proven |
| Intermediate ledgers, reconciliation and event assembly | Gate 3 | Cross-document case assembly | Future private normative runtime; current contract is proposal | Gate 4 | Not implemented |
| Declaration model and review state | Gate 4 | Tax/declaration preparation | Draft/proposal, private by default | Specialist/export | Not implemented |
| Managed metadata/clarification prompts | Gate 1 | Bounded document metadata assistance | Versioned prompt contracts; registry delivery is platform service | Gate 1 validator | Implemented/deployed |
| Managed source/domain prompts | Gate 2 | Source-local semantic proposals | Versioned prompt contracts; deterministic validators remain authority | Gate 2 runtime | Implemented/deployed |
| ArtifactStore, ArtifactResolver, retention and purge | Cross-cutting platform | Persistence, isolation, lifecycle and ref resolution | Platform capability; no business semantics | All gates | Implemented for current runtime contours |
| Provider registry, adapters and structured model client factory | Cross-cutting platform with Gate 2 policy contracts | Approved transport/schema projection and execution metadata | Platform transport; cannot accept business output | Gate-specific runtimes | Implemented/deployed for current profiles |
| Bundle builders, update scripts, parity verifier and operator runbooks | Cross-cutting delivery | Build/deploy/verify controlled runtime paths | Evidence/operations only; never domain authority | Release/operator process | Implemented |
| Dated proof/closure reports | Evidence | Record one revision, scope and outcome | Evidence-only | Human audit | Preserved |

No maintained component has two business owners. Cross-cutting platform
services own mechanics only; the calling gate owns the business contract.

### Physical code-isolation boundary

The maintained Python implementation enforces the ownership map as follows:

| Boundary | Maintained code surface | Enforced rule |
| --- | --- | --- |
| Gate 1 -> Gate 2 | `gate1_public_contracts.py`, versioned DCP/handoff artifacts and `ArtifactResolver` | Gate 2 may import the public Gate 1 surface and resolve validated refs; it may not import format-parser internals or inspect SQLite directly. |
| Gate 2-owned table packages | `gate2_table_packages.py` | Financial/source-fact package construction and validation belong to Gate 2. `table_projection.py` keeps only a lazy compatibility export for older imports. |
| Gate 2 -> Gate 3 | `gate3_context_manifest.py` | The Gate 2 exit factory creates one immutable, validator-recomputed manifest ref. Future Gate 3 code must start from this manifest, not from Gate 1 or Gate 2 internals. |
| Cross-cutting persistence | `ArtifactStorePort`, `ArtifactResolver`, SQLite adapter | Gate runtimes depend on the domain-neutral port/resolver. The adapter permits idempotent replay of identical content but rejects semantic overwrite of an existing artifact id. |
| Gate execution history | terminal Gate 2 run artifacts | Intermediate run states remain in process memory; one terminal run record is appended. Scope expansion or rerun creates new artifact ids. |
| Delivery | bundle builder, architecture test and parity verifier | Bundles include the same public boundary modules; tests fail on private cross-gate imports, store bypass, reverse dependencies or overwrite paths. |

The historical package name `broker_reports_gate1` and top-level compatibility
exports are not ownership authority. They remain to avoid a destructive public
rename; the module-level imports, factories, contracts and artifact writers are
the enforced boundary.

## 6. Readiness and closure model

The allowed status vocabulary is:

`not started`, `research only`, `implemented`, `contracted`,
`unit proven`, `stage proven`, `product accepted`, `partially closed`,
`closed for bounded scope`, `closed` and `superseded`.

| Surface | Current status | Exact claim |
| --- | --- | --- |
| Global Gate 1 | Implemented; partially closed | Runtime exists. Named format/sub-capability closures do not imply universal format support. |
| CSV v1 normalization | Closed for bounded supported profile | Whole accepted CSV representation is normalized under declared limits. |
| PDF Table Intake local Gate 1 | Closed | Table regions become private raster candidates; no cells or financial meaning are claimed. |
| Canonical visual-table reconstruction | Maintained repository runtime, default-off; atomic stage delivery remains pending | Recovered Gemini/OpenAI adapters process one declared crop under a versioned dual-provider policy. Agreement remains review-only; only deterministic validation plus source accounting may promote cells/table JSON. |
| Global Gate 2 | Implemented; partially closed | Bounded typed verticals pass. Whole-document/full-corpus/all-format semantic coverage is not closed. |
| CSV pre-Gate-3 vertical | Closed for bounded scope | One selected segment is terminal and validated; 343 segments are explicit deferred scope. |
| Gate 3 context manifest | Implemented; stage proven for bounded CSV scope | Ready means the declared Gate 2 graph is acceptable as Gate 3 input. |
| Global Gate 3 business logic | Not started; contracts proposed | No ledger, cross-document reconciliation or deterministic case calculation runtime exists. |
| Global Gate 4 | Not started; draft/proposal contracts | No tax/declaration/review/export runtime is accepted. |

### Readiness flag rules

| Name | Canonical meaning |
| --- | --- |
| `gate2_boundary_ready` in PDF Table Intake | Local raster-ref readiness for a downstream Gate 1 table normalizer. It is not global Gate 2 readiness. |
| DCP `stage_readiness.source_fact_extraction` | Gate 1's stage-specific permission for Gate 2 to inspect selected refs. It is not Gate 2 completion. |
| `gate3_handoff_ready` | Historical compatibility boolean on earlier Gate 2 outputs. It is not authoritative and is ignored by the manifest factory. |
| `gate3_input_status=ready` | Deterministically recomputed readiness of exactly the manifest-declared Gate 2 scope. It is not whole-document, whole-case, ledger, tax or declaration readiness. |

Readiness claims must always name the scope, terminal validator, coverage
boundary, access/retention state and next consumer.

## 7. Terminology and compatibility register

| Existing term/name | Canonical interpretation | Compatibility action |
| --- | --- | --- |
| Stage 2 Gate 1..9 | Repository-wide governance/implementation conditions | Keep names; never use them as Broker Reports product-gate numbers. |
| Global Broker Reports Gate 1..4 | The only global Broker Reports product sequence | Use for all new product architecture and goal assignment. |
| Gate 1.5 | Historical label for LLM-assisted document metadata/passport work wholly inside global Gate 1 | Keep in old filenames/contracts where needed; always label it a local compatibility sub-stage, not a global gate. |
| PDF Table Intake Gate 1 | Local child gate `PDF -> private raster candidates` inside global Gate 1 | Keep versioned names; always include parent and bounded meaning. |
| Gate 2 handoff / `gate2_handoff_v0` | Gate 1 output/input manifest for Gate 2 | Keep contract name; it does not prove Gate 2 ran. |
| CSV pre-Gate-3 vertical | A vertical closure spanning Gate 1 normalization, bounded Gate 2 interpretation and Gate 3 input-manifest creation | Keep report/contract names; never call it Gate 3 business closure. |
| `broker_reports_gate3_context_manifest_v0` | Gate 2-produced exit manifest and Gate 3 input root | Keep versioned name. “Gate 3” names the consumer, not the producing business gate. |
| `gate3_handoff_ready` | Legacy local readiness hint | Preserve field for compatibility; do not use as authority. |
| `STAGE2_GATE2_ARCHITECTURE_CLOSURE_READY` | Historical architecture/proof marker for the Gate 2 implementation slice | Keep as evidence; it is not global Gate 2 product acceptance. |
| Vertical proof/closure | Evidence for one explicit format/domain/scope crossing gates | Keep dated labels; never infer whole-gate closure. |
| `gate3_ledger_candidate` and similar forward hints | A downstream-use restriction/hint on a Gate 2 artifact | It is not a Gate 3 ledger item or acceptance decision. |

Versioned contracts are not renamed for cosmetic consistency. New docs must
use the canonical global term first and place historical/local names in
parentheses with their parent gate.

## 8. Superseded boundaries and research contours

The following are not global product gates:

- early “Gate 1.5” passport planning;
- PDF Table Intake's local Gate 1;
- PDF hybrid/table vertical steps numbered inside their own contracts;
- direct whole-PDF, compact JSON/CSV, dual-VLM and structural-repair research
  arms;
- Paddle/local-OCR proof and worker experiments, which remain offline evidence;
- dated “pre-Gate-3” or “vertical closure” proof labels;
- Stage 2 implementation gates.

Research may inform a versioned contract but cannot override it. Historical
reports remain in place and are not deleted.

## 9. Migration and future assignment

The original architecture finalization was documentation-only and
compatibility-safe:

- no runtime behavior changes;
- no deployed Function bundle changes;
- no public/versioned artifact rename;
- no schema migration;
- no validator weakening;
- no Gate 3 or Gate 4 financial functionality.

The subsequent code-isolation enforcement in revision `b61b509` changed
runtime internals and Function bundles without changing public/versioned
schemas or business meaning. It extracted the public Gate 1 surface, moved the
Gate 2 table-package implementation to its owner, routed Gate 2 reads through
the resolver and made artifact creation append-only/immutable. The dated code
audit below is the authority for that enforcement and its stage proof.

Maintained documentation must link to this entry point and use the four-gate
ownership split. Historical names remain aliases with the meanings above.

New work is named:

```text
Broker Reports Global Gate <N> — <owned outcome> — <bounded scope>
```

The next development goal should be:

```text
Broker Reports Global Gate 3 — Bounded Case Assembly and Intermediate Ledger v0
```

It belongs to Gate 3. It must start from one ready
`broker_reports_gate3_context_manifest_v0`, produce a traceable bounded
case-assembly/ledger artifact and stop before tax methodology, declaration
mapping or export.

## 10. Verification and evidence

Current verification and the exact documentation refinements are recorded in
the
[2026-07-18 architecture/domain ownership finalization report](../../reports/2026-07-18/OPENWEBUI_BROKER_REPORTS_GATE_ARCHITECTURE_AND_DOMAIN_OWNERSHIP_FINALIZATION.report.md).

Physical implementation isolation, the violation register, mutation proof and
post-refactor stage evidence are recorded in the
[2026-07-18 gate contract isolation audit](../../reports/2026-07-18/OPENWEBUI_BROKER_REPORTS_GATE_CONTRACT_ISOLATION_AUDIT_AND_ENFORCEMENT.report.md).

Bounded closure evidence remains separate:

- [CSV pre-Gate-3 vertical closure](../../reports/2026-07-17/OPENWEBUI_BROKER_REPORTS_CSV_PRE_GATE3_VERTICAL_CLOSURE.report.md);
- [PDF Table Intake local Gate 1 closure](../../reports/2026-07-17/OPENWEBUI_BROKER_REPORTS_PDF_TABLE_INTAKE_GATE1_CLOSURE.report.md);
- [single-PDF whole-document Gate 2 bounded proof](../proof/BROKER_REPORTS_SINGLE_PDF_WHOLE_DOCUMENT_GATE2_E2E.md).

## 11. Final status

```text
BROKER_REPORTS_GATE_ARCHITECTURE:
VERSIONED_AND_AUTHORITATIVE

DOMAIN_OWNERSHIP:
CONSISTENT

LOCAL_GLOBAL_GATE_TERMINOLOGY:
RECONCILED

DOCUMENTATION_RUNTIME_ALIGNMENT:
PROVEN

VISUAL_RECOVERY_PRODUCTION_POLICY:
GEMINI_AND_OPENAI_VLM

PADDLE_LOCAL_OCR_PRODUCTION_STATUS:
OUT_OF_SCOPE

MODEL_CANONICAL_AUTHORITY:
ZERO

FUTURE_GATE_ASSIGNMENT_MODEL:
READY
```
