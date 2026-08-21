# Broker Reports Service Guidance

These instructions apply to this service, its tests, scripts and generated
OpenWebUI Action bundles.

## Start here

1. Read the
   [architecture authority map](../../docs/stage2/contracts/BROKER_REPORTS_ARCHITECTURE_AUTHORITIES.md).
2. Read the relevant versioned contract; do not infer it from a report, test
   fixture or generated bundle.
3. Search maintained source and tests for the existing owner before creating a
   component, schema, validator, adapter, factory or execution path.
4. Use the public factory/entrypoint named by the authority map.

The current [Pipeline Gates v1](../../docs/stage2/contracts/BROKER_REPORTS_PIPELINE_GATES.v1.md)
is normative for gate placement and product boundaries. The older global gate
architecture is superseded for numbering and remains migration context.

## Context Bootstrap

Before implementation, add at most 15 lines to the working plan or PR body:

- target domain and relevant authority-map rows;
- normative contracts read;
- current sole owner and consumers;
- compatibility and historical paths;
- exact component planned for change;
- documentation impact;
- why the change does not create a second authority.

Build this bootstrap from repository truth, not agent memory. Do not create a
separate bootstrap report.

## Non-negotiable boundaries

- Compatibility wrappers validate only what their pinned version requires and
  otherwise delegate. They do not become current write or policy authorities.
- Generated `openwebui_actions/*_bundled.py` files are closed-world build
  outputs, not maintained authorities. Change maintained source and rebuild.
- Provider request projection, response parsing, error interpretation and
  usage normalization stay in provider adapters and the canonical model-client
  path.
- Financial type, role, ambiguity and lifecycle meaning stays in the
  [Financial Semantic Pack](../../docs/stage2/contracts/BROKER_REPORTS_FINANCIAL_SEMANTIC_PACK.v1.md).
- The implemented candidate surfaces are the historical
  [LLM Semantic Context v1](../../docs/stage2/contracts/BROKER_REPORTS_GATE2_LLM_SEMANTIC_CONTEXT.v1.md)
  and the historical non-active completeness sidecar for
  [LLM Semantic Context V2.0](../../docs/stage2/contracts/BROKER_REPORTS_GATE2_LLM_SEMANTIC_CONTEXT.v2.md).
  V2.0 is the exact implemented non-active completeness baseline, not the
  current minimal model-surface target. Its builder remains version-pinned
  historical evidence and is not called by the current Packet path. The sole
  current minimal sidecar is
  [Context V2.1](../../docs/stage2/contracts/BROKER_REPORTS_GATE2_LLM_SEMANTIC_CONTEXT.v2.1.md);
  its candidate and private exact receipt are built only by the existing V6
  packet owner through the existing projection owner. Neither version is a
  request or runtime authority. Global refs, hashes, provenance and storage
  IDs stay code-only.
- The
  [Minimal Model Surface v1](../../docs/stage2/contracts/BROKER_REPORTS_GATE2_MINIMAL_MODEL_SURFACE.v1.md)
  is the GOAL 5 field-eligibility contract inside the existing Semantic
  Matcher boundary. GOAL 7 implements its inactive managed projection and
  GOAL 8 implements one inactive Packet candidate/private receipt. The later
  governing program authorizes GOAL 9 to implement the inactive
  [Local Choice V2.1 response profile](../../docs/stage2/contracts/BROKER_REPORTS_GATE2_FINANCIAL_SEMANTIC_LOCAL_CHOICE.v2.1.md)
  in the existing Choice owner. GOAL 10 adds the inactive provider-neutral
  sealed request; GOAL 11 adds only a zero-call three-provider local proof.
  GOAL 12 adds only the frozen qualification transport/evidence path governed
  below. Product runtime transport and activation remain absent. The additive
  [Outcome Taxonomy v1](../../docs/stage2/contracts/BROKER_REPORTS_GATE2_OUTCOME_TAXONOMY.v1.md)
  completes GOAL 6: the four zero-choice plausible-type counts are `2,1,1,1`,
  three historical reasons are corrected only in the versioned audit
  successor, and catalog v2 adds inactive candidate reason
  `single_registry_type_no_safe_record`. Historical manifests/catalog v1,
  active V6 Choice, Prompt and Pack stay immutable. GOAL 7 is implemented as
  inactive same-family v3 plus one exact minimal profile in the existing
  loader and shared V5-named projection owner. It has no Packet/request
  consumer outside that Packet construction. GOAL 8 builds only one
  non-active V2.1 candidate plus private mapping receipt in the existing
  Packet factory.
