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
- The closed target for every field exposed to the financial semantic model is
  the versioned
  [LLM Semantic Context](../../docs/stage2/contracts/BROKER_REPORTS_GATE2_LLM_SEMANTIC_CONTEXT.v1.md).
  Context candidates remain inside the existing V6 packet owner. Global refs,
  hashes, provenance and storage IDs stay code-only.
- The model selects only the allowed
  [semantic choice](../../docs/stage2/contracts/BROKER_REPORTS_GATE2_FINANCIAL_SEMANTIC_CHOICE_V6.md).
  It never owns source refs, provenance, retention, records or bindings.
- The active V6 Choice still requires exact option IDs. A local-alias Choice
  candidate is a separate versioned contract change; never hide it inside a
  packet refactor or provider adapter.
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
- Keep private/customer inputs, provider payloads and exact evidence outside
  Git; commit only privacy-scanned safe projections.
- Do not make a provider call until the local seam smoke passes and the task
  explicitly authorizes the call. Do not mutate stage without explicit scope.

Useful test anchor:

```powershell
python -m pytest -q tests/test_broker_reports_gate_architecture.py --tb=short
```
