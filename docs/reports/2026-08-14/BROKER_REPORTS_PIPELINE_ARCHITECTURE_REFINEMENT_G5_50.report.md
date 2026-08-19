# Broker Reports — Pipeline Architecture Refinement G5.50

Date: `2026-08-14`

Goal: `G5.50`

Status: `ARCHITECTURE_REFINEMENT_CORE_PROVEN`

```text
PIPELINE_MENTAL_MODEL_PUBLISHED
DOMAIN_CONTRACTS_REFINED
ARCHITECTURE_AUTHORITY_HIERARCHY_PROVEN
EXECUTABLE_DOMAIN_GUARDRAILS_PROVEN
COLD_AGENT_NAVIGATION_PROVEN
ARCHITECTURE_REFINEMENT_CORE_PROVEN
PHYSICAL_BOUNDARY_DEBT_REMAINS=[gate5_end_to_end_full_target_xml]
```

`ARCHITECTURE_REFINEMENT_COMPLETE` is deliberately not claimed.

## Outcome

The repository now has one current short navigation authority:
`docs/stage2/contracts/BROKER_REPORTS_PIPELINE_GATES.v1.md`. It publishes the
required Gate 1 through Projection flow, domain contract cards, Evidence Demand
loop, provider classes, authority hierarchy, cold-agent decisions and STOP
rules. The longer authority index is subordinate to this map; dated reports
remain evidence rather than current architecture authority.

G5.46 and G5.47 source-recovery documents are explicitly historical. The
current Evidence Demand route is:

```text
Gate5EvidenceDemandFactory
-> Gate3EvidenceDemandPortFactory.create
-> existing Gate3 bounded labeling
-> Gate4 fact publication
-> deterministic Gate5 replay
```

Gate 5 does not own Canonical reading, context selection or source-document
provider calls. The removed `gate3_evidence_demand_adapter` name is no longer a
runtime, bundle or public-package surface.

## Executable guardrails

Architecture policy v4 publishes the domain sequence, owner map, permitted LLM
boundary classes and an exact inventory of maintained structured-model call
sites. Each call site states the uncertainty removed and strict output
contract. Import tests fail on:

- Gate 3 reverse dependencies into Gate 4, Gate 5 or declaration/projection;
- Gate 5 Canonical, source-unit, chunking, provider or Gate 3 implementation
  imports outside the one compatibility-only orchestrator;
- Projection imports of Tax Model implementations, methodology, evidence
  review or Gate 4 source facts;
- an unclassified maintained structured-model call site;
- a second compatibility exception.

The public Evidence Demand port and `declaration_semantics` boundary are also
included in generated OpenWebUI bundles, preventing workspace-only success.

## Concrete boundary correction

`gate5_declaration_projection.py` previously imported and invoked the income
group Tax Model implementation directly. The target-independent
`DeclarationSemanticsIncomeGroupRuntimeFactory.create` owner now performs that
handoff. Projection consumes its values and traces and remains
representation-only. The owner lazily resolves the existing Tax Model factory
to avoid reintroducing the historical package import cycle.

## Cold-agent proof

Contract tests freeze all three navigation outcomes:

1. Missing `SECURITY_PURCHASE.currency` routes from Gate 5 Evidence Demand to
   the public Gate 3 port, Adaptive Context, Gate 3, Gate 4 and Gate 5 replay.
2. Residency requires factual human evidence followed by deterministic
   methodology; the LLM does not decide residency.
3. A missing XML value is repaired at the Declaration Semantics owner; the
   projector does not calculate or infer it.

## Verification

- Focused architecture, bundle and projection regression: `123 passed`.
- Full relevant Gate 3/4/5 and architecture regression: `716 passed`.
- Python compile check: passed.
- Ruff on the changed architecture/runtime/test files: passed.
- `git diff --check`: passed; line-ending notices only.
- Provider calls: `0`.
- Real/customer corpus mutations: `0`.
- Product activation, commit, push and PR: not performed.

The package-wide `broker_reports_gate1/__init__.py` still has a pre-existing
unused-reexport Ruff baseline. G5.50 did not turn that unrelated cleanup into a
large public-API rewrite; behavioral and architecture tests cover the added
exports.

## Physical boundary debt

Debt: `broker_reports_gate1/gate5_end_to_end_full_target_xml.py`.

- **Risk:** the Gate 5-prefixed name and its full-pipeline composition imports
  can suggest that Gate 5 owns Canonical/document orchestration.
- **Current consumers:** the product pipe, `gate5_openwebui_product.py`, bundled
  delivery, end-to-end tests and exact G5.35–G5.37 replay surfaces.
- **Why not safely removable here:** moving or renaming this roughly 2,100-line
  compatibility orchestrator changes production imports, bundle ordering and
  frozen replay consumers. That is a destructive package migration rather than
  architecture refinement.
- **Recommended migration:** in a separately authorized goal, create a
  product-composition owner, retain a temporary compatibility shim, migrate
  product/bundle/test consumers, prove installed/bundled parity, and delete the
  shim only after the consumer inventory is empty.

The architecture test allowlists exactly this one module and forbids any new
exception or new cross-domain import inside it.

## KISS check and scope stop

G5.50 refined one existing entry map, introduced one public Evidence Demand
port and one small declaration-semantics owner justified by an observed
boundary violation. It added no framework, database, DSL, provider path, tax
feature, recovery mechanism or UI workflow.

Next allowed goal: `G5.51 — Product Composition Physical Boundary Migration`.
It is proposed only; it was not started.