- GOAL 9 adds only the versioned inactive V2.1 response schema/parser through
  `Gate2FinancialSemanticV6ChoiceContractFactory.create`. `choice_N` restores
  only through `context_v2_mapping_receipt.choice_restoration`. Active V6
  Choice, historical Local Choice v1 and Expansion remain unchanged.
- GOAL 10 adds only
  `Gate2FinancialSemanticV6ContextLinterFactory.create_context_v2_1` under the
  existing linter authority; historical `create` remains byte/behavior exact.
  The new method uses the inactive request profile
  `broker_reports_gate2_financial_semantic_v6_request_v2_1_candidate`. It
  consumes the exact Prompt, Context V2.1 candidate, Choice-owned schema and
  packet-owned private mapping receipt; it emits
  `broker_reports_gate2_llm_semantic_context_v2_1_sealed_request_receipt_v1`.
  The provider-neutral response wrapper has exactly `type` and `json_schema`,
  with nested `strict` and `schema`; `json_schema.name` is forbidden.
- GOAL 11 composes the existing linter, request builder, provider adapters,
  V2.1 Choice parser, Expansion/validator/materializer, Financial Domain
  persistence and transparent report projector. The proof is synthetic,
  non-active and transport-ineligible. Candidate-only extraction requires
  exactly one terminal simulated provider envelope. The complete prepared
  request must be rebuilt through the canonical request builder and repository
  adapter and compared as one exact contract. The proof must never call
  transport, repair semantics, retry or fall back.
  Provider-specific `choice`/`reason` schema projection is bound to the
  non-active identity
  `broker_reports_gate2_context_v2_1_local_schema_projection_v1`; canonical
  adapter versions remain unchanged. Exact replay must serialize and restore
  `Gate2FinancialSemanticV6DecisionEvidenceFactory.create_context_v2_1_candidate`
  output, then compare the validated sealed request, trusted profile, projection
  policy, exact prepared request and provider-visible schema before
  reconstructing materialization and snapshot. Public
  `Gate2FinancialSemanticV6TransparentSmokeReportFactory.create_context_v2_1_provider_case`
  returns only a raw closed projection and must not mint report evidence.
  `Gate2FinancialSemanticV6ContextV21ProviderProofFactory.create_case` must
  create an unissued full proof, independently recompute it, require exact
  equality, and only then invoke the private authority that issues the opaque
  immutable case-evidence token. Independent full-proof validation follows.
  The aggregate accepts only the issued token; raw or resealed proof
  dictionaries must fail closed.
- GOAL 12 is the separately versioned, qualification-only
  [Context V2.1 Budget Model Smoke](../../docs/stage2/contracts/BROKER_REPORTS_GATE2_CONTEXT_V2_1_BUDGET_MODEL_SMOKE.v1.md).
  Its immutable plan is issued only by
  `Gate2FinancialSemanticV6ContextV21BudgetSmokePlanFactory.create`; its thin
  coordinator reuses the existing linter, request builder, economy budget,
  provider adapter/client, Choice, Expansion/materialization, evidence and
  report owners. It must not become a product runtime or second qualification
  framework.
- The frozen provider-major ceiling is 12 slots: OpenAI
  `gpt-5.4-nano-2026-03-17`, Anthropic
  `claude-haiku-4-5-20251001` and Google
  `models/gemini-3.1-flash-lite`, each over the four audited Context V2.1
  semantic cases. Retry, repair, fallback and runtime model/parameter
  overrides are zero. Google is a stable selector without a proven dated
  immutable identity and must fail before transport unless that proof exists
  before its first submission.
- Every allowed GOAL 12 transport requires a clean committed pre-call plan and
  a real green `broker-reports-ci` GitHub Actions check for the exact open,
  non-draft PR head and exact workflow/run/job provenance. Its frozen policy is
  `direct_exact_provider_http_via_openwebui_connection_v1`: OpenWebUI supplies
  only the enabled Admin connection and credential; the qualification client
  sends the sealed request directly to the canonical provider endpoint with
  redirects and ambient proxies denied, a `180` second timeout, a `1,048,576`
  byte response cap and retry `0`.
