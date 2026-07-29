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

The [global gate architecture](../../docs/stage2/blueprints/BROKER_REPORTS_GATE_ARCHITECTURE.md)
remains normative for gate placement and product boundaries.

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
  in the existing Choice owner. Complete-request linter, request, provider
  route and activation remain absent. The additive
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
  Choice, historical Local Choice v1, Expansion, linter/request builder,
  adapters and provider route remain unchanged.
- **STOP before GOAL 10:** do not begin the V2.1 linter/sealed request until
  GOAL 9 is fresh-reviewed on its immutable PR head, the real
  `broker-reports-ci` check is green and the PR is merged.
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
  response profile/parser. It still has no V2.1 linter, sealed provider
  request, persistence or replay. Runtime and the current qualification runner
  continue to consume only `packet.payload` and exact-ID Choice until a
  separately qualified activation GOAL changes that authority.
- Any Slim + Local Choice transport must first use
  `Gate2FinancialSemanticV6ContextLinterFactory.create`; the existing request
  builder rejects the candidate profile without its exact sealed lint receipt.
  The linter validates the complete request but does not own packet, Prompt,
  Choice, provider projection, canonical expansion or materialization.
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
- Gate 3 consumes the
  [Financial Domain Query API](../../docs/stage2/contracts/BROKER_REPORTS_GATE2_FINANCIAL_DOMAIN_QUERY_API.v1.md);
  it does not read Gate 1 sources, storage or provider output.

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