- The HMAC-sealed external private ledger consumes each slot before network,
  after a permanent per-slot `O_EXCL` claim has been flushed. Resume never
  resubmits a claimed or consumed slot. A nonblocking OS-backed lease under
  git-common metadata serializes the complete execute/resume section before
  auth, state recovery or transport and is released by descriptor close or
  process death. One persistent safe execution-owner claim binds the plan/head
  and hashed external state directory;
  an atomic annotated-tag ref
  `broker-reports-goal12-execution-lock-<plan_hash>` binds the same owner across
  clones and must never be deleted. A second `--execute` cannot reset the
  submission budget by choosing a new directory. Exact provider envelopes
  remain outside Git. Safe and transparent synthetic reports are hash-linked,
  `active=false`, and keep `production_admissions=[]`.
- GOAL 12 completed with `8` submissions and `8` responses. OpenAI and
  Anthropic passed the technical smoke but failed the semantic smoke; Google
  failed closed before transport in all four slots because its immutable dated
  model identity was not proven. Retry, repair, fallback and semantic repair
  remained zero. No provider/model is benchmark-eligible, so GOAL 13 must not
  start without an explicit new candidate or policy decision. Preserve the
  external private ledger and permanent execution-lock tag as audit evidence.
- GOAL 5 selects existing managed strings rather than authoring markers:
  `positive_signal` is exact Pack `examples[0]`, `negative_signal` is exact
  `counterexamples[0]`, nearest distinction is the unique direct rule against
  the only other current visible type, and reason `use_when` is the exact first
  sentence of catalog `meaning` under the contract's closed sentence rule.
  GOAL 7 implements only those mappings; its Python reads managed snapshots
  and does not embed replacement wording. Packet/Prompt/adapter code may not
  copy them. The current V2.1 task is the new contract-owned instruction, not
  the historical V2.0 complete-prebound task.
- The historical Slim View v2, alias receipt and
  [Local Choice](../../docs/stage2/contracts/BROKER_REPORTS_GATE2_FINANCIAL_SEMANTIC_LOCAL_CHOICE.v1.md)
  remain non-active outputs. Context V2.0 has a non-active packet renderer and
  private mapping receipt, but no V2.0 local Choice profile/parser, linter,
  provider request, evidence persistence or replay exists. Context V2.1 has
  one non-active candidate, private exact receipt and Choice-owned inactive
  response profile/parser plus one linter-owned inactive provider-neutral
  sealed request and private sealed-request receipt. GOAL 11 proves local
  OpenAI/Anthropic/Google projection, extraction, candidate-only Expansion,
  private-evidence serialize/restore/replay, materialization and Financial
  Domain persistence/restore/reconstruction. GOAL 12 alone may consume the
  sealed candidate through its explicit qualification profile. Product runtime
  continues to consume only `packet.payload` and exact-ID Choice until a
  separately qualified activation GOAL changes that authority.
- Any historical Slim + Local Choice transport must first use
  `Gate2FinancialSemanticV6ContextLinterFactory.create`; the existing request
  builder rejects the candidate profile without its exact sealed lint receipt.
  The linter validates the complete request but does not own packet, Prompt,
  Choice, provider projection, canonical expansion or materialization.
- Context V2.1 construction must use the same authority's additive
  `create_context_v2_1` method and its exact V2.1 request profile. Complete
  request bytes must be at most `4 500`; the current governed maximum is
  `3 522`. Mapping coverage is `156/156`: 45 source occurrences, 20
  structures, 20 type mappings, 12 choice restorations and 59 binding rows.
  GOAL 11 uses
  `Gate2OpenWebUIRequestBuilder.build_from_sealed_context_v2_1` and
  `Gate2FinancialSemanticV6ContextV21ProviderProofFactory.create_case` only
  after the sealed request validates. Provider calls and runtime activation
  remain zero.
- The historical Slim diagnostic GOAL 4 consumed its one bounded
  six-submission run on the two
  frozen smoke cases. The terminal receipt is failed because Haiku missed the
  unclassified reason; do not rerun, resume, expand to the full benchmark or
  start conditional type-card work from that authorization. Preserve the exact
  receipt/report and require a separately versioned, explicitly authorized
  corrective GOAL.
- The model selects only the allowed
  [semantic choice](../../docs/stage2/contracts/BROKER_REPORTS_GATE2_FINANCIAL_SEMANTIC_CHOICE_V6.md).
  It never owns source refs, provenance, retention, records or bindings.
- The active V6 Choice still requires exact option IDs. Its versioned
  local-alias candidate normalizes through the existing Choice/expansion
  authorities and must never be activated through a packet refactor or
  provider-adapter semantic rewrite.
- Context V2.1 accepts the three governed reason codes only in its inactive
  profile. The third reason is not yet admitted by active V6
  Expansion/materialization; do not claim active parity for it.
- Technical preparation seals the
  [Evidence Bundle](../../docs/stage2/contracts/BROKER_REPORTS_GATE2_FINANCIAL_EVIDENCE_BUNDLE.v1.md);
  the [Candidate Compiler](../../docs/stage2/contracts/BROKER_REPORTS_GATE2_FINANCIAL_CANDIDATE_COMPILER.v1.md)
  creates complete code-owned options.
- Canonical validation and materialization follow
  [Generic Materialization](../../docs/stage2/contracts/BROKER_REPORTS_GATE2_GENERIC_FINANCIAL_MATERIALIZATION.v1.md).
- The active ordinary-security-trade route is
  `CanonicalArtifactV1 -> exact qualified mapping -> Source Observations ->`
  `deterministic runtime records -> Gate4FinancialCaseFactV2 -> deterministic`
  `Gate 5`. Enter only through
  `OrdinaryTradeProductionRuntimeFactory.create`. Current Gate 3 type/role
  model passes, `FinancialAnnotationsV2` reads and
  `Gate4FinancialCaseRuntimeFactory.create` are disabled for this route and are
  retained only as an explicit deployment rollback, never a semantic fallback.
- The current fact boundary is
  [Gate 4 Financial Case Fact v2](../../docs/stage2/contracts/BROKER_REPORTS_GATE4_FINANCIAL_CASE_FACT.v2.md).
  `Gate4OrdinaryTradeCandidateRuntimeFactory.create` is the active ordinary-
  trade producer. The historical field `gate3_binding` binds the ordinary
  projection artifact and Canonical identity on this route; its name does not
  prove Gate 3 execution.
- Qualified mappings may use only exact title/header/column structure and exact
  source enum literals. Broker, year, filename, fuzzy matching, inferred table
  continuation and runtime model calls are forbidden. Unknown/incomplete rows
  remain `RELEVANT_UNMAPPED` and cannot reach Gate 5.
- Gate 5 must start from Fact v2 and must not cross back into broker source,
  CanonicalArtifact, Source Observations, model output, Gate 3 targets or
  physical SQL parsing. Read the current
  [Gate 4 handoff](../../docs/stage2/contracts/BROKER_REPORTS_GATE4_HANDOFF.v1.md)
  before changing the boundary.

## Change and proof

- In the existing PR body, answer only these documentation questions:
  1. Which authority or contract is touched?
  2. Is its documentation still exact?
  3. Was a new authority introduced, and why could the existing owner not be
     used?
- Update the authority map and relevant contract documentation in the same PR
  when authority or contract meaning changes. Use `COMMENTS_ONLY` when only
  local routing guidance changes. If meaning is unchanged, no documentation
  update or separate approval is required.
- Add or update executable architecture tests for a boundary change. Assert
  behavior/import structure, not report text or snapshots alone.
- Run focused tests and the full relevant service suite from this directory
  before PR review.
- Rebuild generated bundles deterministically when their maintained inputs
  change, then run bundle parity tests.
- Keep private/customer inputs, provider payloads and non-allowlisted exact
  evidence outside Git. Commit only contract-approved, privacy-scanned safe
  projections; exact readable context is allowed only for explicitly
  allowlisted frozen synthetic evidence.
- Do not make a provider call until the local seam smoke passes and the task
  explicitly authorizes the call. Do not mutate stage without explicit scope.

Useful test anchor:

```powershell
python -m pytest -q tests/test_broker_reports_gate_architecture.py --tb=short
```
